"""The identity check: record ids follow the identity enum's rule, which the term check half ignores."""

import pytest
import yaml

from goatmech import terms


def test_the_rule_comes_from_the_schema():
    assert terms.identity_rule() == ("VBO:0400025", True, False)


@pytest.fixture
def records(tmp_path):
    def make(*ids):
        paths = []
        for i, rid in enumerate(ids):
            p = tmp_path / f"r{i}.yaml"
            p.write_text(yaml.safe_dump({"id": rid}))
            paths.append(str(p))  # as the command line gives them
        return paths
    return make


def direct_only(monkeypatch, tree):
    monkeypatch.setattr(terms, "identity_rule", lambda: ("X:1", True, False))
    monkeypatch.setattr(terms, "parents", lambda c: [(p, None) for p in tree.get(c, [])])


def test_direct_children_pass_and_deeper_terms_fail(monkeypatch, records, capsys):
    direct_only(monkeypatch, {"X:2": ["X:1"], "X:3": ["X:2"]})
    assert terms.check_identity(records("X:2", "goatmech:minted")) == 0
    assert terms.check_identity(records("X:3")) == 1
    assert "not a direct child of X:1; its parents: X:2" in capsys.readouterr().out


def test_the_root_itself_fails(monkeypatch, records, capsys):
    direct_only(monkeypatch, {})
    assert terms.check_identity(records("X:1")) == 1
    assert "is the root itself" in capsys.readouterr().out


def test_an_outage_is_exit_2(monkeypatch, records):
    direct_only(monkeypatch, {})

    def down(curie):
        raise OSError("connection refused")

    monkeypatch.setattr(terms, "parents", down)
    assert terms.check_identity(records("X:2")) == 2


def test_nothing_to_check_asks_nothing(monkeypatch, records):
    monkeypatch.setattr(terms, "identity_rule", lambda: ("X:1", False, True))
    monkeypatch.setattr(terms, "parents", lambda c: pytest.fail("no lookup needed"))
    assert terms.check_identity(records("X:3")) == 0
