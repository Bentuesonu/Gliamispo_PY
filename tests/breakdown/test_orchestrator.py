import tempfile
import os
import pytest
from gliamispo.breakdown.orchestrator import BreakdownOrchestrator
from gliamispo.parsing.fountain_parser import ParsedScene
from gliamispo.models.scene_element import SceneElement


# --- Stubs ---

class _StubParser:
    def __init__(self, scenes):
        self._scenes = scenes

    def parse(self, text):
        return list(self._scenes)


class _StubNLP:
    def __init__(self, results=None):
        self._results = results or []

    async def process_scene(self, synopsis, location, known_chars=None):
        return list(self._results)


class _StubML:
    def __init__(self, results=None):
        self._results = results or []

    def predict(self, text, **kw):
        return list(self._results)


class _StubFeedback:
    def __init__(self):
        self.calls = []

    def track_import(self, scene_id, element_count):
        self.calls.append((scene_id, element_count))


class _FakeDB:
    def __init__(self, confirmed_chars=None):
        self.executed = []
        self._last_row_id = 1
        # Personaggi già confermati dall'utente (simula query user_verified=1)
        self._confirmed_chars = confirmed_chars or []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        self._last_row_id += 1
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        # Se è la query per personaggi confermati, restituisci i dati simulati
        if self.executed and "user_verified = 1" in self.executed[-1][0]:
            return [(c.lower(), c) for c in self._confirmed_chars]
        return []

    def commit(self):
        pass

    @property
    def lastrowid(self):
        return self._last_row_id


def _make_scene(synopsis="Scena test", location="CUCINA", chars=None):
    ps = ParsedScene()
    ps.scene_number = "1"
    ps.location = location
    ps.int_ext = "INT"
    ps.day_night = "GIORNO"
    ps.page_start = 1.0
    ps.page_end = 1.5
    ps.synopsis = synopsis
    ps.characters = chars or []
    return ps


def _make_orchestrator(scenes=None, nlp_results=None, ml_results=None,
                       confirmed_chars=None):
    db = _FakeDB(confirmed_chars=confirmed_chars)
    fb = _StubFeedback()
    orch = BreakdownOrchestrator(
        parser=_StubParser(scenes or []),
        nlp_pipeline=_StubNLP(nlp_results),
        database=db,
        feedback_loop=fb,
        ml_inference=_StubML(ml_results),
    )
    return orch, db, fb


def _make_script_file(content="INT. CUCINA - GIORNO\n\nMARIO\nCiao."):
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".fountain",
                                     delete=False, encoding="utf-8")
    tmp.write(content)
    tmp.close()
    return tmp.name


async def test_empty_scenes_returns_early():
    orch, db, fb = _make_orchestrator(scenes=[])
    path = _make_script_file()
    try:
        await orch.run_breakdown(path, project_id=1)
    finally:
        os.unlink(path)
    assert not any("INSERT INTO scenes" in q[0] for q in db.executed)


async def test_scene_inserted():
    scene = _make_scene()
    orch, db, fb = _make_orchestrator(scenes=[scene])
    path = _make_script_file()
    try:
        await orch.run_breakdown(path, project_id=1)
    finally:
        os.unlink(path)
    assert any("INSERT INTO scenes" in q[0] for q in db.executed)


async def test_feedback_called_per_scene():
    scenes = [_make_scene(), _make_scene("altra scena", "STRADA")]
    orch, db, fb = _make_orchestrator(scenes=scenes)
    path = _make_script_file()
    try:
        await orch.run_breakdown(path, project_id=1)
    finally:
        os.unlink(path)
    assert len(fb.calls) == 2


async def test_progress_callback_called():
    scene = _make_scene()
    orch, db, fb = _make_orchestrator(scenes=[scene])
    calls = []
    path = _make_script_file()
    try:
        await orch.run_breakdown(path, project_id=1,
                                  on_progress=lambda p, m: calls.append(p))
    finally:
        os.unlink(path)
    assert len(calls) > 0
    assert calls[-1] == 1.0


