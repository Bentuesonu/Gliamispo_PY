import pytest
from gliamispo.nlp.pipeline import NLPPipelineCoordinator
from gliamispo.models.scene_element import SceneElement


def _make_element(name, category="Cast", confidence=0.9):
    e = SceneElement()
    e.element_name = name
    e.category = category
    e.ai_confidence = confidence
    return e


class _StubNER:
    def __init__(self, results):
        self._results = results

    async def extract(self, text, known_chars=None):
        return list(self._results)


class _StubVocab:
    def __init__(self, results):
        self._results = results

    async def match(self, text):
        return list(self._results)


class _StubPatterns:
    def __init__(self, results):
        self._results = results

    async def find(self, text):
        return list(self._results)


class _StubNormalizer:
    def normalize(self, element):
        return element


class _StubContext:
    async def enhance(self, elements, context):
        return elements


def _make_pipeline(ner_results=None, vocab_results=None, pattern_results=None):
    return NLPPipelineCoordinator(
        _StubNER(ner_results or []),
        _StubVocab(vocab_results or []),
        _StubPatterns(pattern_results or []),
        _StubContext(),
        _StubNormalizer(),
    )


async def test_process_scene_returns_list():
    pipeline = _make_pipeline(
        ner_results=[_make_element("MARIO")],
        vocab_results=[_make_element("pistola", "Props")],
        pattern_results=[_make_element("auto rossa", "Vehicles")],
    )
    result = await pipeline.process_scene("testo scena", {})
    assert isinstance(result, list)
    assert len(result) == 3


async def test_empty_inputs_return_empty_list():
    pipeline = _make_pipeline()
    result = await pipeline.process_scene("", {})
    assert result == []


async def test_deduplication_by_category_and_name():
    e1 = _make_element("MARIO", confidence=0.9)
    e2 = _make_element("MARIO", confidence=0.8)
    pipeline = _make_pipeline(ner_results=[e1], vocab_results=[e2])
    result = await pipeline.process_scene("", {})
    assert len(result) == 1


async def test_conflict_resolution_keeps_higher_confidence():
    low = _make_element("MARIO", confidence=0.5)
    high = _make_element("MARIO", confidence=0.9)
    # ner returns low, vocab returns high
    pipeline = _make_pipeline(ner_results=[low], vocab_results=[high])
    result = await pipeline.process_scene("", {})
    assert len(result) == 1
    assert result[0].ai_confidence == 0.9


async def test_sort_descending_by_confidence():
    elements = [
        _make_element("A", confidence=0.5),
        _make_element("B", confidence=0.9),
        _make_element("C", confidence=0.7),
    ]
    pipeline = _make_pipeline(ner_results=elements)
    result = await pipeline.process_scene("", {})
    confidences = [e.ai_confidence for e in result]
    assert confidences == sorted(confidences, reverse=True)


async def test_different_categories_same_name_conflict_resolution():
    # _resolve_conflicts keeps elements with same name but different category
    e1 = _make_element("oggetto", "Props", confidence=0.6)
    e2 = _make_element("oggetto", "Vehicles", confidence=0.8)
    pipeline = _make_pipeline(ner_results=[e1], vocab_results=[e2])
    result = await pipeline.process_scene("", {})
    # After conflict resolution: 2 elements (one per category)
    assert len(result) == 2
    categories = {e.category for e in result}
    assert categories == {"Props", "Vehicles"}


async def test_normalizer_called_on_all_elements():
    called = []

    class TrackingNormalizer:
        def normalize(self, element):
            called.append(element.element_name)
            return element

    ner = _StubNER([_make_element("MARIO"), _make_element("LUCIA")])
    pipeline = NLPPipelineCoordinator(
        ner, _StubVocab([]), _StubPatterns([]),
        _StubContext(), TrackingNormalizer(),
    )
    await pipeline.process_scene("", {})
    assert "MARIO" in called
    assert "LUCIA" in called


async def test_context_enhance_called():
    enhanced = [_make_element("EXTRA")]

    class EnhancingContext:
        async def enhance(self, elements, context):
            return enhanced

    pipeline = NLPPipelineCoordinator(
        _StubNER([]), _StubVocab([]), _StubPatterns([]),
        EnhancingContext(), _StubNormalizer(),
    )
    result = await pipeline.process_scene("", {})
    assert len(result) == 1
    assert result[0].element_name == "EXTRA"


async def test_none_confidence_handled():
    e = _make_element("MARIO")
    e.ai_confidence = None
    pipeline = _make_pipeline(ner_results=[e])
    result = await pipeline.process_scene("", {})
    assert len(result) == 1
