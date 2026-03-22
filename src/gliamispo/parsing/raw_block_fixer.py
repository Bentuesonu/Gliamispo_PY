"""
gliamispo.parsing.raw_block_fixer
-----------------------------------
Fix-P3-B: re-classifica raw_blocks già parsati dove il character header
è stato erroneamente salvato come "action" per mancanza di riga vuota.

FIX-P7-C: gestisce anche blocchi "dialogue" classificati erroneamente:
  - "dialogue" che è un character candidate → promosso a "character"
  - "dialogue" con ≥ N parole (narrativa lunga) → promosso a "action"
  - Dopo il fix, merge blocchi consecutivi dello stesso tipo

Algoritmo:
  1. Scorri i blocchi sequenzialmente.
  2. Un blocco "action" che corrisponde a CHARACTER_RE e non è in blacklist
     viene promosso a "character".
  3. Dopo un "character", tutti i blocchi successivi vengono promossi a
     "dialogue" / "parenthetical" FINO A quando si incontra un blocco
     con ≥ NARRATIVE_WORD_THRESHOLD parole (= lunga narrativa)
     o un character candidate (= nuovo dialogo).
  4. I blocchi "dialogue" vengono controllati: se sono character candidate
     vengono promossi a "character"; se sono narrativa lunga tornano ad "action".
  5. Blocchi consecutivi dello stesso tipo vengono uniti.
"""

import re

# Regex per rilevare artefatti di esportazione PDF (Celtx, Final Draft, Fade In, etc.)
# Questi metadati di stampa/browser finiscono nel testo parsato e vanno scartati.
_PDF_ARTIFACT_RE = re.compile(
    r"about:blank|"
    r"Pagina\s+\d+\s+di\s+\d+|"
    r"Page\s+\d+\s+of\s+\d+|"
    r"Página\s+\d+\s+de\s+\d+|"
    r"\d{2}/\d{2}/\d{2,4},\s+\d{1,2}:\d{2}",
    re.IGNORECASE,
)


def _is_pdf_artifact(text: str) -> bool:
    """Vero se il blocco contiene artefatti di esportazione PDF da scartare."""
    return bool(_PDF_ARTIFACT_RE.search(text))


_CHARACTER_RE = re.compile(
    r"^[A-Z\u00C0-\u00DC][A-Z\u00C0-\u00DC.'\"\\-]{0,19}"
    r"(?:\s+[A-Z\u00C0-\u00DC.'\"\\-]{1,19}){0,2}$"
)

_STAGE_DIRECTION_BLACKLIST = frozenset({
    "FINE", "THE END", "END",
    "DISSOLVENZA IN NERO", "DISSOLVENZA", "DISSOLVE TO",
    "FADE OUT", "FADE IN", "FADE TO BLACK", "FADE TO WHITE",
    "SMASH CUT", "MATCH CUT", "CUT TO", "CUT",
    "TAGLIO", "TAGLIO A", "TENDINA", "WIPE",
    "TIME LAPSE", "SLOW MOTION", "RALENTI",
    "POV", "INIZIO POV", "FINE POV",
    "SOGGETTIVA", "INIZIO SOGGETTIVA", "FINE SOGGETTIVA",
    "FLASHBACK", "FINE FLASHBACK", "INIZIO FLASHBACK",
    "FLASHFORWARD", "FINE FLASHFORWARD",
    "FLASH FORWARD", "FINE FLASH FORWARD",
    "SOGNO", "FINE SOGNO", "INIZIO SOGNO",
    "VISIONE", "FINE VISIONE", "INIZIO VISIONE", "ALLUCINAZIONE",
    "PRIMO PIANO", "CAMPO TOTALE", "CAMPO MEDIO",
    "PIANO AMERICANO", "PIANO SEQUENZA",
    "CARRELLATA", "PANORAMICA", "ZOOM", "PUSH IN", "PULL OUT",
    "INSERTO", "DETTAGLIO",
    "V.O.", "V.O", "O.S.", "O.S", "O.C.", "O.C",
    "VOCE FUORI CAMPO",
    "PIU TARDI", "UN MOMENTO DOPO", "DOPO",
    "PIÙ TARDI", "POCO DOPO",
    "NERO", "BUIO", "BIANCO",
    "CONTINUA", "CONTINUO", "CONTINUOUS",
    "TESTO", "TITOLO", "SOTTOTITOLO",
    "SUPER", "CARTELLO", "DIDASCALIA", "RIPRESA",
    "SUCCESSIVO", "PRECEDENTE", "PROSEGUE", "SEGUE",
    "SILENZIO", "PAUSA", "STOP", "VIA", "BASTA", "AIUTO",
    "FUOCO", "ATTENZIONE", "PERICOLO", "APPLAUSI",
    "RISATE", "URLA", "SPARI",
    "BOOM", "BANG", "CRACK", "SPLASH",
    "OK", "SÌ", "SI", "NO", "EH", "AH", "OH", "UH",
    "BENE", "BRAVO", "BRAVA", "GRAZIE", "PREGO",
    "CIAO", "ADDIO", "ARRIVEDERCI", "SALVE",
})

