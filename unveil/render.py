"""Slide layout and Rich rendering for unveil."""

from __future__ import annotations

import io
import math as _math
import re
import time
from dataclasses import dataclass, replace
from typing import Optional

from rich import box
from rich.color import Color
from rich.console import Console
from rich.panel import Panel
from rich.segment import Segment
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Span, Text

from . import images
from . import latex as tex
from . import math as mdm
from .md import (Block, Callout, Chart, Code, Columns, Deck, Frame, Heading,
                 Image, ListBlock, ListItem, MathBlock, Para, Quote, Rule,
                 Slide, Toc, Table as MdTable, parse_inline, plain_inline,
                 _reveal_number)
from .theme import Theme, mix, override_theme


@dataclass(frozen=True)
class Placement:
    """A raster formula to paint into the finished text frame.

    ``line`` and ``col`` are absolute, zero-based screen coordinates.
    """

    line: int
    col: int
    path: str
    cols: int
    rows: int


@dataclass(frozen=True)
class PendingPlacement:
    """A raster image waiting to be located in the composed frame.

    A private-use marker occupies the image's first cell while the frame is
    being assembled.  Scanning the finished text for that marker handles
    centering, wrapping, indentation and nesting for free.  Used by both
    LaTeX formulas and deck pictures.
    """

    marker: str
    path: str
    cols: int
    rows: int


# A clean presentation table: a hairline under the header and a soft bottom
# rule, with no vertical strokes or stubby corners.
PRESENTATION_TABLE = box.Box(
    "    \n"
    "    \n"
    " ── \n"
    "    \n"
    "    \n"
    "    \n"
    "    \n"
    " ── \n"
)

#: Equation box styles.  ``None`` means no drawn frame, or a custom frame
#: handled outside Rich (``card``).
EQ_BOXES: dict[str, object] = {
    "card": None,
    "clean": None,
    "rounded": box.ROUNDED,
    "square": box.SQUARE,
    "double": box.DOUBLE,
    "heavy": box.HEAVY,
    "simple": box.SIMPLE,
    "minimal": box.MINIMAL,
    "markdown": box.MARKDOWN,
    "accent": box.ROUNDED,
    "presentation": PRESENTATION_TABLE,
    "none": None,
    "plain": None,
}

#: Table styles: (Rich box, draw row separators).
TABLE_STYLES: dict[str, tuple[object, bool]] = {
    "rounded": (box.ROUNDED, False),
    "default": (box.ROUNDED, False),
    "presentation": (PRESENTATION_TABLE, False),
    "clean": (PRESENTATION_TABLE, False),
    "opencode": (box.MARKDOWN, False),
    "github": (box.MARKDOWN, False),
    "markdown": (box.MARKDOWN, False),
    "square": (box.SQUARE, False),
    "grid": (box.SQUARE, True),
    "double": (box.DOUBLE, False),
    "heavy": (box.HEAVY, False),
    "minimal": (box.MINIMAL, False),
    "simple": (box.SIMPLE, False),
    "borderless": (None, False),
    "none": (None, False),
}

#: Unicode eighth-block characters, used for exact bar endings.
_BAR_FRACTIONS = " ▏▎▍▌▋▊▉"

#: Braille dot bits, indexed by [sub-row][sub-column] inside one cell.
#: Braille gives a 2x4 dot grid per cell, enough for a round ring in text.
_BRAILLE_BITS = (
    (0x01, 0x08),  # dots 1, 4
    (0x02, 0x10),  # dots 2, 5
    (0x04, 0x20),  # dots 3, 6
    (0x40, 0x80),  # dots 7, 8
)

CALLOUT_STYLES: dict[str, tuple[str, str]] = {
    "note": ("•", "accent"),
    "info": ("•", "accent"),
    "tip": ("+", "good"),
    "hint": ("+", "good"),
    "success": ("✓", "good"),
    "warning": ("!", "accent2"),
    "caution": ("!", "accent2"),
    "danger": ("×", "bad"),
    "error": ("×", "bad"),
    "quote": ("❝", "dim"),
}


