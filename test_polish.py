"""Tests for presentation polish: directives, styles and layouts."""

from __future__ import annotations

import sys

from unveil.md import (Callout, Columns, MathBlock, Table, Toc,
                       parse_directive, parse_deck)
from unveil.render import Renderer
from unveil.theme import get_theme, override_theme


DECK = """\
---
title: Deck
accent: "#ff0000"
clock: true
eq_style: square
table_style: grid
---

<!-- slide: layout=section section="Part I" subtitle="Intro" -->

# Section

---

<!-- toc: title="Roadmap" start=1 -->

## Agenda

<!-- eq: style=double title="Identity" number=1 align=right -->
$$ E = mc^2 $$

<!-- table: style=minimal title="Data" caption="Numbers" zebra=false -->
| A | B |
|---|---|
| 1 | 2 |

<!-- warning: title="Careful" -->
Be careful.

<!-- columns: 2 -->
### Left
- a
### Right
- b
<!-- endcolumns -->
"""


def test_directives() -> None:
    kind, opts = parse_directive('<!-- eq: style="double" title="A B" number=1 -->')
    assert kind == "eq"
    assert opts == {"style": "double", "title": "A B", "number": "1"}

    kind, opts = parse_directive('<!-- warning: title="Heads up" -->')
    assert kind == "callout" and opts["kind"] == "warning"
    assert opts["title"] == "Heads up"

    assert parse_directive("<!-- just a comment -->") is None


def test_parsing() -> None:
    deck = parse_deck(DECK, "deck")
    assert len(deck.slides) == 2
    first, second = deck.slides
    assert first.options["layout"] == "section"
    assert first.options["section"] == "Part I"
    assert first.options["subtitle"] == "Intro"

    kinds = [type(b) for b in second.blocks]
    assert Toc in kinds
    assert MathBlock in kinds and Table in kinds
    assert Callout in kinds and Columns in kinds

    eq = next(b for b in second.blocks if isinstance(b, MathBlock))
    assert eq.options["style"] == "double"
    assert eq.options["title"] == "Identity"
    assert eq.options["number"] == "1"

    table = next(b for b in second.blocks if isinstance(b, Table))
    assert table.options["style"] == "minimal"
    assert table.options["zebra"] == "false"

    callout = next(b for b in second.blocks if isinstance(b, Callout))
    assert callout.kind == "warning"
    assert callout.title == "Careful"
    assert len(callout.blocks) == 1

    cols = next(b for b in second.blocks if isinstance(b, Columns))
    assert cols.count == 2
    assert len(cols.blocks) == 4


def test_unicode_render() -> None:
    deck = parse_deck(DECK, "deck")
    r = Renderer(deck, get_theme("midnight"), 100, 30, True,
                 math_engine="unicode")
    section = "\n".join(line.plain for line in r.render_slide(0))
    assert "Section" in section and "Intro" in section

    frame = r.render_slide(1)
    text = "\n".join(line.plain for line in frame)
    assert "Roadmap" in text
    assert "Identity" in text and "(1)" in text
    assert "Data" in text and "Numbers" in text
    assert "Careful" in text
    assert "Left" in text and "Right" in text
    # Minimal table style uses the light horizontal rule, not a full border.
    assert "╶" in text
    # The clock runs on every slide; the section label is on the section slide.
    assert "00:" in text
    assert "Part I" in section


def test_latex_render() -> None:
    from unveil import latex

    if not latex.available():
        return
    deck = parse_deck(DECK, "deck")
    r = Renderer(deck, get_theme("midnight"), 100, 30, True,
                 cell_size=(20, 45), graphics=True, math_engine="latex")
    lines = r.render_slide(1)
    assert len(lines) == 30
    assert len(r.frame_placements) == 1, r.frame_placements
    assert not any(any("\ue000" <= ch <= "\uf8ff" for ch in line.plain)
                   for line in lines)


def test_default_styles() -> None:
    deck = parse_deck(
        "---\ntitle: Defaults\n---\n\n# Defaults\n\n"
        "$$E = mc^2$$\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
        "defaults",
    )
    r = Renderer(deck, get_theme("midnight"), 80, 24, True,
                 math_engine="unicode")
    text = "\n".join(line.plain for line in r.render_slide(0))
    # Equations and tables are bordered panels by default again.
    assert "╭" in text and "╯" in text, text
    assert "│" in text and "┼" in text, text
    # The heading accent rule is still present.
    assert "▌" in text


def test_table_row_lines() -> None:
    deck = parse_deck(
        "---\ntitle: Lines\n---\n\n# Lines\n\n"
        "<!-- table: lines=true -->\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n",
        "lines",
    )
    r = Renderer(deck, get_theme("midnight"), 60, 18, True,
                 math_engine="unicode")
    text = "\n".join(line.plain for line in r.render_slide(0))
    # A rounded table has one header separator by default; lines=true adds
    # separators between the two data rows as well.
    assert text.count("├") >= 2, text
    assert text.count("┼") >= 2, text


def test_rules_and_borders() -> None:
    deck = parse_deck(
        "---\ntitle: Decor\n---\n\n# Decor\n\n"
        '<!-- rule: style=double label="PART TWO" -->\n\n'
        '<!-- rule: style=dotted label="AFTER" -->\n\n***\n\n'
        '<!-- border: style=square title="Box" -->\n'
        "Text inside a frame.\n"
        "<!-- endborder -->\n",
        "decor",
    )
    blocks = deck.slides[0].blocks
    assert any(type(b).__name__ == "Rule" for b in blocks)
    assert any(type(b).__name__ == "Frame" for b in blocks)
    r = Renderer(deck, get_theme("midnight"), 80, 24, True,
                 math_engine="unicode")
    text = "\n".join(line.plain for line in r.render_slide(0))
    assert "PART TWO" in text and "═" in text, text
    assert "AFTER" in text and "┄" in text, text
    assert "┌" in text and "Box" in text, text


def test_theme_override() -> None:
    theme = override_theme(get_theme("midnight"), {"accent": "ff0000"})
    assert theme.accent == "#ff0000"
    assert override_theme(theme, {"accent": "not-a-color"}).accent == "#ff0000"


def main() -> int:
    test_directives()
    test_parsing()
    test_unicode_render()
    test_latex_render()
    test_default_styles()
    test_table_row_lines()
    test_rules_and_borders()
    test_theme_override()
    print("polish: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
