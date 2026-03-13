import functools
import os
from importlib.resources import as_file
from platformdirs import user_data_dir
from gliamispo._frozen import resource_path

from gliamispo.database.manager import DatabaseManager
from gliamispo.nlp.term_normalizer import TermNormalizer
from gliamispo.nlp.vocabulary_manager import VocabularyManager
from gliamispo.nlp.ner_extractor import NERExtractor
from gliamispo.nlp.pattern_matcher import DynamicPatternMatcher
from gliamispo.nlp.context_engine import ContextEngine
from gliamispo.nlp.pipeline import NLPPipelineCoordinator
from gliamispo.parsing.fountain_parser import FountainParser
from gliamispo.ml.inference import SklearnInference, OnnxInference
from gliamispo.ml.feedback_loop import FeedbackLoopService
from gliamispo.breakdown.orchestrator import BreakdownOrchestrator


class ServiceContainer:
    def __init__(self, db_path):
        self._db_path = db_path

    @functools.cached_property
    def database(self):
        return DatabaseManager(self._db_path)

    @functools.cached_property
    def term_normalizer(self):
        return TermNormalizer()

    @functools.cached_property
    def vocabulary_manager(self):
        rows = self.database.execute(
            "SELECT term, category FROM vocabulary_terms ORDER BY term"
        ).fetchall()
        terms = [(r[0], r[1]) for r in rows]
        return VocabularyManager(terms)

    @functools.cached_property
    def pattern_matcher(self):
        try:
            db_patterns = self.database.execute(
                "SELECT context_value, suggested_element FROM ai_patterns "
                "WHERE context_type = 'pattern' ORDER BY frequency DESC"
            ).fetchall()
            extra = [(r[0], r[1]) for r in db_patterns if r[0] and r[1]]
        except Exception:
            extra = []

        return DynamicPatternMatcher(extra_patterns=extra)

    @functools.cached_property
    def ner_extractor(self):
        return NERExtractor()

    @functools.cached_property
    def nlp_pipeline(self):
        return NLPPipelineCoordinator(
            ner=self.ner_extractor,
            vocabulary=self.vocabulary_manager,
            pattern_matcher=self.pattern_matcher,
            context_engine=ContextEngine(),
            normalizer=self.term_normalizer,
        )

    @functools.cached_property
    def ml_inference(self):
        from gliamispo.ml.cold_start import ColdStartClassifier

        _data_dir = user_data_dir("Gliamispo", appauthor=False)
        user_model = os.path.join(_data_dir, "model.pkl")
        if os.path.exists(user_model):
            try:
                return SklearnInference(user_model)
            except Exception as e:
                print(f"[Container] Modello corrotto, fallback cold start: {e}")
                return ColdStartClassifier()

        onnx_model = os.path.join(_data_dir, "model.onnx")
        if os.path.exists(onnx_model):
            try:
                return OnnxInference(onnx_model)
            except Exception as e:
                print(f"[Container] ONNX non caricabile, fallback: {e}")

        bundle_ref = resource_path("gliamispo.resources", "model.pkl")
        if bundle_ref.is_file():
            with as_file(bundle_ref) as bundle_model:
                try:
                    return SklearnInference(str(bundle_model))
                except Exception as e:
                    print(f"[Container] Bundle model non caricabile: {e}")

        print("[Container] Nessun modello trovato → ColdStartClassifier attivo")
        return ColdStartClassifier()

    @functools.cached_property
    def feedback_loop(self):
        return FeedbackLoopService(self.database)

    @functools.cached_property
    def ml_scheduler(self):
        from gliamispo.ml.scheduler import MLScheduler
        sched = MLScheduler(self.feedback_loop, interval_seconds=3600)
        sched.start()
        return sched

    @functools.cached_property
    def breakdown_orchestrator(self):
        return BreakdownOrchestrator(
            parser=FountainParser(),
            nlp_pipeline=self.nlp_pipeline,
            database=self.database,
            feedback_loop=self.feedback_loop,
            ml_inference=self.ml_inference,
        )

    @property
    def spacy_status(self) -> dict:
        from gliamispo.nlp.spacy_loader import status_report
        return status_report()