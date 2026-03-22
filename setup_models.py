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


def download_sentence_transformers():
    """
    Scarica il modello sentence-transformers per synopsis avanzate.

    Questo è opzionale — Gliamispo funziona anche senza.
    Il modello "paraphrase-multilingual-MiniLM-L12-v2" (~420MB) viene
    scaricato nella cache locale (~/.cache/torch/sentence_transformers/).

    Uso:
        python setup_models.py --sentence-transformers
    """
    print("\n" + "=" * 60)
    print("Gliamispo — Setup modello sentence-transformers (opzionale)")
    print("=" * 60)

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("✗ sentence-transformers non installato.")
        print("  Installa con: pip install 'gliamispo[nlp-extra]'")
        return False

    model_name = "paraphrase-multilingual-MiniLM-L12-v2"
    print(f"\n→ Download modello {model_name} (~420MB)...")
    print("  Questo potrebbe richiedere alcuni minuti.\n")

    try:
        # Il download avviene automaticamente se il modello non è in cache
        model = SentenceTransformer(model_name)
        print(f"✓ Modello {model_name} scaricato e pronto.")
        print("  Le sinossi useranno ora embedding semantici avanzati.")
        return True
    except Exception as e:
        print(f"✗ Errore durante il download: {e}")
        print("  Gliamispo funzionerà comunque con metodi alternativi.")
        return False


if __name__ == "__main__":
    import sys

    if "--sentence-transformers" in sys.argv or "--st" in sys.argv:
        download_sentence_transformers()
    else:
        main()
        print("\n" + "-" * 60)
        print("Per scaricare anche il modello sentence-transformers (opzionale):")
        print("  python setup_models.py --sentence-transformers")
