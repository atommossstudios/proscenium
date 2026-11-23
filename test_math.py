"""Smoke tests for the built-in Unicode maths typesetter."""

from __future__ import annotations

from unveil.math import render_block, render_inline

CASES = [
    r"e^{i\pi} + 1 = 0",
    r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
    r"\sum_{i=1}^{n} i = \frac{n(n+1)}{2}",
    r"\int_{0}^{\infty} e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}",
    r"\left( \frac{a}{b} \right)^{2}",
    r"\sqrt[3]{\frac{x+1}{y-2}}",
    r"\mathbf{A} = \begin{pmatrix} a & b \\ c & d \end{pmatrix}",
    r"\begin{aligned} f(x) &= (x+1)^2 \\ &= x^2 + 2x + 1 \end{aligned}",
    r"\mathbb{R}^n \to \mathbb{C}",
    r"\lim_{x \to 0} \frac{\sin x}{x} = 1",
    r"\begin{cases} x^2 & x \ge 0 \\ -x & x < 0 \end{cases}",
    r"\vec{v} \cdot \vec{w} = \|\vec{v}\| \, \|\vec{w}\| \cos\theta",
    r"\binom{n}{k} = \frac{n!}{k!(n-k)!}",
    r"f'(x) = \frac{d}{dx}\left[ \int_a^x f(t)\,dt \right]",
    r"\boxed{E = mc^2}",
    r"\alpha\beta\gamma \ne \Gamma \Delta \Omega",
    r"\underbrace{a+b}_{n} \overbrace{c+d}^{m}",
]


def test_display_blocks() -> None:
    for src in CASES:
        lines = render_block(src)
        assert lines, src
        assert all(isinstance(line, str) for line in lines), src
        assert any(line.strip() for line in lines), src


def test_inline_rendering() -> None:
    for src in CASES:
        assert render_inline(src).strip(), src


if __name__ == "__main__":
    test_display_blocks()
    test_inline_rendering()
    print("math: ok")
