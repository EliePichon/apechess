from flask import Flask, request, jsonify
from sunfish2 import initial #Searcher, Move, parse, render, initial, Position
import time


app = Flask(__name__)

@app.route('/')
def home():
    return "Flask is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500, debug=True)
