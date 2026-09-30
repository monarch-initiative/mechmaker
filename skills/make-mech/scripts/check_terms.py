#!/usr/bin/env python3
"""Check ontology CURIEs against OLS4 before a Mech exists. Standard library only.

    check_terms.py label GO:0008150 ENVO:01000813       # print each term's label
    check_terms.py under ENVO:01000813 ENVO:00000051 ENVO:00000022
        # is the first CURIE an is-a ancestor (or self) of each of the rest?
    check_terms.py search envo "hot spring"               # top matches

Exit status is 1 if any term is missing or any check fails, so the result can
gate a script. It exits 2 if OLS does not answer after three tries: that is an
outage, not a missing term. Ontology ids default to the lowercased prefix.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OLS = "https://www.ebi.ac.uk/ols4/api"


class Unreachable(Exception):
    pass


def _get(url, tries=3):
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError:
            raise  # a real answer, such as 404 for a missing term
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == tries:
                raise Unreachable(str(exc)) from exc
            time.sleep(5 * attempt)


def _term_url(curie, suffix=""):
    prefix, local = curie.split(":", 1)
    iri = f"http://purl.obolibrary.org/obo/{prefix}_{local}"
    enc = urllib.parse.quote(urllib.parse.quote(iri, safe=""), safe="")
    return f"{OLS}/ontologies/{prefix.lower()}/terms/{enc}{suffix}"


def label(curie):
    try:
        return _get(_term_url(curie)).get("label")
    except urllib.error.HTTPError:
        return None


def ancestors(curie):
    out, url = set(), _term_url(curie, "/ancestors?size=500")
    while url:
        data = _get(url)
        out |= {t.get("obo_id") for t in data.get("_embedded", {}).get("terms", [])}
        url = data.get("_links", {}).get("next", {}).get("href")
    return out


def main(argv):
    if len(argv) < 2 or argv[0] not in ("label", "under", "search"):
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    ok = True
    if cmd == "label":
        for c in args:
            lab = label(c)
            ok &= lab is not None
            print(f"{c}\t{lab if lab is not None else 'NOT FOUND'}")
    elif cmd == "under":
        root, terms = args[0], args[1:]
        if label(root) is None:
            print(f"{root}\tNOT FOUND")
            return 1
        for c in terms:
            if label(c) is None:
                print(f"{c}\tNOT FOUND")
                ok = False
                continue
            hit = c == root or root in ancestors(c)
            ok &= hit
            print(f"{c}\t{'under' if hit else 'NOT under'} {root}")
    else:
        onto, query = args[0], " ".join(args[1:])
        q = urllib.parse.urlencode({"q": query, "ontology": onto, "rows": 10, "exact": "false"})
        for d in _get(f"{OLS}/search?{q}").get("response", {}).get("docs", []):
            print(f"{d.get('obo_id')}\t{d.get('label')}")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Unreachable as exc:
        print(f"OLS did not answer after three tries ({exc}). Try again later.", file=sys.stderr)
        sys.exit(2)
