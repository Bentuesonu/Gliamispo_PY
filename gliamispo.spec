# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

# ── spaCy model data — aggiunto per Opzione D (v1.1.0) ───────────────────────
import importlib

def get_spacy_model_datas(model_name):
    """Raccoglie tutti i file di dati di un modello spaCy per PyInstaller."""
    try:
        mod = importlib.import_module(model_name)
        model_path = Path(mod.__file__).parent
        datas = []
        for f in model_path.rglob("*"):
            if f.is_file():
                rel = f.relative_to(model_path.parent.parent)
                datas.append((str(f), str(rel.parent)))
        return datas
    except ImportError:
        print(f"[spec] Modello spaCy '{model_name}' non trovato — bundle senza NLP avanzata.")
        return []

_spacy_datas = (
    get_spacy_model_datas("it_core_news_lg") +
    get_spacy_model_datas("en_core_web_sm")
)
# ─────────────────────────────────────────────────────────────────────────────

block_cipher = None

SRC = Path("src/gliamispo")

# Data files to bundle (source, dest_in_bundle)
datas = [
    (str(SRC / "database" / "schema.sql"), "gliamispo/database"),
]

# Include ML resources if they exist
resources_dir = SRC / "resources"
for pattern in ("*.pkl", "*.onnx"):
    for f in resources_dir.glob(pattern):
        datas.append((str(f), "gliamispo/resources"))

a = Analysis(
    [str(SRC / "__main__.py")],
    pathex=["src"],
    binaries=[],
    datas=[*datas, *_spacy_datas],
    hiddenimports=[
        "PySide6",
        "PySide6.QtWidgets",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtSvg",
        "gliamispo",
        "gliamispo.database",
        "gliamispo.database.manager",
        "gliamispo.database.migrations",
        "gliamispo.models",
        "gliamispo.nlp",
        "gliamispo.parsing",
        "gliamispo.scheduling",
        "gliamispo.ml",
        "gliamispo.breakdown",
        "gliamispo.export",
        "gliamispo.import_",
        "gliamispo.ui",
        "gliamispo.services",
        "gliamispo.resources",
        "sklearn",
        "sklearn.ensemble",
        "sklearn.preprocessing",
        "it_core_news_lg",
        "en_core_web_sm",
        "spacy",
        "spacy.lang.it",
        "spacy.lang.en",
        "thinc",
        "blis",
        "cymem",
        "preshed",
        "murmurhash",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "notebook",
        "IPython",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Gliamispo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="src/gliamispo/resources/icon.icns" if sys.platform == "darwin" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Gliamispo",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Gliamispo.app",
        icon="src/gliamispo/resources/icon.icns",
        bundle_identifier="it.gliamispo.app",
        codesign_identity=None,  # Firma esterna via scripts/notarize_mac.sh
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "1.0.0",
        },
    )
