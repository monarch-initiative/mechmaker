"""Load the records into a running database, through linkml-store.

    python -m <slug>.load mongodb             # load, unless the target already holds data
    python -m <slug>.load neo4j --replace     # replace what the target holds
    python -m <slug>.load --list              # the targets conf/load.yaml names

Each target's address is in conf/load.yaml. `${NAME}` in an address is read
from the environment, so passwords stay out of the repository; addresses
are printed with passwords hidden. After loading, the data is counted back.

  mongodb  one collection, named for the records folder, one document per
           record, nested as it is in the YAML. --replace drops and refills
           that collection only.
  neo4j    a graph: every object is a node labelled with its class, every
           field holding objects is an edge named for the field, and an
           ontology term is one shared node per CURIE. The class is the
           label, and the node property mech_class. A nested object's
           node id is its path, e.g. `VBO:0000736/origins/0`. A term with the
           same CURIE as a record gets `<CURIE> (Term)`, with the CURIE in
           its `curie` property. Every node also has the MechNode label and
           this Mech's slug in `mech`; --replace deletes those nodes only.
           Writes are batched Cypher (see load_neo4j), so a large Mech loads
           in seconds.

The packages come from linkml-store, which a Mech installs only when it
chose a load target. Other linkml-store backends were tried and left out:
Postgres (linkml-store 0.3.2 cannot connect to it) and Solr (it cannot
insert).
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import yaml

from .paths import RECORD_CLASS, RECORDS_DIR, REPO_ROOT, SLUG
from .validate import iter_records, load

SETTINGS = REPO_ROOT / "conf" / "load.yaml"
TARGETS = ("mongodb", "neo4j")
# The node property that becomes the Neo4j label: the class name. Not
# "category", linkml-store's default, which a schema may use for a slot.
LABEL = "mech_class"
EXTRA = {"mongodb": "mongodb", "neo4j": "neo4j"}


def settings() -> dict[str, str]:
    data = (yaml.safe_load(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}) or {}
    targets = data.get("targets") or {}
    bad = [t for t in targets if t not in TARGETS]
    if bad:
        raise SystemExit(f"conf/load.yaml: unknown target(s) {bad}; choose from {list(TARGETS)}")
    return targets


def expand(handle: str) -> str:
    """Fill ${NAME} from the environment; a missing one is an error, not an empty string."""
    missing = [n for n in re.findall(r"\$\{(\w+)\}", handle) if n not in os.environ]
    if missing:
        raise SystemExit(f"conf/load.yaml needs {', '.join(missing)} in the environment.")
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ[m.group(1)], handle)


def masked(handle: str) -> str:
    """The address with its password hidden: everything between `user:` and the last `@`."""
    return re.sub(r"(//[^:/@]+:).*@", r"\1***@", handle)


def need(target: str):
    try:
        from linkml_store import Client
    except ModuleNotFoundError as exc:
        if exc.name != "linkml_store":  # installed, but something it needs is not: show that
            raise
        raise SystemExit(
            f"{target}: needs linkml-store, which this Mech does not install. Run "
            f"`uv add 'linkml-store[{EXTRA[target]}]>=0.3.2'` and `just install`.") from None
    return Client


def schemaview():
    from linkml_runtime.utils.schemaview import SchemaView

    from .paths import SCHEMA_PATH

    sv = SchemaView(str(SCHEMA_PATH))
    sv.merge_imports()
    return sv


def graph(sv, records: list[dict]) -> tuple[list[dict], list[dict]]:
    """(nodes, edges) for a property graph. Nodes have id and LABEL; edges subject, predicate, object.

    Every record id is placed before any record is walked, so a record keeps its
    bare id whatever order the files are read in, and a term or other object
    sharing that id becomes "<id> (<Class>)". An object first met as a reference
    by id is a stub until the object itself is met, and is walked then.
    """
    classes = set(sv.all_classes())
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    walked: set[str] = set()

    def place(cid: str, rng: str) -> str:
        """The node id for an object of class rng whose own id is cid."""
        return f"{cid} ({rng})" if cid in nodes and nodes[cid][LABEL] != rng else cid

    def walk(cls: str, obj: dict, node_id: str) -> None:
        walked.add(node_id)
        nodes[node_id] = {"id": node_id, LABEL: cls}
        props = {}
        for slot in sv.class_induced_slots(cls):
            value = obj.get(slot.name)
            if value is None:
                continue
            rng = slot.range if slot.range in classes else None
            if not rng:
                if slot.name == "id":
                    if str(value) != node_id:  # a renamed term keeps its CURIE
                        props["curie"] = value
                    continue
                props[slot.name] = value
                continue
            ident = sv.get_identifier_slot(rng)
            for i, child in enumerate(value if slot.multivalued else [value]):
                if not isinstance(child, dict):  # a reference by id, not a nested object
                    if not ident:
                        raise SystemExit(f"load: {cls}.{slot.name} holds {child!r}, but {rng} has no "
                                         "identifier, so it must be a nested object")
                    cid = place(str(child), rng)
                    nodes.setdefault(cid, {"id": cid, LABEL: rng})  # a stub until the object itself is walked
                    edges.append({"subject": node_id, "predicate": slot.name, "object": cid})
                    continue
                if ident:
                    cid = place(str(child[ident.name]), rng)
                else:
                    cid = f"{node_id}/{slot.name}" + (f"/{i}" if slot.multivalued else "")
                if cid not in walked:
                    walk(rng, child, cid)
                edges.append({"subject": node_id, "predicate": slot.name, "object": cid})
        nodes[node_id].update(props)

    for r in records:
        rid = str(r["id"])
        if rid in nodes:
            raise SystemExit(f"load: two records have the id {rid!r}; their nodes would merge")
        nodes[rid] = {"id": rid, LABEL: RECORD_CLASS}
    walked.update(nodes)  # each record is walked below, never from inside another
    for r in records:
        walk(RECORD_CLASS, r, str(r["id"]))
    return list(nodes.values()), edges


def load_mongodb(handle: str, records: list[dict], replace: bool) -> str:
    Client = need("mongodb")
    db = Client().attach_database(handle, alias="target")
    name = RECORDS_DIR.name
    held = db.native_db[name].count_documents({}) if name in db.native_db.list_collection_names() else 0
    if held and not replace:
        raise SystemExit(f"mongodb: collection {name!r} holds {held} document(s). "
                         "Pass --replace to drop and refill it (that collection only).")
    collection = db.create_collection(RECORD_CLASS, alias=name, recreate_if_exists=True)
    collection.insert(records)
    got = db.native_db[name].count_documents({})
    if got != len(records):
        raise SystemExit(f"mongodb: {got} document(s) in {name!r} after loading {len(records)}.")
    return f"{got} document(s) in collection {name!r}"


# Neo4j writes are batched Cypher, not linkml-store's collection inserts: those
# run three label-less MATCHes per edge, each reading every node, so a load
# grows with nodes times edges. Every node here carries the MechNode label
# and this Mech's slug in `mech`, with an index on MechNode.id, so matching an
# edge's ends uses the index, and --replace can delete this Mech's nodes only.
NODE_LABEL = "MechNode"
BATCH = 1000


def _quote(name: str) -> str:
    """A label or relationship type, escaped for Cypher."""
    return "`" + str(name).replace("`", "``") + "`"


def _batches(rows: list, size: int = BATCH):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def load_neo4j(handle: str, records: list[dict], replace: bool) -> str:
    Client = need("neo4j")
    nodes, edges = graph(schemaview(), records)
    db = Client().attach_database(handle, alias="target")
    ours = "{mech: $mech}"  # a Cypher map: only this Mech's nodes
    mine = f"MATCH (n:{NODE_LABEL} {ours})"
    with db.session() as session:
        held = session.run(f"{mine} RETURN count(n) AS c", mech=SLUG).single()["c"]
        if held and not replace:
            raise SystemExit(f"neo4j: the database holds {held} node(s) from {SLUG}. Pass --replace to "
                             "delete them and load again; other data in the database is left alone.")
        session.run(f"CREATE INDEX mech_node_id IF NOT EXISTS FOR (n:{NODE_LABEL}) ON (n.id)").consume()
        while session.run(f"{mine} WITH n LIMIT 10000 DETACH DELETE n RETURN count(n) AS c",
                          mech=SLUG).single()["c"]:
            pass
        by_class: dict[str, list[dict]] = {}
        for n in nodes:
            by_class.setdefault(n[LABEL], []).append({**n, "mech": SLUG})
        for cls, rows in by_class.items():
            query = f"UNWIND $rows AS row CREATE (n:{NODE_LABEL}:{_quote(cls)}) SET n = row"
            for batch in _batches(rows):
                session.run(query, rows=batch).consume()
        by_predicate: dict[str, list[dict]] = {}
        for e in edges:
            by_predicate.setdefault(e["predicate"], []).append({"s": e["subject"], "o": e["object"]})
        for pred, rows in by_predicate.items():
            query = (f"UNWIND $rows AS row "
                     f"MATCH (s:{NODE_LABEL} " + "{mech: $mech, id: row.s}) "
                     f"MATCH (o:{NODE_LABEL} " + "{mech: $mech, id: row.o}) "
                     f"CREATE (s)-[:{_quote(pred)}]->(o)")
            for batch in _batches(rows):
                session.run(query, rows=batch, mech=SLUG).consume()
        n = session.run(f"{mine} RETURN count(n) AS c", mech=SLUG).single()["c"]
        e = session.run(f"{mine}-[r]->(:{NODE_LABEL} {ours}) RETURN count(r) AS c",
                        mech=SLUG).single()["c"]
    if (n, e) != (len(nodes), len(edges)):
        raise SystemExit(f"neo4j: {n} node(s) and {e} edge(s) after loading {len(nodes)} and {len(edges)}.")
    return f"{n} node(s) and {e} edge(s)"


LOADERS = {"mongodb": load_mongodb, "neo4j": load_neo4j}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", nargs="?", choices=TARGETS)
    parser.add_argument("--replace", action="store_true", help="replace what the target holds (see --help)")
    parser.add_argument("--list", action="store_true", help="print the configured targets")
    args = parser.parse_args(argv)
    targets = settings()
    if args.list or not args.target:
        for name, handle in targets.items():
            print(f"  {name:8} {masked(handle)}")
        if not targets:
            print("No targets in conf/load.yaml.")
        return 0
    if args.target not in targets:
        raise SystemExit(f"{args.target} has no address in conf/load.yaml.")
    handle = expand(targets[args.target])
    records = [load(p) or {} for p in iter_records()]
    print(f"Loading {len(records)} record(s) into {args.target} at {masked(handle)}", flush=True)
    try:
        print(LOADERS[args.target](handle, records, args.replace))
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as exc:  # a server that refuses or does not answer: say so in one line
        first = (str(exc).strip().splitlines() or [""])[0]
        print(f"{args.target}: failed: {type(exc).__name__}: {masked(first)[:300]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
