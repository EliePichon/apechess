.PHONY: test test-top-n test-ignore test-perf help up down logs

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
	@echo "  make test-perf     - Run performance benchmarks"
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
test: test-top-n test-ignore
	@echo ""
	@echo "✓ All tests completed!"

# Run top_n tests
test-top-n:
	@echo "Running top_n tests..."
	python3 test_top_n.py

# Run ignore_squares tests
test-ignore:
	@echo "Running ignore_squares tests..."
	python3 test_ignore_squares.py

# Run performance benchmarks
test-perf:
	@echo "Running performance benchmarks..."
	@echo "This may take a few minutes..."
	python3 test_performance.py
