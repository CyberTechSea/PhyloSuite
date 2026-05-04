#!/usr/bin/env python3
"""
PhyloSuite Build Script
Generates standalone executables for Windows, Linux, macOS
using PyInstaller.

Usage:
  python build/build.py --platform all
  python build/build.py --platform win
  python build/build.py --platform linux
  python build/build.py --platform mac
"""

import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
BACKEND = ROOT / "backend"
DIST = ROOT / "dist"
BUILD_TEMP = ROOT / "build_temp"

PLATFORMS = {
    "win":   "PhyloSuite-win.exe",
    "linux": "PhyloSuite-linux",
    "mac":   "PhyloSuite-mac",
}


def run(cmd, cwd=None):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, cwd=cwd or ROOT, check=True)
    return r


def clean():
    print("► Cleaning previous builds…")
    for d in [DIST, BUILD_TEMP]:
        if d.exists():
            shutil.rmtree(d)
    DIST.mkdir(parents=True)
    BUILD_TEMP.mkdir(parents=True)


def build_executable(platform_id):
    name = PLATFORMS[platform_id].replace(".exe", "")
    print(f"\n► Building for {platform_id} → {name}")

    entry = BACKEND / "launch.py"

    # Write launcher if not exists
    if not entry.exists():
        entry.write_text("""\
import os, sys, webbrowser, threading, time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def open_browser():
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000")

threading.Thread(target=open_browser, daemon=True).start()

from app import create_app
app = create_app()
app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
""")

    sep = ";" if sys.platform == "win32" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", name,
        "--onefile",
        "--windowed" if platform_id == "win" else "--console",
        "--distpath", str(DIST),
        "--workpath", str(BUILD_TEMP),
        "--specpath", str(BUILD_TEMP),
        f"--add-data={ROOT / 'frontend'}{sep}frontend",
        f"--add-data={ROOT / 'backend' / 'core'}{sep}core",
        f"--add-data={ROOT / 'backend' / 'pipeline'}{sep}pipeline",
        f"--add-data={ROOT / 'backend' / 'api'}{sep}api",
        "--hidden-import=flask",
        "--hidden-import=flask_cors",
        "--hidden-import=werkzeug",
        "--hidden-import=jinja2",
        str(entry),
    ]

    try:
        run(cmd)
        print(f"  ✓ Built: {DIST / PLATFORMS[platform_id]}")
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Build failed for {platform_id}: {e}")
        sys.exit(1)


def package_release(platform_id):
    """Create a zip archive with the executable and README"""
    name = PLATFORMS[platform_id]
    exe = DIST / name
    if not exe.exists():
        return

    import zipfile
    archive_name = f"PhyloSuite-{platform_id}-v1.0.0.zip"
    archive_path = DIST / archive_name

    print(f"► Packaging → {archive_name}")
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe, name)
        readme = ROOT / "README.md"
        if readme.exists():
            zf.write(readme, "README.md")
        install_doc = ROOT / "docs" / "INSTALL_TOOLS.md"
        if install_doc.exists():
            zf.write(install_doc, "INSTALL_TOOLS.md")

    print(f"  ✓ Archive: {archive_path}")


def main():
    parser = argparse.ArgumentParser(description="Build PhyloSuite executables")
    parser.add_argument("--platform", choices=["all", "win", "linux", "mac"], default="all")
    parser.add_argument("--clean", action="store_true", default=True)
    parser.add_argument("--package", action="store_true", default=True)
    args = parser.parse_args()

    # Check PyInstaller
    try:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--version"],
                       capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("► Installing PyInstaller…")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    if args.clean:
        clean()

    targets = list(PLATFORMS.keys()) if args.platform == "all" else [args.platform]
    for platform_id in targets:
        build_executable(platform_id)
        if args.package:
            package_release(platform_id)

    print(f"\n✓ Done. Output in: {DIST}")


if __name__ == "__main__":
    main()
