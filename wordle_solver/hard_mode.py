"""NYT Hard Mode: greens stay fixed; hinted letters must be reused."""

from __future__ import annotations

from .feedback import GREEN, YELLOW


def _digits(pattern: int) -> list[int]:
    return [(pattern // (3**i)) % 3 for i in range(4, -1, -1)]


def is_hard_valid(guess: str, history: list[tuple[str, int]]) -> bool:
    """
    True if `guess` respects Hard Mode given prior (guess, pattern) pairs.

    NYT rules:
    - Green letters must remain in those positions.
    - Every green/yellow letter from a prior guess must appear at least as many
      times as it was marked green or yellow (duplicate-aware).
    Gray letters may still be used.
    """
    guess = guess.lower()
    for prev, pattern in history:
        prev = prev.lower()
        marks = _digits(pattern)

        for i, m in enumerate(marks):
            if m == GREEN and guess[i] != prev[i]:
                return False

        required: dict[str, int] = {}
        for i, m in enumerate(marks):
            if m in (GREEN, YELLOW):
                required[prev[i]] = required.get(prev[i], 0) + 1

        have: dict[str, int] = {}
        for ch in guess:
            have[ch] = have.get(ch, 0) + 1

        for ch, n in required.items():
            if have.get(ch, 0) < n:
                return False
    return True


def filter_hard(guesses: list[str], history: list[tuple[str, int]]) -> list[str]:
    if not history:
        return list(guesses)
    return [g for g in guesses if is_hard_valid(g, history)]
