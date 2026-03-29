![Sunfish logo](https://raw.github.com/thomasahle/sunfish/master/docs/logo/sunfish_large.png)

## Introduction
Sunfish is a simple, but strong chess engine, written in Python. With its simple [UCI](http://wbec-ridderkerk.nl/html/UCIProtocol.html) interface, and removing comments and whitespace, it takes up just 131 lines of code! (`build/clean.sh sunfish.py | wc -l`).
Yet [it plays at ratings above 2000 at Lichess](https://lichess.org/@/sunfish-engine).

Because Sunfish is small and strives to be simple, the code provides a great platform for experimenting. People have used it for testing parallel search algorithms, experimenting with evaluation functions, and developing deep learning chess programs. Fork it today and see what you can do!

# REST API Server

This fork includes a REST API server for easy integration with web applications.

## Quick Start

```bash
# Start the development server
make up

# Run tests
make test

# View logs
make logs

# Stop server
make down
```

Available commands:
- `make up` - Start dev server in Docker (http://localhost:5500)
- `make test` - Run all tests
- `make test-top-n` - Test top_n feature
- `make test-ignore` - Test ignore_squares feature
- `make logs` - View server logs
- `make down` - Stop server
- `make help` - Show all commands

## API Endpoints

### GET /getmoves
Get all legal moves for a position.

**Request**: `{"fen": "<fen_string>"}`

**Response**: `{"moves": {"e2": ["e2e4", "e2e3"], ...}, "check": false}`

### POST /bestmove
Get best move(s) for a position.

**Request**:
```json
{
  "fen": "<fen_string>",
  "maxdepth": 6,
  "top_n": 5,
  "ignore_squares": ["e2", "g1"]
}
```

**Response**: `{"bestmoves": [["e2e4", 45], ["d2d4", 42]], "check": false}`

### POST /ischeck
Check if current player is in check.

**Request**: `{"fen": "<fen_string>"}`

**Response**: `{"check": true}`

See `API.md` for detailed API documentation.

# Features

1. Built around the simple, but efficient MTD-bi search algorithm, also known as [C*](https://www.chessprogramming.org/NegaC*).
2. Filled with classic "chess engine tricks" for simpler and faster code.
3. Efficiently updatedable evaluation function through [Piece Square Tables](https://www.chessprogramming.org/Piece-Square_Tables).
4. Uses standard Python collections and data structures for clarity and efficiency.
5. REST API for easy integration with web applications.

# Limitations

Sunfish supports all chess rules, except the 50 moves draw rule.

There are many ways in which you may try to make Sunfish stronger. First you could change from a board representation to a mutable array and add a fast way to enumerate pieces. Then you could implement dedicated capture generation, check detection and check evasions. You could also move everything to bitboards, implement parts of the code in C or experiment with parallel search!

The other way to make Sunfish stronger is to give it more knowledge of chess. The current evaluation function only uses piece square tables - it doesn't even distinguish between midgame and endgame. You can also experiment with more pruning - currently only null move is done - and extensions - currently none are used. Finally Sunfish might benefit from a more advanced move ordering, MVV/LVA and SEE perhaps?

An easy way to get a strong Sunfish is to run with with the [PyPy Just-In-Time intepreter](https://pypy.org/). In particular the python2.7 version of pypy gives a 250 ELO boost compared to the cpython (2 or 3) intepreters at fast time controls:

    Rank Name                    Elo     +/-   Games   Score   Draws
       1 pypy2.7 (7.1)           166      38     300   72.2%   19.7%
       2 pypy3.6 (7.1)            47      35     300   56.7%   21.3%
       3 python3.7               -97      36     300   36.3%   20.7%
       4 python2.7              -109      35     300   34.8%   24.3%


# Why Sunfish?

The name Sunfish actually refers to the [Pygmy Sunfish](http://en.wikipedia.org/wiki/Pygmy_sunfish), which is among the very few fish to start with the letters 'Py'. The use of a fish is in the spirit of great engines such as Stockfish, Zappa and Rybka.

In terms of Heritage, Sunfish borrows much more from [Micro-Max by Geert Muller](http://home.hccnet.nl/h.g.muller/max-src2.html) and [PyChess](http://pychess.org).

# License

[GNU GPL v3](https://www.gnu.org/licenses/gpl-3.0.en.html)
