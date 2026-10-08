#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Write a MechRegistry "Suggest a new Mech" issue from a Mech's draft entry.

    uv run registry_issue.py <mech>               # the issue body, on stdout
    uv run registry_issue.py <mech> --title       # the issue title alone

The draft is `registry/<slug>.md` in the Mech. The body follows the headings
of the registry's new-Mech issue form, the way GitHub writes a filled form,
and ends with the whole draft so a maintainer can copy it into
`mech/<slug>/<slug>.md`.

Exit 0 on success, 2 when the folder has no readable registry draft.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

NO_RESPONSE = "_No response_"

# The registry's HumanReviewEnum -> the form's dropdown options.
HUMAN_REVIEW = {
    "pull_request": "Pull request review",
    "spot_check": "Spot check after merge",
    "none": "None",
}


def find_draft(mech: Path) -> Path | None:
    answers = mech / ".copier-answers.yml"
    if answers.is_file():
        slug = (yaml.safe_load(answers.read_text()) or {}).get("mech_slug")
        if slug and (mech / "registry" / f"{slug}.md").is_file():
            return mech / "registry" / f"{slug}.md"
    drafts = sorted((mech / "registry").glob("*.md"))
    return drafts[0] if len(drafts) == 1 else None


def front_matter(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    data = yaml.safe_load(m.group(1)) if m else None
    return data if isinstance(data, dict) else {}


def contact(entry: dict) -> str:
    out = []
    for c in entry.get("contacts") or []:
        details = [d.get("value") for d in c.get("contact_details") or [] if d.get("value")]
        if c.get("orcid"):
            details.append(f"ORCID {c['orcid']}")
        out.append(f"{c.get('label', '')} ({', '.join(details)})" if details else c.get("label", ""))
    return "; ".join(o for o in out if o)


def evidence(curation: dict) -> str:
    policy = " ".join(str(curation.get("evidence_policy") or "").split())
    checks = curation.get("validation") or []
    if checks:
        policy += f"\n\nValidation: {', '.join(checks)}."
    return policy.strip()


def fields(entry: dict) -> list[tuple[str, str]]:
    curation = entry.get("curation") or {}
    count = entry.get("record_count")
    when = entry.get("record_count_date")
    agent = curation.get("agent_curated")
    return [
        ("Name", entry.get("name", "")),
        ("Repository URL", entry.get("repository", "")),
        ("Homepage or browser URL", entry.get("homepage_url", "")),
        ("Description", " ".join(str(entry.get("description") or "").split())),
        ("What one record represents", entry.get("record_type", "")),
        ("Record count and date", f"{count} as of {when}" if count is not None and when else ""),
        ("LinkML schema URL", entry.get("schema_url", "")),
        ("Ontologies used to ground records", ", ".join(entry.get("ontologies") or [])),
        ("License of the records", (entry.get("license") or {}).get("label", "")),
        ("Do AI agents generate or maintain most of the content?",
         "" if agent is None else ("Yes" if agent else "No")),
        ("Human review", HUMAN_REVIEW.get(curation.get("human_review"), "Not documented")),
        ("Evidence policy", evidence(curation)),
        ("Contact", contact(entry)),
        ("Relations to other Mechs", "\n".join(
            f"- {x.get('relation')} {x.get('target')}" for x in entry.get("cross_references") or [])),
    ]


def body(entry: dict, draft: str, name: str) -> str:
    parts = [f"### {label}\n\n{str(value).strip() or NO_RESPONSE}" for label, value in fields(entry)]
    parts.append(
        f"### Draft entry\n\nmechmaker drafted this entry as `{name}` in the Mech's repository.\n\n"
        f"<details><summary>{name}</summary>\n\n````markdown\n{draft.rstrip()}\n````\n\n</details>"
    )
    return "\n\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mech", type=Path, help="the Mech's repository folder")
    p.add_argument("--title", action="store_true", help="print the issue title instead of the body")
    args = p.parse_args(argv)

    draft = find_draft(args.mech)
    text = draft.read_text() if draft else ""
    entry = front_matter(text)
    if not entry.get("name"):
        print(f"No registry draft with a name under {args.mech / 'registry'}", file=sys.stderr)
        return 2
    print(f"Add this Mech: {entry['name']}" if args.title else body(entry, text, f"registry/{draft.name}"),
          end="\n" if args.title else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