def _as_bool(value: Optional[str], default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in ("false", "no", "off", "0")


def _as_int(value: Optional[str], default: int) -> int:
    try:
        return max(0, int(str(value)))
    except (TypeError, ValueError):
        return default


def _as_float(value: Optional[str], default: float) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


#: Width settings cycled by the ``w`` key.  ``full`` is the default; the
#: others are useful on very wide terminals where a 92-cell column is narrow.
WIDTH_MODES = ("full", "92", "80%", "60%")


def _content_width(setting: Optional[str], terminal: int) -> int:
    """Resolve a width setting to a content width for this terminal."""
    raw = (setting or "full").strip().lower()
    margin = 1 if terminal >= 24 else 0
    room = max(16, terminal - 2 * margin)
    if raw in ("", "full", "auto", "fill", "max", "wide"):
        return room
    if raw in ("classic", "default", "92"):
        side = max(2, (terminal - 92) // 2)
        return max(16, min(terminal - 2 * side, 92))
    if raw.endswith("%"):
        try:
            pct = float(raw[:-1])
        except ValueError:
            return room
        return max(16, min(room, int(terminal * max(1, min(100, pct)) / 100)))
    try:
        wanted = int(float(raw))
    except ValueError:
        return room
    return max(16, min(room, wanted))


#: Slide-transition effects, plus the spellings accepted in deck source.
TRANSITIONS = ("cut", "fade", "wipe", "rise", "iris", "blinds", "dissolve")
_TRANSITION_ALIASES = {
    "none": "cut", "off": "cut", "instant": "cut", "hard": "cut",
    "crossfade": "fade", "veil": "fade", "dim": "fade", "soft": "fade",
    "down": "wipe", "top": "wipe", "cover": "wipe",
    "up": "rise", "bottom": "rise", "push": "rise",
    "center": "iris", "circle": "iris", "zoom": "iris",
    "rows": "blinds", "stripes": "blinds", "venetian": "blinds",
    "noise": "dissolve", "sparkle": "dissolve", "random": "dissolve",
}


def normalize_transition(value: Optional[str]) -> str:
    name = (value or "fade").strip().lower()
    name = _TRANSITION_ALIASES.get(name, name)
    return name if name in TRANSITIONS else "fade"


def _rgb(color: Optional[Color]) -> Optional[tuple[int, int, int]]:
    if color is None:
        return None
    triplet = color.triplet
    if triplet is None:
        return None
    return triplet.red, triplet.green, triplet.blue


def _toward(color: Optional[Color], background: str,
            amount: float) -> Optional[Color]:
    """Mix a Rich colour toward *background* by *amount* (0…1)."""
    source = _rgb(color)
    if source is None or amount <= 0:
        return color
    target = _rgb(Color.parse(background)) or (0, 0, 0)
    values = [round(a + (b - a) * amount) for a, b in zip(source, target)]
    return Color.parse("#" + "".join(f"{max(0, min(255, v)):02x}"
                                     for v in values))


def _dim_style(style: object, amount: float, background: str) -> object:
    if style is None or amount <= 0:
        return style
    if isinstance(style, str):
        try:
            style = Style.parse(style)
        except Exception:  # noqa: BLE001 - keep an unparseable style as-is
            return style
    if not isinstance(style, Style):
        return style
    flags = ("bold", "italic", "underline", "underline2", "dim", "reverse",
             "blink", "blink2", "conceal", "strike", "frame", "encircle",
             "overline")
    opts = {name: getattr(style, name) for name in flags}
    opts.update(color=_toward(style.color, background, amount),
                bgcolor=_toward(style.bgcolor, background, amount),
                link=style.link)
    return Style(**opts)


def dim_line(line: Text, amount: float, background: str) -> Text:
    """Fade one rendered row toward the theme background."""
    if amount <= 0:
        return line
    out = line.copy()
    if out.style is not None:
        out.style = _dim_style(out.style, amount, background)
    out.spans = [Span(span.start, span.end,
                      _dim_style(span.style, amount, background))
                 for span in out.spans]
    return out


def blend_frames(old: list[Text], new: list[Text], progress: float,
                 kind: str, theme: Theme) -> list[Text]:
    """Blend two finished frames into one transition frame.

    ``progress`` runs 0 → 1.  At 0 the old frame is returned, at 1 the new
    frame.  All effects work on whole rows, so wide glyphs, Kitty math and
    styled spans survive untouched.
    """

    t = max(0.0, min(1.0, progress))
    kind = normalize_transition(kind)
    if kind == "cut":
        return [line.copy() for line in (new if t >= 1 else old)]
    total = max(len(old), len(new))
    bg = theme.bg

    def rows(y: int) -> tuple[Text, Text]:
        blank = Text(" " * max(len(old[0].plain) if old else 0,
                               len(new[0].plain) if new else 0),
                     style=theme.on())
        before = old[y] if y < len(old) else blank
        after = new[y] if y < len(new) else blank
        return before, after

    if kind == "fade":
        if t < 0.5:
            strength = t * 2
            return [dim_line(line, strength, bg)
                    for line in (rows(y)[0] for y in range(total))]
        strength = (1 - t) * 2
        return [dim_line(line, strength, bg)
                for line in (rows(y)[1] for y in range(total))]

    if kind == "wipe":
        edge = round(t * total)
        return [rows(y)[1] if y < edge else rows(y)[0]
                for y in range(total)]
    if kind == "rise":
        edge = round(t * total)
        return [rows(y)[1] if y >= total - edge else rows(y)[0]
                for y in range(total)]
    if kind == "iris":
        radius = t * (total / 2 + 1)
        middle = (total - 1) / 2
        return [rows(y)[1] if abs(y - middle) <= radius else rows(y)[0]
                for y in range(total)]
    if kind == "blinds":
        band_h = 3
        out: list[Text] = []
        for y in range(total):
            band = y // band_h
            offset = 0.28 if band % 2 else 0.0
            local = max(0.0, min(1.0, (t - offset) / (1 - offset)))
            within = y - band * band_h
            edge = round(local * min(band_h, total - band * band_h))
            out.append(rows(y)[1] if within < edge else rows(y)[0])
        return out
    # dissolve
    return [rows(y)[1] if ((y * 37 + 19) % 101) / 101 < t else rows(y)[0]
            for y in range(total)]


def reveal_glow(old: list[Text], new: list[Text], progress: float,
                theme: Theme) -> list[Text]:
    """Highlight the rows a reveal step just added, then let the glow fade."""

    t = max(0.0, min(1.0, progress))
    out = [line.copy() for line in new]
    if t >= 1:
        return out
    shade = mix(theme.bg, theme.accent, 0.40 * (1 - t))
    for y, line in enumerate(out):
        before = old[y].plain if y < len(old) else ""
        if before != line.plain and line.cell_len:
            line.stylize(f"on {shade}", 0, len(line))
    return out


def _ellipsis(text: str, width: int) -> str:
    if width <= 0:
        return ""
    text = str(text)
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return text[:width - 1] + "…"


def _cellfit(text: str, width: int) -> str:
    """Ellipsise *text* to a cell budget without splitting wide glyphs."""

    if width <= 0:
        return ""
    text = str(text)
    if mdm.swidth(text) <= width:
        return text
    if width == 1:
        return "…"
    out = ""
    for ch in text:
        if mdm.swidth(out + ch) > width - 1:
            break
        out += ch
    return out + "…"


def gradient_text(s: str, c1: str, c2: str, bold: bool = True) -> Text:
    t = Text()
    denom = max(1, len(s) - 1)
    for i, ch in enumerate(s):
        color = mix(c1, c2, i / denom)
        t.append(ch, f"bold {color}" if bold else color)
    return t


#: Key, description, compact key, compact description.  The compact forms
#: keep the help overlay readable down to 20-column terminals.
HELP_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("→  space  j", "reveal / next slide", "→ sp j", "next"),
    ("←  k  p", "reveal back / previous", "← k p", "back"),
    ("g  G  [  ]", "first / last / ±10 slides", "g G [ ]", "jump"),
    ("1…9  ⏎", "jump to slide", "1-9 ⏎", "goto"),
    ("o", "slide overview", "o", "list"),
    ("s", "speaker notes", "s", "notes"),
    ("J K  d u", "scroll / half-page", "J K d u", "scroll"),
    ("w", "cycle content width", "w", "width"),
    ("f", "toggle fit to terminal", "f", "fit"),
    ("c", "compare two slides", "c", "cmp"),
    ("tab", "switch compare pane", "tab", "pane"),
    ("x", "swap compare panes", "x", "swap"),
    ("a", "toggle transitions", "a", "anim"),
    ("b", "blank the screen", "b", "blank"),
    ("t", "cycle theme", "t", "theme"),
    ("r", "reload the file", "r", "reload"),
    ("q", "quit", "q", "quit"),
)


def _help_layout(width: int, height: int
                 ) -> tuple[int, int, int, int, bool, bool]:
    """Return panel width, columns, rows, pages, pager hint and full labels."""

    panel_w = max(10, min(width - 2, 68))
    inner = max(4, panel_w - 2)
    content_rows = max(1, height - 2)
    cols = 2 if inner >= 30 and height < 20 else 1
    full = cols == 1 and inner >= 44 and content_rows >= len(HELP_ROWS)
    if full:
        return panel_w, cols, content_rows, 1, False, True
    pages = max(1, _math.ceil(len(HELP_ROWS) / (content_rows * cols)))
    hint = pages > 1
    key_rows = max(1, content_rows - 1) if hint else content_rows
    pages = max(1, _math.ceil(len(HELP_ROWS) / (key_rows * cols)))
    return panel_w, cols, content_rows, pages, hint, False


def help_page_count(width: int, height: int) -> int:
    """Number of help pages needed at the given terminal size."""

    return _help_layout(width, height)[3]


def _help_border(left: str, right: str, label: str, inner: int,
                 border_style: str, fill_style: str) -> Text:
    line = Text(left, style=border_style)
    text = f" {label} " if label else ""
    if mdm.swidth(text) > inner:
        text = " " + _cellfit(label, max(0, inner - 2)) + " "
    pad = max(0, inner - mdm.swidth(text))
    line.append("─" * (pad // 2), style=fill_style)
    if text:
        line.append(text, f"bold {border_style}")
    line.append("─" * (pad - pad // 2), style=fill_style)
    line.append(right, style=border_style)
    return line


def segs_to_text(segs: list[Segment]) -> Text:
    t = Text()
    for seg in segs:
        if seg.text:
            t.append(seg.text, seg.style)
    return t


class Canvas:
    """Tiny cell canvas for overlay screens."""

    def __init__(self, width: int, height: int, bg: str):
        self.width = width
        self.height = height
        self.bg = bg
        self.cells: list[list[Optional[tuple[str, str]]]] = [
            [(" ", bg) for _ in range(width)] for _ in range(height)
        ]

    def put(self, x: int, y: int, s: str, style: str = "") -> None:
        if not (0 <= y < self.height):
            return
        for ch in s:
            w = mdm.swidth(ch)
            if x >= self.width:
                break
            if x >= 0:
                self.cells[y][x] = (ch, style)
                for k in range(1, w):
                    if x + k < self.width:
                        self.cells[y][x + k] = None
            x += w

    def to_lines(self) -> list[Text]:
        out: list[Text] = []
        for row in self.cells:
            t = Text()
            run: list[str] = []
            cur: Optional[str] = None
            for cell in row:
                if cell is None:
                    continue
                ch, style = cell
                if style != cur:
                    if run:
                        t.append("".join(run), cur)
                    run = [ch]
                    cur = style
                else:
                    run.append(ch)
            if run:
                t.append("".join(run), cur)
            out.append(t)
        return out


class Renderer:
    def __init__(self, deck: Deck, theme: Theme, width: int, height: int,
                 footer: bool = True, math_italic: Optional[bool] = None,
                 cell_size: tuple[int, int] = (10, 20),
                 graphics: bool = False, math_engine: str = "auto",
                 started: Optional[float] = None,
                 base_dir: Optional[str] = None,
                 dump: bool = False,
                 width_setting: Optional[str] = None,
                 fit: Optional[bool] = None,
                 min_width: int = 20):
        self.deck = deck
        self.base_dir = base_dir
        self.theme = override_theme(theme, deck.meta)
        self.started = time.monotonic() if started is None else started
        self.clock = _as_bool(deck.meta.get("clock"), False)
        self.width = max(min_width, width)
        self.height = max(8, height)
        self.footer = footer
        self.cell_w = max(1, int(cell_size[0]))
        self.cell_h = max(1, int(cell_size[1]))
        self.graphics = graphics
        self.dump = dump
        self.math_engine = self._pick_engine(math_engine)
        self.pending: list[PendingPlacement] = []
        self.frame_placements: list[Placement] = []
        self._marker_index = 0
        self._current_index = 0
        self.step = 0
        self._active_slide = deck.slides[0] if deck.slides else None
        self.width_setting = width_setting or str(deck.meta.get("width")
                                                  or "full")
        self.fit = _as_bool(deck.meta.get("fit"), False) if fit is None else fit
        self.scroll_y = 0
        self.max_scroll = 0
        self.content_w = 16
        self.left = 0
        self._apply_width(None)
        self.console = Console(
            width=self.content_w, force_terminal=True, color_system="truecolor",
            file=io.StringIO(), highlight=False, emoji=False,
            legacy_windows=False,
        )
        self.syntax_theme = self._safe_syntax(theme.syntax)
        if math_italic is None:
            math_style = deck.meta.get("math", "italic").strip().lower()
            self.math_italic = math_style not in ("upright", "roman", "off",
                                                  "false")
        else:
            self.math_italic = math_italic

    def _apply_width(self, slide: Optional[Slide]) -> None:
        """Recompute the content column, honouring a per-slide override."""
        setting = self.width_setting
        if slide is not None:
            setting = slide.options.get("width") or setting
        self.content_w = _content_width(setting, self.width)
        self.left = max(0, (self.width - self.content_w) // 2)

    def _new_marker(self) -> str:
        # Private Use Area, one cell wide in the terminal.
        marker = chr(0xE000 + (self._marker_index % 0x1900))
        self._marker_index += 1
        return marker

    def _pick_engine(self, requested: str) -> str:
        engine = (requested or "auto").strip().lower()
        if engine not in ("auto", "latex", "unicode"):
            engine = "auto"
        if engine == "unicode":
            return "unicode"
        if not self.graphics or not tex.available():
            return "unicode"
        return "latex"

    @staticmethod
    def _safe_syntax(name: str) -> str:
        try:
            from pygments.styles import get_style_by_name
            get_style_by_name(name)
            return name
        except Exception:
            return "monokai"

    # -- low level ---------------------------------------------------------

    def _lines(self, renderable, width: Optional[int] = None) -> list[Text]:
        width = width or self.content_w
        opts = self.console.options.update_width(max(1, width))
        segs = self.console.render_lines(renderable, opts, pad=False)
        return [segs_to_text(s) for s in segs]

    def _inline(self, src: str, base_style: str = "") -> Text:
        th = self.theme
        out = Text()
        for span in parse_inline(src):
            parts: list[str] = []
            if span.bold:
                parts.append("bold")
            if span.italic:
                parts.append("italic")
            if span.strike:
                parts.append("strike")
            if span.code:
                parts.append(f"{th.accent2} on {th.code_bg}")
            elif span.math:
                parts.append(f"bold {th.math}")
                span = type(span)(
                    mdm.render_inline(span.text, italic=self.math_italic),
                    math=True,
                )
            elif span.link:
                parts.append(f"underline {th.accent}")
            elif base_style:
                parts.append(base_style)
            else:
                parts.append(th.fg)
            out.append(span.text, " ".join(parts))
            if span.link and not span.text.endswith(span.link):
                out.append(f" ({span.link})", f"dim {th.dim}")
        return out

    # -- blocks ------------------------------------------------------------

    def _heading(self, block: Heading) -> Text:
        th = self.theme
        text = self._inline(block.text, f"bold {th.fg}")
        if block.level == 1:
            out = Text()
            out.append("▌ ", th.accent2)
            out.append_text(text)
            return out
        if block.level == 2:
            out = Text()
            out.append("▎ ", th.accent)
            out.append_text(text)
            return out
        if block.level == 3:
            text.stylize(f"bold {th.accent2}", 0, len(text))
            return text
        text.stylize(f"bold {th.dim}", 0, len(text))
        return text

    def _table_options(self, block: MdTable) -> dict[str, str]:
        opts = {}
        if self.deck.meta.get("table_style"):
            opts["style"] = self.deck.meta["table_style"]
        opts.update(block.options)
        return opts

    def _table(self, block: MdTable,
               width: Optional[int] = None) -> list[Text]:
        th = self.theme
        available = width or self.content_w
        opts = self._table_options(block)
        style = opts.get("style", "rounded").strip().lower()
        bx, show_lines = TABLE_STYLES.get(style, TABLE_STYLES["rounded"])
        # `lines=true` is the discoverable way to ask for separators between
        # every row, whatever box style is in use.
        line_opt = next((opts[key] for key in ("lines", "row_lines",
                                               "rowlines", "dividers")
                         if key in opts), None)
        if line_opt is not None:
            show_lines = _as_bool(line_opt, False)
        compact = _as_bool(opts.get("compact"), False)
        zebra = _as_bool(opts.get("zebra"), True)
        show_header = _as_bool(opts.get("header"), True)
        border = opts.get("border") or th.border
        title = opts.get("title")
        caption = opts.get("caption")

        def build(pad: tuple[int, int]) -> Table:
            table = Table(
                box=bx, border_style=border,
                header_style=f"bold {th.accent} on {th.table_head}",
                title=title, caption=caption,
                title_style=f"bold {th.accent}",
                caption_style=th.dim,
                title_justify=opts.get("title_align", "left"),
                caption_justify=opts.get("caption_align", "right"),
                padding=pad, expand=_as_bool(opts.get("expand"), False),
                show_lines=show_lines, show_header=show_header, leading=0,
                row_styles=([f"on {th.bg}", f"on {th.code_bg}"]
                            if zebra else None),
            )
            for i, head in enumerate(block.header):
                align = block.aligns[i] if i < len(block.aligns) else "left"
                table.add_column(self._inline(head), justify=align,
                                 overflow="fold", no_wrap=False)
            for row in block.rows:
                cells = []
                for i in range(len(block.header)):
                    src = row[i] if i < len(row) else ""
                    cells.append(self._inline(src))
                table.add_row(*cells)
            return table

        table = build((0, 0) if compact else (0, 1))
        natural = max((mdm.swidth(str(line))
                       for line in self._lines(table, 200)), default=0)
        if natural > available and not compact:
            # Drop horizontal padding before letting Rich fold words in
            # half; a cramped table still reads better than "Complexit/y".
            table = build((0, 0))
        wanted = _as_int(opts.get("width"), 0)
        return self._lines(table, min(wanted, available) if wanted else available)

    # -- charts ------------------------------------------------------------

    @staticmethod
    def _chart_number(cell: str) -> Optional[float]:
        text = plain_inline(cell).replace(",", "").strip()
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group()) if match else None

    @staticmethod
    def _chart_fmt(value: float) -> str:
        if abs(value) >= 1000:
            return f"{value / 1000:.1f}k"
        if abs(value) >= 1 and float(value).is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _chart_tick(value: float, lo: float, hi: float) -> str:
        span = abs(hi - lo)
        decimals = 0 if span >= 100 else 1 if span >= 10 else 2
        return f"{value:.{decimals}f}"

    def _chart_palette(self, opts: dict[str, str], count: int) -> list[str]:
        th = self.theme
        palette = [th.accent, th.accent2, th.good, th.math, th.bad]
        raw = opts.get("colors") or opts.get("color")
        if raw:
            parts = [part.strip() for part in re.split(r"[,; ]+", raw)
                     if part.strip()]
            palette = parts or palette
        return [palette[i % len(palette)] for i in range(max(1, count))]

    def _chart_rows(self, block: Chart):
        table = block.table
        names: list[str] = []
        for i, head in enumerate(table.header[1:]):
            name = plain_inline(head).strip() or f"Series {i + 1}"
            names.append(name)
        if not names:
            names = ["Value"]
        rows: list[tuple[str, list[float]]] = []
        for row in table.rows:
            label = plain_inline(row[0]).strip() if row else ""
            values: list[float] = []
            for cell in row[1:]:
                num = self._chart_number(cell)
                values.append(num if num is not None else 0.0)
            if label or values:
                rows.append((label or "—", values))
        return names, rows

    @staticmethod
    def _join_texts(lines: list[Text]) -> Text:
        out = Text()
        for i, line in enumerate(lines):
            if i:
                out.append("\n")
            out.append_text(line)
        return out

    @staticmethod
    def _bar_run(fraction: float, width: int) -> str:
        """A bar of *width* cells with an eighth-block partial end."""

        total = max(0.0, min(1.0, fraction)) * max(0, width)
        whole = int(total)
        eighth = round((total - whole) * 8)
        if eighth >= 8:
            whole += 1
            eighth = 0
        return "█" * whole + (_BAR_FRACTIONS[eighth] if eighth else "")

    def _chart_legend(self, names: list[str], colors: list[str],
                      opts: dict[str, str], rows=None) -> Optional[Text]:
        if not _as_bool(opts.get("legend"), len(names) >= 2):
            return None
        th = self.theme
        shares: list[float] = []
        if _as_bool(opts.get("percent"), False) and rows:
            totals = [sum(values[i] if i < len(values) else 0.0
                          for _, values in rows)
                      for i in range(len(names))]
            grand = sum(totals) or 1
            shares = [value / grand for value in totals]
        out = Text(" ", style=th.on())
        for i, name in enumerate(names):
            if i:
                out.append("   ", th.on())
            out.append("● ", colors[i % len(colors)])
            out.append(_ellipsis(name, 20), th.dim)
            if shares:
                out.append(f" {shares[i] * 100:.0f}%", th.fg)
        return out

    def _chart_series_index(self, names: list[str],
                            opts: dict[str, str]) -> int:
        wanted = (opts.get("series") or "").strip()
        if not wanted:
            return 0
        if wanted.isdigit():
            return max(0, int(wanted) - 1)
        for i, name in enumerate(names):
            if name.lower() == wanted.lower():
                return i
        return 0

    def _chart_bar(self, rows, names, colors, opts, width: int) -> list[Text]:
        th = self.theme
        multi = len(names) > 1
        label_w = min(18, max(4, max((len(label) for label, _ in rows),
                                    default=4)))
        series_w = min(14, max((len(name) for name in names), default=1)) \
            if multi else 0
        val_w = max(5, max((len(self._chart_fmt(v))
                            for _, values in rows for v in values), default=5))
        prefix = label_w + 1 + (series_w + 1 if multi else 0)
        suffix = val_w + 2 if _as_bool(opts.get("values"), True) else 1
        bar_w = max(6, width - prefix - suffix - 2)
        peak = max((abs(v) for _, values in rows for v in values), default=1) or 1
        out: list[Text] = []
        for label, values in rows:
            for i, value in enumerate(values):
                color = colors[i % len(colors)]
                row = Text(_ellipsis(label, label_w).ljust(label_w),
                           style=th.fg)
                if multi:
                    row.append(" " + _ellipsis(names[i], series_w)
                               .ljust(series_w), color)
                row.append(" ", th.on())
                bar = self._bar_run(value / peak, bar_w)
                row.append(bar, color)
                row.append(" " * max(0, bar_w - len(bar)), th.on())
                if suffix > 1:
                    row.append(" " + self._chart_fmt(value).rjust(val_w),
                               th.dim)
                out.append(row)
            if multi:
                out.append(Text())
        return out

    def _chart_stacked(self, rows, names, colors, opts,
                       width: int) -> list[Text]:
        th = self.theme
        label_w = min(18, max(4, max((len(label) for label, _ in rows),
                                    default=4)))
        total_w = max(5, max((len(self._chart_fmt(sum(values)))
                              for _, values in rows), default=5))
        bar_w = max(6, width - label_w - total_w - 5)
        out: list[Text] = []
        segments = len(next(iter(rows))[1]) if rows else 0
        sep = 1 if segments > 1 and bar_w >= segments * 3 else 0
        plot_w = max(1, bar_w - sep * max(0, segments - 1))
        for label, values in rows:
            total = sum(max(0.0, value) for value in values) or 1
            row = Text(_ellipsis(label, label_w).ljust(label_w), style=th.fg)
            row.append(" ", th.on())
            used = 0
            for i, value in enumerate(values):
                size = round(max(0.0, value) / total * plot_w)
                row.append("█" * size, colors[i % len(colors)])
                used += size
                if sep and i < len(values) - 1:
                    row.append("│", th.dim)
            row.append(" " * max(0, bar_w - used - sep * max(0, len(values) - 1)),
                       th.on())
            row.append(" " + self._chart_fmt(sum(values)).rjust(total_w),
                       th.dim)
            out.append(row)
        return out

    def _chart_columns(self, rows, names, colors, opts,
                       width: int) -> list[Text]:
        th = self.theme
        height = max(3, min(10, _as_int(opts.get("height"), 6)))
        items: list[tuple[str, float, str]] = []
        for label, values in rows:
            for i, value in enumerate(values):
                if len(names) == 1:
                    name = label
                else:
                    name = f"{label[:2]}·{names[i][:2]}"
                items.append((name, value, colors[i % len(colors)]))
        if not items:
            return [Text("no data", th.dim)]
        peak = max(value for _, value, _ in items)
        floor = min(0.0, min(value for _, value, _ in items))
        span = (peak - floor) or 1
        col_w = max(2, min(5, (width - 10) // len(items)))
        gap = 1
        plot_w = len(items) * (col_w + gap) - gap
        axis_w = max(len(self._chart_tick(peak, floor, peak)),
                     len(self._chart_tick(floor, floor, peak))) + 2
        out: list[Text] = []
        for level in range(height, 0, -1):
            threshold = floor + span * level / height
            line = Text(self._chart_tick(threshold, floor, peak).rjust(axis_w - 1)
                        + " │", style=th.dim)
            for _, value, color in items:
                filled = value >= threshold - span / (height * 2)
                if filled:
                    line.append("█" * col_w, color)
                else:
                    line.append("·" * col_w, th.dim)
                line.append(" " * gap, th.on())
            out.append(line)
        out.append(Text(" " * axis_w + "└" + "─" * plot_w, style=th.dim))
        labels = Text(" " * (axis_w + 1), style=th.on())
        for name, _, _ in items:
            labels.append(name[:col_w].ljust(col_w), th.dim)
            labels.append(" " * gap, th.on())
        out.append(labels)
        return out

    def _chart_line(self, rows, names, colors, opts, width: int) -> list[Text]:
        th = self.theme
        height = max(3, min(10, _as_int(opts.get("height"), 7)))
        values = [value for _, row_values in rows for value in row_values]
        if not values:
            return [Text("no data", th.dim)]
        axis_w = max(len(self._chart_tick(max(values), min(values),
                                          max(values))),
                     len(self._chart_tick(min(values), min(values),
                                          max(values)))) + 2
        plot_w = max(10, width - axis_w - 2)
        canvas: list[list[tuple[str, str]]] = [
            [(" ", th.on()) for _ in range(plot_w)] for _ in range(height)
        ]

        def put(x: int, y: int, char: str, color: str) -> None:
            if 0 <= x < plot_w and 0 <= y < height:
                canvas[y][x] = (char, color)

        lo, hi = min(values), max(values)
        if lo == hi:
            lo -= 1
            hi += 1
        for gy in range(0, height, 2):
            for gx in range(0, plot_w, 8):
                put(gx, gy, "·", th.dim)

        points: list[list[tuple[int, int]]] = []
        for s in range(len(names)):
            series: list[tuple[int, int]] = []
            for i, (_, row_values) in enumerate(rows):
                value = row_values[s] if s < len(row_values) else 0.0
                x = round(i * (plot_w - 1) / max(1, len(rows) - 1))
                y = height - 1 - round((value - lo) / (hi - lo) * (height - 1))
                series.append((x, y))
            points.append(series)
            color = colors[s % len(colors)]
            for (x0, y0), (x1, y1) in zip(series, series[1:]):
                dx, dy = x1 - x0, y1 - y0
                steps = max(1, abs(dx), abs(dy))
                if abs(dy) * 2 < abs(dx):
                    char = "─"
                elif abs(dx) * 2 < abs(dy):
                    char = "│"
                else:
                    char = "╱" if dy < 0 else "╲"
                for step in range(steps + 1):
                    x = round(x0 + dx * step / steps)
                    y = round(y0 + dy * step / steps)
                    put(x, y, char, color)
        for s, series in enumerate(points):
            color = colors[s % len(colors)]
            for x, y in series:
                put(x, y, "●", color)

        out: list[Text] = []
        for y in range(height):
            value = hi - (hi - lo) * y / max(1, height - 1)
            line = Text(self._chart_tick(value, lo, hi).rjust(axis_w - 1)
                        + " │", style=th.dim)
            for char, color in canvas[y]:
                line.append(char, color)
            out.append(line)
        out.append(Text(" " * axis_w + "└" + "─" * plot_w, style=th.dim))
        marks = sorted(set([0, len(rows) // 2, len(rows) - 1]))
        cells = [" "] * plot_w
        for row_index in marks:
            x = round(row_index * (plot_w - 1) / max(1, len(rows) - 1))
            label = _ellipsis(rows[row_index][0], min(10, plot_w))
            start = min(plot_w - len(label), max(0, x - len(label) // 2))
            if any(cell != " " for cell in cells[start:start + len(label)]):
                continue
            for offset, ch in enumerate(label):
                cells[start + offset] = ch
        axis = Text(" " * axis_w, style=th.on())
        axis.append("".join(cells).rstrip(), th.dim)
        out.append(axis)
        return out

    def _chart_spark(self, rows, names, colors, opts,
                     width: int) -> list[Text]:
        th = self.theme
        steps = "▁▂▃▄▅▆▇█"
        multi = len(names) > 1
        if multi:
            label_w = min(16, max(4, max((len(name) for name in names),
                                         default=4)))
        else:
            label_w = min(16, max(4, max((len(label) for label, _ in rows),
                                         default=4)))
        out: list[Text] = []

        def sparkline(series: list[float]) -> str:
            lo, hi = min(series), max(series)
            span = (hi - lo) or 1
            return "".join(
                steps[min(7, max(0, round((value - lo) / span * 7)))]
                for value in series
            )

        if multi:
            for i, name in enumerate(names):
                series = [values[i] if i < len(values) else 0.0
                          for _, values in rows]
                row = Text(name[:label_w].ljust(label_w), style=colors[i % len(colors)])
                row.append(sparkline(series), colors[i % len(colors)])
                row.append(" " + self._chart_fmt(series[-1] if series else 0),
                           th.dim)
                out.append(row)
        else:
            # One series means one sparkline. Repeating the whole line for
            # every category just turns the chart into noise.
            series = [values[0] if values else 0.0 for _, values in rows]
            name = names[0] if names else "trend"
            row = Text(name[:label_w].ljust(label_w), style=th.fg)
            row.append(sparkline(series), colors[0])
            row.append(" " + self._chart_fmt(series[-1] if series else 0),
                       th.dim)
            out.append(row)
            if rows:
                axis = Text(" " * label_w, style=th.on())
                axis.append(_ellipsis(str(rows[0][0]), 8).ljust(8), th.dim)
                gap = max(0, len(series) - 16)
                if gap:
                    axis.append(" " * gap, th.on())
                axis.append(_ellipsis(str(rows[-1][0]), 8), th.dim)
                out.append(axis)
        return out

    def _chart_items(self, rows, names, colors, opts):
        """Select one series for pie/gauge/scatter style charts."""

        index = self._chart_series_index(names, opts)
        offset = index % max(1, len(colors))
        items = []
        for position, (label, values) in enumerate(rows):
            value = values[index] if index < len(values) else 0.0
            items.append((label, value,
                          colors[(offset + position) % len(colors)]))
        return items

    def _chart_pie(self, rows, names, colors, opts, width: int,
                   donut: bool = False) -> list[Text]:
        """Draw a smooth pie/ring with a faint frame and breathing room."""

        th = self.theme
        items = [item for item in self._chart_items(rows, names, colors, opts)
                 if item[1] > 0]
        total = sum(value for _, value, _ in items)
        if not items or total <= 0:
            return [Text("no data", th.dim)]

        wanted_h = _as_int(opts.get("height"), 9)
        cell_rows_wanted = max(5, min(wanted_h, max(5, self.height - 6)))
        radius_rows = max(2, cell_rows_wanted // 2)

        # A terminal cell is about twice as tall as it is wide, so a circle
        # needs twice as many character columns as rows. Plain-text dumps have
        # square-ish cells and need a 1:1 character grid instead. `aspect=`
        # overrides either default.
        aspect = _as_float(opts.get("aspect"), 0.0)
        if aspect <= 0:
            aspect = 1.0 if self.dump else self.cell_h / self.cell_w
        aspect = min(3.0, max(0.5, aspect))
        radius_cols = max(2, round(aspect * radius_rows))
        max_radius = max(2, (width - 10) // 2)
        if radius_cols > max_radius:
            radius_cols = max_radius
            radius_rows = max(2, round(radius_cols / aspect))
        cell_cols = 2 * radius_cols + 1
        cell_rows = 2 * radius_rows + 1
        hole = 0.0
        if donut:
            hole = min(0.75, max(0.25, _as_float(opts.get("hole"), 0.55)))

        # The disk gets its own quiet frame plus at least one blank cell of
        # air. `pad=` widens that margin; `frame=none` keeps the air.
        raw_frame = (opts.get("frame") or opts.get("outline") or "box")
        frame = raw_frame.strip().lower()
        if frame in ("none", "off", "false", "0"):
            frame = "none"
        elif frame in ("circle", "ring", "round", "ellipse"):
            frame = "circle"
        elif frame in ("square", "rect", "rectangle"):
            frame = "square"
        else:
            frame = "box"
        pad = max(0, min(3, _as_int(opts.get("pad"), 1)))
        margin = pad + (0 if frame == "none" else 1)
        canvas_cols = cell_cols + 2 * margin
        canvas_rows = cell_rows + 2 * margin
        canvas = Canvas(canvas_cols, canvas_rows, th.on())
        frame_color = opts.get("frame_color") or th.border

        shares: list[float] = []
        running = 0.0
        for _, value, _ in items:
            running += value / total
            shares.append(running)
        full_turn = 2 * _math.pi

        # One braille cell is 2 columns x 4 rows of dots, so the sub-pixel
        # grid is nearly square when the cell grid has a 2:1 aspect ratio.
        sub_cols = 2 * canvas_cols
        sub_rows = 4 * canvas_rows
        dots = [[0] * canvas_cols for _ in range(canvas_rows)]
        votes = [[[0] * len(items) for _ in range(canvas_cols)]
                 for _ in range(canvas_rows)]
        ring = [[0] * canvas_cols for _ in range(canvas_rows)]
        cx = sub_cols / 2
        cy = sub_rows / 2
        # Disk radius stays fixed even though the canvas has grown.
        rx = float(cell_cols)
        ry = float(2 * cell_rows)

        if frame == "circle":
            for sy in range(sub_rows):
                ny = (sy + 0.5 - cy) / ry
                for sx in range(sub_cols):
                    nx = (sx + 0.5 - cx) / rx
                    dist = nx * nx + ny * ny
                    if 1.02 <= dist <= 1.16:
                        bx, by = sx // 2, sy // 4
                        ring[by][bx] |= _BRAILLE_BITS[sy % 4][sx % 2]

        for sy in range(sub_rows):
            ny = (sy + 0.5 - cy) / ry
            for sx in range(sub_cols):
                nx = (sx + 0.5 - cx) / rx
                dist = nx * nx + ny * ny
                if dist > 1.0 or (hole and dist < hole * hole):
                    continue
                angle = _math.atan2(nx, -ny)
                if angle < 0:
                    angle += full_turn
                sector = next(
                    (i for i, stop in enumerate(shares)
                     if angle < stop * full_turn),
                    len(items) - 1,
                )
                bx, by = sx // 2, sy // 4
                dots[by][bx] |= _BRAILLE_BITS[sy % 4][sx % 2]
                votes[by][bx][sector] += 1

        for by in range(canvas_rows):
            for bx in range(canvas_cols):
                mask = dots[by][bx] | ring[by][bx]
                if not mask:
                    continue
                color = frame_color
                if dots[by][bx]:
                    sector = max(range(len(items)),
                                 key=lambda i: votes[by][bx][i])
                    color = items[sector][2]
                canvas.put(bx, by, chr(0x2800 | mask), color)

        if frame in ("box", "square"):
            corner = "┌┐└┘" if frame == "square" else "╭╮╰╯"
            right, bottom = canvas_cols - 1, canvas_rows - 1
            canvas.put(0, 0, corner[0], frame_color)
            canvas.put(right, 0, corner[1], frame_color)
            canvas.put(0, bottom, corner[2], frame_color)
            canvas.put(right, bottom, corner[3], frame_color)
            for x in range(1, right):
                canvas.put(x, 0, "─", frame_color)
                canvas.put(x, bottom, "─", frame_color)
            for y in range(1, bottom):
                canvas.put(0, y, "│", frame_color)
                canvas.put(right, y, "│", frame_color)

        if donut and hole > 0.35:
            center = opts.get("label") or self._chart_fmt(total)
            room = max(4, int(2 * radius_cols * hole) - 1)
            center = _ellipsis(center, room)
            canvas.put(margin + radius_cols - len(center) // 2,
                       margin + radius_rows, center, th.fg)

        disk = canvas.to_lines()
        legend: list[Text] = []
        if _as_bool(opts.get("legend"), True):
            label_w = min(18, max((len(label) for label, _, _ in items),
                                  default=4))
            for label, value, color in items:
                row = Text("  ", th.on())
                row.append("● ", color)
                row.append(_ellipsis(label, label_w).ljust(label_w), th.fg)
                row.append(f" {value / total * 100:>4.0f}%", th.dim)
                if _as_bool(opts.get("values"), False):
                    row.append(" " + self._chart_fmt(value), th.dim)
                legend.append(row)

        def prefixed(line: Text, padding: int) -> Text:
            out = Text(" " * padding, style=th.on())
            out.append_text(line)
            return out

        legend_w = max((line.cell_len for line in legend), default=0)
        legend_gap = max(3, _as_int(opts.get("legend_gap"), 6))
        side = bool(legend) and canvas_cols + legend_gap + legend_w <= width
        if side:
            pad_left = max(0, (width - canvas_cols - legend_gap
                               - legend_w) // 2)
            legend_top = max(0, (len(disk) - len(legend)) // 2)
            out = []
            for i, line in enumerate(disk):
                row = prefixed(line, pad_left)
                j = i - legend_top
                if 0 <= j < len(legend):
                    row.append(" " * legend_gap, th.on())
                    row.append_text(legend[j])
                out.append(row)
            return out

        disk_pad = max(0, (width - canvas_cols) // 2)
        out = [prefixed(line, disk_pad) for line in disk]
        if legend:
            out.append(Text("", th.on()))
            out.extend(prefixed(line, max(0, (width - line.cell_len) // 2))
                       for line in legend)
        return out

    def _chart_gauge(self, rows, names, colors, opts, width: int) -> list[Text]:
        th = self.theme
        items = self._chart_items(rows, names, colors, opts)
        if not items:
            return [Text("no data", th.dim)]
        label, value, color = items[0]
        low = _as_float(opts.get("min"), 0.0)
        high = _as_float(opts.get("max"), 100.0)
        if high <= low:
            high = low + 1
        ratio = min(1.0, max(0.0, (value - low) / (high - low)))
        if not opts.get("colors"):
            color = th.good if ratio < 0.6 else th.accent2 if ratio < 0.85 \
                else th.bad
        bar_w = max(8, width - 14)

        head = Text("  ", th.on())
        head.append(_ellipsis(label or "Value", 30), th.fg)
        head.append(f"  {self._chart_fmt(value)} / {self._chart_fmt(high)}",
                    th.dim)
        bar = Text("  ", th.on())
        bar.append("[", th.dim)
        bar.append(self._bar_run(ratio, bar_w), color)
        bar.append("]", th.dim)
        bar.append(f" {ratio * 100:5.1f}%", th.dim)
        return [head, Text("", th.on()), bar]

    def _chart_scatter(self, rows, names, colors, opts,
                       width: int) -> list[Text]:
        th = self.theme
        height = max(3, min(9, _as_int(opts.get("height"), 7)))
        index = self._chart_series_index(names, opts)
        points: list[tuple[float, float, str, str]] = []
        for i, (label, values) in enumerate(rows):
            x = self._chart_number(label)
            if x is None:
                x = float(i)
            y = values[index] if index < len(values) else 0.0
            color = colors[(index + i) % len(colors)]
            points.append((x, y, label, color))
        if not points:
            return [Text("no data", th.dim)]

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        xlo, xhi = min(xs), max(xs)
        ylo, yhi = min(ys), max(ys)
        if xlo == xhi:
            xlo -= 1
            xhi += 1
        if ylo == yhi:
            ylo -= 1
            yhi += 1
        axis_w = max(len(self._chart_tick(yhi, ylo, yhi)),
                     len(self._chart_tick(ylo, ylo, yhi))) + 2
        plot_w = max(10, width - axis_w - 2)
        canvas: list[list[tuple[str, str]]] = [
            [(" ", th.on()) for _ in range(plot_w)] for _ in range(height)
        ]

        def put(x: int, y: int, char: str, color: str) -> None:
            if 0 <= x < plot_w and 0 <= y < height:
                canvas[y][x] = (char, color)

        for gy in range(0, height, 2):
            for gx in range(0, plot_w, 8):
                put(gx, gy, "·", th.dim)
        for x, y, _, color in points:
            px = round((x - xlo) / (xhi - xlo) * (plot_w - 1))
            py = height - 1 - round((y - ylo) / (yhi - ylo) * (height - 1))
            put(px, py, "●", color)

        out: list[Text] = []
        for row in range(height):
            value = yhi - (yhi - ylo) * row / max(1, height - 1)
            line = Text(self._chart_tick(value, ylo, yhi).rjust(axis_w - 1)
                        + " │", style=th.dim)
            for char, color in canvas[row]:
                line.append(char, color)
            out.append(line)
        out.append(Text(" " * axis_w + "└" + "─" * plot_w, style=th.dim))
        if all(self._chart_number(point[2]) is not None for point in points):
            xlabels = self._chart_fmt(xlo) + "  " + self._chart_fmt(xhi)
        else:
            xlabels = (_ellipsis(points[0][2], 10) + "  "
                       + _ellipsis(points[-1][2], 10))
        out.append(Text(" " * (axis_w + 1) + xlabels[:plot_w], style=th.dim))
        return out

    def _chart(self, block: Chart,
               width: Optional[int] = None) -> list[Text]:
        th = self.theme
        opts = dict(block.options)
        if self.deck.meta.get("chart_type"):
            opts.setdefault("type", self.deck.meta["chart_type"])
        kind = (opts.get("type") or opts.get("style") or "bar").strip().lower()
        aliases = {
            "hbar": "bar", "bars": "bar", "vbar": "columns",
            "column": "columns", "cols": "columns", "line": "line",
            "lines": "line", "spark": "spark", "sparkline": "spark",
            "stack": "stacked", "stacked": "stacked", "area": "line",
            "pie": "pie", "circle": "pie", "donut": "donut", "ring": "donut",
            "doughnut": "donut", "gauge": "gauge", "meter": "gauge",
            "bullet": "gauge", "scatter": "scatter", "xy": "scatter",
            "points": "scatter",
        }
        kind = aliases.get(kind, kind)
        if kind == "stacked" and "percent" not in opts:
            opts["percent"] = "true"
        if self.fit and "height" not in opts and kind in (
                "bar", "columns", "stacked", "line"):
            opts["height"] = "3"
        available = width or self.content_w
        width = min(_as_int(opts.get("width"), 0) or available, available)
        inner = max(6, width - 4)
        names, rows = self._chart_rows(block)
        # Pies/gauges/scatter colour categories (rows), not just data series.
        # Other charts still only read the leading series colours, so sizing
        # the palette by both keeps explicit `colors=` lists usable everywhere.
        colors = self._chart_palette(opts, max(len(names), len(rows)))
        order = (opts.get("sort") or "").strip().lower()
        if order in ("asc", "ascending"):
            rows.sort(key=lambda item: item[1][0] if item[1] else 0)
        elif order in ("desc", "descending", "top"):
            rows.sort(key=lambda item: item[1][0] if item[1] else 0,
                      reverse=True)
        limit = _as_int(opts.get("top"), 0)
        if limit:
            rows = rows[:limit]

        embedded_legend = kind in ("pie", "donut", "gauge", "scatter")
        if kind == "pie":
            body = self._chart_pie(rows, names, colors, opts, inner)
        elif kind == "donut":
            body = self._chart_pie(rows, names, colors, opts, inner,
                                   donut=True)
        elif kind == "gauge":
            body = self._chart_gauge(rows, names, colors, opts, inner)
        elif kind == "scatter":
            body = self._chart_scatter(rows, names, colors, opts, inner)
        elif kind == "stacked":
            body = self._chart_stacked(rows, names, colors, opts, inner)
        elif kind == "columns":
            body = self._chart_columns(rows, names, colors, opts, inner)
        elif kind == "line":
            body = self._chart_line(rows, names, colors, opts, inner)
        elif kind == "spark":
            body = self._chart_spark(rows, names, colors, opts, inner)
        else:
            body = self._chart_bar(rows, names, colors, opts, inner)

        legend = None if embedded_legend else self._chart_legend(
            names, colors, opts, rows)
        pieces = list(body)
        if legend is not None:
            pieces.extend([Text(), legend])
        title = opts.get("title")
        caption = opts.get("caption")
        panel = Panel(
            self._join_texts(pieces), box=box.ROUNDED,
            border_style=opts.get("border") or th.border,
            title=Text(title, style=f"bold {th.accent}") if title else None,
            title_align=opts.get("title_align", "left"),
            subtitle=Text(caption, style=th.dim) if caption else None,
            subtitle_align="right", padding=(0, 1), style=th.on(),
            width=width,
        )
        return self._lines(panel, width)

    def _code(self, block: Code, width: Optional[int] = None) -> list[Text]:
        th = self.theme
        lang = block.lang or "text"
        syntax = Syntax(
            block.code, lang, theme=self.syntax_theme, line_numbers=False,
            word_wrap=True, background_color=th.code_bg, padding=0,
        )
        panel = Panel(
            syntax, box=box.ROUNDED, border_style=th.border,
            title=lang if block.lang else None, title_align="right",
            padding=(0, 1), style=th.on(),
            width=width or self.content_w,
        )
        return self._lines(panel, width or self.content_w)

    def _list(self, block: ListBlock, width: int, indent: int = 0) -> list[Text]:
        th = self.theme
        out: list[Text] = []
        for k, item in enumerate(block.items):
            if item.reveal > self.step:
                continue
            if item.checked is not None:
                marker = "☑ " if item.checked else "☐ "
            elif block.ordered:
                marker = f"{block.start + k}. "
            else:
                marker = "• "
            mw = mdm.swidth(marker)
            avail = max(4, width - indent - mw)
            body = self._lines(self._inline(item.text), avail)
            for j, line in enumerate(body):
                prefix = Text(" " * indent)
                if j == 0:
                    prefix.append(marker, th.accent)
                else:
                    prefix.append(" " * mw)
                prefix.append_text(line)
                out.append(prefix)
            for child in item.children:
                if self._reveal_of(child) > self.step:
                    continue
                if isinstance(child, ListBlock):
                    out.extend(self._list(child, width, indent + mw))
                else:
                    for line in self._block_lines(child, max(8, width - indent - mw)):
                        prefix = Text(" " * (indent + mw))
                        prefix.append_text(line)
                        out.append(prefix)
        return out

    def _quote(self, block: Quote, width: int) -> list[Text]:
        th = self.theme
        inner: list[Text] = []
        for child in block.blocks:
            inner.extend(self._block_lines(child, width - 2))
        out = []
        for line in inner:
            prefix = Text()
            prefix.append("▎ ", th.accent2)
            prefix.append_text(line)
            out.append(prefix)
        return out

    def _image(self, block: Image,
               width: Optional[int] = None) -> list[Text]:
        th = self.theme
        width = width or self.content_w
        opts: dict[str, str] = {}
        for key in ("image_width", "image_height"):
            if self.deck.meta.get(key):
                opts[key[6:]] = self.deck.meta[key]
        opts.update(block.options)
        title = opts.get("title") or block.alt or "image"
        caption = opts.get("caption") or block.src
        resolved = images.resolve_path(block.src, self.base_dir)
        bx = EQ_BOXES.get((opts.get("style") or "rounded").strip().lower(),
                          box.ROUNDED) or box.ROUNDED
        border_style = opts.get("border") or th.border

        def make_panel(body: Text, panel_w: int) -> list[Text]:
            panel_w = max(10, min(width, panel_w))
            return self._lines(Panel(
                body, box=bx, border_style=border_style,
                title=Text(_ellipsis(title, max(8, panel_w - 6)),
                           style=f"bold {th.accent}"),
                subtitle=Text(_ellipsis(caption, max(8, panel_w - 6)),
                              style=th.dim),
                title_align="left", subtitle_align="right",
                padding=(0, 1), style=th.on(), width=panel_w,
            ), panel_w)

        if self.graphics:
            # Leave room for the two border cells and two padding cells so the
            # frame hugs the picture instead of stretching across the slide.
            max_cols = max(6, min(width - 4, self.content_w - 4))
            max_rows = max(3, self.height - 6)
            prepared = images.prepare_image(
                block.src, self.base_dir,
                max_width_px=max_cols * self.cell_w,
                max_height_px=max_rows * self.cell_h,
            )
            if prepared:
                max_cols = min(max_cols, _as_int(opts.get("width"), 0)
                               or max_cols)
                max_rows = min(max_rows, _as_int(opts.get("height"), 0)
                               or max_rows)
                natural_cols = max(1, round(prepared.width / self.cell_w))
                natural_rows = max(1, round(prepared.height / self.cell_h))
                scale = min(1.0, max_cols / natural_cols,
                            max_rows / natural_rows)
                cols = max(1, round(natural_cols * scale))
                rows = max(1, round(natural_rows * scale))
                marker = self._new_marker()
                body = Text(marker + " " * max(0, cols - 1))
                for _ in range(max(0, rows - 1)):
                    body.append("\n" + " " * cols)
                self.pending.append(
                    PendingPlacement(marker, str(prepared.path), cols, rows))
                return make_panel(body, cols + 4)

        size = images.image_size(resolved) if resolved.is_file() else None
        fill = opts.get("fill", "░")[:1] or "░"
        col_limit = max(6, _as_int(opts.get("width"), 0) or 36)
        row_limit = max(3, _as_int(opts.get("height"), 0)
                        or (5 if self.fit else 8))
        panel_cols = max(6, min(width - 4, col_limit))
        panel_rows = 3
        if size:
            aspect = 1.0 if self.dump else self.cell_h / self.cell_w
            max_rows = max(3, min(self.height - 6, row_limit))
            panel_rows = max(2, round(panel_cols * size[1]
                                      / max(1, size[0]) / aspect))
            if panel_rows > max_rows:
                panel_rows = max_rows
                panel_cols = max(6, min(width - 4, col_limit,
                                        round(panel_rows * aspect
                                              * size[0] / max(1, size[1]))))
        body = Text()
        body.append("\n".join(fill * panel_cols
                              for _ in range(panel_rows)), th.dim)
        if not resolved.is_file():
            body.append("\nmissing file", th.bad)
        elif size:
            body.append(f"\n{size[0]}×{size[1]} px", th.dim)
        return make_panel(body, panel_cols + 4)

    def _eq_options(self, block: MathBlock) -> dict[str, str]:
        opts: dict[str, str] = {}
        if self.deck.meta.get("eq_style"):
            opts["style"] = self.deck.meta["eq_style"]
        opts.update(block.options)
        return opts

    def _align_lines(self, lines: list[Text], width: int,
                     align: str = "center") -> list[Text]:
        align = (align or "center").strip().lower()
        out: list[Text] = []
        for line in lines:
            spare = max(0, width - line.cell_len)
            if align == "left":
                left = 0
            elif align == "right":
                left = spare
            else:
                left = spare // 2
            row = Text(" " * left, style=self.theme.on())
            row.append_text(line)
            if spare - left > 0:
                row.append(" " * (spare - left), self.theme.on())
            out.append(row)
        return out

    def _equation_frame(self, body: Text, opts: dict[str, str],
                        width: int) -> list[Text]:
        """Wrap equation lines in a presentation card or a Rich panel."""

        th = self.theme
        style = opts.get("style", "rounded").strip().lower()
        color = opts.get("color") or th.math
        title = opts.get("title") or ""
        number = opts.get("number") or opts.get("no")
        num = f"({number})" if number else ""
        align = opts.get("align", "center")

        body = body.copy()
        body_lines = body.plain.split("\n")
        body_w = max((mdm.swidth(line) for line in body_lines), default=1)

        if style in ("card", "clean"):
            # A quiet math card: a slim accent rule and a small kicker instead
            # of a full border with the title embedded in it (which reads as a
            # clickable button).  The formula background stays the theme
            # background, matching the rasterised LaTeX exactly.
            prefix, suffix = 2, 1
            num_len = mdm.swidth(num)
            wanted = max(body_w + 2,
                         mdm.swidth(title) + num_len + 3 if num else
                         mdm.swidth(title) + 2)
            inner = max(1, min(width - prefix - suffix, wanted))
            room = max(0, inner - num_len - 1)
            if mdm.swidth(title) > room:
                title = title[:max(0, room - 1)] + "…"
            total = prefix + inner + suffix

            head = Text(" " * prefix, style=th.on())
            if title:
                head.append(title, f"bold {th.accent}")
            if num:
                gap = max(1, inner - mdm.swidth(title) - mdm.swidth(num))
                head.append(" " * gap, th.on())
                head.append(num, th.dim)
            head.append(" " * max(0, total - head.cell_len), th.on())

            lines = [head]
            for line in body_lines:
                row = Text("▌ ", style=th.accent)
                row.append(line, f"bold {color}")
                row.append(" " * max(0, inner - mdm.swidth(line)), th.on())
                row.append(" " * suffix, th.on())
                lines.append(row)
            return self._align_lines(lines, width, align)

        bx = EQ_BOXES.get(style, box.ROUNDED)
        pad_v = min(3, _as_int(opts.get("pad"), 1))
        pad_h = 1
        subtitle = num or None
        border = opts.get("border") or (
            th.accent if style == "accent" else th.border)
        body.stylize(f"bold {color}")
        extra = max(mdm.swidth(title), mdm.swidth(num))
        # A Rich panel needs two border cells plus horizontal padding around
        # the body; a frameless equation pads the body itself, so it only
        # needs the body width. Getting this wrong makes Rich re-wrap tall
        # matrices and integrals into a mangled box.
        natural = body_w + (2 * pad_h + 2 if bx is not None else 0)
        if extra:
            natural = max(natural, extra + 6)
        render_w = max(1, min(width, natural))

        if bx is None:
            # Rich panels cannot have box=None; pad the body directly.  Reserve
            # those cells before rendering so the total never exceeds width.
            avail = max(1, width - 2 * pad_h)
            out: list[Text] = []
            for line in self._lines(body, min(render_w, avail)):
                row = Text(" " * pad_h, style=th.on())
                row.append_text(line)
                row.append(" " * pad_h, th.on())
                out.append(row)
            return self._align_lines(out, width, align)

        panel = Panel(
            body, box=bx, border_style=border,
            title=title or None,
            title_align=opts.get("title_align", "center"),
            subtitle=subtitle, subtitle_align="right",
            padding=(pad_v, pad_h), expand=False, style=th.on(),
        )
        lines = self._lines(panel, render_w)
        return self._align_lines(lines, width, align)

    def _math_latex(self, block: MathBlock, width: int) -> Optional[list[Text]]:
        """Typeset a display formula with LaTeX and reserve a box for it."""

        th = self.theme
        opts = self._eq_options(block)
        style = opts.get("style", "rounded").strip().lower()
        boxed = block.latex.strip().startswith("\\boxed")
        no_frame = boxed or style in ("none", "plain")
        card = style in ("card", "clean")

        pad_h = 0 if no_frame else 1
        if no_frame:
            border_cols = 0
        elif card:
            # Accent rule + inner padding + trailing space.
            border_cols = 3
        else:
            border_cols = 0 if EQ_BOXES.get(style) is None else 2
        max_cols = max(2, width - 2 * pad_h - border_cols)
        img = tex.render(block.latex, fg=th.math, bg=th.bg,
                         max_width_px=max_cols * self.cell_w)
        if img is None:
            return None

        natural_cols = max(1, round(img.width / self.cell_w))
        natural_rows = max(1, round(img.height / self.cell_h))
        pad_v = 0 if no_frame else min(3, _as_int(opts.get("pad"), 1))
        max_rows = max(2, self.height - 4 - 2 * pad_v)
        scale = min(1.0, max_cols / natural_cols, max_rows / natural_rows)
        cols = max(1, round(natural_cols * scale))
        rows = max(1, round(natural_rows * scale))

        marker = self._new_marker()
        body = Text(marker + " " * max(0, cols - 1))
        for _ in range(max(0, rows - 1)):
            body.append("\n" + " " * cols)
        if boxed:
            # \boxed already draws a frame; an outer frame would double it.
            opts = dict(opts)
            opts["style"] = "none"
            opts["pad"] = "0"
        lines = self._equation_frame(body, opts, width)
        self.pending.append(
            PendingPlacement(marker, str(img.path), cols, rows))
        return lines

    def _math(self, block: MathBlock, width: Optional[int] = None) -> list[Text]:
        th = self.theme
        width = width or self.content_w
        if self.math_engine == "latex":
            lines = self._math_latex(block, width)
            if lines is not None:
                return lines
        opts = self._eq_options(block)
        style = opts.get("style", "rounded").strip().lower()
        boxed = block.latex.strip().startswith("\\boxed")
        no_frame = boxed or style in ("none", "plain")
        card = style in ("card", "clean")
        pad_h = 0 if no_frame else 1
        side = 3 if card else 2
        inner = max(4, width - 2 * pad_h - side)
        lines = mdm.render_block_wrapped(block.latex, inner,
                                         italic=self.math_italic)
        widest = max((mdm.swidth(line) for line in lines), default=0)
        if boxed:
            # \boxed already draws a frame; an outer frame would double it.
            opts = dict(opts)
            opts["style"] = "none"
            opts["pad"] = "0"
        elif "pad" not in opts and widest + 4 > width:
            opts["pad"] = "0"
        body = Text()
        # Keep each line's own leading spaces: tall constructs such as
        # matrices rely on them to line up their delimiters. Only pad on the
        # right so every line has the same width for the panel.
        body.append("\n".join(
            line + " " * max(0, widest - mdm.swidth(line)) for line in lines))
        return self._equation_frame(body, opts, width)

    def _callout(self, block: Callout, width: int) -> list[Text]:
        th = self.theme
        kind = (block.kind or "note").strip().lower()
        mark, color_key = CALLOUT_STYLES.get(kind, CALLOUT_STYLES["note"])
        color = getattr(th, color_key, th.accent)
        title = block.title or kind.capitalize()
        inner: list[Text] = []
        for child in block.blocks:
            inner.extend(self._block_lines(child, max(12, width - 4)))
        body = Text("\n").join(inner) if inner else Text(" ", th.fg)
        panel = Panel(
            body, box=box.ROUNDED, border_style=color,
            title=f" {mark} {title} ", title_align="left",
            padding=(0, 1), expand=False, style=th.on(),
        )
        lines = self._lines(panel, min(width, self.content_w))
        return self._align_lines(lines, width,
                                 block.options.get("align", "center"))

    def _rule(self, block: Rule, width: int) -> list[Text]:
        th = self.theme
        opts = block.options
        style = (opts.get("style") or "single").strip().lower()
        glyphs = {
            "single": "─", "light": "─", "double": "═", "heavy": "━",
            "thick": "━", "dashed": "╌", "dotted": "┄", "accent": "━",
        }
        char = (opts.get("char") or glyphs.get(style, glyphs["single"]))[:1]
        length = max(3, min(width, _as_int(opts.get("width"), 0) or width))
        color = opts.get("color") or th.dim
        if style in ("accent", "gradient"):
            line = gradient_text(char * length, th.accent, th.accent2)
        else:
            line = Text(char * length, style=color)

        label = opts.get("label")
        if label and len(label) + 4 <= length:
            label_text = f" {label} "
            left = (length - len(label_text)) // 2
            line = Text(char * left, style=color)
            line.append(label_text,
                        f"bold {opts.get('label_color') or th.accent}")
            line.append(char * (length - left - len(label_text)), style=color)
        return self._align_lines([line], width,
                                 opts.get("align", "center"))

    def _frame(self, block: Frame, width: int) -> list[Text]:
        th = self.theme
        opts = block.options
        style = (opts.get("style") or "rounded").strip().lower()
        bx = EQ_BOXES.get(style, box.ROUNDED) or box.ROUNDED
        color = opts.get("border") or (
            th.accent if style in ("double", "heavy", "accent") else th.border)
        inner_w = max(8, width - 4)
        pieces: list[Text] = []
        for child in block.blocks:
            if pieces:
                pieces.append(Text())
            pieces.extend(self._block_lines(child, inner_w))
        body = self._join_texts(pieces) if pieces else Text(" ")
        title = opts.get("title")
        caption = opts.get("caption")
        panel = Panel(
            body, box=bx, border_style=color,
            title=Text(title, style=f"bold {th.accent}") if title else None,
            subtitle=Text(caption, style=th.dim) if caption else None,
            title_align=opts.get("title_align", "left"),
            subtitle_align=opts.get("subtitle_align", "right"),
            padding=(0, 1), style=th.on(), width=width,
        )
        return self._lines(panel, width)

    @staticmethod
    def _weights(raw: Optional[str], count: int) -> list[int]:
        if not raw:
            return [1] * count
        try:
            parts = [max(1, int(float(p))) for p in re.split(r"[/,:]", str(raw))
                     if p.strip()]
        except ValueError:
            return [1] * count
        return parts if len(parts) == count else [1] * count

    @staticmethod
    def _partition(sizes: list[int], count: int) -> list[list[int]]:
        """Split ordered groups into contiguous, roughly balanced segments."""
        segments: list[list[int]] = [[] for _ in range(count)]
        if not sizes:
            return segments
        target = sum(sizes) / count
        cur = 0
        acc = 0
        for i, size in enumerate(sizes):
            if (cur < count - 1 and acc
                    and abs(acc + size - target) > abs(acc - target)):
                cur += 1
                acc = 0
            segments[cur].append(i)
            acc += size
        return segments

    def _columns(self, block: Columns, width: int) -> list[Text]:
        count = max(2, min(4, block.count or 2))
        gap = max(1, min(4, _as_int(block.options.get("gap"), 2)))
        weights = self._weights(block.options.get("weights"), count)
        usable = max(count * 4, width - gap * (count - 1))
        widths = [max(4, usable * w // sum(weights)) for w in weights]
        widths[-1] = max(4, usable - sum(widths[:-1]))

        # A heading starts a group so it stays with the blocks it introduces.
        groups: list[list[Block]] = []
        for child in block.blocks:
            if isinstance(child, Heading) or not groups:
                groups.append([child])
            else:
                groups[-1].append(child)

        ref_w = max(8, (width - gap * (count - 1)) // count)
        sizes: list[int] = []
        for group in groups:
            size = 0
            for child in group:
                if size:
                    size += 1
                size += len(self._block_lines(child, ref_w))
            sizes.append(max(1, size))
        segments = self._partition(sizes, count)

        buffers: list[list[Text]] = [[] for _ in range(count)]
        for col, indexes in enumerate(segments):
            buf: list[Text] = []
            for i in indexes:
                if buf:
                    buf.append(Text())
                for child in groups[i]:
                    if buf and buf[-1].plain.strip():
                        buf.append(Text())
                    buf.extend(self._block_lines(child, widths[col]))
            buffers[col] = buf

        divider = _as_bool(block.options.get("divider"), False)
        height = max((len(c) for c in buffers), default=0)
        out: list[Text] = []
        for r in range(height):
            row = Text(style=self.theme.on())
            for c, buf in enumerate(buffers):
                line = buf[r].copy() if r < len(buf) else Text()
                if line.cell_len > widths[c]:
                    line.truncate(widths[c], overflow="crop")
                row.append_text(line)
                spare = widths[c] - line.cell_len
                if spare > 0:
                    row.append(" " * spare, self.theme.on())
                if c < count - 1:
                    if divider:
                        row.append("│", self.theme.border)
                        row.append(" " * max(0, gap - 1), self.theme.on())
                    else:
                        row.append(" " * gap, self.theme.on())
            out.append(row)
        return out

    def _split(self, index: int) -> list[Text]:
        """Slide-level split: headline on top, then two balanced columns."""
        slide = self._active_slide
        blocks = slide.blocks
        content: list[Text] = []
        if blocks and isinstance(blocks[0], Heading):
            content.extend(self._block_lines(blocks[0], self.content_w))
            blocks = blocks[1:]
        if blocks:
            if content:
                content.append(Text())
            count = max(2, min(4, _as_int(slide.options.get("count"), 2)))
            content.extend(self._columns(Columns(count, list(blocks),
                                                 dict(slide.options)),
                                         self.content_w))
        return content

    def _toc(self, block: Toc, width: int) -> list[Text]:
        th = self.theme
        lines: list[Text] = [Text(block.options.get("title", "Agenda"),
                                  style=f"bold {th.accent2}"), Text()]
        start = max(0, _as_int(block.options.get("start"), 0))
        limit = _as_int(block.options.get("max"), 0)
        slides = self.deck.slides[start:]
        if limit:
            slides = slides[:limit]
        for offset, slide in enumerate(slides):
            index = start + offset
            title = slide.title or "(untitled)"
            if len(title) > width - 8:
                title = title[: max(0, width - 9)] + "…"
            active = index == self._current_index
            row = Text(f"{index + 1:>2} ", style=th.accent if active else th.dim)
            row.append("▸ " if active else "  ",
                       th.accent if active else th.dim)
            row.append(title, f"bold {th.accent}" if active else th.fg)
            lines.append(row)
        return self._align_lines(lines, width, block.options.get("align", "left"))

    def _center_lines(self, lines: list[Text], width: Optional[int] = None) -> list[Text]:
        width = width or self.content_w
        out = []
        for line in lines:
            pad = max(0, (width - line.cell_len) // 2)
            t = Text(" " * pad)
            t.append_text(line)
            out.append(t)
        return out

    def _block_lines(self, block: Block, width: Optional[int] = None,
                     indent: int = 0) -> list[Text]:
        width = width or self.content_w
        if isinstance(block, Heading):
            return self._lines(self._heading(block), width)
        if isinstance(block, Para):
            return self._lines(self._inline(block.text), width)
        if isinstance(block, MdTable):
            return self._center_lines(self._table(block, width), width)
        if isinstance(block, Chart):
            return self._center_lines(self._chart(block, width), width)
        if isinstance(block, Code):
            return self._center_lines(self._code(block, width), width)
        if isinstance(block, MathBlock):
            return self._math(block, width)
        if isinstance(block, Callout):
            return self._callout(block, width)
        if isinstance(block, Columns):
            return self._columns(block, width)
        if isinstance(block, Frame):
            return self._frame(block, width)
        if isinstance(block, Toc):
            return self._toc(block, width)
        if isinstance(block, ListBlock):
            return self._list(block, width, indent)
        if isinstance(block, Quote):
            return self._quote(block, width)
        if isinstance(block, Image):
            return self._center_lines(self._image(block, width), width)
        if isinstance(block, Rule):
            return self._rule(block, width)
        return []

    @staticmethod
    def _reveal_of(block: object) -> int:
        if isinstance(block, ListItem):
            return max(0, int(block.reveal))
        raw = getattr(block, "options", {}).get("reveal")
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return 0

    def _visible_blocks(self, blocks: list[Block]) -> list[Block]:
        """Drop blocks scheduled for a later click, keeping nested ones in sync."""

        out: list[Block] = []
        for block in blocks:
            if self._reveal_of(block) > self.step:
                continue
            if isinstance(block, (Callout, Columns, Frame, Quote)):
                block = replace(block, blocks=self._visible_blocks(block.blocks))
            out.append(block)
        return out

    def _gap_before(self, block: Block, first: bool) -> int:
        if first:
            return 0
        if isinstance(block, Heading):
            if block.level <= 2:
                return 1 if self.fit else 2
            return 0 if self.fit else 1
        return 0 if self.fit else 1

    # -- frames ------------------------------------------------------------

    def _is_hero(self, slide: Slide) -> bool:
        if not slide.blocks:
            return False
        first = slide.blocks[0]
        if not isinstance(first, Heading) or first.level != 1:
            return False
        if len(slide.blocks) > 4:
            return False
        total = 0
        for block in slide.blocks[1:]:
            if not isinstance(block, (Para, Heading)):
                return False
            total += len(getattr(block, "text", ""))
        return total <= 220

    def _hero(self, index: int) -> list[Text]:
        th = self.theme
        slide = self._active_slide
        head = slide.blocks[0]
        title = gradient_text(head.text, th.accent, th.accent2)
        body: list[Text] = []
        for block in slide.blocks[1:]:
            if isinstance(block, Heading):
                t = self._inline(block.text)
                t.stylize(f"bold {th.accent2}", 0, len(t))
                body.append(t)
            else:
                body.append(self._inline(block.text, f"italic {th.dim}"))
        meta_bits = []
        if index == 0:
            if self.deck.author:
                meta_bits.append(self.deck.author)
            if self.deck.date:
                meta_bits.append(self.deck.date)
        chunks: list[Text] = []
        kicker = (slide.options.get("section") or "").strip()
        if kicker and kicker.lower() != title.plain.lower():
            chunks.append(Text(kicker.upper(), style=th.accent2))
            chunks.append(Text())
        rule_width = max(12, min(24, mdm.swidth(title.plain) // 2))
        chunks.append(Text("◆" + "─" * rule_width + "◆", style=th.accent2))
        chunks.append(Text())
        chunks.append(title)
        if body:
            chunks.append(Text())
            chunks.extend(body)
        if meta_bits:
            chunks.append(Text())
            chunks.append(Text("  ·  ".join(meta_bits), style=th.dim))
        chunks.append(Text())
        chunks.append(Text("─" * rule_width, style=th.border))

        # wrap and center each chunk
        lines: list[Text] = []
        for chunk in chunks:
            if not chunk.plain:
                lines.append(Text())
                continue
            for line in self._lines(chunk):
                pad = max(0, (self.content_w - line.cell_len) // 2)
                t = Text(" " * pad)
                t.append_text(line)
                lines.append(t)
        return lines

    def _footer_lines(self, index: int, flash: Optional[str] = None,
                      slide: Optional[Slide] = None,
                      step: int = 0,
                      page: Optional[str] = None) -> list[Text]:
        th = self.theme
        n = len(self.deck.slides)
        title = self.deck.meta.get("footer") or self.deck.title
        page = page or f"{index + 1} / {n}"
        steps = _reveal_number(slide.options.get("reveal_steps")) \
            if slide is not None else 0

        # Build the right-hand metadata from the least to the most important:
        # when space runs out the section label goes first, and the reveal
        # counter and page number always survive.
        chips: list[str] = []
        if slide is not None:
            section = slide.options.get("section") or slide.options.get("subtitle")
            if section:
                chips.append(section)
        if self.clock:
            elapsed = max(0, int(time.monotonic() - self.started))
            chips.append(f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        if self.max_scroll > 0 and slide is not None:
            chips.append(f"↕ {self.scroll_y + 1}/{self.max_scroll + 1}")
        if steps:
            chips.append(f"● {step}/{steps}")
        right_budget = max(0, min(self.width // 2,
                                  self.width - mdm.swidth(page) - 5))
        chosen = list(chips)
        while chosen and mdm.swidth(" · ".join(chosen)) > right_budget:
            chosen.pop(0)
        joined = _cellfit(" · ".join(chosen), right_budget)
        right = (joined + "   " if joined else "") + page

        # Hints live in the middle; a flash message takes their place so the
        # deck title is never truncated just to show a transient note.
        center = ""
        if flash:
            if self.width >= 60:
                center = _cellfit(flash, max(12, self.width // 2))
        elif self.width >= 78:
            center = "space  build" if steps else "?  help"
        if center and mdm.swidth(right) + mdm.swidth(center) + 8 > self.width:
            center = _cellfit(center,
                              max(0, self.width - mdm.swidth(right) - 8))
        left_budget = max(0, self.width - mdm.swidth(right)
                          - mdm.swidth(center) - (4 if center else 3))
        left = _cellfit(flash if (flash and not center) else title, left_budget)
        center_style = f"bold {th.accent}" if flash else th.dim

        line = Text(style=th.on())
        line.append(" " + left, style=th.dim)
        used = 1 + mdm.swidth(left)
        if center:
            line.append(" ", style=th.dim)
            line.append(center, style=center_style)
            line.append(" ", style=th.dim)
            used += mdm.swidth(center) + 2
        fill = max(0, self.width - used - mdm.swidth(right) - 1)
        if fill:
            line.append(" " * fill, style=th.dim)
        line.append(right + " ", style=th.dim)

        frac = (index + 1) / max(1, n)
        filled = round(self.width * frac)
        bar = Text(style=th.on())
        bar.append("━" * filled, style=th.accent)
        bar.append("─" * (self.width - filled), style=th.border)
        return [line, bar]

    def _blank_frame(self) -> list[Text]:
        return [Text(" " * self.width, style=self.theme.on())
                for _ in range(self.height)]

    def _draw_scrollbar(self, frame: list[Text], avail: int, total: int,
                        viewport: int) -> None:
        """Show a slim scrollbar in the right margin when content overflows."""
        if self.max_scroll <= 0 or self.width < 24:
            return
        x = self.width - 1
        track = max(1, avail - 2)
        thumb = max(1, min(track, round(track * viewport / max(1, total))))
        pos = round((self.scroll_y / self.max_scroll) * (track - thumb))
        for r in range(track):
            line = frame[1 + r]
            glyph = "┃" if pos <= r < pos + thumb else "┆"
            plain = line.plain
            if len(plain) < self.width:
                plain = plain.ljust(self.width)
            line.plain = plain[:x] + glyph + plain[x + 1:]

    def _compose(self, content: list[Text], index: int,
                 flash: Optional[str] = None, center: bool = True,
                 slide: Optional[Slide] = None,
                 step: int = 0) -> list[Text]:
        th = self.theme
        footer_h = 2 if self.footer else 0
        avail = self.height - footer_h
        # Leave one quiet row above the footer so dense slides never collide
        # with the progress bar.
        bottom = avail - 1 if self.footer else avail
        viewport = max(1, bottom - 1)
        if len(content) <= viewport:
            self.max_scroll = 0
            self.scroll_y = 0
            top = max(1, 1 + (viewport - len(content)) // 2) if center else 1
        else:
            self.max_scroll = len(content) - viewport
            self.scroll_y = max(0, min(self.scroll_y, self.max_scroll))
            top = 1
        frame = self._blank_frame()
        visible = content[self.scroll_y:self.scroll_y + viewport]
        for r, line in enumerate(visible):
            y = top + r
            if y >= bottom:
                break
            if line.cell_len > self.content_w:
                line = line.copy()
                line.truncate(self.content_w, overflow="crop")
            row = Text(" " * self.left, style=th.on())
            row.append_text(line)
            pad = self.width - self.left - line.cell_len
            if pad > 0:
                row.append(" " * pad, style=th.on())
            row.stylize(th.on())
            frame[y] = row
        self._draw_scrollbar(frame, avail, len(content), viewport)
        self.frame_placements = []
        if self.pending:
            by_marker = {p.marker: p for p in self.pending}
            seen: set[str] = set()
            for y, line in enumerate(frame):
                plain = line.plain
                for marker, p in by_marker.items():
                    if marker in seen:
                        continue
                    idx = plain.find(marker)
                    if idx < 0:
                        continue
                    col = sum(mdm.swidth(ch) for ch in plain[:idx])
                    # Hide the private-use marker even if the placement is
                    # skipped; the image itself covers this cell otherwise.
                    line.plain = plain[:idx] + " " + plain[idx + 1:]
                    plain = line.plain
                    if y + p.rows > avail or col + p.cols > self.width:
                        continue
                    self.frame_placements.append(
                        Placement(y, col, p.path, p.cols, p.rows))
                    seen.add(marker)
        if self.footer:
            f1, f2 = self._footer_lines(index, flash, slide, step)
            frame[self.height - 2] = f1
            frame[self.height - 1] = f2
        return frame

    def _section(self, index: int) -> list[Text]:
        th = self.theme
        slide = self._active_slide
        chunks: list[Text] = [Text("─" * 12, style=th.accent), Text()]
        title = gradient_text(slide.title, th.accent, th.accent2)
        chunks.append(title)
        sub = slide.options.get("subtitle")
        if not sub:
            for block in slide.blocks[1:]:
                if isinstance(block, Para):
                    sub = block.text
                    break
        if sub:
            chunks.append(Text())
            chunks.append(self._inline(sub, f"italic {th.dim}"))
        lines: list[Text] = []
        for chunk in chunks:
            if not chunk.plain:
                lines.append(Text())
                continue
            for line in self._lines(chunk):
                pad = max(0, (self.content_w - line.cell_len) // 2)
                t = Text(" " * pad)
                t.append_text(line)
                lines.append(t)
        return lines

    def render_slide(self, index: int, flash: Optional[str] = None,
                     step: int = 0) -> list[Text]:
        self.pending = []
        self.frame_placements = []
        index = max(0, min(index, len(self.deck.slides) - 1))
        self.step = max(0, step)
        original = self.deck.slides[index]
        slide = replace(original,
                        blocks=self._visible_blocks(original.blocks))
        self._active_slide = slide
        self._current_index = index
        self._apply_width(slide)
        layout = (slide.options.get("layout") or "").strip().lower()
        if layout in ("title", "hero") or (not layout and self._is_hero(slide)):
            return self._compose(self._hero(index), index, flash,
                                 slide=slide, step=self.step)
        if layout in ("section", "divider", "chapter"):
            return self._compose(self._section(index), index, flash,
                                 slide=slide, step=self.step)
        if layout in ("split", "columns", "two-column"):
            return self._compose(self._split(index), index, flash,
                                 slide=slide, step=self.step)
        content: list[Text] = []
        for k, block in enumerate(slide.blocks):
            gap = self._gap_before(block, k == 0)
            content.extend([Text()] * gap)
            content.extend(self._block_lines(block))
        center = layout not in ("top", "left", "start")
        return self._compose(content, index, flash, center=center,
                             slide=slide, step=self.step)

    def render_blank(self) -> list[Text]:
        self.pending = []
        self.frame_placements = []
        frame = self._blank_frame()
        if self.footer:
            f1, f2 = self._footer_lines(0)
            frame[self.height - 2] = Text(" " * self.width, style=self.theme.on())
            frame[self.height - 1] = f2
        return frame

    def render_help(self, page: int = 0) -> list[Text]:
        self.pending = []
        self.frame_placements = []
        th = self.theme
        panel_w, cols, content_rows, pages, hint, full = _help_layout(
            self.width, self.height)
        page = max(0, min(page, pages - 1))
        inner = panel_w - 2
        key_rows = content_rows - 1 if hint else content_rows
        chunk = HELP_ROWS[page * key_rows * cols:(page + 1) * key_rows * cols]

        def right_pad(text: str, width: int) -> str:
            return text + " " * max(0, width - mdm.swidth(text))

        def left_pad(text: str, width: int) -> str:
            return " " * max(0, width - mdm.swidth(text)) + text

        def cell(row: Optional[tuple[str, str, str, str]],
                 width: int) -> Text:
            line = Text(style=th.on())
            if row is None:
                line.append(" " * width, style=th.on())
                return line
            key = row[0] if full else row[2]
            desc = row[1] if full else row[3]
            key_w = max(1, min(width - 3, mdm.swidth(key)))
            desc_w = max(1, width - key_w - 2)
            line.append(left_pad(key, key_w), f"bold {th.accent}")
            line.append("  ", style=th.dim)
            line.append(right_pad(_cellfit(desc, desc_w), desc_w),
                         th.fg if row else th.dim)
            return line

        lines: list[Text] = []
        if cols == 2:
            half = key_rows
            for r in range(key_rows):
                left = chunk[r] if r < len(chunk) else None
                right = chunk[half + r] if half + r < len(chunk) else None
                col_w = (inner - 2) // 2
                pair = cell(left, col_w)
                pair.append("  ", style=th.dim)
                pair.append_text(cell(right, inner - col_w - 2))
                lines.append(pair)
        else:
            for r in range(key_rows):
                lines.append(cell(chunk[r] if r < len(chunk) else None,
                                  inner))
        if hint:
            if inner >= 28:
                note = f"←/→ page {page + 1}/{pages}  ·  any key closes"
            else:
                note = "→ page  q close"
            note = _cellfit(note, inner)
            pad = max(0, inner - mdm.swidth(note))
            line = Text(" " * (pad // 2), style=th.on())
            line.append(note, th.dim)
            line.append(" " * (pad - pad // 2), style=th.on())
            lines.append(line)
        while len(lines) < content_rows:
            lines.append(Text(" " * inner, style=th.on()))

        label = "unveil" if pages == 1 else f"unveil {page + 1}/{pages}"
        top = _help_border("╭", "╮", label, inner, th.accent, th.on())
        bottom = _help_border("╰", "╯",
                              "any key to close" if pages == 1 and
                              inner >= 18 else "",
                              inner, th.accent, th.on())
        side = Text("│", style=th.accent)
        framed = [top]
        for line in lines:
            row = Text()
            row.append_text(side)
            row.append_text(line)
            row.append_text(side)
            framed.append(row)
        framed.append(bottom)
        return self._center_panel(framed)


    def _center_panel(self, lines: list[Text]) -> list[Text]:
        th = self.theme
        frame = self._blank_frame()
        h = len(lines)
        top = max(0, (self.height - h) // 2)
        for r, line in enumerate(lines[: self.height]):
            left = max(0, (self.width - line.cell_len) // 2)
            row = Text(" " * left, style=th.on())
            row.append_text(line)
            pad = self.width - left - line.cell_len
            if pad > 0:
                row.append(" " * pad, style=th.on())
            row.stylize(th.on())
            frame[top + r] = row
        return frame

    def render_notes(self, index: int) -> list[Text]:
        self.pending = []
        self.frame_placements = []
        th = self.theme
        index = max(0, min(index, len(self.deck.slides) - 1))
        slide = self.deck.slides[index]
        body = Text(slide.notes or "No notes for this slide.", style=th.fg)
        nxt = ""
        if index + 1 < len(self.deck.slides):
            nxt = f"   next: {self.deck.slides[index + 1].title}"
        panel = Panel(
            body, box=box.ROUNDED, border_style=th.accent2,
            title=f" notes · slide {index + 1} ",
            subtitle=f" s to close{nxt} ",
            padding=(1, 2), style=th.on(),
        )
        lines = self._lines(panel, min(self.width - 4, 88))
        return self._center_panel(lines)

    def render_overview(self, selected: int) -> list[Text]:
        self.pending = []
        self.frame_placements = []
        th = self.theme
        slides = self.deck.slides
        n = len(slides)
        cols = 3 if self.width >= 88 else 2 if self.width >= 56 else 1
        gap = 2
        card_w = max(18, (self.width - 2 - gap * (cols - 1)) // cols)
        card_h = 3
        rows_that_fit = max(1, (self.height - 4) // (card_h + 1))
        per_page = cols * rows_that_fit
        start = 0
        if n > per_page:
            start = selected - per_page // 2
            start = max(0, min(start, n - per_page))
        shown = slides[start:start + per_page]
        rows = max(1, _math.ceil(len(shown) / cols))

        canvas = Canvas(self.width, self.height, th.bg)
        canvas.put(2, 0, "Slides", f"bold {th.accent}")
        canvas.put(max(2, self.width - len(f"{n} slides") - 2), 0,
                   f"{n} slides", th.dim)
        top = max(2, (self.height - rows * (card_h + 1)) // 2)
        for k, slide in enumerate(shown):
            r, c = divmod(k, cols)
            x = 1 + c * (card_w + gap)
            y = top + r * (card_h + 1)
            idx = start + k
            cur = idx == selected
            border = th.accent if cur else th.border
            title_style = f"bold {th.accent}" if cur else th.fg
            num_style = th.accent2 if cur else th.dim
            canvas.put(x, y, "╭" + "─" * (card_w - 2) + "╮", border)
            canvas.put(x, y + 1, "│", border)
            canvas.put(x + 2, y + 1, f"{idx + 1:>2}", num_style)
            title = slide.title or "(untitled)"
            room = card_w - 7
            if len(title) > room:
                title = title[: max(0, room - 1)] + "…"
            canvas.put(x + 5, y + 1, title, title_style)
            canvas.put(x + card_w - 1, y + 1, "│", border)
            canvas.put(x, y + 2, "╰" + "─" * (card_w - 2) + "╯", border)
        hint = "↑↓←→ move   ·   enter jump   ·   esc close"
        canvas.put(max(2, (self.width - len(hint)) // 2), self.height - 1,
                   hint, th.dim)
        return canvas.to_lines()
