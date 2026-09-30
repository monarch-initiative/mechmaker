"""Render .github/prompts/<name>.md for an agent run and write it to $GITHUB_OUTPUT.

    python .github/scripts/render_prompt.py <name>

`${NAME}` placeholders in the prompt are filled from environment variables
named PROMPT_<NAME>. Only run facts go in: repository, numbers, flags. Text
written by other people (issue bodies, comments) never goes into a prompt;
the agent reads it with its tools, as data.

The prompt is read from the checked-out default branch, so a pull request
cannot rewrite the instructions it is reviewed under.
"""

import os
import secrets
import string
import sys
from pathlib import Path

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def main() -> int:
    name = sys.argv[1]
    template = string.Template((PROMPTS / f"{name}.md").read_text())
    values = {k.removeprefix("PROMPT_"): v for k, v in os.environ.items() if k.startswith("PROMPT_")}
    text = template.safe_substitute(values)
    delim = f"PROMPT_{secrets.token_hex(8)}"
    out = os.environ.get("GITHUB_OUTPUT")
    block = f"prompt<<{delim}\n{text}\n{delim}\n"
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(block)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
