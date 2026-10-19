"""Load Wordle answer and guess dictionaries."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS_DIR = ROOT / "words"


def _read_words(path: Path) -> tuple[str, ...]:
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        w = line.strip().lower()
        if len(w) == 5 and w.isalpha():
            words.append(w)
    return tuple(words)


@lru_cache(maxsize=1)
def load_answers() -> tuple[str, ...]:
    return _read_words(WORDS_DIR / "answers.txt")


@lru_cache(maxsize=1)
def load_guesses() -> tuple[str, ...]:
    """All valid guess words (includes answers)."""
    guesses = list(_read_words(WORDS_DIR / "guesses.txt"))
    answers = load_answers()
    # ensure every answer is guessable
    seen = set(guesses)
    for a in answers:
        if a not in seen:
            guesses.append(a)
            seen.add(a)
    return tuple(guesses)
