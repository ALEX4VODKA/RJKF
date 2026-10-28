"""Qt 后台识别线程，避免模型加载和推理阻塞主界面。"""

from PyQt5.QtCore import QThread, pyqtSignal


class RecognitionThread(QThread):
    recognized = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, recognizer, media_path: str, parent=None):
        super().__init__(parent)
        self.recognizer = recognizer
        self.media_path = media_path

    def run(self):
        try:
            result = self.recognizer.recognize_media(self.media_path)
        except Exception as exc:
            self.failed.emit(exc)
        else:
            self.recognized.emit(result)
