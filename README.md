# Sunfish API

A chess engine REST API, forked from [sunfish](https://github.com/thomasahle/sunfish) by Thomas Ahle.

Sunfish is a simple but strong chess engine written in Python. This fork wraps it in a Flask REST API with session management, custom piece types, and a Docker dev environment.

## Features

- **REST API** — Session-based and stateless modes, CORS-enabled
- **Dream API** — Simplified game loop: `/newgame` → `/turn` → `/move` with move grading and look-ahead
- **Rocks** — Immovable obstacle pieces that block movement (knights can jump over them)
- **Powered Pieces** — Variants (A, C, D, T, X, Y) that can land on and destroy rocks
- **Clutchness** — Measures how critical a move is (eval gap between best and second-best move)
- **Move Grading** — Per-move accuracy scoring against the engine's best line
- **MTD-bi Search** — With Piece Square Tables, transposition tables, and null-move pruning
- **C Extension** — Hot paths (gen_moves, value, move, rotate) in C for ~5x speedup over pure Python

## Quick Start

```bash
make up      # Start dev server in Docker (http://localhost:5500)
make test    # Run all tests
make down    # Stop server
```

## API

See [API.md](API.md) for full endpoint documentation.

## Architecture

| File | Role |
|------|------|
| `sunfish.py` | Core engine — board representation, search, evaluation |
| `engine.py` | Python API wrapping sunfish, session management |
| `server.py` | Flask REST API |
| `tools/uci.py` | UCI protocol layer (CLI use) |
| `csrc/_sunfish_core.c` | C extension — hot path acceleration (~650 lines) |

## Development

```bash
make lint          # Run ruff linter
make format        # Auto-format with ruff
make setup-hooks   # Install pre-commit hooks
make profile       # Generate flame graph (profiles/flame.svg)
make help          # Show all available commands
```

Hot-reload is enabled — code changes to Python files are picked up automatically without restarting the server. Changes to `csrc/` require rebuilding the C extension (`pip install -e .` locally, or `make down && make up` for Docker).

### Building the C extension locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install setuptools && pip install -e .
python -c "import sunfish; print(sunfish._USING_C_EXTENSION)"  # True
```

The engine falls back to pure Python automatically if the extension isn't built. Set `SUNFISH_NO_C=1` to force the fallback.

## Attribution

Forked from [sunfish](https://github.com/thomasahle/sunfish) by Thomas Ahle. Sunfish heritage traces back to [Micro-Max](http://home.hccnet.nl/h.g.muller/max-src2.html) by Geert Muller and [PyChess](http://pychess.org).

## License

[GNU GPL v3](https://www.gnu.org/licenses/gpl-3.0.en.html)
