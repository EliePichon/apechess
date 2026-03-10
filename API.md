# Sunfish Chess Engine — API Documentation

Base URL: `http://localhost:5500`

## Quick Start (Dream API)

```bash
# 1. Start a game
curl -X POST /newgame -d '{}'
# → { "session_id": "a3f8b2c1d4e5" }

# 2. Opponent (computer) plays with peek_next — one call does everything
curl -X POST /turn -d '{ "session_id": "a3f8b2c1d4e5", "maxdepth": 8, "peek_next": true }'
# → { "move": "g1f3", "eval": 32, "check": false, "game_over": null,
#     "next": { "legal_moves": {"e7": ["e7e5", "e7e6"], ...}, "check": false, "clutchness": 42, "best_eval": 38 } }

# 3. Player moves (with grading + peek for next turn)
curl -X POST /move -d '{ "session_id": "a3f8b2c1d4e5", "move": "e7e5", "grade": true, "peek_next": true }'
# → { "status": "ok", "check": false, "game_over": null,
#     "grade": { "player_eval": 30, "best_eval": 38, "best_move": "e7e6", "accuracy": 0.96 },
#     "next": { "legal_moves": {...}, "check": false, "clutchness": 8, "best_eval": -12 } }

# 4. Next computer turn — repeat
curl -X POST /turn -d '{ "session_id": "a3f8b2c1d4e5", "maxdepth": 8, "peek_next": true }'
```

---

## Three Modes of Operation

### Dream API (recommended)

Computer turns = `/turn`. Player turns = `/move`. That's it. Two endpoints for the entire game loop.

`/turn` searches for the best move, applies it, and optionally pre-computes the next position's legal moves + clutchness via `peek_next`. This enables **instant puzzle triggers** — no follow-up API call needed.

**Workflow:**
1. `POST /newgame` to create a session
2. `POST /turn` for computer turns (with `peek_next: true`)
3. `POST /move` for player turns (with `grade` and/or `peek_next`)

### Session-based (legacy)

The backend holds the game position. The frontend sends moves, not FENs. The engine's transposition tables persist across turns, giving ~15-30% faster searches.

**Workflow:**
1. `POST /newgame` to create a session
2. Use `session_id` on all subsequent calls
3. `POST /move` to advance the game
4. `POST /evalmoves` or `POST /bestmove` to get analysis

### Stateless (legacy)

Every request includes the full FEN string. No state persists between calls. All original endpoints still work this way when `session_id` is omitted.

---

## Endpoints

### POST /newgame

Create a new game session.

**Request:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `fen` | string | No | Standard starting position | FEN string for the initial position |

**Response:**

```json
{ "session_id": "a3f8b2c1d4e5" }
```

**Notes:**
- Session IDs are server-generated (12-char hex strings)
- Sessions auto-expire after 30 minutes of inactivity

---

### POST /turn

Computer plays a turn. Searches for the best move, applies it to the session, detects game state, and optionally pre-computes the next position's legal moves + clutchness.

**Request:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `session_id` | string | Yes | — | Session to play on |
| `maxdepth` | int | No | `15` | Maximum search depth |
| `movetime` | int | No | — | Time limit in milliseconds |
| `precision` | float | No | `0.0` | Randomness factor. `0.0` = deterministic/strongest |
| `top_n` | int | No | `1` | Number of candidate moves to evaluate internally |
| `ignore_squares` | string[] | No | `[]` | Squares whose pieces cannot move |
| `peek_next` | bool | No | `false` | Pre-compute next position's legal moves + clutchness |
| `peek_maxdepth` | int | No | `5` | Search depth for the peek (keep shallow for speed) |
| `fen` | string | No | — | Override session position before playing (re-sync/undo) |
| `moves` | string | No | `""` | Space-separated move history to replay after FEN override |

**Response:**

```json
{
  "move": "g1f3",
  "eval": 32,
  "check": false,
  "game_over": null,
  "ply": 3,
  "next": {
    "legal_moves": {
      "e7": ["e7e5", "e7e6"],
      "g8": ["g8f6", "g8h6"]
    },
    "check": false,
    "clutchness": 42,
    "best_eval": 38
  }
}
```

