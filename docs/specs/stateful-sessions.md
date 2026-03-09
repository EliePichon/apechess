# Stateful Game Sessions — Implementation Plan

**Branch**: `feat/stateful-sessions`
**Status**: In progress

## Overview

Replace the fully stateless API with a session-based architecture where the backend holds game positions. Frontend sends moves instead of full FENs. Searcher's `tp_move` table persists across turns for ~15-30% faster searches.

## New Game Loop

```
1. POST /newgame  { fen: "..." }           → { session_id: "abc123" }
2. POST /bestmove { session_id: "abc123" }  → { bestmoves: [...], clutchness: 23 }
   (or /evalmoves for player turn)
3. POST /move     { session_id: "abc123", move: "e2e4" }
   → Computer turn: auto-computes bestmoves + clutchness
   → Player turn:   just confirms + check status
4. Repeat
```

Any request can include optional `fen` to override/re-sync the session position.

## New Features

- **Clutchness**: eval gap between best and 2nd-best move (how critical the turn is)
- **Per-move evals** (`/evalmoves`): all legal moves with scores, grouped by source square
- **Session management**: server-generated IDs, 30-min auto-expire, tp_move cap at 100K

## Implementation Steps

### Step 1: GameSession class + session store in engine.py
- `GameSession` class: holds Searcher, position history, thread lock
- Session store: `_sessions` dict with create/get/cleanup helpers
- Auto-expire (30 min), tp_move size cap (100K)
- Server-generated UUID session IDs

### Step 2: Refactor get_best_moves() for dual mode
- Session mode: uses session's position + Searcher
- Stateless mode: unchanged behavior (backward-compatible)
- Optional `session_id` and `clutchness` params

### Step 3: Clutchness in _search_best_moves()
- Compute eval gap between top 2 moves before trimming to top_n
- When clutchness requested with top_n=1, skip fast path → use multi-move eval with internal top_n=2
- Return in result dict, propagate to API response

### Step 4: get_evaluated_moves() in engine.py
- Runs search to populate TT, then scores each legal move via TT/shallow bound
- Groups by source square with eval scores
- Includes clutchness
- Session or stateless mode

### Step 5: apply_move() in engine.py
- Validates move legality
- Applies move to session position
- Auto-computes bestmoves on computer turns
- FEN override for re-sync

### Step 6: Server endpoints
- POST /newgame → { session_id }
- POST /move → { status, check, [bestmoves, clutchness] }
- POST /evalmoves → { moves: {square: [{move, eval}]}, check, clutchness }
- GET /session/stats → debug info
- Extend /bestmove with session_id + clutchness
- CORS updates

### Step 7: Tests
- tests/test_session.py — integration tests covering full workflow

### Step 8: Makefile + CLAUDE.md
- test-session target
- Documentation updates

## Sync / Resilience

| Risk | Mitigation |
|------|------------|
| Frontend sends invalid move | /move validates legality, returns error, position unchanged |
| Message lost | Frontend sends fen override on next request to re-sync |
| Server restart | Sessions lost, frontend re-creates via /newgame with current FEN |
| Undo | Send request with fen override to set position to any prior state |
| Abandoned sessions | Auto-expire after 30 min, tp_move capped at 100K |

## Files Modified

| File | Changes |
|------|---------|
| `engine.py` | GameSession, session store, dual-mode get_best_moves, clutchness, get_evaluated_moves, apply_move |
| `server.py` | /newgame, /move, /evalmoves, /session/stats, extended /bestmove, CORS |
| `tests/test_session.py` | New integration tests |
| `Makefile` | test-session target |
| `CLAUDE.md` | New API documentation |
| `sunfish.py` | NOT modified |
