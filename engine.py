# engine.py - Clean Python API for the Sunfish chess engine
# Replaces the UCI stdin/stdout wrapper with direct function calls.

import time
import logging
from threading import Event

import sunfish
import tools.uci as uci
from tools.uci import from_fen, can_kill_king, render_move, parse_move, pv

# Set the global sunfish reference that tools/uci.py helpers depend on.
# Normally set by uci.run(), but we bypass run() entirely.
uci.sunfish = sunfish

logger = logging.getLogger(__name__)


def build_history(fen, moves_str=""):
    """Parse a FEN string and optional move history into a position history list.

    Mirrors the logic from tools/uci.py run() lines 400-414.
    """
    fen_parts = fen.split()
    pos = from_fen(*fen_parts[:6])
    color = fen_parts[1]

    if color == 'b':
        hist = [pos.rotate(), pos]
    else:
        hist = [pos]

    if moves_str and moves_str.strip():
        for move_str in moves_str.strip().split():
            parsed_move = parse_move(move_str, white_pov=(len(hist) % 2 == 1))
            hist.append(hist[-1].move(parsed_move))

    return hist


def is_check(fen):
    """Check if the active player is currently in check.

    Matches the behavior of server.py /ischeck endpoint (line 329).
    """
    hist = build_history(fen)
    position = hist[-1]
    return can_kill_king(position)


def get_legal_moves(fen):
    """Get all legal moves for the position described by the FEN.

    Returns dict with "moves" and "check" keys matching /getmoves response format.
    Mirrors server.py lines 135-167.
    """
    fen_parts = fen.split()
    side_to_move = fen_parts[1]

    hist = build_history(fen)
    position = hist[-1]

    player_pieces = set("PNBRQK")
    moves = {}
    for i, piece in enumerate(position.board):
        if piece in player_pieces:
            legal = position.get_legal_moves(square=i)
            if legal:
                rendered = [
                    sunfish.render(m.i) + sunfish.render(m.j) + m.prom.lower()
                    for m in legal
                ]
                if side_to_move == "b":
                    flipped_square = sunfish.render(119 - i)
                    flipped_moves = [
                        sunfish.render(119 - m.i) + sunfish.render(119 - m.j) + m.prom.lower()
                        for m in legal
                    ]
                    moves[flipped_square] = flipped_moves
                else:
                    moves[sunfish.render(i)] = rendered

    rotated_pos = position.rotate()
    check = can_kill_king(rotated_pos)

    return {"moves": moves, "check": check}


