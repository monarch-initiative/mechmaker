#!/usr/bin/env python3
"""Check ontology CURIEs against OLS4 before a Mech exists. Standard library only.

    check_terms.py label GO:0008150 ENVO:01000813       # print each term's label
    check_terms.py under ENVO:01000813 ENVO:00000051 ENVO:00000022
        # is the first CURIE an is-a ancestor (or self) of each of the rest?
    check_terms.py under --direct VBO:0400025 VBO:0000827 VBO:0009093
        # is the first CURIE a direct is-a parent of each of the rest?
    check_terms.py search envo "hot spring"               # top matches

Every command takes --adapter for an ontology OLS does not serve, with any
adapter OAK accepts. OAK runs through uvx, so this needs uv:

    check_terms.py --adapter sqlite:obo:vt label VT:0000001
    check_terms.py --adapter bioportal:<ACRONYM> label <ACRONYM>:<id>
    check_terms.py --adapter simpleobo:my.obo under MY:0000001 MY:0000042
    check_terms.py --adapter simpleobo:my.obo search - "l~widget"

bioportal: needs BIOPORTAL_API_KEY in the environment. With --adapter, the
ontology argument of search is ignored; pass -. An ols:<id> adapter searches
the OLS ontology <id>.

Exit status is 1 if any term is missing or obsolete, or any check fails, so the result can
gate a script. It exits 2 if OLS or the adapter does not answer: that is an
outage, not a missing term. It exits 3 if OAK itself fails, and 64 on a
usage error, such as a missing argument or a CURIE with no colon. Ontology ids
default to the lowercased prefix.
"""

import functools
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OLS = "https://www.ebi.ac.uk/ols4/api"
OAK = ["uvx", "--quiet", "--from", "oaklib", "runoak"]
OAK_PY = ["uvx", "--quiet", "--from", "oaklib", "python"]
ADAPTER = None  # set by --adapter; None means OLS by prefix


class Unreachable(Exception):
    pass


class OakFailed(Exception):
    """OAK ran and failed: not an outage, so trying again will not help."""


def _mask(text):
    """Hide API keys: some adapters put them in the URLs their errors print."""
    return re.sub(r"(apikey=)[^&\s]+", r"\1***", text, flags=re.I)


