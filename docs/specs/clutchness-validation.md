# Clutchness Validation & Calibration Tests

**Type**: feature
**Priority**: medium
**Scope**: small (< 1 session)

## Problem

Clutchness (eval gap between best and 2nd-best move) is exposed via multiple endpoints but we have no way to know if:
1. The `peek_next` shortcut produces values consistent with a full independent calculation
2. The raw numbers are meaningful — what's "low"? what's "high"? There's no reference scale for frontend use

## Solution

Two test suites in a single file, both printing results for human review (no hard assertions on values).

### Part 1: peek_next vs independent calculation

Validate that `peek_next` clutchness matches an independent `/evalmoves` call on the same position.

**Flow for each test position (3-5 positions, variety of phases):**
1. `/newgame` with a FEN where it's the computer's turn
2. `/turn` with `peek_next: true` → record `next.clutchness`
3. After the computer moves, the session is now at the player's position
4. Call `/evalmoves` with the same `session_id` → record its `clutchness`
5. Print both values side-by-side. Flag if delta > 20% of the larger value (warning, not failure)

The positions don't need to be special — just a mix of opening/middlegame/endgame so we cover different move counts.

### Part 2: Calibration table

10 curated positions spanning the clutchness spectrum, measured via `/evalmoves` (the full independent calculation — no shortcut). Each position is set up so the **side to move** faces the clutchness scenario we want to measure.

**Flow for each position:**
1. `/newgame` with the curated FEN
2. `/evalmoves` with `session_id` and `maxdepth: 8` → record `clutchness`, best eval, 2nd-best eval
3. Print a table row: label, expected category, clutchness value, best_eval, 2nd_best_eval

**Curated positions (white to move unless noted):**

| # | Label | Expected | FEN | Rationale |
|---|-------|----------|-----|-----------|
| 1 | Opening — many good moves | low | `rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1` | After 1.e4, black has many reasonable replies (e5, c5, e6, d5, etc.) |
| 2 | Symmetrical middlegame | low | `r1bqkb1r/pppp1ppp/2n2n2/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 4 4` | Four Knights — very equal, many decent moves |
| 3 | K+P endgame — easy win | low | `8/8/8/8/8/4K3/4P3/4k3 w - - 0 1` | King+pawn vs king, several paths to promote |
| 4 | Middlegame — slight edge | medium | `r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4` | Italian Game — some moves are better but alternatives aren't terrible |
| 5 | Open position — one good plan | medium | `r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7` | Giuoco Piano — d4 is strong but other moves are playable |
| 6 | Undefended piece | medium-high | `r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1n3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 4` | Scholar's mate threat (Qxf7#) — one move is much better |
| 7 | Back rank threat | high | `6k1/5ppp/8/8/8/8/5PPP/1r2R1K1 w - - 0 1` | Must deal with back rank, one defensive move stands out |
| 8 | Fork opportunity | high | `r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4` | Knight/bishop tactics — one move wins material (will swap for a more tactical FEN if this one is too calm) |
| 9 | Mate in 2 | very high | `2bqkbn1/2pppppp/np2N3/r3P1p1/p2N2B1/5Q2/PPPPPP1P/RNB1K2R w KQq - 0 1` | Only one move sequence leads to mate |
| 10 | Puzzle — only move saves | very high | `r1b1k2r/ppppqppp/2n2n2/2b5/3NP3/2P1B3/PP3PPP/RN1QKB1R w KQkq - 0 7` | Piece hanging, must find the one saving move |

Note: Some FENs may need adjustment during implementation if the engine's eval doesn't produce the expected spread. The positions are starting points — the implementer should verify each one produces a distinct clutchness value and swap any that don't differentiate well.

## Acceptance Criteria

- [ ] Test file `tests/test_clutchness.py` runs via `make test-clutchness`
- [ ] Part 1: Prints peek_next vs evalmoves clutchness side-by-side for 3-5 positions, flags large deltas
- [ ] Part 2: Prints a calibration table with 10 positions showing label, expected category, actual clutchness, best/2nd-best eval
- [ ] All values are printed clearly for human review — no hard value assertions
- [ ] Makefile target `test-clutchness` added
- [ ] Test follows existing patterns (uses `requests`, same `BASE_URL`, same `test()` helper for structural checks)

## Out of Scope

- Asserting specific clutchness value ranges (this test *discovers* them)
- Changing the clutchness formula
- Frontend integration or percentile bucketing (that's the separate "cross-session database" backlog item)
- Testing clutchness via `/bestmove` (focus is on `/turn` + `peek_next` and `/evalmoves`)

## Open Questions

- Some curated FENs may not produce the expected clutchness spread at `maxdepth: 8`. The implementer should run them and swap any positions that don't differentiate. The spec provides the categories to hit, not necessarily the final FENs.
- `peek_next` uses `maxdepth: 5` by default (shallow). The delta with `/evalmoves` at `maxdepth: 8` may be significant — the test should document this and the implementer can experiment with matching depths.

## Related

- [engine.py](../../engine.py) — clutchness computation in `_search_best_moves()` and `_peek_next_position()`
- [tests/test_session.py](../../tests/test_session.py) — existing clutchness smoke tests
- [tests/test_dream_api.py](../../tests/test_dream_api.py) — peek_next structural tests
- Backlog: "cross-session database of clutchness values" (downstream consumer of calibration data)
