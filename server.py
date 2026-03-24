import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import engine
from engine import EngineError

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app,
    resources={r"/getmoves": {"origins": "*"},
               r"/bestmove": {"origins": "*"},
               r"/ischeck": {"origins": "*"},
               r"/evalmoves": {"origins": "*"},
               r"/newgame": {"origins": "*"},
               r"/move": {"origins": "*"},
               r"/turn": {"origins": "*"},
               r"/session/stats": {"origins": "*"},
               r"/health": {"origins": "*"}})

@app.errorhandler(EngineError)
def handle_engine_error(error):
    return jsonify({"error": error.message}), error.status_code

def validate_fen(fen):
    """Return a 400 error response if FEN is invalid, or None if OK."""
    fen_parts = fen.split()
    if len(fen_parts) < 2:
        return jsonify({"error": "Invalid FEN string"}), 400
    return None

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/getmoves", methods=["POST"])
def get_moves_endpoint():
    """
    Get all legal moves for the current position.
    Request JSON:
      { "fen": "<fen_string>" }
    Response JSON:
      { "moves": { "e2": ["e2e4", "e2e3"], ... }, "check" : "true/false }
    """
    data = request.get_json()
    if not data or "fen" not in data:
        return jsonify({"error": "Missing 'fen' field"}), 400

    fen = data["fen"]
    err = validate_fen(fen)
    if err:
        return err

    try:
        result = engine.get_legal_moves(fen)
        return jsonify(result)
    except EngineError:
        raise
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/bestmove", methods=["POST"])
def bestmove_endpoint():
    """
    Get the best move(s) for the current position.
    Supports both stateless (fen required) and session-based modes.
    Request JSON:
      { "fen": "<fen_string>", "movetime": <int>, "maxdepth": <int>,
        "top_n": <int>, "ignore_squares": ["e2", "g1"],
        "session_id": "<string>", "clutchness": <bool> }
    Response JSON:
      { "bestmoves": [["e2e4", 45], ...], "check": <bool>, "clutchness": <int> }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    fen = data.get("fen")
    session_id = data.get("session_id")

    if not fen and not session_id:
        return jsonify({"error": "Either 'fen' or 'session_id' is required"}), 400

    if fen:
        err = validate_fen(fen)
        if err:
            return err

    movetime = data.get("movetime", None)
    maxdepth = data.get("maxdepth", None)
    precision = data.get("precision", None)
    top_n = data.get("top_n", 1)
    ignore_squares = data.get("ignore_squares", [])
    moves_history = data.get("moves", "").lower()
    clutchness = data.get("clutchness", False)

    # Match default depth logic from original server
    if not movetime and not maxdepth:
        maxdepth = 15
    elif not maxdepth:
        maxdepth = 1000  # effectively unlimited when using movetime

    try:
        result = engine.get_best_moves(
            fen=fen,
            moves_history=moves_history,
            movetime=movetime,
            maxdepth=maxdepth,
            precision=float(precision) if precision else 0.0,
            top_n=top_n,
            ignore_squares=ignore_squares,
            session_id=session_id,
            clutchness=clutchness,
        )
        return jsonify(result)
    except EngineError:
        raise
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/ischeck", methods=["POST"])
def is_check_endpoint():
    """
    Is the active player in check atm ?
    Request JSON:
      { "fen": "<fen_string>" }
    Response JSON:
      { "check": "true/false" }
    """
    data = request.get_json()
    if not data or "fen" not in data:
        return jsonify({"error": "Missing 'fen' field"}), 400

    fen = data["fen"]
    try:
        check = engine.is_check(fen)
        return jsonify({"check": check})
    except EngineError:
        raise
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/newgame", methods=["POST"])
def new_game_endpoint():
    """
    Create a new game session. Returns a server-generated session_id.
    Request JSON:
      { "fen": "<fen_string>" }  (optional, defaults to starting position)
    Response JSON:
      { "session_id": "<string>" }
    """
    data = request.get_json() or {}
    fen = data.get("fen")

    if fen:
        err = validate_fen(fen)
        if err:
            return err

    try:
        session_id = engine.create_session(fen)
        return jsonify({"session_id": session_id})
    except EngineError:
        raise
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/move", methods=["POST"])
def move_endpoint():
    """
    Apply a move to a session.
    Request JSON:
      { "session_id": "<string>", "move": "e2e4",
        "computer_turn": <bool>, "maxdepth": <int>, "movetime": <int>,
        "fen": "<fen_string>" }
    Response JSON (player turn):
      { "status": "ok", "check": <bool> }
    Response JSON (computer turn):
      { "status": "ok", "check": <bool>, "bestmoves": [...], "clutchness": <int> }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    session_id = data.get("session_id")
    move_str = data.get("move")

    if not session_id:
        return jsonify({"error": "Missing 'session_id' field"}), 400
    if not move_str:
        return jsonify({"error": "Missing 'move' field"}), 400

    is_computer_turn = data.get("computer_turn", False)
    maxdepth = data.get("maxdepth", 15)
    movetime = data.get("movetime", None)
    fen = data.get("fen")
    moves_history = data.get("moves", "").lower()
    grade = data.get("grade", False)
    grade_maxdepth = data.get("grade_maxdepth", 8)
    peek_next = data.get("peek_next", False)
    peek_maxdepth = data.get("peek_maxdepth", 5)

    try:
        # Dream API path: grade or peek_next requested
        if grade or peek_next:
            result = engine.player_move(
                session_id=session_id,
                move_str=move_str.lower(),
                grade=grade,
                grade_maxdepth=grade_maxdepth,
                peek_next=peek_next,
                peek_maxdepth=peek_maxdepth,
                fen=fen,
                moves_history=moves_history,
            )
        else:
            # Legacy path (unchanged)
            result = engine.apply_move(
                session_id=session_id,
                move_str=move_str.lower(),
                is_computer_turn=is_computer_turn,
                maxdepth=maxdepth,
                movetime=movetime,
                fen=fen,
                moves_history=moves_history,
            )
        return jsonify(result)
    except EngineError:
        raise
    except Exception as e:
        logger.error(f"Error processing move: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/turn", methods=["POST"])
