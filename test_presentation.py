"""Tests for reveal builds, transitions and arbitrary two-slide comparison."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

from unveil import tui
from unveil.math import swidth
from unveil.md import ListBlock, parse_deck, parse_directive
from unveil.render import (Renderer, blend_frames, normalize_transition,
                           reveal_glow)
from unveil.theme import get_theme


BASE = "---\ntitle: t\n---\n\n"


SHORT_SYNTAX_SRC = """@slide section=Short reveal=true

## Build

@reveal

- one
- two

@columns count=2

first

@colbreak

second

@qcolumns

@note title="Tip"
Remember this.

<uv notes>
A secret script.
<uv qnotes>
"""


def test_short_directive_forms() -> None:
    assert parse_directive("<uv slide layout=title section=Grand>") == (
        "slide", {"layout": "title", "section": "Grand"})
    assert parse_directive("@reveal items") == (
        "reveal", {"reveal": "items"})
    assert parse_directive('uv<title="skibdi">') == (
        "slide", {"title": "skibdi"})
    assert parse_directive("</uv columns>") == ("endcolumns", {})
    assert parse_directive("@qnotes") == ("endnotes", {})
    assert parse_directive("@qcolumns") == ("endcolumns", {})
    assert parse_directive("<uv qborder>") == ("endborder", {})


def test_short_syntax_parses_like_comment_syntax() -> None:
    deck = parse_deck(BASE + SHORT_SYNTAX_SRC, "t")
    assert len(deck.slides) == 1
    slide = deck.slides[0]
    assert slide.options["section"] == "Short"
    assert slide.options["reveal"] == "true"
    assert slide.notes == "A secret script."
    kinds = [type(block).__name__ for block in slide.blocks]
    assert "Columns" in kinds
    assert "Callout" in kinds


REVEAL_SRC = """<!-- slide: reveal=true -->

## Build

- one
- two
- three
"""

FOUR_SLIDES = REVEAL_SRC + """
---

# Alpha

alpha text

---

# Beta

beta text

---

# Gamma

gamma text
"""


def _app(src: str, size=(80, 16)):
    root = tempfile.TemporaryDirectory()
    path = Path(root.name) / "deck.md"
    path.write_text(BASE + src, encoding="utf-8")
    app = tui.App(str(path), size=size, math_engine="unicode",
                  transition="none")
    return root, app, path


def _text(app: tui.App) -> str:
    return "\n".join(line.plain for line in app.frame())


def test_reveal_metadata_marks_blocks_and_items() -> None:
    deck = parse_deck(BASE + """<!-- slide: reveal=true -->

## Head

- one
- two

After

---

<!-- reveal: 7 -->

Seven

---

<!-- reveal: items -->

