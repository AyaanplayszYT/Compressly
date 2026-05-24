"""Build a standalone Compressly.exe with PyInstaller.

Usage:
    python build.py            # one-folder build (faster startup)
    python build.py --onefile  # single .exe (slower startup, easier to ship)

Outputs land in `dist/Compressly` (or `dist/Compressly.exe` for --onefile).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ICON = ROOT / "assets" / "icon.ico"
PNG = ROOT / "assets" / "icon.png"


def ensure_icon() -> None:
    if ICON.exists() and PNG.exists():
        return
    print("[build] generating icon assets…")
    import_script = ROOT / "assets" / "make_icon.py"
    subprocess.check_call([sys.executable, str(import_script)])


def clean(*folders: Path) -> None:
    for f in folders:
        if f.exists():
            print(f"[build] cleaning {f}")
            shutil.rmtree(f, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--onefile", action="store_true", help="Build a single-file .exe")
    parser.add_argument("--noclean", action="store_true", help="Skip cleaning dist/build")
    args = parser.parse_args()

    ensure_icon()

    # Generate version info file (reduces AV false positives)
    version_script = ROOT / "version_info.py"
    version_txt    = ROOT / "version_info.txt"
    if version_script.exists():
        subprocess.check_call([sys.executable, str(version_script)])

    if not args.noclean:
        clean(ROOT / "build", ROOT / "dist")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "Compressly",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--icon",
        str(ICON),
        "--manifest",
        str(ROOT / "Compressly.manifest"),
    ]

    # Add version info if generated
    if version_txt.exists():
        cmd += ["--version-file", str(version_txt)]

    cmd += [
        "--add-data",
        f"{ROOT / 'assets'}{';' if sys.platform == 'win32' else ':'}assets",
        "--collect-submodules",
        "rembg",
        "--collect-submodules",
        "onnxruntime",
        "--collect-data",
        "rembg",
        # Only the Qt modules we actually use — keeps the binary small.
        "--exclude-module",
        "PySide6.QtNetwork",
        "--exclude-module",
        "PySide6.QtWebEngineCore",
        "--exclude-module",
        "PySide6.QtWebEngineWidgets",
        "--exclude-module",
        "PySide6.QtWebEngineQuick",
        "--exclude-module",
        "PySide6.QtQml",
        "--exclude-module",
        "PySide6.QtQuick",
        "--exclude-module",
        "PySide6.QtQuick3D",
        "--exclude-module",
        "PySide6.QtQuickControls2",
        "--exclude-module",
        "PySide6.QtMultimedia",
        "--exclude-module",
        "PySide6.QtMultimediaWidgets",
        "--exclude-module",
        "PySide6.QtSql",
        "--exclude-module",
        "PySide6.QtTest",
        "--exclude-module",
        "PySide6.QtCharts",
        "--exclude-module",
        "PySide6.QtDataVisualization",
        "--exclude-module",
        "PySide6.Qt3DCore",
        "--exclude-module",
        "PySide6.Qt3DRender",
        "--exclude-module",
        "PySide6.Qt3DInput",
        "--exclude-module",
        "PySide6.Qt3DLogic",
        "--exclude-module",
        "PySide6.Qt3DAnimation",
        "--exclude-module",
        "PySide6.Qt3DExtras",
        "--exclude-module",
        "PySide6.QtPdf",
        "--exclude-module",
        "PySide6.QtPdfWidgets",
        "--exclude-module",
        "PySide6.QtPositioning",
        "--exclude-module",
        "PySide6.QtLocation",
        "--exclude-module",
        "PySide6.QtBluetooth",
        "--exclude-module",
        "PySide6.QtNfc",
        "--exclude-module",
        "PySide6.QtSerialPort",
        "--exclude-module",
        "PySide6.QtSerialBus",
        "--exclude-module",
        "PySide6.QtSensors",
        "--exclude-module",
        "PySide6.QtRemoteObjects",
        "--exclude-module",
        "PySide6.QtScxml",
        "--exclude-module",
        "PySide6.QtStateMachine",
        "--exclude-module",
        "PySide6.QtTextToSpeech",
        "--exclude-module",
        "PySide6.QtSpatialAudio",
        "--exclude-module",
        "PySide6.QtSvg",
        "--exclude-module",
        "PySide6.QtSvgWidgets",
        "--exclude-module",
        "PySide6.QtHelp",
        "--exclude-module",
        "PySide6.QtDesigner",
        "--exclude-module",
        "PySide6.QtWebChannel",
        "--exclude-module",
        "PySide6.QtWebSockets",
        "--exclude-module",
        "PySide6.QtNetworkAuth",
        "--exclude-module",
        "PySide6.QtHttpServer",
        "--exclude-module",
        "PySide6.QtUiTools",
        "--exclude-module",
        "PySide6.QtConcurrent",
        "--exclude-module",
        "PySide6.QtDBus",
        "--exclude-module",
        "PySide6.QtPrintSupport",
        "--exclude-module",
        "PySide6.QtAxContainer",
        "--exclude-module",
        "PySide6.QtOpenGL",
        "--exclude-module",
        "PySide6.QtOpenGLWidgets",
        "--exclude-module",
        "PySide6.QtQuickWidgets",
        "--exclude-module",
        "PySide6.QtQuickTest",
        "--exclude-module",
        "PySide6.QtGraphs",
        "--exclude-module",
        "PySide6.QtGraphsWidgets",
        "--exclude-module",
        "PySide6.QtExampleIcons",
        "--exclude-module",
        "PySide6.QtAsyncio",
        "--exclude-module",
        "PySide6.scripts",
        # Standard library modules we don't need.
        "--exclude-module",
        "tkinter",
        "--exclude-module",
        "unittest",
        str(ROOT / "main.py"),
    ]
    if args.onefile:
        cmd.insert(4, "--onefile")

    print("[build] running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    print("\n[build] success")
    if args.onefile:
        print(f"  -> {ROOT / 'dist' / 'Compressly.exe'}")
    else:
        print(f"  -> {ROOT / 'dist' / 'Compressly' / 'Compressly.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
