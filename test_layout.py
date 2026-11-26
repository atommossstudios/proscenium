"""Tests for full-width layout, scrolling, fit mode and split views."""

from __future__ import annotations

import tempfile
from pathlib import Path

from proscenium import tui
from proscenium.math import swidth
from proscenium.md import parse_deck
from proscenium.render import (HELP_ROWS, Renderer, _content_width,
                          help_page_count)
from proscenium.theme import get_theme


def _deck(src: str):
    return parse_deck("---\ntitle: t\n---\n\n" + src, "t")


def _renderer(src: str, width: int = 80, height: int = 14, **kwargs):
    return Renderer(_deck(src), get_theme("midnight"), width, height, True,
                    math_engine="unicode", **kwargs)


def _app(src: str, size=(80, 16)):
    root = tempfile.TemporaryDirectory()
    path = Path(root.name) / "deck.md"
    path.write_text("---\ntitle: t\n---\n\n" + src, encoding="utf-8")
    app = tui.App(str(path), size=size, math_engine="unicode")
    return root, app


def test_content_width_defaults_to_full_terminal() -> None:
    assert _content_width("full", 120) == 118
    r = _renderer("# one\n\ntext\n", width=120, height=14)
    assert r.content_w == 118
    assert r.left == 1
    assert all(len(line.plain) == 120 for line in r.render_slide(0))


def test_content_width_can_be_limited() -> None:
    assert _content_width("92", 120) == 92
    assert _content_width("60%", 120) == 72
    assert _content_width("60", 120) == 60
    r = _renderer("# one\n\ntext\n", width=120, height=14,
                  width_setting="60")
    assert r.content_w == 60


def test_per_slide_width_overrides_deck_default() -> None:
    src = "# one\n\ntext\n\n---\n\n<!-- slide: width=40 -->\n\n# two\n\ntext\n"
    r = _renderer(src, width=100, height=14, width_setting="full")
    r.render_slide(0)
    assert r.content_w == 98
    r.render_slide(1)
    assert r.content_w == 40


def test_scrolling_keeps_every_line_reachable() -> None:
    lines = "\n\n".join(f"UNIQUE LINE {i:03d}" for i in range(1, 201))
    r = _renderer("# Head\n\n" + lines, width=60, height=12)
    first = r.render_slide(0)
    assert r.max_scroll > 0
    assert "UNIQUE LINE 001" in "\n".join(l.plain for l in first)
    r.scroll_y = r.max_scroll
    last = r.render_slide(0)
    text = "\n".join(l.plain for l in last)
    assert "UNIQUE LINE 200" in text
    assert "UNIQUE LINE 001" not in text


def test_scroll_indicator_appears_in_footer() -> None:
    lines = "\n\n".join(f"line {i}" for i in range(1, 60))
    r = _renderer("# Head\n\n" + lines, width=60, height=12)
    frame = r.render_slide(0)
    assert "↕" in frame[-2].plain


def test_fit_compacts_vertical_spacing() -> None:
    lines = "\n\n".join(f"line {i}" for i in range(1, 40))
    normal = _renderer("# Head\n\n" + lines, width=60, height=12)
    normal.render_slide(0)
    fitted = _renderer("# Head\n\n" + lines, width=60, height=12, fit=True)
    fitted.render_slide(0)
    assert fitted.max_scroll < normal.max_scroll


def test_split_layout_places_two_columns_side_by_side() -> None:
    src = ("<!-- slide: layout=split -->\n\n## Topic\n\n- alpha\n- beta\n\n"
           "## Other\n\n- gamma\n- delta\n")
    frame = _renderer(src, width=90, height=20).render_slide(0)
    rows = [line.plain for line in frame]
    assert any("alpha" in row and "Other" in row for row in rows), rows


def test_width_and_fit_keys_toggle_state() -> None:
    root, app = _app("# one\n\ntext\n")
    try:
        assert app.width_setting == "full"
        app.handle("w")
        assert app.width_setting == "92"
        assert app.renderer.content_w == _content_width("92", 80)
        assert app.fit is False
        app.handle("f")
        assert app.fit is True
        assert app.renderer.fit is True
    finally:
        root.cleanup()


def test_scroll_keys_move_the_current_pane() -> None:
    src = "# Head\n\n" + "\n\n".join(f"line {i}" for i in range(1, 60))
    root, app = _app(src, size=(60, 12))
    try:
        app.frame()
        assert app.renderer.max_scroll > 0
        app.handle("J")
        assert app.renderer.scroll_y == 1
        app.handle("d")
        paged = app.renderer.scroll_y
        assert paged > 1
        app.handle("K")
        assert app.renderer.scroll_y == paged - 1
    finally:
        root.cleanup()


