# engine.py - Clean Python API for the Sunfish chess engine
# Replaces the UCI stdin/stdout wrapper with direct function calls.

import time
import uuid
import logging
import threading

import sunfish
import tools.uci as uci
from tools.uci import from_fen, can_kill_king, render_move, parse_move, pv

# Set the global sunfish reference that tools/uci.py helpers depend on.
# Normally set by uci.run(), but we bypass run() entirely.
uci.sunfish = sunfish

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Game Session — holds position + Searcher state across requests
# ---------------------------------------------------------------------------

DEFAULT_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _tt_lookup(searcher, pos, final_depth, min_depth=1):
    """Look up position score from transposition table across depth range.

    Returns the score (negated, from opponent's perspective) or None if not found.
    """
    for check_depth in range(final_depth - 1, min_depth - 1, -1):
        entry = searcher.tp_score.get((pos, check_depth, True), None)
        if entry is not None:
            bound_width = entry.upper - entry.lower
            if bound_width < 1000:
                return -((entry.lower + entry.upper) // 2)
    return None


class GameSession:
    TP_MOVE_CAP = 100_000
    EXPIRE_SECONDS = 1800  # 30 minutes

    def __init__(self, session_id, fen=None):
        self.session_id = session_id
        self._searcher = sunfish.Searcher()
        self._lock = threading.Lock()
        self._last_used = time.time()
        self._set_position(fen or DEFAULT_FEN)

    def _set_position(self, fen, moves_str=""):
        self._fen = fen
        self._hist = build_history(fen, moves_str)

    def apply_move(self, move_str):
        """Apply a single move to the session position. Validates legality."""
        white_pov = len(self._hist) % 2 == 1
        parsed = parse_move(move_str, white_pov=white_pov)
        pos = self._hist[-1]
        legal = list(pos.get_legal_moves())
        if parsed not in legal:
            raise ValueError(f"Illegal move: {move_str}")
        self._hist.append(pos.move(parsed))
        return self._hist[-1]

    def override_fen(self, fen, moves_str=""):
        """Force-set position from FEN (for re-sync, undo, analysis)."""
        self._set_position(fen, moves_str)

    def run_search(self, search_fn):
        """Execute search_fn(searcher, hist) while holding the lock."""
        with self._lock:
            self._last_used = time.time()
            if len(self._searcher.tp_move) > self.TP_MOVE_CAP:
                self._searcher.tp_move.clear()
            return search_fn(self._searcher, self._hist)

    def is_expired(self):
        return time.time() - self._last_used > self.EXPIRE_SECONDS

    @property
    def hist(self):
        return self._hist

    @property
    def position(self):
        return self._hist[-1]

    def stats(self):
        return {
            "tp_move_size": len(self._searcher.tp_move),
            "tp_score_size": len(self._searcher.tp_score),
            "ply": len(self._hist),
        }


# Session store
_sessions = {}


def create_session(fen=None):
    """Create a new session with a server-generated ID. Returns session_id."""
    _cleanup_expired()
    sid = uuid.uuid4().hex[:12]
    _sessions[sid] = GameSession(sid, fen)
    return sid


def get_session(session_id):
    """Get a session by ID. Returns None if not found or expired."""
    s = _sessions.get(session_id)
    if s and not s.is_expired():
        return s
    return None


def reset_session(session_id, fen=None):
    """Reset an existing session or create a new one."""
    if session_id in _sessions:
        _sessions[session_id].override_fen(fen or DEFAULT_FEN)
        _sessions[session_id]._searcher = sunfish.Searcher()
    else:
        _sessions[session_id] = GameSession(session_id, fen)


def session_stats(session_id):
    """Return stats for a session."""
    s = get_session(session_id)
    if s is None:
        return None
    return s.stats()


def _cleanup_expired():
    """Remove expired sessions."""
    expired = [sid for sid, s in _sessions.items() if s.is_expired()]
    for sid in expired:
        del _sessions[sid]


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


def _detect_game_over(pos):
    """Check if a position is checkmate, stalemate, or ongoing.

    Returns "checkmate", "stalemate", or None (game continues).
    """
    legal = list(pos.get_legal_moves())
    if legal:
        return None
    in_check = can_kill_king(pos.rotate())
    return "checkmate" if in_check else "stalemate"


def _get_legal_moves_from_pos(pos, white_pov):
    """Get legal moves grouped by source square from a Position object.

    Returns dict: {square_str: [move_str, ...]}
    """
    player_pieces = frozenset("PNBRQKACDTXY")
    moves = {}
    for i, piece in enumerate(pos.board):
        if piece in player_pieces:
            legal = pos.get_legal_moves(square=i)
            if legal:
                if white_pov:
                    sq = sunfish.render(i)
                    move_strs = [
                        sunfish.render(m.i) + sunfish.render(m.j) + m.prom.lower()
                        for m in legal
                    ]
                else:
                    sq = sunfish.render(119 - i)
                    move_strs = [
                        sunfish.render(119 - m.i) + sunfish.render(119 - m.j) + m.prom.lower()
                        for m in legal
                    ]
                moves[sq] = move_strs
    return moves


def get_legal_moves(fen):
    """Get all legal moves for the position described by the FEN.

    Returns dict with "moves" and "check" keys matching /getmoves response format.
    Mirrors server.py lines 135-167.
    """
    fen_parts = fen.split()
    side_to_move = fen_parts[1]

    hist = build_history(fen)
    position = hist[-1]

    moves = _get_legal_moves_from_pos(position, white_pov=(side_to_move != "b"))

    rotated_pos = position.rotate()
    check = can_kill_king(rotated_pos)

    return {"moves": moves, "check": check}


def _peek_next_position(searcher, hist, maxdepth=5):
    """Search current position for legal moves, clutchness, best_move, best_eval.

    Uses _search_best_moves() with top_n=2 for clutchness calculation.
    The searcher's tp_move table carries over from the preceding deep search,
    giving excellent move ordering even at shallow depth.

    Must be called under session lock. Reuses the session's searcher.
    """
    pos = hist[-1]
    white_pov = len(hist) % 2 == 1

    moves_dict = _get_legal_moves_from_pos(pos, white_pov)
    check = can_kill_king(pos.rotate())

    result = _search_best_moves(searcher, hist, 0, maxdepth, 2, [])
    scored = result.get("scored_moves", [])
    clutchness_val = result.get("clutchness")
    best_eval = scored[0][1] if scored else None
    best_move = scored[0][0] if scored else result.get("bestmove")

    return {
        "legal_moves": moves_dict,
        "check": check,
        "clutchness": clutchness_val,
        "best_eval": best_eval,
        "best_move": best_move,
    }


def _grade_move(searcher, hist, move_str, maxdepth=8):
    """Grade a player's move by comparing to the engine's best.

    Must be called BEFORE applying the move (needs pre-move position + TT).
    """
    # Search for the best move
    result = _search_best_moves(searcher, hist, 0, maxdepth, 2, [])
    best_move_str = result.get("bestmove", "(none)")
    best_eval = result["scored_moves"][0][1] if result.get("scored_moves") else 0

    # Evaluate the player's specific move
    pos = hist[-1]
    white_pov = len(hist) % 2 == 1
    player_move_obj = parse_move(move_str, white_pov=white_pov)
    new_pos = pos.move(player_move_obj)

    # Try TT lookup first
    final_depth = result.get("depth_reached", 1)
    player_eval = _tt_lookup(searcher, new_pos, final_depth)

    # Fallback: shallow search
    if player_eval is None:
        try:
            eval_depth = max(3, final_depth - 3)
            player_eval = -searcher.bound(new_pos, 0, eval_depth, can_null=True)
        except Exception:
            player_eval = pos.value(player_move_obj)

    # Accuracy: 1.0 = perfect, 0.0 = lost >= 200 centipawns
    ACCURACY_SCALE = 200
    eval_gap = max(0, best_eval - player_eval)
    accuracy = round(max(0.0, 1.0 - eval_gap / ACCURACY_SCALE), 2)

    return {
        "player_eval": player_eval,
        "best_eval": best_eval,
        "best_move": best_move_str,
        "accuracy": accuracy,
    }


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
            score = _tt_lookup(searcher, new_pos, final_depth)
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
            score = _tt_lookup(searcher, new_pos, final_depth, min_depth=max(1, final_depth - 2))
            if score is None and shallow_depth > 0:
                try:
                    score = -searcher.bound(new_pos, 0, shallow_depth, can_null=True)
                except Exception:
                    score = quick_score
            elif score is None:
                score = quick_score
            scored_moves.append((move_str, score))

        # Step 3d: Final sort
        scored_moves.sort(key=lambda x: x[1], reverse=True)

    # 3e - Compute clutchness (eval gap between best and 2nd-best) before trimming
    clutchness_val = None
    if len(scored_moves) >= 2:
        clutchness_val = scored_moves[0][1] - scored_moves[1][1]

    # 3f - Trim to requested top_n
    if len(scored_moves) > top_n:
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
        "clutchness": clutchness_val,
    }


