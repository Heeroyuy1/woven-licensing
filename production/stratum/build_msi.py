#!/usr/bin/env python3
"""Build script for Stratum MSI installer using PyInstaller + WiX Toolset.

Run:
    python build_msi.py              # MSI installer (default)
    python build_msi.py --portable   # Portable single-file EXE
    python build_msi.py --msi        # MSI installer (explicit)
    python build_msi.py --all        # Both portable + MSI

Produces:
    dist/Stratum.exe          # Portable single-file EXE (--portable or --all)
    dist/Stratum.msi          # MSI installer (--msi or --all)
"""
import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path

# Script location: production/stratum/build_msi.py
# Stratum source:  ../../stratum/  (relative to this script)
SCRIPT_DIR = Path(__file__).resolve().parent                      # production/stratum/
PROJECT_ROOT = SCRIPT_DIR.parent.parent                           # Backtesting Bot/
STRATUM_SRC = PROJECT_ROOT / "stratum"                            # stratum/ — the PyQt6 app
APP_SCRIPT = STRATUM_SRC / "app.py"
ICON_PATH = STRATUM_SRC / "assets" / "icon.ico"
DIST_DIR = STRATUM_SRC / "dist"                                   # output: stratum/dist/
BUILD_DIR = STRATUM_SRC / "build_tmp"

HIDDEN_IMPORTS = [
    "yfinance",
    "pandas._libs.tslibs.base",
    "pandas._libs.tslibs.np_datetime",
    "pandas._libs.tslibs.timedeltas",
    "cryptography",
    "cryptography.fernet",
    "reportlab",
    "openpyxl",
]

# Do NOT use --collect-all for numpy/pandas — that pulls in ALL test modules
# (thousands of files, ~150 MB of tests). PyQt6 needs collect-all because
# it has many Qt plugins we rely on.
COLLECT_ALL = [
    "PyQt6",
]

# Exclude test/data/doc modules from numpy/pandas to keep size small
EXCLUDES = [
    "numpy.testing",
    "numpy.tests",
    "numpy.core.tests",
    "numpy.lib.tests",
    "numpy.f2py.tests",
    "numpy.polynomial.tests",
    "numpy.random.tests",
    "numpy.ma.tests",
    "numpy.matrixlib.tests",
    "numpy.fft.tests",
    "numpy.linalg.tests",
    "numpy.distutils.tests",
    "numpy.array_api.tests",
    "numpy.compat.tests",
    "numpy.typing.tests",
    "pandas.tests",
    "pandas._testing",
    "pandas.util._doctools",
    "matplotlib.tests",
    "scipy.tests",
    "PIL.ImageFilter",
]

DATA_DIRS = ["profiles", "reports", "data", "logs", "cache"]


def create_icon():
    """Create a placeholder icon if it doesn't exist.

    Writes an SVG-based icon (named .ico for PyInstaller compat — all modern
    Windows and browsers support SVG favicons). If the file already exists
    or creation fails, we skip gracefully.
    """
    icon_dir = ICON_PATH.parent
    icon_dir.mkdir(parents=True, exist_ok=True)
    if ICON_PATH.exists():
        return ICON_PATH

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" '
        'shape-rendering="crispEdges">'
        '<rect width="32" height="32" rx="6" fill="#0891b2"/>'
        '<text x="16" y="23" font-family="Arial,sans-serif" font-size="18" '
        'font-weight="bold" fill="#ffffff" text-anchor="middle">S</text>'
        '</svg>'
    )
    try:
        ICON_PATH.write_text(svg, encoding="utf-8")
        print(f"ℹ  Created placeholder icon at {ICON_PATH}")
        print(f"   Replace with a proper .ico file if targeting Windows 8.1 or older.")
    except Exception as e:
        print(f"⚠  Could not create placeholder icon: {e}")
        print(f"   Provide your own icon at: {ICON_PATH}")
    return ICON_PATH


