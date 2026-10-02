"""Work around an OAK gap so BioPortal terms can be checked like any others.

OAK's BioPortal adapter (oaklib 0.7.4) replaces `ancestors` with a version
that takes only a term. The term checks call it with `predicates` and
`reflexive`, it raises TypeError, and every BioPortal term fails its dynamic
enum. BioPortal's own ancestors endpoint gives the class hierarchy, which is
is-a, so the patch drops the predicate filter and honors `reflexive`.

It patches only while OAK still has the narrow signature, so it stops acting
once OAK is fixed. Ontologies on other adapters are untouched.
"""

from __future__ import annotations

import inspect


def patch() -> None:
    try:
        from oaklib.implementations.ontoportal.ontoportal_implementation_base import (
            OntoPortalImplementationBase as Base,
        )
    except ImportError:  # OAK moved it; nothing to patch
        return
    original = Base.ancestors
    if "predicates" in inspect.signature(original).parameters or getattr(original, "_mech_patched", False):
        return

    def ancestors(self, start_curies, predicates=None, reflexive=True, **_):
        curies = [start_curies] if isinstance(start_curies, str) else list(start_curies)
        seen: set[str] = set()
        for curie in curies:
            if reflexive and curie not in seen:
                seen.add(curie)
                yield curie
            for a in original(self, curie):
                if a not in seen:
                    seen.add(a)
                    yield a

    ancestors._mech_patched = True
    Base.ancestors = ancestors
