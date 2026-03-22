import pickle
import tempfile
import os
import threading
import pytest
from gliamispo.ml.inference import DummyInference, SklearnInference
from gliamispo.ml.feedback_loop import FeedbackLoopService
from gliamispo.ml.scheduler import MLScheduler
from gliamispo.ml.analytics import MLAnalyticsService


# --- DummyInference ---

def test_dummy_returns_empty():
    d = DummyInference()
    assert d.predict("testo scena") == []


def test_dummy_ignores_params():
    d = DummyInference()
    assert d.predict("x", max_results=10, min_confidence=0.0) == []


# --- SklearnInference ---

def _make_model_file():
    from sklearn.linear_model import SGDClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = [
        "pistola arma fuoco",
        "macchina auto veicolo",
        "attore personaggio cast",
    ]
    labels = ["Props", "Vehicles", "Cast"]
    vec = TfidfVectorizer()
    X = vec.fit_transform(texts)
    clf = SGDClassifier(loss="modified_huber", max_iter=100, random_state=0)
    clf.fit(X, labels)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pkl")
    pickle.dump({"vectorizer": vec, "classifier": clf}, tmp)
    tmp.close()
    return tmp.name


@pytest.fixture
def model_path():
    path = _make_model_file()
    yield path
    os.unlink(path)


def test_sklearn_predict_returns_list(model_path):
    inf = SklearnInference(model_path)
    results = inf.predict("pistola arma fuoco")
    assert isinstance(results, list)


def test_sklearn_results_have_confidence(model_path):
    inf = SklearnInference(model_path)
    results = inf.predict("pistola arma fuoco")
    for r in results:
        assert r.ai_confidence is not None
        assert 0.0 <= r.ai_confidence <= 1.0


def test_sklearn_detection_method(model_path):
    inf = SklearnInference(model_path)
    results = inf.predict("pistola arma fuoco")
    for r in results:
        assert r.detection_method == "sklearn"


def test_sklearn_respects_min_confidence(model_path):
    inf = SklearnInference(model_path)
    results = inf.predict("pistola arma fuoco", min_confidence=1.1)
    assert results == []


def test_sklearn_thread_safe(model_path):
    inf = SklearnInference(model_path)
    errors = []

    def call():
        try:
            inf.predict("auto macchina")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=call) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


# --- FeedbackLoopService ---

class _FakeDB:
    def __init__(self):
        self.queries = []
        self._correction_count = 0

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        return self

    def fetchone(self):
        return (self._correction_count,)

    def fetchall(self):
        return []


def test_feedback_track_import_queues():
    db = _FakeDB()
    fb = FeedbackLoopService(db)
    fb.track_import(1, 3)
    assert len(fb._queue) == 1


def test_feedback_flush_on_threshold():
    db = _FakeDB()
    fb = FeedbackLoopService(db)
    for i in range(FeedbackLoopService.FLUSH_THRESHOLD):
        fb.track_import(i, 1)
    assert len(fb._queue) == 0
    assert any("training_data" in q[0] for q in db.queries)


def test_feedback_flush_persists_before_clear():
    db = _FakeDB()
    fb = FeedbackLoopService(db)
    for i in range(FeedbackLoopService.FLUSH_THRESHOLD):
        fb.track_import(i, 1)
    insert_queries = [q for q in db.queries if "INSERT INTO training_data" in q[0]]
    assert len(insert_queries) == FeedbackLoopService.FLUSH_THRESHOLD


def test_feedback_retrain_callback():
    db = _FakeDB()
    db._correction_count = FeedbackLoopService.RETRAIN_THRESHOLD
    called = []
    fb = FeedbackLoopService(db)
    fb._on_retrain_needed = lambda: called.append(True)
    fb._check_retrain()
    assert called == [True]


def test_feedback_no_callback_below_threshold():
    db = _FakeDB()
    db._correction_count = FeedbackLoopService.RETRAIN_THRESHOLD - 1
    called = []
    fb = FeedbackLoopService(db)
    fb._on_retrain_needed = lambda: called.append(True)
    fb._check_retrain()
    assert called == []


def test_feedback_record_category_change():
    db = _FakeDB()
    fb = FeedbackLoopService(db)
    fb.record_category_change(1, 2, "Cast", "Props", 0.8)
    assert any("user_corrections" in q[0] and "MODIFY_CATEGORY" in q[0] for q in db.queries)


def test_feedback_track_verification_accept():
    db = _FakeDB()
    fb = FeedbackLoopService(db)
    fb.track_verification(1, 1, accepted=True)
    assert any("VERIFY" in str(q[1]) for q in db.queries)


def test_feedback_track_verification_reject():
    db = _FakeDB()
    fb = FeedbackLoopService(db)
    fb.track_verification(1, 1, accepted=False)
    assert any("REJECT" in str(q[1]) for q in db.queries)


# --- MLScheduler ---

def test_scheduler_start_stop():
    db = _FakeDB()
    fb = FeedbackLoopService(db)
    sched = MLScheduler(fb, interval_seconds=3600)
    sched.start()
    assert sched._running
    sched.stop()
    assert not sched._running


def test_scheduler_trigger_now():
    db = _FakeDB()
    db._correction_count = 0
    fb = FeedbackLoopService(db)
    sched = MLScheduler(fb)
    sched.trigger_now()


def test_scheduler_double_start_no_error():
    db = _FakeDB()
    fb = FeedbackLoopService(db)
    sched = MLScheduler(fb, interval_seconds=3600)
    sched.start()
    sched.start()
    sched.stop()


# --- MLAnalyticsService ---

class _FakeDBAnalytics:
    def __init__(self, row=None):
        self._row = row or (0,)
        self.queries = []

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        return self

    def fetchone(self):
        return self._row


def test_analytics_acceptance_rate_no_data():
    db = _FakeDBAnalytics((None,))
    svc = MLAnalyticsService(db)
    assert svc.acceptance_rate() == 0.0


def test_analytics_acceptance_rate_value():
    db = _FakeDBAnalytics((0.75,))
    svc = MLAnalyticsService(db)
    assert svc.acceptance_rate() == 0.75


def test_analytics_correction_count():
    db = _FakeDBAnalytics((7,))
    svc = MLAnalyticsService(db)
    assert svc.correction_count() == 7


def test_analytics_pending_training_scenes():
    db = _FakeDBAnalytics((3,))
    svc = MLAnalyticsService(db)
    assert svc.pending_training_scenes() == 3


def test_analytics_record_prediction():
    db = _FakeDBAnalytics()
    svc = MLAnalyticsService(db)
    svc.record_prediction(1, "Cast", 0.9, "sklearn")
    assert any("ml_analytics" in q[0] for q in db.queries)