def build_pyinstaller(mode="msi"):
    """Run PyInstaller and produce a single EXE.

    Args:
        mode: "portable" or "msi" (both produce an EXE; MSI step is separate)
    """
    print("=" * 60)
    label = "Portable EXE" if mode == "portable" else "MSI-ready EXE"
    print(f"  Stratum — {label} Build")
    print("=" * 60)

    create_icon()

    # Clean previous dist/build
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "Stratum",
    ]

    # Add data dirs (only if they exist in source)
    for d in DATA_DIRS:
        src = STRATUM_SRC / d
        if src.exists():
            cmd.extend(["--add-data", f"{src}{os.pathsep}{d}"])

    # Hidden imports
    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])

    # Collect-all for big packages (only PyQt6 — not numpy/pandas!)
    for pkg in COLLECT_ALL:
        cmd.extend(["--collect-all", pkg])

    # Exclude test/data/doc modules to keep size reasonable
    for exclude in EXCLUDES:
        cmd.extend(["--exclude-module", exclude])

    cmd.extend([
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
        "--noconfirm",
    ])

    if ICON_PATH.exists():
        cmd.extend(["--icon", str(ICON_PATH)])

    cmd.append(str(APP_SCRIPT))

    print(f"\n  App script: {APP_SCRIPT}")
    print(f"  Output EXE: {DIST_DIR / 'Stratum.exe'}")
    print(f"\n  Running PyInstaller (this may take several minutes)...\n")

    result = subprocess.run(cmd, cwd=str(STRATUM_SRC))

    if result.returncode != 0:
        print(f"\n❌ PyInstaller build FAILED with return code {result.returncode}")
        print("   Check the output above for errors.")
        return False

    exe_path = DIST_DIR / "Stratum.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n✅ PyInstaller succeeded!")
        print(f"   Executable: {exe_path}")
        print(f"   Size: {size_mb:.1f} MB")
        return True
    else:
        print(f"\n❌ Executable not found at {exe_path}")
        return False


def detect_wix():
    """Detect WiX Toolset installation (candle.exe and light.exe).

    Returns:
        (candle_path, light_path) if found, else (None, None)
    """
    # Common WiX install locations
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "WiX Toolset" / "v3" / "bin",
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "WiX Toolset" / "v3" / "bin",
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "WiX Toolset" / "v3.11" / "bin",
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "WiX Toolset" / "v3.11" / "bin",
    ]

    # Also check PATH
    candle = shutil.which("candle.exe")
    light = shutil.which("light.exe")
    if candle and light:
        return Path(candle), Path(light)

    for wix_dir in candidates:
        c = wix_dir / "candle.exe"
        l = wix_dir / "light.exe"
        if c.exists() and l.exists():
            return c, l

    return None, None


