# -*- coding: utf-8 -*-
"""动画接口自测：验证占位 / 序列帧 / 工厂选择（含入口、出口两套资源）。

用法： python tools/selftest_anim.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from PyQt5.QtCore import QEventLoop, Qt, QTimer  # noqa: E402
from PyQt5.QtGui import QColor, QImage  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from parking.anim import LOWER, RAISE, create_animator  # noqa: E402
from parking.anim.placeholder import PlaceholderAnimator  # noqa: E402
from parking.anim.sequence import SequenceAnimator  # noqa: E402


def wait_finished(animator, direction, timeout_ms=4000):
    loop = QEventLoop()
    got = {"value": None}

    def on_finished(d):
        got["value"] = d
        loop.quit()

    animator.finished.connect(on_finished)
    QTimer.singleShot(timeout_ms, loop.quit)
    animator.play(direction)
    loop.exec_()
    return got["value"]


def make_frames(directory, count=6):
    os.makedirs(directory, exist_ok=True)
    for i in range(count):
        img = QImage(320, 180, QImage.Format_RGB32)
        img.fill(QColor(11 + i * 8, 18, 25))
        img.save(os.path.join(directory, f"{i:04d}.png"))


def main():
    app = QApplication(sys.argv[:1])
    ok = True

    # 1) 占位实现
    ph = PlaceholderAnimator("test")
    d = wait_finished(ph, RAISE)
    print(f"[1] placeholder raise -> {d}")
    ok &= (d == RAISE)
    d = wait_finished(ph, LOWER)
    print(f"[2] placeholder lower -> {d}")
    ok &= (d == LOWER)

    # 2) 序列帧实现
    tmp = os.path.join(BASE_DIR, "tools", "_tmp_anim")
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    make_frames(os.path.join(tmp, "in", "up"))
    make_frames(os.path.join(tmp, "in", "down"))
    make_frames(os.path.join(tmp, "out", "up"))
    make_frames(os.path.join(tmp, "out", "down"))
    seq = SequenceAnimator(os.path.join(tmp, "in", "up"), os.path.join(tmp, "in", "down"), fps=60)
    d = wait_finished(seq, RAISE)
    print(f"[3] sequence raise -> {d}")
    ok &= (d == RAISE)

    # 3) 工厂：空目录 → 占位
    a1 = create_animator(os.path.join(tmp, "empty"), mode="placeholder", gate="in")
    print(f"[4] factory(empty, in)  -> {a1.mode_name()}")
    ok &= (a1.mode_name() == "预留位")

    # 4) 工厂：入口有帧、出口没帧
    a2 = create_animator(tmp, mode="sequence", gate="in")
    print(f"[5] factory(in)         -> {a2.mode_name()}")
    ok &= (a2.mode_name() == "序列帧")

    a3 = create_animator(tmp, mode="sequence", gate="out")
    print(f"[6] factory(out)        -> {a3.mode_name()}")
    ok &= (a3.mode_name() == "序列帧")

    # 5) 镜头归位：有 focus 帧时，抬杆前先走 focus 阶段
    make_frames(os.path.join(tmp, "in", "focus"), count=4)
    a4 = create_animator(tmp, mode="sequence", gate="in")
    stages = []
    a4.stage.connect(lambda st: stages.append(st))
    d = wait_finished(a4, RAISE)
    print(f"[9] focus+raise stages = {stages} -> {d}")
    ok &= stages == ["focus", "action"] and d == RAISE
    ok &= a4.has_prelude() if hasattr(a4, "has_prelude") else True

    # 6) 两个道闸各自独立：资源目录不同
    print(f"[7] in desc  = {a2.describe()}")
    print(f"[8] out desc = {a3.describe()}")
    ok &= a2.surface() is not a3.surface()

    print("SELFTEST", "PASS" if ok else "FAIL")
    shutil.rmtree(tmp, ignore_errors=True)      # 清理临时帧
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
