# mechmaker: the template's own checks.

default:
    @just --list --unsorted

# Install dev tools
install:
    uv sync

# Fast tests: render the template under several answer sets
test *args:
    uv run pytest -m "not slow" {{args}}

# Slow test: generate a Mech, install it, run its `just qc` (network)
test-generated:
    uv run pytest -m slow -s

# Lint the repository's own code
lint:
    uv run ruff check .

# Build this documentation site into site/ (strict: a broken link fails)
docs-build:
    uv run python scripts/gen_docs.py
    uv run mkdocs build --strict -d site

# Serve this documentation at http://127.0.0.1:8000 while you edit
docs-serve:
    uv run python scripts/gen_docs.py
    uv run mkdocs serve

# Render a sample Mech into a directory to look at: `just sample /tmp/samplemech`
sample dest:
    uv run copier copy --trust --defaults --data-file tests/answers/habitat.yml . {{dest}}
