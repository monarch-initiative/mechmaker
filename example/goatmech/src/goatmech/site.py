"""Site settings: how the documentation site and record browser look.

    python -m <slug>.site check   # validate conf/site.yaml and report contrast

Settings live in conf/site.yaml. The palette names are Material for MkDocs'
own, so one name colors both the docs site and the record browser. Links in
the browser use the palette color, darkened (light pages) or lightened (dark
pages) just enough to reach WCAG AA contrast, so any palette stays readable.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .paths import MECH_NAME, REPO_ROOT

CONFIG = REPO_ROOT / "conf" / "site.yaml"

# From Material for MkDocs' palette stylesheet: the color, and the text color
# Material puts on it (the docs site uses that pairing; the browser picks its
# own header text for contrast).
PRIMARY = {
    "red": ("#ef5552", "#ffffff"), "pink": ("#e92063", "#ffffff"),
    "purple": ("#ab47bd", "#ffffff"), "deep-purple": ("#7e56c2", "#ffffff"),
    "indigo": ("#4051b5", "#ffffff"), "blue": ("#2094f3", "#ffffff"),
    "light-blue": ("#02a6f2", "#ffffff"), "cyan": ("#00bdd6", "#ffffff"),
    "teal": ("#009485", "#ffffff"), "green": ("#4cae4f", "#ffffff"),
    "light-green": ("#8bc34b", "#ffffff"), "lime": ("#cbdc38", "#1f1f1f"),
    "yellow": ("#ffec3d", "#1f1f1f"), "amber": ("#ffc105", "#1f1f1f"),
    "orange": ("#ffa724", "#1f1f1f"), "deep-orange": ("#ff6e42", "#ffffff"),
    "brown": ("#795649", "#ffffff"), "grey": ("#757575", "#ffffff"),
    "blue-grey": ("#546d78", "#ffffff"),
}
ACCENT = {
    "red": "#ff1947", "pink": "#f50056", "purple": "#df41fb", "deep-purple": "#7c4dff",
    "indigo": "#526cfe", "blue": "#4287ff", "light-blue": "#0091eb", "cyan": "#00bad6",
    "teal": "#00bda4", "green": "#00c753", "light-green": "#63de17", "lime": "#b0eb00",
    "yellow": "#ffd500", "amber": "#ffaa00", "orange": "#ff9100", "deep-orange": "#ff6e42",
}
THEMES = ("auto", "light", "dark")
LIGHT_BG, DARK_BG = "#ffffff", "#151517"
MIN_CONTRAST = 4.5  # WCAG AA for body text

DEFAULTS = {
    "title": MECH_NAME,
    "palette": "indigo",
    "accent": "indigo",
    "theme": "auto",
    "index_columns": ["name", "id", "status"],
    "hidden_sections": [],
    "footer": (
        "AI-curated. Validation checks that citations exist, quotes are exact and "
        "ontology terms are real. It does not check that the science is right."
    ),
}


def _rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in rgb)


def luminance(hex_color: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable(color: str, background: str, minimum: float = MIN_CONTRAST) -> str:
    """Mix color toward black (light background) or white (dark) until readable."""
    target = (0.0, 0.0, 0.0) if luminance(background) > 0.5 else (1.0, 1.0, 1.0)
    base = _rgb(color)
    for step in range(0, 101):
        t = step / 100
        mixed = _hex(tuple(c + (x - c) * t for c, x in zip(base, target, strict=True)))
        if contrast(mixed, background) >= minimum:
            return mixed
    return _hex(target)


def load(path: Path = CONFIG) -> dict:
    data = yaml.safe_load(path.read_text()) if path.exists() else {}
    settings = {**DEFAULTS, **(data or {})}
    return settings


def problems(settings: dict) -> list[str]:
    out = []
    if settings["palette"] not in PRIMARY:
        out.append(f"palette {settings['palette']!r} is not one of: {', '.join(PRIMARY)}")
    if settings["accent"] not in ACCENT:
        out.append(f"accent {settings['accent']!r} is not one of: {', '.join(ACCENT)}")
    if settings["theme"] not in THEMES:
        out.append(f"theme {settings['theme']!r} is not one of: {', '.join(THEMES)}")
    for key in ("index_columns", "hidden_sections"):
        if not isinstance(settings[key], list):
            out.append(f"{key} must be a list")
    return out


def colors(settings: dict) -> dict[str, str]:
    """Every color the browser stylesheet uses, derived from the settings."""
    primary, _ = PRIMARY[settings["palette"]]
    # Header text: whichever of white or near-black reads better on the
    # palette color. Material's own pairing is sometimes under 3:1.
    on_primary = max(("#ffffff", "#1f1f1f"), key=lambda t: contrast(t, primary))
    accent = ACCENT[settings["accent"]]
    return {
        "primary": primary,
        "on_primary": on_primary,
        "accent": accent,
        "link_light": readable(primary, LIGHT_BG),
        "link_dark": readable(primary, DARK_BG),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["check"])
    parser.parse_args(argv)
    settings = load()
    errs = problems(settings)
    for e in errs:
        print(f"ERROR conf/site.yaml: {e}")
    if errs:
        return 1
    c = colors(settings)
    print(f"palette {settings['palette']}, accent {settings['accent']}, theme {settings['theme']}")
    header = contrast(c["on_primary"], c["primary"])
    print(f"  header: {c['on_primary']} on {c['primary']}, contrast {header:.1f}")
    for mode, bg in (("light", LIGHT_BG), ("dark", DARK_BG)):
        link = c[f"link_{mode}"]
        note = "" if link == c["primary"] else f" (adjusted from {c['primary']})"
        print(f"  links on {mode} pages: {link}{note}, contrast {contrast(link, bg):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
