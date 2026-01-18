set dotenv-load

# Install dependencies and setup environment
setup:
    uv sync
    uv run playwright install

# Run the job CLI
run *args:
    uv run job {{args}}

# Format code using Ruff
fmt:
    uvx ruff format .

# Lint code using Ruff
lint:
    uvx ruff check .

# Fix linting issues using Ruff
fix:
    uvx ruff check --fix .

# Clean up common temporary files
clean:
    rm -rf __pycache__
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
