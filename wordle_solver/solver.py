"""Entropy-maximizing Wordle solver (minimize average guesses)."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from .feedback import matches, pattern_for
from .hard_mode import filter_hard
from .words import ROOT, load_answers, load_guesses

CACHE_PATH = ROOT / "words" / "opener_cache.json"

# Only score the full allowed-guess list when few candidates remain.
# Above this, scoring remaining answers is nearly as good and much faster.
FULL_POOL_LIMIT = 60


class Solver:
    def __init__(self, hard_mode: bool = False) -> None:
        self.hard_mode = hard_mode
        self.answers = list(load_answers())
        self.all_guesses = list(load_guesses())
        self.candidates = list(self.answers)
        self.history: list[tuple[str, int]] = []
        self._answer_set = set(self.answers)

    def reset(self) -> None:
        self.candidates = list(self.answers)
        self.history = []

    def apply(self, guess: str, pattern: int) -> None:
        guess = guess.lower()
        self.history.append((guess, pattern))
        self.candidates = [
            w for w in self.candidates if matches(w, guess, pattern)
        ]

    def remaining(self) -> list[str]:
        return list(self.candidates)

    def recommend(self, top_k: int = 5) -> list[tuple[str, float, bool]]:
        """
        Return top guesses as (word, entropy, is_possible_answer).

        First move uses a cached opener when available.
        """
        n = len(self.candidates)
        if n == 0:
            return []
        if n == 1:
            w = self.candidates[0]
            return [(w, 0.0, True)]

        # First move is identical with/without Hard Mode (no constraints yet).
        if not self.history:
            opener = self._cached_opener()
            if opener and top_k <= 1:
                ent = self._entropy(opener, self.candidates)
                return [(opener, ent, opener in self._answer_set)]
            # Rank answer pool for a fast top-K list (full guess pool is slow).
            scored = self._rank(list(self.answers), self.candidates)
            if opener:
                scored = [s for s in scored if s[0] != opener]
                ent = self._entropy(opener, self.candidates)
                scored.insert(0, (opener, ent, opener in self._answer_set))
            return scored[:top_k]

        pool = self._guess_pool()
        scored = self._rank(pool, self.candidates)
        return scored[:top_k]

    def best_guess(self) -> str:
        recs = self.recommend(top_k=1)
        if not recs:
            raise RuntimeError("没有剩余候选词")
        return recs[0][0]

    def _guess_pool(self) -> list[str]:
        n = len(self.candidates)
        if n <= FULL_POOL_LIMIT:
            pool = list(self.all_guesses)
        else:
            # large search space: prefer possible answers; still near-optimal
            pool = list(self.candidates)
        if self.hard_mode:
            pool = filter_hard(pool, self.history)
            # hard mode may exclude all non-candidates; always keep candidates
            if not pool:
                pool = filter_hard(list(self.candidates), self.history)
        # ensure remaining answers are always considered
        seen = set(pool)
        extra = list(self.candidates)
        if self.hard_mode:
            extra = filter_hard(extra, self.history)
        for c in extra:
            if c not in seen:
                pool.append(c)
                seen.add(c)
        return pool

    def _rank(
        self, pool: list[str], candidates: list[str]
    ) -> list[tuple[str, float, bool]]:
        cand_set = set(candidates)
        scored: list[tuple[float, float, str]] = []
        for g in pool:
            ent = self._entropy(g, candidates)
            # Prefer possible answers on near-ties (can win this turn).
            in_set = 1.0 if g in cand_set else 0.0
            # Prefer lower expected remaining as secondary signal baked into sort
            # via entropy first, then in_set.
            scored.append((ent, in_set, g))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [(g, ent, bool(ins)) for ent, ins, g in scored]

    @staticmethod
    def _entropy(guess: str, candidates: list[str]) -> float:
        counts = Counter(pattern_for(guess, c) for c in candidates)
        n = len(candidates)
        h = 0.0
        for c in counts.values():
            p = c / n
            h -= p * math.log2(p)
        return h

    def _cached_opener(self) -> str | None:
        if CACHE_PATH.exists():
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            return data.get("opener")
        return None

    def compute_and_cache_opener(self, use_full_pool: bool = True) -> str:
        """Compute best first guess and save to cache (slow once)."""
        pool = list(self.all_guesses) if use_full_pool else list(self.answers)
        print(f"计算最佳开局词（候选答案 {len(self.answers)}，猜测池 {len(pool)}）…")
        best = self._rank(pool, self.answers)[0]
        word, ent, in_set = best
        CACHE_PATH.write_text(
            json.dumps(
                {
                    "opener": word,
                    "entropy": ent,
                    "is_answer": in_set,
                    "answer_count": len(self.answers),
                    "guess_pool": len(pool),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"最佳开局: {word}  (熵={ent:.4f}, 是答案词={in_set})")
        return word


def filter_candidates(
    candidates: list[str], guess: str, pattern: int
) -> list[str]:
    return [w for w in candidates if matches(w, guess, pattern)]
