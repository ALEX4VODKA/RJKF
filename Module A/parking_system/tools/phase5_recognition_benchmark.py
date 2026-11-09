"""运行 Phase 5 的 100 张车牌图片准确率与性能验收。"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from statistics import mean, median
from time import perf_counter

import cv2
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = PROJECT_DIR.parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from parking.recognition import LicenseRecognizer, RecognitionError  # noqa: E402
from parking.services.parking_service import normalize_plate  # noqa: E402


ACCURACY_TARGET = 0.90
BATCH_TARGET_MS = 120_000
SINGLE_FRAME_TARGET_MS = 2_000
DEFAULT_MANIFEST = REPOSITORY_DIR / "res" / "phase5_images" / "final" / "ground_truth.csv"
DEFAULT_DATA_ROOT = PROJECT_DIR / "runtime"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "runtime" / "phase5" / "recognition"


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    image_path: Path
    relative_file: str
    expected_plate: str
    plate_color: str
    source: str
    width: int
    height: int


@dataclass(frozen=True)
class BenchmarkResult:
    case_id: str
    file: str
    expected_plate: str
    predicted_plate: str
    candidate_plates: str
    expected_in_candidates: bool
    automatic_success: bool
    exact_match: bool
    confidence: float | None
    elapsed_ms: int
    width: int
    height: int
    plate_color: str
    source: str
    error: str


def _image_size(path: Path) -> tuple[int, int]:
    try:
        payload = np.fromfile(str(path), dtype=np.uint8)
    except OSError as exc:
        raise ValueError(f"图片无法读取：{path}") from exc
    image = cv2.imdecode(payload, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"图片已损坏或格式不受支持：{path}")
    height, width = image.shape[:2]
    return int(width), int(height)


def load_cases(manifest_path: Path, expected_count: int) -> list[BenchmarkCase]:
    manifest_path = manifest_path.resolve()
    if not manifest_path.is_file():
        raise ValueError(f"真值清单不存在：{manifest_path}")
    cases: list[BenchmarkCase] = []
    seen_ids: set[str] = set()
    seen_files: set[Path] = set()
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"id", "file", "plate", "plate_color", "source"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"真值清单缺少列：{', '.join(sorted(missing))}")
        for line_number, row in enumerate(reader, start=2):
            case_id = (row.get("id") or "").strip()
            relative_file = (row.get("file") or "").strip().replace("\\", "/")
            expected_plate = (row.get("plate") or "").strip().upper()
            if not case_id or not relative_file or not expected_plate:
                raise ValueError(f"真值清单第 {line_number} 行存在空的 id/file/plate")
            try:
                normalized = normalize_plate(expected_plate)
            except Exception as exc:
                raise ValueError(
                    f"真值清单第 {line_number} 行车牌无效：{expected_plate}"
                ) from exc
            if normalized != expected_plate:
                raise ValueError(
                    f"真值清单第 {line_number} 行车牌未规范化：{expected_plate}"
                )
            image_path = (manifest_path.parent / relative_file).resolve()
            if not image_path.is_file():
                raise ValueError(f"真值清单第 {line_number} 行图片不存在：{image_path}")
            if case_id in seen_ids:
                raise ValueError(f"真值清单存在重复 id：{case_id}")
            if image_path in seen_files:
                raise ValueError(f"真值清单存在重复图片：{relative_file}")
            seen_ids.add(case_id)
            seen_files.add(image_path)
            width, height = _image_size(image_path)
            cases.append(
                BenchmarkCase(
                    case_id=case_id,
                    image_path=image_path,
                    relative_file=relative_file,
                    expected_plate=expected_plate,
                    plate_color=(row.get("plate_color") or "").strip(),
                    source=(row.get("source") or "").strip(),
                    width=width,
                    height=height,
                )
            )
    if len(cases) != expected_count:
        raise ValueError(f"真值清单应有 {expected_count} 条，实际为 {len(cases)} 条")
    return cases


def run_cases(cases: list[BenchmarkCase], recognizer: LicenseRecognizer) -> tuple[list[BenchmarkResult], int]:
    results: list[BenchmarkResult] = []
    batch_started = perf_counter()
    for index, case in enumerate(cases, start=1):
        started = perf_counter()
        predicted = ""
        confidence: float | None = None
        candidate_plates = ""
        expected_in_candidates = False
        error = ""
        automatic_success = False
        try:
            result = recognizer.recognize_media(case.image_path)
            predicted = result.plate
            confidence = result.confidence
            candidates = tuple(result.candidates) or ()
            plates = list(dict.fromkeys([result.plate, *(item.plate for item in candidates)]))
            candidate_plates = "|".join(plates)
            expected_in_candidates = case.expected_plate in plates
            automatic_success = True
        except RecognitionError as exc:
            predicted = exc.suggested_plate or ""
            confidence = exc.confidence
            error = str(exc)
        elapsed_ms = round((perf_counter() - started) * 1000)
        results.append(
            BenchmarkResult(
                case_id=case.case_id,
                file=case.relative_file,
                expected_plate=case.expected_plate,
                predicted_plate=predicted,
                candidate_plates=candidate_plates,
                expected_in_candidates=expected_in_candidates,
                automatic_success=automatic_success,
                exact_match=automatic_success and predicted == case.expected_plate,
                confidence=confidence,
                elapsed_ms=elapsed_ms,
                width=case.width,
                height=case.height,
                plate_color=case.plate_color,
                source=case.source,
                error=error,
            )
        )
        if index % 10 == 0 or index == len(cases):
            matches = sum(item.exact_match for item in results)
            print(f"进度 {index}/{len(cases)}，精确命中 {matches}", flush=True)
    return results, round((perf_counter() - batch_started) * 1000)


def _group_summary(results: list[BenchmarkResult], field: str) -> dict[str, dict[str, object]]:
    groups: dict[str, list[BenchmarkResult]] = {}
    for result in results:
        groups.setdefault(str(getattr(result, field)) or "unknown", []).append(result)
    return {
        name: {
            "count": len(group),
            "exact_matches": sum(item.exact_match for item in group),
            "accuracy": sum(item.exact_match for item in group) / len(group),
            "automatic_failures": sum(not item.automatic_success for item in group),
        }
        for name, group in sorted(groups.items())
    }


def build_summary(
    results: list[BenchmarkResult], prepare_ms: int, batch_elapsed_ms: int
) -> dict[str, object]:
    if not results:
        raise ValueError("没有可汇总的验收结果")
    exact_matches = sum(item.exact_match for item in results)
    elapsed = sorted(item.elapsed_ms for item in results)
    p95_index = max(0, int(len(elapsed) * 0.95 + 0.999999) - 1)
    full_hd = [
        item
        for item in results
        if (item.width, item.height) in {(1920, 1080), (1080, 1920)}
    ]
    accuracy = exact_matches / len(results)
    expected_in_candidates = sum(item.expected_in_candidates for item in results)
    full_hd_assessment: bool | None = None
    if full_hd:
        full_hd_assessment = all(
            item.elapsed_ms <= SINGLE_FRAME_TARGET_MS for item in full_hd
        )
    return {
        "sample_count": len(results),
        "exact_matches": exact_matches,
        "accuracy": accuracy,
        "expected_in_candidates": expected_in_candidates,
        "candidate_recall": expected_in_candidates / len(results),
        "wrong_default_but_expected_candidate": sum(
            item.automatic_success
            and not item.exact_match
            and item.expected_in_candidates
            for item in results
        ),
        "automatic_successes": sum(item.automatic_success for item in results),
        "automatic_failures": sum(not item.automatic_success for item in results),
        "wrong_automatic_results": sum(
            item.automatic_success and not item.exact_match for item in results
        ),
        "prepare_ms": prepare_ms,
        "batch_elapsed_ms": batch_elapsed_ms,
        "total_with_prepare_ms": prepare_ms + batch_elapsed_ms,
        "mean_image_ms": round(mean(elapsed), 2),
        "median_image_ms": round(median(elapsed), 2),
        "p95_image_ms": elapsed[p95_index],
        "max_image_ms": max(elapsed),
        "within_2000_ms_count": sum(
            item.elapsed_ms <= SINGLE_FRAME_TARGET_MS for item in results
        ),
        "full_hd_sample_count": len(full_hd),
        "full_hd_within_2000_ms_count": sum(
            item.elapsed_ms <= SINGLE_FRAME_TARGET_MS for item in full_hd
        ),
        "acceptance": {
            "accuracy_target": ACCURACY_TARGET,
            "accuracy_pass": accuracy >= ACCURACY_TARGET,
            "batch_target_ms": BATCH_TARGET_MS,
            "batch_pass": batch_elapsed_ms <= BATCH_TARGET_MS,
            "single_frame_1080p_target_ms": SINGLE_FRAME_TARGET_MS,
            "single_frame_1080p_pass": full_hd_assessment,
            "single_frame_note": (
                "仅按实际 1920x1080 或 1080x1920 样本判定；无此尺寸时为 null"
            ),
        },
        "by_plate_color": _group_summary(results, "plate_color"),
        "by_source": _group_summary(results, "source"),
    }


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def _processor_name() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                value, _kind = winreg.QueryValueEx(key, "ProcessorNameString")
                if str(value).strip():
                    return str(value).strip()
        except OSError:
            pass
    return platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "")


def _unique_output_paths(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for suffix in range(100):
        stem = f"recognition_{timestamp}" + (f"_{suffix:02d}" if suffix else "")
        csv_path = output_dir / f"{stem}.csv"
        json_path = output_dir / f"{stem}.json"
        if not csv_path.exists() and not json_path.exists():
            return csv_path, json_path
    raise RuntimeError("无法生成不冲突的验收结果文件名")


def write_results(
    results: list[BenchmarkResult],
    summary: dict[str, object],
    *,
    manifest_path: Path,
    data_root: Path,
    output_dir: Path,
) -> tuple[Path, Path]:
    csv_path, json_path = _unique_output_paths(output_dir.resolve())
    fieldnames = list(asdict(results[0]).keys())
    with csv_path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(result) for result in results)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest": str(manifest_path.resolve()),
        "data_root": str(data_root.resolve()),
        "environment": {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "processor": _processor_name(),
            "logical_cpu_count": os.cpu_count(),
            "opencv_python": _package_version("opencv-python"),
            "hyperlpr3": _package_version("hyperlpr3"),
            "onnxruntime": _package_version("onnxruntime"),
        },
        "recognizer": {"threshold": 0.80, "max_attempts": 3},
        "summary": summary,
        "results": [asdict(result) for result in results],
    }
    with json_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return csv_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-count", type=int, default=100)
    args = parser.parse_args(argv)
    if args.expected_count <= 0:
        parser.error("--expected-count 必须大于 0")

    try:
        cases = load_cases(args.manifest, args.expected_count)
        recognizer = LicenseRecognizer(args.data_root, threshold=0.80, max_attempts=3)
        prepare_started = perf_counter()
        recognizer.prepare()
        prepare_ms = round((perf_counter() - prepare_started) * 1000)
        print(f"模型预加载完成：{prepare_ms} ms", flush=True)
        results, batch_elapsed_ms = run_cases(cases, recognizer)
        summary = build_summary(results, prepare_ms, batch_elapsed_ms)
        csv_path, json_path = write_results(
            results,
            summary,
            manifest_path=args.manifest,
            data_root=args.data_root,
            output_dir=args.output_dir,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"验收无法执行：{exc}", file=sys.stderr)
        return 2

    acceptance = summary["acceptance"]
    print(
        f"准确率：{summary['exact_matches']}/{summary['sample_count']} "
        f"({summary['accuracy']:.2%})，目标 >= {ACCURACY_TARGET:.0%}"
    )
    print(
        f"批处理：{summary['batch_elapsed_ms']} ms，目标 <= {BATCH_TARGET_MS} ms"
    )
    print(f"逐张结果：{csv_path}")
    print(f"汇总与环境：{json_path}")
    return 0 if acceptance["accuracy_pass"] and acceptance["batch_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