| Field | Description |
|-------|-------------|
| `move` | The move the engine chose and applied. `null` if no legal moves. |
| `eval` | Score of the chosen move in centipawns |
| `check` | Whether the move gives check |
| `game_over` | `null`, `"checkmate"`, or `"stalemate"` — detected server-side |
| `ply` | Number of positions in the session history (for tracking move number) |
| `next` | Only present when `peek_next: true` and `game_over` is `null` |
| `next.legal_moves` | Legal moves for the next side to move (grouped by source square) |
| `next.check` | Whether the next side to move is in check |
| `next.clutchness` | Clutchness of the next position (shallow search) |
| `next.best_eval` | Eval of the best move in the next position |

**Notes:**
- The `peek_next` shallow search adds ~50-150ms to the response — negligible compared to the main search
- When `game_over` is not `null`, there is no `next` block (no legal moves to show)
- The transposition table from the main search is reused for the peek, making it even cheaper

**Errors:**

| Status | Cause |
|--------|-------|
| 400 | Missing fields |
| 404 | Invalid or expired session_id |

---

### POST /move

Apply a move to a session. Supports two modes:
- **Dream API** (when `grade` or `peek_next` is set): grades the move, detects game state, peeks ahead
- **Legacy** (neither set): original behavior with optional `computer_turn`

**Request:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `session_id` | string | Yes | — | Session to apply the move to |
| `move` | string | Yes | — | Move in coordinate notation (e.g. `"e2e4"`, `"e7e8q"` for promotion) |
| `grade` | bool | No | `false` | Evaluate how good the player's move was vs the best move |
| `grade_maxdepth` | int | No | `8` | Search depth for grading |
| `peek_next` | bool | No | `false` | Pre-compute next position's legal moves + clutchness |
| `peek_maxdepth` | int | No | `5` | Search depth for the peek |
| `computer_turn` | bool | No | `false` | *(Legacy)* Auto-compute bestmoves + clutchness after applying |
| `maxdepth` | int | No | `15` | *(Legacy)* Search depth for auto-compute |
| `movetime` | int | No | — | *(Legacy)* Time limit in milliseconds for auto-compute |
| `fen` | string | No | — | Override session position before applying the move |
| `moves` | string | No | `""` | Space-separated move history to replay after FEN override |

**Response (Dream API — grade + peek_next):**

```json
{
  "status": "ok",
  "check": true,
  "game_over": null,
  "ply": 2,
  "grade": {
    "player_eval": 12,
    "best_eval": 45,
    "best_move": "e7e6",
    "accuracy": 0.84
  },
  "next": {
    "legal_moves": { "g1": ["g1f3"] },
    "check": false,
    "clutchness": 8,
    "best_eval": -12
  }
}
```

