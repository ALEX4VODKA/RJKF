import csv
from pathlib import Path

import cv2
import numpy as np
import pytest

from parking.recognition import PlateCandidate, RecognitionError, RecognitionResult
from tools.phase5_recognition_benchmark import (
    BenchmarkCase,
    build_summary,
    load_cases,
    run_cases,
)


def _write_image(path: Path):
    ok, payload = cv2.imencode(".jpg", np.full((1080, 1920, 3), 128, dtype=np.uint8))
    assert ok
    payload.tofile(str(path))


def test_load_cases_validates_count_and_reads_utf8_bom_manifest(tmp_path):
    image = tmp_path / "plate.jpg"
    _write_image(image)
    manifest = tmp_path / "ground_truth.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["id", "file", "plate", "plate_color", "source"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "id": "1",
                "file": image.name,
                "plate": "陕A12345",
                "plate_color": "blue",
                "source": "fixture",
            }
        )

    cases = load_cases(manifest, expected_count=1)

    assert cases[0].expected_plate == "陕A12345"
    assert (cases[0].width, cases[0].height) == (1920, 1080)
    with pytest.raises(ValueError, match="应有 2 条"):
        load_cases(manifest, expected_count=2)


class _FakeRecognizer:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)

    def recognize_media(self, _path):
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_run_cases_and_summary_count_only_exact_automatic_matches(tmp_path):
    cases = [
        BenchmarkCase("1", tmp_path / "a.jpg", "a.jpg", "陕A12345", "blue", "x", 1920, 1080),
        BenchmarkCase("2", tmp_path / "b.jpg", "b.jpg", "陕B12345", "yellow", "y", 1280, 720),
    ]
    success = RecognitionResult(
        plate="陕A12345",
        confidence=0.95,
        kind="blue",
        box=(1, 2, 3, 4),
        photo_path="capture.jpg",
        frame_index=0,
        elapsed_ms=10,
        candidates=(
            PlateCandidate("陕C12345", 0.97, "blue", (1, 2, 3, 4)),
            PlateCandidate("陕A12345", 0.95, "blue", (1, 2, 3, 4)),
        ),
    )
    failure = RecognitionError(
        "低于阈值", suggested_plate="陕B12345", confidence=0.79
    )

    results, batch_ms = run_cases(cases, _FakeRecognizer([success, failure]))
    summary = build_summary(results, prepare_ms=20, batch_elapsed_ms=batch_ms)

    assert results[0].exact_match is True
    assert results[0].candidate_plates == "陕A12345|陕C12345"
    assert results[0].expected_in_candidates is True
    assert results[1].predicted_plate == "陕B12345"
    assert results[1].exact_match is False
    assert summary["exact_matches"] == 1
    assert summary["expected_in_candidates"] == 1
    assert summary["automatic_failures"] == 1
    assert summary["accuracy"] == pytest.approx(0.5)
    assert summary["acceptance"]["accuracy_pass"] is False
