# -*- coding: utf-8 -*-
"""动画实现工厂：按资源自动选择 实时 3D / MP4 / 序列帧 / 占位。

优先级（mode="auto"）：实时 3D（有 resources/model/parking.glb）
                        > MP4 > 序列帧 > 占位

3D 之外的备用资源按道闸分开：
    gate_in_up.mp4 / gate_in_down.mp4        入口
    gate_out_up.mp4 / gate_out_down.mp4      出口
或序列帧：
    in/up/*.png  in/down/*.png               入口
    out/up/*.png out/down/*.png              出口

为兼容早期的单文件命名（gate_up.mp4 / gate_down.mp4），
找不到对应门位的资源时会退回共用资源，并在界面上标注“共用”。
"""
import os

from .base import LOWER, RAISE, GateAnimator
from .placeholder import PlaceholderAnimator
from .sequence import SequenceAnimator
from .video import HAS_QTMM, VideoAnimator
from .webgl import HAS_WEBENGINE, WebGLAnimator

__all__ = [
    "GateAnimator", "RAISE", "LOWER", "PlaceholderAnimator",
    "SequenceAnimator", "VideoAnimator", "WebGLAnimator",
    "HAS_WEBENGINE", "create_animator", "resource_names",
]

GATES = ("in", "out")

HINT = (
    "入口：gate_in_up.mp4 / gate_in_down.mp4\n"
    "出口：gate_out_up.mp4 / gate_out_down.mp4\n"
    "或 in/up、in/down、out/up、out/down 帧目录"
)


def resource_names(anim_dir: str, gate: str):
    """返回某道闸期望的资源路径。"""
    return {
        "video_up": os.path.join(anim_dir, f"gate_{gate}_up.mp4"),
        "video_down": os.path.join(anim_dir, f"gate_{gate}_down.mp4"),
        "video_focus": os.path.join(anim_dir, f"gate_{gate}_focus.mp4"),
        "frames_up": os.path.join(anim_dir, gate, "up"),
        "frames_down": os.path.join(anim_dir, gate, "down"),
        "frames_focus": os.path.join(anim_dir, gate, "focus"),
    }


def _has_frames(directory: str) -> bool:
    if not os.path.isdir(directory):
        return False
    return any(n.lower().endswith((".png", ".jpg", ".jpeg")) for n in os.listdir(directory))


def create_animator(anim_dir: str, mode: str = "auto", fps: int = 30,
                    gate: str = "in", placeholder_hint: str = HINT) -> GateAnimator:
    """按道闸编号（in / out）选择实现。

    mode: auto | webgl | video | sequence | placeholder
    auto 的优先级：实时 3D（有 parking.glb 时）> MP4 > 序列帧 > 占位
    """
    names = resource_names(anim_dir, gate)
    app_root = os.path.dirname(os.path.dirname(anim_dir))   # <parking_system>
    model_file = os.path.join(app_root, "resources", "model", "parking.glb")

    # 0) 实时 3D：装了 WebEngine 且（有模型 或 强制 webgl 模式）
    if mode in ("auto", "webgl") and HAS_WEBENGINE:
        if mode == "webgl" or os.path.exists(model_file):
            try:
                return WebGLAnimator(app_root, gate)
            except Exception as exc:      # 例如 WebEngine 初始化失败
                print("[anim] WebGL 初始化失败，降级到视频：", exc)

    # 1) 该门位自己的视频
    if mode in ("auto", "video") and HAS_QTMM:
        if os.path.exists(names["video_up"]) and os.path.exists(names["video_down"]):
            try:
                return VideoAnimator(names["video_up"], names["video_down"],
                                     focus_file=names["video_focus"])
            except Exception:
                pass

        # 2) 退化：旧的单文件资源，两个道闸共用
        legacy_up = os.path.join(anim_dir, "gate_up.mp4")
        legacy_down = os.path.join(anim_dir, "gate_down.mp4")
        if os.path.exists(legacy_up) and os.path.exists(legacy_down):
            try:
                anim = VideoAnimator(legacy_up, legacy_down)
                anim.set_shared(True)
                return anim
            except Exception:
                pass

    # 3) 序列帧
    if mode in ("auto", "sequence"):
        if _has_frames(names["frames_up"]) and _has_frames(names["frames_down"]):
            try:
                focus = names["frames_focus"] if _has_frames(names["frames_focus"]) else None
                return SequenceAnimator(names["frames_up"], names["frames_down"],
                                        fps=fps, focus_dir=focus)
            except Exception:
                pass

    return PlaceholderAnimator(placeholder_hint,
                                has_prelude=os.path.exists(names["video_focus"]))
