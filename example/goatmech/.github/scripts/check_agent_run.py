"""Turn an agent run's execution log into a clear pass or a clear failure.

    python .github/scripts/check_agent_run.py <execution_file> <label>

An agent that errors can leave a green job behind. This step reads the log
that claude-code-action writes, prints the agent's final message and cost to
the step summary, and fails the job with a remedy that fits the cause.
Adapted from DisMech's review verifier.
"""

import json
import os
import sys
from pathlib import Path

BILLING = ("out of credit", "credit balance", "insufficient quota", "billing", "payment required")
LIMITS = ("usage limit", "weekly limit", "hit your limit", "rate limit", "rate_limit", "limit reached")


def summary(md: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(md + "\n")


def fail(label: str, title: str, body: str) -> int:
    print(f"::error title={label}: {title}::{body}")
    summary(f"### {label}: {title}\n\n{body}")
    return 1


def load(path: Path) -> list:
    raw = path.read_text(encoding="utf-8").strip()
    try:
        events = json.loads(raw)
        return events if isinstance(events, list) else [events]
    except json.JSONDecodeError:
        return [json.loads(line) for line in raw.splitlines() if line.strip()]


def main() -> int:
    file_arg, label = (sys.argv[1:3] + ["", "Agent"])[:2]
    default = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "claude-execution-output.json"
    path = Path(file_arg) if file_arg else default
    if not path.is_file():
        return fail(label, "did not run", "No execution log was found. The agent did not start.")
    results = [e for e in load(path) if isinstance(e, dict) and e.get("type") == "result"]
    if not results:
        return fail(label, "did not finish", "The log has no result event. The agent did not complete.")
    r = results[-1]
    stats = f"turns={r.get('num_turns')} cost=${r.get('total_cost_usd')} subtype={r.get('subtype')}"
    detail = str(r.get("result") or "").strip()
    if not r.get("is_error"):
        summary(f"### {label}\n\n`{stats}`\n\n~~~~\n{detail[:6000]}\n~~~~")
        print(f"{label} finished: {stats}")
        return 0
    text = f"{r.get('error') or ''} {detail}".lower()
    if r.get("subtype") == "error_max_turns":
        return fail(label, "ran out of turns", f"{stats}. Raise max_turns for this workflow in "
                    ".github/agent-config.yaml, or narrow its prompt. This is not a credential problem.")
    if any(m in text for m in BILLING):
        return fail(label, "account out of credit", f"{stats}. The account behind ANTHROPIC_API_KEY "
                    "has no credit. Top it up. Re-setting the secret will not help.")
    if any(m in text for m in LIMITS):
        return fail(label, "usage limit reached", f"{stats}. The run used CLAUDE_CODE_OAUTH_TOKEN and "
                    "its subscription limit is spent. Set ANTHROPIC_API_KEY, which is preferred when "
                    "present, or wait for the limit to reset.")
    return fail(label, "errored", f"{stats} detail={detail[:500]!r}. Common causes: a retired model "
                "name in .github/agent-config.yaml, a bad credential, or a cancelled run.")


if __name__ == "__main__":
    sys.exit(main())
