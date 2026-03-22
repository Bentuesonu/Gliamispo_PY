import re
from gliamispo.models.scene_element import SceneElement
from gliamispo.nlp.spacy_loader import get_nlp_it, get_nlp_en

_CHAR_INTRO_RE = re.compile(
    r'(?:^|(?<=\s)|(?<=[.!?]))'
    r'(?:[A-Z]{1,3}\s+)?'
    r'([A-Z\u00C0-\u00DC][A-Z\u00C0-\u00DC.\'\"\-\s]{0,30}?)'
    r'\s*\(\s*(\d{1,3})\s*\)',
    re.MULTILINE
)

_CHARACTER_RE = re.compile(
    r"\b([A-Z\u00C0-\u00DC][A-Z\u00C0-\u00DC.'\"-]{0,19}"
    r"(?:\s+[A-Z\u00C0-\u00DC.'\"-]{1,19}){0,2})\b"
)

_NER_STOPWORDS = frozenset({
    "INT", "EXT", "INT/EXT", "INTERNO", "ESTERNO",
    "GIORNO", "NOTTE", "MATTINA", "MATTINO", "SERA", "POMERIGGIO",
    "TRAMONTO", "ALBA", "DAY", "NIGHT", "MORNING", "EVENING", "DUSK", "DAWN",
    "AFTERNOON",
    "CONTINUA", "CONTINUO", "CONTINUOUS", "LATER",
    "VOC", "V.O", "V.O.", "O.S", "O.S.", "O.C", "O.C.", "VOCE",
    "VOCE FUORI CAMPO",
    "CUT", "TO", "FADE", "IN", "OUT", "SMASH", "DISSOLVENZA",
    "TAGLIO", "NERO", "BUIO", "BIANCO", "TENDINA",
    "FLASHBACK", "FLASH", "FLASHFORWARD", "POV", "SOGGETTIVA",
    "INIZIO", "FINE",
    "PRIMO", "PIANO", "CAMPO", "TOTALE", "MEDIO",
    "CARRELLATA", "PANORAMICA", "ZOOM", "PUSH", "PULL",
    "INSERTO", "DETTAGLIO", "AMERICANO", "PIANO SEQUENZA",
    "TESTO", "TITOLO", "SOTTOTITOLO", "CARTELLO", "DIDASCALIA",
    "SUPER", "THE", "END", "THE END",
    "PIU TARDI", "PIÙ TARDI", "DOPO", "UN MOMENTO DOPO",
    "BOOM", "BANG", "CRASH", "CRACK", "SPLASH",
    "SILENZIO", "PAUSA", "STOP", "VIA", "BASTA",
    "AIUTO", "FUOCO", "ATTENZIONE", "PERICOLO",
    "APPLAUSI", "RISATE", "URLA", "SPARI",
    "OK", "SÌ", "SI", "NO", "EH", "AH", "OH", "UH",
    "BENE", "BRAVO", "BRAVA", "GRAZIE", "PREGO",
    "CIAO", "ADDIO", "ARRIVEDERCI", "SALVE",
    "RIPRESA", "SUCCESSIVO", "PRECEDENTE", "PROSEGUE", "SEGUE",
    "SOGNO", "VISIONE",
    "UN", "UNA", "IL", "LA", "I", "LE", "LO", "GL",
    "DEL", "DELLA", "DELLO", "DELL",
    "È", "HA", "VA",
    "SLOW", "MOTION", "RALENTI", "TIME", "LAPSE", "MATCH",
    # Insulti e parolacce (dialogo urlato / testo di azione)
    "CAZZO", "MERDA", "STRONZO", "STRONZA", "BASTARDO", "BASTARDA",
    "PUTTANA", "FIGLIO", "FIGLIA", "VAFFANCULO", "PORCO", "PORKA",
    "COGLIONE", "COGLIONA", "IDIOTA", "IMBECILLE", "DEFICIENTE",
    "MINCHIA", "CRETINO", "CRETINA", "SCEMO", "SCEMA", "PIRLA",
    "TESTA", "PEZZO", "MERDOSO", "CORNUTO", "CORNUTA",
    "MOSTRO", "ANIMALE", "BESTIA",
    # Esclamazioni e comandi comuni in maiuscolo
    "ASPETTA", "FERMATI", "SCAPPA", "CORRI", "VIENI", "VIENI QUI",
    "FORZA", "AVANTI", "DAI", "SMETTILA", "MUOVITI", "TACI",
    "GUARDA", "SENTI", "ASCOLTA", "PRONTO", "SUBITO", "ADESSO",
    "BASTA COSÌ", "FUORI", "DENTRO", "SU", "GIÙ", "GIU",
    "ATTENTO", "ATTENTA", "ATTENZIONE", "PIANO", "LENTO",
    "FERMO", "FERMA", "FATTI", "DEVI", "PUOI", "VIENI",
    # Onomatopee e suoni
    "CLICK", "TICK", "TACK", "DING", "DONG", "RING", "PING",
    "WHOOSH", "THUD", "SLAM", "POW", "ZAP", "WHAM",
    "CLANG", "CLANK", "RATTLE", "BUZZ", "HUM", "ROAR",
    # Oggetti/concetti comuni in cartelli e testi di azione
    "SCONTRINO", "GRAPPINO", "CASSA", "BAR", "MENU", "LISTA",
    "PRIMA", "SECONDA", "TERZA", "QUARTA", "QUINTA",
    "PARTE", "CAPITOLO", "ATTO", "SCENA",
    "STUDIO", "CASA", "UFFICIO", "STRADA", "PIAZZA",
    "MONDO", "VITA", "MORTE", "AMORE", "ODIO",
    "TEMPO", "MODO", "COSA", "FATTO", "CASO",
    "TUTTO", "NIENTE", "NULLA", "ALTRO", "ALTRI",
    "STESSO", "STESSA", "NUOVO", "NUOVA",
    "GRANDE", "PICCOLO", "PICCOLA", "GRANDE",
    "SOLO", "SOLA", "INSIEME", "SEMPRE", "MAI",
    "ORA", "ALLORA", "QUINDI", "PERÒ", "PERÒ",
    "ANCORA", "TROPPO", "MOLTO", "POCO",
    "QUI", "LÀ", "LA", "QUA", "DOVE", "COME", "PERCHÉ",
    "CHE", "CHI", "CON", "PER", "SU", "DA", "DI",
})

