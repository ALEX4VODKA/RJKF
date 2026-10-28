"""真实图片与视频车牌识别。"""

from .service import (
    LicenseRecognizer,
    PlateCandidate,
    RecognitionError,
    RecognitionResult,
)
__all__ = [
    "LicenseRecognizer",
    "PlateCandidate",
    "RecognitionError",
    "RecognitionResult",
]
