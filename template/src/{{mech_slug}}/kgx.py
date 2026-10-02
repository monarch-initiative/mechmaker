"""KGX exports of the records: record-to-term associations, and the whole record graph.

The export calls this for the formats kgx and kgx_maximal in conf/export.yaml;
conf/kgx.yaml says how records map onto a graph. Files, in build/export/:

  kgx          <slug>-kgx_nodes.jsonl / _edges.jsonl, and .tsv of each
               One association per term a record's section binds, from the
               record to the term, with the section's predicate.
               Evidence goes on the edge: references in `publications`,
               quotes in `supporting_text` ("[ref] [SUPPORT] quote --- Explanation: ...").
  kgx_maximal  <slug>-kgx_maximal_nodes.jsonl / _edges.jsonl, and .tsv
               Every object in a record is a node (category <slug>:<Class>,
               and record_category for records); every field holding
               objects is an edge, predicate <slug>:<field>. Ontology terms
               are shared nodes, with the category of the section whose
               terms share their prefix.

Every edge carries primary_knowledge_source, knowledge_level and agent_type
from conf/kgx.yaml, and an id hashed from subject, predicate and object, so
ids are stable from one export to the next. In TSV, a list is joined with |.

With `biolink: true` (the default), each biolink: category and predicate is
checked against the Biolink model (the biolink-model package), and every
category and predicate must be Biolink's or, in kgx_maximal, the Mech's
own. With `biolink: false`, Biolink is not loaded: categories and
predicates are the Mech's own CURIEs, unchecked but for having a prefix. A
category must be a class that is neither a mixin nor abstract; a predicate,
a slot under `related to`. A predicate whose Biolink domain or range does
not fit the subject's or object's category is a warning, not an error.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from .paths import RECORD_CLASS, REPO_ROOT, SLUG

SETTINGS = REPO_ROOT / "conf" / "kgx.yaml"
DEFAULTS = {
    "biolink": True,
    "knowledge_source": f"infores:{SLUG}",
    "knowledge_level": "knowledge_assertion",
    "agent_type": "manual_validation_of_automated_agent",
    "sections": {},
}
BIOLINK_MISSING = (
    "kgx: needs biolink-model, which this Mech does not install. Run `uv add 'biolink-model>=4.4.5'` "
    "and `just install`, or set `biolink: false` in conf/kgx.yaml, or take kgx out of conf/export.yaml."
)
EDGE_FIELDS = ["id", "subject", "predicate", "object", "primary_knowledge_source", "knowledge_level",
               "agent_type", "publications", "supporting_text"]


def settings() -> dict:
    return resolve((yaml.safe_load(SETTINGS.read_text()) if SETTINGS.exists() else {}) or {})


def resolve(data: dict) -> dict:
    """conf/kgx.yaml's settings, with the defaults filled in."""
    cfg = {**DEFAULTS, **data}
    cfg["sections"] = cfg.get("sections") or {}
    # The category of a node nothing else gives one.
    cfg["default_category"] = "biolink:NamedThing" if cfg["biolink"] else f"{SLUG}:Term"
    cfg.setdefault("record_category", "biolink:NamedThing" if cfg["biolink"] else f"{SLUG}:{RECORD_CLASS}")
    for slot, sec in cfg["sections"].items():
        if not isinstance(sec, dict) or not sec.get("predicate"):
            raise SystemExit(f"conf/kgx.yaml: section {slot!r} needs a predicate")
    return cfg


# ---------------------------------------------------------------- Biolink


class Biolink:
    """The Biolink model, for checking categories and predicates. Needs biolink-model."""

    def __init__(self):
        import biolink_model  # ModuleNotFoundError (name biolink_model) when not installed
        from linkml_runtime.utils.formatutils import camelcase, underscore
        from linkml_runtime.utils.schemaview import SchemaView

        root = Path(list(biolink_model.__path__)[0])
        self.sv = SchemaView(str(root / "schema" / "biolink_model.yaml"))
        self.version = str(self.sv.schema.version)
        self.classes = {f"biolink:{camelcase(n)}": n for n in self.sv.all_classes()}
        self.slots = {f"biolink:{underscore(n)}": n for n in self.sv.all_slots()}
        self.predicates = set(self.sv.slot_descendants("related to", reflexive=True))

    def category_problem(self, curie: str) -> str | None:
        name = self.classes.get(curie)
        if name is None:
            return f"{curie} is not a Biolink class"
        c = self.sv.get_class(name)
        if c.mixin or c.abstract:
            return f"{curie} is a Biolink {'mixin' if c.mixin else 'abstract class'}; use a concrete class"
        return None

    def predicate_problem(self, curie: str) -> str | None:
        name = self.slots.get(curie)
        if name is None or name not in self.predicates:
            return f"{curie} is not a Biolink predicate"
        return None

    def fit_warning(self, predicate: str, subject_cat: str, object_cat: str) -> str | None:
        slot = self.sv.get_slot(self.slots[predicate])

        def fits(cat: str, expected: str | None) -> bool:
            if not expected or cat not in self.classes:
                return True
            ancestors = set(self.sv.class_ancestors(self.classes[cat]))
            mixins = set()
            for a in ancestors:
                mixins |= set(self.sv.get_class(a).mixins or [])
            return expected in ancestors | mixins

        bad = []
        if not fits(subject_cat, slot.domain):
            bad.append(f"its domain is {slot.domain}, not {subject_cat}")
        if not fits(object_cat, slot.range):
            bad.append(f"its range is {slot.range}, not {object_cat}")
        return f"{predicate}: " + "; ".join(bad) if bad else None


