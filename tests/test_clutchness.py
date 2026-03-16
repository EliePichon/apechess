#!/usr/bin/env python3
"""
Clutchness validation and calibration tests.

Part 1: peek_next vs independent /evalmoves consistency check.
Part 2: Calibration table — 10 curated positions spanning the clutchness spectrum.

All values printed for human review. No hard assertions on specific clutchness values.
"""

import requests

BASE_URL = "http://localhost:5500"

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS  {name}")
        passed += 1
    else:
        print(f"  FAIL  {name} — {detail}")
        failed += 1


def create_session(fen=None):
    body = {"fen": fen} if fen else {}
    r = requests.post(f"{BASE_URL}/newgame", json=body)
    return r.json()["session_id"]


def extract_top_two_evals(moves_dict):
    """Extract the two highest eval scores from an /evalmoves moves dict."""
    all_evals = []
    for square, entries in moves_dict.items():
        for entry in entries:
            if "eval" in entry and isinstance(entry["eval"], (int, float)):
                all_evals.append(entry["eval"])
    all_evals.sort(reverse=True)
    best = all_evals[0] if len(all_evals) >= 1 else None
    second = all_evals[1] if len(all_evals) >= 2 else None
    return best, second


# ---------------------------------------------------------------------------
# Part 1: peek_next vs /evalmoves consistency
# ---------------------------------------------------------------------------