async def test_characters_inserted():
    scene = _make_scene(chars=["MARIO", "LUCIA"])
    orch, db, fb = _make_orchestrator(scenes=[scene])
    path = _make_script_file()
    try:
        await orch.run_breakdown(path, project_id=1)
    finally:
        os.unlink(path)
    cast_inserts = [q for q in db.executed if "scene_elements" in q[0] and "Cast" in str(q[1])]
    assert len(cast_inserts) == 2


async def test_min_confidence_filter():
    elem_high = SceneElement(category="Props", element_name="pistola",
                             ai_confidence=0.9)
    elem_low = SceneElement(category="Props", element_name="sedia",
                            ai_confidence=0.3)
    scene = _make_scene()
    orch, db, fb = _make_orchestrator(
        scenes=[scene],
        nlp_results=[elem_high, elem_low],
    )
    path = _make_script_file()
    try:
        await orch.run_breakdown(path, project_id=1)
    finally:
        os.unlink(path)
    element_inserts = [q for q in db.executed
                       if "scene_elements" in q[0] and "ai_suggested" in q[0]]
    assert len(element_inserts) == 1


def test_merge_ml_no_duplicates():
    orch, _, _ = _make_orchestrator()
    e1 = SceneElement(category="Props", element_name="pistola")
    e2 = SceneElement(category="Props", element_name="pistola")
    result = orch._merge_ml([e1], [e2])
    assert len(result) == 1


def test_merge_ml_adds_new():
    orch, _, _ = _make_orchestrator()
    e1 = SceneElement(category="Props", element_name="pistola")
    e2 = SceneElement(category="Vehicles", element_name="auto")
    result = orch._merge_ml([e1], [e2])
    assert len(result) == 2


def test_merge_ml_empty_ml():
    orch, _, _ = _make_orchestrator()
    e1 = SceneElement(category="Cast", element_name="MARIO")
    result = orch._merge_ml([e1], [])
    assert result == [e1]


# ── BUG 4 regression: scena senza dialogo con personaggi nel testo d'azione ──


async def test_known_char_found_in_action_title_case():
    """BUG 4: personaggio in Title Case nel testo d'azione di una scena senza dialogo."""
    # Scena 1: BEPPE ha dialogo → finisce in all_known_chars
    scene1 = _make_scene(
        synopsis="beppe entra in cucina.",
        chars=["BEPPE"],
    )
    # Scena 2: niente dialogo, ma "Beppe" appare in Title Case nel testo d'azione
    scene2 = _make_scene(
        synopsis="Beppe guida verso il mare in silenzio.",
        chars=[],
        location="MACCHINA",
    )
    orch, db, fb = _make_orchestrator(scenes=[scene1, scene2])
    path = _make_script_file()
    try:
        await orch.run_breakdown(path, project_id=1)
    finally:
        os.unlink(path)

    cast_inserts = [
        q for q in db.executed
        if "scene_elements" in q[0] and "Cast" in str(q[1]) and "Beppe" in str(q[1])
    ]
    assert len(cast_inserts) >= 1, "Beppe deve essere trovato nella scena 2 via known_character_lookup"


async def test_known_char_found_in_action_all_caps():
    """BUG 4: personaggio in ALL CAPS nel testo d'azione di una scena senza dialogo."""
    scene1 = _make_scene(
        synopsis="mario saluta.",
        chars=["MARIO"],
    )
    scene2 = _make_scene(
        synopsis="MARIO corre verso l'uscita.",
        chars=[],
        location="STRADA",
    )
    orch, db, fb = _make_orchestrator(scenes=[scene1, scene2])
    path = _make_script_file()
    try:
        await orch.run_breakdown(path, project_id=1)
    finally:
        os.unlink(path)

    cast_inserts = [
        q for q in db.executed
        if "scene_elements" in q[0] and "Cast" in str(q[1]) and "Mario" in str(q[1])
    ]
    assert len(cast_inserts) >= 1, "Mario (ALL CAPS action) deve essere trovato via known_character_lookup"


