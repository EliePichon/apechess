# Current Communication Diagram

POST /bestmove {fen, maxdepth, top_n, ...}
  │
  ▼
server.py: bestmove_endpoint()
  │  Constructs text commands: "position fen ...", "go depth 8 top_n 3 ..."
  │
  ▼
server.py: run_uci_session(commands, expected_response="bestmove")
  │  Creates BlockingInput (fake stdin queue)
  │  Creates StringIO (fake stdout)
  │  Creates callback_holder = {"position": None, "moves": None}
  │  Spawns thread → uci_loop()
  │
  ├──────────── THREAD ────────────────────────────────────┐
  │                                                         │
  │  sys.stdin = BlockingInput                              │
  │  sys.stdout = StringIO                                  │
  │                                                         │
  │  uci.run(sunfish, startpos, callbackPos=λ, callbackMove=λ)
  │    │                                                    │
  │    │  while True: args = input().split()  ◄── reads from fake stdin
  │    │                                                    │
  │    ├─ "position fen ..." → from_fen() → hist            │
  │    │   callbackPos(hist[-1]) ──► callback_holder["position"] = Position
  │    │   print("info string position set") ──► StringIO   │
  │    │                                                    │
  │    ├─ "go depth 8 ..." → go_loop(searcher, hist, ...)   │
  │    │   │  iterative deepening search                    │
  │    │   │  filter ignore_squares                         │
  │    │   │  score top_n moves (TT + shallow search)       │
  │    │   │  callbackMove(scored_moves) ──► callback_holder["moves"]
  │    │   │  print("bestmove e2e4 score 45 depth 8") ──► StringIO
  │    │                                                    │
  │    └─ "quit" → break                                    │
  │                                                         │
  ├─────────────────────────────────────────────────────────┘
  │
  │  Polling loop: reads StringIO looking for "bestmove" prefix
  │  Sends "quit" to fake stdin when found
  │  Returns (["bestmove e2e4 score 45 depth 8"], callback_holder)
  │
  ▼
server.py: bestmove_endpoint() continues
  │  Parses "bestmove e2e4 score 45 depth 8" text ← TEXT CHANNEL
  │  Reads callback_holder["position"] and ["moves"] ← OBJECT CHANNEL
  │  Computes check, builds response
  │
  ▼
Response: {"bestmoves": [["e2e4", 45]], "check": false, "depth_reached": 8}