def _get(url, tries=3):
    """JSON from OLS. A 4xx is a real answer, such as 404 for a missing term, and is raised as is.
    A 5xx, a 429 or no answer at all is tried again, then raised as Unreachable."""
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                raise
            if attempt == tries:
                raise Unreachable(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == tries:
                raise Unreachable(str(exc)) from exc
        time.sleep(5 * attempt)


def _term(curie):
    """The OLS record of a term, or None if OLS does not have it. IRIs differ by
    ontology (EFO's are not OBO PURLs), so the term is found by its CURIE."""
    return _lookup(_ols_ontology() or curie.split(":", 1)[0].lower(), curie)


@functools.cache
def _lookup(onto, curie):
    q = urllib.parse.urlencode({"obo_id": curie})
    try:
        terms = _get(f"{OLS}/ontologies/{onto}/terms?{q}").get("_embedded", {}).get("terms", [])
    except urllib.error.HTTPError:
        terms = []
    if terms:
        return terms[0]
    # Some loads leave obo_id empty (PR's, at times); try the OBO PURL.
    iri = urllib.parse.quote("http://purl.obolibrary.org/obo/" + curie.replace(":", "_", 1), safe="")
    try:
        return _get(f"{OLS}/ontologies/{onto}/terms/" + urllib.parse.quote(iri, safe=""))
    except urllib.error.HTTPError:
        return None


def _term_url(curie, suffix=""):
    """The OLS URL of a term, built from the IRI OLS gives it, or None if OLS does not have it."""
    term = _term(curie)
    if term is None:
        return None
    enc = urllib.parse.quote(urllib.parse.quote(term["iri"], safe=""), safe="")
    onto = _ols_ontology() or curie.split(":", 1)[0].lower()
    return f"{OLS}/ontologies/{onto}/terms/{enc}{suffix}"


def _ols_ontology():
    """The ontology an ols:<id> adapter names, or None."""
    return ADAPTER.removeprefix("ols:") if ADAPTER and ADAPTER.startswith("ols:") else None


def _oak_mode():
    return ADAPTER is not None and not ADAPTER.startswith("ols:")


def _oak(*args):
    """Lines of `runoak -i ADAPTER ...` as (curie, label) pairs."""
    try:
        out = subprocess.run(OAK + ["-i", ADAPTER, *args], capture_output=True, text=True, timeout=3600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Unreachable(f"runoak did not run: {exc}") from exc
    if out.returncode != 0:
        last = _mask((out.stderr.strip().splitlines()[-1:] or [f"exit {out.returncode}"])[0])
        if re.search(r"Timeout|ConnectionError|Max retries", last):
            raise Unreachable(f"runoak -i {ADAPTER}: {last}")
        raise OakFailed(f"runoak -i {ADAPTER} failed: {last}")
    # `info` and `search` print "CURIE ! label". A term OAK does not know has
    # the label None.
    pairs = []
    for line in out.stdout.splitlines():
        curie, _, lab = line.partition("\t") if "\t" in line else line.partition(" ! ")
        curie, lab = curie.strip(), lab.strip()
        if curie:
            pairs.append((curie, None if lab in ("", "None") else lab))
    return pairs


def label(curie):
    if _oak_mode():
        hits = [lab for c, lab in _oak("info", curie) if c == curie and lab]
        return hits[0] if hits else None
    term = _term(curie)
    return term.get("label") if term else None


def obsolete(curie):
    """True when OLS marks the term obsolete. OAK mode does not say, so False there."""
    if _oak_mode():
        return False
    term = _term(curie)
    return bool(term and term.get("is_obsolete"))


# `runoak ancestors` fails on BioPortal (OAK 0.7.4 passes arguments its
# BioPortal adapter does not take), so ancestors go through OAK's Python API,
# without a predicate filter when the adapter refuses one.
ANCESTORS_PY = """
import sys
from oaklib import get_adapter
from oaklib.datamodels.vocabulary import IS_A
a = get_adapter(sys.argv[1])
try:
    found = list(a.ancestors(sys.argv[2], predicates=[IS_A]))
except TypeError:
    found = list(a.ancestors(sys.argv[2]))
print("\\n".join(found))
"""


def _oak_py(program, curie):
    """CURIEs, one per line, from an OAK Python program run with (adapter, curie)."""
    cmd = OAK_PY + ["-c", program, ADAPTER, curie]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Unreachable(f"OAK did not run: {exc}") from exc
    if out.returncode != 0:
        last = _mask((out.stderr.strip().splitlines()[-1:] or [f"exit {out.returncode}"])[0])
        if re.search(r"Timeout|ConnectionError|Max retries", last):
            raise Unreachable(f"{ADAPTER}: {last}")
        raise OakFailed(f"{ADAPTER} failed: {last}")
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


def _oak_ancestors(curie):
    return _oak_py(ANCESTORS_PY, curie)


PARENTS_PY = """
import sys
from oaklib import get_adapter
from oaklib.datamodels.vocabulary import IS_A
a = get_adapter(sys.argv[1])
print("\\n".join(o for _, _, o in a.relationships([sys.argv[2]], predicates=[IS_A]) if o != sys.argv[2]))
"""


def parents(curie):
    """Direct is-a parents."""
    if _oak_mode():
        return _oak_py(PARENTS_PY, curie)
    url = _term_url(curie, "/parents?size=500")
    if url is None:
        return set()
    try:
        data = _get(url)
    except urllib.error.HTTPError:
        return set()
    return {t.get("obo_id") for t in data.get("_embedded", {}).get("terms", [])}


def ancestors(curie):
    if _oak_mode():
        return _oak_ancestors(curie)
    out, url = set(), _term_url(curie, "/ancestors?size=500")
    while url:
        try:
            data = _get(url)
        except urllib.error.HTTPError:
            break
        out |= {t.get("obo_id") for t in data.get("_embedded", {}).get("terms", [])}
        url = data.get("_links", {}).get("next", {}).get("href")
    return out


def main(argv):
    global ADAPTER
    if "--adapter" in argv:
        i = argv.index("--adapter")
        if i + 1 == len(argv):
            print("--adapter needs a value, e.g. --adapter sqlite:obo:vt", file=sys.stderr)
            return 64
        ADAPTER, argv = argv[i + 1], argv[:i] + argv[i + 2:]
    if len(argv) < 2 or argv[0] not in ("label", "under", "search"):
        print(__doc__)
        return 64
    cmd, args = argv[0], argv[1:]
    if cmd in ("label", "under"):
        bad = [a for a in args if a != "--direct" and ":" not in a]
        if bad:
            print(f"Not a CURIE: {', '.join(bad)}. Write PREFIX:ID, e.g. GO:0008150.", file=sys.stderr)
            return 64
    ok = True
    if cmd == "label":
        for c in args:
            lab = label(c)
            old = lab is not None and obsolete(c)
            ok &= lab is not None and not old
            tag = "\tOBSOLETE" if old else ""
            print(f"{c}\t{lab if lab is not None else 'NOT FOUND'}{tag}")
    elif cmd == "under":
        direct = "--direct" in args
        args = [a for a in args if a != "--direct"]
        if len(args) < 2:
            print("under needs a root and at least one term: under ROOT TERM [TERM ...]", file=sys.stderr)
            return 64
        root, terms = args[0], args[1:]
        if label(root) is None or obsolete(root):
            print(f"{root}\t{'NOT FOUND' if label(root) is None else 'OBSOLETE'}")
            return 1
        for c in terms:
            if label(c) is None or obsolete(c):
                print(f"{c}\t{'NOT FOUND' if label(c) is None else 'OBSOLETE'}")
                ok = False
                continue
            if direct:
                hit = root in parents(c)
                print(f"{c}\t{'a direct child of' if hit else 'NOT a direct child of'} {root}")
            else:
                hit = c == root or root in ancestors(c)
                print(f"{c}\t{'under' if hit else 'NOT under'} {root}")
            ok &= hit
    else:
        onto, query = args[0], " ".join(args[1:])
        if _oak_mode():
            for c, lab in _oak("search", query)[:10]:
                print(f"{c}\t{lab}")
            return 0
        onto = _ols_ontology() or onto
        q = urllib.parse.urlencode({"q": query, "ontology": onto, "rows": 10, "exact": "false"})
        for d in _get(f"{OLS}/search?{q}").get("response", {}).get("docs", []):
            print(f"{d.get('obo_id')}\t{d.get('label')}")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Unreachable as exc:
        where = f"The adapter {ADAPTER}" if _oak_mode() else "OLS"
        print(f"{where} did not answer ({exc}). Try again later.", file=sys.stderr)
        sys.exit(2)
    except OakFailed as exc:
        print(f"OAK failed, and trying again will not help: {exc}", file=sys.stderr)
        sys.exit(3)
