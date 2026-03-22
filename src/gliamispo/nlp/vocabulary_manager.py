import re
from gliamispo.models.scene_element import SceneElement


def _make_pattern(term):
    return re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)


# FIX 6: categorie che richiedono una soglia di confidenza base più alta.
# Livestock in particolare soffre di falsi positivi quando i termini appaiono
# in contesti non-animale (es. "uccello" usato in senso volgare nel dialogo).
# Richiedere confidenza 0.90 invece di 0.85 riduce i falsi positivi borderline.
_HIGH_CONFIDENCE_CATEGORIES = {
    "Livestock": 0.90,
    "Intimacy":  0.90,
}

# FIX 6: pattern per rilevare se un termine è contenuto in una riga di dialogo.
# Nel testo di azione Fountain il dialogo appare tra virgolette, oppure la riga
# di synopsis (dopo il fix al FountainParser) non contiene più le battute,
# ma il VocabularyManager può ricevere anche testo grezzo ancora con dialogo.
# Questi pattern riconoscono il contesto "tra virgolette" o dopo esclamativo/
# punto interrogativo (caratteristico del dialogo scritto in action text).
_DIALOGUE_CONTEXT_RE = re.compile(
    r'["""«»]([^"""«»]{0,200})\b{term}\b([^"""«»]{0,200})["""«»]',
    re.IGNORECASE
)

# Parole immediatamente precedenti al termine che indicano uso metaforico/volgare
# e non l'animale reale.
_LIVESTOCK_FALSE_POSITIVE_CONTEXTS: dict[str, tuple[str, ...]] = {
    "uccello": ("succhiare", "tua", "mio", "suo", "cazzo", "pene",),
    "gallo":   ("cazzo", "pene",),
    "coniglio": ("fifone", "codardo",),
    "capra":   ("stupida", "idiota",),
}


def _is_livestock_false_positive(term, text):
    """
    FIX 6: controlla se il termine animale appare in un contesto volgare
    o metaforico che esclude la sua interpretazione come animale reale.
    """
    term_lower = term.lower()
    if term_lower not in _LIVESTOCK_FALSE_POSITIVE_CONTEXTS:
        return False

    bad_contexts = _LIVESTOCK_FALSE_POSITIVE_CONTEXTS[term_lower]
    # Cerca il termine nel testo e guarda le 40 parole circostanti
    pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
    for m in pattern.finditer(text):
        start = max(0, m.start() - 80)
        end   = min(len(text), m.end() + 80)
        window = text[start:end].lower()
        if any(ctx in window for ctx in bad_contexts):
            return True
    return False


class VocabularyManager:
    def __init__(self, terms=None):
        self._terms = []
        self.load_terms(terms or [])

    def load_terms(self, terms):
        self._terms = [
            (_make_pattern(term), term, category)
            for term, category in terms
        ]

    async def match(self, text):
        results = []
        seen = set()
        for pattern, original_term, category in self._terms:
            if pattern.search(text):
                key = (category, original_term.lower())
                if key not in seen:

                    # FIX 6: per Livestock verifica che non sia un falso positivo
                    # contestuale (termine animale usato in senso figurato/volgare)
                    if category == "Livestock" and _is_livestock_false_positive(
                        original_term, text
                    ):
                        continue

                    seen.add(key)
                    e = SceneElement()
                    e.element_name = original_term
                    e.category = category
                    e.ai_suggested = 1
                    # FIX 6: usa confidenza specifica per categoria se definita
                    e.ai_confidence = _HIGH_CONFIDENCE_CATEGORIES.get(
                        category, 0.85
                    )
                    e.detection_method = "vocabulary"
                    results.append(e)
        return results