| Field | Description |
|-------|-------------|
| `grade.player_eval` | Eval of the move the player chose |
| `grade.best_eval` | Eval of the objectively best move |
| `grade.best_move` | What the best move was |
| `grade.accuracy` | `0.0` to `1.0` — how close to the best move (see [Grade Accuracy](#grade-accuracy)) |
| `next.*` | Same as `/turn` peek — legal moves + clutchness for the next side |

**Response (Legacy — player turn):**

```json
{
  "status": "ok",
  "check": false
}
```

**Response (Legacy — computer turn):**

```json
{
  "status": "ok",
  "check": false,
  "bestmoves": [["g1f3", 32]],
  "clutchness": 12
}
```

**Notes:**
- When `grade` or `peek_next` is set, the response includes `game_over` (Dream API path)
- When neither is set, the original legacy behavior is used (backward compatible)
- Grading runs before the move is applied (needs pre-move position for accurate comparison)

**Errors:**

| Status | Cause |
|--------|-------|
| 400 | Illegal move, missing fields |
| 404 | Invalid or expired session_id |

---

### POST /evalmoves

Get all legal moves with an evaluation score for each. Runs a search to populate the transposition table, then scores every legal move.

**Request:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `session_id` | string | One of these | — | Session to analyze |
| `fen` | string | required | — | FEN string (stateless mode) |
| `maxdepth` | int | No | `8` | Search depth |
| `movetime` | int | No | — | Time limit in milliseconds |
| `moves` | string | No | `""` | Space-separated move history (used with `fen`) |

**Response:**

```json
{
  "moves": {
    "e2": [
      { "move": "e2e4", "eval": 45 },
      { "move": "e2e3", "eval": 12 }
    ],
    "g1": [
      { "move": "g1f3", "eval": 38 },
      { "move": "g1h3", "eval": -15 }
    ]
  },
  "check": false,
  "clutchness": 7
}
```

**Notes:**
- Moves are grouped by source square
- Within each square, moves are sorted by eval (best first)
- `clutchness` is always included (eval gap between the best and 2nd-best move across all squares)

---

### POST /bestmove

Get the engine's best move(s) for the current position.

**Request:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `session_id` | string | One of these | — | Session to analyze |
| `fen` | string | required | — | FEN string (stateless mode) |
| `maxdepth` | int | No | `15` | Maximum search depth |
| `movetime` | int | No | — | Time limit in milliseconds |
| `precision` | float | No | `0.0` | Randomness factor. `0.0` = deterministic/strongest. `0.1`-`0.3` = weaker, more varied play |
| `top_n` | int | No | `1` | Number of top moves to return with scores |
| `ignore_squares` | string[] | No | `[]` | List of squares whose pieces should not be moved (e.g. `["e2", "g1"]`) |
| `moves` | string | No | `""` | Space-separated move history |
| `clutchness` | bool | No | `false` | Include clutchness metric in response |

**Response:**

```json
{
  "bestmoves": [["e2e4", 45], ["d2d4", 38]],
  "check": false,
  "depth_reached": 12,
  "clutchness": 7
}
```

**Notes:**
- `bestmoves` is an array of `[move_string, score]` pairs, sorted best-first
- `clutchness` only appears when requested via the `clutchness` parameter
- `precision` adds multiplicative randomness to move scores — it makes the engine weaker, not smarter
- When using `session_id`, the engine reuses its transposition tables from previous searches, improving speed

---

### POST /getmoves

Get all legal moves for the current position (no evaluation scores).

**Request:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `fen` | string | Yes | — | FEN string |

**Response:**

```json
{
  "moves": {
    "e2": ["e2e4", "e2e3"],
    "g1": ["g1f3", "g1h3"]
  },
  "check": false
}
```

---

### POST /ischeck

Check if the active player is currently in check.

**Request:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `fen` | string | Yes | — | FEN string |

**Response:**

```json
{ "check": true }
```

---

### GET /session/stats

Debug endpoint for inspecting session state.

**Query parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | Yes | Session to inspect |

**Response:**

```json
{
  "tp_move_size": 4523,
  "tp_score_size": 0,
  "ply": 5
}
```

| Field | Description |
|-------|-------------|
| `tp_move_size` | Number of entries in the move ordering table (persists across searches) |
| `tp_score_size` | Number of entries in the score bounds table (cleared each search) |
| `ply` | Number of positions in the game history |

---

### GET /health

Health check.

**Response:**

```json
{ "status": "ok" }
```

---

## Key Concepts

### Clutchness

The eval gap between the best move and the second-best move. A high clutchness means the position is critical — there's one clearly best move and the others are significantly worse. A low clutchness means several moves are roughly equally good.

Available on:
- `/turn` — in the `next` block when `peek_next: true`
- `/move` — in the `next` block when `peek_next: true`, or with `computer_turn: true` (legacy)
- `/bestmove` — when `clutchness: true` is set
- `/evalmoves` — always included

### Grade Accuracy

The accuracy score on `/move` (when `grade: true`) measures how close the player's move was to the engine's best:

```
eval_gap = max(0, best_eval - player_eval)
accuracy = max(0.0, 1.0 - eval_gap / 200)
```

Rounded to 2 decimal places. Scale: `1.0` = optimal move, `0.0` = 200+ centipawns worse than the best.

### FEN Override (Re-sync)

Any endpoint that accepts `session_id` also accepts an optional `fen` field. When provided, the session position is replaced with the given FEN before processing the request. Use this for:

- **Undo**: Set the position back to a previous state
- **Re-sync**: If the frontend and backend get out of sync (e.g. after a network error)
- **Analysis**: Jump to an arbitrary position without creating a new session

### Session Lifecycle

| Event | Behavior |
|-------|----------|
| `POST /newgame` | Creates a new session, returns `session_id` |
| Any request with `session_id` | Refreshes the session's expiry timer |
| 30 minutes of inactivity | Session is automatically deleted |
| Server restart | All sessions are lost — frontend should detect 404 and call `/newgame` again |
| Transposition table > 100K entries | Table is cleared automatically (rebuilds within 1-2 searches) |

### Move Format

Moves use coordinate notation: source square + destination square + optional promotion piece.

| Example | Meaning |
|---------|---------|
| `e2e4` | Pawn from e2 to e4 |
| `g1f3` | Knight from g1 to f3 |
| `e7e8q` | Pawn promotes to queen |
| `e1g1` | King-side castling |

### Eval Scores

Scores are in centipawns (1 pawn = 100). Positive means the side to move is ahead. Scores above 50000 or below -50000 indicate forced mate.

---

## Typical Workflows

### Game Loop with Puzzles (Dream API)

```
POST /newgame                                        → session_id

# Opponent turn — computer plays, peeks ahead
POST /turn { session_id, maxdepth: 12,
             peek_next: true }                       → move + next.legal_moves + next.clutchness

# Decision: is next.clutchness high enough for a puzzle?
#   YES → show legal_moves instantly (already have them), player moves
#   NO  → auto-play for the player with another /turn

# Player puzzle — player moves, grade + peek for next turn
POST /move { session_id, move: "e7e5",
             grade: true, peek_next: true }          → grade + next.legal_moves + next.clutchness

# Next opponent turn — repeat
POST /turn { session_id, maxdepth: 12,
             peek_next: true }                       → ...
```

**Round-trip comparison:**

| Scenario | Legacy API | Dream API |
|----------|-----------|-----------|
| Opponent turn + puzzle trigger | 3-4 calls | **1 call** (`/turn` with peek) |
| Player puzzle (show board) | 1 call (`/getmoves`) | **0 calls** (pre-fetched) |
| Full puzzle cycle | 5 calls | **2 calls** |
| Full auto turn | 3 calls | **1 call** |

### Player vs Engine (Legacy)

```
POST /newgame                                    → session_id
POST /evalmoves { session_id, maxdepth: 8 }      → show player their options
POST /move { session_id, move: "e2e4" }          → player moves
POST /move { session_id, move: "e7e5",           → opponent moves, engine
             computer_turn: true, maxdepth: 10 }    auto-computes response
POST /evalmoves { session_id, maxdepth: 8 }      → show player options again
... repeat ...
```

### Engine vs Engine

```
POST /newgame                                    → session_id
POST /turn { session_id, maxdepth: 12 }          → white plays
POST /turn { session_id, maxdepth: 12 }          → black plays
POST /turn { session_id, maxdepth: 12 }          → white plays
... repeat until game_over is not null ...
```

### Analysis (stateless)

```
POST /bestmove { fen: "...", maxdepth: 15, top_n: 5, clutchness: true }
POST /evalmoves { fen: "...", maxdepth: 10 }
POST /getmoves { fen: "..." }
POST /ischeck { fen: "..." }
```

---

## Error Handling

All errors return JSON with an `error` field:

```json
{ "error": "Illegal move: e1e5" }
```

| Status Code | Meaning |
|-------------|---------|
| 200 | Success |
| 400 | Bad request (missing fields, invalid FEN, illegal move) |
| 404 | Session not found or expired |
| 500 | Internal server error |

When a session-based request gets a 404, the frontend should call `/newgame` with the current FEN to create a fresh session.