# ---------------------------------------------------------------- building


def edge_id(subject: str, predicate: str, obj: str) -> str:
    return f"{SLUG}:edge-" + hashlib.sha1(f"{subject}|{predicate}|{obj}".encode()).hexdigest()[:16]


def term_of(item, field: str | None):
    """(id, label) of the term an item binds, or None."""
    if not isinstance(item, dict):
        return None
    t = item.get(field) if field else item
    if isinstance(t, dict) and t.get("id"):
        return str(t["id"]), t.get("label")
    if field == "term" and "id" in item and "label" in item:
        return str(item["id"]), item.get("label")  # the item is itself a term
    return None


def publications(evidence: list) -> list[str]:
    out = []
    for e in evidence or []:
        ref = str(e.get("reference", ""))
        if ref:
            out.append(ref.removeprefix("url:"))
    return out


def supporting_text(evidence: list) -> list[str]:
    out = []
    for e in evidence or []:
        if e.get("snippet"):
            text = f"[{e.get('reference', '')}] [{e.get('supports', 'SUPPORT')}] {e['snippet']}"
            if e.get("explanation"):
                text += f" --- Explanation: {e['explanation']}"
            out.append(text)
    return out


def _provenance(cfg: dict) -> dict:
    return {"primary_knowledge_source": cfg["knowledge_source"], "knowledge_level": cfg["knowledge_level"],
            "agent_type": cfg["agent_type"]}


def association_graph(records: list[dict], cfg: dict) -> tuple[list[dict], list[dict]]:
    """Record-to-term associations."""
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    for r in records:
        rid = str(r["id"])
        nodes[rid] = {"id": rid, "category": [cfg["record_category"]], "name": r.get("name"),
                      "provided_by": [cfg["knowledge_source"]]}
        for slot, sec in cfg["sections"].items():
            value = r.get(slot)
            for item in value if isinstance(value, list) else [value] if value else []:
                term = term_of(item, sec.get("term_field", "term"))
                if term is None:
                    continue
                tid, label = term
                nodes.setdefault(tid, {"id": tid, "category": [sec.get("category", cfg["default_category"])],
                                       "name": label, "provided_by": [cfg["knowledge_source"]]})
                pred = sec["predicate"]
                eid = edge_id(rid, pred, tid)
                edge = edges.setdefault(eid, {"id": eid, "subject": rid, "predicate": pred, "object": tid,
                                              **_provenance(cfg), "publications": [], "supporting_text": []})
                evidence = item.get("evidence") if isinstance(item, dict) else None
                edge["publications"] += [p for p in publications(evidence) if p not in edge["publications"]]
                edge["supporting_text"] += supporting_text(evidence)
    return list(nodes.values()), list(edges.values())


def maximal_graph(sv, records: list[dict], cfg: dict) -> tuple[list[dict], list[dict]]:
    """Every object a node, every object-holding field an edge."""
    from .load import LABEL, graph

    gnodes, gedges = graph(sv, records)
    by_prefix: dict[str, str] = {}
    for r in records:
        for slot, sec in cfg["sections"].items():
            value = r.get(slot)
            for item in value if isinstance(value, list) else [value] if value else []:
                term = term_of(item, sec.get("term_field", "term"))
                if term:
                    prefix = term[0].split(":", 1)[0]
                    by_prefix.setdefault(prefix, sec.get("category", cfg["default_category"]))
    shared = {c for c in sv.all_classes() if c != RECORD_CLASS and sv.get_identifier_slot(c)}
    nodes = []
    for n in gnodes:
        cls = n[LABEL]
        if cls == RECORD_CLASS:
            cats = list(dict.fromkeys([cfg["record_category"], f"{SLUG}:{cls}"]))
        elif cls in shared:
            cats = [by_prefix.get(n["id"].split(":", 1)[0], cfg["default_category"])]
        else:
            cats = [f"{SLUG}:{cls}"]
        props = {k: v for k, v in n.items() if k not in ("id", LABEL)}
        name = props.pop("name", None) or props.get("preferred_term") or props.get("label")
        nodes.append({"id": n["id"], "category": cats, "name": name,
                      "provided_by": [cfg["knowledge_source"]], **props})
    edges = [{"id": edge_id(e["subject"], f"{SLUG}:{e['predicate']}", e["object"]), "subject": e["subject"],
              "predicate": f"{SLUG}:{e['predicate']}", "object": e["object"], **_provenance(cfg)}
             for e in gedges]
    return nodes, edges


