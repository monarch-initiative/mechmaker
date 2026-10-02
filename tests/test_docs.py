"""The agent-facing docs: the start prompt, the skills' script paths, and llms.txt."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gen_docs  # noqa: E402


def prompt_in(path: Path) -> str:
    m = re.search(r"```text\n(.*?)```", path.read_text(), re.S)
    assert m, f"{path.name} has no start prompt"
    return m.group(1)


def test_the_start_prompt_is_the_same_everywhere():
    want = prompt_in(ROOT / "docs" / "getting-started.md")
    for page in (ROOT / "README.md", ROOT / "docs" / "index.md"):
        assert prompt_in(page) == want, page.name
    assert "npx skills add monarch-initiative/mechmaker" in want


def test_skills_call_scripts_by_their_own_folder():
    # Installed skills do not sit in a mechmaker checkout, so a command like
    # `python skills/make-mech/scripts/...` fails for everyone who installed them.
    for skill in (ROOT / "skills").glob("*/SKILL.md"):
        bad = re.findall(r"python3? skills/\S+", skill.read_text())
        assert not bad, f"{skill.parent.name}: {bad}"


def test_llms_txt_links_every_page_and_skill():
    gen_docs.main()
    text = (ROOT / "docs" / "llms.txt").read_text()
    assert text.startswith("# mechmaker\n\n> ")
    assert gen_docs.start_prompt() in text
    for _, path in gen_docs.nav_pages():
        if path.startswith("skills/") and path != "skills/index.md":
            name = Path(path).stem
            assert f"{gen_docs.RAW}skills/{name}/SKILL.md" in text, name
            assert (ROOT / "skills" / name / "SKILL.md").exists()
    for raw in re.findall(re.escape(gen_docs.RAW) + r"(\S+?)\)", text):
        assert (ROOT / raw).exists(), raw  # a raw link only to a file in git
