import sys
import time
import threading
import queue
from io import StringIO
import logging
from flask import Flask, request, jsonify
import tools.uci as uci
import sunfish
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app,
    resources={r"/getmoves": {"origins": "*"},
               r"/bestmove": {"origins": "*"},
               r"/ischeck": {"origins": "*"}})

class BlockingInput:
    def __init__(self):
        self.queue = queue.Queue()

    def write(self, data):
        """Write data to the blocking input."""
        self.queue.put(data)

    def readline(self):
        """Simulate readline for the UCI loop."""
        return self.queue.get()

    def isatty(self):
        """Required for Werkzeug reloader compatibility."""
        return False

def run_uci_session(commands, expected_response=None, timeout=25):
    """
    Run a new UCI session, send commands, and capture the response.

    Args:
        commands (list[str]): A list of UCI commands to send.
        expected_response (str): Prefix of the expected response.
        timeout (int): Maximum wait time for the response in seconds.

    Returns:
        list[str]: Lines of response from the UCI loop.
    """
    input_stream = BlockingInput()
    output_stream = StringIO()
    callback_holder = {"position": None, "moves": None}  # Shared object to hold the Position object

    logger.debug(f"Starting UCI session... commands: {commands}")
    def uci_loop():
        sys.stdin = input_stream
        sys.stdout = output_stream
        startpos = sunfish.Position(
            sunfish.initial, 0, (True, True), (True, True), 0, 0
        )
        
        try:
            uci.run(sunfish, startpos, callbackPos=lambda pos: callback_holder.update({'position':pos}), callbackMove=lambda moves: callback_holder.update({'moves': moves}))
        except Exception as e:
            logger.error(f"UCI loop error: {e}")
        finally:
            logger.debug("UCI loop terminated.")

    thread = threading.Thread(target=uci_loop, daemon=True)
    thread.start()

    # Send commands
    for cmd in commands:
        input_stream.write(cmd + "\n")

    start_time = time.time()
    while time.time() - start_time < timeout:
        output_stream.seek(0)
        response = output_stream.read().strip().split("\n")

        if expected_response:
            filtered_response = [line for line in response if line.startswith(expected_response)]
            if filtered_response:
                input_stream.write("quit\n")
                thread.join(timeout=20.0)
                return filtered_response, callback_holder

        if not expected_response and response:
            input_stream.write("quit\n")
            thread.join(timeout=20.0)
            return response, callback_holder

        time.sleep(0.1)

    input_stream.write("quit\n")
    thread.join(timeout=20.0)
    raise TimeoutError(f"UCI session timed out waiting for response: {expected_response}")

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
    # Extract side to move from the FEN string
    fen_parts = fen.split()
    if len(fen_parts) < 2:
        return jsonify({"error": "Invalid FEN string"}), 400
    side_to_move = fen_parts[1]  # 'w' or 'b'

    commands = [f"position fen {fen}"]
    try:
        _, holder = run_uci_session(commands)
        position = holder['position']
        if not position:
            return jsonify({"error": "Unable to retrieve position from UCI."}), 500

        # Collect moves for the specified side
        player_pieces = set("PNBRQK") #Always white since we just sent a fen position => sunfish flipped if black
        moves = {}
        for i, piece in enumerate(position.board):
            if piece in player_pieces:
                legal_moves = position.get_legal_moves(square=i)
                if legal_moves:
                    square = sunfish.render(i)
                    rendered_moves = [
                        sunfish.render(move.i) + sunfish.render(move.j) + move.prom.lower()
                        for move in legal_moves
                    ]

                    # If it's Black's turn, re-flip the moves
                    if side_to_move == "b":
                        flipped_square = sunfish.render(119 - i)
                        flipped_moves = [
                            sunfish.render(119 - move.i) + sunfish.render(119 - move.j) + move.prom.lower()
                            for move in legal_moves
                        ]
                        moves[flipped_square] = flipped_moves
                    else:
                        moves[square] = rendered_moves
        rotated_pos = position.rotate()
        is_check = uci.can_kill_king(rotated_pos)
        return jsonify({"moves": moves, "check": is_check})
    except TimeoutError as e:
        logger.error(f"Timeout error: {e}")
        return jsonify({"error": "Engine timed out while getting moves"}), 504
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/bestmove", methods=["POST"])
def bestmove_endpoint():
    """
    Get the best move for the current position.
    Request JSON:
      { "fen": "<fen_string>", "movetime": <int>, "maxdepth": <int>, "top_n": <int>, "ignore_squares": ["e2", "g1"] }
    Response JSON:
      { "bestmove": "<move>", "score": "<score>", "check": <bool>, "allmoves": [...] }
    """
    data = request.get_json()
    if not data or "fen" not in data:
        return jsonify({"error": "Missing 'fen' field"}), 400

    fen = data["fen"]
    # Extract the original side from the FEN
    fen_parts = fen.split()
    if len(fen_parts) < 2:
        return jsonify({"error": "Invalid FEN string"}), 400
    initial_side = fen_parts[1]  # 'w' or 'b'

    movetime = data.get("movetime", None)
    maxdepth = data.get("maxdepth", None)
    precision = data.get("precision", None)
    top_n = data.get("top_n", 10)  # Default: return top 10 moves
    ignore_squares = data.get("ignore_squares", [])  # Squares to ignore (e.g., ["e2", "g1"])
    moves_history = data.get("moves", "").lower()

    logger.debug(f"Received FEN: {fen}")
    logger.debug(f"Received movetime: {movetime}")
    logger.debug(f"Received maxdepth: {maxdepth}")
    logger.debug(f"Received precision: {precision}")
    logger.debug(f"Received top_n: {top_n}")
    logger.debug(f"Received ignore_squares: {ignore_squares}")
    logger.debug(f"Received moves history: {moves_history}")

    go_command = "go"
    if movetime:
        go_command += f" movetime {movetime}"
    elif maxdepth:
        go_command += f" depth {maxdepth}"
    else:
        go_command += " depth 8"

    go_command += f" precision {precision if precision else 0}"
    go_command += f" top_n {top_n}"

    # Add ignore_squares if provided
    if ignore_squares and len(ignore_squares) > 0:
        # Convert list to comma-separated string
        ignore_str = ",".join([sq.lower() for sq in ignore_squares])
        go_command += f" ignore {ignore_str}"

    # Build the position command with moves history.
    position_command = f"position fen {fen}"
    if moves_history:
        position_command += " moves " + moves_history

    commands = [position_command, go_command]
    logger.debug(commands)
    try:
        response, holder = run_uci_session(commands, expected_response="bestmove")
        position = holder['position']
        moves = holder['moves']
        bestmove_line = response[0] if response else None

        # Process the bestmove line (expected format like "bestmove f2f1q score 735").
        parts = bestmove_line.split()
        bestmove = parts[1] if len(parts) > 1 else "(none)"
        score = parts[3] if len(parts) > 3 else "(none)"
        if bestmove == "(none)":
            return jsonify({"bestmove": "(none)"})

        # Determine the effective side.
        num_moves = len(moves_history.split()) if moves_history.strip() != "" else 0
        if initial_side == 'w':
            effective_side = 'w' if (num_moves % 2 == 0) else 'b'
        else:
            effective_side = 'b' if (num_moves % 2 == 0) else 'w'

        logger.debug(f"Initial side: {initial_side}, moves count: {num_moves}, effective side: {effective_side}")

        # Parse the bestmove.
        if effective_side == 'b':
            # Flip coordinates from white's perspective to black's.
            move_from = 119 - sunfish.parse(bestmove[:2])
            move_to = 119 - sunfish.parse(bestmove[2:4])
        else:
            move_from = sunfish.parse(bestmove[:2])
            move_to = sunfish.parse(bestmove[2:4])
        promo = bestmove[4:].upper() if len(bestmove) > 4 else ""

        new_position = position.move(sunfish.Move(move_from, move_to, promo))

        is_check = uci.can_kill_king(new_position.rotate())

        return jsonify({"bestmove": bestmove, "score": score, "check": is_check, "allmoves": moves})
    except TimeoutError as e:
        logger.error(f"Timeout error: {e}")
        return jsonify({"error": "Engine timed out while computing best move"}), 504
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/ischeck", methods=["POST"])
def is_check():
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
    commands = [f"position fen {fen}"]
    try:
        _, holder = run_uci_session(commands)
        position = holder['position']
        is_check = False
        if position:
            is_check = uci.can_kill_king(position)
        return jsonify({"check": is_check})
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500
     
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500, debug=True)
