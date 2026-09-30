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

# Build this documentation site into site/ (strict: a broken link fails).
# It includes the GoatMech example's own site at /example/goatmech/.
docs-build: example-site
    uv run python scripts/gen_docs.py
    uv run mkdocs build --strict -d site

# Serve this documentation at http://127.0.0.1:8000 while you edit
docs-serve: example-site
    uv run python scripts/gen_docs.py
    uv run mkdocs serve

# Build the GoatMech example's site (its docs and record browser) into docs/example/goatmech/
example-site:
    cd example/goatmech && just install && just docs-build
    rm -rf docs/example/goatmech
    mkdir -p docs/example
    cp -r example/goatmech/site docs/example/goatmech

# Render a sample Mech into a directory to look at: `just sample /tmp/samplemech`
sample dest:
    uv run copier copy --trust --defaults --data-file tests/answers/habitat.yml . {{dest}}
