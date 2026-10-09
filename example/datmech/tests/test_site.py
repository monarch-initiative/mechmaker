"""Site settings: every palette stays readable, and bad settings are caught."""

import pytest

from datmech import site


@pytest.mark.parametrize("palette", sorted(site.PRIMARY))
def test_links_are_readable_on_every_palette(palette):
    colors = site.colors({**site.DEFAULTS, "palette": palette})
    assert site.contrast(colors["link_light"], site.LIGHT_BG) >= site.MIN_CONTRAST
    assert site.contrast(colors["link_dark"], site.DARK_BG) >= site.MIN_CONTRAST


@pytest.mark.parametrize("palette", sorted(site.PRIMARY))
def test_header_text_is_the_more_readable_choice(palette):
    colors = site.colors({**site.DEFAULTS, "palette": palette})
    other = "#1f1f1f" if colors["on_primary"] == "#ffffff" else "#ffffff"
    assert site.contrast(colors["on_primary"], colors["primary"]) >= site.contrast(other, colors["primary"])


@pytest.mark.parametrize("browser", [True, False])
def test_check_reports_the_docs_header_as_material_pairs_it(tmp_path, monkeypatch, capsys, browser):
    monkeypatch.setattr(site, "load", lambda: {**site.DEFAULTS, "palette": "cyan"})
    monkeypatch.setattr(site, "BROWSER", site.BROWSER if browser else tmp_path / "no-render.py")
    if browser and not site.BROWSER.exists():
        pytest.skip("this Mech has no record browser")
    assert site.main(["check"]) == 0
    out = capsys.readouterr().out
    assert "docs header: #ffffff on #00bdd6, contrast 2.3 (WARNING" in out
    assert ("browser header:" in out) == browser and ("links on" in out) == browser


def test_committed_settings_are_valid():
    assert site.problems(site.load()) == []


@pytest.mark.parametrize("bad", [
    {"palette": "chartreuse"},
    {"accent": "brown"},
    {"theme": "sepia"},
    {"index_columns": "name"},
])
def test_bad_settings_are_rejected(bad):
    assert site.problems({**site.DEFAULTS, **bad})
