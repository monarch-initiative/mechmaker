"""Print `model=` and `max-turns=` for one workflow, for $GITHUB_OUTPUT.

    python .github/scripts/agent_config.py <workflow> [--override MODEL] [--tier TIER]

Fails if no model can be resolved: a silent default is how a repository ends
up running a model nobody chose.
"""

import argparse
import sys
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[1] / "agent-config.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow")
    parser.add_argument("--override", default="")
    parser.add_argument("--tier", default="", help="effort tier; looks in the workflow's `tiers` map")
    args = parser.parse_args()
    cfg = yaml.safe_load(CONFIG.read_text()) or {}
    wf = (cfg.get("workflows") or {}).get(args.workflow) or {}
    tier_model = (wf.get("tiers") or {}).get(args.tier) if args.tier else None
    model = args.override.strip() or tier_model or wf.get("model") or cfg.get("default_model")
    turns = wf.get("max_turns") or cfg.get("default_max_turns") or 40
    if not model:
        print(f"{CONFIG} names no model for {args.workflow} and has no default_model", file=sys.stderr)
        return 1
    print(f"model={model}")
    print(f"max-turns={int(turns)}")
    print(f"{args.workflow}: model={model} max_turns={turns}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