- alpha
- beta
""", "t")
    first = deck.slides[0]
    assert first.options["reveal_steps"] == "3"
    assert first.blocks[0].options.get("reveal") is None
    assert isinstance(first.blocks[1], ListBlock)
    assert [item.reveal for item in first.blocks[1].items] == [1, 2]
    assert first.blocks[2].options["reveal"] == "3"
    assert deck.slides[1].options["reveal_steps"] == "7"
    assert deck.slides[2].options["reveal_steps"] == "2"


def test_render_slide_hides_later_builds() -> None:
    deck = parse_deck(BASE + REVEAL_SRC, "t")
    renderer = Renderer(deck, get_theme("midnight"), 80, 14, True,
                        math_engine="unicode")
    frames = ["\n".join(line.plain for line in renderer.render_slide(0, step=n))
              for n in range(4)]
    assert "• one" not in frames[0]
    assert "• one" in frames[1] and "• two" not in frames[1]
    assert "• two" in frames[2] and "• three" not in frames[2]
    assert "• three" in frames[3]
    assert ["0/3", "1/3", "2/3", "3/3"] == [
        re.search(r"●\s+(\d+/\d+)", frame).group(1)  # type: ignore[union-attr]
        for frame in frames
    ]


def test_transition_effects_blend_whole_rows() -> None:
    assert normalize_transition("crossfade") == "fade"
    assert normalize_transition("off") == "cut"
    assert normalize_transition("nonsense") == "fade"
    deck = parse_deck(BASE + "# One\n\nalpha\n\n---\n\n# Two\n\nbeta\n", "t")
    renderer = Renderer(deck, get_theme("midnight"), 80, 14, True,
                        math_engine="unicode")
    old = renderer.render_slide(0)
    new = renderer.render_slide(1)
    assert len(old) == len(new)
    for kind in ("cut", "fade", "wipe", "rise", "iris", "blinds", "dissolve"):
        for progress in (0.0, 0.3, 0.5, 0.8, 1.0):
            frame = blend_frames(old, new, progress, kind,
                                 get_theme("midnight"))
            assert len(frame) == len(new)
            assert all(line.cell_len == 80 for line in frame)
        assert "\n".join(line.plain for line in
                         blend_frames(old, new, 1.0, kind,
                                      get_theme("midnight"))) == \
            "\n".join(line.plain for line in new)
    glow = reveal_glow(old, new, 0.0, get_theme("midnight"))
    assert len(glow) == len(new)


def test_space_and_arrows_walk_builds_before_changing_slides() -> None:
    root, app, _ = _app(FOUR_SLIDES)
    try:
        assert app._steps_for(0) == 3
        assert "• one" not in _text(app)
        app.handle("space")
        assert app.index == 0 and "• one" in _text(app)
        app.handle("right")
        assert app.index == 0 and "• two" in _text(app)
        app.handle("left")
        assert app.index == 0 and "• two" not in _text(app)
        app.handle("space")
        app.handle("space")
        app.handle("space")
        assert app.index == 1, "extra spaces should move to the next slide"
        root.cleanup()
    except Exception:
        root.cleanup()
        raise


def test_compare_any_slides_with_independent_focused_panes() -> None:
    root, app, _ = _app(FOUR_SLIDES)
    try:
        app.compare = True
        app.compare_indices = [0, 3]
        app.rebuild()
        frame = _text(app)
        assert "1/4" in frame and "4/4" in frame and "↔" in frame
        assert all(line.cell_len == 80 for line in app.frame())

        app.handle("right")
        assert app.compare_indices == [1, 3]
        app.handle("tab")
        app.handle("left")
        assert app.compare_indices == [1, 2]
        app.handle("x")
        assert app.compare_indices == [2, 1]
        app.handle("tab")  # focus the left pane again
        app.handle("4")
        app.handle("enter")
        assert app.compare_indices == [3, 1]
        app.handle("[")
        assert app.compare_indices == [0, 1]
        assert "1/4" in _text(app) and "2/4" in _text(app)
    finally:
        root.cleanup()


def test_cli_compare_and_dump_step(capsys) -> None:  # noqa: ANN001
    root, _, path = _app(FOUR_SLIDES)
    try:
        base = [sys.executable, "-m", "unveil", str(path), "--size", "80x14"]
        cwd = str(Path(__file__).parent)
        result = subprocess.run(base + ["--dump", "--dump-step", "1"],
                                cwd=cwd, text=True, capture_output=True,
                                check=True)
        assert "• one" in result.stdout
        assert "• two" not in result.stdout
        assert "● 1/3" in result.stdout

        result = subprocess.run(base + ["--dump", "--compare", "2", "4"],
                                cwd=cwd, text=True, capture_output=True,
                                check=True)
        assert "2/4" in result.stdout and "4/4" in result.stdout
        assert "↔" in result.stdout
        assert "alpha text" in result.stdout and "gamma text" in result.stdout
        assert "beta text" not in result.stdout
        assert len(result.stdout.splitlines()) <= 14

        narrow = [sys.executable, "-m", "unveil", str(path), "--dump",
                  "--size", "20x8", "--compare", "1", "2"]
        result = subprocess.run(narrow, cwd=cwd, text=True,
                                capture_output=True, check=False)
        assert result.returncode == 2
        assert "compare needs 40 columns" in result.stderr
    finally:
        capsys.readouterr()
        root.cleanup()


def test_showcase_stays_inside_cell_widths(capsys) -> None:  # noqa: ANN001
    path = Path(__file__).parent / "showcase.md"
    text = path.read_text(encoding="utf-8")
    assert len(parse_deck(text, "showcase").slides) == 56
    for width, height in ((20, 8), (80, 24), (160, 40)):
        assert tui.dump(str(path), size=(width, height),
                        math_engine="unicode") == 0
        out = capsys.readouterr().out
        for line in out.splitlines():
            assert swidth(line) <= width, (width, height, line)
