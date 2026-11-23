"""Smoke tests for the LaTeX display-math pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

from unveil import latex
from unveil.md import parse_deck
from unveil.render import Renderer
from unveil.theme import get_theme


def main() -> int:
    if not latex.available():
        print("latex: skipped (tectonic/pdftoppm not installed)")
        return 0

    img = latex.render(r"E = mc^2", "#d5dbe6", "#0b0e14")
    assert img is not None, "simple formula did not compile"
    assert img.width > 0 and img.height > 0
    assert not latex.png_has_white_edge(Path(img.path)), "white edge left in PNG"
    print(f"simple: {img.width}x{img.height}")

    long = (
        r"\int_{-\infty}^{\infty}\int_{-\infty}^{\infty} f(x,y)\,"
        r"e^{-2\pi i(ux+vy)}\,dx\,dy = F(u,v) = G(u) + H(v) + K(u,v)"
    )
    wrapped = latex._wrap_source(long, 60)
    assert wrapped and r"\begin{gathered}" in wrapped
    print("wrap: ok")

    deck = parse_deck(
        "---\ntitle: t\n---\n\n# t\n\n$$\\boxed{E = mc^2}$$\n\n"
        "$$\\begin{aligned}a &= b \\\\ c &= d\\end{aligned}$$\n",
        "t",
    )
    renderer = Renderer(
        deck, get_theme("midnight"), 56, 30, True,
        cell_size=(20, 45), graphics=True, math_engine="latex",
    )
    lines = renderer.render_slide(0)
    assert len(lines) == 30
    assert len(renderer.frame_placements) == 2, renderer.frame_placements
    print("renderer: ok", [(p.line, p.col, p.cols, p.rows)
                           for p in renderer.frame_placements])
    return 0


def test_latex_pipeline() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