def _compute_check_after_move(bestmove, hist, moves_history="", initial_side="w"):
    """Compute whether the opponent is in check after applying a move."""
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
    return can_kill_king(new_position.rotate())


def get_best_moves(fen=None, moves_history="", movetime=None, maxdepth=15,
                   precision=0.0, top_n=1, ignore_squares=None,
                   session_id=None, clutchness=False):
    """Compute the best move(s) for a position.

    Two modes:
    - Stateless (fen required): creates fresh Searcher, backward-compatible.
    - Session (session_id required): uses persistent Searcher for tp_move reuse.

    When clutchness=True, returns the eval gap between best and 2nd-best move.
    Any request can include fen to override/re-sync the session position.
    """
    internal_top_n = max(top_n, 2) if clutchness else top_n

    max_movetime = 0
    if movetime:
        max_movetime = movetime / 1000.0

    if session_id:
        session = get_session(session_id)
        if session is None:
            return {"error": "Invalid or expired session_id"}, 404
        if fen:
            session.override_fen(fen, moves_history)

        def do_search(searcher, hist):
            searcher.precision = precision
            return _search_best_moves(
                searcher, hist, max_movetime, maxdepth,
                internal_top_n, ignore_squares or []
            )

        result = session.run_search(do_search)
        hist = session.hist
    else:
        if not fen:
            return {"error": "Either fen or session_id is required"}, 400
        hist = build_history(fen, moves_history)
        searcher = sunfish.Searcher()
        searcher.precision = precision
        result = _search_best_moves(
            searcher, hist, max_movetime, maxdepth,
            internal_top_n, ignore_squares or []
        )

    if result["bestmove"] == "(none)":
        return {"bestmoves": [], "check": False}

    # Determine initial_side from hist or fen
    if fen:
        initial_side = fen.split()[1]
    else:
        # Infer from session: odd hist length = white to move
        initial_side = 'w' if len(hist) % 2 == 1 else 'b'

    is_check_val = _compute_check_after_move(
        result["bestmove"], hist, moves_history, initial_side
    )

    response = {
        "bestmoves": result["scored_moves"][:top_n],
        "check": is_check_val,
    }
    if result["depth_reached"] is not None:
        response["depth_reached"] = result["depth_reached"]
    if clutchness and result.get("clutchness") is not None:
        response["clutchness"] = result["clutchness"]

    return response


