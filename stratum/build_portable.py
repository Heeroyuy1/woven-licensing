"""Build script for Stratum portable EXE using PyInstaller.
Run: python build_portable.py"""
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_SCRIPT = ROOT / "app.py"
ICON_PATH = ROOT / "assets" / "icon.ico"


def create_icon():
    """Create a simple SVG icon if it doesn't exist."""
    icon_dir = ROOT / "assets"
    icon_dir.mkdir(exist_ok=True)
    ico_path = icon_dir / "icon.ico"
    if not ico_path.exists():
        # Create minimal ICO-compatible SVG (saved as .ico name, but modern apps support SVG favicons)
        svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="url(#g)"/>
  <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" style="stop-color:#22d3ee"/>
    <stop offset="100%" style="stop-color:#0891b2"/>
  </linearGradient>
  <text x="16" y="22" font-family="Arial" font-size="16" font-weight="bold" fill="#0a0f1e" text-anchor="middle">S</text>
</svg>"""
        ico_path.write_text(svg)
        print(f"Created placeholder icon at {ico_path}")
    return ico_path


def build_portable():
    """Build a single-file portable EXE."""
    print("=" * 60)
    print("Stratum — Portable Build")
    print("=" * 60)

    icon_path = create_icon()

    # PyInstaller command for portable single-file executable
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                    # Single executable
        "--windowed",                   # No console window
        "--name", "Stratum",
        "--add-data", f"profiles{os.pathsep}profiles",
        "--add-data", f"reports{os.pathsep}reports",
        "--add-data", f"data{os.pathsep}data",
        "--add-data", f"logs{os.pathsep}logs",
        "--add-data", f"cache{os.pathsep}cache",
        "--hidden-import", "yfinance",
        "--hidden-import", "pandas._libs.tslibs.base",
        "--hidden-import", "pandas._libs.tslibs.np_datetime",
        "--hidden-import", "pandas._libs.tslibs.timedeltas",
        "--hidden-import", "cryptography",
        "--hidden-import", "cryptography.fernet",
        "--hidden-import", "reportlab",
        "--hidden-import", "openpyxl",
        "--collect-all", "PyQt6",
        "--collect-all", "numpy",
        "--collect-all", "pandas",
        "--distpath", "dist",
        "--workpath", "build_tmp",
        "--specpath", "build_tmp",
        "--noconfirm",
    ]

    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    cmd.append(str(APP_SCRIPT))

    print(f"\nRunning PyInstaller...")
    print(f"  App: {APP_SCRIPT}")
    print(f"  Output: {ROOT / 'dist' / 'Stratum.exe'}")
    print(f"\nThis may take several minutes...\n")

    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode == 0:
        print(f"\n✅ Success! Portable EXE created at:")
        print(f"   {ROOT / 'dist' / 'Stratum.exe'}")
    else:
        print(f"\n❌ Build failed with return code {result.returncode}")


def build_msi():
    """Build an MSI installer."""
    print("=" * 60)
    print("Stratum — MSI Installer Build")
    print("=" * 60)

    icon_path = create_icon()

    # PyInstaller command for MSI installer
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "Stratum",
        "--add-data", f"profiles{os.pathsep}profiles",
        "--add-data", f"reports{os.pathsep}reports",
        "--add-data", f"data{os.pathsep}data",
        "--add-data", f"logs{os.pathsep}logs",
        "--add-data", f"cache{os.pathsep}cache",
        "--hidden-import", "yfinance",
        "--hidden-import", "pandas._libs.tslibs.base",
        "--hidden-import", "pandas._libs.tslibs.np_datetime",
        "--hidden-import", "pandas._libs.tslibs.timedeltas",
        "--hidden-import", "cryptography",
        "--hidden-import", "cryptography.fernet",
        "--hidden-import", "reportlab",
        "--hidden-import", "openpyxl",
        "--collect-all", "PyQt6",
        "--collect-all", "numpy",
        "--collect-all", "pandas",
        "--distpath", "dist",
        "--workpath", "build_tmp",
        "--specpath", "build_tmp",
        "--noconfirm",
    ]

    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    cmd.append(str(APP_SCRIPT))

    print(f"\nRunning PyInstaller for MSI...")
    print(f"  App: {APP_SCRIPT}")
    print(f"  Output: {ROOT / 'dist' / 'Stratum.exe'}")
    print(f"\nAfter build completes, use the EXE with your MSI packaging tool.\n")

    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode == 0:
        print(f"\n✅ Success! Executable created at:")
        print(f"   {ROOT / 'dist' / 'Stratum.exe'}")
        print(f"\nTo create MSI, you can use:")
        print(f"   1. Advanced Installer (free edition)")
        print(f"   2. WiX Toolset")
        print(f"   3. Inno Setup (creates setup.exe)")
        print(f"\nOr run directly: dist/Stratum.exe")
    else:
        print(f"\n❌ Build failed with return code {result.returncode}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build Stratum distribution")
    parser.add_argument("--portable", action="store_true", help="Build portable EXE")
    parser.add_argument("--msi", action="store_true", help="Build MSI-ready EXE")
    parser.add_argument("--all", action="store_true", help="Build both")

    args = parser.parse_args()

    if args.all or args.portable:
        build_portable()
    if args.all or args.msi:
        build_msi()

    if not any([args.portable, args.msi, args.all]):
        parser.print_help()
