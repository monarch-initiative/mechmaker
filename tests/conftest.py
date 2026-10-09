"""Settings for every test in this folder."""

from __future__ import annotations

import os

# Copier commits in temporary repositories and deletes them when it is done, and the tests copy
# and delete repositories of their own. git can start its automatic cleanup (gc, maintenance)
# in the background after a commit; one still writing into a folder being copied or deleted
# fails the test at random ("Directory not empty"). Keep it in the foreground. sync_mech.py
# does the same for the Copier it runs.
_n = int(os.environ.get("GIT_CONFIG_COUNT") or 0)
for _i, _key in enumerate(("gc.autoDetach", "maintenance.autoDetach"), _n):
    os.environ[f"GIT_CONFIG_KEY_{_i}"] = _key
    os.environ[f"GIT_CONFIG_VALUE_{_i}"] = "false"
os.environ["GIT_CONFIG_COUNT"] = str(_n + 2)
