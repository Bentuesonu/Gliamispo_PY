import random
import asyncio


def scene_duration_hours(scene: dict) -> float:
    """
    Calcola durata stimata in ore con moltiplicatori professionali.
    Standard industria: 1 pagina = 1.5h base, modificata da complessità.
    """
    # Override manuale utente ha priorità assoluta
    if scene.get("manual_shooting_hours", 0.0) > 0:
        return float(scene["manual_shooting_hours"])

    # Base: ottavi di pagina → ore (1 pagina = 1.5h, 1/8 = ~11min)
    eighths = (
        (scene.get("page_end_whole", 1) * 8 + scene.get("page_end_eighths", 0))
        - (scene.get("page_start_whole", 1) * 8 + scene.get("page_start_eighths", 0))
    )
    base_hours = max(eighths / 8.0 * 1.5, 0.25)  # minimo 15 min

    multiplier = 1.0

    # Tipo scena da scene_elements (passati come liste nel dict)
    elements = scene.get("elements", [])  # lista di (category, name) tuple
    categories = {e[0] for e in elements} if elements else set()

    if "Stunts" in categories:
        multiplier *= 3.0        # stunt: setup sicurezza, prove, take multipli
    if "Intimacy" in categories or scene.get("requires_intimacy_coordinator"):
        multiplier *= 1.8        # protocollo intimacy coordinator obbligatorio
    if "VFX" in categories or "Mechanical FX" in categories:
        multiplier *= 2.0        # playback plates, witness cam, marcatori VFX

    # Numero cast (ogni attore oltre 2 aggiunge 15% — direzione attori, continuità)
    cast_count = sum(1 for e in elements if e[0] == "Cast")
    if cast_count > 2:
        multiplier *= 1.0 + (cast_count - 2) * 0.15

    # INT/EXT: scene INT richiedono setup luci completo (+20%)
    if scene.get("int_ext") == "INT":
        multiplier *= 1.2

    # Notte: attrezzatura aggiuntiva, crew più lenta, setup generatori (+50%)
    if scene.get("day_night") == "NOTTE":
        multiplier *= 1.5
    elif scene.get("day_night") in ("ALBA", "TRAMONTO"):
        multiplier *= 1.3   # finestra luce ristretta, pressione temporale

    # Shot count: ogni 5 inquadrature oltre le 5 base = +30min setup macchina
    shot_count = scene.get("shot_count", 0)
    if shot_count > 5:
        multiplier *= 1.0 + ((shot_count - 5) / 5) * 0.25

    return round(base_hours * multiplier, 2)


