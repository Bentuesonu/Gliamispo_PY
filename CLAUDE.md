# Gliamispo — Migrazione Swift → Python

## Contesto
Migrazione di un'app macOS di breakdown cinematografico da Swift a Python 3.11+ con PyQt6.
La guida tecnica completa è in `guida_migrazione_gliamispo_v2.md`.

## Regole
- Leggi sempre la guida prima di creare file
- Struttura directory target: src/gliamispo/ con sottomoduli models, database, nlp, ecc.
- Schema DDL: usa esattamente gli schemi in sezione 3.3 della guida
- Migrazioni V2–V10: implementa in database/migrations.py seguendo sezione 3.4
- No type hints nelle firme dei metodi, no docstring, no logging
- Test in tests/ con pytest