def get_evaluated_moves(fen=None, moves_history="", maxdepth=8, movetime=None,
                        session_id=None):
    """Get all legal moves with evaluation scores for each.

    Runs a search to populate the TT, then scores each legal move via TT
    lookup or shallow search. Returns moves grouped by source square.
    Supports both stateless (fen) and session-based modes.
    """
    max_movetime = 0
    if movetime:
        max_movetime = movetime / 1000.0

    if session_id:
        session = get_session(session_id)
        if session is None:
            return {"error": "Invalid or expired session_id"}, 404
        if fen:
            session.override_fen(fen, moves_history)

        def do_eval(searcher, hist):
            searcher.precision = 0.0
            return _evaluate_all_moves(searcher, hist, max_movetime, maxdepth)

        result = session.run_search(do_eval)
        hist = session.hist
    else:
        if not fen:
            return {"error": "Either fen or session_id is required"}, 400
        hist = build_history(fen, moves_history)
        searcher = sunfish.Searcher()
        searcher.precision = 0.0
        result = _evaluate_all_moves(searcher, hist, max_movetime, maxdepth)

    # Determine side to move for coordinate rendering
    white_pov = len(hist) % 2 == 1

    # Check detection
    pos = hist[-1]
    check = can_kill_king(pos.rotate())

    # Build response grouped by source square
    player_pieces = frozenset("PNBRQKACDTXY")
    moves_by_square = {}
    all_evals = []

    for m, score in result["move_evals"]:
        if white_pov:
            src = sunfish.render(m.i)
            move_str = sunfish.render(m.i) + sunfish.render(m.j) + m.prom.lower()
        else:
            src = sunfish.render(119 - m.i)
            move_str = sunfish.render(119 - m.i) + sunfish.render(119 - m.j) + m.prom.lower()

        if src not in moves_by_square:
            moves_by_square[src] = []
        moves_by_square[src].append({"move": move_str, "eval": score})
        all_evals.append(score)

    # Sort moves within each square by eval descending
    for sq in moves_by_square:
        moves_by_square[sq].sort(key=lambda x: x["eval"], reverse=True)

    # Compute clutchness
    all_evals.sort(reverse=True)
    clutchness_val = None
    if len(all_evals) >= 2:
        clutchness_val = all_evals[0] - all_evals[1]

    return {
        "moves": moves_by_square,
        "check": check,
        "clutchness": clutchness_val,
    }


