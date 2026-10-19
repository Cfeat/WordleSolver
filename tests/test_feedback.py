"""Basic correctness checks for feedback and hard mode."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wordle_solver.feedback import colors_to_pattern, pattern_for, pattern_to_colors
from wordle_solver.hard_mode import is_hard_valid


def test_all_green():
    assert pattern_to_colors(pattern_for("crane", "crane")) == "ggggg"


def test_duplicates():
    # guess abbey vs abate -> a g, b y?, ...
    # abate: a,b,a,t,e
    # abbey: a,b,b,e,y
    # a green, b green, b gray (only one b in answer), e yellow, y gray
    assert pattern_to_colors(pattern_for("abbey", "abate")) == "ggbyb"


def test_parse_feedback():
    assert pattern_to_colors(colors_to_pattern("gybbb")) == "gybbb"
    assert pattern_to_colors(colors_to_pattern("ggggg")) == "ggggg"


def test_hard_mode_green():
    p = pattern_for("crane", "crate")  # gggbg — must keep C,R,A,_,E
    assert pattern_to_colors(p) == "gggbg"
    assert is_hard_valid("crave", [("crane", p)])
    assert not is_hard_valid("trace", [("crane", p)])
    assert not is_hard_valid("cramp", [("crane", p)])  # missing final E


if __name__ == "__main__":
    test_all_green()
    test_duplicates()
    test_parse_feedback()
    test_hard_mode_green()
    print("ok")
