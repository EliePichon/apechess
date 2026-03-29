# Advanced UCI interface

import sys
import re, time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from functools import partial
import logging

# Configure logging
logger = logging.getLogger("sunfish")
logger.setLevel(logging.DEBUG)

# Create a handler that still goes to original stdout or to stderr
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.DEBUG)

# Format if you like
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)


def render_move(move, white_pov):
    if move is None:
        return "(none)"
    i, j = move[0], move[1]
    if not white_pov:
        i, j = sunfish.flip_coord(i), sunfish.flip_coord(j)
    render = sunfish.render
    return render(i) + render(j) + move[2].lower()


def parse_move(move_str, white_pov):
    parse = sunfish.parse
    i, j, prom = parse(move_str[:2]), parse(move_str[2:4]), move_str[4:].upper()
    logger.debug(f"Parsed move {move_str} to {i}, {j}, {prom}")
    if not white_pov:
        i, j = sunfish.flip_coord(i), sunfish.flip_coord(j)
    return (i, j, prom)


def go_loop(searcher, hist, stop_event, max_movetime=0, max_depth=8, debug=False, callbackMove=None, top_n=10, ignore_squares=[]):
    # Lazy import to break circular dependency (engine.py imports from tools/uci.py)
    from engine import run_iterative_deepening, get_filtered_legal_moves, score_moves, select_best_move

    if debug:
        logger.debug(f"Going movetime={max_movetime}, depth={max_depth}, top_n={top_n}, ignore_squares={ignore_squares}")

    pos = hist[-1]
    white_pov = len(hist) % 2 == 1

    # 1 - Iterative deepening search
    final_depth = run_iterative_deepening(searcher, hist, max_depth, max_movetime, stop_event=stop_event)

    # 2 - Legal moves (with ignore_squares filtering)
    legal_moves = get_filtered_legal_moves(pos, white_pov, ignore_squares)
    if not legal_moves:
        print("bestmove", "(none)", flush=True)
        return

    # 3 - Score and rank moves
    scored_moves, _ = score_moves(searcher, pos, legal_moves, white_pov, final_depth, top_n)

    # 4 - PV extraction + score refinement for fast path
    my_pv = pv(searcher, pos, include_scores=True)
    if top_n == 1 and scored_moves and scored_moves[0][1] == 0:
        if len(my_pv) >= 3:
            score = int(my_pv[2]) - pos.score
            scored_moves = [(scored_moves[0][0], score)]

    # Send scored moves to callback
    if callbackMove:
        callbackMove(scored_moves)

    # 5 - Select best move and print to stdout
    bestmove_str = select_best_move(my_pv, scored_moves, ignore_squares)

    if bestmove_str:
        # Derive score for output
        bestmove_score = None
        if my_pv and len(my_pv) >= 3 and my_pv[1] == bestmove_str:
            bestmove_score = int(my_pv[2]) - pos.score
        elif scored_moves:
            bestmove_score = scored_moves[0][1]

        if bestmove_score is not None:
            print("bestmove", bestmove_str, "score", bestmove_score, "depth", final_depth, flush=True)
        else:
            print("bestmove", bestmove_str, "depth", final_depth, flush=True)
    else:
        print("bestmove (none)", flush=True)


def mate_loop(
    searcher,
    hist,
    stop_event,
    max_movetime=0,
    max_depth=8,
    find_draw=False,
    debug=False,
):
    start = time.time()
    for d in range(int(max_depth) + 1):
        if find_draw:
            s0 = searcher.bound(hist[-1], 0, d)
            elapsed = time.time() - start
            print("info", "depth", d, "score lowerbound cp", s0)
            s1 = searcher.bound(hist[-1], 1, d)
            elapsed = time.time() - start
            print("info", "depth", d, "score upperbound cp", s1)
            if s0 >= 0 and s1 < 1:
                break
        else:
            score = searcher.bound(hist[-1], sunfish.MATE_LOWER, d)
            elapsed = time.time() - start
            print(
                "info depth",
                d,
                "score cp",
                score,
                "time",
                round(1000 * elapsed),
                "pv",
                " ".join(pv(searcher, hist[-1], include_scores=False)),
            )
            if score >= sunfish.MATE_LOWER:
                break
        if elapsed > max_movetime:
            break
        if stop_event.is_set():
            break
    move = searcher.tp_move.get(hist[-1])
    move_str = render_move(move, white_pov=len(hist) % 2 == 1)
    print("bestmove", move_str, flush=True)


