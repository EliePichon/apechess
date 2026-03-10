# Session vs Stateless Performance Benchmark

**Type**: feature
**Priority**: medium
**Scope**: small (< 1 session)

## Problem

We introduced session-based stateful mode where the engine keeps a transposition table (TP) across moves. In theory, TP reuse should speed up searches because positions explored in previous moves are already cached. But we have no data on whether this actually matters in practice, or by how much.

We need a benchmark that quantifies the speedup (or lack thereof) of session mode vs stateless mode over a realistic multi-move game.

## Solution

A new benchmark script that has the engine play itself for ~20 moves, measuring per-move search time in two modes:

1. **Session mode** (TP reuse): `/newgame` → repeated `/turn` calls. The TP table accumulates across moves.
2. **Stateless mode** (cold TP): `/bestmove` with FEN for each position. No session, no TP history — each move starts from scratch.

The stateless run replays the **same move sequence** produced by the session run, ensuring both modes evaluate identical positions for a fair comparison.

### How It Works

#### Phase 1: Session Run (generates the game)
1. `POST /newgame` → get `session_id`
2. Loop 20 times:
   - `POST /turn` with `session_id`, `maxdepth: 8`
   - Record the move played and the response time
   - Stop early if `game_over` is not null
3. Store the ordered list of moves and the per-move timings.

#### Phase 2: Extract position FENs
After the session run, replay the move sequence to reconstruct the FEN at each ply. Use a helper session:
1. `POST /newgame` → get a fresh `session_id`
2. For each move in the sequence:
   - Before applying the move, call `GET /session/stats` or a lightweight endpoint to note the position. (Alternatively, track FENs by calling `/getmoves` or just use `/bestmove` with the session to get the position.)

**Simpler approach**: During Phase 1, also record the FEN at each step. Since `/turn` doesn't return the FEN directly, use a parallel tracking session:
1. Create a second "shadow" session from the same starting position.
2. After each `/turn` move on the main session, apply the same move on the shadow session via `/move`.
3. Use the shadow session's known state to reconstruct FENs.

**Simplest approach**: Build the FEN programmatically. Start from the initial FEN, and after each move, derive the next FEN. This can be done with a lightweight helper (python-chess or manual tracking). Since we control the starting position and know every move, this is deterministic.

**Recommended**: Use python-chess (`chess` library) to track the board state and generate FENs after each move. Add it as a test-only dependency.

#### Phase 3: Stateless Run (replays the game)
For each position FEN from Phase 2:
1. `POST /bestmove` with `fen: <position_fen>`, `maxdepth: 8`
2. Record the response time.
3. No session — each request is fully independent with a cold TP table.

#### Phase 4: Compare and Print
Print a table with:
- Per-move timings for both modes
- Total time for each mode
- Speedup ratio (stateless_total / session_total)
- Per-move delta

### Output Format

Follow the existing `test_performance.py` style:

```
======================================================================
SESSION vs STATELESS BENCHMARK
======================================================================
Depth: 8 | Moves: 20 | Starting position: standard
======================================================================

Move  Session (s)  Stateless (s)  Delta (s)  Speedup
----------------------------------------------------------------------
 1    0.142        0.158          +0.016     1.11x
 2    0.135        0.161          +0.026     1.19x
 3    0.189        0.203          +0.014     1.07x
...
----------------------------------------------------------------------
Total 3.241        4.017          +0.776     1.24x
======================================================================
```

### Technical Approach

- New file: `tests/test_session_perf.py`
- New make target: `make test-session-perf`
- Uses `python-chess` for FEN tracking (add to test requirements or use a minimal board tracker)
- Alternatively, avoid the python-chess dependency: after Phase 1, create a fresh session and replay moves one by one via `/move`, calling an endpoint that returns position info at each step. Since we only need FENs for the `/bestmove` calls, we could also add a small `/session/fen` endpoint — but that's scope creep. Prefer python-chess.
- Runs against the Docker dev server (same as other tests).

**If python-chess is too heavy**: A simpler alternative is to run the stateless pass using throwaway sessions. For each move:
1. `POST /newgame` with the same starting FEN
2. Replay all moves up to that point via `/move`
3. Call `/bestmove` with the session
4. Discard the session

This is slower (O(n²) moves) but avoids any dependency. Given n=20, the overhead is negligible.

**Recommended final approach**: Use throwaway sessions to avoid adding dependencies. For each position in the game:
1. `POST /newgame`
2. Replay moves 1..i via `/move`
3. `POST /bestmove` with `session_id`, `maxdepth: 8` — time this call only
4. This gives a cold TP for each position (fresh session = empty TP)

This is the cleanest comparison: same search engine, same depth, same position, but the session run has accumulated TP entries while the stateless run has none.

## Acceptance Criteria

- [ ] New benchmark script at `tests/test_session_perf.py`
- [ ] `make test-session-perf` target in Makefile
- [ ] Engine plays itself for ~20 moves (stops early on game_over)
- [ ] Session run uses `/turn` with persistent session (TP reuse)
- [ ] Stateless run uses fresh sessions per position (cold TP)
- [ ] Both runs evaluate identical positions at `maxdepth: 8`
- [ ] Per-move and total timing comparison printed in table format
- [ ] Speedup ratio displayed
- [ ] No new pip dependencies (use throwaway-session approach)

## Out of Scope

- Pass/fail assertions (this is a knowledge benchmark, not a test)
- Graphical output or file export
- Testing multiple depths or starting positions (can be added later)
- Adding new API endpoints to support this benchmark

## Open Questions

- Should we run multiple iterations of the full benchmark and average? (Probably not needed for a first pass — engine search is mostly deterministic at fixed depth.)
- If the speedup is negligible, does that change any architectural decisions? (Probably not — sessions have value beyond TP reuse: simpler client code, position tracking, etc.)

## Related

- Existing perf benchmark: `tests/test_performance.py`
- Session tests: `tests/test_session.py`
- Spec: `docs/specs/stateful-sessions.md`