def turn_endpoint():
    """
    Computer plays a turn: search for best move, apply it, detect game state.
    Request JSON:
      { "session_id": "<string>", "maxdepth": <int>, "movetime": <int>,
        "precision": <float>, "top_n": <int>, "ignore_squares": [...],
        "peek_next": <bool>, "peek_maxdepth": <int> }
    Response JSON:
      { "move": "g1f3", "eval": 32, "check": false, "game_over": null,
        "next": { "legal_moves": {...}, "check": false, "clutchness": 42, "best_eval": 38 } }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "Missing 'session_id' field"}), 400

    maxdepth = data.get("maxdepth", 15)
    movetime = data.get("movetime", None)
    precision = float(data.get("precision", 0.0))
    top_n = data.get("top_n", 1)
    ignore_squares = data.get("ignore_squares", [])
    peek_next = data.get("peek_next", False)
    peek_maxdepth = data.get("peek_maxdepth", 5)
    fen = data.get("fen")
    moves_history = data.get("moves", "").lower()

    try:
        result = engine.computer_turn(
            session_id=session_id,
            maxdepth=maxdepth,
            movetime=movetime,
            precision=precision,
            top_n=top_n,
            ignore_squares=ignore_squares,
            peek_next=peek_next,
            peek_maxdepth=peek_maxdepth,
            fen=fen,
            moves_history=moves_history,
        )
        return jsonify(result)
    except EngineError:
        raise
    except Exception as e:
        logger.error(f"Error processing turn: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/evalmoves", methods=["POST"])
def eval_moves_endpoint():
    """
    Get all legal moves with evaluation scores for each.
    Request JSON:
      { "session_id": "<string>", "maxdepth": <int>, "fen": "<fen_string>" }
    Response JSON:
      { "moves": { "e2": [{"move": "e2e4", "eval": 45}, ...] },
        "check": <bool>, "clutchness": <int> }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    fen = data.get("fen")
    session_id = data.get("session_id")

    if not fen and not session_id:
        return jsonify({"error": "Either 'fen' or 'session_id' is required"}), 400

    if fen:
        err = validate_fen(fen)
        if err:
            return err

    maxdepth = data.get("maxdepth", 8)
    movetime = data.get("movetime", None)
    moves_history = data.get("moves", "").lower()

    try:
        result = engine.get_evaluated_moves(
            fen=fen,
            moves_history=moves_history,
            maxdepth=maxdepth,
            movetime=movetime,
            session_id=session_id,
        )
        return jsonify(result)
    except EngineError:
        raise
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/session/stats", methods=["GET"])
def session_stats_endpoint():
    """
    Get session statistics for debugging.
    Query param: ?session_id=<string>
    Response JSON:
      { "tp_move_size": <int>, "tp_score_size": <int>, "ply": <int> }
    """
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "Missing 'session_id' query parameter"}), 400

    stats = engine.session_stats(session_id)
    if stats is None:
        return jsonify({"error": "Invalid or expired session_id"}), 404

    return jsonify(stats)


if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5500))
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    debug = os.environ.get("debug", "False").lower() == "true"
    app.run(host=host, port=port, debug=debug)
