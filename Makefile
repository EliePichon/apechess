.PHONY: test test-top-n test-ignore test-rock-landing test-session test-dream test-perf test-depth test-movetime help up down logs

# Default target
help:
	@echo "Sunfish Chess Engine - Available Commands:"
	@echo ""
	@echo "  make up            - Start the dev server in Docker"
	@echo "  make down          - Stop the dev server"
	@echo "  make logs          - View server logs"
	@echo "  make test          - Run all tests (server must be running)"
	@echo "  make test-top-n    - Run top_n feature tests"
	@echo "  make test-ignore   - Run ignore_squares feature tests"
	@echo "  make test-rock-landing - Run powered pieces (rock-landing) tests"
	@echo "  make test-session  - Run session/stateful engine tests"
	@echo "  make test-dream    - Run Dream API tests (/turn + grade/peek)"
	@echo "  make test-perf     - Run performance benchmarks"
	@echo "  make test-depth    - Run depth performance analysis (15-20 min)"
	@echo "  make test-movetime - Run movetime performance analysis (5-10 min)"
	@echo ""

# Start dev server
up:
	docker-compose up -d
	@echo "Server starting... waiting 3 seconds"
	@sleep 3
	@echo "Server ready at http://localhost:5500"

# Stop dev server
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# Run all tests
test: test-top-n test-ignore test-rock-landing test-session test-dream
	@echo ""
	@echo "✓ All tests completed!"

# Run top_n tests
test-top-n:
	@echo "Running top_n tests..."
	python3 tests/test_top_n.py

# Run ignore_squares tests
test-ignore:
	@echo "Running ignore_squares tests..."
	python3 tests/test_ignore_squares.py

# Run rock-landing (powered pieces) tests
test-rock-landing:
	@echo "Running rock-landing tests..."
	python3 tests/test_rock_landing.py

# Run session/stateful engine tests
test-session:
	@echo "Running session/stateful engine tests..."
	python3 tests/test_session.py

# Run Dream API tests
test-dream:
	@echo "Running Dream API tests..."
	python3 tests/test_dream_api.py

# Run performance benchmarks
test-perf:
	@echo "Running performance benchmarks..."
	@echo "This may take a few minutes..."
	python3 tests/test_performance.py

# Run depth performance analysis
test-depth:
	@echo "Running depth performance analysis..."
	@echo "Testing depths 8, 10, 12, 15 across 6 positions (early/mid/endgame)"
	@echo "This will take 15-20 minutes..."
	@echo ""
	python3 tests/test_depth_performance.py

# Run movetime performance analysis
test-movetime:
	@echo "Running movetime performance analysis..."
	@echo "Testing movetimes 2s, 4s, 7s, 10s with maxdepth=25 across 6 positions"
	@echo "This will take 5-10 minutes..."
	@echo ""
	python3 tests/test_movetime_performance.py
