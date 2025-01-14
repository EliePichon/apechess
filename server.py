from flask import Flask, request, jsonify
import tools.uci as uci
import sunfish
from io import StringIO
import sys

app = Flask(__name__)

# Redirect UCI output
class UCIEngine:
    def __init__(self):
        self.startpos = sunfish.Position(
            sunfish.initial, 0, (True, True), (True, True), 0, 0
        )
        self.searcher = sunfish.Searcher()
        self.hist = [self.startpos]

    def handle_uci_command(self, command):
        """
        Handle a UCI command and return the engine's response.
        """
        # Save original stdin and stdout
        old_stdin = sys.stdin
        old_stdout = sys.stdout
        sys.stdin = StringIO(command + "\n")
        sys.stdout = StringIO()

        try:
            # Redirected input for `uci.run`
            uci.run(sunfish, self.startpos)
            # Capture the redirected output
            output = sys.stdout.getvalue()
        finally:
            # Restore stdin and stdout
            sys.stdin = old_stdin
            sys.stdout = old_stdout

        # Return the captured output as a list of lines
        return output.strip().split("\n")


# Create a single shared instance of the UCI engine
engine = UCIEngine()


@app.route("/uci", methods=["POST"])
def uci_endpoint():
    """
    Flask endpoint for handling UCI commands.
    Request JSON: { "command": "<uci_command>" }
    Response JSON: { "response": ["<line1>", "<line2>", ...] }
    """
    data = request.get_json()
    if not data or "command" not in data:
        return jsonify({"error": "Missing 'command' field in request"}), 400

    # Extract the UCI command
    command = data["command"]
    try:
        # Pass the command to the engine and get the response
        response = engine.handle_uci_command(command)
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500, debug=True)
