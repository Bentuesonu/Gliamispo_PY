#!/usr/bin/env python3
"""Build Gliamispo executable with PyInstaller."""
import subprocess
import sys

def main():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "gliamispo.spec",
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print("\nBuild complete. Output in dist/Gliamispo/")


if __name__ == "__main__":
    main()