def _evaluate_all_moves(searcher, hist, max_movetime, max_depth):
    """Run a search then evaluate each legal move using TT + shallow search."""
    start = time.time()
    final_depth = 1

    # Run main search to populate TT
    for depth, gamma, score, move in searcher.search(hist):
        final_depth = depth
        if depth - 1 >= max_depth:
            break
        elapsed = time.time() - start
        if depth > 1 and max_movetime > 0 and elapsed > max_movetime * 2 / 3:
            break

    pos = hist[-1]
    legal_moves = [m for m in pos.gen_moves() if not can_kill_king(pos.move(m))]

    eval_depth = max(3, final_depth - 3)
    move_evals = []

    for m in legal_moves:
        new_pos = pos.move(m)
        score = _tt_lookup(searcher, new_pos, final_depth)

        # Fallback: shallow search
        if score is None:
            try:
                score = -searcher.bound(new_pos, 0, eval_depth, can_null=True)
            except Exception:
                score = pos.value(m)

        move_evals.append((m, score))

    return {"move_evals": move_evals, "depth_reached": final_depth}


def apply_move(session_id, move_str, is_computer_turn=False,
               maxdepth=15, movetime=None, fen=None, moves_history=""):
    """Apply a move to a session and optionally auto-compute the response.

    On computer turns, automatically computes and returns the best move(s)
    with clutchness. On player turns, just confirms the move and check status.
    Optional fen parameter for re-sync.
    """
    session = get_session(session_id)
    if session is None:
        return {"error": "Invalid or expired session_id"}, 404

    if fen:
        session.override_fen(fen, moves_history)

    try:
        session.apply_move(move_str)
    except ValueError as e:
        return {"error": str(e)}, 400

    result = {"status": "ok"}

    # Check detection after the move
    pos = session.position
    result["check"] = can_kill_king(pos.rotate())
    result["ply"] = len(session.hist)

    # Auto-compute on computer turn
    if is_computer_turn:
        best = get_best_moves(
            session_id=session_id, maxdepth=maxdepth,
            movetime=movetime, clutchness=True
        )
        if isinstance(best, tuple):
            # Error case (returns (dict, status_code))
            result["bestmoves"] = []
            result["clutchness"] = None
        else:
            result["bestmoves"] = best.get("bestmoves", [])
            result["clutchness"] = best.get("clutchness")

    return result


