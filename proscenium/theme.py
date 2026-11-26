"""Terminal themes for proscenium."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    fg: str
    dim: str
    accent: str
    accent2: str
    math: str
    code_bg: str
    border: str
    table_head: str
    good: str
    bad: str
    syntax: str

    def on(self) -> str:
        return f"on {self.bg}"


THEMES: dict[str, Theme] = {
    "midnight": Theme(
        name="midnight", bg="#0b0e14", fg="#d5dbe6", dim="#5c677d",
        accent="#7aa2f7", accent2="#bb9af7", math="#7dcfff",
        code_bg="#121722", border="#2a3140", table_head="#1b2230",
        good="#9ece6a", bad="#f7768e", syntax="monokai",
    ),
    "gruvbox": Theme(
        name="gruvbox", bg="#1d2021", fg="#ebdbb2", dim="#928374",
        accent="#fabd2f", accent2="#83a598", math="#b8bb26",
        code_bg="#282828", border="#3c3836", table_head="#32302f",
        good="#b8bb26", bad="#fb4934", syntax="gruvbox-dark",
    ),
    "nord": Theme(
        name="nord", bg="#2e3440", fg="#eceff4", dim="#7b88a1",
        accent="#88c0d0", accent2="#b48ead", math="#a3be8c",
        code_bg="#3b4252", border="#434c5e", table_head="#3b4252",
        good="#a3be8c", bad="#bf616a", syntax="nord",
    ),
    "dracula": Theme(
        name="dracula", bg="#282a36", fg="#f8f8f2", dim="#6272a4",
        accent="#bd93f9", accent2="#8be9fd", math="#ffb86c",
        code_bg="#21222c", border="#44475a", table_head="#343746",
        good="#50fa7b", bad="#ff5555", syntax="dracula",
    ),
    "paper": Theme(
        name="paper", bg="#f6f2e9", fg="#2b2b2b", dim="#8a8578",
        accent="#b45309", accent2="#0f766e", math="#6d28d9",
        code_bg="#eee8da", border="#d6cfc0", table_head="#e8e1d2",
        good="#15803d", bad="#b91c1c", syntax="friendly",
    ),
    "mono": Theme(
        name="mono", bg="#101010", fg="#e6e6e6", dim="#777777",
        accent="#ffffff", accent2="#bbbbbb", math="#ffffff",
        code_bg="#181818", border="#333333", table_head="#1e1e1e",
        good="#cccccc", bad="#999999", syntax="monokai",
    ),
}


def get_theme(name: str) -> Theme:
    return THEMES.get(name.strip().lower(), THEMES["midnight"])


def theme_names() -> list[str]:
    return list(THEMES)


_COLOR_KEYS = {
    "bg", "fg", "dim", "accent", "accent2", "math", "code_bg",
    "border", "table_head", "good", "bad",
}
_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def override_theme(theme: Theme, meta: dict[str, str]) -> Theme:
    """Apply front-matter colour keys (``accent: "#ff0000"``) to a theme."""

    overrides: dict[str, str] = {}
    for field in fields(Theme):
        if field.name not in _COLOR_KEYS:
            continue
        value = meta.get(field.name)
        if value and _HEX_RE.match(value.strip()):
            value = value.strip()
            overrides[field.name] = (
                value if value.startswith("#") else "#" + value
            )
    return replace(theme, **overrides) if overrides else theme


def mix(a: str, b: str, t: float) -> str:
    a = a.lstrip("#")
    b = b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    out = [round(x + (y - x) * t) for x, y in zip(ca, cb)]
    return "#" + "".join(f"{v:02x}" for v in out)
