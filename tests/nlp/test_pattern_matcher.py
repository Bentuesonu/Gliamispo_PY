import pytest
from gliamispo.nlp.pattern_matcher import DynamicPatternMatcher


@pytest.fixture
def matcher():
    return DynamicPatternMatcher()


@pytest.mark.asyncio
async def test_adjective_after_noun(matcher):
    results = await matcher.find("Mario indossa una camicia stropicciata.")
    names = [e.element_name for e in results]
    assert any("stropicciata" in n for n in names), names


@pytest.mark.asyncio
async def test_adjective_after_animal(matcher):
    results = await matcher.find("Un gatto nero dorme sul tappeto.")
    names = [e.element_name for e in results]
    assert any("nero" in n for n in names), names


@pytest.mark.asyncio
async def test_compound_set_dressing(matcher):
    # il pattern è \btende?\b che cattura "tende" (plurale), non "tenda"
    results = await matcher.find("Le tende moschiera sono appese alle finestre.")
    names = [e.element_name for e in results]
    assert any("moschiera" in n for n in names), names


@pytest.mark.asyncio
async def test_no_adjective_when_followed_by_stopword(matcher):
    results = await matcher.find("La camicia è sul tavolo.")
    names = [e.element_name for e in results]
    # "è" è stopword, nessun qualificatore dovrebbe essere aggiunto
    assert any(n == "camicia" for n in names), names


@pytest.mark.asyncio
async def test_adjective_before_noun(matcher):
    # "vecchia" precede "valigia"
    results = await matcher.find("La vecchia valigia era pesante.")
    names = [e.element_name for e in results]
    assert any("vecchia" in n for n in names), names


@pytest.mark.asyncio
async def test_uppercase_word_not_captured(matcher):
    # "MARIO" dopo il match è un nome proprio → non deve diventare qualificatore
    results = await matcher.find("La camicia MARIO portava.")
    names = [e.element_name for e in results]
    # "MARIO" è maiuscolo, non deve essere incluso
    assert not any("mario" in n.lower() for n in names), names


@pytest.mark.asyncio
async def test_empty_text(matcher):
    results = await matcher.find("")
    assert results == []


@pytest.mark.asyncio
async def test_canonical_base_preserved(matcher):
    # Il nome canonico deve rimanere invariato se non ci sono aggettivi
    results = await matcher.find("Vedo una pistola.")
    names = [e.element_name for e in results]
    assert any("pistola" in n for n in names), names


@pytest.mark.asyncio
async def test_deduplication_same_context(matcher):
    # Stessa occorrenza non deve duplicarsi
    results = await matcher.find("La camicia stropicciata e ancora la camicia stropicciata.")
    cat_names = [(e.category, e.element_name.lower()) for e in results]
    assert len(cat_names) == len(set(cat_names))
