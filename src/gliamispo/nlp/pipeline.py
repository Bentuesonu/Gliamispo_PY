import asyncio


class NLPPipelineCoordinator:
    def __init__(self, ner, vocabulary, pattern_matcher,
                 context_engine, normalizer):
        self._ner = ner
        self._vocab = vocabulary
        self._patterns = pattern_matcher
        self._context = context_engine
        self._normalizer = normalizer
        self._norm_lock = asyncio.Lock()

    async def process_scene(self, scene_text, scene_context,
                            known_chars=None):
        # Step 1: 3 estrazioni in parallelo (equivale a async let triplo)
        ner_task = asyncio.create_task(
            self._ner.extract(scene_text, known_chars=known_chars)
        )
        vocab_task = asyncio.create_task(
            self._vocab.match(scene_text)
        )
        pattern_task = asyncio.create_task(
            self._patterns.find(scene_text)
        )
        ner_results, vocab_results, pattern_results = await asyncio.gather(
            ner_task, vocab_task, pattern_task
        )

        # Step 2: normalizzazione serializzata (MainActor → Lock)
        merged = ner_results + vocab_results + pattern_results
        async with self._norm_lock:
            normalized = [
                self._normalizer.normalize(e) for e in merged
            ]

        # Step 3: conflict resolution sincrono
        resolved = self._resolve_conflicts(normalized)

        # Step 4: context enhancement
        enhanced = await self._context.enhance(resolved, scene_context)

        # Step 5: dedup + sort by confidence
        seen = set()
        deduped = []
        for e in enhanced:
            key = (e.category, e.element_name)
            if key not in seen:
                seen.add(key)
                deduped.append(e)
        deduped.sort(key=lambda e: e.ai_confidence or 0, reverse=True)
        return deduped

    def _resolve_conflicts(self, elements):
        by_key = {}
        for e in elements:
            key = (e.element_name.lower(), e.category)
            if key not in by_key or \
               (e.ai_confidence or 0) > (by_key[key].ai_confidence or 0):
                by_key[key] = e
        return list(by_key.values())