# ---------------------------------------------------------------- writing and checking


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return "|".join(str(x) for x in v)
    return str(v)


def write(nodes: list[dict], edges: list[dict], out_dir: Path, stem: str) -> list[Path]:
    files = []
    node_first = ["id", "category", "name", "provided_by"]
    for kind, rows, first in (("nodes", nodes, node_first), ("edges", edges, EDGE_FIELDS)):
        jl = out_dir / f"{stem}_{kind}.jsonl"
        jl.write_text("".join(json.dumps({k: v for k, v in r.items() if v not in (None, [], "")},
                                         ensure_ascii=False) + "\n" for r in rows))
        cols = first + sorted({k for r in rows for k in r} - set(first))
        tsv = out_dir / f"{stem}_{kind}.tsv"
        with tsv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, delimiter="\t", lineterminator="\n")
            w.writerow(cols)
            for r in rows:
                w.writerow([_cell(r.get(c)) for c in cols])
        files += [jl, tsv]
    return files


def check(nodes: list[dict], edges: list[dict], biolink: Biolink | None,
          maximal: bool) -> tuple[list[str], list[str]]:
    """(problems, warnings) for one graph. With no Biolink, categories and predicates need only a prefix."""
    problems, warnings = [], []
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        problems.append("node ids repeat")
    known = set(ids)
    dangling = [e["id"] for e in edges if e["subject"] not in known or e["object"] not in known]
    if dangling:
        problems.append(f"{len(dangling)} edge(s) point at a node that is not exported")
    if biolink is None:
        unprefixed = sorted({c for n in nodes for c in n["category"] if ":" not in c}
                            | {e["predicate"] for e in edges if ":" not in e["predicate"]})
        problems += [f"{c} is not a CURIE: give it a prefix" for c in unprefixed]
        return problems, warnings
    local = f"{SLUG}:"
    cats: dict[str, str] = {}
    for n in nodes:
        for c in n["category"]:
            if c.startswith("biolink:"):
                p = biolink.category_problem(c)
                if p and p not in problems:
                    problems.append(p)
            elif not (maximal and c.startswith(local)):
                problems.append(f"category {c} is not a Biolink class")
        cats[n["id"]] = next((c for c in n["category"] if c.startswith("biolink:")), "")
    seen = set()
    for e in edges:
        pred = e["predicate"]
        if pred.startswith("biolink:"):
            p = biolink.predicate_problem(pred)
            if p:
                if p not in problems:
                    problems.append(p)
                continue
            key = (pred, cats.get(e["subject"]), cats.get(e["object"]))
            if key not in seen:
                seen.add(key)
                w = biolink.fit_warning(*key)
                if w:
                    warnings.append(w)
        elif not (maximal and pred.startswith(local)):
            problems.append(f"predicate {pred} is not a Biolink predicate")
    return problems, warnings


def export(fmt: str, sv, records: list[dict], out_dir: Path) -> tuple[list[Path], list[str], list[str]]:
    """Write one KGX format and read it back. (files, problems, warnings)."""
    cfg = settings()
    biolink = Biolink() if cfg["biolink"] else None
    if fmt == "kgx":
        nodes, edges = association_graph(records, cfg)
    else:
        nodes, edges = maximal_graph(sv, records, cfg)
    problems, warnings = check(nodes, edges, biolink, maximal=fmt == "kgx_maximal")
    stem = f"{SLUG}-{fmt}"
    files = write(nodes, edges, out_dir, stem)
    for f, want in ((files[0], len(nodes)), (files[2], len(edges))):
        if len(f.read_text().splitlines()) != want:
            problems.append(f"{f.name}: does not hold {want} line(s)")
    return files, problems, [f"{fmt} (Biolink {biolink.version}): {w}" for w in warnings] if biolink else []
