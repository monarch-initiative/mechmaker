"""Deep research for one record, through deep-research-client.

    python -m <slug>.research providers                 # which providers this machine can use
    python -m <slug>.research run PROVIDER TARGET [...]  # research one record, or a new name
    python -m <slug>.research validate REPORT            # redo a report's reference and term checks
    python -m <slug>.research status                     # which records have research, by provider
    python -m <slug>.research check-template             # the prompt can be filled, and is adapted

TARGET is a record's filename stem, or the name of something that has no
record yet. The report goes to research/<stem>-deep-research-<provider>.md,
with a citations sidecar, and carries its provider, model, timing and check
results in its frontmatter.

deep-research-client runs through uvx in its own environment: it needs
Python 3.12 or newer and brings dependencies a Mech does not otherwise need.
Reports are leads for a curator, never record input. See research/README.md.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .paths import RECORD_NOUN, RECORDS_DIR, REPO_ROOT
from .validate import iter_records, load, slugify

VERSION = "0.2.12"
CLIENT = [
    "uvx", "--python", "3.13",
    "--from", f"deep-research-client[validation,terms]=={VERSION}",
    "deep-research-client",
]
RESEARCH_DIR = REPO_ROOT / "research"
TEMPLATE = RESEARCH_DIR / "templates" / "record.md"

# Provider, and what it needs. The client decides; this is the quick local view.
PROVIDERS = {
    "claude_code": ("the `claude` command, signed in (sign-in not checked here)", None),
    "cyberian": ("an agent CLI such as `claude`, and agentapi (agentapi not checked here)", None),
    "openai": ("OpenAI Deep Research", "OPENAI_API_KEY"),
    "falcon": ("Edison Scientific", "EDISON_API_KEY"),
    "asta": ("Asta", "ASTA_API_KEY"),
    "perplexity": ("Perplexity", "PERPLEXITY_API_KEY"),
    "consensus": ("Consensus", "CONSENSUS_API_KEY"),
    "openscientist": ("OpenScientist", "OPENSCIENTIST_API_KEY"),
}

# Validation runs after the report is written, into the caches the Mech's own
# validators read. Exit code 3 means the report is saved and a check found
# problems: read the report's validation sections; do not pay for a rerun.
CHECKS = [
    "--validate-references", "--validation-cache-dir", "references_cache",
    "--validate-terms", "--term-cache-dir", "cache", "--term-oak-config", "conf/oak_config.yaml",
]


# The placeholders target_vars fills. The client reads any other {...} as a
# placeholder too, and fails on it.
PLACEHOLDERS = {"name", "id", "label", "synonyms", "record_noun"}
# A line of the generic prompt the template ships; still present means the
# prompt was never adapted to docs/DOMAIN.md.
GENERIC_LINE = "1. What it is, and how it is identified."


def template_problems(text: str) -> tuple[list[str], list[str]]:
    """Errors (the client cannot fill it) and warnings (it is not adapted)."""
    errors = []
    for m in re.finditer(r"\{([^{}]*)\}", text):
        if m.group(1) not in PLACEHOLDERS:
            found = "{" + m.group(1) + "}"
            errors.append(f"{found} is not a placeholder this Mech fills; "
                          f"use one of {', '.join(sorted(PLACEHOLDERS))}, or remove the braces")
    stray = re.sub(r"\{[^{}]*\}", "", text)
    if "{" in stray or "}" in stray:
        errors.append("a brace outside a placeholder; the client would read it as one")
    warnings = []
    if GENERIC_LINE in text:
        warnings.append("the prompt still has the generic sections; rewrite them from docs/DOMAIN.md "
                        "(the design-mech-schema and deep-research skills say how)")
    return errors, warnings


def check_template() -> int:
    if not TEMPLATE.exists():
        print(f"ERROR: no research prompt at {TEMPLATE.relative_to(REPO_ROOT)}")
        return 1
    errors, warnings = template_problems(TEMPLATE.read_text())
    for e in errors:
        print(f"ERROR {TEMPLATE.relative_to(REPO_ROOT)}: {e}")
    for w in warnings:
        print(f"WARNING {TEMPLATE.relative_to(REPO_ROOT)}: {w}")
    if not errors:
        print(f"{TEMPLATE.relative_to(REPO_ROOT)}: placeholders are fillable.")
    return 1 if errors else 0


def available() -> dict[str, bool]:
    """Which providers look usable here. Key values are never read, only their presence."""
    out = {}
    for name, (_, key) in PROVIDERS.items():
        out[name] = bool(os.environ.get(key)) if key else shutil.which("claude") is not None
    return out


def target_vars(target: str) -> tuple[str, list[str]]:
    """The report's stem and the template variables for a record or a new name."""
    match = sorted(RECORDS_DIR.rglob(f"{target}.yaml"))
    if match:
        data = load(match[0]) or {}
        name = str(data.get("name") or target)
        term = data.get("record_term") or {}
        values = {
            "name": name,
            "id": str(data.get("id", "")),
            "label": str(term.get("label", "")) if isinstance(term, dict) else "",
            "synonyms": ", ".join(map(str, data.get("synonyms") or [])),
        }
        stem = match[0].stem
    else:
        values = {"name": target.replace("_", " "), "id": "", "label": "", "synonyms": ""}
        stem = slugify(values["name"])
    values["record_noun"] = RECORD_NOUN
    args = []
    for k, v in values.items():
        args += ["--var", f"{k}={v}"]
    return stem, args


