import random
import asyncio


def save_schedule_to_db(db, project_id, ordered_scenes):
    db.execute("DELETE FROM schedule_entries WHERE project_id = ?", (project_id,))
    for day_num, scene in enumerate(ordered_scenes, start=1):
        db.execute(
            "INSERT OR REPLACE INTO schedule_entries (project_id, scene_id, shooting_day, position) VALUES (?, ?, ?, ?)",
            (project_id, scene["id"], day_num, day_num),
        )
    db.commit()


class GeneticScheduler:
    POP_SIZE = 100
    GENERATIONS = 500
    MUTATION_RATE = 0.10
    ELITE_SIZE = 10
    TOURNAMENT_SIZE = 5
    CONVERGENCE_THRESHOLD = 0.001

    def __init__(self, scenes, constraints):
        self.scenes = scenes
        self.constraints = constraints

    async def optimize(self, on_progress=None):
        if not self.scenes:
            return []

        population = [self._random_schedule() for _ in range(self.POP_SIZE)]
        best_fitness = None

        for gen in range(self.GENERATIONS):
            scored = [(ind, self._fitness(ind)) for ind in population]
            scored.sort(key=lambda x: x[1], reverse=True)

            current_best = scored[0][1]
            if best_fitness is not None:
                if abs(current_best - best_fitness) < self.CONVERGENCE_THRESHOLD:
                    break
            best_fitness = current_best

            if gen % 10 == 0:
                if on_progress:
                    on_progress(gen / self.GENERATIONS, f"Gen {gen}")
                await asyncio.sleep(0)

            elite = [s[0] for s in scored[:self.ELITE_SIZE]]
            children = list(elite)
            while len(children) < self.POP_SIZE:
                p1 = self._tournament(scored)
                p2 = self._tournament(scored)
                child = self._crossover(p1, p2)
                if random.random() < self.MUTATION_RATE:
                    child = self._mutate(child)
                children.append(child)
            population = children

        scored = [(ind, self._fitness(ind)) for ind in population]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def _tournament(self, scored):
        contestants = random.sample(scored, self.TOURNAMENT_SIZE)
        return max(contestants, key=lambda x: x[1])[0]

    def _random_schedule(self):
        schedule = list(range(len(self.scenes)))
        random.shuffle(schedule)
        return schedule

    def _fitness(self, individual):
        score = 0.0
        for i in range(len(individual) - 1):
            a = self.scenes[individual[i]]
            b = self.scenes[individual[i + 1]]
            if a.get("location") == b.get("location"):
                score += 3.0
            if a.get("int_ext") == b.get("int_ext"):
                score += 1.0
        for rank, idx in enumerate(individual):
            sc = self.scenes[idx]
            if sc.get("is_locked") and \
               sc.get("original_position") is not None:
                if rank != sc["original_position"]:
                    score -= 10.0
        return score

    def _crossover(self, p1, p2):
        size = len(p1)
        if size < 2:
            return list(p1)
        start, end = sorted(random.sample(range(size), 2))
        child = [None] * size
        child[start:end] = p1[start:end]
        fill = [g for g in p2 if g not in child[start:end]]
        idx = 0
        for i in range(size):
            if child[i] is None:
                child[i] = fill[idx]
                idx += 1
        return child

    def _mutate(self, individual):
        if len(individual) < 2:
            return individual
        a, b = random.sample(range(len(individual)), 2)
        individual[a], individual[b] = individual[b], individual[a]
        return individual