_STAGE_PREFIXES = (
    "INIZIO POV ",
    "FINE POV ",
    "INIZIO SOGGETTIVA ",
    "FINE SOGGETTIVA ",
    "INIZIO FLASHBACK",
    "FINE FLASHBACK",
    "INIZIO SOGNO",
    "FINE SOGNO",
)

_ARTICLE_PREFIXES = frozenset({
    "UN ", "UNA ", "IL ", "LA ", "I ", "LE ", "LO ",
    "DEL ", "DELLA ", "DELLO ", "DELL'", "È ",
})


def _strip_article(name: str) -> str:
    upper = name.upper()
    for art in _ARTICLE_PREFIXES:
        if upper.startswith(art):
            return name[len(art):].strip()
    return name.strip()


def _make_cast_element(name: str, confidence: float,
                       method: str) -> SceneElement:
    e = SceneElement()
    e.element_name = name
    e.category = "Cast"
    e.ai_suggested = 1
    e.ai_confidence = confidence
    e.detection_method = method
    return e


_IT_MARKERS = frozenset({
    "il", "la", "lo", "le", "gli", "una", "delle", "degli",
    "che", "con", "per", "non", "del", "della", "dalla", "nella",
    "verso", "dopo", "prima", "mentre", "anche", "come", "quando",
})
_EN_MARKERS = frozenset({
    "the", "and", "with", "for", "from", "into", "onto",
    "while", "after", "before", "then", "also", "when",
    "his", "her", "their", "they", "she",
})


def _detect_language(text: str) -> str:
    words = set(re.findall(r'\b[a-z]{2,}\b', text.lower()))
    it_score = len(words & _IT_MARKERS)
    en_score = len(words & _EN_MARKERS)
    if it_score == 0 and en_score == 0:
        return 'it'
    if en_score > it_score * 1.5:
        return 'en'
    if it_score > en_score * 1.5:
        return 'it'
    return 'mixed'


_TITLE_CASE_CHAR_RE = re.compile(
    r'(?<![A-Za-zÀ-ÿ])'          # non preceduto da lettera
    r'([A-Z\u00C0-\u00DC]'        # inizia con maiuscola
    r'[a-z\u00E0-\u00FC]{1,19}'   # seguito da minuscole (non è tutto-maiuscolo)
    r'(?:\s+[A-Z\u00C0-\u00DC][a-z\u00E0-\u00FC]{1,19}){0,2})'  # max 2 token extra
    r'(?![A-Za-zÀ-ÿ])'           # non seguito da lettera
)

_TITLE_CASE_STOPWORDS = frozenset({
    "Int", "Ext", "Interno", "Esterno", "Giorno", "Notte", "Sera",
    "Mattina", "Mattino", "Continua", "Continuo", "Dopo", "Prima",
    "Poi", "Mentre", "Quando", "Come", "Dove", "Perché", "Cosa",
    "Solo", "Anche", "Ancora", "Subito", "Sempre", "Mai", "Poi",
    "Adesso", "Ora", "Qui", "Là", "Qua",
    "Un", "Una", "Il", "La", "Lo", "Le", "I", "Gli",
    "Del", "Della", "Dello", "Dell",
    "The", "And", "With", "For", "From", "Into", "While",
})


