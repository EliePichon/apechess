#!/usr/bin/env python3
"""Quick test to verify depth_reached is returned in API response."""

import requests
import json

from helpers import BASE_URL

# Simple starting position
TEST_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

print("Testing depth_reached in API response...\n")

# Test 1: Short movetime
print("Test 1: movetime=1000ms (1s), maxdepth=25")
response = requests.post(f"{BASE_URL}/bestmove", json={"fen": TEST_FEN, "movetime": 1000, "maxdepth": 25, "precision": 0.0})
data = response.json()
print(f"Response: {json.dumps(data, indent=2)}")
print(f"Depth reached: {data.get('depth_reached', 'NOT FOUND')}\n")

# Test 2: Fixed depth
print("Test 2: maxdepth=8")
response = requests.post(f"{BASE_URL}/bestmove", json={"fen": TEST_FEN, "maxdepth": 8, "precision": 0.0})
data = response.json()
print(f"Response: {json.dumps(data, indent=2)}")
print(f"Depth reached: {data.get('depth_reached', 'NOT FOUND')}\n")

# Test 3: Longer movetime
print("Test 3: movetime=3000ms (3s), maxdepth=25")
response = requests.post(f"{BASE_URL}/bestmove", json={"fen": TEST_FEN, "movetime": 3000, "maxdepth": 25, "precision": 0.0})
data = response.json()
print(f"Response: {json.dumps(data, indent=2)}")
print(f"Depth reached: {data.get('depth_reached', 'NOT FOUND')}\n")

print("✓ Test complete!")
