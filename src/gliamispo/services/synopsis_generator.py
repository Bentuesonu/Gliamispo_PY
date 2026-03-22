"""
synopsis_generator.py — Summarization estrattiva per sceneggiature italiane
100% offline · zero dipendenze nuove

PERCHÉ TEXTRANK NON FUNZIONA QUI
─────────────────────────────────
TextRank trova la frase "più centrale nel grafo di similarità" — cioè quella
che condivide più vocabolario con le altre. Funziona sui giornali perché i
paragrafi di un articolo parlano tutti dello stesso argomento e si ripetono.

Le action line di una sceneggiatura sono scritte al contrario: ogni riga
descrive un momento DIVERSO con parole DIVERSE (buona scrittura = zero
ridondanza). La matrice di similarità risulta quasi completamente zero, e
PageRank su una matrice zero converge a punteggi uniformi → selezione casuale.

L'ALGORITMO CORRETTO PER IL DOMINIO
──────────────────────────────────────
Per le sceneggiature, l'importanza di una frase dipende da COSA dice,
non da quanto si ripete. L'algoritmo usa tre componenti:

1. CONTENT SCORE (quando spaCy è disponibile)
   Conta entità nominate (personaggi, luoghi) e verbi lessicali.
   Frasi con più personaggi che fanno cose = più contenuto narrativo.

2. POSITION SCORE
   Peso esponenziale decrescente dalla prima frase.
   Le prime righe di action stabiliscono sempre chi/dove/cosa:
   principio "lead" consolidato nella letteratura di summarization.
   La ULTIMA frase di action riceve un bonus extra (risoluzione della scena).

3. LUHN SCORE (fallback senza spaCy)
   Algoritmo Luhn (1958): trova parole "significative" (frequenza media,
   non stopword), poi punteggia le frasi per densità di cluster di
   parole significative. Robusto su testi brevi e frammentati.

SELEZIONE MMR (Maximal Marginal Relevance)
   Kulesza & Taskar (2011): seleziona la frase successiva che massimizza
   rilevanza - λ * similarità_con_già_selezionate.
   Garantisce diversità: non seleziona due frasi che dicono la stessa cosa.
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# 1. ESTRAZIONE DA RAW_BLOCKS
# ---------------------------------------------------------------------------

def extract_scene_text(raw_blocks: list[dict]) -> str:
    """Estrae testo completo per visualizzazione (non per summarization)."""
    parts = []
    current_char: Optional[str] = None
    for block in raw_blocks:
        btype = block.get("type", "")
        btext = (block.get("text") or "").strip()
        if not btext:
            continue
        if btype == "character":
            current_char = btext
        elif btype == "dialogue":
            parts.append(f"{current_char}: {btext}" if current_char else btext)
        elif btype == "parenthetical":
            parts.append(f"({btext})")
        elif btype == "action":
            current_char = None
            parts.append(btext)
    return "\n".join(parts)


def _get_action_blocks(raw_blocks: list[dict]) -> list[str]:
    """
    Estrae solo i blocchi di azione con contenuto sufficiente.
    I blocchi dopo _merge_consecutive_blocks sono già multi-frase.
    """
    return [
        (b.get("text") or "").strip()
        for b in raw_blocks
        if b.get("type") == "action"
        and len((b.get("text") or "").split()) >= 3
    ]


def _get_key_dialogue(raw_blocks: list[dict], max_exchanges: int = 2) -> list[str]:
    """
    Estrae le prime battute di dialogo significative.
    Usate come integrazione quando l'action è scarsa.
    Formato: "PERSONAGGIO: battuta"
    """
    result = []
    current_char: Optional[str] = None
    for block in raw_blocks:
        if len(result) >= max_exchanges:
            break
        btype = block.get("type", "")
        btext = (block.get("text") or "").strip()
        if btype == "character":
            current_char = btext
        elif btype == "dialogue" and current_char and len(btext.split()) >= 3:
            result.append(f"{current_char}: {btext}")
            current_char = None
    return result


# Stopwords italiane per filtri e scoring
_STOPWORDS_IT = frozenset({
    "il","lo","la","i","gli","le","un","una","uno","di","a","da","in",
    "con","su","per","tra","fra","e","o","ma","se","che","non","è","si",
    "mi","ti","ci","vi","ne","ha","ho","ai","del","della","dei","delle",
    "degli","dal","dalla","dai","nel","nella","nei","nelle","col","allo",
    "alla","alle","agli","poi","già","anche","ancora","sempre","mai","ora",
    "qui","lì","là","più","meno","molto","poco","tutto","questo","questa",
    "questi","queste","quello","quella","lui","lei","loro","noi","voi",
    "suo","sua","suoi","sue","mio","tuo","come","quando","dove","mentre",
    "però","quindi","allora","essere","avere","fare","dire","andare",
    "stare","sapere","volere","potere","dovere","ad","ed","od","li","lo",
})

# Patterns di micro-azioni irrilevanti per la sinossi
_IRRELEVANT_ACTION_PATTERNS = (
    r"^si avvicina",
    r"^si volta",
    r"^si alza",
    r"^si siede",
    r"^si ferma",
    r"^si gira",
    r"^si guarda",
    r"^lo guarda",
    r"^la guarda",
    r"^lo fissa",
    r"^ci pensa",
    r"^annuisce",
    r"^scuote la testa",
    r"^alza gli occhi",
    r"^abbassa gli occhi",
    r"^sorride",
    r"^ride",
    r"^piange",
    r"^sospira",
    r"^sbuffa",
    r"^fa per",
    r"^resta in silenzio",
    r"^rimane in silenzio",
    r"^tace",
    r"^pausa",
    r"^silenzio",
)
_IRRELEVANT_PATTERN_RE = re.compile(
    "|".join(_IRRELEVANT_ACTION_PATTERNS),
    re.IGNORECASE
)


def _is_relevant_action(text: str) -> bool:
    """
    Determina se un blocco di action è narrativamente rilevante.

    Restituisce False (stage direction irrilevante) se il blocco:
    - Ha meno di 5 parole, OPPURE
    - Inizia con pattern di micro-azione (gesti, sguardi, pause), OPPURE
    - Contiene solo verbi di movimento/reazione senza oggetto narrativo

    Restituisce True altrimenti.
    """
    text = text.strip()
    if not text:
        return False

    words = text.split()

    # Meno di 5 parole: troppo breve per contenuto narrativo
    if len(words) < 5:
        return False

    # Inizia con pattern irrilevante
    if _IRRELEVANT_PATTERN_RE.match(text):
        return False

    # Verifica presenza di sostantivi significativi (> 4 caratteri, non nomi propri)
    # Se la frase ha solo verbi di movimento senza oggetti, è irrilevante
    # Cerchiamo parole lunghe che non siano all'inizio (nomi propri iniziano con maiuscola)
    substantive_words = [
        w for i, w in enumerate(words)
        if len(w) > 4
        and w[0].islower()  # Esclude nomi propri
        and w.lower() not in _STOPWORDS_IT
        and not w.endswith(("ando", "endo", "ato", "uto", "ito"))  # Gerundi e participi
    ]

    # Se non ci sono sostantivi significativi, la frase descrive solo movimento
    if not substantive_words:
        return False

    return True


def _get_narrative_dialogue(
    raw_blocks: list[dict],
    max_exchanges: int = 4
) -> list[str]:
    """
    Estrae battute di dialogo narrativamente dense.

    Diversa da _get_key_dialogue() che prende le PRIME battute.
    Questa seleziona le battute più significative:

    - Ignora battute < 5 parole
    - Ignora battute che sono solo domande brevi
    - Preferisce battute con sostantivi concreti, nomi, numeri, luoghi
    - Prende: prima significativa, ultima significativa, e le migliori intermedie

    Formato output: "PERSONAGGIO: testo battuta"
    """
    # Estrai tutte le battute con punteggio
    dialogues: list[tuple[str, str, float, int]] = []  # (character, text, score, original_idx)
    current_char: Optional[str] = None
    idx = 0

    for block in raw_blocks:
        btype = block.get("type", "")
        btext = (block.get("text") or "").strip()

        if btype == "character":
            current_char = btext
        elif btype == "dialogue" and current_char:
            words = btext.split()

            # Ignora battute troppo brevi
            if len(words) < 5:
                current_char = None
                continue

            # Ignora domande brevi (solo "?" e poche parole)
            if btext.endswith("?") and len(words) <= 6:
                # Verifica se è una domanda generica
                generic_questions = ("che", "cosa", "chi", "come", "dove",
                                     "quando", "perché", "e allora", "davvero",
                                     "sicuro", "sì", "no")
                first_word = words[0].lower().rstrip("?")
                if first_word in generic_questions or len(words) <= 3:
                    current_char = None
                    continue

            # Calcola score di densità narrativa
            score = 0.0

            # Sostantivi concreti (parole lunghe non stopword)
            for w in words:
                if len(w) > 4 and w.lower() not in _STOPWORDS_IT:
                    score += 0.5

            # Numeri (date, quantità, indirizzi)
            if re.search(r'\d+', btext):
                score += 2.0

            # Nomi propri (parole capitalizzate non a inizio frase)
            for w in words[1:]:
                if w[0].isupper() and len(w) > 2:
                    score += 1.5

            # Virgolette (citazioni, enfasi)
            if '"' in btext or "«" in btext:
                score += 1.0

            # Penalizza battute troppo lunghe (monologhi dispersivi)
            if len(words) > 30:
                score *= 0.8

            dialogues.append((current_char, btext, score, idx))
            idx += 1
            current_char = None

    if not dialogues:
        return []

    # Seleziona: prima significativa, ultima significativa, migliori intermedie
    result: list[str] = []

    # Prima battuta significativa
    if dialogues:
        first = dialogues[0]
        result.append(f"{first[0]}: {first[1]}")

    # Ultima battuta significativa (se diversa dalla prima)
    if len(dialogues) > 1:
        last = dialogues[-1]
        result.append(f"{last[0]}: {last[1]}")

    # Battute intermedie per score (se servono più scambi)
    if max_exchanges > 2 and len(dialogues) > 2:
        intermediate = dialogues[1:-1]
        intermediate.sort(key=lambda x: x[2], reverse=True)
        for char, text, _, _ in intermediate[:max_exchanges - 2]:
            result.append(f"{char}: {text}")

    return result[:max_exchanges]


# ---------------------------------------------------------------------------
# 2. SEGMENTAZIONE IN FRASI
# ---------------------------------------------------------------------------

def _split_spacy(text: str, nlp) -> list[str]:
    doc = nlp(text[:6000])
    return [s.text.strip() for s in doc.sents if len(s.text.strip().split()) >= 3]


def _split_regex(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?…])\s+(?=[A-ZÀÈÉÌÎÒÓÙÚ"\'])', text)
    return [s.strip() for s in parts if len(s.strip().split()) >= 3]


def _split(text: str, nlp=None) -> list[str]:
    if nlp:
        sents = _split_spacy(text, nlp)
        if sents:
            return sents
    sents = _split_regex(text)
    return sents if sents else ([text.strip()] if text.strip() else [])


# ---------------------------------------------------------------------------
# 3A. CONTENT SCORE — con spaCy (NER + POS)
# ---------------------------------------------------------------------------

def _content_score_spacy(sent: str, nlp) -> float:
    """
    Punteggio basato su densità informativa NLP:
    - Entità nominate (PERSON, LOC, ORG, GPE) → chi e dove
    - Verbi lessicali (non ausiliari, non modali) → cosa succede
    - Normalizzato per lunghezza (evita bias su frasi lunghe)
    """
    doc = nlp(sent)
    tokens = [t for t in doc if not t.is_space]
    if not tokens:
        return 0.0

    # Entità nominate rilevanti
    ne_score = sum(
        1.0 for ent in doc.ents
        if ent.label_ in ("PER", "PERSON", "LOC", "GPE", "ORG", "FAC")
    )

    # Verbi lessicali (non AUX, non modale)
    verb_score = sum(
        1.0 for t in doc
        if t.pos_ == "VERB"
        and t.dep_ not in ("aux", "auxpass")
        and t.lemma_.lower() not in {
            "essere", "avere", "stare", "venire", "andare",
            "fare", "dire", "vedere", "potere", "dovere", "volere"
        }
    )

    # Sostantivi concreti (oggetti, persone non riconosciute come NE)
    noun_score = sum(
        0.5 for t in doc
        if t.pos_ in ("NOUN", "PROPN")
        and len(t.text) > 3
    )

    total = ne_score * 2.0 + verb_score * 1.5 + noun_score * 0.5
    return total / max(len(tokens), 1)


# ---------------------------------------------------------------------------
# 3B. LUHN SCORE — fallback senza spaCy
# ---------------------------------------------------------------------------

def _luhn_score(sentence: str, significant: set[str], window: int = 4) -> float:
    """
    Algoritmo Luhn (1958) adattato.
    Trova il cluster più denso di parole significative nella frase.
    Score = (parole_significative_nel_cluster)² / lunghezza_cluster
    
    Il quadrato al numeratore premia cluster densi vs cluster sparsi.
    """
    words = re.findall(r'\b[a-zA-ZàèéìîòóùúÀÈÉÌÎÒÓÙÚ]{3,}\b', sentence.lower())
    if not words:
        return 0.0

    # Marca ogni parola come significativa o meno
    is_sig = [w in significant for w in words]

    best = 0.0
    n = len(words)

    # Scorri tutti i possibili cluster (finestra scorrevole)
    for start in range(n):
        if not is_sig[start]:
            continue
        end = start
        sig_count = 0
        # Estendi il cluster finché c'è almeno una parola significativa
        # entro `window` posizioni dall'ultima significativa trovata
        last_sig = start
        for i in range(start, n):
            if is_sig[i]:
                sig_count += 1
                last_sig = i
                end = i
            elif i - last_sig > window:
                break

        cluster_len = end - start + 1
        if cluster_len > 0 and sig_count >= 2:
            score = (sig_count ** 2) / cluster_len
            best = max(best, score)

    # Normalizza per lunghezza frase (penalizza frasi lunghissime)
    return best / max(len(words), 1)


def _find_significant_words(sentences: list[str]) -> set[str]:
    """
    Parole significative = appaiono ≥ 2 volte nel corpus della scena,
    non sono stopwords, lunghezza > 3 caratteri.
    
    Non usiamo IDF globale perché il corpus è solo la scena corrente.
    La soglia minima di 2 occorrenze separa termini specifici della scena
    da parole casuali.
    """
    freq: dict[str, int] = {}
    for sent in sentences:
        words = re.findall(r'\b[a-zA-ZàèéìîòóùúÀÈÉÌÎÒÓÙÚ]{4,}\b', sent.lower())
        for w in set(words):   # set: conta ogni parola una volta per frase
            if w not in _STOPWORDS_IT:
                freq[w] = freq.get(w, 0) + 1

    # Significative: appaiono in 2+ frasi (non troppo rare)
    # ma non in TUTTE le frasi (non troppo generiche)
    n = len(sentences)
    return {
        w for w, f in freq.items()
        if f >= 2 and f < max(n, 2)
    }


# ---------------------------------------------------------------------------
# 3C. LEXRANK SCORE — con sumy (opzionale)
# ---------------------------------------------------------------------------

def _lexrank_score(sentences: list[str]) -> dict[str, float]:
    """
    Calcola score LexRank per ogni frase usando la libreria sumy.

    LexRank (Erkan & Radev, 2004) usa una matrice di similarità coseno
    tra frasi basata su TF-IDF. A differenza di TextRank base, funziona
    meglio su testi brevi perché usa IDF per pesare i termini.

    Input: lista di frasi già estratte e pulite.
    Output: dict {frase: score_normalizzato_0_1}

    Se sumy non è installato: return {} silenziosamente.
    """
    if not sentences:
        return {}

    try:
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.summarizers.lex_rank import LexRankSummarizer
    except ImportError:
        return {}

    try:
        # Unisci le frasi in un testo per il parser
        full_text = " ".join(sentences)

        parser = PlaintextParser.from_string(full_text, Tokenizer("italian"))
        summarizer = LexRankSummarizer()

        # Chiedi un riassunto lungo quanto il testo (per ottenere tutti gli score)
        # LexRank restituisce le frasi ordinate per score
        summary = summarizer(parser.document, len(sentences))

        # Mappa ogni frase al suo indice nella lista di output (posizione = rank)
        # La prima frase restituita ha rank più alto
        scores: dict[str, float] = {}
        n = len(summary)

        for rank, sumy_sent in enumerate(summary):
            sent_text = str(sumy_sent).strip()
            # Score normalizzato: primo = 1.0, ultimo = 0.0
            score = 1.0 - (rank / max(n - 1, 1)) if n > 1 else 1.0

            # Trova la frase originale più simile (sumy può modificare il testo)
            best_match = None
            best_overlap = 0.0
            for orig_sent in sentences:
                if orig_sent in scores:
                    continue
                # Overlap Jaccard semplice
                orig_words = set(orig_sent.lower().split())
                sent_words = set(sent_text.lower().split())
                if not orig_words or not sent_words:
                    continue
                overlap = len(orig_words & sent_words) / len(orig_words | sent_words)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match = orig_sent

            if best_match and best_match not in scores:
                scores[best_match] = score

        # Assegna score 0.0 a frasi non matchate
        for sent in sentences:
            if sent not in scores:
                scores[sent] = 0.0

        return scores

    except Exception:
        # Qualsiasi errore: fallback silenzioso
        return {}


# ---------------------------------------------------------------------------
# 3D. SEMANTIC SCORE — con sentence-transformers (opzionale)
# ---------------------------------------------------------------------------

# Cache globale per il modello sentence-transformers
_ST_MODEL = None
_ST_MODEL_CHECKED = False


def _get_st_model():
    """
    Carica il modello sentence-transformers con lazy loading.

    Usa "paraphrase-multilingual-MiniLM-L12-v2" — un modello multilingue
    leggero (~420MB) ottimizzato per similarità semantica.

    Return:
        Il modello caricato, oppure None se:
        - sentence_transformers non è installato
        - Il modello non è scaricato localmente
        - Si verifica un errore durante il caricamento

    NON scarica automaticamente — richiede setup manuale.
    """
    global _ST_MODEL, _ST_MODEL_CHECKED

    # Se abbiamo già verificato e fallito, non riprovare
    if _ST_MODEL_CHECKED:
        return _ST_MODEL

    _ST_MODEL_CHECKED = True

    try:
        from sentence_transformers import SentenceTransformer
        import os

        # Controlla se il modello è già in cache locale
        # sentence-transformers usa ~/.cache/torch/sentence_transformers/
        # o la variabile d'ambiente SENTENCE_TRANSFORMERS_HOME
        cache_folder = os.environ.get(
            'SENTENCE_TRANSFORMERS_HOME',
            os.path.join(os.path.expanduser('~'), '.cache', 'torch', 'sentence_transformers')
        )

        model_name = "paraphrase-multilingual-MiniLM-L12-v2"
        model_folder = os.path.join(cache_folder, f"sentence-transformers_{model_name}")

        # Se la cartella non esiste, il modello non è scaricato
        if not os.path.isdir(model_folder):
            return None

        # Carica il modello (local_files_only per evitare download)
        _ST_MODEL = SentenceTransformer(
            model_name,
            device='cpu'  # Forza CPU per compatibilità
        )
        return _ST_MODEL

    except ImportError:
        return None
    except Exception:
        return None


def _semantic_score(sentences: list[str], model) -> dict[str, float]:
    """
    Calcola score semantico per ogni frase usando sentence embeddings.

    Il punteggio di ogni frase è la similarità coseno tra il suo embedding
    e l'embedding del documento completo (tutte le frasi concatenate).
    Frasi più "centrali" semanticamente al contenuto complessivo = score più alto.

    Args:
        sentences: Lista di frasi da valutare
        model: Modello sentence-transformers già caricato (o None)

    Returns:
        Dict {frase: score_normalizzato_0_1}
        Dict vuoto se model è None o si verifica un errore
    """
    if model is None or not sentences:
        return {}

    try:
        import numpy as np

        # Embedding di ogni frase
        sentence_embeddings = model.encode(sentences, convert_to_numpy=True)

        # Embedding del documento completo (media degli embedding delle frasi)
        doc_embedding = np.mean(sentence_embeddings, axis=0)

        # Calcola similarità coseno tra ogni frase e il documento
        def cosine_similarity(a, b):
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(np.dot(a, b) / (norm_a * norm_b))

        scores_raw = [
            cosine_similarity(sent_emb, doc_embedding)
            for sent_emb in sentence_embeddings
        ]

        # Normalizza in [0, 1]
        min_score = min(scores_raw) if scores_raw else 0.0
        max_score = max(scores_raw) if scores_raw else 1.0
        score_range = max_score - min_score

        if score_range > 0:
            scores_norm = [(s - min_score) / score_range for s in scores_raw]
        else:
            scores_norm = [1.0] * len(scores_raw)

        return {sent: score for sent, score in zip(sentences, scores_norm)}

    except Exception:
        return {}


# ---------------------------------------------------------------------------
# 4. POSITION SCORE
# ---------------------------------------------------------------------------

def _position_score(idx: int, total: int, is_last_block: bool = False) -> float:
    """
    Decadimento esponenziale dalla prima frase.
    La prima frase (idx=0) vale 1.0.
    L'ultima frase del blocco finale riceve bonus 0.3 (risoluzione scena).

    Base: lead-based summarization (Brandow et al. 1995 su news, 
    Lin & Hovy 1997 su discourse structure).
    Adattamento per sceneggiature: anche la CONCLUSIONE è importante.
    """
    if total <= 1:
        return 1.0

    # Decadimento esponenziale: peso = e^(-k * posizione_relativa)
    k = 2.0   # k alto = fortemente front-biased
    relative_pos = idx / (total - 1)
    base = 2.718 ** (-k * relative_pos)

    # Bonus conclusione
    if is_last_block and idx == total - 1:
        base += 0.3

    return base


# ---------------------------------------------------------------------------
# 5. MMR — Maximal Marginal Relevance
# ---------------------------------------------------------------------------

def _word_overlap(s1: str, s2: str) -> float:
    """Similarità Jaccard su bag-of-words (senza stopwords)."""
    def words(s):
        ws = re.findall(r'\b[a-zA-ZàèéìîòóùúÀÈÉÌÎÒÓÙÚ]{3,}\b', s.lower())
        return set(w for w in ws if w not in _STOPWORDS_IT)

    w1, w2 = words(s1), words(s2)
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


def _mmr_select(
    candidates: list[tuple[int, str, float]],  # (orig_idx, sentence, relevance)
    k: int,
    lambda_: float = 0.6,
) -> list[tuple[int, str, float]]:
    """
    Maximal Marginal Relevance (Carbonell & Goldstein, 1998).
    Seleziona k frasi bilanciando rilevanza e diversità.

    score_MMR(s) = λ * relevance(s) - (1-λ) * max_similarity(s, già_selezionate)

    λ = 0.6: leggermente sbilanciato verso rilevanza vs diversità.
    Valore scelto empiricamente per testi brevi come le scene.
    """
    if not candidates:
        return []

    selected: list[tuple[int, str, float]] = []
    remaining = list(candidates)

    while remaining and len(selected) < k:
        best_score = -1.0
        best = None

        for item in remaining:
            _, sent, relevance = item
            if not selected:
                # Prima selezione: pura rilevanza
                mmr = relevance
            else:
                max_sim = max(
                    _word_overlap(sent, sel_sent)
                    for _, sel_sent, _ in selected
                )
                mmr = lambda_ * relevance - (1 - lambda_) * max_sim

            if mmr > best_score:
                best_score = mmr
                best = item

        if best:
            selected.append(best)
            remaining.remove(best)

    return selected


# ---------------------------------------------------------------------------
# 6. PIPELINE PRINCIPALE
# ---------------------------------------------------------------------------

def generate_synopsis(
    raw_blocks: list[dict],
    max_sentences: int = 2,
) -> str:
    """
    Genera una sinossi estrattiva per una scena di sceneggiatura.

    Pipeline:
      1. Estrae blocchi di azione e dialogo
      2. Segmenta in frasi (spaCy → regex)
      3. Calcola content score (spaCy NER+POS) o Luhn (fallback)
      4. Calcola position score (lead + conclusione)
      5. Score finale = content * 0.55 + position * 0.45
      6. Selezione MMR per garantire diversità

    Fallback per scene con ≤ 2 frasi di action:
      Restituisce le prime N frasi disponibili (action poi dialogo).
    """
    if not raw_blocks:
        return ""

    # Carica spaCy (già in memoria se il breakdown è stato fatto)
    nlp = None
    try:
        from gliamispo.nlp.spacy_loader import get_nlp_it
        nlp = get_nlp_it()
    except Exception:
        pass

    # ── Estrazione e filtraggio action/dialogo ─────────────────────────────────
    action_blocks = _get_action_blocks(raw_blocks)

    # Filtra le micro-azioni irrilevanti
    relevant = [b for b in action_blocks if _is_relevant_action(b)]

    # Determina il corpus da usare in base alla quantità di action rilevante
    dialogue_position_offset = 0.0  # Offset per position score del dialogo

    if len(relevant) == 0:
        # Solo dialogo o action irrilevante: dialogo come fonte primaria
        narrative_dialogue = _get_narrative_dialogue(raw_blocks, max_exchanges=3)
        if not narrative_dialogue:
            # Fallback: prime battute qualsiasi
            dialogue = _get_key_dialogue(raw_blocks, max_exchanges=max_sentences)
            return _assemble(dialogue[:max_sentences])
        corpus = narrative_dialogue
        dialogue_position_offset = 0.0  # Dialogo è il corpus principale

    elif len(relevant) <= 2:
        # Poca action rilevante: integra con dialogo
        narrative_dialogue = _get_narrative_dialogue(raw_blocks, max_exchanges=2)
        corpus = relevant + narrative_dialogue
        # Dialogo parte da posizione 0.6 per non penalizzarlo troppo
        dialogue_position_offset = 0.6

    else:
        # Action sufficiente: pipeline normale
        corpus = relevant
        dialogue_position_offset = 0.0

    # Segmenta ogni elemento del corpus in frasi
    all_sentences: list[tuple[int, str, int, bool]] = []
    # (block_idx, sentence, sent_idx_in_block, is_dialogue)
    dialogue_start_idx = len(relevant) if len(relevant) <= 2 else len(corpus)

    for block_idx, block_text in enumerate(corpus):
        is_dialogue = block_idx >= dialogue_start_idx
        sents = _split(block_text, nlp)
        for si, s in enumerate(sents):
            all_sentences.append((block_idx, s, si, is_dialogue))

    if not all_sentences:
        # Fallback finale
        if corpus:
            return _assemble(corpus[:max_sentences])
        dialogue = _get_key_dialogue(raw_blocks, max_exchanges=max_sentences)
        return _assemble(dialogue[:max_sentences])

    # Fallback per scene molto brevi
    if len(all_sentences) <= 2:
        result = [s for _, s, _, _ in all_sentences[:max_sentences]]
        if len(result) < max_sentences:
            dialogue = _get_key_dialogue(raw_blocks, max_exchanges=1)
            result.extend(dialogue[:max_sentences - len(result)])
        return _assemble(result)

    # ── Calcolo score ──────────────────────────────────────────────────────────
    n_blocks = len(corpus)
    n_sents = len(all_sentences)

    all_sent_texts = [s for _, s, _, _ in all_sentences]

    # Priorità content score:
    # 1. sentence-transformers (semantic) → content×0.75 + position×0.25
    # 2. sumy (LexRank) → content×0.70 + position×0.30
    # 3. spaCy (NER+POS) → content×0.55 + position×0.45
    # 4. Luhn (keyword) → content×0.55 + position×0.45

    # Prova sentence-transformers
    st_model = _get_st_model()
    semantic_scores = _semantic_score(all_sent_texts, st_model) if st_model else {}
    use_semantic = bool(semantic_scores)

    # Prova LexRank se semantic non disponibile
    lexrank_scores: dict[str, float] = {}
    use_lexrank = False
    if not use_semantic:
        lexrank_scores = _lexrank_score(all_sent_texts)
        use_lexrank = bool(lexrank_scores)

    # Fallback a Luhn se nessun metodo avanzato disponibile e spaCy non presente
    significant = set()
    if not use_semantic and not use_lexrank and not nlp:
        significant = _find_significant_words(all_sent_texts)

    candidates: list[tuple[int, str, float]] = []

    for global_idx, (block_idx, sent, _si, is_dialogue) in enumerate(all_sentences):
        is_last = (block_idx == n_blocks - 1)

        # Content score con priorità: semantic → LexRank → spaCy → Luhn
        if use_semantic:
            content = semantic_scores.get(sent, 0.0)
        elif use_lexrank:
            content = lexrank_scores.get(sent, 0.0)
        elif nlp:
            content = _content_score_spacy(sent, nlp)
        else:
            content = _luhn_score(sent, significant)

        # Position score (basato sull'indice globale nel testo)
        position = _position_score(global_idx, n_sents, is_last_block=is_last)

        # Per le frasi di dialogo, applica offset per non penalizzarle troppo
        # (il dialogo viene aggiunto dopo l'action, quindi avrebbe position bassa)
        if is_dialogue and dialogue_position_offset > 0:
            # Sposta la posizione relativa: il dialogo parte da 0.6 invece di 0.0
            position = max(position, dialogue_position_offset * (1 - global_idx / n_sents))

        # Score finale con pesi adattivi per metodo:
        # - semantic: content×0.75 + position×0.25 (embeddings catturano già il contesto)
        # - LexRank: content×0.70 + position×0.30 (matrice di similarità include posizione)
        # - spaCy/Luhn: content×0.55 + position×0.45 (affidabilità struttura narrativa)
        if use_semantic:
            total = content * 0.75 + position * 0.25
        elif use_lexrank:
            total = content * 0.70 + position * 0.30
        else:
            total = content * 0.55 + position * 0.45

        candidates.append((global_idx, sent, total))

    # ── Selezione MMR ──────────────────────────────────────────────────────────
    selected = _mmr_select(candidates, k=max_sentences, lambda_=0.6)

    # Ripristina ordine narrativo originale
    selected.sort(key=lambda x: x[0])

    result = [s for _, s, _ in selected]

    # Se abbiamo solo 1 frase e ne vogliamo 2, integra con dialogo chiave
    if len(result) < max_sentences:
        dialogue = _get_key_dialogue(raw_blocks, max_exchanges=1)
        result.extend(dialogue[:max_sentences - len(result)])

    return _assemble(result)


# ---------------------------------------------------------------------------
# 7. POST-PROCESSING
# ---------------------------------------------------------------------------

def _clean(s: str) -> str:
    """Pulizia frase estratta."""
    # Rimuove "PERSONAGGIO: " se un dialogo è sfuggito
    s = re.sub(
        r'^[A-ZÀÈÉÌÎÒÓÙÚ][A-Za-zÀ-ú]+(?:\s[A-ZÀÈÉÌÎÒÓÙÚ][A-Za-z]+)*:\s+',
        '', s
    )
    # Tronca frasi eccessivamente lunghe
    words = s.split()
    if len(words) > 35:
        # Cerca taglio naturale su virgola o punto e virgola
        for i in range(34, 20, -1):
            if i < len(words) and words[i].endswith((',', ';')):
                s = " ".join(words[:i + 1]).rstrip(',;') + "."
                break
        else:
            s = " ".join(words[:35]) + "…"
    return s.strip()


def _assemble(sentences: list[str]) -> str:
    """Assembla e capitalizza la sinossi finale."""
    parts = [_clean(s) for s in sentences if s and s.strip()]
    if not parts:
        return ""
    result = " ".join(parts)
    return result[0].upper() + result[1:] if result else ""