"""
gliamispo.breakdown.orchestrator
----------------------------------
Orchestratore del breakdown: coordina FountainParser → NLPPipeline → ML → DB.

Soglie di confidenza (aggiornate — BUG-P2-H fix):

  >= 0.75   → Elemento inserito, ai_suggested=1, user_verified=0
               Note: None  (alta confidenza, accettato automaticamente)

  0.60–0.74 → Elemento inserito, ai_suggested=1, user_verified=0
               Note: "⚠️ Da verificare (AI: XX%)"
               (confidenza media: visibile ma marcato per revisione)

  < 0.60    → Elemento SCARTATO (troppo rumoroso)

Il valore ml_min_confidence nel DB (progetto) agisce come soglia
configurabile per la fascia inferiore. Default: 0.60.
La soglia di alta confidenza è fissa a 0.75.
"""

import asyncio
import json
import re as _re
from gliamispo.models.scene_element import SceneElement
from gliamispo.models.eighths import Eighths

# Soglia di alta confidenza — elementi accettati senza nota
_HIGH_CONFIDENCE_THRESHOLD = 0.75

# Soglia minima assoluta — sotto questo valore si scarta sempre
_ABSOLUTE_MIN_CONFIDENCE = 0.60


class BreakdownOrchestrator:
    def __init__(self, parser, nlp_pipeline, database,
                 feedback_loop, ml_inference):
        self._parser   = parser
        self._nlp      = nlp_pipeline
        self._db       = database
        self._feedback = feedback_loop
        self._ml       = ml_inference

    async def run_breakdown(self, script_path: str, project_id: int,
                            on_progress=None) -> None:
        # Leggi la soglia minima dal progetto (configurabile dall'utente)
        proj_row = self._db.execute(
            "SELECT ml_min_confidence FROM projects WHERE id = ?",
            (project_id,)
        ).fetchone()
        min_confidence = (
            proj_row[0] if proj_row and proj_row[0] is not None
            else _ABSOLUTE_MIN_CONFIDENCE
        )
        # Clamp di sicurezza: non scendere mai sotto la soglia assoluta
        min_confidence = max(min_confidence, _ABSOLUTE_MIN_CONFIDENCE)

        with open(script_path, encoding='utf-8') as f:
            text = f.read()

        parsed_scenes = self._parser.parse(text)
        total = len(parsed_scenes)
        if total == 0:
            if on_progress:
                on_progress(1.0, "Nessuna scena trovata")
            return

        # ── Passata 0: vocabolario globale dei personaggi ─────────────────
        # char_lower → (canonical_title, n_scenes_with_dialogue)
        all_known_chars: dict = {}
        _char_freq: dict = {}
        for ps in parsed_scenes:
            for char in ps.characters:
                key = char.lower()
                all_known_chars[key] = char.title()
                _char_freq[key] = _char_freq.get(key, 0) + 1

        # ── Passata 1: elaborazione scena per scena ───────────────────────
        for i, ps in enumerate(parsed_scenes):
            pct = (i + 1) / total
            if on_progress:
                on_progress(pct * 0.6, f"NLP scena {i + 1}/{total}")

            scene_context = {
                "location":  ps.location,
                "int_ext":   ps.int_ext,
                "day_night": ps.day_night,
            }

            # ── Cast dal parser (confidence alta — fonte primaria) ────────
            char_elements = [
                SceneElement(
                    category="Cast",
                    element_name=char.title(),
                    ai_suggested=1,
                    ai_confidence=0.92,
                    detection_method="fountain_parser",
                )
                for char in ps.characters
            ]

            # ── Cast da "known character lookup" nel synopsis ─────────────
            # Cerca ogni personaggio noto nel testo di azione della scena.
            # Strategia a tre livelli (BUG-4 fix):
            #   1. Ricerca case-sensitive del nome in Title Case → conf 0.85
            #   2. Ricerca case-sensitive in ALL CAPS               → conf 0.82
            #   3. Ricerca IGNORECASE (esclude tutto-minuscolo)      → conf 0.80
            # I personaggi frequenti (≥ 2 scene con dialogo) ricevono +0.03.
            seen_in_scene = {e.element_name.lower() for e in char_elements}
            known_char_elements = []
            for char_lower, char_title in all_known_chars.items():
                if char_lower in seen_in_scene:
                    continue
                pat = r'\b' + _re.escape(char_lower) + r'\b'
                # Livello 1 – Title Case esplicito
                m = _re.search(r'\b' + _re.escape(char_title) + r'\b',
                                ps.synopsis)
                conf_base = 0.85
                if not m:
                    # Livello 2 – ALL CAPS esplicito
                    m = _re.search(r'\b' + _re.escape(char_lower.upper()) + r'\b',
                                   ps.synopsis)
                    conf_base = 0.82
                if not m:
                    # Livello 3 – IGNORECASE, ma rifiuta tutto-minuscolo
                    m = _re.search(pat, ps.synopsis, _re.IGNORECASE)
                    if m and m.group(0)[0].islower():
                        m = None
                    conf_base = 0.80
                if not m:
                    continue
                freq = _char_freq.get(char_lower, 0)
                conf = conf_base + (0.03 if freq >= 2 else 0.0)
                seen_in_scene.add(char_lower)
                known_char_elements.append(SceneElement(
                    category="Cast",
                    element_name=char_title,
                    ai_suggested=1,
                    ai_confidence=min(conf, 0.92),
                    detection_method="known_character_lookup",
                ))

            # ── NLP pipeline sul synopsis (async, 3 flussi paralleli) ─────
            nlp_elements = await self._nlp.process_scene(
                ps.synopsis, scene_context,
                known_chars=set(all_known_chars.keys()),
            )

            # ── ML inference ──────────────────────────────────────────────
            ml_elements  = self._ml.predict(ps.synopsis)
            elements     = (char_elements + known_char_elements
                            + nlp_elements)
            elements     = self._merge_ml(elements, ml_elements)
            elements     = self._resolve_conflicts(elements)

            # ── Calcolo eighths ───────────────────────────────────────────
            start_e = Eighths.from_decimal(ps.page_start)
            end_e   = Eighths.from_decimal(ps.page_end)

            # ── Inserimento scena ─────────────────────────────────────────
            raw_blocks_json = json.dumps(
                ps.raw_blocks, ensure_ascii=False
            ) if ps.raw_blocks else None

            scene_id = self._db.execute(
                "INSERT INTO scenes "
                "(project_id, scene_number, location, "
                "int_ext, day_night, "
                "page_start_whole, page_start_eighths, "
                "page_end_whole, page_end_eighths, synopsis, raw_blocks) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    project_id, ps.scene_number, ps.location,
                    ps.int_ext, ps.day_night,
                    start_e.whole, start_e.eighths,
                    end_e.whole,   end_e.eighths,
                    ps.synopsis,
                    raw_blocks_json,
                )
            ).lastrowid

            # ── Inserimento elementi con soglie confidenza ────────────────
            for elem in elements:
                conf = elem.ai_confidence or 0.0

                # Sotto la soglia minima: scarta
                if conf < min_confidence:
                    continue

                # Blacklist: l'utente ha eliminato questo elemento
                rejected = self._db.execute(
                    "SELECT 1 FROM rejected_elements "
                    "WHERE element_name = ? "
                    "AND (category = ? OR category IS NULL)",
                    (elem.element_name, elem.category)
                ).fetchone()
                if rejected:
                    continue

                # Fascia media (min_confidence ≤ conf < 0.75): "da verificare"
                if conf < _HIGH_CONFIDENCE_THRESHOLD:
                    pct_str = f"{int(conf * 100)}%"
                    note    = f"⚠️ Da verificare (AI: {pct_str})"
                else:
                    note = None

                self._db.execute(
                    "INSERT OR IGNORE INTO scene_elements "
                    "(scene_id, category, element_name, "
                    "ai_suggested, ai_confidence, "
                    "detection_method, notes) "
                    "VALUES (?,?,?,1,?,?,?)",
                    (
                        scene_id,
                        elem.category,
                        elem.element_name,
                        conf,
                        getattr(elem, "detection_method", "unknown"),
                        note,
                    )
                )

            self._feedback.track_import(scene_id, len(elements))

            if on_progress:
                on_progress(0.6 + pct * 0.3, f"Inserita scena {i + 1}")

        self._db.commit()

        if on_progress:
            on_progress(1.0, "Breakdown completato")

    # ── Helpers privati ───────────────────────────────────────────────────────

    def _merge_ml(self, nlp_elements: list, ml_elements: list) -> list:
        existing = {
            (e.category, e.element_name.lower())
            for e in nlp_elements
        }
        for ml_e in ml_elements:
            key = (ml_e.category, ml_e.element_name.lower())
            if key not in existing:
                nlp_elements.append(ml_e)
                existing.add(key)
        return nlp_elements

    def _resolve_conflicts(self, elements: list) -> list:
        by_key: dict = {}
        for e in elements:
            key = (e.element_name.lower(), e.category)
            if key not in by_key or \
               (e.ai_confidence or 0) > (by_key[key].ai_confidence or 0):
                by_key[key] = e
        return list(by_key.values())
