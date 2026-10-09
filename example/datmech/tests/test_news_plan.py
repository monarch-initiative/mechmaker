"""scripts/news_plan.py: a news search plan from a ZIP area record."""

import datetime as dt
import importlib.util
from pathlib import Path

from datmech.validate import load

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("news_plan", ROOT / "scripts" / "news_plan.py")
news_plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(news_plan)

TODAY = dt.date(2026, 10, 9)


def test_partial_dates_cover_their_whole_period():
    assert news_plan.first_day("2014-04") == dt.date(2014, 4, 1)
    assert news_plan.last_day("2019") == dt.date(2019, 12, 31)
    assert news_plan.last_day("2014-02") == dt.date(2014, 2, 28)


def test_phrases_are_quoted_and_repeats_dropped():
    assert news_plan.any_of(["spill", "vinyl chloride", "spill"]) == '(spill OR "vinyl chloride")'
    assert news_plan.any_of(["boil"]) == "boil"


def test_east_palestine_plan():
    data = load(ROOT / "data" / "zip_areas" / "44413_east_palestine_ohio.yaml")
    plan = news_plan.plan(data, years=3, today=TODAY)
    first = plan["searches"][0]
    assert first["why"] == "Recorded incident: East Palestine train derailment"
    assert first["query"].startswith('"East Palestine" "Ohio" water (spill')
    assert '"vinyl chloride"' in first["query"]
    assert (first["from"], first["to"]) == ("2023-01-04", "2024-02-03")
    assert [s["why"] for s in plan["searches"] if s["why"].startswith("New incidents")] == [
        "New incidents in 2024", "New incidents in 2025", "New incidents in 2026"]
    assert plan["searches"][-1]["to"] == "2026-10-09"  # never past today
    assert plan["wikipedia"] == ["East_Palestine,_Ohio,_train_derailment"]
    assert "WIKIPEDIA:East_Palestine,_Ohio,_train_derailment" in plan["known"]


def test_every_record_plans():
    for path in sorted((ROOT / "data" / "zip_areas").glob("*.yaml")):
        plan = news_plan.plan(load(path), years=1, today=TODAY)
        assert plan["searches"] and all(s["from"] <= s["to"] for s in plan["searches"])


def test_one_incident_s_words_never_reach_the_next():
    data = load(ROOT / "data" / "zip_areas" / "48502_flint_michigan.yaml")
    before = {k: list(v) for k, v in news_plan.KIND_WORDS.items()}
    queries = {s["why"]: s["query"] for s in news_plan.plan(data, years=1, today=TODAY)["searches"]}
    assert before == news_plan.KIND_WORDS  # the table is unchanged
    assert "boil" not in queries["Recorded incident: Flint trihalomethane violation"]
    sewage = queries["Recorded incident: Flint River sewage release of March 2026"]
    assert '"no contact"' in sewage and "trihalomethanes" not in sewage
