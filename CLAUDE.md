# Sunfish Chess Engine - Project Documentation

## Overview
This is a fork of the open-source Sunfish chess engine, modified to work as a REST API backend for a chess game. Sunfish is a compact but strong chess engine (~131 lines of core code) written in Python, playing at 2000+ rating on Lichess.

## Project Purpose
The REST API provides three main functionalities for a chess game:
1. List all available legal moves for a position
2. Check if a board state is in check
3. Return the N best moves with scores for a given position

## Architecture

### Core Components

#### 1. `sunfish.py` - Chess Engine Core
- **Search Algorithm**: MTD-bi (also known as C*) - a memory-enhanced variant of alpha-beta search
- **Board Representation**: 120-character string (10x12 mailbox with padding for fast boundary detection)
- **Evaluation**: Piece-Square Tables (PST) for position evaluation
- **Key Classes**:
  - `Position`: Named tuple representing game state (board, score, castling rights, en passant, king passant)
  - `Move`: Named tuple (i, j, prom) for source square, destination square, and promotion piece
  - `Searcher`: Search algorithm implementation with transposition table

#### 2. `server.py` - Flask REST API
- **Framework**: Flask with CORS enabled
- **Port**: 5500
- **Architecture Pattern**: Threading model with UCI sessions
- **Key Design**: Each API call spawns a new UCI session in a separate thread

#### 3. `tools/uci.py` - UCI Protocol Interface
- Handles Universal Chess Interface protocol
- Bridges between REST API and chess engine
- Manages position parsing from FEN strings
- Coordinate transformation for black/white perspective

### Board Representation Details

