import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import engine

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app,
    resources={r"/getmoves": {"origins": "*"},
               r"/bestmove": {"origins": "*"},
               r"/ischeck": {"origins": "*"},
               r"/health": {"origins": "*"}})

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
    fen_parts = fen.split()
    if len(fen_parts) < 2:
        return jsonify({"error": "Invalid FEN string"}), 400

    try:
        result = engine.get_legal_moves(fen)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/bestmove", methods=["POST"])
def bestmove_endpoint():
    """
    Get the best move(s) for the current position.
    Request JSON:
      { "fen": "<fen_string>", "movetime": <int>, "maxdepth": <int>, "top_n": <int> (default: 1), "ignore_squares": ["e2", "g1"] }
    Response JSON:
      { "bestmoves": [["e2e4", 45], ...], "check": <bool> }
    """
    data = request.get_json()
    if not data or "fen" not in data:
        return jsonify({"error": "Missing 'fen' field"}), 400

    fen = data["fen"]
    fen_parts = fen.split()
    if len(fen_parts) < 2:
        return jsonify({"error": "Invalid FEN string"}), 400

    movetime = data.get("movetime", None)
    maxdepth = data.get("maxdepth", None)
    precision = data.get("precision", None)
    top_n = data.get("top_n", 1)
    ignore_squares = data.get("ignore_squares", [])
    moves_history = data.get("moves", "").lower()

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
        )
        return jsonify(result)
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
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5500))
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    debug = os.environ.get("debug", "False").lower() == "true"
    app.run(host=host, port=port, debug=debug)
