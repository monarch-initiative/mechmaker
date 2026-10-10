"""DaTMech's rules: curation_priority follows from incidents (docs/DOMAIN.md, Priority)."""

import pytest

from datmech.validate import zip_area_errors

ADVISED = {"name": "Spill", "advisories": [{"advisory_kind": "BOIL_WATER"}]}
QUIET = {"name": "Bloom"}


@pytest.mark.parametrize("incidents, priority, ok", [
    ([ADVISED], "HIGH", True),
    ([ADVISED, QUIET], "MEDIUM", False),
    ([QUIET], "MEDIUM", True),
    ([QUIET], "HIGH", False),
    ([QUIET], "LOW", False),
    ([], "LOW", True),
    ([], "UNASSESSED", True),
    ([], "HIGH", False),
])
def test_priority_follows_incidents(incidents, priority, ok):
    errors = zip_area_errors({"status": "PROPOSED", "state": "OH", "curation_priority": priority,
                              "incidents": incidents})
    assert (not errors) == ok, errors


def test_draft_may_leave_priority_and_state_unset():
    assert zip_area_errors({"status": "DRAFT"}) == []


def test_proposed_needs_priority_and_state():
    errors = zip_area_errors({"status": "PROPOSED"})
    assert any("state" in e for e in errors) and any("curation_priority" in e for e in errors)


def test_incident_names_only_listed_facilities():
    record = {"curation_priority": "MEDIUM", "treatment_facilities": [{"name": "Plant A"}],
              "incidents": [{"name": "Spill", "affected_facilities": ["Plant A", "Plant B"]}]}
    errors = zip_area_errors(record)
    assert len(errors) == 1 and "Plant B" in errors[0]
