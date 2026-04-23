# Apechess API

A REST chess engine with optional custom pieces — forked from [Sunfish](https://github.com/thomasahle/sunfish).

Apechess wraps Thomas Ahle's Sunfish engine in a Flask HTTP API with session management, a C-accelerated search, and a set of opt-in piece variants (rocks, ninja knights, laser bishops…) built for chess-variant games. **Standard chess works out of the box** — the custom pieces are opt-in.

## Features

- **Standard chess engine** — MTD-bi search, piece-square tables, transposition tables, null-move pruning. Works as a plain chess API.
- **REST API** — Session-based *or* stateless. CORS-enabled.
- **Dream API** — A simplified 3-verb game loop (`/newgame` → `/turn` → `/move`) with optional move grading and look-ahead for puzzle triggers.
- **C extension** — Hot paths rewritten in C for a **~6.4× speedup** (18K → 117K NPS on an M1 MacBook). Pure-Python fallback if the extension isn't built.
- **Custom pieces (optional)** — Rocks, Powered Pieces, Ninja Knight, Laser Bishop. Encoded as extra FEN characters — regular chess FENs behave exactly like upstream Sunfish.
- **Clutchness & grading** — Eval-gap metric and per-move accuracy scoring, useful for puzzles and coaching UIs.

## Quick start

```bash
git clone https://github.com/EliePichon/apechess.git
cd apechess
make up
```

Server runs at `http://localhost:5500`. Hot-reload is enabled for Python files.

```bash
make test    # Run the full integration suite
make down    # Stop the server
make help    # Show all commands
```

## API at a glance

Full endpoint docs in [API.md](API.md). The minimal session loop:

```bash
# 1. Start a new game (standard chess, or pass a custom FEN)
curl -s -X POST http://localhost:5500/newgame \
  -H 'Content-Type: application/json' -d '{}'
# → { "session_id": "..." }

# 2. Ask the engine to play a turn
curl -s -X POST http://localhost:5500/turn \
  -H 'Content-Type: application/json' \
  -d '{"session_id": "<id>", "peek_next": true}'
# → { "move": "e2e4", "eval": 34, "check": false, "game_over": null,
#     "next": { "legal_moves": {...}, "best_move": "e7e5", ... } }

# 3. Apply the player's move (with grading)
curl -s -X POST http://localhost:5500/move \
  -H 'Content-Type: application/json' \
  -d '{"session_id": "<id>", "move": "e7e5", "grade": true}'
# → { "status": "ok", "grade": { "accuracy": 97, "best_move": "e7e5", ... } }
```

Sessions are server-assigned UUIDs, expire after 30 minutes of inactivity, and are thread-safe (each session has its own lock to prevent concurrent-search corruption).

### Stateless mode

Every endpoint also accepts a `fen` field if you'd rather keep state on the client:

```bash
curl -s -X POST http://localhost:5500/bestmove \
  -H 'Content-Type: application/json' \
  -d '{"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "maxdepth": 12}'
```

## Performance

The C extension accelerates move generation, evaluation, move-ordering, and board rotation. Benchmark across 6 positions (opening / midgame / endgame) at depth 8, measured on an M1 MacBook:

| Path         | Total time | NPS      | Relative |
|--------------|-----------:|---------:|---------:|
| Pure Python  |     118.3s |  ~18,000 |     1.0× |
| C extension  |      18.4s | ~117,000 |    ~6.4× |

```bash
python scripts/benchmark.py                 # Direct engine benchmark, depth 8
python scripts/benchmark.py --depth 5       # Quick sanity check
SUNFISH_NO_C=1 python scripts/benchmark.py  # Force Python fallback
```

Node counts are **invariant across the C and Python paths** — same board iteration, same move order, same tie-breaking. Enforced by `tests/test_node_invariance.py`.

## Custom pieces

Apechess adds a handful of optional piece variants, encoded as extra ASCII letters (uppercase = White, lowercase = Black) that survive `swapcase()` rotation cleanly. A standard FEN uses only the six standard pieces and behaves like any other chess engine.

| Char          | Piece            | Notes                                                   |
|---------------|------------------|---------------------------------------------------------|
| P N B R Q K   | Standard pieces  | —                                                       |
| O             | Rock             | Neutral, immovable obstacle                             |
| A C D T X Y   | Powered pieces   | Variants of P/N/B/R/Q/K that can destroy rocks          |
| J             | Ninja Knight     | Chains knight-hops off rocks                            |
| L             | Laser Bishop     | Slides through all pieces on diagonals                  |

See [CLAUDE.md](CLAUDE.md) for full piece behavior, activation rules, and FEN encoding.

## Architecture

| File                     | Role                                                     |
|--------------------------|----------------------------------------------------------|
| `sunfish.py`             | Core engine — board, search, evaluation                  |
| `engine.py`              | Clean Python API + session management                    |
| `server.py`              | Flask REST layer                                         |
| `tools/uci.py`           | UCI protocol layer (CLI, not used by the server)         |
| `csrc/_sunfish_core.c`   | C extension, ~650 lines — accelerates the hot paths      |
| `scripts/gen_tables.py`  | Regenerates `csrc/tables.h` from the Python PSTs         |

## Development

```bash
# Local (without Docker)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install setuptools && pip install -e .    # Builds the C extension
python server.py

# Verify the C extension is loaded
python -c "import sunfish; print(sunfish._USING_C_EXTENSION)"  # → True
```

Hot-reload covers Python files (`server.py`, `engine.py`, `sunfish.py`, `tools/`). Changes to `csrc/` require a rebuild: `make rebuild` in Docker, or `pip install -e .` locally.

```bash
make lint          # ruff
make format        # ruff format
make setup-hooks   # pre-commit hooks
make profile       # Flame graph → profiles/flame.svg
```

## Testing

Integration tests hit the HTTP API inside Docker:

```bash
make up && make test
make test-dream        # Dream API (/turn + grade/peek)
make test-session      # Session / stateful engine + clutchness
make test-rock-landing # Powered pieces
```

C-extension correctness tests run locally (no Docker needed):

```bash
python -m pytest tests/test_c_extension.py -v       # gen_moves, value, sort, move, rotate
python -m pytest tests/test_node_invariance.py -v   # C vs Python node-count parity
```

See [TESTING.md](TESTING.md) for the full test layout.

## What's changed vs. upstream Sunfish

Apechess is a substantial fork. The core search is still Sunfish's MTD-bi; everything around it is new or rewritten:

- Flask REST API (`server.py`) + stateful session layer (`engine.py`)
- C extension for move generation, evaluation, sort, move, rotate
- Custom piece types (Rock, Powered Pieces, Ninja Knight, Laser Bishop)
- Dream API (`/turn`, peek-ahead, move grading)
- Clutchness metric, `top_n`, `ignore_squares`, `precision` parameters
- Docker dev environment with hot-reload and profiling

## Contributing

Issues and PRs are welcome. Before opening a PR:

1. `make lint && make format-check` — code style
2. `make test` — integration tests (Docker must be up)
3. `python -m pytest tests/test_c_extension.py tests/test_node_invariance.py` — if you touched `csrc/` or `sunfish.py`
4. If you changed piece logic, update **both** `sunfish.py` *and* `csrc/_sunfish_core.c` — the C extension must stay in lockstep.

See [CLAUDE.md](CLAUDE.md) for a deeper architecture / pitfall guide.

## Attribution

- [Sunfish](https://github.com/thomasahle/sunfish) by Thomas Ahle — the Python chess engine this project is forked from.
- Sunfish's lineage: [Micro-Max](http://home.hccnet.nl/h.g.muller/max-src2.html) by H.G. Muller, and [PyChess](http://pychess.org).

## License

[GNU GPL v3](LICENSE.md) — same license as upstream Sunfish.
