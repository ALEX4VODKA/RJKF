from pathlib import Path

import cv2
import numpy as np
import pytest

from parking.recognition import LicenseRecognizer, RecognitionError


class FakeBackend:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def recognize(self, _image):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


def _write_image(path: Path, value: int = 128):
    frame = np.full((96, 160, 3), value, dtype=np.uint8)
    ok, payload = cv2.imencode(".jpg", frame)
    assert ok
    payload.tofile(str(path))


def test_image_recognition_normalizes_plate_and_saves_capture(tmp_path):
    source = tmp_path / "中文车牌.jpg"
    _write_image(source)
    backend = FakeBackend(
        [[("陕a·12-345", 0.93, 0, [10, 20, 130, 70])]]
    )
    recognizer = LicenseRecognizer(tmp_path / "runtime", backend=backend)

    result = recognizer.recognize_media(source)

    assert result.plate == "陕A12345"
    assert result.kind == "blue"
    assert result.confidence == pytest.approx(0.93)
    assert result.box == (10, 20, 130, 70)
    assert Path(result.photo_path).is_file()
    assert backend.calls == 3


def test_multiple_high_confidence_plates_are_returned_for_operator_choice(tmp_path):
    source = tmp_path / "two-plates.jpg"
    _write_image(source)
    backend = FakeBackend(
        [[
            ("陕A12345", 0.91, 0, [1, 2, 30, 20]),
            ("陕B67890", 0.96, 1, [40, 2, 80, 20]),
        ]]
    )
    recognizer = LicenseRecognizer(tmp_path / "runtime", backend=backend)

    result = recognizer.recognize_media(source)

    assert result.plate == "陕B67890"
    assert [candidate.plate for candidate in result.candidates] == [
        "陕B67890",
        "陕A12345",
    ]


def test_low_confidence_retries_three_times_then_preserves_manual_context(tmp_path):
    source = tmp_path / "blurred.png"
    _write_image(source, 80)
    backend = FakeBackend(
        [
            [["陕A12345", 0.55, 0, [1, 2, 30, 20]]],
            [["陕A12345", 0.72, 0, [1, 2, 30, 20]]],
            [["陕A12345", 0.79, 0, [1, 2, 30, 20]]],
        ]
    )
    recognizer = LicenseRecognizer(tmp_path / "runtime", backend=backend)

    with pytest.raises(RecognitionError) as caught:
        recognizer.recognize_media(source)

    assert backend.calls == 3
    assert caught.value.suggested_plate == "陕A12345"
    assert caught.value.confidence == pytest.approx(0.79)
    assert Path(caught.value.photo_path).is_file()
    assert "低于阈值" in str(caught.value)


def test_video_input_reads_real_frames_and_returns_frame_index(tmp_path):
    source = tmp_path / "sample.avi"
    writer = cv2.VideoWriter(
        str(source), cv2.VideoWriter_fourcc(*"MJPG"), 5.0, (160, 96)
    )
    if not writer.isOpened():
        pytest.skip("当前 OpenCV 构建不支持 MJPG 测试视频")
    for value in (40, 80, 120, 160, 200):
        writer.write(np.full((96, 160, 3), value, dtype=np.uint8))
    writer.release()
    backend = FakeBackend(
        [[("陕A54321", 0.91, 3, [5, 6, 120, 60])]]
    )
    recognizer = LicenseRecognizer(tmp_path / "runtime", backend=backend)

    result = recognizer.recognize_media(source)

    assert result.plate == "陕A54321"
    assert result.kind == "green"
    assert result.frame_index >= 0
    assert Path(result.photo_path).is_file()


def test_video_frame_selection_spans_timeline_and_prefers_clear_frames(
    tmp_path, monkeypatch
):
    class FakeCapture:
        def __init__(self, frames):
            self.frames = frames
            self.position = 0

        def isOpened(self):
            return True

        def get(self, prop):
            if prop == cv2.CAP_PROP_FRAME_COUNT:
                return len(self.frames)
            return 0

        def set(self, prop, value):
            if prop == cv2.CAP_PROP_POS_FRAMES:
                self.position = int(value)
                return True
            return False

        def read(self):
            if not 0 <= self.position < len(self.frames):
                return False, None
            frame = self.frames[self.position].copy()
            self.position += 1
            return True, frame

        def release(self):
            pass

    frames = [np.full((96, 160, 3), 128, dtype=np.uint8) for _ in range(90)]
    checkerboard = (np.indices((96, 160)).sum(axis=0) % 2 * 255).astype(np.uint8)
    sharp_frame = np.repeat(checkerboard[:, :, None], 3, axis=2)
    expected = [25, 50, 76]
    for position in expected:
        frames[position] = sharp_frame

    monkeypatch.setattr(
        "parking.recognition.service.cv2.VideoCapture",
        lambda _path: FakeCapture(frames),
    )
    recognizer = LicenseRecognizer(
        tmp_path / "runtime",
        backend=FakeBackend([[('陕A12345', 0.95, 0, [1, 2, 3, 4])]]),
    )

    attempts = list(recognizer._video_attempts(tmp_path / "sample.mp4"))

    assert [position for position, _inference, _capture in attempts] == expected
    assert len(attempts) == recognizer.max_attempts


def test_unsupported_media_fails_explicitly(tmp_path):
    source = tmp_path / "plate.txt"
    source.write_text("not an image", encoding="utf-8")
    recognizer = LicenseRecognizer(tmp_path / "runtime", backend=FakeBackend([[]]))

    with pytest.raises(RecognitionError, match="仅支持"):
        recognizer.recognize_media(source)
