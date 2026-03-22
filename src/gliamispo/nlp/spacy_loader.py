import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

IT_MODEL_NAME = "it_core_news_lg"
EN_MODEL_NAME = "en_core_web_sm"

_lock = threading.Lock()

_nlp_it = None
_nlp_en = None
_spacy_available: Optional[bool] = None
_load_done_it = False
_load_done_en = False


def _check_spacy() -> bool:
    global _spacy_available
    if _spacy_available is not None:
        return _spacy_available
    try:
        import spacy  # noqa: F401
        _spacy_available = True
    except ImportError:
        _spacy_available = False
        logger.warning(
            "[spaCy] Libreria spaCy non installata. "
            "NER avanzata disabilitata. "
            "Per abilitarla: pip install spacy"
        )
    return _spacy_available


def _load_model(model_name: str):
    if not _check_spacy():
        return None
    try:
        import spacy
        nlp = spacy.load(model_name)
        logger.info(f"[spaCy] Modello '{model_name}' caricato correttamente.")
        return nlp
    except OSError:
        logger.warning(
            f"[spaCy] Modello '{model_name}' non trovato. "
            f"Installa con: python -m spacy download {model_name}"
        )
        return None
    except Exception as e:
        logger.error(f"[spaCy] Errore imprevisto caricando '{model_name}': {e}")
        return None


def get_nlp_it():
    global _nlp_it, _load_done_it
    if not _load_done_it:
        with _lock:
            if not _load_done_it:
                _nlp_it = _load_model(IT_MODEL_NAME)
                _load_done_it = True
    return _nlp_it


def get_nlp_en():
    global _nlp_en, _load_done_en
    if not _load_done_en:
        with _lock:
            if not _load_done_en:
                _nlp_en = _load_model(EN_MODEL_NAME)
                _load_done_en = True
    return _nlp_en


def is_available() -> bool:
    return get_nlp_it() is not None or get_nlp_en() is not None


def status_report() -> dict:
    return {
        "spacy_installed": _check_spacy(),
        "it_model": IT_MODEL_NAME,
        "it_loaded": get_nlp_it() is not None,
        "en_model": EN_MODEL_NAME,
        "en_loaded": get_nlp_en() is not None,
    }
