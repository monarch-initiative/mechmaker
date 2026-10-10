"""The BioPortal workaround: ancestors accepts the checks' arguments once patched."""

import io

import pytest

from datmech import oak_compat, termcheck

base = pytest.importorskip("oaklib.implementations.ontoportal.ontoportal_implementation_base")


def test_patched_ancestors_takes_predicates(monkeypatch):
    Base = base.OntoPortalImplementationBase

    def narrow(self, uri):  # the shape OAK 0.7.4 has
        return iter({"X:2": ["X:1"], "X:3": ["X:2", "X:1"]}.get(uri, []))

    monkeypatch.setattr(Base, "ancestors", narrow)
    oak_compat.patch()
    got = list(Base.ancestors(object(), "X:3", predicates=["rdfs:subClassOf"], reflexive=True))
    assert got == ["X:3", "X:2", "X:1"]
    assert list(Base.ancestors(object(), ["X:2"], reflexive=False)) == ["X:1"]


def test_patch_leaves_a_fixed_oak_alone(monkeypatch):
    Base = base.OntoPortalImplementationBase

    def full(self, start_curies, predicates=None, reflexive=True):
        return iter(["fixed"])

    monkeypatch.setattr(Base, "ancestors", full)
    oak_compat.patch()
    assert Base.ancestors is full


def test_keys_are_masked():
    out = io.StringIO()
    termcheck.Masked(out).write("GET /classes/x?display_context=false&apikey=abc-123 failed")
    assert "abc-123" not in out.getvalue() and "apikey=***" in out.getvalue()
