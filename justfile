set dotenv-load := true

# Default recipe (shows help)
default:
    @just --list

# Install dependencies and setup environment
setup:
    uv sync --all-groups
    uv run playwright install

alias s := search

# Search career pages: just search [company] [keyword]
search company="" keyword="":
    @if [ -z "{{ company }}" ]; then \
        uv run job search; \
    elif [ -z "{{ keyword }}" ]; then \
        uv run job search --company "{{ company }}"; \
    else \
        uv run job search --company "{{ company }}" --keyword "{{ keyword }}"; \
    fi

alias ls-m := ls-models

# List available models (optional filter: just ls-m openai)
ls-models filter="":
    uv run python scripts/list_models.py "{{ filter }}"

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

# Generate schema/schema.json from Pydantic models
schema:
    @echo "🔄 Generating schema.json from Pydantic..."
    @uv run python -c "from job.config import write_schema; write_schema()"
    @echo "✅ schema.json regenerated"

# Format and lint job.toml with tombi
tombi:
    tombi format job.toml
    tombi lint job.toml
    @echo "✅ job.toml formatted and linted"

alias b := build

# Build wheel and source distribution at dist/
build:
    rm -rf dist
    uv build --sdist --wheel --out-dir dist
    @echo "✅ built wheel and source distribution"

alias bi := build-install

# Install job CLI tool from dist/*.whl
build-install: build
    uv tool install dist/*.whl --force
    @echo "✅ installed job CLI tool"

alias ei := editable-install

# Install job CLI tool in editable mode (for development)
editable-install:
    uv tool install --editable . --python 3.12
    @echo "✅ installed job CLI tool in editable mode"

alias gi := git-install

# Install job CLI tool from git
git-install:
    uv tool install git+https://github.com/xrsl/job.git --python 3.12
    @echo "✅ installed job CLI tool from git"

alias u := uninstall

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
    bump-my-version bump {{ type }}

alias rp := release-push

# Release new version: just release [major|minor|patch] and push
release-push type:
    bump-my-version bump {{ type }}
    git push
    git push --tags
    @echo "✅ released and pushed {{ type }} version"

alias t := test

# Run tests with pytest
test +FLAGS='-q': && clean
    uv run pytest {{ FLAGS }}

# Run tests with coverage report
test-cov:
    uv run pytest --cov=job --cov-report=term-missing --cov-report=html

ci: prek lint fmt type test clean
