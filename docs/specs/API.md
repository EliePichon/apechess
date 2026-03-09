# Sunfish Chess Engine — API Documentation

Base URL: `http://localhost:5500`

## Quick Start

```bash
# 1. Start a game
curl -X POST /newgame -d '{}'
# → { "session_id": "a3f8b2c1d4e5" }

# 2. Get evaluated moves for the player
curl -X POST /evalmoves -d '{ "session_id": "a3f8b2c1d4e5", "maxdepth": 8 }'
# → { "moves": { "e2": [{"move": "e2e4", "eval": 45}, ...] }, "check": false, "clutchness": 5 }

# 3. Player chooses e2e4
curl -X POST /move -d '{ "session_id": "a3f8b2c1d4e5", "move": "e2e4" }'
# → { "status": "ok", "check": false }

# 4. Opponent plays e7e5, engine auto-computes its response
curl -X POST /move -d '{ "session_id": "a3f8b2c1d4e5", "move": "e7e5", "computer_turn": true, "maxdepth": 8 }'
# → { "status": "ok", "check": false, "bestmoves": [["g1f3", 32]], "clutchness": 12 }
```

---

## Two Modes of Operation

### Session-based (recommended)

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

### POST /move

Apply a move to a session. On computer turns, automatically computes and returns the engine's best response.

**Request:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `session_id` | string | Yes | — | Session to apply the move to |
| `move` | string | Yes | — | Move in coordinate notation (e.g. `"e2e4"`, `"e7e8q"` for promotion) |
| `computer_turn` | bool | No | `false` | If `true`, auto-computes bestmoves + clutchness after applying the move |
| `maxdepth` | int | No | `15` | Search depth for auto-compute (only used when `computer_turn` is `true`) |
| `movetime` | int | No | — | Time limit in milliseconds for auto-compute |
| `fen` | string | No | — | Override session position before applying the move (for re-sync or undo) |
| `moves` | string | No | `""` | Space-separated move history to replay after FEN override |

**Response (player turn):**

```json
{
  "status": "ok",
  "check": false
}
```

**Response (computer turn):**

```json
{
  "status": "ok",
  "check": false,
  "bestmoves": [["g1f3", 32]],
  "clutchness": 12
}
```

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
- `/bestmove` — when `clutchness: true` is set
- `/evalmoves` — always included
- `/move` — included when `computer_turn: true`

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

### Player vs Engine

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
POST /bestmove { session_id, maxdepth: 12 }      → white's move
POST /move { session_id, move: "<white_move>",
             computer_turn: true, maxdepth: 12 } → apply + get black's response
POST /move { session_id, move: "<black_move>",
             computer_turn: true, maxdepth: 12 } → apply + get white's response
... repeat ...
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
