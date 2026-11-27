"""Tests for character-level and object-level entrance animations."""

from __future__ import annotations

from rich.text import Text

from proscenium.anim import (ANIMATIONS, animate_frame, ease_in_out_cubic,
                             ease_out_back, ease_out_cubic,
                             normalize_animation)
from proscenium.cli import build_parser
from proscenium.md import parse_deck
from proscenium.render import Placement
from proscenium.theme import get_theme

THEME = get_theme("midnight")


def test_normalize_animation() -> None:
    assert normalize_animation("typewriter") == "type"
    assert normalize_animation("glide") == "slide"
    assert normalize_animation("slide_right") == "slide-right"
    assert normalize_animation("from bottom") == "rise"
    assert normalize_animation("zoomin") == "grow"
    assert normalize_animation("nonsense") == "none"
    assert normalize_animation(None) == "none"
    for name in ANIMATIONS:
        assert normalize_animation(name) == name


def test_easing_stays_sane() -> None:
    for fn in (ease_out_cubic, ease_in_out_cubic, ease_out_back):
        assert abs(fn(0)) < 1e-9
        assert abs(fn(1) - 1) < 1e-9
        assert fn(-1) == 0 or fn(-1) >= 0
    assert ease_out_back(0.8) > 1.0  # the spring overshoots
    assert ease_out_cubic(0.5) > ease_in_out_cubic(0.5)


def test_typewriter_reveals_with_fixed_width() -> None:
    old = [Text(" " * 13), Text("")]
    new = [Text("  Hello world"), Text("")]
    seen: list[str] = []
    for progress in (0.0, 0.25, 0.5, 0.75, 1.0):
        lines, _ = animate_frame(old, new, progress, "type", THEME, 13, 2)
        assert all(line.cell_len == 13 for line in lines)
        seen.append(lines[0].plain)
    assert "▍" in "".join(seen[:-1])
    assert seen[-1] == "  Hello world"
    assert seen[0].strip() in ("", "▍")


def test_typewriter_keeps_style_spans() -> None:
    text = Text("Hello world")
    text.stylize("bold", 6, 11)
    lines, _ = animate_frame([Text(" " * 11)], [text], 1.0, "type",
                             THEME, 11, 1)
    spans = [(span.start, span.end) for span in lines[0].spans]
    assert (6, 11) in spans


def test_slide_moves_objects_and_placements() -> None:
    item = Placement(line=2, col=3, path="x.png", cols=4, rows=2)
    old = [Text(" " * 20) for _ in range(10)]
    new = [Text(" " * 20) for _ in range(10)]
    early, places = animate_frame(old, new, 0.0, "slide", THEME, 20, 10,
                                  placements=[item])
    assert all(line.cell_len == 20 for line in early)
    assert places == []
    final, places = animate_frame(old, new, 1.0, "slide", THEME, 20, 10,
                                  placements=[item])
    assert final == new
    assert places == [item]


def test_rise_drop_and_grow_place_images() -> None:
    item = Placement(2, 3, "x.png", 4, 2)
    frame = [Text(" " * 20) for _ in range(10)]
    for kind in ("rise", "drop"):
        _, early = animate_frame(frame, frame, 0.0, kind, THEME, 20, 10,
                                 placements=[item])
        assert early == []
    _, grown = animate_frame(frame, frame, 0.2, "grow", THEME, 20, 10,
                             placements=[item])
    assert grown and grown[0].cols < item.cols
    assert grown[0].rows < item.rows
    _, done = animate_frame(frame, frame, 1.0, "grow", THEME, 20, 10,
                            placements=[item])
    assert done == [item]


def test_draw_and_spark_are_progressive() -> None:
    line = Text("abcdefgh")
    old = [Text(" " * 8)]
    new = [line]
    partial, _ = animate_frame(old, new, 0.5, "draw", THEME, 8, 1)
    assert partial[0].cell_len == 8
    assert "▏" in partial[0].plain
    full, _ = animate_frame(old, new, 1.0, "draw", THEME, 8, 1)
    assert full[0].plain == "abcdefgh"
    first, _ = animate_frame(old, new, 0.6, "spark", THEME, 8, 1)
    second, _ = animate_frame(old, new, 0.6, "spark", THEME, 8, 1)
    assert [x.plain for x in first] == [x.plain for x in second]
    done, _ = animate_frame(old, new, 1.0, "spark", THEME, 8, 1)
    assert done[0].plain == "abcdefgh"


def test_reveal_animation_only_touches_new_rows() -> None:
    old = [Text("alpha"), Text("beta")]
    new = [Text("alpha"), Text("GAMMA")]
    lines, _ = animate_frame(old, new, 0.3, "type", THEME, 5, 2,
                             reveal=True)
    assert lines[0].plain == "alpha"
    assert lines[1].plain != "beta"


def test_none_animation_passes_frame_through() -> None:
    old = [Text("old")]
    new = [Text("new")]
    item = Placement(0, 0, "x.png", 1, 1)
    lines, places = animate_frame(old, new, 0.4, "none", THEME, 3, 1,
                                  placements=[item])
    assert lines == new
    assert places == [item]


def test_animation_directives_reach_slide_options() -> None:
    for src, expected in (
        ("@anim type\n\n# Hi\n", "type"),
        ("@animation slide\n\n# Hi\n", "slide"),
        ("@typewriter\n\n# Hi\n", "type"),
        ("@glide\n\n# Hi\n", "slide"),
        ("@slide animation=grow\n\n# Hi\n", "grow"),
    ):
        deck = parse_deck(src, "t")
        assert deck.slides[0].options.get("animation") == expected, src
    assert parse_deck("---\nanimation: spark\n---\n\n# Hi\n", "t").meta[
        "animation"] == "spark"
    deck = parse_deck("@glide 0.9\n\n# Hi\n", "t")
    assert deck.slides[0].options["animation"] == "slide"
    assert deck.slides[0].options["animation_time"] == "0.9"


def test_cli_exposes_animation_flags() -> None:
    args = build_parser().parse_args(
        ["deck.md", "--animation", "type", "--animation-time", "0.9"])
    assert args.animation == "type"
    assert args.animation_time == "0.9"


def test_app_starts_entrance_animation(tmp_path) -> None:  # noqa: ANN001
    from proscenium.tui import App

    deck = tmp_path / "deck.md"
    deck.write_text("@typewriter\n\n# Hi\n", encoding="utf-8")
    app = App(str(deck), size=(80, 24), graphics=False, math_engine="unicode")
    assert app._animation_for(0) == "type"
    app.start_transition([Text(" " * 80)] * 24, [])
    assert app.anim is not None
    assert app.anim["mode"] == "animation"
    assert app.anim["kind"] == "type"