def computer_turn(session_id, maxdepth=15, movetime=None, precision=0.0,
                  top_n=1, ignore_squares=None, peek_next=False, peek_maxdepth=5,
                  fen=None, moves_history=""):
    """Computer plays a turn: search, apply best move, detect game over, optionally peek.

    All operations in a single session lock acquisition for thread safety and TT reuse.
    """
    session = get_session(session_id)
    if session is None:
        return {"error": "Invalid or expired session_id"}, 404

    if fen:
        session.override_fen(fen, moves_history)

    max_movetime = (movetime / 1000.0) if movetime else 0

    def do_turn(searcher, hist):
        searcher.precision = precision

        # 1. Search for best move
        result = _search_best_moves(
            searcher, hist, max_movetime, maxdepth,
            top_n, ignore_squares or []
        )

        if result["bestmove"] == "(none)":
            game_over = _detect_game_over(hist[-1])
            return {"move": None, "eval": None, "check": False, "game_over": game_over,
                    "ply": len(session.hist)}

        best_move_str = result["bestmove"]
        best_eval = result["scored_moves"][0][1] if result.get("scored_moves") else 0

        # 2. Apply the move to the session
        session.apply_move(best_move_str)

        # 3. Detect check and game_over after our move
        pos_after = session.position
        check = can_kill_king(pos_after.rotate())
        game_over = _detect_game_over(pos_after)

        response = {
            "move": best_move_str,
            "eval": best_eval,
            "check": check,
            "game_over": game_over,
            "ply": len(session.hist),
        }

        # 4. Optionally peek at the next position
        if peek_next and game_over is None:
            response["next"] = _peek_next_position(searcher, session.hist, peek_maxdepth)

        return response

    return session.run_search(do_turn)


def player_move(session_id, move_str, grade=False, grade_maxdepth=8,
                peek_next=False, peek_maxdepth=5,
                fen=None, moves_history=""):
    """Player makes a move: validate, optionally grade, apply, detect game over, optionally peek.

    All operations in a single session lock acquisition.
    Order: grade (before move) -> apply -> game_over -> peek (after move).
    """
    session = get_session(session_id)
    if session is None:
        return {"error": "Invalid or expired session_id"}, 404

    if fen:
        session.override_fen(fen, moves_history)

    def do_move(searcher, hist):
        searcher.precision = 0.0

        # Validate move legality
        white_pov = len(hist) % 2 == 1
        parsed = parse_move(move_str, white_pov=white_pov)
        pos = hist[-1]
        legal = list(pos.get_legal_moves())
        if parsed not in legal:
            raise ValueError(f"Illegal move: {move_str}")

        response = {"status": "ok"}

        # 1. Grade BEFORE applying (needs pre-move position + TT)
        if grade:
            response["grade"] = _grade_move(searcher, hist, move_str, grade_maxdepth)

        # 2. Apply move
        session.apply_move(move_str)

        # 3. Check and game_over detection
        pos_after = session.position
        check = can_kill_king(pos_after.rotate())
        game_over = _detect_game_over(pos_after)
        response["check"] = check
        response["game_over"] = game_over
        response["ply"] = len(session.hist)

        # 4. Peek at next position
        if peek_next and game_over is None:
            response["next"] = _peek_next_position(searcher, session.hist, peek_maxdepth)

        return response

    try:
        return session.run_search(do_move)
    except ValueError as e:
        return {"error": str(e)}, 400
