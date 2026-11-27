"""Frame-level entrance animations for proscenium decks.

The renderer produces finished Rich frames; this module transforms a finished
frame into an intermediate animation frame.  Working at that level keeps wide
glyphs, styled spans and Kitty image placements intact while still allowing
typewriter text, objects sliding in from off-stage, draw-on charts and
centre-out zooms.  Everything is pure and testable, with no terminal access.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Optional, Sequence

from rich.cells import cell_len
from rich.text import Text

from .render import Placement, dim_line
from .theme import Theme

#: Entrance effects.  ``none`` keeps the existing slide-transition behaviour.
ANIMATIONS = (
    "none", "fade", "type", "slide", "slide-right", "rise", "drop",
    "grow", "pop", "draw", "spark",
)

_ANIMATION_ALIASES = {
    "off": "none", "cut": "none", "instant": "none", "hard": "none",
    "typing": "type", "typewriter": "type", "write": "type",
    "keyboard": "type", "keys": "type",
    "fadein": "fade", "fade_in": "fade", "appear": "fade",
    "slidein": "slide", "slide_in": "slide", "glide": "slide",
    "move": "slide", "move_in": "slide", "fly": "slide",
    "slide_left": "slide", "from_left": "slide", "left": "slide",
    "slide_right": "slide-right", "from_right": "slide-right",
    "right": "slide-right",
    "risein": "rise", "rise_in": "rise", "up": "rise", "push": "rise",
    "from_bottom": "rise", "bottom": "rise",
    "dropin": "drop", "drop_in": "drop", "down": "drop",
    "from_top": "drop", "top": "drop",
    "zoomin": "grow", "zoom_in": "grow", "scale": "grow",
    "scale_in": "grow", "expand": "grow", "growin": "grow",
    "bounce": "pop", "popin": "pop", "pop_in": "pop",
    "trace": "draw", "scan": "draw", "drawin": "draw", "line": "draw",
    "sparkle": "spark", "burst": "spark", "twinkle": "spark",
}


def normalize_animation(value: Optional[str]) -> str:
    """Return a canonical animation name, defaulting to ``none``."""

    name = (value or "none").strip().lower().replace(" ", "_")
    name = _ANIMATION_ALIASES.get(name, name)
    return name if name in ANIMATIONS else "none"


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t ** 3
    return 1.0 - (-2.0 * t + 2.0) ** 3 / 2.0


def ease_out_back(t: float) -> float:
    """Slightly overshoot the target, like a spring settling into place."""

    t = max(0.0, min(1.0, t))
    c = 1.70158
    return 1.0 + (c + 1.0) * (t - 1.0) ** 3 + c * (t - 1.0) ** 2


def _blank(width: int, theme: Theme) -> Text:
    return Text(" " * max(0, width), style=theme.on())


def _slice(line: Text, start: int, end: int) -> Text:
    """Slice a Rich line by character index, keeping its style spans."""

    plain = line.plain
    start = max(0, min(len(plain), start))
    end = max(start, min(len(plain), end))
    out = Text(plain[start:end], style=line.style)
    for span in line.spans:
        a = max(span.start, start) - start
        b = min(span.end, end) - start
        if b > a:
            out.stylize(span.style, a, b)
    return out


def _fit(line: Text, width: int, theme: Theme) -> Text:
    """Keep a frame row exactly ``width`` cells wide."""

    if line.cell_len > width:
        line.truncate(width, overflow="crop")
    need = width - line.cell_len
    if need > 0:
        line.append(Text(" " * need, style=theme.on()))
    return line


def _bounds(line: Text) -> tuple[int, int]:
    plain = line.plain
    first = len(plain) - len(plain.lstrip())
    last = len(plain.rstrip())
    return first, max(first, last)


def _changed_rows(old: Sequence[Text], new: Sequence[Text]) -> list[bool]:
    return [i >= len(old) or old[i].plain != new[i].plain
            for i in range(len(new))]


def _typewriter(lines: Sequence[Text], progress: float, theme: Theme,
                width: int, changed: Optional[list[bool]]) -> list[Text]:
    """Reveal characters left to right, top to bottom, with a blinking head."""

    targets = [i for i in range(len(lines))
               if changed is None or changed[i]]
    total = 0
    for i in targets:
        first, last = _bounds(lines[i])
        total += max(0, last - first)
    budget = int(math.ceil(max(0.0, min(1.0, progress)) * total))
    out: list[Text] = []
    for i, line in enumerate(lines):
        if changed is not None and not changed[i]:
            out.append(_fit(line.copy(), width, theme))
            continue
        first, last = _bounds(line)
        room = max(0, last - first)
        take = min(room, budget)
        budget -= take
        piece = _slice(line, 0, first + take)
        # Only the row currently being typed carries the cursor.  Without the
        # `take` guard, every later row would sprout a stray block when the
        # character budget ran out mid-frame.
        cursor = (take < room and (take > 0 or (targets and i == targets[0]))
                  and (int(progress * 12) % 2 == 0 or progress >= 1.0))
        if cursor:
            piece.append(Text("▍", style=f"bold {theme.accent}"))
        out.append(_fit(piece, width, theme))
    return out


def _shift_horizontal(line: Text, dx: int, width: int, theme: Theme) -> Text:
    if dx > 0:
        out = Text(" " * dx, style=theme.on())
        out.append_text(line.copy())
    elif dx < 0:
        out = _slice(line, -dx, len(line.plain))
    else:
        out = line.copy()
    return _fit(out, width, theme)


def _slide(lines: Sequence[Text], progress: float, theme: Theme,
           width: int, height: int, direction: str,
           changed: Optional[list[bool]]) -> list[Text]:
    """Move the frame in from a side or edge with cubic easing."""

    p = ease_out_cubic(progress)
    dx = dy = 0
    if direction == "slide":
        dx = -int(round((1.0 - p) * width))
    elif direction == "slide-right":
        dx = int(round((1.0 - p) * width))
    elif direction == "rise":
        dy = int(round((1.0 - p) * height))
    elif direction == "drop":
        dy = -int(round((1.0 - p) * height))
    source = [line if i < len(lines) else _blank(width, theme)
              for i, line in enumerate(lines)]
    while len(source) < height:
        source.append(_blank(width, theme))
    out: list[Text] = []
    for y in range(height):
        sy = y - dy
        if not 0 <= sy < len(source):
            out.append(_blank(width, theme))
            continue
        if (dx or dy) and (changed is None or
                           (sy < len(changed) and changed[sy])):
            out.append(_shift_horizontal(source[sy], dx, width, theme))
        else:
            out.append(_fit(source[sy].copy(), width, theme))
    return out


def _zoom(lines: Sequence[Text], progress: float, theme: Theme,
          width: int, height: int, spring: bool,
          changed: Optional[list[bool]]) -> list[Text]:
    """Expand a central window outward, like a camera pushing in."""

    p = min(1.0, max(0.0, ease_out_back(progress) if spring
                     else ease_out_cubic(progress)))
    half_h = max(1, int(round(p * height / 2)))
    half_w = max(1, int(round(p * width / 2)))
    cy, cx = (height - 1) / 2, (width - 1) / 2
    top, bottom = math.floor(cy - half_h), math.ceil(cy + half_h)
    left, right = math.floor(cx - half_w), math.ceil(cx + half_w)
    out: list[Text] = []
    for y in range(height):
        if not top <= y <= bottom or (changed is not None
                                      and not changed[min(y, len(lines) - 1)]):
            out.append(_blank(width, theme))
            continue
        line = lines[y] if y < len(lines) else _blank(width, theme)
        piece = _slice(line, left, right + 1)
        if spring and 0.55 < progress < 0.85 and line.cell_len:
            piece.stylize(f"on {theme.accent2}")
        out.append(_fit(piece, width, theme))
    return out


def _draw(lines: Sequence[Text], progress: float, theme: Theme,
          width: int, changed: Optional[list[bool]]) -> list[Text]:
    """Sweep a bright drawing head across each row, left to right."""

    p = ease_out_cubic(progress)
    edge = int(round(p * width))
    out: list[Text] = []
    for i, line in enumerate(lines):
        if changed is not None and not changed[i]:
            out.append(_fit(line.copy(), width, theme))
            continue
        piece = _slice(line, 0, edge)
        if 0 < edge < width and line.cell_len:
            piece.append(Text("▏", style=f"bold {theme.accent2}"))
        out.append(_fit(piece, width, theme))
    return out


def _spark(lines: Sequence[Text], progress: float, theme: Theme,
           width: int, changed: Optional[list[bool]]) -> list[Text]:
    """Pop individual cells in with a deterministic, shimmering order."""

    p = ease_in_out_cubic(progress)
    out: list[Text] = []
    for y, line in enumerate(lines):
        if changed is not None and not changed[y]:
            out.append(_fit(line.copy(), width, theme))
            continue
        piece = Text(style=theme.on())
        x = 0
        pos = 0
        while pos < len(line.plain) and x < width:
            ch = line.plain[pos]
            size = max(1, cell_len(ch))
            threshold = ((y * 47 + x * 61 + 17) % 101) / 101.0
            if threshold < p:
                cell = _slice(line, pos, pos + 1)
                if p - threshold < 0.10:
                    cell.stylize(f"on {theme.accent2}")
                piece.append_text(cell)
            else:
                piece.append(Text(" " * size, style=theme.on()))
            pos += 1
            x += size
        out.append(_fit(piece, width, theme))
    return out


def _placement_frame(kind: str, progress: float, theme: Theme,
                     width: int, height: int,
                     placements: Sequence[Placement],
                     old_placements: Sequence[Placement],
                     reveal: bool) -> list[Placement]:
    """Move, grow or delay Kitty placements to match the text effect."""

    p = ease_out_cubic(progress)
    if not placements:
        return []
    if kind == "none":
        return list(placements)
    if reveal and progress < 0.35 and old_placements:
        return list(old_placements)
    if kind == "fade":
        return list(placements) if p >= 0.45 else []
    if kind == "type":
        return list(placements) if p >= 0.75 else []
    if kind == "draw":
        if p < 0.35:
            return []
        return [replace(item, cols=max(1, int(item.cols * p)))
                for item in placements]
    if kind == "spark":
        return list(placements) if p >= 0.55 else []
    if kind in ("grow", "pop"):
        scale = min(1.0, max(0.05, ease_out_back(progress) if kind == "pop"
                             else p))
        out = []
        for item in placements:
            cols = max(1, round(item.cols * scale))
            rows = max(1, round(item.rows * scale))
            out.append(replace(
                item, cols=cols, rows=rows,
                col=item.col + (item.cols - cols) // 2,
                line=item.line + (item.rows - rows) // 2,
            ))
        return out
    dx = dy = 0
    if kind == "slide":
        dx = -int(round((1.0 - p) * width))
    elif kind == "slide-right":
        dx = int(round((1.0 - p) * width))
    elif kind == "rise":
        dy = int(round((1.0 - p) * height))
    elif kind == "drop":
        dy = -int(round((1.0 - p) * height))
    out = []
    for item in placements:
        col, line = item.col + dx, item.line + dy
        if col + item.cols <= 0 or col >= width \
                or line + item.rows <= 0 or line >= height:
            continue
        out.append(replace(item, col=col, line=line))
    return out


def animate_frame(old: Sequence[Text], new: Sequence[Text], progress: float,
                  kind: str, theme: Theme, width: int, height: int,
                  old_placements: Optional[Sequence[Placement]] = None,
                  placements: Optional[Sequence[Placement]] = None,
                  reveal: bool = False) -> tuple[list[Text], list[Placement]]:
    """Return an intermediate frame for *kind* at ``progress`` (0…1).

    With ``reveal=True`` only rows that changed since *old* animate in; the
    rest of the stage stays put.  That is what makes a build feel like new
    objects arriving rather than the whole slide being replayed.
    """

    kind = normalize_animation(kind)
    fresh = [line.copy() for line in new]
    fresh_placements = list(placements or [])
    t = max(0.0, min(1.0, progress))
    if kind == "none" or t >= 1.0:
        return [_fit(line, width, theme) for line in fresh], fresh_placements
    changed = _changed_rows(old, new) if reveal else None
    old_placements = list(old_placements or [])

    if kind == "fade":
        lines = []
        for i, line in enumerate(fresh):
            if changed is None or changed[i]:
                lines.append(_fit(
                    dim_line(line, 1.0 - ease_out_cubic(t), theme.bg),
                    width, theme))
            else:
                lines.append(_fit(line, width, theme))
    elif kind == "type":
        lines = _typewriter(fresh, t, theme, width, changed)
    elif kind in ("slide", "slide-right", "rise", "drop"):
        lines = _slide(fresh, t, theme, width, height, kind, changed)
    elif kind in ("grow", "pop"):
        lines = _zoom(fresh, t, theme, width, height, kind == "pop", changed)
    elif kind == "draw":
        lines = _draw(fresh, t, theme, width, changed)
    else:  # spark
        lines = _spark(fresh, t, theme, width, changed)

    shaped = _placement_frame(kind, t, theme, width, height,
                              fresh_placements, old_placements, reveal)
    return lines, shaped
