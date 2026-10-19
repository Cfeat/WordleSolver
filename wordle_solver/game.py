"""Simulate Wordle games and measure average guess count."""

from __future__ import annotations

from dataclasses import dataclass, field

from .feedback import pattern_for, pattern_to_colors
from .solver import Solver
from .words import load_answers


@dataclass
class GameResult:
    answer: str
    guesses: list[str] = field(default_factory=list)
    won: bool = False

    @property
    def steps(self) -> int:
        return len(self.guesses)


def play_one(
    answer: str,
    hard_mode: bool = False,
    max_guesses: int = 6,
    verbose: bool = False,
) -> GameResult:
    solver = Solver(hard_mode=hard_mode)
    result = GameResult(answer=answer)

    for _ in range(max_guesses):
        guess = solver.best_guess()
        result.guesses.append(guess)
        pattern = pattern_for(guess, answer)
        if verbose:
            print(f"  {guess} -> {pattern_to_colors(pattern)}")
        if guess == answer:
            result.won = True
            break
        solver.apply(guess, pattern)
        if not solver.candidates:
            break
    return result


def simulate(
    hard_mode: bool = False,
    limit: int | None = None,
    max_guesses: int = 6,
    progress_every: int = 100,
) -> dict:
    answers = list(load_answers())
    if limit is not None:
        answers = answers[:limit]

    # Warm opener cache for normal mode
    if not hard_mode:
        s = Solver(hard_mode=False)
        if s._cached_opener() is None:
            # Use answer-only pool for faster first-time cache; still strong.
            s.compute_and_cache_opener(use_full_pool=False)

    results: list[GameResult] = []
    for i, answer in enumerate(answers, 1):
        results.append(play_one(answer, hard_mode=hard_mode, max_guesses=max_guesses))
        if progress_every and i % progress_every == 0:
            won = sum(1 for r in results if r.won)
            avg = sum(r.steps for r in results) / len(results)
            print(
                f"  [{i}/{len(answers)}] 胜率={won/i:.1%} 平均步数={avg:.3f}",
                flush=True,
            )

    won_n = sum(1 for r in results if r.won)
    steps = [r.steps for r in results]
    dist = {k: 0 for k in range(1, max_guesses + 1)}
    fails = 0
    for r in results:
        if r.won:
            dist[r.steps] = dist.get(r.steps, 0) + 1
        else:
            fails += 1

    return {
        "n": len(results),
        "wins": won_n,
        "win_rate": won_n / len(results) if results else 0.0,
        "avg_steps": sum(steps) / len(steps) if steps else 0.0,
        "avg_steps_won": (
            sum(r.steps for r in results if r.won) / won_n if won_n else 0.0
        ),
        "max_steps": max(steps) if steps else 0,
        "distribution": dist,
        "fails": fails,
        "hard_mode": hard_mode,
        "fail_words": [r.answer for r in results if not r.won],
    }
