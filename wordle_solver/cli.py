"""Command-line interface: interactive helper + simulation."""

from __future__ import annotations

import argparse
import sys

from .feedback import colors_to_pattern, pattern_to_colors
from .game import play_one, simulate
from .solver import Solver
from .words import load_answers


def cmd_play(args: argparse.Namespace) -> int:
    solver = Solver(hard_mode=args.hard)
    print("Wordle 辅助猜词")
    print("反馈格式: g=绿 y=黄 b=灰，例如 gybby")
    print("命令: quit 退出 | undo 撤销 | remaining 查看候选 | hint 仅看推荐")
    if args.hard:
        print("Hard Mode: 已开启")
    print()

    if solver._cached_opener() is None and not args.hard:
        print("首次运行：用答案词表预计算开局词（约几秒）…")
        solver.compute_and_cache_opener(use_full_pool=False)
        print()

    turn = 1
    while True:
        n = len(solver.candidates)
        if n == 0:
            print("没有符合条件的候选词，请检查反馈或 undo。")
            break
        if n == 1:
            print(f"答案应为: {solver.candidates[0].upper()}")
            break

        recs = solver.recommend(top_k=args.top)
        print(f"—— 第 {turn} 步 | 剩余候选 {n} ——")
        for i, (word, ent, in_set) in enumerate(recs, 1):
            tag = "答案池" if in_set else "探测词"
            print(f"  {i}. {word.upper():5}  熵={ent:.3f}  [{tag}]")

        raw = input("输入猜测与反馈（如 slate gybbb），或命令: ").strip()
        if not raw:
            continue
        low = raw.lower()
        if low in ("q", "quit", "exit"):
            return 0
        if low == "undo":
            if not solver.history:
                print("没有可撤销的步骤。")
                continue
            hist = solver.history[:-1]
            solver.reset()
            for g, p in hist:
                solver.apply(g, p)
            turn = max(1, turn - 1)
            print("已撤销一步。")
            continue
        if low in ("remaining", "list", "ls"):
            words = solver.remaining()
            show = words[:50]
            print(", ".join(show) + (" …" if len(words) > 50 else ""))
            continue
        if low == "hint":
            continue

        parts = raw.split()
        if len(parts) == 1 and len(parts[0]) == 5 and parts[0].isalpha():
            guess = parts[0].lower()
            fb = input(f"  {guess.upper()} 的反馈 (gybbb): ").strip()
        elif len(parts) >= 2:
            guess, fb = parts[0].lower(), parts[1]
        else:
            print("格式: <猜测> <反馈>，例如 crane ybgbb")
            continue

        if len(guess) != 5 or not guess.isalpha():
            print("猜测必须是 5 个字母。")
            continue
        try:
            pattern = colors_to_pattern(fb)
        except ValueError as e:
            print(e)
            continue

        if args.hard and solver.history:
            from .hard_mode import is_hard_valid

            if not is_hard_valid(guess, solver.history):
                print("该猜测不符合 Hard Mode 约束，请换词。")
                continue

        solver.apply(guess, pattern)
        print(f"已记录: {guess.upper()} -> {pattern_to_colors(pattern)}")
        turn += 1

        if pattern_to_colors(pattern) == "ggggg":
            print(f"完成！共用 {turn - 1} 步。")
            return 0
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    print(
        f"模拟 {'Hard Mode' if args.hard else '普通模式'}，"
        f"词数={args.limit or '全部'} …"
    )
    stats = simulate(
        hard_mode=args.hard,
        limit=args.limit,
        max_guesses=args.max_guesses,
        progress_every=args.progress,
    )
    print()
    print("=== 模拟结果 ===")
    print(f"局数:       {stats['n']}")
    print(f"胜率:       {stats['win_rate']:.2%}  ({stats['wins']}/{stats['n']})")
    print(f"平均步数:   {stats['avg_steps']:.4f}  (含失败按实际步数)")
    print(f"获胜均步:   {stats['avg_steps_won']:.4f}")
    print(f"最大步数:   {stats['max_steps']}")
    print("步数分布:")
    for k, v in sorted(stats["distribution"].items()):
        print(f"  {k} 步: {v}")
    print(f"失败:       {stats['fails']}")
    if stats["fail_words"] and len(stats["fail_words"]) <= 30:
        print("失败单词:", ", ".join(stats["fail_words"]))
    elif stats["fail_words"]:
        print(
            "失败单词(前30):",
            ", ".join(stats["fail_words"][:30]),
            f"… 共 {len(stats['fail_words'])}",
        )
    return 0


def cmd_auto(args: argparse.Namespace) -> int:
    answer = args.answer.lower()
    if answer not in set(load_answers()):
        print(f"警告: '{answer}' 不在答案词表中，仍继续模拟。")
    result = play_one(answer, hard_mode=args.hard, verbose=True)
    status = "成功" if result.won else "失败"
    print(f"{status}: {answer.upper()} 用了 {result.steps} 步 -> {result.guesses}")
    return 0 if result.won else 1


def cmd_opener(args: argparse.Namespace) -> int:
    solver = Solver(hard_mode=False)
    word = solver.compute_and_cache_opener(use_full_pool=not args.fast)
    print(f"已缓存开局词: {word.upper()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wordle-solver",
        description="Wordle 自动求解 / 辅助猜词（熵最大化，优先平均步数）",
    )
    sub = p.add_subparsers(dest="command", required=True)

    play = sub.add_parser("play", help="交互式辅助猜词")
    play.add_argument("--hard", action="store_true", help="启用 Hard Mode")
    play.add_argument("--top", type=int, default=5, help="显示前 K 个推荐")
    play.set_defaults(func=cmd_play)

    sim = sub.add_parser("simulate", help="对答案词表做全量/抽样模拟")
    sim.add_argument("--hard", action="store_true", help="启用 Hard Mode")
    sim.add_argument("--limit", type=int, default=None, help="只测前 N 个答案")
    sim.add_argument("--max-guesses", type=int, default=6)
    sim.add_argument("--progress", type=int, default=100)
    sim.set_defaults(func=cmd_simulate)

    auto = sub.add_parser("auto", help="自动求解一个指定答案")
    auto.add_argument("answer", help="目标单词")
    auto.add_argument("--hard", action="store_true")
    auto.set_defaults(func=cmd_auto)

    opener = sub.add_parser("opener", help="预计算并缓存最佳开局词")
    opener.add_argument(
        "--fast",
        action="store_true",
        help="只用答案词表作猜测池（更快，略次优）",
    )
    opener.set_defaults(func=cmd_opener)

    return p


def main(argv: list[str] | None = None) -> int:
    # Windows consoles often default to a legacy code page.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
