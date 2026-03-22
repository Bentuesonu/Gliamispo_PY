"""Resolve package data files in both normal and PyInstaller-frozen mode."""
import os
import sys
from pathlib import Path


def _is_frozen():
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def resource_path(package_dotted, filename):
    if _is_frozen():
        parts = package_dotted.split(".")
        return Path(sys._MEIPASS, *parts, filename)

    from importlib.resources import files
    return files(package_dotted).joinpath(filename)
