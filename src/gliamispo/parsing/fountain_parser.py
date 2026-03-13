"""
gliamispo.parsing.fountain_parser
----------------------------------
Parser per sceneggiature in formato Fountain / adattamento italiano.

FIX applicati rispetto alla versione originale:
  FIX-P1-H  — Calcolo pagine: FOUNTAIN_LINES_PER_PAGE = 56 (non 0.125)
  FIX-P2-F  — Numero scena estratto dallo slug line (non sequenziale)
  FIX-P2-G  — Slug line NON incluso nel synopsis
  BUG-P2-K  — Blacklist _STAGE_DIRECTION_BLACKLIST estesa con
               keyword cinematografiche italiane mancanti (v6)
  EURISTICA  — Un character header valido deve essere preceduto
               da almeno una riga vuota
  FIX-P7-A  — In dialogue mode: riconosce character cue senza riga vuota;
               esce da dialogue quando incontra narrativa lunga (≥8 parole)
  FIX-P7-B  — Merge consecutive lines: righe consecutive dello stesso tipo
               (senza riga vuota di mezzo) vengono unite in un singolo blocco
"""

import re

FOUNTAIN_LINES_PER_PAGE = 56   # FIX-P1-H: standard industry (non 0.125)

# ── Prefisso numerico di scena ────────────────────────────────────────────────
_SCENE_NUM_RE = re.compile(r'^(\d+[A-Za-z]?)\.?\s+')

# ── Numero di pagina standalone (es. "2.", "42", "2. ") → da scartare ─────────
_PAGE_NUMBER_RE = re.compile(r'^\d+\.?\s*$')

# ── Pattern INT/EXT (ordine importante: più lunghi prima) ─────────────────────
_IE_PATTERNS = [
    ('INT/EXT', 'INT/EXT'), ('INT-EXT', 'INT/EXT'), ('I/E', 'INT/EXT'),
    ('INT.',    'INT'),      ('INT ',    'INT'),      ('INT-',  'INT'),
    ('INTERNO', 'INT'),      ('INTERNI', 'INT'),
    ('EXT.',    'EXT'),      ('EXT ',    'EXT'),      ('EXT-',  'EXT'),
    ('EST.',    'EXT'),      ('EST ',    'EXT'),      ('EST-',  'EXT'),
    ('ESTERNO', 'EXT'),      ('ESTERNI', 'EXT'),
    ('I.',      'INT'),
]

# ── Mapping giorno/notte ──────────────────────────────────────────────────────
_DAYNIGHT_MAP = [
    ('NOTTE',      'NOTTE'),
    ('NIGHT',      'NOTTE'),
    ('POMERIGGIO', 'GIORNO'),
    ('AFTERNOON',  'GIORNO'),
    ('MATTINA',    'GIORNO'),
    ('MATTINO',    'GIORNO'),
    ('MORNING',    'GIORNO'),
    ('GIORNO',     'GIORNO'),
    ('DAY',        'GIORNO'),
    ('TRAMONTO',   'TRAMONTO'),
    ('DUSK',       'TRAMONTO'),
    ('SERA',       'TRAMONTO'),
    ('EVENING',    'TRAMONTO'),
    ('ALBA',       'ALBA'),
    ('DAWN',       'ALBA'),
    ('CONTINUA',   'CONTINUO'),
    ('CONTINUO',   'CONTINUO'),
    ('CONTINUOUS', 'CONTINUO'),
    ('LATER',      'CONTINUO'),
]

# ── Regex per personaggi: ALL CAPS, max 3 token, max 20 char per token ────────
# FIX-P2-F: usa fullmatch per evitare falsi positivi su frasi lunghe.
_CHARACTER_RE = re.compile(
    r"^[A-Z\u00C0-\u00DC][A-Z\u00C0-\u00DC.'\"-]{0,19}"
    r"(?:\s+[A-Z\u00C0-\u00DC.'\"-]{1,19}){0,2}$"
)

