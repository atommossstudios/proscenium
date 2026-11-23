"""Command line entry point for unveil."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from . import __version__
from .md import parse_deck
from .theme import get_theme, theme_names
from . import tui


def _size(value: str) -> tuple[int, int]:
    try:
        w, h = value.lower().split("x", 1)
        return max(20, int(w)), max(8, int(h))
    except Exception as exc:  # noqa: BLE001
        raise argparse.ArgumentTypeError("size must look like 100x30") from exc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="unveil",
        description="A terminal-first markdown slide deck with real math.",
        epilog="slide break: a line containing ---    math: $inline$ and $$display$$",
    )
    p.add_argument("deck", nargs="?", help="markdown file to present")
    p.add_argument("--theme", choices=theme_names(), help="color theme")
    p.add_argument("--list", action="store_true", help="list slides and exit")
    p.add_argument("--dump", action="store_true",
                   help="print every slide as plain text and exit "
                        "(automatic when stdin or stdout is not a TTY)")
    p.add_argument("--size", type=_size, metavar="WxH",
                   help="dump-only size, minimum 20x8 (default 100x30)")
    p.add_argument("--no-footer", action="store_true",
                   help="hide the title, hints and progress bar")
    p.add_argument("--math-upright", action="store_true",
                   help="use upright math letters (if italic glyphs are missing)")
    p.add_argument("--math-engine", choices=("auto", "latex", "unicode"),
                   default=None,
                   help="display-math renderer: auto (LaTeX when available), "
                        "latex (falls back if unavailable), or unicode")
    p.add_argument("--width", metavar="WIDTH",
                   help="content width: full (default), 92, a percentage, "
                        "or a cell count")
    fit = p.add_mutually_exclusive_group()
    fit.add_argument("--fit", action="store_true", default=None,
                     help="squeeze spacing and visuals to fit the terminal")
    fit.add_argument("--no-fit", action="store_false", dest="fit",
                     help="keep authored spacing even when content scrolls")
    p.add_argument("--transition", metavar="NAME",
                   help="slide transition: fade, wipe, rise, iris, blinds, "
                        "dissolve or none")
    p.add_argument("--transition-time", metavar="SECONDS",
                   help="transition duration in seconds (default 0.22)")
    p.add_argument("--compare", nargs=2, type=int, metavar=("A", "B"),
                   help="compare two slides by number (opens compare view, "
                        "or dumps just that comparison with --dump)")
    p.add_argument("--dump-step", type=int, default=None, metavar="N",
                   help="reveal step to dump (default: show every build)")
    p.add_argument("--version", action="version", version=f"unveil {__version__}")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.deck:
        build_parser().print_help()
        return 2
    path = args.deck
    if not os.path.exists(path):
        sys.stderr.write(f"unveil: no such file: {path}\n")
        return 1
    if not os.path.isfile(path):
        sys.stderr.write(f"unveil: not a file: {path}\n")
        return 1

    if args.list:
        with open(path, "r", encoding="utf-8") as fh:
            deck = parse_deck(fh.read(), os.path.splitext(os.path.basename(path))[0])
        for i, slide in enumerate(deck.slides, 1):
            print(f"{i:>3}  {slide.title}")
        return 0

    footer = not args.no_footer
    math_italic = False if args.math_upright else None
    compare = None
    if args.compare:
        compare = (args.compare[0] - 1, args.compare[1] - 1)
    if args.dump:
        return tui.dump(path, args.theme, footer, args.size, math_italic,
                        args.math_engine, width_setting=args.width, fit=args.fit,
                        step=args.dump_step, compare=compare,
                        transition=args.transition,
                        transition_time=args.transition_time)
    return tui.run(path, args.theme, footer, math_italic, args.math_engine,
                   args.size, width_setting=args.width, fit=args.fit,
                   transition=args.transition,
                   transition_time=args.transition_time, compare=compare)
