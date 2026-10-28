"""基于 HyperLPR3 的离线图片/视频车牌识别服务。"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Protocol, Sequence
from uuid import uuid4

import cv2
import numpy as np

from parking.services.parking_service import ParkingError, normalize_plate


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv"}
MODEL_VERSION = "20230229"
MODEL_FILES = (
    "y5fu_320x_sim.onnx",
    "y5fu_640x_sim.onnx",
    "rpv3_mdict_160_r3.onnx",
    "litemodel_cls_96x_r1.onnx",
)

PLATE_TYPE_TO_KIND = {
    0: "blue",
    1: "yellow",
    2: "white",
    3: "green",
    4: "black",
    5: "other",
    6: "other",
    7: "other",
    8: "other",
    9: "yellow",
}


class RecognitionBackend(Protocol):
    def recognize(self, image: np.ndarray) -> Sequence[Sequence[object]]: ...


@dataclass(frozen=True)
class PlateCandidate:
    plate: str
    confidence: float
    kind: str
    box: tuple[int, int, int, int]


@dataclass(frozen=True)
class RecognitionResult:
    plate: str
    confidence: float
    kind: str
    box: tuple[int, int, int, int]
    photo_path: str
    frame_index: int
    elapsed_ms: int
    candidates: tuple[PlateCandidate, ...] = ()


class RecognitionError(RuntimeError):
    """可向操作员展示、并携带人工补录上下文的识别错误。"""

    def __init__(
        self,
        message: str,
        *,
        photo_path: str | None = None,
        suggested_plate: str | None = None,
        confidence: float | None = None,
    ):
        super().__init__(message)
        self.photo_path = photo_path
        self.suggested_plate = suggested_plate
        self.confidence = confidence


class HyperLprBackend:
    """隔离 HyperLPR3 的路径缺陷与第三方返回格式。"""

    def __init__(self, data_root: Path):
        self.model_home = data_root / ".hyperlpr3"
        # Windows 下 HyperLPR3 先加载自身推理模块、再延迟导入 ONNX Runtime
        # 会触发原生 DLL 初始化冲突；提前加载可让其后续导入复用同一模块。
        try:
            import onnxruntime  # noqa: F401
        except Exception as exc:
            raise RecognitionError(f"ONNX Runtime 加载失败：{exc}") from exc
        lpr3 = self._import_hyperlpr(data_root)
        try:
            self._catcher = lpr3.LicensePlateCatcher(
                folder=str(self.model_home),
                detect_level=lpr3.DETECT_LEVEL_HIGH,
            )
        except Exception as exc:  # ONNX Runtime 的异常类型并不稳定
            raise RecognitionError(f"车牌识别模型加载失败：{exc}") from exc

    def recognize(self, image: np.ndarray) -> Sequence[Sequence[object]]:
        return self._catcher(image)

    def _import_hyperlpr(self, data_root: Path):
        # HyperLPR3 0.1.3 在 Windows 上只读取无盘符 HOMEPATH。这里仅在导入
        # 期间把其模型目录定向到项目 runtime，导入后立即恢复进程环境。
        previous = os.environ.get("HOMEPATH")
        os.environ["HOMEPATH"] = str(data_root)
        try:
            try:
                return importlib.import_module("hyperlpr3")
            except PermissionError as exc:
                # 该版本首次解压模型后会在 ZIP 句柄关闭前删除 ZIP，Windows 会
                # 报 WinError 32；模型完整时清理半导入模块并重试即可。
                if not self._models_ready():
                    raise RecognitionError(f"车牌识别模型初始化失败：{exc}") from exc
                for name in tuple(sys.modules):
                    if name == "hyperlpr3" or name.startswith("hyperlpr3."):
                        sys.modules.pop(name, None)
                importlib.invalidate_caches()
                return importlib.import_module("hyperlpr3")
            except ModuleNotFoundError as exc:
                raise RecognitionError(
                    "未安装 HyperLPR3，请先执行 python -m pip install -r requirements.txt"
                ) from exc
            except Exception as exc:
                raise RecognitionError(f"车牌识别引擎初始化失败：{exc}") from exc
        finally:
            if previous is None:
                os.environ.pop("HOMEPATH", None)
            else:
                os.environ["HOMEPATH"] = previous

    def _models_ready(self) -> bool:
        model_dir = self.model_home / MODEL_VERSION / "onnx"
        return all((model_dir / name).is_file() for name in MODEL_FILES)


class LicenseRecognizer:
    """从图片或视频中识别一个置信度最高的有效车牌。"""

    def __init__(
        self,
        data_root: str | Path,
        *,
        threshold: float = 0.80,
        max_attempts: int = 3,
        backend: RecognitionBackend | None = None,
    ):
        if not 0.0 < threshold <= 1.0:
            raise ValueError("识别置信度阈值须在 0～1 之间")
        if not 1 <= max_attempts <= 3:
            raise ValueError("识别重试次数须为 1～3")
        self.data_root = Path(data_root).resolve()
        self.capture_dir = self.data_root / "captures"
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold
        self.max_attempts = max_attempts
        self._backend = backend

    def prepare(self) -> None:
        """预加载运行时和本地模型，供安装阶段离线准备。"""
        self._backend_instance()

    def recognize_media(self, media_path: str | Path) -> RecognitionResult:
        path = Path(media_path).resolve()
        if not path.is_file():
            raise RecognitionError("选择的图片或视频文件不存在")
        suffix = path.suffix.lower()
        if suffix not in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
            raise RecognitionError("仅支持 JPG/PNG/BMP/MP4/AVI/MOV/MKV 文件")

        started = perf_counter()
        attempts = (
            self._image_attempts(path)
            if suffix in IMAGE_SUFFIXES
            else self._video_attempts(path)
        )
        best: PlateCandidate | None = None
        best_frame: np.ndarray | None = None
        fallback_frame: np.ndarray | None = None
        last_engine_error: Exception | None = None
        accepted: list[tuple[PlateCandidate, np.ndarray, int]] = []

        for frame_index, inference_frame, capture_frame in attempts:
            if fallback_frame is None:
                fallback_frame = capture_frame
            try:
                candidates = self._recognize_frame(inference_frame)
            except RecognitionError as exc:
                last_engine_error = exc
                break
            except Exception as exc:  # 单帧失败仍允许按需求重试
                last_engine_error = exc
                continue
            if not candidates:
                continue
            by_plate: dict[str, PlateCandidate] = {}
            for candidate in candidates:
                previous = by_plate.get(candidate.plate)
                if previous is None or candidate.confidence > previous.confidence:
                    by_plate[candidate.plate] = candidate
            candidate = max(by_plate.values(), key=lambda item: item.confidence)
            if best is None or candidate.confidence > best.confidence:
                best = candidate
                best_frame = capture_frame
            for candidate in by_plate.values():
                if candidate.confidence >= self.threshold:
                    accepted.append((candidate, capture_frame, frame_index))

        if accepted:
            groups: dict[str, list[tuple[PlateCandidate, np.ndarray, int]]] = {}
            for observation in accepted:
                groups.setdefault(observation[0].plate, []).append(observation)
            ranked_groups = sorted(
                groups.values(),
                key=lambda group: (
                    len(group),
                    max(item[0].confidence for item in group),
                ),
                reverse=True,
            )
            selected_group = ranked_groups[0]
            selected, selected_frame, selected_index = max(
                selected_group, key=lambda item: item[0].confidence
            )
            eligible = tuple(
                max(group, key=lambda item: item[0].confidence)[0]
                for group in ranked_groups
            )
            photo = self._save_capture(selected_frame)
            return RecognitionResult(
                plate=selected.plate,
                confidence=selected.confidence,
                kind=selected.kind,
                box=selected.box,
                photo_path=str(photo),
                frame_index=selected_index,
                elapsed_ms=round((perf_counter() - started) * 1000),
                candidates=eligible,
            )

        photo_frame = best_frame if best_frame is not None else fallback_frame
        photo = self._save_capture(photo_frame) if photo_frame is not None else None
        if best is not None:
            raise RecognitionError(
                f"识别置信度 {best.confidence:.3f} 低于阈值 {self.threshold:.2f}，请人工核对",
                photo_path=str(photo) if photo else None,
                suggested_plate=best.plate,
                confidence=best.confidence,
            )
        if last_engine_error is not None:
            message = f"识别引擎处理失败：{last_engine_error}"
        else:
            message = "未检测到有效车牌，请更换清晰画面或人工录入"
        raise RecognitionError(message, photo_path=str(photo) if photo else None)

    def _backend_instance(self) -> RecognitionBackend:
        if self._backend is None:
            self._backend = HyperLprBackend(self.data_root)
        return self._backend

    def _recognize_frame(self, frame: np.ndarray) -> list[PlateCandidate]:
        raw_results = self._backend_instance().recognize(frame)
        candidates: list[PlateCandidate] = []
        for raw in raw_results or ():
            if len(raw) < 4:
                continue
            try:
                plate = normalize_plate(str(raw[0]))
                confidence = float(raw[1])
                plate_type = int(raw[2])
                values = tuple(int(value) for value in raw[3])
            except (ParkingError, TypeError, ValueError):
                continue
            if len(values) != 4 or not 0.0 <= confidence <= 1.0:
                continue
            candidates.append(
                PlateCandidate(
                    plate=plate,
                    confidence=confidence,
                    kind=PLATE_TYPE_TO_KIND.get(plate_type, "other"),
                    box=values,
                )
            )
        return candidates

    def _image_attempts(self, path: Path):
        frame = self._read_image(path)
        if frame is None:
            raise RecognitionError("图片无法读取或文件已损坏")
        yield 0, frame, frame
        if self.max_attempts >= 2:
            enhanced = cv2.convertScaleAbs(frame, alpha=1.15, beta=6)
            yield 1, enhanced, frame
        if self.max_attempts >= 3:
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            light, channel_a, channel_b = cv2.split(lab)
            light = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(light)
            enhanced = cv2.cvtColor(
                cv2.merge((light, channel_a, channel_b)), cv2.COLOR_LAB2BGR
            )
            yield 2, enhanced, frame

    def _video_attempts(self, path: Path):
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            capture.release()
            raise RecognitionError("视频无法打开或编码格式不受支持")
        try:
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if frame_count > 0:
                positions = np.linspace(
                    0, max(0, frame_count - 1), self.max_attempts + 2, dtype=int
                )[1:-1]
                positions = list(dict.fromkeys(int(value) for value in positions))
            else:
                positions = list(range(self.max_attempts))
            emitted = 0
            for position in positions:
                if frame_count > 0:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, position)
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue
                yield position, frame, frame
                emitted += 1
                if emitted >= self.max_attempts:
                    break
            if emitted == 0:
                raise RecognitionError("视频中没有可读取的画面")
        finally:
            capture.release()

    @staticmethod
    def _read_image(path: Path) -> np.ndarray | None:
        # imdecode + fromfile 可正确读取含中文字符的 Windows 路径。
        try:
            payload = np.fromfile(str(path), dtype=np.uint8)
        except OSError:
            return None
        return cv2.imdecode(payload, cv2.IMREAD_COLOR)

    def _save_capture(self, frame: np.ndarray) -> Path:
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            raise RecognitionError("抓拍照片保存失败")
        day_dir = self.capture_dir / datetime.now().strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        target = day_dir / f"{datetime.now():%H%M%S_%f}_{uuid4().hex[:8]}.jpg"
        encoded.tofile(str(target))
        return target