async def test_frequent_char_gets_higher_confidence():
    """BUG 4: personaggio con ≥2 scene di dialogo riceve confidence potenziata."""
    scene1 = _make_scene(synopsis="mario entra.", chars=["MARIO"])
    scene2 = _make_scene(synopsis="mario esce.", chars=["MARIO"])
    scene3 = _make_scene(synopsis="Mario cammina solo.", chars=[])
    orch, db, fb = _make_orchestrator(scenes=[scene1, scene2, scene3])
    path = _make_script_file()
    try:
        await orch.run_breakdown(path, project_id=1)
    finally:
        os.unlink(path)

    # Trova l'INSERT di Mario nella scena 3 (known_char_lookup con boost freq)
    lookup_inserts = [
        q for q in db.executed
        if "scene_elements" in q[0]
        and "known_character_lookup" in str(q[1])
        and "Mario" in str(q[1])
    ]
    assert len(lookup_inserts) >= 1
    # La confidence deve essere ≥ 0.85 (0.85 base + 0.03 freq boost)
    conf = lookup_inserts[0][1][3]  # parametro ai_confidence
    assert conf >= 0.85, f"Confidence attesa ≥ 0.85 per personaggio frequente, ottenuto {conf}"


# ── Persistenza known_chars: correzioni utente alimentano breakdown successivi ──


async def test_user_confirmed_char_used_in_new_breakdown():
    """Personaggi confermati dall'utente (user_verified=1) vengono usati
    nel breakdown di nuovi script, anche se non hanno dialogo."""
    # LUCIA è stata confermata in un breakdown precedente (simula DB)
    # Nuovo script: LUCIA appare nel testo d'azione ma senza dialogo
    scene = _make_scene(
        synopsis="Lucia osserva dalla finestra.",
        chars=[],  # nessun dialogo
        location="CAMERA DA LETTO",
    )
    orch, db, fb = _make_orchestrator(
        scenes=[scene],
        confirmed_chars=["Lucia"],  # <- personaggio confermato in passato
    )
    path = _make_script_file()
    try:
        await orch.run_breakdown(path, project_id=1)
    finally:
        os.unlink(path)

    # Verifica che la query per personaggi confermati sia stata eseguita
    confirmed_query = [q for q in db.executed if "user_verified = 1" in q[0]]
    assert len(confirmed_query) == 1, "Deve eseguire la query per personaggi confermati"

    # Verifica che LUCIA sia stata trovata e inserita
    cast_inserts = [
        q for q in db.executed
        if "scene_elements" in q[0] and "Cast" in str(q[1]) and "Lucia" in str(q[1])
    ]
    assert len(cast_inserts) >= 1, "Lucia (confermata dall'utente) deve essere trovata nel testo d'azione"


async def test_user_confirmed_char_gets_frequency_boost():
    """Personaggi confermati dall'utente ricevono boost frequenza (≥2)
    quindi confidence più alta."""
    scene = _make_scene(
        synopsis="Marco entra nella stanza.",
        chars=[],
        location="UFFICIO",
    )
    orch, db, fb = _make_orchestrator(
        scenes=[scene],
        confirmed_chars=["Marco"],
    )
    path = _make_script_file()
    try:
        await orch.run_breakdown(path, project_id=1)
    finally:
        os.unlink(path)

    lookup_inserts = [
        q for q in db.executed
        if "scene_elements" in q[0]
        and "known_character_lookup" in str(q[1])
        and "Marco" in str(q[1])
    ]
    assert len(lookup_inserts) >= 1
    # Confidence: 0.85 (Title Case) + 0.03 (freq boost) = 0.88
    conf = lookup_inserts[0][1][3]
    assert conf >= 0.88, f"Personaggio confermato deve avere boost frequenza, confidence={conf}"
