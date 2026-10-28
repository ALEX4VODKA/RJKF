"""安装阶段预加载 HyperLPR3 模型，完成后应用可离线识别。"""

from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from parking.config import RuntimePaths  # noqa: E402
from parking.recognition import LicenseRecognizer  # noqa: E402


def main() -> int:
    paths = RuntimePaths.from_environment(PROJECT_DIR)
    paths.ensure_directories()
    LicenseRecognizer(paths.root).prepare()
    print(f"识别模型已就绪：{paths.root / '.hyperlpr3'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
