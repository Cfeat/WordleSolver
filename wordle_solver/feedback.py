"""Wordle color feedback (handles duplicate letters correctly)."""

from __future__ import annotations

# Pattern encoded as base-3 int: 0=gray, 1=yellow, 2=green. Range 0..242.
GRAY, YELLOW, GREEN = 0, 1, 2


def pattern_for(guess: str, answer: str) -> int:
    """Return feedback pattern of `guess` against `answer` as a base-3 int."""
    g = guess.lower()
    a = answer.lower()
    marks = [GRAY] * 5
    remaining = [0] * 26

    for i in range(5):
        if g[i] == a[i]:
            marks[i] = GREEN
        else:
            remaining[ord(a[i]) - 97] += 1

    for i in range(5):
        if marks[i] == GREEN:
            continue
        idx = ord(g[i]) - 97
        if remaining[idx] > 0:
            marks[i] = YELLOW
            remaining[idx] -= 1

    # encode base-3
    code = 0
    for m in marks:
        code = code * 3 + m
    return code


def pattern_to_colors(pattern: int) -> str:
    """Convert pattern int to a 5-char string of g/y/b (green/yellow/black)."""
    chars = []
    for i in range(4, -1, -1):
        digit = (pattern // (3**i)) % 3
        chars.append("byg"[digit])  # 0=b, 1=y, 2=g
    return "".join(chars)


def colors_to_pattern(colors: str) -> int:
    """Parse user feedback like 'gybbY' or '🟩🟨⬛⬛⬛' into a pattern int."""
    colors = colors.strip().lower().replace(" ", "")
    mapping = {
        "b": GRAY,
        "x": GRAY,
        "0": GRAY,
        "-": GRAY,
        "y": YELLOW,
        "1": YELLOW,
        "g": GREEN,
        "2": GREEN,
        # emoji
        "⬛": GRAY,
        "⬜": GRAY,
        "🟨": YELLOW,
        "🟩": GREEN,
    }
    # emoji may be multi-codepoint; try sequential parse
    marks: list[int] = []
    i = 0
    while i < len(colors) and len(marks) < 5:
        ch = colors[i]
        if ch in mapping:
            marks.append(mapping[ch])
            i += 1
            continue
        # try 2-char emoji slices already handled by single char above for common ones
        raise ValueError(
            f"无法解析反馈 '{colors}'。请使用 g/y/b，例如 gybby（绿/黄/灰）。"
        )
    if len(marks) != 5:
        raise ValueError(f"反馈必须是 5 个字符，收到 {len(marks)}：'{colors}'")
    code = 0
    for m in marks:
        code = code * 3 + m
    return code


def matches(word: str, guess: str, pattern: int) -> bool:
    """True if `word` would produce `pattern` when guessed as `guess`."""
    return pattern_for(guess, word) == pattern
