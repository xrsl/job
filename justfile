set dotenv-load
# Default recipe (shows help)
default:
    @just --list

# Install dependencies and setup environment
setup:
    uv sync
    uv run playwright install

alias s := search
# - just search              → all companies, all TOML keywords
# - just search novo         → filter to Novo, all TOML keywords
# - just search novo python  → filter to Novo, only search "python"
# Search career pages: just search [company] [keyword]
search company="" keyword="":
    @if [ -z "{{company}}" ]; then \
        uv run job search; \
    elif [ -z "{{keyword}}" ]; then \
        uv run job search --company "{{company}}"; \
    else \
        uv run job search --company "{{company}}" --keyword "{{keyword}}"; \
    fi

alias p := prek
# Run pre-commit checks (includes ruff, ty)
prek:
    prek run --all-files

# Format code using Ruff
fmt:
    uvx ruff format .

# Lint code using Ruff
lint:
    uvx ruff check .

# Type check code using ty
type:
    uvx ty check .

alias c := clean
# Clean up common temporary files
clean:
    rm -rf __pycache__
    rm -rf .ruff_cache
    rm -rf .pytest_cache
    rm -rf htmlcov
    rm -rf build
    rm -rf dist
    rm -rf .coverage
    rm -rf *.egg-info
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Generate schema/schema.json from schema/schema.cue
schema:
    cue def schema/schema.cue --out jsonschema > schema/schema.json
    @echo "✅ schema.json regenerated"
    @cat schema/schema.json | schema/order-schema.sh > schema/schema.json.tmp \
    && mv schema/schema.json.tmp schema/schema.json
    @echo "✅ schema.json keys successfully ordered"

# Format and lint job-search.toml with tombi
tombi:
    tombi format job-search.toml
    tombi lint job-search.toml
    @echo "✅ job-search.toml formatted and linted"


alias b := build
# Build wheel and source distribution at dist/
build:
    rm -rf dist
    uv build --sdist --wheel --out-dir dist
    @echo "✅ built wheel and source distribution"

alias i := install
# Install job CLI tool from dist/*.whl
install: build
    uv tool install dist/*.whl --force
    @echo "✅ installed job CLI tool"

alias gi := git-install
# Install job CLI tool from git
git-install:
    uv tool install git+https://github.com/xrsl/job.git --python 3.12
    @echo "✅ installed job CLI tool from git"


# Uninstall job CLI tool
uninstall:
    uv tool uninstall job
    @echo "✅ uninstalled job CLI tool"

# Remove ALL job binaries from system (with confirmation)
rmjob:
    #!/usr/bin/env zsh
    setopt pipefail
    binaries=("${(@f)$(whence -a job 2>/dev/null | sort -u)}")
    # Filter out empty elements
    binaries=(${binaries:#})
    if [[ ${#binaries[@]} -eq 0 ]]; then
        echo "No job binaries found."
        uv tool uninstall job 2>/dev/null || true
        exit 0
    fi
    echo "Found job binaries:"
    for bin in $binaries; do echo "  - $bin"; done
    echo ""
    read -q "REPLY?Remove all? [y/N] "
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for bin in $binaries; do
            rm -f "$bin" && echo "✅ removed $bin"
        done
        uv tool uninstall job 2>/dev/null || true
    else
        echo "Aborted."
    fi

alias r := release
# Release new version: just release [major|minor|patch]
release type:
    bump-my-version bump {{type}}

alias t := test
# Run tests with pytest
test:
    uv run pytest

# Run tests with coverage report
test-cov:
    uv run pytest --cov=job --cov-report=term-missing --cov-report=html


ci: prek lint fmt type test clean
