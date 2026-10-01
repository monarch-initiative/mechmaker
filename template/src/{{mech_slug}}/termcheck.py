"""linkml-term-validator, with the OAK workaround in oak_compat applied first.

    python -m <slug>.termcheck validate-data FILE -s SCHEMA -t CLASS --labels -c conf/oak_config.yaml

The justfile runs term checks through this, so BioPortal terms are checked
like terms from any other adapter. Output is filtered on the way out: a
failed BioPortal request prints its URL, and the URL holds the API key.
"""

import re
import sys

from .oak_compat import patch

KEY = re.compile(r"(apikey=)[^&\s'\")]+", re.IGNORECASE)


class Masked:
    """A stream that hides API keys before they are written."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, text):
        return self._stream.write(KEY.sub(r"\1***", text))

    def __getattr__(self, name):
        return getattr(self._stream, name)


def run() -> int:
    sys.stdout, sys.stderr = Masked(sys.stdout), Masked(sys.stderr)
    patch()
    from linkml_term_validator.cli import main  # after the patch

    return main()


if __name__ == "__main__":
    sys.exit(run())