# ── Blacklist stage directions ────────────────────────────────────────────────
# BUG-P2-K FIX: aggiunta massiva di keyword italiane mancanti
# che in maiuscolo sembravano nomi di personaggi.
_STAGE_DIRECTION_BLACKLIST = frozenset({
    # ── Transizioni / montaggio ──────────────────────────────────────────────
    "FINE", "THE END", "END",
    "DISSOLVENZA IN NERO", "DISSOLVENZA", "DISSOLVE TO",
    "FADE OUT", "FADE IN", "FADE TO BLACK", "FADE TO WHITE",
    "SMASH CUT", "MATCH CUT", "CUT TO", "CUT",
    "TAGLIO", "TAGLIO A",
    "TENDINA", "WIPE",
    "TIME LAPSE", "SLOW MOTION", "RALENTI",

    # ── POV e soggettive ─────────────────────────────────────────────────────
    "POV", "INIZIO POV", "FINE POV",
    "SOGGETTIVA", "INIZIO SOGGETTIVA", "FINE SOGGETTIVA",

    # ── Flashback / Flashforward ─────────────────────────────────────────────
    "FLASHBACK", "FINE FLASHBACK", "INIZIO FLASHBACK",
    "FLASHFORWARD", "FINE FLASHFORWARD",
    "FLASH FORWARD", "FINE FLASH FORWARD",

    # ── Sogno / Visione ───────────────────────────────────────────────────────
    "SOGNO", "FINE SOGNO", "INIZIO SOGNO",
    "VISIONE", "FINE VISIONE", "INIZIO VISIONE",
    "ALLUCINAZIONE",

    # ── Termini tecnici di regia ──────────────────────────────────────────────
    "PRIMO PIANO", "CAMPO TOTALE", "CAMPO MEDIO",
    "PIANO AMERICANO", "PIANO SEQUENZA",
    "CARRELLATA", "PANORAMICA", "ZOOM", "PUSH IN", "PULL OUT",
    "INSERTO", "DETTAGLIO",

    # ── Voci fuori campo ─────────────────────────────────────────────────────
    "V.O.", "V.O", "O.S.", "O.S", "O.C.", "O.C",
    "VOCE FUORI CAMPO",

    # ── Didascalie temporali ──────────────────────────────────────────────────
    "PIU TARDI", "UN MOMENTO DOPO", "DOPO",
    "PIÙ TARDI", "POCO DOPO",

    # ── Scena e scenografia ───────────────────────────────────────────────────
    "NERO", "BUIO", "BIANCO",
    "CONTINUA", "CONTINUO", "CONTINUOUS",
    "TESTO", "TITOLO", "SOTTOTITOLO",
    "SUPER",          # BUG-P2-K: "SUPER: Anno 1943" non è un personaggio
    "CARTELLO",       # BUG-P2-K
    "DIDASCALIA",     # BUG-P2-K
    "RIPRESA",        # BUG-P2-K
    "SUCCESSIVO",     # BUG-P2-K
    "PRECEDENTE",     # BUG-P2-K
    "PROSEGUE",       # BUG-P2-K
    "SEGUE",          # BUG-P2-K

    # ── Indicazioni di azione / effetti in maiuscolo ──────────────────────────
    # (spesso scritte in caps per enfasi nei copioni italiani)
    "SILENZIO",       # BUG-P2-K
    "PAUSA",          # BUG-P2-K
    "STOP",           # BUG-P2-K
    "VIA",            # BUG-P2-K
    "BASTA",          # BUG-P2-K
    "AIUTO",          # BUG-P2-K
    "FUOCO",          # BUG-P2-K — anche se è Special FX, non un personaggio
    "ATTENZIONE",     # BUG-P2-K
    "PERICOLO",       # BUG-P2-K
    "APPLAUSI",       # BUG-P2-K
    "RISATE",         # BUG-P2-K
    "URLA",           # BUG-P2-K
    "SPARI",          # BUG-P2-K

    # ── Interiezioni e risposte in maiuscolo ──────────────────────────────────
    "BOOM",           # BUG-P2-K
    "BANG",           # BUG-P2-K
    "CRACK",          # BUG-P2-K
    "SPLASH",         # BUG-P2-K
    "OK",             # BUG-P2-K
    "SÌ",             # BUG-P2-K
    "SI",             # BUG-P2-K
    "NO",             # BUG-P2-K
    "EH", "AH", "OH", "UH",  # BUG-P2-K
    "BENE",           # BUG-P2-K
    "BRAVO", "BRAVA", # BUG-P2-K
    "GRAZIE",         # BUG-P2-K
    "PREGO",          # BUG-P2-K
    "CIAO",           # BUG-P2-K
    "ADDIO",          # BUG-P2-K
    "ARRIVEDERCI",    # BUG-P2-K
    "SALVE",          # BUG-P2-K
})