_STAGE_DIRECTION_PREFIXES = (
    "INIZIO POV ", "FINE POV ", "INIZIO SOGGETTIVA ", "FINE SOGGETTIVA ",
    "INIZIO FLASHBACK", "FINE FLASHBACK", "INIZIO SOGNO", "FINE SOGNO",
)

# Soglia parole per decidere che un blocco è narrativa (azione) e NON dialogo.
NARRATIVE_WORD_THRESHOLD = 8


def _is_stage_direction(name):
    upper = name.upper()
    if upper in _STAGE_DIRECTION_BLACKLIST:
        return True
    for prefix in _STAGE_DIRECTION_PREFIXES:
        if upper.startswith(prefix):
            return True
    return False


def _is_character_candidate(text):
    return (
        bool(_CHARACTER_RE.fullmatch(text))
        and not _is_stage_direction(text)
    )


def _is_long_narrative(text):
    return len(text.split()) >= NARRATIVE_WORD_THRESHOLD


def _looks_like_parenthetical(text):
    return text.startswith("(") and text.endswith(")")


def _merge_consecutive(blocks):
    """Unisce blocchi consecutivi dello stesso tipo (action+action, dialogue+dialogue)."""
    if not blocks:
        return blocks
    merged = [dict(blocks[0])]
    for b in blocks[1:]:
        prev = merged[-1]
        if b["type"] == prev["type"] and b["type"] in ("action", "dialogue"):
            prev["text"] = prev["text"] + " " + b["text"]
        else:
            merged.append(dict(b))
    return merged


def fix_raw_blocks(raw_blocks):
    """
    Re-classifica raw_blocks già parsati.

    Logica:
    - Ogni blocco "action" che soddisfa CHARACTER_RE (e non è blacklist)
      viene promosso a "character".
    - Dopo un character, i blocchi "action" successivi vengono promossi
      a "dialogue" (o "parenthetical") finché non si incontra:
        * un altro character candidate  → apre nuovo blocco dialogo
        * un blocco con ≥ N parole      → torniamo in modalità action
    - FIX-P7-C: i blocchi "dialogue" vengono anche controllati:
        * character candidate → promosso a "character"
        * narrativa lunga → promosso a "action", uscita da dialogue

    Returns:
        (blocks_corretti, n_modifiche)
    """
    if not raw_blocks:
        return raw_blocks, 0

    # ── Filtra artefatti PDF prima di ogni altra operazione ──────────────────
    raw_blocks = [b for b in raw_blocks if not _is_pdf_artifact(b.get("text", ""))]
    if not raw_blocks:
        return [], 0

    blocks = [dict(b) for b in raw_blocks]
    n = len(blocks)
    changes = 0
    in_dialogue = False

    for i, b in enumerate(blocks):
        btype = b["type"]
        btext = b["text"]

        if btype == "action":
            if in_dialogue:
                if _is_character_candidate(btext):
                    blocks[i]["type"] = "character"
                    changes += 1
                elif _looks_like_parenthetical(btext):
                    blocks[i]["type"] = "parenthetical"
                    changes += 1
                elif _is_long_narrative(btext):
                    in_dialogue = False
                else:
                    blocks[i]["type"] = "dialogue"
                    changes += 1
            else:
                if _is_character_candidate(btext):
                    blocks[i]["type"] = "character"
                    in_dialogue = True
                    changes += 1

        elif btype == "character":
            in_dialogue = True

        elif btype == "dialogue":
            # FIX-P7-C: verifica se un blocco "dialogue" è in realtà un character
            # o narrativa lunga
            if _is_character_candidate(btext):
                blocks[i]["type"] = "character"
                in_dialogue = True
                changes += 1
            elif _is_long_narrative(btext):
                blocks[i]["type"] = "action"
                in_dialogue = False
                changes += 1
            else:
                # Resta dialogue — ok
                in_dialogue = True

        elif btype == "parenthetical":
            in_dialogue = True

        else:
            in_dialogue = False

    # FIX-P7-C: merge blocchi consecutivi dello stesso tipo
    merged = _merge_consecutive(blocks)
    if len(merged) != len(blocks):
        changes += len(blocks) - len(merged)

    return merged, changes