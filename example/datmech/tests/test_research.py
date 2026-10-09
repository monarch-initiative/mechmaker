"""The research prompt: fillable placeholders, no stray braces."""

import pytest

from datmech import research


def test_shipped_prompt_is_fillable():
    errors, _ = research.template_problems(research.TEMPLATE.read_text(encoding="utf-8"))
    assert errors == []


@pytest.mark.parametrize("text", [
    "Research {disease_name}.",      # a placeholder this Mech does not fill
    "Return JSON like {\"a\": 1}.",  # literal braces
    "Unbalanced { brace.",
])
def test_bad_prompts_are_caught(text):
    errors, _ = research.template_problems(text)
    assert errors


def test_generic_prompt_warns():
    _, warnings = research.template_problems(research.GENERIC_LINE)
    assert warnings
