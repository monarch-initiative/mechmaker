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
# It includes each example Mech's own site, at /example/<name>/.
docs-build: example-sites
    uv run python scripts/gen_docs.py
    uv run mkdocs build --strict -d site

# Serve this documentation at http://127.0.0.1:8000 while you edit
docs-serve: example-sites
    uv run python scripts/gen_docs.py
    uv run mkdocs serve

# Build every example Mech's site (its docs and record browser) into docs/example/
example-sites: (example-site "goatmech") (example-site "ingestmech")

# Build one example Mech's site into docs/example/<name>/
example-site name:
    cd example/{{name}} && just install && just docs-build
    rm -rf docs/example/{{name}}
    mkdir -p docs/example
    cp -r example/{{name}}/site docs/example/{{name}}

# Check this machine for the tools (and, with --network, the services) a Mech needs
check-env *args:
    python3 skills/make-mech/scripts/check_env.py {{args}}

# Render a sample Mech into a directory to look at: `just sample /tmp/samplemech`
sample dest:
    uv run copier copy --trust --defaults --vcs-ref HEAD --data-file tests/answers/habitat.yml . {{dest}}

# Bring the example Mechs in step with the template (tests/test_examples.py checks it)
sync-examples *names:
    uv run python scripts/sync_examples.py {{names}}
