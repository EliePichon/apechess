# Sunfish Chess Engine

Fork of Sunfish chess engine, exposed as a REST API (Flask, port 5500).

## Architecture

- `sunfish.py` — Core engine (board, search, evaluation). Do not modify unless changing engine logic.
- `engine.py` — Clean Python API wrapping sunfish directly.
- `server.py` — Flask REST API calling engine.py. Stateless: each call creates a fresh UCI session in a thread.
- `tools/uci.py` — UCI protocol layer (used for CLI, not by server). `from_fen()` takes 6 args, not a FEN string. Needs `uci.sunfish = sunfish` before use.

## Board Representation

120-char string (10x12 mailbox). A1=91, H1=98, A8=21, H8=28. Direction offsets: N=-10, E=1, S=10, W=-1.

**Pieces**: Uppercase=White (PNBRQK), lowercase=Black. Dot=empty, space/newline=padding.

**Critical**: Engine always works from white's perspective. Black positions are rotated via `Position.rotate()` which calls `swapcase()`. Coordinate flip: `119 - coord`.

### Rocks (`O`/`o`)

Neutral, immovable obstacles. Cannot be moved or captured by normal pieces.
- Block sliding pieces (R, B, Q) like the board edge. Block pawn advances and king movement.
- Knights **can** jump over rocks (as they jump over everything).
- Zero piece value. PST is all zeros. Use `O` in FEN (e.g., `8/8/8/3O4/8/8/8/8`).
- In `gen_moves()`: `O` is skipped as a movable piece, `o` is treated as an impassable blocker (breaks ray, no capture generated).
- `value()` excludes `o` from capture scoring.
- **swapcase pitfall**: `Position.rotate()` flips `O`↔`o`. Both cases must be handled. Failing to handle `o` makes rocks appear as capturable black pieces. Always test both white-to-move and black-to-move positions.
- Tests: `tests/test_rocks.py`

### Powered Pieces (Rock-Landing)

Variants of standard pieces that can **land on rocks**, destroying them. Encoded as alternate characters that survive `swapcase()` rotation automatically.

| Base | Powered (White) | Powered (Black) | Mnemonic |
|------|-----------------|-----------------|----------|
| P    | `A`             | `a`             | Augmented |
| N    | `C`             | `c`             | Cavalry |
| B    | `D`             | `d`             | Diagonal |
| R    | `T`             | `t`             | Tower |
| Q    | `X`             | `x`             | eXtreme |
| K    | `Y`             | `y`             | Yonder |

**Behavior**:
- Move exactly like their base piece. Can land on rocks (`O`/`o`), destroying them.
- Sliding powered pieces (T, D, X) stop after landing on a rock — do NOT slide through.
- Non-powered pieces remain fully blocked by rocks.
- Powered pawns (`A`) promote to powered pieces (`C`/`D`/`T`/`X`), not normal pieces.
- Same piece values and PSTs as their base pieces.

**Implementation touchpoints** (check all when modifying piece logic):
- `POWERED_TO_BASE` dict: maps powered chars to base chars (e.g., `'T': 'R'`)
- `POWERED_PIECES` frozenset: `'ACDTXY'` for fast membership checks
- `piece`, `pst`, `directions` dicts: entries for powered pieces share base piece values
- `gen_moves()`: allows powered pieces past rock-blocking check (both `O` and `o`)
- Pawn logic: `p in "PA"` (not `p == "P"`)
- King logic: `p in "KY"` (not `p == "K"`)
- Non-slider stop set: `"PNKACY"` (not `"PNK"`)
- `engine.py`: player_pieces includes `ACDTXY`
- Tests: `tests/test_rock_landing.py`

## REST API

All endpoints accept `{"fen": "..."}`. API is **fully stateless** — no memory between calls.

- `POST /getmoves` — Returns `{moves: {square: [move_strings]}, check: bool}`
- `POST /bestmove` — Returns `{bestmoves: [[move, score], ...], check: bool}`
  - Optional params: `movetime`, `maxdepth` (default 8), `precision` (0=strongest, 0.1-0.3=weaker), `top_n` (default 1), `ignore_squares` (list of squares to skip), `moves` (space-separated history)
- `POST /ischeck` — Returns `{check: bool}`

## Key Conventions

- Coords: `parse("e2")` → board index, `render(idx)` → algebraic notation
- Black coordinate flipping: `119 - coord`
- Check detection: `can_kill_king(pos)` checks if opponent is in check. Current player: `can_kill_king(pos.rotate())`
- Legal moves: `Position.get_legal_moves(square=None)` filters out self-check
- Move application: `Position.move(m)` returns new position (rotated for opponent)
- Piece values: P=100, N=280, B=320, R=479, Q=929, K=60000, O=0
- Pawn logic uses `p in "PA"`, king logic uses `p in "KY"` to include powered variants
- Non-slider stop set: `"PNKACY"`
- `engine.py` player_pieces includes `ACDTXY`

## Testing

```bash
make up && make test        # Start Docker dev server + run all tests
make test-top-n             # Test top_n feature
make test-ignore            # Test ignore_squares feature
make logs                   # View server logs
```

Tests are integration tests in `tests/` hitting HTTP endpoints inside Docker.
Test files: `test_top_n.py`, `test_ignore_squares.py`, `test_rocks.py`, `test_rock_landing.py`, `test_performance.py`.

## Common Pitfalls

1. **Stateless API**: Every call must send complete FEN + moves. No state persists.
2. **Coordinate flipping**: All black moves need `119 - coord`. FEN side-to-move determines this.
3. **Rocks + swapcase**: `rotate()` flips O↔o. Both must be handled. Test both white/black to move.
4. **`from_fen()` signature**: Takes 6 positional args (board, color, castling, enpas, hclock, fclock), NOT a FEN string.
5. **Black history init**: `from_fen()` returns `pos.rotate()` for color='b'. History needs `[pos.rotate(), pos]`.
6. **Precision**: Adds randomness (weaker play), not intelligence. 0.0 = deterministic/strongest.

## Dev Setup

```bash
make up                     # Docker dev server on localhost:5500
make down                   # Stop
python server.py            # Direct (after pip install -r requirements.txt)
```
