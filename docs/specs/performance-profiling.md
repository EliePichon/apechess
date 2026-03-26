# Performance Profiling: Flame Graphs + Real-Time Timing

## Context

After a code quality refactoring phase, the priority shifts to performance. The engine has no profiling infrastructure — we know *how long* searches take (wall-clock in tests) but not *where* time is spent. This plan adds two complementary tools:
1. **Flame graphs** (py-spy) — visual breakdown of CPU time across the call stack during real HTTP requests
2. **Lightweight instrumentation** — per-move timing counters exposed via the existing stats endpoint

## Step 1: Docker setup for py-spy

**Files:** `docker-compose.yml`, `Dockerfile.local`

- `Dockerfile.local`: Add `RUN pip install py-spy` after the requirements install
- `docker-compose.yml`:
  - Add `cap_add: [SYS_PTRACE]` (required for py-spy to attach to the Flask process)
  - Add volume mount `./profiles:/usr/src/app/profiles` for flame graph output
  - Add `SUNFISH_PERF=0` env var (toggle for fine-grained counters)

## Step 2: Profiling script

**New file:** `scripts/profile_game.py`

A script that plays a standardized game scenario via HTTP (5-6 positions across opening/midgame/endgame, depth 12, top_n=3). This generates sustained CPU load for py-spy to sample. Runs in ~30-60s.

## Step 3: Makefile targets

**File:** `Makefile`

Add three targets:
- `make profile` — runs py-spy in background inside Docker, executes the profiling script, outputs `profiles/flame.svg`
- `make profile-top` — live `py-spy top` view of the running server (interactive, for quick checks)
- `make profile-record DURATION=30` — raw py-spy recording for N seconds

## Step 4: Lightweight perf counters in Searcher

**File:** `sunfish.py` (lines 347-352, 431, 491-495)

Add flag-gated (`SUNFISH_PERF=1`) counters to the Searcher class:

- `__init__`: Add `self._perf = os.environ.get("SUNFISH_PERF") == "1"` and counter fields
- `search()`: Reset counters at search start
- `bound()` line 431: Time the `sorted(gen_moves + value)` expression — this is the single hottest line, where move generation and move ordering happen together

When `_perf=False`: one `if` check per `bound()` call (~50K checks = ~10us, <0.01% overhead).
When `_perf=True`: two `perf_counter` calls per gen_moves invocation (~1-3% overhead).

## Step 5: Coarse timing in engine.py

**File:** `engine.py` (lines 316-330 and `_search_best_moves`)

Always-on (3 `perf_counter` calls per request = negligible):
- Time `run_iterative_deepening()` duration
- Time `get_filtered_legal_moves()` duration
- Time `score_moves()` duration
- Record `searcher.nodes` count and final depth

Store as a `perf` dict returned alongside search results.

## Step 6: Expose via `/session/stats`

**File:** `engine.py` (`GameSession.stats()`)

Extend the existing stats dict with perf data when `SUNFISH_PERF=1`:
- `gen_moves_calls`, `gen_moves_time_ms`, `nodes` from the Searcher
- Last search timing from the coarse engine.py instrumentation

No new endpoint needed.

## Step 7: Housekeeping

- Add `profiles/` to `.gitignore`
- Create empty `scripts/` directory with the profiling script

## Verification

1. `make down && make up` (rebuild with py-spy)
2. `make profile` — should produce `profiles/flame.svg`, open in browser
3. `SUNFISH_PERF=1` in docker-compose → `make up` → play a game via `/turn` → `GET /session/stats` should show timing data
4. `make test` — all existing tests still pass (no behavior changes)
