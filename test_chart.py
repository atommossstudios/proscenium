"""Tests for chart and data-visualisation blocks."""

from __future__ import annotations

import sys

from proscenium.md import Chart, parse_deck
from proscenium.render import Renderer
from proscenium.theme import get_theme


DECK = """\
---
title: Charts
---

# Charts

<!-- chart: type=bar title="Transform cost" caption="lower is better" -->

| Transform | Build | Query |
|:----------|------:|------:|
| DFT       | 42     | 18    |
| FFT       | 9      | 3     |

```chart
type=line
title=Trend
height=4
Version,r1,r2
v1,18,22
v2,24,29
v3,31,35
```
"""


def _braille_box(renderer: Renderer) -> tuple[int, int]:
    lines: list[str] = []
    columns: set[int] = set()
    for line in renderer.render_slide(0):
        plain = line.plain
        hits = [i for i, ch in enumerate(plain)
                if 0x2800 <= ord(ch) <= 0x28FF]
        if hits:
            lines.append(plain)
            columns.update(hits)
    return (max(columns) - min(columns) + 1 if columns else 0, len(lines))


def main() -> int:
    deck = parse_deck(DECK, "charts")
    blocks = deck.slides[0].blocks
    charts = [b for b in blocks if isinstance(b, Chart)]
    assert len(charts) == 2, blocks

    bar, line = charts
    assert bar.options["type"] == "bar"
    assert bar.options["title"] == "Transform cost"
    assert bar.table.header == ["Transform", "Build", "Query"]
    assert bar.table.rows[0] == ["DFT", "42", "18"]

    assert line.options["type"] == "line"
    assert line.options["height"] == "4"
    assert line.table.header == ["Version", "r1", "r2"]
    assert line.table.rows[2] == ["v3", "31.0", "35.0"]

    renderer = Renderer(deck, get_theme("midnight"), 80, 28, True,
                        math_engine="unicode")
    frame = renderer.render_slide(0)
    text = "\n".join(line.plain for line in frame)
    assert "Transform cost" in text
    assert "lower is better" in text
    assert "█" in text
    assert "Trend" in text
    assert "●" in text

    for kind in ("bar", "stacked", "columns", "line", "spark", "pie",
                 "donut", "gauge", "scatter"):
        one = parse_deck(
            "---\ntitle: t\n---\n\n# t\n\n```chart\n"
            f"type={kind}\ntitle={kind}\n"
            "Month,Alpha,Beta\nJan,12,5\nFeb,19,9\nMar,14,13\n```\n",
            "t",
        )
        r = Renderer(one, get_theme("midnight"), 80, 24, True,
                     math_engine="unicode")
        assert len(r.render_slide(0)) == 24, kind

    pie_deck = parse_deck(
        "---\ntitle: t\n---\n\n# t\n\n"
        "<!-- chart: pie title=\"Split\" caption=\"percentages\" -->\n\n"
        "| Part | Hours |\n|:-----|------:|\n"
        "| A    | 30    |\n| B    | 70    |\n",
        "t",
    )
    pie = next(b for b in pie_deck.slides[0].blocks if isinstance(b, Chart))
    assert pie.options["type"] == "pie"
    pie_renderer = Renderer(pie_deck, get_theme("midnight"), 72, 22, True,
                            math_engine="unicode")
    pie_text = "\n".join(line.plain
                         for line in pie_renderer.render_slide(0))
    assert "Split" in pie_text and "percentages" in pie_text
    assert "30%" in pie_text and "70%" in pie_text
    assert any(0x2800 <= ord(ch) <= 0x28FF for ch in pie_text), pie_text
    # Outer chart panel plus the quiet frame around the disk itself.
    assert pie_text.count("╭") >= 2 and pie_text.count("╮") >= 2, pie_text

    bare_deck = parse_deck(
        "---\ntitle: t\n---\n\n# t\n\n"
        '<!-- chart: type=pie title="Bare" frame=none -->\n\n'
        "| Part | Value |\n|:-----|------:|\n| A | 3 |\n| B | 7 |\n",
        "t",
    )
    bare_text = "\n".join(
        line.plain for line in Renderer(
            bare_deck, get_theme("midnight"), 72, 22, True,
            math_engine="unicode").render_slide(0))
    assert bare_text.count("╭") == 1, bare_text

    donut_deck = parse_deck(
        "---\ntitle: t\n---\n\n# t\n\n"
        "<!-- chart: type=donut title=\"Ring\" hole=.6 -->\n\n"
        "| Part | Value |\n|:-----|------:|\n| A | 3 |\n| B | 7 |\n",
        "t",
    )
    donut_renderer = Renderer(donut_deck, get_theme("midnight"), 72, 22, True,
                              math_engine="unicode")
    donut_text = "\n".join(line.plain
                           for line in donut_renderer.render_slide(0))
    assert any(0x2800 <= ord(ch) <= 0x28FF for ch in donut_text)
    assert "7" in donut_text  # centre total

    # Pie categories must each get their own colour, including when the data
    # has a single numeric series (the common pie/donut case).
    color_deck = parse_deck(
        "---\ntitle: t\n---\n\n# t\n\n"
        "<!-- chart: type=pie title=\"Colours\" "
        "colors=\"#ff0000,#00ff00,#0000ff,#ffff00\" -->\n\n"
        "| Part | Value |\n|:-----|------:|\n"
        "| A | 25 |\n| B | 25 |\n| C | 25 |\n| D | 25 |\n",
        "t",
    )
    color_renderer = Renderer(color_deck, get_theme("midnight"), 80, 24, True,
                              math_engine="unicode")
    sector_styles: set[str] = set()
    for line in color_renderer.render_slide(0):
        for span in line.spans:
            fragment = line.plain[span.start:span.end]
            if any(0x2800 <= ord(ch) <= 0x28FF for ch in fragment):
                sector_styles.add(str(span.style))
    assert len(sector_styles) >= 3, sector_styles

    dump_box = _braille_box(Renderer(pie_deck, get_theme("midnight"), 80, 24,
                                     True, math_engine="unicode", dump=True))
    assert abs(dump_box[0] - dump_box[1]) <= 2, dump_box
    terminal_box = _braille_box(Renderer(
        pie_deck, get_theme("midnight"), 80, 24, True,
        cell_size=(10, 20), math_engine="unicode"))
    assert terminal_box[0] >= terminal_box[1] * 1.5, terminal_box

    print("chart: ok")
    return 0


def test_charts() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