def run(provider: str, target: str, extra: list[str], force: bool) -> int:
    if not TEMPLATE.exists():
        print(f"ERROR: no research template at {TEMPLATE.relative_to(REPO_ROOT)}")
        return 1
    errors, _ = template_problems(TEMPLATE.read_text())
    if errors:
        print("ERROR: the research prompt cannot be filled; run check-template. No provider was called.")
        return 1
    stem, var_args = target_vars(target)
    out = RESEARCH_DIR / f"{stem}-deep-research-{provider}.md"
    if out.exists() and not force:
        print(f"{out.relative_to(REPO_ROOT)} exists. A rerun costs a provider run; "
              "pass --force to replace it.")
        return 1
    RESEARCH_DIR.mkdir(exist_ok=True)
    cmd = CLIENT + [
        "research", "--template", str(TEMPLATE), *var_args, "--provider", provider,
        "--output", str(out), "--separate-citations", f"{out}.citations.md", *CHECKS, *extra,
    ]
    print(f"Researching {stem} with {provider} -> {out.relative_to(REPO_ROOT)}", flush=True)
    code = subprocess.run(cmd, cwd=REPO_ROOT).returncode
    if code == 3 and out.exists():
        print("The report is saved, and its checks found problems: see its Reference Validation and "
              "Term Validation sections. Do not rerun the provider for this.")
    return code


def validate(report: Path) -> int:
    code = 0
    for sub, flags in (
        ("validate-references", ["--in-place", "--cache-dir", "references_cache"]),
        ("validate-terms", ["--in-place", "--cache-dir", "cache", "--oak-config", "conf/oak_config.yaml"]),
    ):
        code = max(code, subprocess.run(CLIENT + [sub, str(report), *flags], cwd=REPO_ROOT).returncode)
    return code


def status() -> int:
    reports = sorted(r for r in RESEARCH_DIR.glob("*-deep-research-*.md")
                     if not r.name.endswith(".citations.md")) if RESEARCH_DIR.exists() else []
    by_stem: dict[str, list[str]] = {}
    for r in reports:
        m = re.match(r"(.+)-deep-research-(.+)\.md$", r.name)
        if m:
            by_stem.setdefault(m.group(1), []).append(m.group(2))
    stems = [p.stem for p in iter_records()]
    for stem in stems:
        print(f"{stem:40} {', '.join(sorted(by_stem.get(stem, []))) or '-'}")
    extra = sorted(set(by_stem) - set(stems))
    if extra:
        print("\nReports for names with no record yet: " + ", ".join(extra))
    print(f"\n{sum(1 for s in stems if s in by_stem)} of {len(stems)} record(s) have research.")
    return 0


def providers() -> int:
    ok = available()
    for name, (what, key) in PROVIDERS.items():
        need = f"set {key}" if key else what
        print(f"  {'ready  ' if ok[name] else 'missing'}  {name:14} {need}")
    if not any(ok.values()):
        print("\nNo provider is ready. The simplest is claude_code: install Claude Code and sign in.")
        return 1
    print("\nThe client's own view, which also checks credit where it can:", flush=True)
    return subprocess.run(CLIENT + ["providers"], cwd=REPO_ROOT).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("providers", help="which providers this machine can use")
    r = sub.add_parser("run", help="research one record, or a new name")
    r.add_argument("provider", choices=sorted(PROVIDERS) + ["mock"])
    r.add_argument("target", help="a record's filename stem, or a name with no record yet")
    r.add_argument("--force", action="store_true", help="replace an existing report")
    v = sub.add_parser("validate", help="redo a report's checks")
    v.add_argument("report", type=Path)
    sub.add_parser("status", help="which records have research")
    sub.add_parser("check-template", help="the prompt can be filled, and is adapted")
    # Anything run does not recognize, such as `-- --fallback`, goes to the client.
    args, extra = parser.parse_known_args(argv)
    if extra and args.cmd != "run":
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    if args.cmd == "providers":
        return providers()
    if args.cmd == "run":
        return run(args.provider, args.target, [a for a in extra if a != "--"], args.force)
    if args.cmd == "validate":
        return validate(args.report)
    if args.cmd == "check-template":
        return check_template()
    return status()


if __name__ == "__main__":
    sys.exit(main())
