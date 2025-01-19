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
CORS(app, resources={r"/getmoves": {"origins": "*"}, r"/bestmove": {"origins": "*"}})

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

def run_uci_session(commands, expected_response=None, timeout=15):
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
    position_holder = {"position": None}  # Shared object to hold the Position object

    def uci_loop():
        sys.stdin = input_stream
        sys.stdout = output_stream
        startpos = sunfish.Position(
            sunfish.initial, 0, (True, True), (True, True), 0, 0
        )
        try:
            uci.run(sunfish, startpos, callback=lambda pos: position_holder.update({"position": pos}))
        except Exception as e:
            logger.error(f"UCI loop error: {e}")
        finally:
            logger.debug("UCI loop terminated.")

    thread = threading.Thread(target=uci_loop, daemon=True)
    thread.start()

    # Send commands
    for cmd in commands:
        logger.debug(f"Sending command: {cmd}")
        input_stream.write(cmd + "\n")

    start_time = time.time()
    while time.time() - start_time < timeout:
        output_stream.seek(0)
        response = output_stream.read().strip().split("\n")

        if expected_response:
            filtered_response = [line for line in response if line.startswith(expected_response)]
            if filtered_response:
                logger.debug(f"Matched response: {filtered_response}")
                input_stream.write("quit\n")
                thread.join(timeout=5.0)
                return filtered_response, position_holder["position"]

        if not expected_response and response:
            input_stream.write("quit\n")
            thread.join(timeout=5.0)
            return response, position_holder["position"]

        time.sleep(0.1)

    input_stream.write("quit\n")
    thread.join(timeout=5.0)
    raise TimeoutError(f"UCI session timed out waiting for response: {expected_response}")

@app.route("/getmoves", methods=["POST"])
def get_moves_endpoint():
    """
    Get all legal moves for the current position.
    Request JSON:
      { "fen": "<fen_string>" }
    Response JSON:
      { "moves": { "e2": ["e2e4", "e2e3"], ... } }
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
        _, position = run_uci_session(commands)
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

        return jsonify({"moves": moves})
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
      { "fen": "<fen_string>", "movetime": <int>, "maxdepth": <int> }
    Response JSON:
      { "bestmove": "<move>" }
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

    movetime = data.get("movetime", None)
    maxdepth = data.get("maxdepth", None)

    go_command = "go"
    if movetime:
        go_command += f" movetime {movetime}"
    elif maxdepth:
        go_command += f" depth {maxdepth}"
    else:
        go_command += " depth 5"

    commands = [f"position fen {fen}", go_command]
    try:
        response, position = run_uci_session(commands, expected_response="bestmove")
        bestmove_line = response[0] if response else None
        if not bestmove_line:
            return jsonify({"bestmove": "(none)"})

        # Correctly handle the response as a string
        parts = bestmove_line.split()
        bestmove = parts[1] if len(parts) > 1 else "(none)"

        is_check = False
        if position:
            # If it's black turn, the bord in Position is rotated as white
            logger.debug(f'board position we got after the bestmove {position.board}')
            if side_to_move == 'b':
                move = 119 - sunfish.parse(bestmove[:2]), 119 - sunfish.parse(bestmove[2:4])
            else:
                move = sunfish.parse(bestmove[:2]), sunfish.parse(bestmove[2:4])
            new_position = position.move(sunfish.Move(move[0], move[1], bestmove[4:] if len(bestmove) > 4 else ""))
            logger.debug(f'new position after {new_position.board}')
            is_check = uci.can_kill_king(new_position.rotate())
            logger.debug(f'can kill king in this pos ? {is_check}')

        return jsonify({"bestmove": bestmove, "check": is_check})
    except TimeoutError as e:
        logger.error(f"Timeout error: {e}")
        return jsonify({"error": "Engine timed out while computing best move"}), 504
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500, debug=True)
