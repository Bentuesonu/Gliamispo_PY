#!/usr/bin/env python3
"""
setup_models.py — Scarica i modelli spaCy per Gliamispo (IT + EN).

Uso (una tantum dopo l'installazione):
    python setup_models.py

Il programma funziona anche senza eseguire questo script,
ma la qualità del riconoscimento Cast sarà inferiore (fallback a regex).

Peso modelli:
  it_core_news_lg   ~560 MB   (italiano — alta qualità NER)
  en_core_web_sm    ~12  MB   (inglese  — modello compatto)
"""

import subprocess
import sys


MODELS = [
    ("it_core_news_lg", "~560 MB", "Italiano (alta qualità NER)"),
    ("en_core_web_sm",  "~12 MB",  "Inglese (modello compatto)"),
]


def download_model(model_name: str) -> bool:
    print(f"\n→ Download {model_name} ...", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "spacy", "download", model_name],
        capture_output=False,
    )
    return result.returncode == 0


def check_model(model_name: str) -> bool:
    try:
        import spacy
        spacy.load(model_name)
        return True
    except OSError:
        return False
    except ImportError:
        return False


def main():
    print("=" * 60)
    print("Gliamispo — Setup modelli NLP spaCy")
    print("=" * 60)

    # Verifica spaCy installato
    try:
        import spacy
        print(f"✓ spaCy {spacy.__version__} installato")
    except ImportError:
        print("✗ spaCy non trovato. Installa prima con:")
        print("  pip install spacy")
        sys.exit(1)

    print()

    for model_name, size, description in MODELS:
        already = check_model(model_name)
        status  = "già installato" if already else f"da scaricare ({size})"
        print(f"  {model_name:25s} {description:35s} [{status}]")

    print()

    errors = []
    for model_name, size, description in MODELS:
        if check_model(model_name):
            print(f"✓ {model_name} già presente, skip.")
            continue

        ok = download_model(model_name)
        if ok:
            print(f"✓ {model_name} installato correttamente.")
        else:
            print(f"✗ Errore durante il download di {model_name}.")
            errors.append(model_name)

    print()
    if errors:
        print(f"⚠️  Modelli non scaricati: {', '.join(errors)}")
        print("   Gliamispo funzionerà in modalità degradata (NER a regex).")
        sys.exit(1)
    else:
        print("✓ Tutti i modelli NLP sono pronti.")
        print("  Avvia Gliamispo normalmente: python -m gliamispo")


if __name__ == "__main__":
    main()