def _search_best_moves(searcher, hist, max_movetime, max_depth, top_n, ignore_squares):
    """Core search logic. Adapted from tools/uci.py go_loop() lines 44-263.

    Returns dict instead of printing to stdout / calling callbacks.
    """
    start = time.time()
    final_depth = 1

    # 1 - Main iterative deepening search
    for depth, gamma, score, move in searcher.search(hist):
        final_depth = depth
        if depth - 1 >= max_depth:
            break
        elapsed = time.time() - start
        if score >= gamma:
            best_move = render_move(move, white_pov=len(hist) % 2 == 1)
        if depth > 1:
            time_budget = max_movetime * 2 / 3
            if max_movetime > 0 and elapsed > time_budget:
                break

    # 2 - Get all legal moves
    pos = hist[-1]
    move_list = list(pos.gen_moves())
    legal_moves = [m for m in move_list if not can_kill_king(pos.move(m))]

    # Filter out moves from ignored squares
    if ignore_squares and len(ignore_squares) > 0:
        white_pov = len(hist) % 2 == 1
        ignored_indices = set()
        for square_str in ignore_squares:
            try:
                idx = sunfish.parse(square_str)
                if not white_pov:
                    idx = 119 - idx
                ignored_indices.add(idx)
            except Exception:
                pass
        legal_moves = [m for m in legal_moves if m.i not in ignored_indices]

    if not legal_moves:
        return {"bestmove": "(none)", "scored_moves": [], "depth_reached": final_depth}

    # 3 - Evaluate moves based on top_n parameter
    scored_moves = []

    # FAST PATH: top_n=1
    if top_n == 1:
        best_move_obj = searcher.tp_move.get(hist[-1])
        if best_move_obj:
            if best_move_obj in legal_moves:
                move_str = render_move(best_move_obj, len(hist) % 2 == 1)
                scored_moves = [(move_str, 0)]
            elif len(legal_moves) > 0:
                m = legal_moves[0]
                move_str = render_move(m, len(hist) % 2 == 1)
                scored_moves = [(move_str, 0)]
        elif len(legal_moves) > 0:
            m = legal_moves[0]
            move_str = render_move(m, len(hist) % 2 == 1)
            scored_moves = [(move_str, 0)]

    # STANDARD PATH: Multi-move evaluation using TT + shallow search
    else:
        # Step 3a: Quick screening with TT/static eval
        quick_scored = []
        for m in legal_moves:
            new_pos = pos.move(m)
            move_str = render_move(m, len(hist) % 2 == 1)
            score = None
            for check_depth in range(final_depth - 1, 0, -1):
                entry = searcher.tp_score.get((new_pos, check_depth, True), None)
                if entry is not None:
                    bound_width = entry.upper - entry.lower
                    if bound_width < 1000:
                        score = -((entry.lower + entry.upper) // 2)
                        break
            if score is None:
                score = pos.value(m)
            quick_scored.append((m, move_str, score, new_pos))

        # Step 3b: Sort and select top candidates
        quick_scored.sort(key=lambda x: x[2], reverse=True)
        buffer_size = min(5, max(2, top_n // 2))
        top_candidates = quick_scored[:min(top_n + buffer_size, len(quick_scored))]

        # Step 3c: Deep evaluation for top candidates
        shallow_depth = max(3, final_depth - 3)
        for m, move_str, quick_score, new_pos in top_candidates:
            score = None
            for check_depth in range(final_depth - 1, max(0, final_depth - 3), -1):
                entry = searcher.tp_score.get((new_pos, check_depth, True), None)
                if entry is not None:
                    bound_width = entry.upper - entry.lower
                    if bound_width < 1000:
                        score = -((entry.lower + entry.upper) // 2)
                        break
            if score is None and shallow_depth > 0:
                try:
                    score = -searcher.bound(new_pos, 0, shallow_depth, can_null=True)
                except Exception:
                    score = quick_score
            elif score is None:
                score = quick_score
            scored_moves.append((move_str, score))

        # Step 3d: Final sort and trim
        scored_moves.sort(key=lambda x: x[1], reverse=True)
        scored_moves = scored_moves[:top_n]

    # 4 - Calculate PV for scoring
    my_pv = pv(searcher, hist[-1], include_scores=True)

    # Update score for top_n=1 fast path
    if top_n == 1 and len(scored_moves) > 0 and scored_moves[0][1] == 0:
        if len(my_pv) >= 3:
            score = int(my_pv[2]) - pos.score
            scored_moves = [(scored_moves[0][0], score)]

    # 5 - Determine best move
    bestmove_str = None

    if my_pv and len(my_pv) >= 2:
        potential_best = my_pv[1]
        move_from = potential_best[:2]
        is_ignored = False
        if ignore_squares and len(ignore_squares) > 0:
            is_ignored = move_from in ignore_squares
        if not is_ignored:
            bestmove_str = potential_best
            if len(my_pv) >= 3:
                bestmove_score = int(my_pv[2]) - pos.score

    if bestmove_str is None and len(scored_moves) > 0:
        bestmove_str = scored_moves[0][0]

    if not bestmove_str:
        return {"bestmove": "(none)", "scored_moves": [], "depth_reached": final_depth}

    return {
        "bestmove": bestmove_str,
        "scored_moves": scored_moves,
        "depth_reached": final_depth,
    }


def get_best_moves(fen, moves_history="", movetime=None, maxdepth=15,
                   precision=0.0, top_n=1, ignore_squares=None):
    """Compute the best move(s) for a position.

    Returns dict with "bestmoves", "check", and optionally "depth_reached" keys
    matching /bestmove response format.
    """
    fen_parts = fen.split()
    initial_side = fen_parts[1]

    hist = build_history(fen, moves_history)

    searcher = sunfish.Searcher()
    searcher.precision = precision

    max_movetime = 0
    if movetime:
        max_movetime = movetime / 1000.0

    result = _search_best_moves(
        searcher, hist, max_movetime, maxdepth,
        top_n, ignore_squares or []
    )

    if result["bestmove"] == "(none)":
        return {"bestmoves": [], "check": False}

    # Compute check status after applying best move
    bestmove = result["bestmove"]
    position = hist[-1]

    num_moves = len(moves_history.split()) if moves_history.strip() else 0
    if initial_side == 'w':
        effective_side = 'w' if (num_moves % 2 == 0) else 'b'
    else:
        effective_side = 'b' if (num_moves % 2 == 0) else 'w'

    if effective_side == 'b':
        move_from = 119 - sunfish.parse(bestmove[:2])
        move_to = 119 - sunfish.parse(bestmove[2:4])
    else:
        move_from = sunfish.parse(bestmove[:2])
        move_to = sunfish.parse(bestmove[2:4])
    promo = bestmove[4:].upper() if len(bestmove) > 4 else ""

    new_position = position.move(sunfish.Move(move_from, move_to, promo))
    is_check_val = can_kill_king(new_position.rotate())

    response = {
        "bestmoves": result["scored_moves"],
        "check": is_check_val,
    }
    if result["depth_reached"] is not None:
        response["depth_reached"] = result["depth_reached"]

    return response
