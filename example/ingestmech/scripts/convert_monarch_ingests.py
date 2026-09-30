"""Convert Monarch ingest repositories into IngestMech records.

    just convert scripts/convert_monarch_ingests.py                  # dry run, the trial set
    just convert scripts/convert_monarch_ingests.py --all            # dry run, every ingest
    just convert scripts/convert_monarch_ingests.py --model M --apply

Each repository is read at its current commit, and the record keeps that
commit in `source_commit`. Every fact copied from the repository carries a
url: evidence item quoting the file it came from, pinned to the commit, so
`just validate-references` can check it. The script reads:

  .copier-answers.yml  description and code license
  src/versions.py      upstream sources, by infores id and name
  download.yaml        the files, assigned to sources as versions.py assigns them
  README.md            species listed by NCBITaxon id, Biolink association classes
  src/*.yaml           koza transform names

What no repository records, such as the upstream data licenses, becomes a
CURATION_TODO discussion on the record. An infores id missing from the
Biolink information resource catalog is left out and becomes one too.
Fetched files are kept under build/convert/, so a rerun does not fetch again.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request

import yaml

from ingestmech.convert import Entry, Skip, run
from ingestmech.paths import REPO_ROOT

ORG = "monarch-initiative"
TRIAL = ["zfin-ingest", "omim-ingest", "go-ingest"]
CATALOG_REPO = "biolink/information-resource-registry"
CATALOG_COMMIT = "1d5fa9924e518315dbcbeb87c80e9d783c8fd2fc"
CACHE = REPO_ROOT / "build" / "convert"
OLS = "https://www.ebi.ac.uk/ols4/api/ontologies/ncbitaxon/terms?obo_id="


def get(url: str) -> str:
    """Fetch a URL once; later runs read build/convert/."""
    path = CACHE / urllib.parse.quote(url, safe="")
    if path.exists():
        return path.read_text()
    req = urllib.request.Request(url, headers={"User-Agent": "ingestmech-convert/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return text


def head_commit(repo: str) -> str:
    out = subprocess.run(["git", "ls-remote", f"https://github.com/{ORG}/{repo}", "HEAD"],
                         capture_output=True, text=True, timeout=120, check=True).stdout
    return out.split()[0]


def all_ingests() -> list[str]:
    """Repositories named *ingest* that have the template layout, per the GitHub API."""
    names, page = [], 1
    while True:
        batch = json.loads(get(f"https://api.github.com/orgs/{ORG}/repos?per_page=100&page={page}"))
        if not batch:
            break
        names += [r["name"] for r in batch if "ingest" in r["name"] and not r["archived"]]
        page += 1
    return sorted(names)


def catalog() -> dict[str, dict]:
    raw = get(f"https://raw.githubusercontent.com/{CATALOG_REPO}/{CATALOG_COMMIT}/infores_catalog.yaml")
    return {e["id"]: e for e in yaml.safe_load(raw)["information_resources"]}


def taxon_label(curie: str) -> str | None:
    data = json.loads(get(OLS + urllib.parse.quote(curie)))
    terms = data.get("_embedded", {}).get("terms", [])
    return terms[0]["label"] if terms else None


class Repo:
    """One repository's files at one commit."""

    def __init__(self, name: str):
        self.name = name
        self.sha = head_commit(name)
        tree = json.loads(get(f"https://api.github.com/repos/{ORG}/{name}/git/trees/{self.sha}?recursive=1"))
        self.paths = {t["path"] for t in tree["tree"] if t["type"] == "blob"}

    def raw_ref(self, path: str) -> str:
        return f"url:https://raw.githubusercontent.com/{ORG}/{self.name}/{self.sha}/{path}"

    def text(self, path: str) -> str:
        return get(self.raw_ref(path).removeprefix("url:"))

    def quote(self, path: str, snippet: str, explanation: str | None = None) -> dict:
        """An evidence item quoting this repository. The validator checks it later."""
        item = {"reference": self.raw_ref(path), "supports": "SUPPORT",
                "evidence_source": "INGEST_REPOSITORY", "snippet": snippet}
        if explanation:
            item["explanation"] = explanation
        return item


def todo(name: str, topic: str, prompt: str, attaches_to: str | None = None) -> dict:
    d = {"discussion_id": f"{name}-{topic}", "prompt": prompt, "kind": "CURATION_TODO", "status": "OPEN"}
    if attaches_to:
        d["attaches_to"] = [attaches_to]
    return d