def perft(pos, depth, debug=False):

    def _perft_count(pos, depth):
        # Check that we didn't get to an illegal position
        if can_kill_king(pos):
            return -1
        if depth == 0:
            return 1
        res = 0
        for move in pos.gen_moves():
            cnt = _perft_count(pos.move(move), depth - 1)
            if cnt != -1:
                res += cnt
        return res

    total = 0
    for move in pos.gen_moves():
        move_uci = render_move(move, get_color(pos) == WHITE)
        cnt = _perft_count(pos.move(move), depth - 1)
        if cnt != -1:
            print(f"{move_uci}: {cnt}")
            total += cnt
    print()
    print("Nodes searched:", total)


def run(sunfish_module, startpos, callbackPos=None, callbackMove=None):
    global sunfish
    sunfish = sunfish_module

    debug = False
    hist = [startpos]
    searcher = sunfish.Searcher()

    with ThreadPoolExecutor(max_workers=1) as executor:
        # Noop future to get started
        go_future = executor.submit(lambda: None)
        do_stop_event = Event()

        while True:
            try:
                args = input().split()
                if not args:
                    continue

                elif args[0] in ("stop", "quit"):
                    if go_future.running():
                        if debug:
                            print("Stopping go loop...")
                        do_stop_event.set()
                        go_future.result()
                    else:
                        if debug:
                            print("Go loop not running...")
                    if args[0] == "quit":
                        break

                elif not go_future.done():
                    print(f"Ignoring input {args}. Please call 'stop' first.")
                    continue

                # Make sure we are really done, and throw any errors that may have
                # happened in the go loop.
                go_future.result(timeout=0)

                if args[0] == "uci":
                    print(f"id name {sunfish.version}")
                    for attr, (lo, hi) in sunfish.opt_ranges.items():
                        default = getattr(sunfish, attr)
                        print(f"option name {attr} type spin default {default} min {lo} max {hi}")
                    print("uciok")

                elif args[0] == "setoption":
                    _, uci_key, _, uci_value = args[1:]
                    setattr(sunfish, uci_key, int(uci_value))

                # FIXME: It seems we should reply to "isready" even while thinking.
                # See: https://talkchess.com/forum3/viewtopic.php?f=7&t=81233&start=10
                elif args[0] == "isready":
                    print("readyok")

                elif args[0] == "quit":
                    break

                elif args[:2] == ["position", "startpos"]:
                    hist = [startpos]
                    for ply, move in enumerate(args[3:]):
                        hist.append(hist[-1].move(parse_move(move, ply % 2 == 0)))

                elif args[:2] == ["position", "fen"]:
                    # The FEN format is: fen board color castling enpas hclock fclock,
                    # so args[3] is the side ('w' or 'b').
                    pos = from_fen(*args[2:8])
                    # For white FEN, keep the board as is;
                    # for black, initialize history with two entries so that moves alternate properly.
                    if args[3] == "b":
                        hist = [pos.rotate(), pos]
                    else:
                        hist = [pos]
                    if len(args) > 8 and args[8] == "moves":
                        for move_str in args[9:]:
                            # Use the alternating scheme: if len(hist) % 2 == 1, then white's move; otherwise black's.
                            parsed_move = parse_move(move_str, white_pov=(len(hist) % 2 == 1))
                            hist.append(hist[-1].move(parsed_move))
                    logger.debug(f"Position {hist[-1]}")

                    # Call the callback with the current position
                    if callbackPos:
                        callbackPos(hist[-1])

                    # Write a confirmation response
                    print("info string position set successfully")

                # New function : get moves
                elif args[0] == "getmoves":
                    # Example: getmoves e2 P
                    if len(args) < 2:
                        print("info string getmoves requires a square (and optional piece type)")
                        continue

                    square = args[1]  # e.g., "e2"
                    piece_filter = args[2] if len(args) > 2 else None  # e.g., "P"

                    moves = hist[-1].get_legal_moves(square=square, piece_filter=piece_filter)
                    moves_uci = [render_move(move, white_pov=len(hist) % 2 == 1) for move in moves]
                    print("legal moves:", " ".join(moves_uci), flush=True)

                elif args[0] == "go":
                    think = 10**6
                    max_depth = 8
                    loop = go_loop

                    if args[1:] == [] or args[1] == "infinite":
                        pass

                    elif args[1] == "movetime":
                        movetime = args[2]
                        think = int(movetime) / 1000

                    elif args[1] == "wtime":
                        wtime, btime, winc, binc = [int(a) / 1000 for a in args[2::2]]
                        # we always consider ourselves white, but uci doesn't
                        if len(hist) % 2 == 0:
                            wtime, winc = btime, binc
                        think = min(wtime / 40 + winc, wtime / 2 - 1)
                        # let's go fast for the first moves
                        if len(hist) < 3:
                            think = min(think, 1)

                    elif args[1] == "depth":
                        max_depth = int(args[2])

                    elif args[1] in ("mate", "draw"):
                        max_depth = int(args[2])
                        loop = partial(mate_loop, find_draw=args[1] == "draw")

                    # Parse optional parameters (can appear in any order)
                    precision = 0
                    top_n = 1  # Default: return only best move (fast)
                    ignore_squares = []  # Squares to ignore (e.g., ["e2", "g1"])

                    if "precision" in args:
                        idx = args.index("precision")
                        if idx + 1 < len(args):
                            precision = args[idx + 1]

                    if "top_n" in args:
                        idx = args.index("top_n")
                        if idx + 1 < len(args):
                            top_n = int(args[idx + 1])

                    if "ignore" in args:
                        idx = args.index("ignore")
                        if idx + 1 < len(args):
                            # Parse comma-separated squares (e.g., "e2,g1,b1")
                            ignore_str = args[idx + 1]
                            ignore_squares = [sq.strip() for sq in ignore_str.split(",")]
                            logger.debug(f"Ignoring squares: {ignore_squares}")

                    setattr(searcher, "precision", float(precision))

                    do_stop_event.clear()
                    if loop is go_loop:
                        go_future = executor.submit(
                            loop,
                            searcher,
                            hist,
                            do_stop_event,
                            think,
                            max_depth,
                            debug=debug,
                            callbackMove=callbackMove,
                            top_n=top_n,
                            ignore_squares=ignore_squares,
                        )
                    else:
                        go_future = executor.submit(
                            loop,
                            searcher,
                            hist,
                            do_stop_event,
                            think,
                            max_depth,
                            debug=debug,
                        )

                    # Make sure we get informed if the job fails
                    def callback(fut):
                        fut.result(timeout=0)

                    go_future.add_done_callback(callback)

            except (KeyboardInterrupt, EOFError):
                if go_future.running():
                    if debug:
                        print("Stopping go loop...", flush=True)
                    do_stop_event.set()
                    go_future.result()
                break