# Positions where it is the computer's turn (computer plays via /turn).
# Mix of game phases. Depths kept shallow to avoid timeout.
PART1_POSITIONS = [
    {
        "label": "Opening (after 1.e4)",
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
    },
    {
        "label": "Four Knights middlegame",
        "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 4 4",
    },
    {
        "label": "Italian Game",
        "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    },
    {
        "label": "K+P endgame",
        "fen": "8/8/8/8/8/4K3/4P3/4k3 w - - 0 1",
    },
]


def run_part1():
    print("\n" + "=" * 70)
    print("Part 1: peek_next vs /evalmoves clutchness consistency")
    print("=" * 70)
    print(
        "Note: peek_next uses peek_maxdepth=5 (shallow); /evalmoves uses maxdepth=5.\n"
        "      Delta expected — this test documents the spread, not asserts equality.\n"
    )
    print(f"  {'Position':<35} {'peek_next':>12} {'evalmoves':>12} {'delta':>8}  flag")
    print(f"  {'-'*35} {'-'*12} {'-'*12} {'-'*8}  ----")

    for pos in PART1_POSITIONS:
        label = pos["label"]
        fen = pos["fen"]

        # 1. Create session
        sid = create_session(fen)

        # 2. /turn with peek_next
        r = requests.post(f"{BASE_URL}/turn", json={
            "session_id": sid,
            "maxdepth": 6,
            "peek_next": True,
            "peek_maxdepth": 5,
        })
        test(f"[{label}] /turn returns 200", r.status_code == 200, f"got {r.status_code}")
        turn_data = r.json()

        test(f"[{label}] /turn has next block", "next" in turn_data,
             f"keys: {list(turn_data.keys())}")
        nxt = turn_data.get("next", {})
        test(f"[{label}] next has clutchness field", "clutchness" in nxt,
             f"next keys: {list(nxt.keys())}")

        peek_clutchness = nxt.get("clutchness")
        test(f"[{label}] peek clutchness is numeric or null",
             peek_clutchness is None or isinstance(peek_clutchness, (int, float)),
             f"got {peek_clutchness!r}")

        # 3. /evalmoves on the same session (after /turn advanced the position)
        r2 = requests.post(f"{BASE_URL}/evalmoves", json={
            "session_id": sid,
            "maxdepth": 5,
        })
        test(f"[{label}] /evalmoves returns 200", r2.status_code == 200, f"got {r2.status_code}")
        eval_data = r2.json()

        test(f"[{label}] /evalmoves has clutchness field", "clutchness" in eval_data,
             f"keys: {list(eval_data.keys())}")
        eval_clutchness = eval_data.get("clutchness")
        test(f"[{label}] evalmoves clutchness is numeric or null",
             eval_clutchness is None or isinstance(eval_clutchness, (int, float)),
             f"got {eval_clutchness!r}")

        # Print side-by-side
        peek_str = f"{peek_clutchness}" if peek_clutchness is not None else "null"
        eval_str = f"{eval_clutchness}" if eval_clutchness is not None else "null"

        flag = ""
        if peek_clutchness is not None and eval_clutchness is not None:
            larger = max(abs(peek_clutchness), abs(eval_clutchness))
            if larger > 0:
                delta = abs(peek_clutchness - eval_clutchness)
                delta_pct = delta / larger
                flag = "WARN >20%" if delta_pct > 0.20 else "ok"
                delta_str = f"{delta_pct*100:.0f}%"
            else:
                delta_str = "0%"
                flag = "ok"
        else:
            delta_str = "n/a"
            flag = ""

        print(f"  {label:<35} {peek_str:>12} {eval_str:>12} {delta_str:>8}  {flag}")

    print()


# ---------------------------------------------------------------------------
# Part 2: Calibration table
# ---------------------------------------------------------------------------

# Positions verified at maxdepth=5. Expected clutchness ranges (approximate):
#   low:         0-20
#   medium:      20-80
#   medium-high: 50-200
#   high:        200-600
#   very high:   600+
CALIBRATION_POSITIONS = [
    {
        "label": "Opening — many good moves",
        "expected": "low",
        # After 1.e4, black has many near-equal replies (c5, e5, e6, d5, Nf6, c6...)
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
    },
    {
        "label": "Four Knights — very equal",
        "expected": "low",
        # Symmetrical Four Knights: extremely balanced, many decent moves
        "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 4 4",
    },
    {
        "label": "K+P endgame — easy win",
        "expected": "low",
        # King + pawn vs lone king, several paths to promotion
        "fen": "8/8/8/8/8/4K3/4P3/4k3 w - - 0 1",
    },
    {
        "label": "Italian Game — slight edge",
        "expected": "medium",
        # Italian Game: some moves are better but alternatives aren't terrible
        "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    },
    {
        "label": "Open middlegame — plan matters",
        "expected": "medium",
        # Open Four Knights variant: d4/exd4 push is best but other moves are playable
        "fen": "r1bqkb1r/ppp2ppp/2np1n2/4p3/3PP3/2N2N2/PPP2PPP/R1BQKB1R w KQkq - 0 5",
    },
    {
        "label": "Pin wins material",
        "expected": "medium-high",
        # Bishop pinning Nc6 against king — Bxc6 wins a pawn/piece clearly
        "fen": "r1bqk2r/pppp1ppp/2n2n2/4p3/1bB1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 2 5",
    },
    {
        "label": "Back rank threat",
        "expected": "high",
        # Rook on b1 threatens back rank — Rxb1 is far better than alternatives
        "fen": "6k1/5ppp/8/8/8/8/5PPP/1r2R1K1 w - - 0 1",
    },
    {
        "label": "Fork opportunity — Fried Liver",
        "expected": "high",
        # Nxf7 fork wins material decisively; alternatives are significantly worse
        "fen": "r1bqkb1r/ppp2ppp/2np4/4p3/2BPP3/2N2N2/PPP2PPP/R1BQK2R w KQkq - 0 6",
    },
    {
        "label": "Mate in 2",
        "expected": "very high",
        # Qxf7+ leads to forced mate; only one move sequence wins
        "fen": "2bqkbn1/2pppppp/np2N3/r3P1p1/p2N2B1/5Q2/PPPPPP1P/RNB1K2R w KQq - 0 1",
    },
    {
        "label": "Tactical desperado",
        "expected": "very high",
        # Only one move avoids material loss while creating threats
        "fen": "r1b2rk1/pp4pp/2p2n2/3pq3/3P4/2N1B1P1/PP3P1P/R2QK2R w KQ - 0 14",
    },
]


def run_part2():
    print("\n" + "=" * 70)
    print("Part 2: Clutchness calibration table (maxdepth=5)")
    print("=" * 70)
    print(
        "All values from /evalmoves — no assertions on specific ranges.\n"
        "Use this output to calibrate frontend thresholds.\n"
    )

    header = (
        f"  {'#':>2}  {'Label':<35} {'Expected':<12} "
        f"{'Clutchness':>12} {'Best eval':>10} {'2nd best':>10}"
    )
    print(header)
    print(f"  {'--':>2}  {'-'*35} {'-'*12} {'-'*12} {'-'*10} {'-'*10}")

    for i, pos in enumerate(CALIBRATION_POSITIONS, start=1):
        label = pos["label"]
        expected = pos["expected"]
        fen = pos["fen"]

        # Create session + evalmoves
        sid = create_session(fen)
        r = requests.post(f"{BASE_URL}/evalmoves", json={
            "session_id": sid,
            "maxdepth": 5,
        })

        test(f"[{i}. {label}] /evalmoves returns 200",
             r.status_code == 200, f"got {r.status_code}")
        data = r.json()

        test(f"[{i}. {label}] has clutchness", "clutchness" in data,
             f"keys: {list(data.keys())}")
        test(f"[{i}. {label}] has moves", "moves" in data,
             f"keys: {list(data.keys())}")

        clutchness = data.get("clutchness")
        test(f"[{i}. {label}] clutchness is numeric",
             isinstance(clutchness, (int, float)),
             f"got {clutchness!r} (type {type(clutchness).__name__})")

        moves_dict = data.get("moves", {})
        best_eval, second_eval = extract_top_two_evals(moves_dict)

        clutch_str = f"{clutchness}" if clutchness is not None else "null"
        best_str = f"{best_eval}" if best_eval is not None else "n/a"
        second_str = f"{second_eval}" if second_eval is not None else "n/a"

        print(
            f"  {i:>2}  {label:<35} {expected:<12} "
            f"{clutch_str:>12} {best_str:>10} {second_str:>10}"
        )

    print()


def main():
    print("=" * 70)
    print("Clutchness Validation & Calibration Tests")
    print("=" * 70)

    run_part1()
    run_part2()

    print(f"{'=' * 70}")
    print(f"Structural checks: {passed} passed, {failed} failed")
    print(f"{'=' * 70}")

    if failed > 0:
        exit(1)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to server.")
        print("Make sure the server is running: make up")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