def save_schedule_to_db(db, project_id, ordered_scenes, max_hours_per_day: float = 10.0):
    """
    Raggruppa le scene ordinate in giorni di ripresa rispettando max_hours_per_day.
    Non mescola GIORNO e NOTTE nello stesso giorno (standard industria).
    """
    db.execute("DELETE FROM schedule_entries WHERE project_id = ?", (project_id,))

    day, pos = 1, 0
    day_hours = 0.0
    day_type = None  # 'GIORNO' o 'NOTTE' — non si mescolano

    for scene in ordered_scenes:
        h = scene_duration_hours(scene)
        dn = scene.get("day_night", "GIORNO")
        # Normalizza: ALBA/TRAMONTO vanno con GIORNO per semplicità
        dn_bucket = "NOTTE" if dn == "NOTTE" else "GIORNO"

        # Forza nuovo giorno se: supera ore massime OPPURE cambia tipo giorno/notte
        overflow = day_hours + h > max_hours_per_day and day_hours > 0
        type_conflict = day_type is not None and dn_bucket != day_type and day_hours > 0

        if overflow or type_conflict:
            day += 1
            pos = 0
            day_hours = 0.0
            day_type = None

        if day_type is None:
            day_type = dn_bucket

        db.execute(
            "INSERT OR REPLACE INTO schedule_entries "
            "(project_id, scene_id, shooting_day, position) VALUES (?,?,?,?)",
            (project_id, scene["id"], day, pos),
        )
        day_hours += h
        pos += 1

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

    def _fitness(self, individual) -> float:
        score = 0.0
        max_h = self.constraints.get("max_hours_per_day", 10.0)

        # Simula assegnazione giorni per calcolare penalità realistiche
        day, day_hours, day_type = 1, 0.0, None
        day_locations: dict[int, set] = {}

        for rank, idx in enumerate(individual):
            sc = self.scenes[idx]
            h = scene_duration_hours(sc)
            dn = "NOTTE" if sc.get("day_night") == "NOTTE" else "GIORNO"

            overflow = day_hours + h > max_h and day_hours > 0
            type_conflict = day_type is not None and dn != day_type and day_hours > 0
            if overflow or type_conflict:
                day += 1; day_hours = 0.0; day_type = None

            if day_type is None: day_type = dn
            day_locations.setdefault(day, set()).add(sc.get("location", ""))
            day_hours += h

            # Penalità scene locked fuori posizione
            if sc.get("is_locked") and sc.get("original_position") is not None:
                if rank != sc["original_position"]:
                    score -= 15.0

        # Premia location consecutive (meno spostamenti)
        for i in range(len(individual) - 1):
            a = self.scenes[individual[i]]
            b = self.scenes[individual[i + 1]]
            if a.get("location") == b.get("location"):
                score += 5.0          # stessa location consecutiva: massimo risparmio
            if a.get("int_ext") == b.get("int_ext"):
                score += 1.0          # stesso tipo INT/EXT: setup simile
            if (a.get("int_ext") == "EXT" and a.get("day_night") == "GIORNO"
                    and b.get("int_ext") == "EXT" and b.get("day_night") == "GIORNO"):
                score += 2.0          # EXT/GIORNO consecutivi: stessa luce naturale

        # Penalità giorni con troppe location diverse (travel time)
        for d, locs in day_locations.items():
            if len(locs) > 3:
                score -= (len(locs) - 3) * 4.0   # ogni location in più oltre 3 = -4

        # Penalità stunt/intimacy consecutivi senza pausa
        for i in range(len(individual) - 1):
            a_cats = {e[0] for e in self.scenes[individual[i]].get("elements", [])}
            b_cats = {e[0] for e in self.scenes[individual[i + 1]].get("elements", [])}
            if "Stunts" in a_cats and "Stunts" in b_cats:
                score -= 3.0   # stunt consecutivi senza reset sicurezza
            if "Intimacy" in a_cats and "Intimacy" in b_cats:
                score -= 2.0   # intimacy back-to-back: crew e cast esauriti

        score += self._cast_availability_score(individual)
        return score

    def _cast_availability_score(self, individual) -> float:
        if not self.constraints.get("cast_blocked_days"):
            return 0.0
        score, blocked = 0.0, self.constraints["cast_blocked_days"]
        pages_per_day = self.constraints.get("pages_per_day", 8)
        cumulative, current_day = 0, 1
        for idx in individual:
            sc = self.scenes[idx]
            for actor in sc.get("cast", []):
                if current_day in blocked.get(actor, []):
                    score -= 8.0
            cumulative += sc.get("page_duration", 1)
            if cumulative >= pages_per_day:
                cumulative = 0
                current_day += 1
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

    def explain_schedule(self, ordered_indices) -> list[str]:
        explanations, loc_groups = [], {}
        for idx in ordered_indices:
            loc = self.scenes[idx].get("location", "?")
            loc_groups.setdefault(loc, []).append(idx)
        for loc, idxs in loc_groups.items():
            if len(idxs) > 1:
                explanations.append(
                    f"📍 {len(idxs)} scene consecutive a {loc} → risparmio logistico")
        ext_day = sum(
            1 for i in ordered_indices
            if self.scenes[i].get("int_ext") == "EXT"
            and self.scenes[i].get("day_night") == "GIORNO"
        )
        if ext_day > 0:
            explanations.append(
                f"☀️ {ext_day} scene EXT/GIORNO raggruppate per luce naturale")
        return explanations or ["Schedulazione ottimizzata completata."]
