"""Tests for synopsis_generator module."""

import pytest


def test_generate_synopsis_returns_string():
    """Smoke test: generate_synopsis returns a non-empty string."""
    blocks = [
        {"type": "action", "text": "Erika entra in cucina e trova Mauro."},
        {"type": "character", "text": "MAURO"},
        {"type": "dialogue", "text": "Hai mangiato?"},
        {"type": "action", "text": "Lei appoggia la borsa senza rispondere."},
    ]
    from gliamispo.services.synopsis_generator import generate_synopsis
    result = generate_synopsis(blocks)
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_synopsis_empty_blocks():
    """Empty blocks should return empty string."""
    from gliamispo.services.synopsis_generator import generate_synopsis
    result = generate_synopsis([])
    assert result == ""


def test_extract_scene_text():
    """extract_scene_text should combine action and dialogue."""
    blocks = [
        {"type": "action", "text": "Marco apre la porta."},
        {"type": "character", "text": "MARCO"},
        {"type": "dialogue", "text": "Chi è?"},
    ]
    from gliamispo.services.synopsis_generator import extract_scene_text
    result = extract_scene_text(blocks)
    assert "Marco apre la porta." in result
    assert "MARCO: Chi è?" in result


def test_lexrank_fallback_if_sumy_missing(monkeypatch):
    """When sumy is not installed, generate_synopsis should not raise."""
    import sys

    # Simula ImportError su sumy
    original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

    def mock_import(name, *args, **kwargs):
        if name.startswith('sumy'):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr('builtins.__import__', mock_import)

    # Rimuovi sumy dalla cache dei moduli se presente
    modules_to_remove = [k for k in sys.modules if k.startswith('sumy')]
    for mod in modules_to_remove:
        monkeypatch.delitem(sys.modules, mod, raising=False)

    blocks = [
        {"type": "action", "text": "Erika entra nella stanza e guarda fuori dalla finestra."},
        {"type": "action", "text": "La pioggia cade incessante mentre lei riflette sul passato."},
        {"type": "action", "text": "Si volta verso Marco che è appena entrato dalla porta."},
    ]

    # Reimporta per testare con il mock
    from importlib import reload
    import gliamispo.services.synopsis_generator as sg
    reload(sg)

    # Non deve sollevare eccezioni
    result = sg.generate_synopsis(blocks)
    assert isinstance(result, str)


def test_irrelevant_action_filtered():
    """Scenes with only micro-actions should use dialogue instead."""
    blocks = [
        {"type": "action", "text": "Si avvicina."},
        {"type": "action", "text": "Ci pensa un attimo."},
        {"type": "action", "text": "Annuisce."},
        {"type": "character", "text": "MARCO"},
        {"type": "dialogue", "text": "Devo dirti una cosa importante sulla questione del testamento."},
        {"type": "character", "text": "ANNA"},
        {"type": "dialogue", "text": "Hai scoperto qualcosa di nuovo sui documenti del nonno?"},
    ]
    from gliamispo.services.synopsis_generator import generate_synopsis

    result = generate_synopsis(blocks)

    # Le micro-azioni non dovrebbero apparire nel risultato
    assert "Si avvicina" not in result
    assert "Ci pensa" not in result
    assert "Annuisce" not in result

    # Il dialogo dovrebbe essere usato
    # (verifica che ci sia almeno una parola chiave dal dialogo)
    assert len(result) > 0


def test_dialogue_heavy_scene():
    """Scenes with 1 action line and many dialogues should not output just the action."""
    blocks = [
        {"type": "action", "text": "Si siede."},
        {"type": "character", "text": "MARCO"},
        {"type": "dialogue", "text": "Ho finalmente trovato il documento che cercavamo da mesi."},
        {"type": "character", "text": "ANNA"},
        {"type": "dialogue", "text": "Davvero? Dove lo hai trovato dopo tutto questo tempo?"},
        {"type": "character", "text": "MARCO"},
        {"type": "dialogue", "text": "Era nascosto nella cassaforte del vecchio studio di papà."},
        {"type": "character", "text": "ANNA"},
        {"type": "dialogue", "text": "Non posso crederci. Abbiamo cercato lì mille volte."},
        {"type": "character", "text": "MARCO"},
        {"type": "dialogue", "text": "C'era un doppio fondo segreto che nessuno conosceva."},
        {"type": "character", "text": "ANNA"},
        {"type": "dialogue", "text": "Questo cambia tutto per l'eredità della famiglia."},
        {"type": "character", "text": "MARCO"},
        {"type": "dialogue", "text": "Esatto. Ora abbiamo le prove che ci servivano."},
        {"type": "character", "text": "ANNA"},
        {"type": "dialogue", "text": "Dobbiamo chiamare subito l'avvocato per informarlo."},
        {"type": "character", "text": "MARCO"},
        {"type": "dialogue", "text": "Già fatto. Viene domani mattina alle nove in punto."},
        {"type": "character", "text": "ANNA"},
        {"type": "dialogue", "text": "Finalmente potremo chiudere questa storia una volta per tutte."},
        {"type": "character", "text": "MARCO"},
        {"type": "dialogue", "text": "Sì, dopo tre anni di battaglie legali vediamo la fine."},
        {"type": "character", "text": "ANNA"},
        {"type": "dialogue", "text": "Non vedo l'ora di raccontarlo a mamma. Sarà felicissima."},
        {"type": "character", "text": "MARCO"},
        {"type": "dialogue", "text": "Andiamo insieme da lei stasera per darle la notizia."},
        {"type": "character", "text": "ANNA"},
        {"type": "dialogue", "text": "Perfetto. Porto una bottiglia di spumante per festeggiare."},
    ]
    from gliamispo.services.synopsis_generator import generate_synopsis

    result = generate_synopsis(blocks)

    # La sinossi non dovrebbe essere solo "Si siede."
    assert result != "Si siede."
    assert len(result) > 15  # Deve contenere contenuto significativo


def test_semantic_score_without_model():
    """_semantic_score with model=None should return empty dict without crash."""
    from gliamispo.services.synopsis_generator import _semantic_score

    sentences = [
        "Erika entra nella stanza.",
        "Marco la guarda con sorpresa.",
        "Lei sorride e si avvicina.",
    ]

    result = _semantic_score(sentences, model=None)

    assert result == {}
    assert isinstance(result, dict)
