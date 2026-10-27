# -*- coding: utf-8 -*-
"""
道闸动画导出脚本（在 Blender 里运行，不是在 Python 里运行）

用途：把 changjing.blend 里做好的抬杆 / 落杆动画，按项目要求的参数
（1920×1080 / 30fps / H.264）渲染到 resources/anim/ 下。

------------------------------------------------------------------
用法一：在 Blender 界面里运行（推荐给第一次用）
  1. 打开 changjing.blend
  2. 顶部工作区切到 Scripting
  3. Open 打开本文件
  4. 改下面的 CONFIG（主要是 name、start、end）
  5. 点右上角 ▶ Run Script
  脚本会先打印场景摘要，再开始渲染，进度在界面底部状态栏。

用法二：命令行（批量、可重复）
  "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe" ^
      -b changjing.blend -P blender_export_gate.py -- ^
      --out "D:/AllCode/parking_system/resources/anim" --name gate_up --frames 1-48

  只查看场景信息不渲染：  ... -- --list
------------------------------------------------------------------
"""
import os
import sys

import bpy

# ==================================================================
# 在 Blender 界面里运行时，改这里
CONFIG = {
    "out_dir": r"D:\AllCode\parking_system\resources\anim",
    "name": "gate_in_up",     # 见下表，四条视频分别导出
    "start": 1,               # 动画起始帧
    "end": 48,                # 动画结束帧（30fps 下 48 帧 ≈ 1.6 秒）
    # 四条（可选六条）视频的 name：
    #   gate_in_up     入口抬杆      gate_in_down    入口落杆
    #   gate_out_up    出口抬杆      gate_out_down   出口落杆
    #   gate_in_focus  入口镜头归位   gate_out_focus  出口镜头归位（可选）
    "fps": 30,
    "res_x": 1920,
    "res_y": 1080,
    "engine": "auto",         # auto / eevee / cycles
    "samples": 64,
    "render": True,           # False 时只打印信息
}
# ==================================================================


def _parse_argv():
    """读取 -- 之后的命令行参数；没有则返回 None。"""
    argv = sys.argv
    if "--" not in argv:
        return None
    args = argv[argv.index("--") + 1:]

    import argparse
    ap = argparse.ArgumentParser(prog="blender_export_gate")
    ap.add_argument("--out", help="输出目录")
    ap.add_argument("--name", help="文件名（不含扩展名），如 gate_up")
    ap.add_argument("--frames", help="帧范围，如 1-48")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--engine", default="auto", choices=["auto", "eevee", "cycles"])
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--list", action="store_true", help="只打印场景信息")
    ap.add_argument("--no-render", action="store_true", help="只配置不渲染")
    return ap.parse_args(args)


def scene_summary():
    sc = bpy.context.scene
    print("\n================ 场景摘要 ================")
    print(f"Blender      : {bpy.app.version_string}")
    print(f"文件         : {bpy.data.filepath}")
    print(f"帧率         : {sc.render.fps}")
    print(f"帧范围       : {sc.frame_start} - {sc.frame_end}")
    print(f"分辨率       : {sc.render.resolution_x} x {sc.render.resolution_y}"
          f" @ {sc.render.resolution_percentage}%")
    print(f"渲染引擎     : {sc.render.engine}")
    print(f"活动相机     : {sc.camera.name if sc.camera else '（无）'}")

    animated = [o for o in sc.objects if o.animation_data and o.animation_data.action]
    print(f"有动画的物体 : {len(animated)} 个")
    for o in animated[:15]:
        act = o.animation_data.action
        rng = act.frame_range
        print(f"   - {o.name:24s} action={act.name:24s} 帧 {rng[0]:.0f}-{rng[1]:.0f}")

    sel = bpy.context.selected_objects
    print(f"当前选中     : {', '.join(o.name for o in sel) if sel else '（无）'}")
    print("提示：把要做动画的那根杆选中，脚本会用它判断是否已有动画。")
    print("=========================================\n")


