"""Build the documentation site, in the usual LinkML style.

    python -m <slug>.docs generate   # write the generated pages into docs/
    python -m <slug>.docs build      # generate, then build the site into site/

Generated, and not committed:
  docs/elements/     one page per class, slot, enum and type (LinkML gen-doc),
                     with class diagrams and the example record inline
  docs/structure.md  what a record can contain, as one diagram
  docs/corpus.md     counts from the records
  docs/schema/       the schema with imports merged, and as JSON Schema
  docs/records/      a copy of the record browser (pages/), when there is one

`build` runs MkDocs in strict mode, so a broken link fails. Every link to the
record browser is relative, so the site works wherever it is hosted.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from .paths import BUILD_DIR, MECH_NAME, PAGES_DIR, RECORD_CLASS, REPO_ROOT, SCHEMA_PATH, SLUG
from .report import compute

DOCS = REPO_ROOT / "docs"
SITE = REPO_ROOT / "site"
EXAMPLE = REPO_ROOT / "tests" / "data" / "example_record.yaml"


def generate() -> None:
    from linkml.generators.docgen import DocGenerator
    from linkml.generators.erdiagramgen import ERDiagramGenerator
    from linkml.generators.jsonschemagen import JsonSchemaGenerator
    from linkml.generators.yamlgen import YAMLGenerator

    # Class pages show examples named <Class>-<name>.yaml.
    examples = BUILD_DIR / "doc-examples"
    shutil.rmtree(examples, ignore_errors=True)
    examples.mkdir(parents=True)
    if EXAMPLE.exists():
        shutil.copy(EXAMPLE, examples / f"{RECORD_CLASS}-example.yaml")

    elements = DOCS / "elements"
    shutil.rmtree(elements, ignore_errors=True)
    DocGenerator(str(SCHEMA_PATH), example_directory=str(examples)).serialize(directory=str(elements))

    diagram = ERDiagramGenerator(str(SCHEMA_PATH), structural=True).serialize()
    (DOCS / "structure.md").write_text(
        f"# Record structure\n\n"
        f"Everything a `{RECORD_CLASS}` record can contain, from the record down. "
        f"Each class links to its page under [Schema](elements/index.md).\n\n{diagram}\n"
    )

    schema_out = DOCS / "schema"
    shutil.rmtree(schema_out, ignore_errors=True)
    schema_out.mkdir(parents=True)
    (schema_out / f"{SLUG}.yaml").write_text(YAMLGenerator(str(SCHEMA_PATH), mergeimports=True).serialize())
    (schema_out / f"{SLUG}.schema.json").write_text(
        JsonSchemaGenerator(str(SCHEMA_PATH), not_closed=False, top_class=RECORD_CLASS).serialize()
    )

    records = DOCS / "records"
    shutil.rmtree(records, ignore_errors=True)
    if (PAGES_DIR / "index.html").exists():
        shutil.copytree(PAGES_DIR, records)

    stats = compute()
    rows = "\n".join(
        f"| {k.replace('_', ' ')} | {v} |" for k, v in stats.items() if k not in ("mech", "by_status")
    )
    status = "\n".join(f"| {k} | {v} |" for k, v in stats["by_status"].items()) or "| none | 0 |"
    (DOCS / "corpus.md").write_text(
        f"# Corpus\n\nCounted from the records when this site was built. "
        f"`just report` gives the same numbers.\n\n"
        f"| Measure | Count |\n|---|---|\n{rows}\n\n"
        f"## Records by status\n\n| Status | Records |\n|---|---|\n{status}\n"
    )
    print(f"Generated docs/elements/, docs/schema/, docs/structure.md and docs/corpus.md for {MECH_NAME}.")


def build() -> int:
    generate()
    shutil.rmtree(SITE, ignore_errors=True)
    cmd = [sys.executable, "-m", "mkdocs", "build", "--strict", "-d", str(SITE)]
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        return result.returncode
    print(f"Built the site in {SITE.relative_to(REPO_ROOT)}/.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["generate", "build"])
    args = parser.parse_args(argv)
    if args.command == "generate":
        generate()
        return 0
    return build()


if __name__ == "__main__":
    sys.exit(main())
