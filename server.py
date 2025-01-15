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
CORS(app, resources={r"/uci": {"origins": "http://localhost:8081"}, r"/getmoves": {"origins": "http://localhost:8081"}})

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

class SunfishManager:
    def __init__(self):
        self.input_stream = BlockingInput()
        self.output_stream = StringIO()
        self.lock = threading.Lock()

        # Initialize Sunfish with startpos
        self.startpos = sunfish.Position(
            sunfish.initial, 0, (True, True), (True, True), 0, 0
        )

        # Start the UCI loop in a separate thread
        self.thread = threading.Thread(target=self._start_uci_loop, daemon=True)
        self.thread.start()

    def _start_uci_loop(self):
        """Start the Sunfish UCI loop."""
        logger.debug("Starting Sunfish UCI loop")
        sys.stdin = self.input_stream
        sys.stdout = self.output_stream

        try:
            uci.run(sunfish, self.startpos)
        except Exception as e:
            logger.error(f"UCI loop exited with an error: {e}")
        finally:
            logger.debug("Exited Sunfish UCI loop")

    def send_command(self, command):
        """
        Send a UCI command to the Sunfish engine and wait for the appropriate response.

        Args:
            command (str): The UCI command to send.

        Returns:
            list[str]: The response lines from the engine.
        """
        with self.lock:
            # Log the incoming command
            logger.debug(f"Sending UCI command: {command}")

            # Write the command to the blocking input
            self.input_stream.write(command + "\n")

            # Clear the output stream
            self.output_stream.truncate(0)
            self.output_stream.seek(0)

            # Handle specific commands that require waiting for a particular response
            if command.startswith("go"):
                return self._wait_for_response("bestmove")
            elif command.startswith("getmoves"):
                return self._wait_for_response("legal moves:")
            elif command.startswith("position"):
                # Ensure the position is set successfully
                return ["info string position set successfully"]

            # For all other commands, return generic output
            return self._wait_for_response()

    def _wait_for_response(self, expected_prefix=None, timeout=15):
        """
        Wait for a response containing a specific prefix.

        Args:
            expected_prefix (str): The prefix to look for in the response. If None, return the first response received.
            timeout (int): Maximum time to wait in seconds.

        Returns:
            list[str]: The response lines matching the prefix or the full response.

        Raises:
            TimeoutError: If no matching response is found within the timeout.
        """
        start_time = time.time()

        while True:
            self.output_stream.seek(0)
            response = self.output_stream.read().strip().split("\n")

            # If a specific prefix is expected, filter the response
            if expected_prefix:
                filtered_response = [line for line in response if line.startswith(expected_prefix)]
                if filtered_response:
                    logger.debug(f"Matched response: {filtered_response}")
                    return filtered_response

            # If no prefix is expected, return the full response
            if not expected_prefix and response and any(line.strip() for line in response):
                logger.debug(f"Received response: {response}")
                return response

            # Timeout check
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Timed out waiting for response: {expected_prefix or 'any response'}")

            # Sleep briefly to avoid busy-waiting
            time.sleep(0.1)


# Initialize SunfishManager
engine = SunfishManager()

@app.route("/uci", methods=["POST"])
def uci_endpoint():
    """
    Handle UCI commands via the Flask API.
    Request JSON:
      { "command": "<uci_command>" }
    Response JSON:
      { "response": ["<line1>", "<line2>", ...] }
    """
    data = request.get_json()
    if not data or "command" not in data:
        return jsonify({"error": "Missing 'command' field in request"}), 400

    command = data["command"]
    try:
        # Send the command to Sunfish and get the response
        response = engine.send_command(command)
        return jsonify({"response": response})
    except TimeoutError as e:
        logger.error(f"Timeout error: {e}")
        return jsonify({"error": "Engine timed out waiting for response"}), 504
    except Exception as e:
        logger.error(f"Error processing command: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500, debug=True)
