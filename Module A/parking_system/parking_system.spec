# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_dir = Path(SPECPATH)

a = Analysis(
    [str(project_dir / "app.py")],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[
        (str(project_dir / "resources"), "resources"),
        (str(project_dir / "viewer"), "viewer"),
        (str(project_dir / "parking" / "data" / "schema.sql"), "parking/data"),
    ],
    hiddenimports=["hyperlpr3"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_dir / "tools" / "pyi_rth_onnxruntime_first.py")],
    excludes=[
        "hyperlpr3.command",
        "hyperlpr3.common.mnn_adapt",
        "MNN",
        "fastapi",
        "uvicorn",
        "torch",
        "torchvision",
        "torchaudio",
        "matplotlib",
        "pandas",
        "pytest",
        "IPython",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="智慧停车收费系统",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="智慧停车收费系统",
)