def test_split_layout_honours_count() -> None:
    src = ("<!-- slide: layout=split count=3 -->\n\n## Head\n\n- a\n- b\n\n"
           "## Mid\n\n- c\n- d\n\n## Tail\n\n- e\n- f\n")
    frame = _renderer(src, width=100, height=20).render_slide(0)
    rows = [line.plain for line in frame]
    text = "\n".join(rows)
    assert all(marker in text for marker in ("▎ Head", "▎ Mid", "▎ Tail"))
    assert any("Mid" in row and "Tail" in row for row in rows), rows


def test_compare_needs_a_reasonable_width() -> None:
    root, app = _app("# one\n\n---\n\n# two\n", size=(20, 10))
    try:
        app.handle("c")
        assert app.compare is False
        assert "40 columns" in (app.flash or "")
    finally:
        root.cleanup()


def test_compare_mode_stitches_two_slides() -> None:
    root, app = _app("# One\n\nfirst\n\n---\n\n# Two\n\nsecond\n")
    try:
        app.compare = True
        app.rebuild()
        frame = app.frame()
        assert len(frame) == 16
        assert all(len(line.plain) == 80 for line in frame)
        text = "\n".join(line.plain for line in frame)
        assert "│" in text
        assert "One" in text and "Two" in text
        assert app.frame_placements == []
    finally:
        root.cleanup()


def test_compare_fits_exactly_forty_columns() -> None:
    root, app = _app("# One\n\nfirst\n\n---\n\n# Two\n\nsecond\n",
                     size=(40, 20))
    try:
        app.handle("c")
        assert app.compare is True
        frame = app.frame()
        assert len(frame) == 20
        assert [renderer.width for renderer in app.compare_renderers] == [19, 20]
        assert all(len(line.plain) == 40 for line in frame)
    finally:
        root.cleanup()


def test_compare_header_replaces_slide_heading() -> None:
    root, app = _app("# One\n\nfirst\n\n---\n\n# Two\n\nsecond\n",
                     size=(80, 16))
    try:
        app.compare = True
        app.rebuild()
        frame = app.frame()
        left_w = app.compare_renderers[0].width
        right_w = app.compare_renderers[1].width
        left = "\n".join(line.plain[:left_w] for line in frame)
        right = "\n".join(line.plain[-right_w:] for line in frame)
        assert left.splitlines()[0].strip().startswith("1/2")
        assert right.splitlines()[0].strip().startswith("2/2")
        assert left.count("One") == 1
        assert right.count("Two") == 1
    finally:
        root.cleanup()


def test_compare_header_drops_wrapped_title_continuation() -> None:
    root, app = _app(
        "# A deliberately long title that wraps\n\nbody\n\n---\n\n"
        "# Another deliberately long title\n\nbody\n",
        size=(60, 12))
    try:
        app.compare = True
        app.rebuild()
        frame = app.frame()
        left_w = app.compare_renderers[0].width
        right_w = app.compare_renderers[1].width
        left = "\n".join(line.plain[:left_w] for line in frame)
        right = "\n".join(line.plain[-right_w:] for line in frame)
        assert "wraps" not in left
        assert "title" not in left
        assert "title" not in right
    finally:
        root.cleanup()


def test_help_fits_small_terminals() -> None:
    for size in ((20, 8), (40, 20), (80, 24)):
        width, height = size
        root, app = _app("# one\n\ntext\n", size=size)
        try:
            pages = help_page_count(width, height)
            text = ""
            for page in range(pages):
                lines = app.renderer.render_help(page)
                assert len(lines) == height
                assert all(swidth(line.plain) <= width for line in lines)
                text += "\n".join(line.plain for line in lines)
            assert "╭" in text and "╯" in text
            if pages > 1:
                assert f"1/{pages}" in text
            for full, _desc, compact, _short in HELP_ROWS:
                assert full in text or compact in text
        finally:
            root.cleanup()


def test_help_paging_keys() -> None:
    root, app = _app("# one\n\ntext\n", size=(20, 8))
    try:
        app.handle("?")
        assert app.mode == "help"
        assert app.help_page == 0
        app.handle("right")
        assert app.help_page == 1
        app.handle("left")
        assert app.help_page == 0
        app.handle("x")
        assert app.mode == "slide"
    finally:
        root.cleanup()
