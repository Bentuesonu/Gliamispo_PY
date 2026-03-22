import pytest
from gliamispo.scheduling.genetic import GeneticScheduler


def _make_scheduler(n=5):
    scenes = [{"id": i} for i in range(n)]
    return GeneticScheduler(scenes, constraints={})


async def test_empty_scenes_returns_empty():
    s = GeneticScheduler([], {})
    result = await s.optimize()
    assert result == []


async def test_result_length_matches_scenes():
    s = _make_scheduler(4)
    result = await s.optimize()
    assert len(result) == 4


async def test_result_is_permutation():
    n = 6
    s = _make_scheduler(n)
    result = await s.optimize()
    assert sorted(result) == list(range(n))


async def test_single_scene():
    s = GeneticScheduler([{"id": 42}], {})
    result = await s.optimize()
    assert result == [0]


async def test_progress_callback_called():
    calls = []

    def on_progress(pct, msg):
        calls.append((pct, msg))

    s = _make_scheduler(3)
    await s.optimize(on_progress=on_progress)
    assert len(calls) > 0


async def test_progress_first_call_is_zero():
    calls = []

    def on_progress(pct, msg):
        calls.append(pct)

    s = _make_scheduler(3)
    await s.optimize(on_progress=on_progress)
    assert calls[0] == 0.0


async def test_convergence_stops_early():
    class ConstantScheduler(GeneticScheduler):
        def _fitness(self, individual):
            return 1.0

    s = ConstantScheduler(list(range(5)), {})
    result = await s.optimize()
    assert sorted(result) == [0, 1, 2, 3, 4]


def test_random_schedule_is_permutation():
    s = _make_scheduler(8)
    sched = s._random_schedule()
    assert sorted(sched) == list(range(8))


def test_crossover_produces_permutation():
    s = _make_scheduler(6)
    p1 = [0, 1, 2, 3, 4, 5]
    p2 = [5, 4, 3, 2, 1, 0]
    child = s._crossover(p1, p2)
    assert sorted(child) == [0, 1, 2, 3, 4, 5]


def test_mutate_produces_permutation():
    s = _make_scheduler(6)
    ind = [0, 1, 2, 3, 4, 5]
    mutated = s._mutate(list(ind))
    assert sorted(mutated) == [0, 1, 2, 3, 4, 5]


def test_tournament_returns_valid_individual():
    s = _make_scheduler(5)
    ind_a = list(range(5))
    ind_b = list(range(5, 10))
    # Build scored list with at least TOURNAMENT_SIZE entries
    scored = [(ind_a, 0.5)] * 3 + [(ind_b, 0.9)] * 3
    winner = s._tournament(scored)
    assert winner in [ind_a, ind_b]


def test_fitness_returns_float():
    s = _make_scheduler(3)
    result = s._fitness([0, 1, 2])
    assert isinstance(result, float)