# Prefissi che invalidano il token successivo come personaggio
_STAGE_DIRECTION_PREFIXES = (
    "INIZIO POV ",
    "FINE POV ",
    "INIZIO SOGGETTIVA ",
    "FINE SOGGETTIVA ",
    "INIZIO FLASHBACK",
    "FINE FLASHBACK",
    "INIZIO SOGNO",
    "FINE SOGNO",
)

# Limite synopsis per bilanciare completezza e memoria
_SYNOPSIS_MAX_CHARS = 8000

# FIX-P7-A: soglia parole per uscire da dialogue mode
_NARRATIVE_WORD_THRESHOLD = 8


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


class ParsedScene:
    __slots__ = ('scene_number', 'location', 'int_ext', 'day_night',
                 'page_start', 'page_end', 'synopsis', 'characters',
                 'raw_blocks')

    def __init__(self):
        self.scene_number = ''
        self.location     = ''
        self.int_ext      = 'INT'
        self.day_night    = 'GIORNO'
        self.page_start   = 0.0
        self.page_end     = 0.0
        self.synopsis     = ''
        self.characters   = []
        self.raw_blocks   = []  # lista di dict {"type": ..., "text": ...}


def _parse_scene_heading(line):
    working = line.strip()
    if not working:
        return None

    upper     = working.upper()
    scene_num = None

    # FIX-P2-F: estrae il numero di scena dallo slug, non usare indice seq.
    m = _SCENE_NUM_RE.match(working)
    if m:
        scene_num = m.group(1)
        working   = working[m.end():]
        upper     = working.upper()

    matched_ie  = None
    matched_len = 0
    for prefix, ie_val in _IE_PATTERNS:
        if upper.startswith(prefix):
            matched_ie  = ie_val
            matched_len = len(prefix)
            break

    if matched_ie is None:
        return None

    rest       = working[matched_len:].strip(' .\t')
    upper_rest = rest.upper()

    day_night = 'GIORNO'
    dn_end    = len(rest)

    sep_match = re.search(r'\s*[-–—]\s*([A-Z]+)', upper_rest)
    if sep_match:
        keyword = sep_match.group(1)
        for kw, dn_val in _DAYNIGHT_MAP:
            if keyword.startswith(kw):
                day_night = dn_val
                dn_end    = sep_match.start()
                break

    if dn_end == len(rest):
        for kw, dn_val in _DAYNIGHT_MAP:
            idx = upper_rest.rfind(kw)
            if idx != -1:
                if idx == 0 or upper_rest[idx - 1] in (' ', '-', '–', '—'):
                    day_night = dn_val
                    dn_end    = idx
                    break

    loc = rest[:dn_end].strip(' -–—\t')
    if not loc:
        loc = 'LOCATION SCONOSCIUTA'

    loc = re.sub(r'\s{2,}', ' ', loc)

    return scene_num, matched_ie, loc, day_night


def _merge_consecutive_blocks(raw_blocks):
    """FIX-P7-B: unisce blocchi consecutivi dello stesso tipo in un unico blocco."""
    if not raw_blocks:
        return raw_blocks

    merged = [dict(raw_blocks[0])]
    for b in raw_blocks[1:]:
        prev = merged[-1]
        # Merge solo action con action, dialogue con dialogue
        if b["type"] == prev["type"] and b["type"] in ("action", "dialogue"):
            prev["text"] = prev["text"] + " " + b["text"]
        else:
            merged.append(dict(b))

    return merged


