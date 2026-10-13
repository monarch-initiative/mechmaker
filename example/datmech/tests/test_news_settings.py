"""conf/news.yaml: the news searches DaTMech's records get. It replaced scripts/news_plan.py."""

import datetime as dt
from pathlib import Path

from datmech import news
from datmech.validate import load

ROOT = Path(__file__).resolve().parents[1]
TODAY = dt.date(2026, 10, 9)
CONF = news.settings()


def plan(stem: str) -> dict:
    return news.plan(load(ROOT / "data" / "zip_areas" / f"{stem}.yaml"), CONF, today=TODAY)


def test_east_palestine_plan():
    p = plan("44413_east_palestine_ohio")
    first = p["searches"][0]
    assert first["why"] == "Recorded event: East Palestine train derailment"
    assert first["query"].startswith('"East Palestine" "Ohio" water (spill')
    assert '"vinyl chloride"' in first["query"]
    assert (first["from"], first["to"]) == ("2023-01-04", "2024-02-03")
    assert [s["why"] for s in p["searches"] if s["why"].startswith("New events")] == [
        "New events in 2024", "New events in 2025", "New events in 2026"]
    assert p["searches"][-1]["to"] == "2026-10-09"  # never past today
    assert p["wikipedia"] == ["East_Palestine,_Ohio,_train_derailment"]
    assert "WIKIPEDIA:East_Palestine,_Ohio,_train_derailment" in p["known"]
    assert "drink" in p["rank"]


def test_every_record_plans():
    for path in sorted((ROOT / "data" / "zip_areas").glob("*.yaml")):
        p = news.plan(load(path), CONF, today=TODAY)
        assert p["searches"] and all(s["from"] <= s["to"] for s in p["searches"])


def test_one_incident_s_words_never_reach_the_next():
    queries = {s["why"]: s["query"] for s in plan("48502_flint_michigan")["searches"]}
    assert "boil" not in queries["Recorded event: Flint trihalomethane violation"]
    sewage = queries["Recorded event: Flint River sewage release of March 2026"]
    assert '"no contact"' in sewage and "trihalomethanes" not in sewage