class NERExtractor:
    SPACY_PERSON_CONFIDENCE = 0.82
    INTRO_CONFIDENCE = 0.88
    REGEX_CONFIDENCE = 0.65
    TITLE_CASE_CONFIDENCE = 0.70

    async def extract(self, text: str, known_chars: set = None) -> list:
        if not text or not text.strip():
            return []

        seen: set = set()
        results: list = []

        self._extract_intros(text, seen, results)
        if known_chars:
            self._extract_known_titles(text, seen, results, known_chars)
        self._extract_spacy(text, seen, results)
        if not results:
            self._extract_regex(text, seen, results)

        return results

    def _extract_intros(self, text: str, seen: set, results: list) -> None:
        for m in _CHAR_INTRO_RE.finditer(text):
            raw_name = m.group(1).strip()
            name = _strip_article(raw_name)
            if not name:
                continue
            if name.upper() in _NER_STOPWORDS:
                continue
            first_word = name.split()[0].rstrip(".")
            if first_word.upper() in _NER_STOPWORDS:
                continue
            if name.isupper() and len(name) > 4:
                name = name.title()
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(_make_cast_element(
                name, self.INTRO_CONFIDENCE, "ner_intro"
            ))

    def _extract_known_titles(self, text: str, seen: set, results: list,
                              known_chars: set) -> None:
        """Trova nomi noti (Title Case) nel testo di azione.

        Usato per scene senza dialogo dove i personaggi compaiono nel testo
        d'azione con iniziale maiuscola (es. "Beppe guida in silenzio.").
        Richiede che il nome appaia con iniziale maiuscola per escludere
        usi come sostantivo comune.
        """
        for name_lower in known_chars:
            if name_lower in seen:
                continue
            title_form = name_lower.title()
            # Cerca la forma Title Case esplicitamente (case-sensitive)
            m = re.search(r'(?<![A-Za-zÀ-ÿ])' + re.escape(title_form)
                          + r'(?![A-Za-zÀ-ÿ])', text)
            if not m:
                # Cerca anche ALL CAPS (es. "BEPPE" nel testo di azione)
                m = re.search(r'(?<![A-Za-zÀ-ÿ])' + re.escape(name_lower.upper())
                              + r'(?![A-Za-zÀ-ÿ])', text)
            if not m:
                continue
            canonical = title_form
            if canonical in _TITLE_CASE_STOPWORDS:
                continue
            seen.add(name_lower)
            results.append(_make_cast_element(
                canonical, self.TITLE_CASE_CONFIDENCE, "ner_known_title"
            ))

    def _extract_spacy(self, text: str, seen: set, results: list) -> bool:
        lang = _detect_language(text)
        found_any = False

        models_to_try = []
        if lang in ('it', 'mixed'):
            nlp_it = get_nlp_it()
            if nlp_it:
                models_to_try.append(('it', nlp_it))
        if lang in ('en', 'mixed'):
            nlp_en = get_nlp_en()
            if nlp_en:
                models_to_try.append(('en', nlp_en))
        if not models_to_try:
            nlp_en = get_nlp_en()
            if nlp_en:
                models_to_try.append(('en', nlp_en))
            nlp_it = get_nlp_it()
            if nlp_it:
                models_to_try.append(('it', nlp_it))

        for lang_tag, nlp in models_to_try:
            try:
                doc = nlp(text[:5000])
            except Exception:
                continue

            for ent in doc.ents:
                if ent.label_ not in ("PERSON", "PER"):
                    continue
                name = ent.text.strip()
                if not name or len(name) < 2:
                    continue
                if name.upper() in _NER_STOPWORDS:
                    continue
                if name.isupper() and len(name) > 4:
                    name = name.title()
                key = name.lower()
                if key in seen:
                    continue
                if re.fullmatch(r'[A-Z]|[\d]+', name.upper()):
                    continue
                seen.add(key)
                results.append(_make_cast_element(
                    name,
                    self.SPACY_PERSON_CONFIDENCE,
                    f"spacy_{lang_tag}"
                ))
                found_any = True

        return found_any

    def _extract_regex(self, text: str, seen: set, results: list) -> None:
        for m in _CHARACTER_RE.finditer(text):
            name = m.group(1).strip()
            if not name or name.lower() in seen:
                continue
            if re.fullmatch(r'[A-Z]|[\d]+', name.upper()):
                continue
            if name.upper() in _NER_STOPWORDS:
                continue
            first_word = name.split()[0].rstrip(".")
            if first_word.upper() in _NER_STOPWORDS:
                continue
            start = m.start()
            # Skip matches embedded mid-sentence: a real Fountain character
            # header is always the only content on its line.
            line_start = text.rfind('\n', 0, start) + 1
            before_on_line = text[line_start:start].strip()
            if before_on_line:
                continue
            line_end = text.find('\n', m.end())
            if line_end == -1:
                line_end = len(text)
            after_on_line = text[m.end():line_end].strip()
            # Allow trailing stage directions like "(V.O.)" but reject plain text
            if after_on_line and not re.fullmatch(r'\([\w\s./]+\)', after_on_line):
                continue
            preceding = text[max(0, start - 30):start].upper()
            if any(preceding.endswith(p) for p in _STAGE_PREFIXES):
                continue
            if len(name.split()) > 3:
                continue
            if name.replace(".", "").isdigit():
                continue
            seen.add(name.lower())
            results.append(_make_cast_element(
                name, self.REGEX_CONFIDENCE, "ner_regex"
            ))