def build_msi():
    """Build MSI installer from the EXE using WiX Toolset."""
    print("=" * 60)
    print("  Stratum — MSI Installer Packaging")
    print("=" * 60)

    # First, build the EXE if not already present
    exe_path = DIST_DIR / "Stratum.exe"
    if not exe_path.exists():
        print("  No existing EXE found. Building with PyInstaller first...")
        if not build_pyinstaller(mode="msi"):
            return False

    # The WiX source file lives next to this script: production/stratum/stratum.wxs
    wxs_path = SCRIPT_DIR / "stratum.wxs"
    if not wxs_path.exists():
        print(f"\n❌ WiX source file not found: {wxs_path}")
        print("   Please ensure stratum.wxs exists in the production/stratum/ directory.")
        return False

    # Detect WiX
    candle_exe, light_exe = detect_wix()
    if not candle_exe or not light_exe:
        print("\n⚠  WiX Toolset not detected.")
        print("   To build MSI manually:")
        print("     1. Download WiX Toolset v3 from: https://wixtoolset.org/releases/")
        print("     2. Install it (default location is recommended)")
        print("     3. Open a command prompt in: production\\stratum")
        print("     4. Run:  candle.exe -arch x64 stratum.wxs")
        print("     5. Run:  light.exe -out dist\\Stratum.msi stratum.wixobj")
        print("     6. Output: production\\stratum\\dist\\Stratum.msi")
        print("\n   Or use an alternative packager like Inno Setup or Advanced Installer.")
        print(f"\n   The EXE is ready at: {exe_path}")
        return False

    print(f"\n  Found WiX Toolset:")
    print(f"    candle: {candle_exe}")
    print(f"    light:  {light_exe}")

    # Compile .wxs -> .wixobj
    wixobj_path = BUILD_DIR / "stratum.wixobj"
    wixobj_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n  Compiling WiX source: {wxs_path}")
    candle_cmd = [
        str(candle_exe),
        "-arch", "x64",
        "-out", str(wixobj_path),
        str(wxs_path),
    ]

    result = subprocess.run(candle_cmd, cwd=str(STRATUM_SRC), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\n❌ candle.exe failed:")
        if result.stdout.strip():
            print(result.stdout)
        if result.stderr.strip():
            print(result.stderr)
        return False

    print(f"  ✓ Compiled: {wixobj_path}")

    # Link .wixobj -> .msi
    msi_path = DIST_DIR / "Stratum.msi"
    msi_path.parent.mkdir(parents=True, exist_ok=True)

    light_cmd = [
        str(light_exe),
        "-out", str(msi_path),
        str(wixobj_path),
    ]

    print(f"\n  Linking MSI: {msi_path}")
    result = subprocess.run(light_cmd, cwd=str(STRATUM_SRC), capture_output=True, text=True)
    if result.returncode != 0:
        # Light often gives warnings (LGHT1076) about ICE validation but still produces the MSI
        # Only treat as failure if the output file wasn't created
        if result.stderr.strip():
            print(result.stderr)
        # Check if MSI was produced despite warnings
        if msi_path.exists():
            print(f"\n⚠  light.exe reported warnings, but MSI was created.")
        else:
            print(f"\n❌ light.exe failed:")
            if result.stdout.strip():
                print(result.stdout)
            if result.stderr.strip():
                print(result.stderr)
            return False

    if msi_path.exists():
        size_mb = msi_path.stat().st_size / (1024 * 1024)
        print(f"\n✅ MSI Installer created successfully!")
        print(f"   Location: {msi_path}")
        print(f"   Size: {size_mb:.1f} MB")
        return True
    else:
        print(f"\n❌ MSI file not found at expected location: {msi_path}")
        return False


def validate_exe():
    """Run basic validation on the built EXE."""
    exe_path = DIST_DIR / "Stratum.exe"
    if not exe_path.exists():
        print("  ⚠  No EXE to validate.")
        return False

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"\n  EXE validation:")
    print(f"    File: {exe_path}")
    print(f"    Size: {size_mb:.1f} MB")

    if size_mb > 400:
        print("    ⚠  WARNING: EXE is very large (>400 MB). Consider removing")
        print("       unnecessary --exclude-module entries or --collect-all flags.")
    elif size_mb > 300:
        print("    ⚠  EXE is large. Acceptable if PyQt6 + numpy + pandas + cryptography are bundled.")
    else:
        print("    ✅ Size is reasonable.")

    # Check it's a valid PE executable (has MZ header)
    try:
        with open(exe_path, "rb") as f:
            header = f.read(2)
        if header == b"MZ":
            print("    ✅ Valid PE executable (MZ header present).")
        else:
            print("    ⚠  Unexpected file header — may not be a valid EXE.")
    except Exception as e:
        print(f"    ⚠  Could not read EXE: {e}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Build Stratum distribution (EXE and/or MSI installer).",
        epilog="Examples:\n"
               "  python build_msi.py              # Build MSI (default)\n"
               "  python build_msi.py --portable    # Build portable EXE only\n"
               "  python build_msi.py --msi         # Build MSI explicitly\n"
               "  python build_msi.py --all         # Build both portable EXE and MSI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--portable", action="store_true", help="Build portable single-file EXE only")
    group.add_argument("--msi", action="store_true", help="Build MSI installer (default)")
    group.add_argument("--all", action="store_true", help="Build both portable EXE and MSI installer")

    args = parser.parse_args()

    # Default: --msi if no flag given
    if args.portable:
        mode = "portable"
    elif args.all:
        mode = "all"
    else:
        mode = "msi"

    success = True

    if mode in ("portable", "all"):
        print()
        ok = build_pyinstaller(mode="portable")
        if ok:
            validate_exe()
        if not ok:
            success = False
            print("\n  ❌ Portable build failed.\n")
        else:
            print("\n  ✅ Portable build completed.\n")

    if mode in ("msi", "all"):
        ok = build_msi()
        if not ok:
            success = False
            print("\n  ❌ MSI build failed.\n")
        else:
            print("\n  ✅ MSI build completed.\n")

    if success:
        print("=" * 60)
        print("  ✅ All builds completed successfully!")
        print("=" * 60)
        if mode in ("portable", "all"):
            print(f"     Portable EXE: {DIST_DIR / 'Stratum.exe'}")
        if mode in ("msi", "all"):
            print(f"     MSI Installer: {DIST_DIR / 'Stratum.msi'}")
        print()
    else:
        print("=" * 60)
        print("  ❌ Build completed with errors. See messages above.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
