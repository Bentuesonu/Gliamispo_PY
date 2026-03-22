import re as _re

from gliamispo.models.scene_element import SceneElement

# ── FIX 4: rimosso "boom" (falso positivo: BOOM! = effetto sonoro/impatto,
#           non microfono boom). Sostituito con "microfono boom".
# ── FIX 3: rimosso "gatto" (non matcha "gattino") → gestito da Livestock
#           con il pattern aggiornato in ner_extractor e container.
# ── NOTA: l'ordine del dizionario è significativo — i termini più specifici
#          (multi-parola) vanno PRIMA di quelli più corti, per evitare che
#          "macchia di sangue" venga oscurata da "sangue" trovato prima.
COLD_START_RULES: list[tuple[str, str]] = [
    # Props  (multi-parola prima dei singoli)
    ("gratta e vinci",      "Props"),
    ("macchia di sangue",   "Special FX"),   # multi-parola prima di "sangue"
    ("effetto speciale",    "Special FX"),
    ("microfono boom",      "Sound"),         # FIX 4: era "boom"
    ("green screen",        "VFX"),
    # Props singoli
    ("pistola",             "Props"),
    ("coltello",            "Props"),
    ("telefono",            "Props"),
    ("bottiglia",           "Props"),
    ("bicchiere",           "Props"),
    ("borsa",               "Props"),
    ("valigia",             "Props"),
    ("banconota",           "Props"),
    ("portafogli",          "Props"),
    ("bastone",             "Props"),
    ("cartello",            "Props"),
    # Vehicles
    ("panda",               "Vehicles"),      # più specifico prima di "auto"
    ("fiat",                "Vehicles"),
    ("auto",                "Vehicles"),
    ("macchina",            "Vehicles"),
    ("motocicletta",        "Vehicles"),
    ("camion",              "Vehicles"),
    ("elicottero",          "Vehicles"),
    ("moto",                "Vehicles"),
    # Special FX
    ("esplosione",          "Special FX"),
    ("fuoco",               "Special FX"),
    ("pirotecnica",         "Special FX"),
    ("sangue",              "Special FX"),
    ("sudore",              "Special FX"),
    # Makeup
    ("trucco",              "Makeup"),
    ("parrucca",            "Makeup"),
    ("protesi",             "Makeup"),
    # Stunts
    ("stunt",               "Stunts"),
    ("controfigura",        "Stunts"),
    ("caduta",              "Stunts"),
    ("rissa",               "Stunts"),
    ("combattimento",       "Stunts"),
    ("inseguimento",        "Stunts"),
    ("pugno",               "Stunts"),
    ("pugni",               "Stunts"),
    ("picchia",             "Stunts"),
    ("schiaffo",            "Stunts"),
    ("schiaffi",            "Stunts"),
    ("violento",            "Stunts"),
    ("aggredisce",          "Stunts"),
    # Special Equipment
    ("gru",                 "Special Equipment"),
    ("drone",               "Special Equipment"),
    ("steadicam",           "Special Equipment"),
    ("crane",               "Special Equipment"),
    ("carrellata",          "Special Equipment"),
    # Set Dressing
    ("arredamento",         "Set Dressing"),
    ("mobili",              "Set Dressing"),
    ("scenografia",         "Set Dressing"),
    ("sedia",               "Set Dressing"),
    ("tavolo",              "Set Dressing"),
    ("lampada",             "Set Dressing"),
    ("specchio",            "Set Dressing"),
    ("tenda",               "Set Dressing"),
    # Sound
    ("microfono",           "Sound"),
    ("playback",            "Sound"),
    # VFX
    ("CGI",                 "VFX"),
    ("chroma",              "VFX"),
    # Cast — personaggi principali
    ("attore",              "Cast"),
    ("attrice",             "Cast"),
    ("protagonista",        "Cast"),
    ("personaggio",         "Cast"),
    ("interprete",          "Cast"),
    # Cast — figurazioni / background actors
    ("figurante",           "Cast"),
    ("figuranti",           "Cast"),
    ("comparsa",            "Cast"),
    ("comparse",            "Cast"),
    ("folla",               "Cast"),
    ("anziani",             "Cast"),
    ("passanti",            "Cast"),
    # Livestock — FIX 3: aggiunti gattino/gattini oltre a gatto/gatti
    ("gattino",             "Livestock"),
    ("gattina",             "Livestock"),
    ("gatto",               "Livestock"),
    ("gatti",               "Livestock"),
    ("cane",                "Livestock"),
    ("cavallo",             "Livestock"),
    ("uccello",             "Livestock"),
]


class ColdStartClassifier:
    def __init__(self):
        # Precompila i pattern con word boundaries per evitare falsi positivi
        # da sottostringhe (es. "gru" in "gruppo", "moto" in "motore").
        self._rules: list[tuple[_re.Pattern, str, str]] = [
            (_re.compile(r'\b' + _re.escape(term) + r'\b', _re.IGNORECASE), term, category)
            for term, category in COLD_START_RULES
        ]

    def predict(self, text: str, max_results: int = 20,
                min_confidence: float = 0.30) -> list[SceneElement]:
        results: list[SceneElement] = []
        covered_spans: list[tuple[int, int]] = []

        for pattern, term, category in self._rules:
            for m in pattern.finditer(text):
                idx, end = m.start(), m.end()
                already_covered = any(
                    cs <= idx and end <= ce for cs, ce in covered_spans
                )
                if not already_covered:
                    covered_spans.append((idx, end))
                    results.append(SceneElement(
                        category=category,
                        element_name=term.title(),
                        ai_suggested=1,
                        ai_confidence=0.65,
                        detection_method="cold_start_rules",
                    ))

        return results[:max_results]