class FountainParser:
    def parse(self, text):
        if not text:
            return []

        # Rimuovi il frontmatter Fountain (Title:, Author: ecc.)
        stripped = text.lstrip()
        if stripped.startswith('Title:') or stripped.startswith('title:'):
            parts = re.split(r'\n\n', text, 1)
            if len(parts) == 2:
                text = parts[1]

        lines        = text.splitlines()
        scenes       = []
        current      = None
        scene_seq    = 0

        _prev_was_blank  = True
        _prev_block_type = None
        _in_dialogue     = False

        for line_num, line in enumerate(lines, 1):
            raw     = line.rstrip()
            trimmed = raw.strip()

            # ── Riga vuota ────────────────────────────────────────────────────
            if not trimmed:
                _in_dialogue    = False
                _prev_was_blank = True
                continue

            # ── Commenti Fountain ─────────────────────────────────────────────
            if trimmed.startswith('/*') or trimmed.startswith('[['):
                continue

            # ── Numero di pagina (es. "2.", "42", "2. ") → scarta ─────────────
            if _PAGE_NUMBER_RE.match(trimmed):
                _prev_was_blank = False
                continue

            # ── Slug line? ────────────────────────────────────────────────────
            result = _parse_scene_heading(trimmed)
            if result:
                _in_dialogue     = False
                _prev_was_blank  = True
                _prev_block_type = "slug"

                if current:
                    current.page_end = line_num / FOUNTAIN_LINES_PER_PAGE
                    current.raw_blocks = _merge_consecutive_blocks(current.raw_blocks)
                    scenes.append(current)

                scene_seq += 1
                sn, ie, loc, dn = result

                current = ParsedScene()
                current.scene_number = sn if sn else str(scene_seq)
                current.int_ext      = ie
                current.location     = loc
                current.day_night    = dn
                current.page_start   = line_num / FOUNTAIN_LINES_PER_PAGE
                continue

            if current is None:
                _prev_was_blank = False
                continue

            # ── FIX-P7-A: Dentro un dialogo, check se dobbiamo uscirne ───────
            if _in_dialogue:
                # (a) Nuovo character cue? (priorità massima)
                if _is_character_candidate(trimmed):
                    char_name = re.sub(r'\s*\(.*?\)', '', trimmed).strip()
                    if char_name and char_name not in current.characters:
                        current.characters.append(char_name)
                    current.raw_blocks.append({"type": "character", "text": trimmed})
                    _prev_was_blank  = False
                    _prev_block_type = "character"
                    # _in_dialogue rimane True (nuovo dialogo)
                    continue

                # (b) Parentetica?
                if trimmed.startswith('(') and trimmed.endswith(')'):
                    current.raw_blocks.append({"type": "parenthetical", "text": trimmed})
                    _prev_block_type = "parenthetical"
                    if len(current.synopsis) < _SYNOPSIS_MAX_CHARS:
                        if current.synopsis:
                            current.synopsis += '\n'
                        current.synopsis += trimmed.lower()
                    _prev_was_blank = False
                    continue

                # (c) Riga lunga di narrativa → esce da dialogue
                if len(trimmed.split()) >= _NARRATIVE_WORD_THRESHOLD:
                    _in_dialogue = False
                    # cade nel blocco action sotto
                else:
                    # Dialogo breve/medio → resta dialogue
                    current.raw_blocks.append({"type": "dialogue", "text": trimmed})
                    _prev_block_type = "dialogue"
                    if len(current.synopsis) < _SYNOPSIS_MAX_CHARS:
                        if current.synopsis:
                            current.synopsis += '\n'
                        current.synopsis += trimmed.lower()
                    _prev_was_blank = False
                    continue

            # ── Character header? ─────────────────────────────────────────────
            _context_ok = _prev_was_blank or _prev_block_type in (
                "action", "transition", "slug"
            )
            if (
                _CHARACTER_RE.fullmatch(trimmed)
                and not _is_stage_direction(trimmed)
                and _context_ok
            ):
                char_name = re.sub(r'\s*\(.*?\)', '', trimmed).strip()
                if char_name and char_name not in current.characters:
                    current.characters.append(char_name)
                current.raw_blocks.append({"type": "character", "text": trimmed})
                _in_dialogue     = True
                _prev_was_blank  = False
                _prev_block_type = "character"
                continue

            # ── Testo di azione → aggiunto al synopsis ────────────────────────
            is_transition = (
                trimmed.isupper() and len(trimmed) < 40
                and any(trimmed.startswith(t) for t in (
                    'FADE', 'CUT', 'DISSOLV', 'SMASH', 'MATCH',
                    'TAGLIO', 'TENDINA', 'WIPE',
                ))
            )
            if is_transition:
                current.raw_blocks.append({"type": "transition", "text": trimmed})
                _prev_block_type = "transition"
            else:
                current.raw_blocks.append({"type": "action", "text": trimmed})
                _prev_block_type = "action"

            if len(current.synopsis) < _SYNOPSIS_MAX_CHARS:
                if current.synopsis:
                    current.synopsis += '\n'
                current.synopsis += trimmed

            _prev_was_blank = False

        # Chiudi l'ultima scena
        if current:
            current.page_end = len(lines) / FOUNTAIN_LINES_PER_PAGE
            current.raw_blocks = _merge_consecutive_blocks(current.raw_blocks)
            scenes.append(current)

        return scenes