# Old tools stuff

WHITE, BLACK = range(2)


def from_fen(board, color, castling, enpas, _hclock, _fclock):
    board = re.sub(r"\d", (lambda m: "." * int(m.group(0))), board)
    board = list(21 * " " + "  ".join(board.split("/")) + 21 * " ")
    board[9::10] = ["\n"] * 12
    board = "".join(board)
    wc = ("Q" in castling, "K" in castling)
    bc = ("k" in castling, "q" in castling)
    ep = sunfish.parse(enpas) if enpas != "-" else 0
    if hasattr(sunfish, "features"):
        wf, bf = sunfish.features(board)
        pos = sunfish.Position(board, 0, wf, bf, wc, bc, ep, 0)
        pos = pos._replace(score=pos.calculate_score())
    else:
        score = sum(sunfish.pst[c][i] for i, c in enumerate(board) if c.isupper())
        score -= sum(sunfish.pst[c.upper()][sunfish.flip_coord(i)] for i, c in enumerate(board) if c.islower())
        pos = sunfish.Position(board, score, wc, bc, ep, 0)
    return pos if color == "w" else pos.rotate()


def get_color(pos):
    """A slightly hacky way to to get the color from a sunfish position"""
    return BLACK if pos.board.startswith("\n") else WHITE


def can_kill_king(pos):
    # If we just checked for opponent moves capturing the king, we would miss
    # captures in case of illegal castling.
    # MATE_LOWER = 60_000 - 10 * 929
    # return any(pos.value(m) >= MATE_LOWER for m in pos.gen_moves())
    return any(pos.board[m[1]] == "k" or abs(m[1] - pos.kp) < 2 for m in pos.gen_moves())


def pv(searcher, pos, include_scores=True, include_loop=False):
    res = []
    seen_pos = set()
    color = get_color(pos)
    origc = color
    if include_scores:
        res.append(str(pos.score))
    while True:
        if hasattr(pos, "wf"):
            move = searcher.tp_move.get(pos.hash())
        elif hasattr(searcher, "tp_move"):
            move = searcher.tp_move.get(pos)
        elif hasattr(searcher, "tt_new"):
            move = searcher.tt_new[0][pos, True].move
        # The tp may have illegal moves, given lower depths don't detect king killing
        if move is None or can_kill_king(pos.move(move)):
            break
        res.append(render_move(move, get_color(pos) == WHITE))
        pos, color = pos.move(move), 1 - color

        if hasattr(pos, "wf"):
            if pos.hash() in seen_pos:
                if include_loop:
                    res.append("loop")
                break
            seen_pos.add(pos.hash())
        else:
            if pos in seen_pos:
                if include_loop:
                    res.append("loop")
                break
            seen_pos.add(pos)

        if include_scores:
            res.append(str(pos.score if color == origc else -pos.score))
    return res
