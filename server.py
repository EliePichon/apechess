from flask import Flask, request, jsonify
from sunfish import Position, Searcher, Move, parse, render, initial
import time

app = Flask(__name__)

# Initialize the Sunfish engine state



# Create a SunfishWrapper instance
#engine = SunfishWrapper()

@app.route('/uci', methods=['POST'])
def uci_endpoint():
    """
    Flask endpoint to handle UCI commands.
    Request JSON:
      { "command": "uci" }
    Response JSON:
      { "response": ["uciok"] }
    """
    data = request.get_json()
    if not data or "command" not in data:
        return jsonify({"error": "Missing 'command' field in request"}), 400

    command = data["command"]
    response = engine.handle_command(command)
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