#### Coordinate System
- 120-character string: 10x12 board with 2-row padding on all sides
- Key coordinates:
  - `A1 = 91` (white's queen rook starting position)
  - `H1 = 98` (white's king rook starting position)
  - `A8 = 21` (black's queen rook starting position)
  - `H8 = 28` (black's king rook starting position)
- Padding allows fast illegal move detection (moves going off-board hit spaces/newlines)

#### Board Layout
```
         \n  (0-9)
         \n  (10-19)
 rnbqkbnr\n  (20-29) - Rank 8
 pppppppp\n  (30-39) - Rank 7
 ........\n  (40-49) - Rank 6
 ........\n  (50-59) - Rank 5
 ........\n  (60-69) - Rank 4
 ........\n  (70-79) - Rank 3
 PPPPPPPP\n  (80-89) - Rank 2
 RNBQKBNR\n  (90-99) - Rank 1
         \n  (100-109)
         \n  (110-119)
```

#### Piece Representation
- **Uppercase** = White pieces (P, N, B, R, Q, K)
- **Lowercase** = Black pieces (p, n, b, r, q, k)
- **Dot** (.) = Empty square
- **Space/Newline** = Padding (off-board)

### Position Perspective Convention
**Critical**: The engine always works from white's perspective (uppercase pieces at bottom).
- When it's white's turn: board is as-is
- When it's black's turn: board is rotated (flipped 180°) using `Position.rotate()`
- Coordinate flipping formula: `flipped_coord = 119 - coord`

## REST API Endpoints

### 1. POST `/getmoves`
Lists all legal moves for the current position.

**Request**:
```json
{
  "fen": "<fen_string>"
}
```

**Response**:
```json
{
  "moves": {
    "e2": ["e2e4", "e2e3"],
    "g1": ["g1f3", "g1h3"],
    ...
  },
  "check": true/false
}
```

**Implementation Notes**:
- Parses side to move from FEN (field 1)
- Creates UCI session to set position
- Iterates through all pieces of the current player
- Filters to legal moves (excludes moves that leave king in check)
- Flips coordinates back if side to move is black

### 2. POST `/bestmove`
Returns the best move(s) for current position with evaluation.

**Request**:
```json
{
  "fen": "<fen_string>",
  "movetime": <milliseconds>,    // optional
  "maxdepth": <int>,              // optional (default: 8)
  "precision": <float>,           // optional (default: 0)
  "top_n": <int>,                 // optional (default: 1)
  "ignore_squares": ["e2", "g1"], // optional, squares to ignore
  "moves": "<move_history>"       // optional, space-separated moves
}
```

**Response**:
```json
{
  "bestmoves": [
    ["e2e4", 45],
    ["d2d4", 42],
    ["g1f3", 38],
    ["b1c3", 35]
  ],
  "check": false
}
```

**Implementation Notes**:
- Tracks move history to determine effective side (white/black)
- Uses iterative deepening search for best move
- **top_n parameter**: Number of moves to return in `bestmoves` array (default: 1)
  - `top_n=1`: Fast path, returns only best move (zero overhead)
  - `top_n>1`: Returns top N moves with TT + shallow search evaluation
- **ignore_squares parameter**: List of squares whose pieces should be ignored (e.g., `["e2", "g1"]`)
  - Useful for training mode, puzzles, or analysis
  - Filters out all moves originating from specified squares
  - Best move automatically switches to next best if ignored
- Returns moves in `bestmoves` array, sorted by **search-based scores** (not static eval)
- Array length always equals `top_n`
- Access best move as `bestmoves[0][0]`, best score as `bestmoves[0][1]`
- **Precision parameter**: Adds artificial noise to weaken the engine (see Precision Parameter section below)
- See "Top-N Move Evaluation" and "Ignore Squares" sections for implementation details

### 3. POST `/ischeck`
Checks if the active player is currently in check.

**Request**:
```json
{
  "fen": "<fen_string>"
}
```

**Response**:
```json
{
  "check": true/false
}
```

**Implementation Notes**:
- Uses `can_kill_king()` helper function
- Checks if opponent can capture king in next move

## Advanced Architecture Details

### The Precision Parameter: Artificial Weakening

The `precision` parameter is a mechanism to make the engine deliberately less strong by adding randomness to move evaluation.

**How it works**:
1. Client sends precision value (e.g., 0.1) in `/bestmove` request
2. Server passes it to UCI via `go` command: `go depth 8 precision 0.1`
3. UCI sets it on the Searcher: `setattr(searcher, 'precision', float(precision))`
4. During position evaluation in `Position.value()`, the precision is applied:

```python
# sunfish.py:266-268
if hasattr(self, 'searcher') and self.searcher.precision > 0.0:
    factor = random.uniform(1 - self.searcher.precision, 1 + self.searcher.precision)
    score = int(score * factor)
```

**Effect**:
- `precision = 0.0`: Deterministic, full strength
- `precision = 0.1`: Score multiplied by random factor between 0.9 and 1.1 (±10%)
- `precision = 0.3`: Score multiplied by random factor between 0.7 and 1.3 (±30%)

This randomness causes the engine to:
- Misjudge move values
- Potentially choose suboptimal moves
- Play more "human-like" (inconsistent)
- Be easier to beat

**Use cases**: Adjustable difficulty levels, testing, making the engine less predictable.

### Callback Mechanism: Wrapping CLI as REST

The original Sunfish engine was designed as a **CLI program** that communicates via the UCI (Universal Chess Interface) protocol:
- Reads commands from **stdin** (e.g., "position fen ...", "go depth 8")
- Writes responses to **stdout** (e.g., "bestmove e2e4")

The REST API needed to reuse this CLI interface without rewriting it. The solution is an elaborate wrapping mechanism.

**The Problem**:
- Flask REST API needs to call the engine programmatically
- Engine expects interactive stdin/stdout
- Need to capture internal Python objects (Position, moves list), not just text output

**The Solution - `run_uci_session()` in server.py**:

1. **BlockingInput Class** (lines 23-37):
   - Wraps a `queue.Queue()` to simulate stdin
   - `write(data)`: Puts data in queue (simulates typing a command)
   - `readline()`: Gets data from queue (simulates engine reading input)
   - Allows REST API to "type" UCI commands programmatically

2. **Thread Isolation** (lines 56-68):
   ```python
   def uci_loop():
       sys.stdin = input_stream      # Redirect stdin to our fake input
       sys.stdout = output_stream     # Redirect stdout to StringIO
       uci.run(sunfish, startpos, callbackPos=..., callbackMove=...)
   ```
   - Runs in separate thread to avoid blocking Flask
   - Redirects `sys.stdin` to BlockingInput
   - Redirects `sys.stdout` to StringIO (captures output)

3. **Callback Holder** (line 53):
   ```python
   callback_holder = {"position": None, "moves": None}
   ```
   - UCI protocol only outputs text (e.g., "bestmove e2e4")
   - But REST API needs actual Python objects (Position, list of moves)
   - Callbacks update this dict with internal state:
     - `callbackPos`: Captures Position object after "position fen" command
     - `callbackMove`: Captures scored moves list after search completes

4. **Command Injection** (lines 74-75):
   ```python
   for cmd in commands:
       input_stream.write(cmd + "\n")  # "Type" commands into fake stdin
   ```

5. **Response Polling** (lines 77-92):
   - Continuously reads from `output_stream` to capture text responses
   - When expected response appears (e.g., "bestmove"), stops and returns
   - Returns both text output AND callback_holder with Python objects

**Data Flow**:
```
REST Request → run_uci_session() → BlockingInput (fake stdin)
                                 ↓
                            uci.run() reads commands
                                 ↓
                            Engine processes
                                 ↓
                   ┌─────────────┴──────────────┐
                   ↓                            ↓
           StringIO (fake stdout)      callback_holder dict
              "bestmove e2e4"           {position: Position(...),
                                         moves: [("e2e4", 100), ...]}
                   ↓                            ↓
                   └─────────────┬──────────────┘
                                 ↓
                     Return to REST endpoint
```

**Why This Design**:
- **Reuse**: Doesn't require rewriting UCI protocol implementation
- **Isolation**: Each REST call gets fresh UCI session (no state bleeding)
- **Flexibility**: Can capture both text output AND internal objects
- **Compatibility**: Original CLI interface still works unchanged

### Top-N Move Evaluation: High-Quality Multi-Move Ranking

The `/bestmove` endpoint returns not just the best move, but a ranked list of top moves. The challenge is providing **high-quality scores** for multiple moves without excessive computation time.

**The Problem with Naive Approaches**:
- **Static eval only** (old): Fast but inaccurate (just PST differences)
- **Full-depth all moves**: Accurate but 300-500% slower
- **Need**: Search-based scores with reasonable overhead

**The Solution: TT + Shallow Search with Fast Path**

The implementation uses a two-tier strategy:

**1. Fast Path for top_n=1** (tools/uci.py:97-113):
```python
if top_n == 1:
    best_move_obj = searcher.tp_move.get(hist[-1])  # Already found by main search
    # Extract from PV or TT, zero additional computation
    scored_moves = [(move_str, score)]
```
- **Zero overhead**: Best move already found by iterative deepening
- **Same speed** as old implementation (or faster)

**2. Standard Path for top_n>1** (tools/uci.py:115-171):

Three-step process:

**Step A - Quick Screening (fast)**:
```python
for move in legal_moves:
    # Try TT lookup first (O(1))
    for check_depth in range(final_depth - 1, 0, -1):
        entry = searcher.tp_score.get((new_pos, check_depth, True))
        if entry:
            score = -((entry.lower + entry.upper) // 2)
            break
    # Fallback to static eval if not in TT
    if score is None:
        score = pos.value(move)
```
- All moves get quick scores (TT or static eval)
- ~3-5ms for 30-40 moves

**Step B - Candidate Selection**:
```python
quick_scored.sort(key=lambda x: x[2], reverse=True)
top_candidates = quick_scored[:top_n + 5]  # Buffer of +5
```
- Only top candidates proceed to deep evaluation
- Dramatically reduces shallow search count

**Step C - Deep Evaluation**:
```python
shallow_depth = max(3, final_depth - 3)
for move in top_candidates:
    # Check TT at high depth
    entry = searcher.tp_score.get((new_pos, final_depth - 1))
    if not entry:
        # Shallow search (depth-3)
        score = -searcher.bound(new_pos, 0, shallow_depth)
```
- First tries TT at high depth (many moves already there)
- Falls back to shallow search (depth-3) only if needed
- Much faster than full-depth search

**Performance Characteristics**:

| top_n | Moves Evaluated | Overhead | Use Case |
|-------|----------------|----------|----------|
| 1 | 1 (fast path) | 0% | Single best move only |
| 5 | 10 candidates | ~10-15% | Quick UI hints |
| 10 | 15 candidates | ~15-20% | Default, good balance |
| 20 | 25 candidates | ~25-30% | Detailed analysis |

**Why This Works**:

1. **TT already populated**: Main search fills TT with many positions
2. **Shallow depth sufficient**: depth-3 provides good move ordering
3. **Candidate pruning**: Only evaluate promising moves deeply
4. **Zero cost for top_n=1**: Fast path bypasses everything

**Quality vs Old Implementation**:

| Aspect | Old (Static Eval) | New (TT + Shallow) |
|--------|-------------------|-------------------|
| Accuracy | Poor (PST only) | Excellent (search-based) |
| Tactical awareness | None | Good (depth-3+) |
| Positional understanding | Basic | Very good |
| Time overhead | 0% | 0-30% (depends on top_n) |
| Best move quality | Same | Same (from main search) |

### Ignore Squares: Piece-Level Move Filtering

The `ignore_squares` parameter allows you to exclude specific pieces from move consideration, creating constrained search scenarios.

**Use Cases**:
1. **Training Mode**: Force players to develop specific pieces
2. **Puzzle Mode**: Create scenarios where only certain pieces can move
3. **Analysis**: "What's the best move if I can't use my queen?"
4. **Game Variants**: Implement rules that restrict piece movement

**How It Works** (tools/uci.py:88-118):

```python
# Step 1: Parse squares to indices
ignored_indices = set()
for square_str in ignore_squares:  # e.g., ["e2", "g1"]
    idx = sunfish.parse(square_str)  # Convert to board index
    if not white_pov:
        idx = 119 - idx  # Flip for black's perspective
    ignored_indices.add(idx)

# Step 2: Filter legal moves
legal_moves = [m for m in legal_moves if m.i not in ignored_indices]

# Step 3: Override bestmove if necessary
if bestmove_from in ignore_squares:
    bestmove = scored_moves[0][0]  # Use top allowed move
```

**Example API Usage**:

```bash
# Ignore both knights in starting position
curl -X POST http://localhost:5500/bestmove \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "maxdepth": 6,
    "ignore_squares": ["g1", "b1"]
  }'

# Response will exclude knight moves, return best pawn move instead
{
  "bestmoves": [
    ["d2d4", 33],
    ["e2e3", 22],
    ["d2d3", 13]
    // No g1f3 or b1c3
  ],
  "check": false
}
```

**Behavior Details**:

- **Filtering Stage**: Happens after legal move generation, before search
- **Complete Removal**: Ignored pieces are completely excluded from consideration
- **Best Move Override**: If PV best move is ignored, uses top scored move
- **Performance**: No significant overhead (just list filtering)
- **Coordinate System**: Handles white/black perspective automatically

**Edge Cases**:

1. **All moves ignored**: Returns `bestmove: (none)`
2. **Invalid square names**: Logged as warning, ignored gracefully
3. **Empty list**: No filtering applied
4. **Case insensitive**: "E2" and "e2" both work

**Implementation Notes**:

- Filtering happens in `go_loop()`, not in move generation
- Main search still runs normally on filtered move list
- All moves in `bestmoves` array respect the filter
- Compatible with all other parameters (`top_n`, `precision`, etc.)

### Stateless History Tracking

**Critical Understanding**: The REST API is **completely stateless**. There is NO persistent game state between API calls.

**How History Works**:

1. **Each UCI Session is Fresh** (server.py:39-98):
   - Every REST API call creates a new thread with `run_uci_session()`
   - Each thread creates a new UCI instance with fresh state
   - When thread finishes, all state is discarded

2. **History Initialization** (tools/uci.py:192):
   ```python
   def run(sunfish_module, startpos, ...):
       hist = [startpos]  # Fresh history for this UCI session
       searcher = sunfish.Searcher()  # Fresh searcher
   ```

3. **History Built from Request** (tools/uci.py:247-266):
   - Client sends FEN + optional moves history
   - UCI parses "position fen ... moves e2e4 e7e5 ..."
   - Builds history from scratch:
     ```python
     hist = [pos]  # Start from FEN position
     for move_str in args[9:]:  # Apply each move in sequence
         hist.append(hist[-1].move(parsed_move))
     ```

4. **Black Position Handling** (tools/uci.py:258-261):
   - For black FEN, history needs two entries for correct alternation:
   ```python
   if args[3] == 'b':  # Black to move
       hist = [pos.rotate(), pos]  # Two entries for alternation
   else:
       hist = [pos]  # White to move
   ```

**Implications**:

- **No Session Memory**: Engine doesn't "remember" previous positions
- **Client Responsibility**: Client must track full game state
- **Every Call Standalone**: Each request must provide complete position info
- **History in Request**: For move repetition detection, pass move history via `moves` parameter
- **Performance**: No optimization from remembered positions, but simpler and more RESTful

**Example Flow**:
```
Request 1: POST /bestmove {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}
→ Creates UCI session with fresh hist = [startpos]
→ Returns "e2e4"
→ Session destroyed

Request 2: POST /bestmove {"fen": "...", "moves": "e2e4"}
→ Creates NEW UCI session (doesn't know about Request 1)
→ Rebuilds hist = [startpos] → apply e2e4 → [startpos, pos_after_e2e4]
→ Returns next best move
→ Session destroyed
```

**Advantages of Stateless Design**:
- **Simplicity**: No session management, no state synchronization
- **Scalability**: Easy to load balance across multiple servers
- **Reliability**: No stale state, no memory leaks
- **RESTful**: True REST principles

**Disadvantages**:
- **Repetition**: Must rebuild history on every call
- **No Optimization**: Can't reuse transposition table across requests
- **Client Complexity**: Client must maintain full game state

## Key Functions & Helpers

### `sunfish.py`

#### `Position.gen_moves()`
Generator that yields all pseudo-legal moves (may include moves that leave king in check).

#### `Position.get_legal_moves(square=None)`
Returns list of legal moves, optionally filtered by starting square. Filters out moves that would leave king in check.

#### `Position.move(move)`
Applies a move and returns new position (rotated for opponent).

#### `Position.rotate(nullmove=False)`
Flips board 180° and swaps colors. Used to switch perspective between players.

#### `Position.value(move)`
Calculates the value/score of a move using piece-square tables.

#### `Searcher.bound(pos, gamma, depth, can_null=True)`
Core search function using MTD-bi algorithm. Returns score bound for position.

#### `Searcher.search(history)`
Iterative deepening search. Yields depth, gamma, score, and best move at each iteration.

### `tools/uci.py`

#### `from_fen(board, color, castling, enpas, hclock, fclock)`
Parses FEN string into Position object.

#### `parse_move(move_str, white_pov)`
Converts UCI move string (e.g., "e2e4") to Move object. Handles perspective flipping.

#### `render_move(move, white_pov)`
Converts Move object to UCI string notation.

#### `can_kill_king(pos)`
Returns True if current player can capture opponent's king (indicates illegal position).

#### `go_loop(searcher, hist, stop_event, max_movetime, max_depth, ...)`
Main search loop. Runs iterative deepening and returns best move.

### `server.py`

#### `run_uci_session(commands, expected_response, timeout)`
Creates isolated UCI session in thread, sends commands, captures output.
- Uses `BlockingInput` for thread-safe input simulation
- Captures position and moves via callback mechanism
- Returns response lines and callback holder with position/moves data

## Coding Conventions & Patterns

### Coordinate Handling
```python
# Parse algebraic notation to board index
def parse(c):
    fil, rank = ord(c[0]) - ord("a"), int(c[1]) - 1
    return A1 + fil - 10 * rank

# Convert board index to algebraic notation
def render(i):
    rank, fil = divmod(i - A1, 10)
    return chr(fil + ord("a")) + str(-rank + 1)
```

### Direction Vectors
Movement directions are defined as offsets:
- `N = -10` (north/up)
- `E = 1` (east/right)
- `S = 10` (south/down)
- `W = -1` (west/left)

### Move Generation Pattern
1. Iterate through all board squares
2. For each piece, iterate through direction vectors
3. For sliding pieces (B, R, Q), continue in direction until blocked
4. Yield moves that stay on board and follow piece rules

### Score Conventions
- Positive scores favor the current player (always white from engine's perspective)
- Piece values: P=100, N=280, B=320, R=479, Q=929, K=60000
- Mate detection: `MATE_LOWER = K - 10*Q`, `MATE_UPPER = K + 10*Q`
- Scores include positional bonuses from piece-square tables

### Search Optimizations
- **Null-move pruning**: Skip making move if position is strong enough
- **Transposition table**: Cache position evaluations
- **Killer move heuristic**: Try previously best moves first
- **Quiescent search**: Extend search for tactical moves (captures/promotions)
- **Futility pruning**: Skip moves unlikely to improve position

## File Organization

```
sunfish/
├── sunfish.py              # Core chess engine (111 lines of logic)
├── sunfish_nnue.py         # Experimental NNUE version
├── server.py               # Flask REST API wrapper
├── requirements.txt        # Dependencies: chess, tqdm, Flask-Cors
├── Makefile                # Convenient commands for dev/testing
├── Dockerfile              # Production container config
├── Dockerfile.local        # Development container config
├── docker-compose.yml      # Docker Compose for local dev
├── .gitlab-ci.yml          # CI/CD pipeline configuration
├── test_top_n.py          # Tests for top_n feature
├── test_ignore_squares.py # Tests for ignore_squares feature
├── test_performance.py    # Performance benchmarks
├── tools/
│   ├── uci.py             # UCI protocol implementation
│   ├── fancy.py           # Terminal interface for playing
│   ├── tester.py          # Test suite
│   └── test_files/        # Test positions and cases
├── nnue/
│   ├── sunfish2.py        # NNUE architecture variant
│   ├── sunfish_king.py    # King-focused NNUE
│   └── models/            # Trained NNUE models
└── docs/                  # Documentation and logo
```

## Important Limitations & Quirks

### Rules Support
- Supports all chess rules EXCEPT the 50-move draw rule
- En passant: Supported
- Castling: Supported (including king passant detection)
- Promotion: Supported

### Known Behaviors
1. **King capture engine**: Sunfish allows capturing the king instead of stopping at mate
2. **Stalemate detection**: Only accurate at higher search depths (depth > 2)
3. **Coordinate flipping**: All black moves must be flipped (119 - coord)
4. **Position rotation**: After every move, board is rotated for next player

### Performance Notes
- Pure Python implementation (can be slow for deep searches)
- PyPy interpreter gives ~250 ELO boost over CPython
- Default search depth: 8 plies
- Typical search time: 1-2 seconds for middlegame positions

## Common Pitfalls & Debugging Tips

### 1. Coordinate Confusion
When debugging moves, remember:
- Engine internal coords are always white-perspective
- Black's moves need flipping: `119 - coord`
- FEN side-to-move determines if flipping is needed

### 2. Stateless API - No Memory Between Calls
**CRITICAL**: The REST API is completely stateless (see "Stateless History Tracking" section).
- Each API call creates a new UCI session from scratch
- No position or game state is remembered between calls
- Client MUST send complete position (FEN + moves) every time
- Transposition table is lost between requests

Example mistake:
```python
# WRONG: Assuming engine remembers position
response1 = POST /bestmove {"fen": startpos}
response2 = POST /bestmove {"moves": response1.bestmove}  # ERROR: No FEN!

# CORRECT: Always provide full state
response1 = POST /bestmove {"fen": startpos}
response2 = POST /bestmove {"fen": startpos, "moves": response1.bestmove}
```

### 3. Move History Tracking
The `/bestmove` endpoint tracks move history to determine effective side:
```python
num_moves = len(moves_history.split())
if initial_side == 'w':
    effective_side = 'w' if (num_moves % 2 == 0) else 'b'
else:
    effective_side = 'b' if (num_moves % 2 == 0) else 'w'
```

### 4. Check Detection
- `can_kill_king(pos)` checks if OPPONENT is in check
- For checking current player: `can_kill_king(pos.rotate())`
- After applying move: `can_kill_king(new_pos.rotate())`

### 5. Precision Parameter Usage
- Precision adds **randomness**, not intelligence
- Higher precision = weaker play (more noise)
- Set to 0.0 for deterministic/strongest play
- Use 0.1-0.3 for adjustable difficulty levels
- See "The Precision Parameter" section for details

### 6. UCI Session Threading and Callbacks
- Each REST call spawns isolated thread with redirected stdin/stdout
- `callback_holder` dict captures Python objects (Position, moves)
- Don't rely on text output parsing alone
- See "Callback Mechanism" section for architecture details

## Testing

### Running Tests
```bash
# Start dev server and run all tests
make up && make test

# Individual test suites
make test-top-n      # Test top_n feature
make test-ignore     # Test ignore_squares feature

# View server logs
make logs

# Legacy commands (if needed)
tools/quick_tests.sh
python tools/tester.py
tools/fancy.py -cmd ./sunfish.py
```

### Available Make Commands
- `make up` - Start dev server in Docker (http://localhost:5500)
- `make down` - Stop server
- `make test` - Run all API tests
- `make test-top-n` - Test multiple best moves feature
- `make test-ignore` - Test ignore squares feature
- `make test-perf` - Run performance benchmarks
- `make logs` - View server logs in real-time
- `make help` - Show all available commands

### Test Files
- `test_top_n.py` - Tests for top_n parameter and multi-move evaluation
- `test_ignore_squares.py` - Tests for ignore_squares filtering
- `test_performance.py` - Performance benchmarks for different configurations
- `tools/test_files/` - Legacy test positions (FEN strings for edge cases)

## Deployment

### Local Development
```bash
# Recommended: Use Makefile
make up

# Alternative: Docker Compose directly
docker-compose up

# Alternative: Direct Python
pip install -r requirements.txt
python server.py
```

### Production
```bash
docker build -f Dockerfile -t sunfish:latest .
docker run -p 5500:5500 sunfish:latest
```

Server runs on `http://0.0.0.0:5500`

## Performance Tuning

### Configurable Parameters
Located at top of `sunfish.py`:
- `QS = 40`: Quiescent search threshold
- `QS_A = 140`: Quiescent search aggression
- `EVAL_ROUGHNESS = 15`: Evaluation window size

### Search Depth Guidelines
- Depth 4-6: Fast, suitable for blitz
- Depth 8: Default, good balance (1-2 seconds)
- Depth 10+: Slow but strong (5+ seconds)

## Future Enhancements & TODOs

Potential improvements to consider:
1. Add 50-move draw rule support
2. Implement opening book
3. Add endgame tablebase support
4. **Persistent game sessions** (avoid re-parsing FEN each call, reuse transposition table)
   - Current: Completely stateless, rebuilds everything per request
   - Future: Session-based API with game ID tracking
5. WebSocket support for real-time search updates
6. Multi-PV (return multiple best move variations)
7. Move validation endpoint
8. Position evaluation endpoint (without computing best move)
9. Transposition table persistence across requests (for performance)
10. Difficulty levels using precision parameter as tunable setting

## Additional Resources

- [Original Sunfish GitHub](https://github.com/thomasahle/sunfish)
- [UCI Protocol Specification](http://wbec-ridderkerk.nl/html/UCIProtocol.html)
- [Chess Programming Wiki](https://www.chessprogramming.org/)
- [Sunfish on Lichess](https://lichess.org/@/sunfish-engine)
