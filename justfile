set dotenv-load

# Install dependencies and setup environment
setup:
    uv sync
    uv run playwright install

# Run the job CLI
run *args:
    uv run job {{args}}

# Search career pages: just search [company] [keyword]
# - just search              → all companies, all TOML keywords
# - just search novo         → filter to Novo, all TOML keywords
# - just search novo python  → filter to Novo, only search "python"
alias s := search
search company="" keyword="":
    @if [ -z "{{company}}" ]; then \
        uv run job search; \
    elif [ -z "{{keyword}}" ]; then \
        uv run job search --company "{{company}}"; \
    else \
        uv run job search --company "{{company}}" --keyword "{{keyword}}"; \
    fi

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
    rm -rf .ruff_cache
    rm -rf job.egg-info
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Generate JSON schema from CUE
schema:
    cue def schema/schema.cue --out jsonschema > schema/schema.json
    @echo "✅ schema.json regenerated"
    @cat schema/schema.json | schema/order-schema.sh > schema/schema.json.tmp \
    && mv schema/schema.json.tmp schema/schema.json
    @echo "✅ schema.json keys successfully ordered"

alias b := build
build:
    uv build --sdist --wheel --out-dir dist
    @echo "✅ built wheel and source distribution"

alias i := install
install: build
    uv tool install dist/*.whl --force
    @echo "✅ installed job CLI tool"

uninstall:
    uv tool uninstall job
    @echo "✅ uninstalled job CLI tool"