def sources(repo: Repo, downloads: list[dict], known: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """Upstream sources from src/versions.py, with their files. Returns (sources, discussions)."""
    text = repo.text("src/versions.py")
    # `zfin_urls = urls_from_download_yaml(DOWNLOAD_YAML, contains=["zfin.org"])`
    assign = r"(\w+)\s*=\s*urls_from_download_yaml\(\s*DOWNLOAD_YAML\s*(?:,\s*contains=\[([^\]]*)\])?\s*\)"
    filters = {var: re.findall(r'"([^"]+)"', contains or "") for var, contains in re.findall(assign, text)}
    out, talk, used = [], [], set()
    for m in re.finditer(r'"id":\s*"(infores:[^"]+)",\s*"name":\s*"([^"]+)"', text):
        infores, name = m.group(1), m.group(2)
        src: dict = {}
        if infores in known:
            src["infores"] = infores
        else:
            talk.append(todo(repo.name, f"infores-{re.sub(r'[^a-z0-9]+', '-', infores.lower())}",
                             f"src/versions.py names the source {infores!r}, which is not in the Biolink "
                             f"information resource catalog at {CATALOG_COMMIT[:7]}.",
                             f"upstream_sources#{name}"))
        src["name"] = name
        after = text[m.end():m.end() + 400]
        var = re.search(r'"urls":\s*(\w+)', after)
        wanted = filters.get(var.group(1)) if var else None
        files = []
        for d in downloads:
            if wanted is None or wanted == [] or any(w in d["url"] for w in wanted):
                files.append({"download_url": d["url"], "local_name": d["local_name"],
                              "evidence": [repo.quote("download.yaml", f"url: {d['url']}")]})
                used.add(d["url"])
        if any(re.search(r"\{[A-Z_]+\}", f["download_url"]) for f in files):
            src["access"] = "REGISTRATION_REQUIRED"
        if files:
            src["files"] = files
        src["evidence"] = [repo.quote("src/versions.py", " ".join(m.group(0).split()),
                                      "The ingest's own name and id for the source.")]
        out.append(src)
    stray = [d["url"] for d in downloads if d["url"] not in used]
    if stray:
        talk.append(todo(repo.name, "unassigned-files",
                         f"download.yaml fetches {len(stray)} file(s) that src/versions.py assigns to no "
                         f"source: {', '.join(stray)}.", "upstream_sources"))
    return out, talk


def readme_facts(repo: Repo) -> tuple[list[dict], list[dict]]:
    """Species listed as `- Name (NCBITaxon:n)`, and Biolink association classes."""
    text = repo.text("README.md") if "README.md" in repo.paths else ""
    organisms = []
    for line in text.splitlines():
        m = re.fullmatch(r"\s*[-*]\s+(.+?)\s+\((NCBITaxon:\d+)\)\s*", line)
        if not m:
            continue
        label = taxon_label(m.group(2))
        org = {"preferred_term": m.group(1)}
        if label:
            org["term"] = {"id": m.group(2), "label": label}
        org["evidence"] = [repo.quote("README.md", line.strip().lstrip("-* "))]
        organisms.append(org)
    associations: dict[str, dict] = {}
    for line in text.splitlines():
        for name in re.findall(r"(?<![.\w])(?:biolink:)?([A-Z][A-Za-z]+Association)\b", line):
            if name in associations:
                continue
            a = {"category": f"biolink:{name}"}
            predicates = re.findall(r"`(biolink:[a-z_]+)`", line)
            if predicates:
                a["predicates"] = predicates
            a["evidence"] = [repo.quote("README.md", line.strip().lstrip("-* |").rstrip(" |"))]
            associations[name] = a
    return organisms, list(associations.values())


def convert(name: str, known: dict[str, dict]) -> Entry | Skip:
    try:
        repo = Repo(name)
    except Exception as exc:  # the network, or a repository that is gone
        return Skip(name, f"could not read the repository: {exc}")
    missing = [p for p in ("download.yaml", "src/versions.py", ".copier-answers.yml") if p not in repo.paths]
    if missing:
        return Skip(name, f"not in the koza template layout: no {', '.join(missing)}")

    answers = yaml.safe_load(repo.text(".copier-answers.yml"))
    downloads = [d for d in (yaml.safe_load(repo.text("download.yaml")) or []) if isinstance(d, dict)]
    ups, talk = sources(repo, downloads, known)
    if not ups:
        return Skip(name, "src/versions.py names no source as \"id\": \"infores:...\"")
    organisms, associations = readme_facts(repo)

    record: dict = {"id": f"ingestmech:{name}", "name": name}
    description = " ".join(str(answers.get("project_description", "")).split())
    if description:
        record["description"] = description
    record["repository"] = f"https://github.com/{ORG}/{name}"
    record["source_commit"] = repo.sha
    license_ = answers.get("license")
    if license_:
        record["code_license"] = {"name": license_, "spdx_id": license_,
                                  "evidence": [repo.quote(".copier-answers.yml", f"license: {license_}")]}
    record["upstream_sources"] = ups
    if organisms:
        record["organisms"] = organisms
    else:
        talk.append(todo(name, "species", "The README lists no species by NCBITaxon id. "
                         "Curate the species the ingest takes data for.", "organisms"))
    if associations:
        record["associations"] = associations
    transforms = []
    for path in sorted(p for p in repo.paths if re.fullmatch(r"src/[^/]+\.yaml", p)):
        t = yaml.safe_load(repo.text(path)) or {}
        if isinstance(t, dict) and t.get("name"):
            transforms.append(str(t["name"]))
    if transforms:
        record["koza_transforms"] = transforms
    if description:
        first = str(answers["project_description"]).split("\n")[0]
        record["evidence"] = [repo.quote(".copier-answers.yml", f"project_description: {first}",
                                         "The record's description is the repository's own.")]
    talk.append(todo(name, "data-licenses", "No ingest records the terms of its upstream data. "
                     "Curate each source's data_license from the source's own terms.", "upstream_sources"))
    record["discussions"] = talk
    return Entry(name, record)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--all", action="store_true", help="every ingest in the organization")
    args, rest = parser.parse_known_args()
    names = all_ingests() if args.all else TRIAL
    known = catalog()
    return run((convert(n, known) for n in names), source="Monarch ingest repositories",
               script=__file__, argv=rest)


if __name__ == "__main__":
    sys.exit(main())