def set_engine(sc, prefer):
    order = {
        "auto": ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"],
        "eevee": ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"],
        "cycles": ["CYCLES"],
    }[prefer]
    for name in order:
        try:
            sc.render.engine = name
            return name
        except (TypeError, AttributeError):
            continue
    return sc.render.engine


def configure(sc, cfg):
    start, end = int(cfg["start"]), int(cfg["end"])
    if end <= start:
        raise ValueError("结束帧必须大于起始帧")

    sc.frame_start = start
    sc.frame_end = end
    sc.frame_set(start)

    sc.render.fps = int(cfg["fps"])
    sc.render.fps_base = 1.0

    sc.render.resolution_x = int(cfg["res_x"])
    sc.render.resolution_y = int(cfg["res_y"])
    sc.render.resolution_percentage = 100
    sc.render.pixel_aspect_x = 1.0
    sc.render.pixel_aspect_y = 1.0

    engine = set_engine(sc, cfg["engine"])
    try:
        if engine.startswith("BLENDER_EEVEE"):
            sc.eevee.taa_render_samples = int(cfg["samples"])
        elif engine == "CYCLES":
            sc.cycles.samples = int(cfg["samples"])
            sc.cycles.device = "GPU" if getattr(sc.cycles, "device", "") == "GPU" else "CPU"
    except Exception as exc:          # 不同版本属性名略有差异，不影响导出
        print(f"[warn] 采样设置失败：{exc}")

    sc.render.film_transparent = False        # 视频没有透明通道，用浅灰背景与界面一致
    sc.render.use_file_extension = True

    # 输出：FFmpeg 视频，H.264
    sc.render.image_settings.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = "HIGH"
    sc.render.ffmpeg.ffmpeg_preset = "GOOD"
    sc.render.ffmpeg.audio_codec = "NONE"

    out_dir = os.path.abspath(cfg["out_dir"])
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, cfg["name"])
    sc.render.filepath = base

    print(f"已设置：{engine} / {sc.render.resolution_x}x{sc.render.resolution_y}"
          f" / {sc.render.fps}fps / 帧 {start}-{end}")
    print(f"输出到：{base}.mp4")
    return base + ".mp4"


def main():
    args = _parse_argv()
    cfg = dict(CONFIG)
    if args:
        if args.out:
            cfg["out_dir"] = args.out
        if args.name:
            cfg["name"] = args.name
        if args.frames:
            a, b = args.frames.split("-")
            cfg["start"], cfg["end"] = int(a), int(b)
        cfg["fps"] = args.fps
        cfg["engine"] = args.engine
        cfg["samples"] = args.samples
        if args.list or args.no_render:
            cfg["render"] = False

    scene_summary()

    if args and args.list:
        return

    sc = bpy.context.scene
    target = sc.camera
    sel = bpy.context.selected_objects
    if sel:
        target = sel[0]

    has_anim = bool(target and target.animation_data and target.animation_data.action)
    if not has_anim:
        print(f"[提示] 物体 “{target.name if target else '无'}” 上没找到关键帧。")
        print("       如果动画在父级或骨骼上，请先在该物体上插帧，或忽略此提示继续渲染。")

    out_path = configure(sc, cfg)
    if not cfg["render"]:
        print("已跳过渲染（--no-render / --list）。")
        return

    print("开始渲染……（Ctrl+C 或 Esc 可中断）")
    bpy.ops.render.render(animation=True)

    if os.path.exists(out_path):
        size = os.path.getsize(out_path) / 1024 / 1024
        print(f"\n完成：{out_path}  ({size:.1f} MB)")
        print("回到界面点「重新加载」，胶囊应变成「MP4 动画」。")
    else:
        print(f"\n[注意] 没找到 {out_path}，请检查输出目录与文件名（Blender 可能自动加了后缀）。")
        for f in os.listdir(os.path.dirname(out_path) or "."):
            if os.path.splitext(f)[0].startswith(cfg["name"]):
                print("  实际生成：", f)


if __name__ == "__main__":
    main()
