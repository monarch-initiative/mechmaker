"""Bring the example Mechs in step with this checkout's template.

    uv run python scripts/sync_examples.py              # every example
    uv run python scripts/sync_examples.py goatmech     # one

Each example's answers are rendered with the template as it is in the
working tree. Every file the render writes is copied into the example,
except the files the Mech owns (OWN below), which are left alone. Those the
template changed since the last sync (_commit) are listed, to merge by hand
where the change applies. A file the template wrote at the last sync and no
longer writes is removed. The answers file takes the render's answers, so a new
question gets its default, and _commit becomes the template commit at the
sync (HEAD; commit the template change first for an exact record).
tests/test_examples.py fails until this has run.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import copier
import yaml

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "example"
ANSWERS = ".copier-answers.yml"

# Files each Mech changed on purpose after generation, and why.
SHARED_OWN = {
    "README.md": "links point into mechmaker, where the example lives",
    "docs/index.md": "links point into mechmaker",
    "mkdocs.yml": "published under mechmaker's site",
    "docs/DOMAIN.md": "the design record",
    "conf/site.yaml": "front-page columns chosen for the domain",
    "tests/data/example_record.yaml": "reshaped to the designed schema",
}
OWN = {
    "goatmech": {
        **SHARED_OWN,
        "src/goatmech/paths.py": "REPO_URL is mechmaker",
        "src/goatmech/schema/goatmech.yaml": "the designed schema",
        "conf/export.yaml": "adds the KGX exports",
        "conf/kgx.yaml": "KGX categories and predicates for breeds",
        "pyproject.toml": "biolink-model, for the KGX exports",
        "conf/literature_scan.yaml": "search terms for goat breeds",
        "conf/oak_config.yaml": "adds NCIT and VT, which the schema uses",
        "research/templates/record.md": "sections in a goat breed's order",
        "registry/goatmech.md": "the filled-in registry entry",
    },
    "ingestmech": {
        **SHARED_OWN,
        "src/ingestmech/paths.py": "REPO_URL is mechmaker",
        "src/ingestmech/schema/ingestmech.yaml": "the designed schema",
        "curation/source_queue.tsv": "the converted knowledge base and its sources",
        "registry/ingestmech.md": "the filled-in registry entry",
    },
}


def answers(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def render(name: str, dest: Path, ref: str = "HEAD") -> Path:
    """The example's answers, rendered with the template at REF (HEAD: the working tree)."""
    # vcs_ref="HEAD" with a dirty tree renders the working tree, not a release tag.
    copier.run_copy(str(ROOT), str(dest), data=answers(EXAMPLES / name / ANSWERS), defaults=True,
                    unsafe=True, quiet=True, vcs_ref=ref)
    return dest


def files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} - {ANSWERS}


def since(name: str, ref: str, fresh: Path, owned: list[str],
          tmp: Path) -> tuple[list[str], list[str]] | None:
    """(Owned files the template changed since REF, files it wrote then and writes no
    longer), or None if REF cannot be rendered."""
    try:
        before = render(name, tmp / "before", ref)
    except Exception:  # an unknown ref, or a template too old for today's answers
        return None
    changed = [rel for rel in owned
               if not (before / rel).is_file() or (before / rel).read_bytes() != (fresh / rel).read_bytes()]
    return changed, sorted(files(before) - files(fresh) - set(OWN[name]))


def compare(name: str, fresh: Path) -> tuple[list[str], list[str]]:
    """(template files the example lacks or differs on, owned files that differ from the render)."""
    mech = EXAMPLES / name
    drifted, owned = [], []
    for path in sorted(p for p in fresh.rglob("*") if p.is_file()):
        rel = path.relative_to(fresh).as_posix()
        if rel == ANSWERS:
            continue
        same = (mech / rel).is_file() and (mech / rel).read_bytes() == path.read_bytes()
        if not same:
            (owned if rel in OWN[name] else drifted).append(rel)
    return drifted, owned


def sync(name: str) -> None:
    mech = EXAMPLES / name
    with tempfile.TemporaryDirectory() as tmp:
        fresh = render(name, Path(tmp) / name)
        drifted, owned = compare(name, fresh)
        last = yaml.safe_load((mech / ANSWERS).read_text(encoding="utf-8"))["_commit"]
        found = since(name, str(last), fresh, owned, Path(tmp))
        touched, dropped = found if found else (None, [])
        dropped = [rel for rel in dropped if (mech / rel).is_file()]
        for rel in dropped:
            (mech / rel).unlink()
        for rel in drifted:
            (mech / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fresh / rel, mech / rel)
        # The render's answers, as Copier wrote them, with the example's source
        # and the template commit it now matches.
        src = yaml.safe_load((mech / ANSWERS).read_text(encoding="utf-8"))["_src_path"]
        commit = subprocess.run(["git", "describe", "--tags", "--always", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        text = (fresh / ANSWERS).read_text(encoding="utf-8")
        text = re.sub(r"(?m)^_commit: .*$", f"_commit: {commit}", text)
        text = re.sub(r"(?m)^_src_path: .*$", f"_src_path: {src}", text)
        (mech / ANSWERS).write_text(text, encoding="utf-8")
    print(f"example/{name}: {len(drifted)} file(s) copied from the template" +
          "".join(f"\n  {rel}" for rel in drifted))
    if dropped:
        print(f"  removed, no longer written by the template: {', '.join(dropped)}")
    if touched is None:
        print(f"  could not render the last sync ({last}); check the owned files by hand: {', '.join(owned)}")
    elif touched:
        print(f"  owned files the template changed since {last}; merge by hand where it applies: "
              f"{', '.join(touched)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", metavar="NAME",
                        help=f"examples to sync (default: all of {', '.join(sorted(OWN))})")
    args = parser.parse_args(argv)
    unknown = sorted(set(args.names) - set(OWN))
    if unknown:
        parser.error(f"no example named {', '.join(unknown)}")
    for name in args.names or sorted(OWN):
        sync(name)
    print("Then run each changed example's `just qc`, and `just test`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
