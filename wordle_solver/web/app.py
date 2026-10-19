"""Flask app: Wordle board helper + simulation charts."""

from __future__ import annotations

import secrets
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session

from wordle_solver.challenge import ChallengeGame
from wordle_solver.feedback import colors_to_pattern, pattern_to_colors
from wordle_solver.game import simulate
from wordle_solver.hard_mode import is_hard_valid
from wordle_solver.solver import Solver

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).parent / "static"

# In-memory sessions: sid -> Solver (helper mode)
_SESSIONS: dict[str, Solver] = {}
# Challenge mode: gid -> ChallengeGame
_GAMES: dict[str, ChallengeGame] = {}


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(TEMPLATES),
        static_folder=str(STATIC),
    )
    app.secret_key = secrets.token_hex(16)

    def _solver() -> Solver:
        sid = session.get("sid")
        if not sid or sid not in _SESSIONS:
            sid = uuid.uuid4().hex
            session["sid"] = sid
            hard = bool(session.get("hard", False))
            _SESSIONS[sid] = Solver(hard_mode=hard)
            _ensure_opener(_SESSIONS[sid])
        return _SESSIONS[sid]

    def _ensure_opener(solver: Solver) -> None:
        if solver._cached_opener() is None:
            solver.compute_and_cache_opener(use_full_pool=False)

    def _snapshot(solver: Solver) -> dict:
        recs = solver.recommend(top_k=8)
        remaining = solver.remaining()
        history = [
            {
                "guess": g.upper(),
                "colors": pattern_to_colors(p),
            }
            for g, p in solver.history
        ]
        solved = len(remaining) == 1 and (
            not history
            or history[-1]["colors"] == "ggggg"
            or remaining[0] == history[-1]["guess"].lower()
        )
        if history and history[-1]["colors"] == "ggggg":
            solved = True
            answer = history[-1]["guess"].lower()
        elif len(remaining) == 1:
            answer = remaining[0]
        else:
            answer = None

        return {
            "hard": solver.hard_mode,
            "remaining": len(remaining),
            "candidates": remaining[:40],
            "candidates_truncated": len(remaining) > 40,
            "history": history,
            "recommendations": [
                {
                    "word": w.upper(),
                    "entropy": round(ent, 4),
                    "in_answers": in_set,
                }
                for w, ent, in_set in recs
            ],
            "solved": solved and answer is not None,
            "answer": answer.upper() if answer else None,
            "turn": len(history) + (0 if solved else 1),
        }

    @app.get("/")
    def index():
        _solver()
        return render_template("index.html")

    @app.post("/api/new")
    def api_new():
        data = request.get_json(silent=True) or {}
        hard = bool(data.get("hard", False))
        session["hard"] = hard
        sid = uuid.uuid4().hex
        session["sid"] = sid
        solver = Solver(hard_mode=hard)
        _ensure_opener(solver)
        _SESSIONS[sid] = solver
        return jsonify(_snapshot(solver))

    @app.get("/api/state")
    def api_state():
        return jsonify(_snapshot(_solver()))

    @app.post("/api/guess")
    def api_guess():
        solver = _solver()
        data = request.get_json(force=True)
        guess = str(data.get("guess", "")).strip().lower()
        colors = str(data.get("colors", "")).strip().lower()

        if len(guess) != 5 or not guess.isalpha():
            return jsonify({"error": "猜测必须是 5 个英文字母"}), 400
        try:
            pattern = colors_to_pattern(colors)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        if solver.hard_mode and solver.history:
            if not is_hard_valid(guess, solver.history):
                return jsonify({"error": "不符合 Hard Mode：须使用已揭示的绿/黄线索"}), 400

        solver.apply(guess, pattern)
        return jsonify(_snapshot(solver))

    @app.post("/api/undo")
    def api_undo():
        solver = _solver()
        if not solver.history:
            return jsonify(_snapshot(solver))
        hist = solver.history[:-1]
        hard = solver.hard_mode
        solver.reset()
        solver.hard_mode = hard
        for g, p in hist:
            solver.apply(g, p)
        return jsonify(_snapshot(solver))

    @app.post("/api/simulate")
    def api_simulate():
        data = request.get_json(force=True)
        hard = bool(data.get("hard", False))
        limit = data.get("limit")
        if limit is not None:
            limit = int(limit)
            if limit < 1:
                return jsonify({"error": "limit 至少为 1"}), 400
            if limit > 2309:
                limit = 2309
        stats = simulate(
            hard_mode=hard,
            limit=limit,
            progress_every=0,
        )
        return jsonify(
            {
                "n": stats["n"],
                "wins": stats["wins"],
                "win_rate": stats["win_rate"],
                "avg_steps": stats["avg_steps"],
                "avg_steps_won": stats["avg_steps_won"],
                "max_steps": stats["max_steps"],
                "distribution": {
                    str(k): v for k, v in stats["distribution"].items()
                },
                "fails": stats["fails"],
                "hard_mode": stats["hard_mode"],
            }
        )

    def _game() -> ChallengeGame | None:
        gid = session.get("gid")
        if not gid:
            return None
        return _GAMES.get(gid)

    def _require_game() -> tuple[ChallengeGame | None, tuple | None]:
        game = _game()
        if game is None:
            return None, (jsonify({"error": "还没有对局，请先抽题"}), 400)
        return game, None

    @app.post("/api/game/new")
    def api_game_new():
        data = request.get_json(silent=True) or {}
        hard = bool(data.get("hard", False))
        # Ensure opener cache exists once, before creating the game (avoids long stall in draw).
        warm = Solver(hard_mode=False)
        _ensure_opener(warm)
        gid = uuid.uuid4().hex
        session["gid"] = gid
        game = ChallengeGame.draw(hard_mode=hard)
        _GAMES[gid] = game
        return jsonify(game.snapshot())

    @app.get("/api/game/state")
    def api_game_state():
        game = _game()
        if game is None:
            return jsonify({"active": False})
        snap = game.snapshot()
        snap["active"] = True
        return jsonify(snap)

    @app.post("/api/game/guess")
    def api_game_guess():
        game, err = _require_game()
        if err:
            return err
        data = request.get_json(force=True)
        result = game.submit(str(data.get("guess", "")))
        if "error" in result:
            return jsonify(result), 400
        return jsonify(game.snapshot())

    @app.post("/api/game/auto-step")
    def api_game_auto_step():
        game, err = _require_game()
        if err:
            return err
        result = game.auto_step()
        if "error" in result:
            return jsonify(result), 400
        return jsonify(game.snapshot())

    @app.post("/api/game/auto-all")
    def api_game_auto_all():
        game, err = _require_game()
        if err:
            return err
        result = game.auto_all()
        if "error" in result:
            return jsonify(result), 400
        return jsonify(game.snapshot())

    return app


def run(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    app = create_app()
    print(f"WordleSolver 可视化: http://{host}:{port}")
    # threaded=True: page-load helper ranking must not block 题库抽题.
    app.run(host=host, port=port, debug=debug, threaded=True)
