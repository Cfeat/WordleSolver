"""Random-answer challenge: human play or solver auto-play."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .feedback import pattern_for, pattern_to_colors
from .hard_mode import is_hard_valid
from .solver import Solver
from .words import load_answers, load_guesses

MAX_GUESSES = 6
_GUESS_SET: set[str] | None = None


def _allowed_guesses() -> set[str]:
    global _GUESS_SET
    if _GUESS_SET is None:
        _GUESS_SET = set(load_guesses())
    return _GUESS_SET


@dataclass
class ChallengeGame:
    answer: str
    hard_mode: bool = False
    max_guesses: int = MAX_GUESSES
    guesses: list[str] = field(default_factory=list)
    patterns: list[int] = field(default_factory=list)
    solver: Solver = field(init=False)

    def __post_init__(self) -> None:
        self.answer = self.answer.lower()
        self.solver = Solver(hard_mode=self.hard_mode)
        if self.solver._cached_opener() is None:
            self.solver.compute_and_cache_opener(use_full_pool=False)

    @classmethod
    def draw(cls, hard_mode: bool = False, seed: int | None = None) -> ChallengeGame:
        rng = random.Random(seed)
        answer = rng.choice(load_answers())
        return cls(answer=answer, hard_mode=hard_mode)

    @property
    def won(self) -> bool:
        return bool(self.guesses) and self.guesses[-1] == self.answer

    @property
    def lost(self) -> bool:
        return (not self.won) and len(self.guesses) >= self.max_guesses

    @property
    def finished(self) -> bool:
        return self.won or self.lost

    def submit(self, guess: str) -> dict:
        if self.finished:
            return {"error": "本局已结束，请换一题"}
        guess = guess.strip().lower()
        if len(guess) != 5 or not guess.isalpha():
            return {"error": "猜测必须是 5 个英文字母"}
        if guess not in _allowed_guesses():
            return {"error": f"「{guess.upper()}」不在合法词表中"}
        if self.hard_mode and self.solver.history:
            if not is_hard_valid(guess, self.solver.history):
                return {"error": "不符合 Hard Mode：须使用已揭示的绿/黄线索"}

        pattern = pattern_for(guess, self.answer)
        self.guesses.append(guess)
        self.patterns.append(pattern)
        self.solver.apply(guess, pattern)
        return {"ok": True}

    def auto_step(self) -> dict:
        if self.finished:
            return {"error": "本局已结束，请换一题"}
        guess = self.solver.best_guess()
        return self.submit(guess)

    def auto_all(self) -> dict:
        steps = 0
        while not self.finished:
            result = self.auto_step()
            if "error" in result:
                return result
            steps += 1
        return {"ok": True, "steps": steps}

    def snapshot(self, reveal: bool = False) -> dict:
        history = [
            {"guess": g.upper(), "colors": pattern_to_colors(p)}
            for g, p in zip(self.guesses, self.patterns)
        ]
        recs = []
        if not self.finished:
            # First move: top_k=1 uses opener cache (instant).
            # Later: top_k=5 is fine with a smaller candidate set.
            top_k = 1 if not self.solver.history else 5
            recs = [
                {
                    "word": w.upper(),
                    "entropy": round(ent, 4),
                    "in_answers": in_set,
                }
                for w, ent, in_set in self.solver.recommend(top_k=top_k)
            ]

        show_answer = reveal or self.finished
        return {
            "hard": self.hard_mode,
            "history": history,
            "guesses_used": len(self.guesses),
            "guesses_left": max(0, self.max_guesses - len(self.guesses)),
            "max_guesses": self.max_guesses,
            "won": self.won,
            "lost": self.lost,
            "finished": self.finished,
            "answer": self.answer.upper() if show_answer else None,
            "recommendations": recs,
            "remaining": len(self.solver.candidates),
            "turn": len(self.guesses) + (0 if self.finished else 1),
        }
