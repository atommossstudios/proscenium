"""Regression tests for v1 correctness fixes."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from unveil import latex, tui
from unveil.md import Callout, Chart, Table, parse_deck
from unveil.render import Renderer
from unveil.theme import get_theme


def _render(src: str, width: int = 60, height: int = 22) -> list[str]:
    deck = parse_deck(src, "t")
    renderer = Renderer(deck, get_theme("midnight"), width, height, True,
                        math_engine="unicode")
    return [line.plain for line in renderer.render_slide(0)]


def test_unicode_digit_does_not_crash_jump_prompt() -> None:
    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "deck.md"
        path.write_text("---\ntitle: t\n---\n\n# one\n\n---\n\n# two\n",
                        encoding="utf-8")
        app = tui.App(str(path), math_engine="unicode")
        app.handle("²")
        assert app.pending == ""
        app.handle("enter")
        assert app.index == 0


def test_auto_dump_honours_requested_size() -> None:
    with patch.object(tui, "dump", return_value=0) as dump:
        with patch.object(tui.sys.stdin, "isatty", return_value=False), \
                patch.object(tui.sys.stdout, "isatty", return_value=False):
            tui.run("deck.md", size=(44, 19))
    assert dump.call_args.kwargs["size"] == (44, 19)


def test_kitty_image_cache_tracks_source_changes() -> None:
    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "shot.png"
        path.write_bytes(b"before")
        parts: list[str] = []
        first = tui._image_id_for(str(path), parts)
        assert any("a=t,f=100" in chunk for chunk in parts)

        parts.clear()
        second = tui._image_id_for(str(path), parts)
        assert second == first and not parts, "unchanged file was retransmitted"

        path.write_bytes(b"changed contents")
        parts.clear()
        third = tui._image_id_for(str(path), parts)
        assert third != first
        assert any("d=i" in chunk for chunk in parts), "old id was not freed"
        assert any("a=t,f=100" in chunk for chunk in parts)

        with patch.object(tui.sys, "stdout") as stdout:
            tui.clear_images()
        assert tui._IMAGE_IDS == {}
        stdout.write.assert_called_once()


def test_nested_tables_and_charts_fit_their_column() -> None:
    lines = _render(
        "---\ntitle: t\n---\n\n# t\n\n<!-- columns: 2 -->\n\n"
        "### Tab\n\n<!-- table: lines=true -->\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "### Chart\n\n<!-- chart: type=bar height=3 -->\n"
        "| X | Y |\n|:--|--:|\n| a | 1 |\n| b | 2 |\n\n"
        "<!-- endcolumns -->\n",
    )
    assert all(len(line) <= 60 for line in lines)
    assert any("┼" in line and line.find("┼") < 30 for line in lines)
    assert any("█" in line and line.find("█") > 30 for line in lines)


def test_frameless_equation_does_not_overflow() -> None:
    lines = _render(
        "---\ntitle: t\n---\n\n# t\n\n<!-- eq: style=none -->\n"
        "$$E = mc^2 + a + b + c + d + e + f + g + h + i + j$$\n",
    )
    assert max(len(line) for line in lines) <= 60


def test_failed_latex_compile_is_cached_in_process() -> None:
    latex.reset_failures()
    calls: list[str] = []

    def fake_compile(source: str, fg: str, bg: str, dest: Path) -> bool:
        calls.append(source)
        return False

    with patch.object(latex, "available", return_value=True), \
            patch.object(latex, "_compile", side_effect=fake_compile), \
            patch.object(latex, "cache_root", return_value=Path("/nonexistent")):
        assert latex.render(r"\notacommand{1}", "#fff", "#000") is None
        assert latex.render(r"\notacommand{1}", "#fff", "#000") is None
    assert len(calls) == 1, calls
    latex.reset_failures()


def test_block_options_reach_block_inside_callout() -> None:
    deck = parse_deck(
        "---\ntitle: t\n---\n\n# t\n\n"
        '<!-- note: title="Heads up" -->\n\n'
        "<!-- table: lines=true -->\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n",
        "t",
    )
    callout = next(b for b in deck.slides[0].blocks if isinstance(b, Callout))
    table = next(b for b in callout.blocks if isinstance(b, Table))
    assert table.options["lines"] == "true"
    assert callout.title == "Heads up"
    assert "lines" not in callout.options


def test_single_series_sparkline_appears_once() -> None:
    lines = _render(
        "---\ntitle: t\n---\n\n# t\n\n```chart\n"
        "type=spark\nMon,12\nTue,19\nWed,14\nThu,23\n```\n",
    )
    glyphs = set("▁▂▃▄▅▆▇█")
    spark_rows = [line for line in lines if any(ch in glyphs for ch in line)]
    assert len(spark_rows) == 1, spark_rows


def test_footer_fits_narrow_dump() -> None:
    lines = _render(
        "---\ntitle: t\nfooter: A rather long deck title\nclock: true\n---\n\n"
        "<!-- slide: section=\"Part I · Analysis\" -->\n\n# one\n",
        width=40,
    )
    assert max(len(line) for line in lines) <= 40


def test_large_equation_box_keeps_tall_constructs_intact() -> None:
    lines = _render(
        "---\ntitle: t\n---\n\n# Matrices\n\n"
        "$$A = \\begin{pmatrix}\n"
        "a_{11} & a_{12} \\\\\n"
        "a_{21} & a_{22}\n"
        "\\end{pmatrix}\n"
        "\\qquad \\det(A) = \\sum_{i=1}^{n} a_{i,i}$$\n",
        width=100,
        height=30,
    )
    text = "\n".join(lines)
    assert "╭" in text and "╰" in text, text
    assert any("⎛" in line and "⎞" in line for line in lines), text
    assert any("⎝" in line and "⎠" in line for line in lines), text
    delimiters = [line.index(glyph) for line in lines
                  for glyph in ("⎛", "⎜", "⎝") if glyph in line]
    assert delimiters and len(set(delimiters)) == 1, delimiters


if __name__ == "__main__":
    test_unicode_digit_does_not_crash_jump_prompt()
    test_auto_dump_honours_requested_size()
    test_kitty_image_cache_tracks_source_changes()
    test_nested_tables_and_charts_fit_their_column()
    test_frameless_equation_does_not_overflow()
    test_failed_latex_compile_is_cached_in_process()
    test_block_options_reach_block_inside_callout()
    test_single_series_sparkline_appears_once()
    test_footer_fits_narrow_dump()
    print("regressions: ok")
