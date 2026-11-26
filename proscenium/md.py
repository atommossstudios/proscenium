"""Markdown subset parser for proscenium decks.

In addition to ordinary markdown, proscenium understands *directives*.  The short
form is ``@kind key=value`` (or ``<uv kind key=value>``); the original HTML
comment form ``<!-- kind: key=value ... -->`` still works too.  Directives
configure the slide (``@slide``), the next block (``@eq``, ``@table``,
``@code``, ``@chart``), wrap the next block in a callout (``@note``, ``@tip``,
…), or group blocks into columns (``@columns`` … ``@qcolumns``).  A
``@chart`` directive turns the following table into a chart; a fenced
``chart`` block can also carry its own CSV-like data.  Images can be written
as ``![alt](path)``, with ``@image``, or as a bare line containing just the
path.  Unknown directives are ignored; ``@notes`` … ``@qnotes`` keeps its old meaning.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------
# inline spans
# --------------------------------------------------------------------------

@dataclass
class Span:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    strike: bool = False
    link: Optional[str] = None
    math: bool = False


def parse_inline(src: str) -> list[Span]:
    spans: list[Span] = []
    buf: list[str] = []
    bold = italic = strike = False

    def flush() -> None:
        if buf:
            spans.append(Span("".join(buf), bold=bold, italic=italic,
                              strike=strike))
            buf.clear()

    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == "\\" and i + 1 < n:
            nxt = src[i + 1]
            if nxt in "\\`*_{}[]()#+-.!|$>~":
                buf.append(nxt)
                i += 2
                continue
            if nxt == "n":
                buf.append("\n")
                i += 2
                continue
        if src.startswith("**", i) or src.startswith("__", i):
            flush()
            bold = not bold
            i += 2
            continue
        if src.startswith("~~", i):
            flush()
            strike = not strike
            i += 2
            continue
        if ch == "`":
            j = src.find("`", i + 1)
            if j != -1:
                flush()
                spans.append(Span(src[i + 1:j], code=True))
                i = j + 1
                continue
        if ch in "*_":
            # only treat _ as emphasis at word boundaries
            if ch == "_" and i > 0 and src[i - 1].isalnum():
                buf.append(ch)
                i += 1
                continue
            flush()
            italic = not italic
            i += 1
            continue
        if ch == "$" and not src.startswith("$$", i):
            j = i + 1
            while j < n:
                if src[j] == "$" and src[j - 1] != "\\":
                    break
                j += 1
            if (j < n and j > i + 1 and not src[i + 1].isspace()
                    and not src[j - 1].isspace()):
                flush()
                spans.append(Span(src[i + 1:j], math=True))
                i = j + 1
                continue
        if src.startswith("![", i):
            m = re.match(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", src[i:])
            if m:
                flush()
                spans.append(Span(m.group(1) or m.group(2), italic=True,
                                  link=m.group(2)))
                i += m.end()
                continue
        if ch == "[":
            m = re.match(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", src[i:])
            if m:
                flush()
                spans.append(Span(m.group(1), link=m.group(2)))
                i += m.end()
                continue
        if ch == "<":
            m = re.match(r"<[^>]+>", src[i:])
            if m:
                i += m.end()
                continue
        buf.append(ch)
        i += 1
    flush()
    return spans


def plain_inline(src: str) -> str:
    out = []
    for span in parse_inline(src):
        if span.math:
            out.append(span.text)
        elif span.link:
            out.append(span.text)
        else:
            out.append(span.text)
    return "".join(out)


# --------------------------------------------------------------------------
# directives
# --------------------------------------------------------------------------

#: Directive aliases.  Bare admonition kinds are also accepted.
DIRECTIVE_ALIASES = {
    "layout": "slide", "section": "slide", "clock": "slide",
    "equation": "eq", "math": "eq", "formula": "eq",
    "tbl": "table", "tabular": "table",
    "charts": "chart", "graph": "chart", "viz": "chart",
    "visualization": "chart", "visualisation": "chart",
    "img": "image", "images": "image", "picture": "image",
    "pic": "image", "photo": "image", "figure": "image",
    "admonition": "callout", "note": "callout", "info": "callout",
    "tip": "callout", "hint": "callout", "success": "callout",
    "warning": "callout", "caution": "callout", "danger": "callout",
    "error": "callout", "quote": "callout",
    "cols": "columns", "colbreak": "endcolumns", "endcol": "endcolumns",
    "qcol": "endcolumns", "qcolumns": "endcolumns",
    "build": "reveal", "step": "reveal", "reveal_items": "reveal",
    "agenda": "toc", "contents": "toc", "outline": "toc",
    "panel": "border", "frame": "border",
    "endpanel": "endborder", "endframe": "endborder",
    "qpanel": "endborder", "qframe": "endborder", "qborder": "endborder",
    "qnotes": "endnotes", "notes_end": "endnotes",
}

_DIRECTIVE_RE = re.compile(r"^<!--\s*([\w-]+)\s*:?\s*(.*?)\s*-->\s*$", re.S)

_IMAGE_SUFFIXES = (
    ".png", ".apng", ".jpg", ".jpeg", ".jpe", ".gif", ".webp", ".bmp",
    ".tif", ".tiff", ".svg", ".avif", ".heic", ".heif", ".pdf",
)
_BARE_IMAGE_RE = re.compile(r"^(?:\"([^\"]+)\"|'([^']+)'|(\S+))\s*$")

# Short directive syntax.  ``@reveal`` and ``<uv reveal>`` are both rewritten
# to the HTML-comment form the rest of the parser already understands, so the
# two syntaxes can be mixed freely in one deck.
_AT_DIRECTIVE_RE = re.compile(r"^\s*@([\w-]+)\b(.*)$", re.S)
_UV_TAG_RE = re.compile(
    r"^\s*(?:uv\s*:?\s*)?<\s*(/)?\s*(?:uv\s*:?\s*)?([\w-]+)([^>]*)>\s*$",
    re.S)
_END_DIRECTIVES = {
    "columns": "endcolumns", "cols": "endcolumns",
    "border": "endborder", "panel": "endborder", "frame": "endborder",
}


def _short_directive(line: str) -> Optional[tuple[str, str, bool]]:
    """Return ``(kind, body, closing)`` for a short directive line."""

    match = _UV_TAG_RE.match(line)
    if match:
        closing, kind, body = match.groups()
        return kind.strip().lower(), body.strip(), bool(closing)
    match = _AT_DIRECTIVE_RE.match(line)
    if match:
        return match.group(1).strip().lower(), match.group(2).strip(), False
    return None


def _normalize_short_directives(text: str) -> str:
    """Rewrite short directives to legacy comments without touching code."""

    lines = text.split("\n")
    out: list[str] = []
    i = 0
    fence = False
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            out.append(line)
            i += 1
            continue
        found = None if fence else _short_directive(line)
        if not found:
            out.append(line)
            i += 1
            continue
        kind, body, closing = found
        alias = DIRECTIVE_ALIASES.get(kind, kind)
        if alias.startswith("end"):
            out.append(f"<!-- {kind} -->")
            i += 1
            continue
        if closing:
            out.append(f"<!-- {_END_DIRECTIVES.get(alias, 'end' + alias)} -->")
            i += 1
            continue
        if kind == "title" and body.startswith("="):
            kind, body = "slide", "title" + body
        if alias == "notes" and not body:
            j = i + 1
            parts: list[str] = []
            while j < len(lines):
                nxt = _short_directive(lines[j])
                if nxt and (DIRECTIVE_ALIASES.get(nxt[0], nxt[0]) in
                            ("endnotes", "notes")):
                    break
                parts.append(lines[j])
                j += 1
            inner = "\n".join(parts).strip()
            out.append("<!-- notes:\n" + inner + "\n-->")
            i = j + 1 if j < len(lines) else j
            continue
        suffix = ":" if body else ""
        out.append(f"<!-- {kind}{suffix} {body} -->")
        i += 1
    return "\n".join(out)


def _image_suffix(value: str) -> bool:
    return os.path.splitext(value.strip().strip("\"'<>()"))[1].lower() \
        in _IMAGE_SUFFIXES


def bare_image_path(text: str) -> Optional[str]:
    """Return a path when *text* is a standalone image reference.

    A bare line like ``assets/overview.png`` (or a quoted path containing
    spaces) is enough to insert a picture; no ``![alt](...)`` wrapper needed.
    """

    stripped = text.strip()
    if not stripped or _looks_like_block_start(stripped):
        return None
    match = _BARE_IMAGE_RE.match(stripped)
    if not match:
        return None
    path = next((part for part in match.groups() if part), None)
    if not path or not _image_suffix(path):
        return None
    if path.startswith(("http://", "https://", "data:")):
        return None
    return path


def image_alt(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path.strip()))[0]
    stem = re.sub(r"[_-]+", " ", stem)
    return stem.strip().title() or "Image"


def parse_kv(body: str) -> dict[str, str]:
    """Parse ``key=value key2="two words" flag`` into a lowercase-key dict."""

    opts: dict[str, str] = {}
    positional: list[str] = []
    i = 0
    n = len(body)

    def clean(value: str) -> str:
        low = value.lower()
        if low in ("true", "yes", "on"):
            return "true"
        if low in ("false", "no", "off"):
            return "false"
        return value

    while i < n:
        while i < n and body[i].isspace():
            i += 1
        if i >= n:
            break
        if body[i] in "\"'":
            quote = body[i]
            j = i + 1
            while j < n and body[j] != quote:
                j += 1
            if j < n:
                j += 1
        else:
            j = i
            while j < n and not body[j].isspace() and body[j] != "=":
                j += 1
        word = body[i:j]
        if j < n and body[j] == "=":
            key = word.strip().lower()
            i = j + 1
            while i < n and body[i].isspace():
                i += 1
            if i < n and body[i] in "\"'":
                quote = body[i]
                i += 1
                start = i
                while i < n and body[i] != quote:
                    i += 1
                value = body[start:i]
                i += 1
            else:
                start = i
                while i < n and not body[i].isspace():
                    i += 1
                value = body[start:i]
            if key:
                opts[key] = clean(value)
            continue
        i = j
        if word.startswith(("\"", "'")) and len(word) > 1:
            quote = word[0]
            if word.endswith(quote):
                word = word[1:-1]
        positional.append(word)

    if positional:
        first = positional[0].lower()
        consumed = -1
        if "style" not in opts and first in (
                "rounded", "square", "double", "heavy", "minimal", "none",
                "simple", "grid", "borderless", "markdown", "accent",
                "light", "plain", "card", "clean", "presentation"):
            opts["style"] = first
            consumed = 0
        elif "type" not in opts and first in (
                "bar", "hbar", "bars", "column", "vbar", "cols", "line",
                "lines", "spark", "sparkline", "stacked", "stack", "area",
                "pie", "donut", "ring", "gauge", "meter", "scatter"):
            opts["type"] = first
            consumed = 0
        image_path = None
        for idx, extra in enumerate(positional):
            if idx == consumed:
                continue
            if image_path is None and _image_suffix(extra):
                image_path = extra.strip("\"'")
                continue
            opts.setdefault(extra.lower(), "true")
        if image_path is not None:
            opts.setdefault("path", image_path)
    return opts


def parse_directive(comment: str) -> Optional[tuple[str, dict[str, str]]]:
    """Return ``(kind, options)`` when *comment* is a known directive."""

    comment = comment.strip()
    if not comment.startswith("<!--"):
        normalized = _normalize_short_directives(comment)
        if normalized != comment:
            comment = normalized
    m = _DIRECTIVE_RE.match(comment)
    if not m:
        return None
    kind = m.group(1).strip().lower()
    opts = parse_kv(m.group(2))
    kind = DIRECTIVE_ALIASES.get(kind, kind)
    known = ("slide", "eq", "table", "code", "chart", "image", "callout",
             "columns", "endcolumns", "notes", "endnotes", "colbreak",
             "toc", "rule", "border", "endborder", "reveal")
    if kind not in known:
        return None
    if kind == "reveal":
        # Accept <!-- reveal --> (auto), <!-- reveal: 2 -->,
        # <!-- reveal: items --> and <!-- reveal: step=3 -->.
        value = opts.get("reveal") or opts.get("step")
        if value is None:
            value = m.group(2).strip().strip("\"'").strip().lower() or "auto"
        opts = {"reveal": value}
    if kind == "callout":
        # ``<!-- warning: ... -->`` and ``<!-- callout: warning ... -->``
        # both name the admonition directly.
        callout_kinds = ("note", "info", "tip", "hint", "success", "warning",
                         "caution", "danger", "error", "quote")
        raw = m.group(1).strip().lower()
        if raw in callout_kinds + ("admonition",):
            opts.setdefault("kind", raw)
        elif "kind" not in opts:
            words = m.group(2).strip().split()
            candidate = (opts.get("style") or
                         (words[0].strip("\"'") if words else "")).lower()
            if candidate in callout_kinds:
                opts["kind"] = candidate
                opts.pop("style", None)
    if kind == "columns" and "count" not in opts:
        first = opts.get("style") or m.group(2).strip().strip("\"'")
        if first.isdigit():
            opts["count"] = first
    return kind, opts


# --------------------------------------------------------------------------
# block nodes
# --------------------------------------------------------------------------

@dataclass
class Block:
    pass


@dataclass
class Heading(Block):
    level: int
    text: str
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Para(Block):
    text: str
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Code(Block):
    code: str
    lang: str = ""
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class MathBlock(Block):
    latex: str
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Table(Block):
    header: list[str]
    aligns: list[str]
    rows: list[list[str]]
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Chart(Block):
    """A data visualisation built from a GFM table or fenced chart data."""

    table: Table
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Callout(Block):
    kind: str
    blocks: list[Block]
    title: str = ""
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Columns(Block):
    count: int
    blocks: list[Block]
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Toc(Block):
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class ListItem:
    text: str
    children: list[Block] = field(default_factory=list)
    checked: Optional[bool] = None
    reveal: int = 0


@dataclass
class ListBlock(Block):
    ordered: bool
    start: int
    items: list[ListItem]
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Quote(Block):
    blocks: list[Block]
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Rule(Block):
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Image(Block):
    alt: str
    src: str
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Frame(Block):
    """A decorated panel wrapping other blocks."""

    blocks: list[Block]
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Slide:
    blocks: list[Block]
    notes: str = ""
    options: dict[str, str] = field(default_factory=dict)

    @property
    def title(self) -> str:
        for block in self.blocks:
            if isinstance(block, Heading):
                return plain_inline(block.text)
        for block in self.blocks:
            if isinstance(block, Para):
                return plain_inline(block.text)[:70]
        return ""

    @property
    def section(self) -> str:
        return self.options.get("section", "")


@dataclass
class Deck:
    slides: list[Slide]
    meta: dict[str, str]
    title: str

    @property
    def author(self) -> str:
        return self.meta.get("author", "")

    @property
    def date(self) -> str:
        return self.meta.get("date", "")


# --------------------------------------------------------------------------
# block parsing
# --------------------------------------------------------------------------

FENCE_RE = re.compile(r"^\s*(```+|~~~+)\s*([\w+-]*)\s*$")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
TABLE_DELIM_RE = re.compile(
    r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$")


def _indent(line: str) -> int:
    expanded = line.expandtabs(4)
    return len(expanded) - len(expanded.lstrip())


def _strip_indent(line: str, amount: int) -> str:
    """Remove up to *amount* leading spaces, preserving relative indentation."""
    expanded = line.expandtabs(4)
    n = 0
    while n < amount and n < len(expanded) and expanded[n] == " ":
        n += 1
    return expanded[n:]


_BLOCK_START_RE = re.compile(r"^(?:[>#|]|\$\$|\\\[|<!--|-{3,})")


def _looks_like_block_start(text: str) -> bool:
    return bool(_BLOCK_START_RE.match(text))


def split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    parts = re.split(r"(?<!\\)\|", line)
    return [p.strip().replace("\\|", "|") for p in parts]


_CHART_SPLIT_RE = re.compile(r"\s*[,;|\t]\s*")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_NUMERIC_CELL_RE = re.compile(
    r"[+-]?\d+(?:\.\d+)?\s*(?:%|[A-Za-zµμ]+)?"
)


def is_chart_number(text: str) -> bool:
    """True when a cell is a number, optionally with a unit or percent."""

    cleaned = plain_inline(text).replace(",", "").strip()
    return bool(_NUMERIC_CELL_RE.fullmatch(cleaned))


def chart_number(text: str) -> Optional[float]:
    """Best-effort numeric conversion for chart cells ("12%", "1.2 ms")."""

    cleaned = str(text).replace(",", "").strip()
    match = _NUMBER_RE.search(cleaned)
    return float(match.group()) if match else None


def parse_chart_data(body: str, options: Optional[dict[str, str]] = None) -> Chart:
    """Parse fenced chart data into a :class:`Chart`.

    Lines may be ``label, value, ...`` (comma, semicolon, tab or ``|``) or
    ``key=value`` option lines.  A first row of text cells is used as series
    names; a first numeric row gets generic names.
    """

    opts = dict(options or {})
    opts.pop("__chart", None)
    rows_raw: list[list[str]] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line and not any(sep in line for sep in ",;|	"):
            kv = parse_kv(line)
            if kv and all(_NUMBER_RE.match(k) or k.isalpha() or "_" in k
                          for k in kv):
                opts.update(kv)
                continue
        parts = [part.strip() for part in _CHART_SPLIT_RE.split(line)]
        parts = [part for part in parts if part]
        if len(parts) >= 2:
            rows_raw.append(parts)

    if not rows_raw:
        table = Table(["Value"], ["left"], [])
        return Chart(table, opts)

    first = rows_raw[0]
    if all(is_chart_number(cell) for cell in first[1:]):
        header = [f"Series {k + 1}" for k in range(len(first) - 1)]
        data_rows = rows_raw
    else:
        header = first
        data_rows = rows_raw[1:]

    rows: list[list[str]] = []
    for parts in data_rows:
        cells = [parts[0]]
        for cell in parts[1:]:
            num = chart_number(cell)
            cells.append("" if num is None else str(num))
        rows.append(cells)
    aligns = ["left"] + ["right"] * max(0, len(header) - 1)
    return Chart(Table(header, aligns, rows), opts)


def _read_comment(lines: list[str], i: int) -> tuple[str, int]:
    """Read one (possibly multi-line) HTML comment starting at *i*."""

    chunk = [lines[i]]
    j = i
    while "-->" not in chunk[-1] and j + 1 < len(lines):
        j += 1
        chunk.append(lines[j])
    return "\n".join(chunk), j + 1


def _attach(block: Block, pending: dict[str, str],
            callout: dict[str, str]) -> Block:
    """Apply the pending directive options to *block*."""

    if pending.get("__chart"):
        chart_opts = dict(pending)
        chart_opts.pop("__chart", None)
        pending.clear()
        if isinstance(block, Table):
            block = Chart(block, chart_opts)
        elif isinstance(block, Chart):
            block.options.update(chart_opts)
        else:
            block.options.update(chart_opts)

    # Block options must land on the inner block before an admonition wraps
    # it. Otherwise `<!-- note: -->\n<!-- table: lines=true -->` puts the table
    # options on the Callout, where the table renderer never sees them.
    if pending:
        block.options.update(pending)
        pending.clear()
    if callout:
        kind = callout.pop("kind", "info")
        title = callout.pop("title", "")
        block = Callout(kind, [block], title, dict(callout))
        callout.clear()
    return block


def parse_blocks(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    pending: dict[str, str] = {}
    callout: dict[str, str] = {}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        if stripped.startswith("<!--"):
            comment, j = _read_comment(lines, i)
            directive = parse_directive(comment)
            if directive:
                kind, opts = directive
                if kind == "chart":
                    pending.update(opts)
                    pending["__chart"] = "true"
                    i = j
                    continue
                if kind == "image":
                    src = opts.pop("src", None) or opts.pop("path", None)
                    if src:
                        alt = opts.pop("alt", "") or image_alt(src)
                        block_opts = dict(pending)
                        block_opts.update(opts)
                        blocks.append(_attach(Image(alt, src, block_opts),
                                              {}, callout))
                        pending.clear()
                    else:
                        pending.update(opts)
                    i = j
                    continue
                if kind == "reveal":
                    value = str(opts.get("reveal", "auto")).strip().lower()
                    if value in ("items", "item", "bullets", "bullet", "list"):
                        pending["reveal_items"] = "true"
                    else:
                        pending["reveal"] = value
                    i = j
                    continue
                if kind in ("eq", "table", "code"):
                    pending.update(opts)
                    i = j
                    continue
                if kind == "callout":
                    callout.update(opts)
                    i = j
                    continue
                if kind == "columns":
                    try:
                        count = max(2, min(4, int(opts.get("count", "2"))))
                    except ValueError:
                        count = 2
                    inner_lines: list[str] = []
                    while j < n:
                        s = lines[j].strip()
                        if s.startswith("<!--"):
                            c, nj = _read_comment(lines, j)
                            d = parse_directive(c)
                            if d and d[0] == "endcolumns":
                                j = nj
                                break
                        inner_lines.append(lines[j])
                        j += 1
                    inner = parse_blocks(inner_lines)
                    blocks.append(_attach(Columns(count, inner, opts),
                                          pending, callout))
                    i = j
                    continue
                if kind == "endcolumns":
                    i = j
                    continue
                if kind == "toc":
                    blocks.append(_attach(Toc(opts), pending, callout))
                    i = j
                    continue
                if kind == "rule":
                    # Allow both `<!-- rule: ... -->` alone and the same
                    # directive written just before `***` / `___`.
                    k = j
                    while k < n and not lines[k].strip():
                        k += 1
                    if k < n and re.match(r"^\s*(\*{3,}|_{3,})\s*$",
                                          lines[k]):
                        pending.update(opts)
                        i = j
                        continue
                    blocks.append(_attach(Rule(dict(opts)), pending, callout))
                    i = j
                    continue
                if kind == "border":
                    start = j
                    inner_lines: list[str] = []
                    k = j
                    found_end = False
                    while k < n:
                        s = lines[k].strip()
                        if s.startswith("<!--"):
                            c, nk = _read_comment(lines, k)
                            d = parse_directive(c)
                            if d and d[0] == "endborder":
                                j = nk
                                found_end = True
                                break
                        inner_lines.append(lines[k])
                        k += 1
                    if not found_end:
                        trimmed: list[str] = []
                        seen_text = False
                        for ln in inner_lines:
                            trimmed.append(ln)
                            if ln.strip():
                                seen_text = True
                            elif seen_text:
                                break
                        inner_lines = trimmed
                        j = start + len(trimmed)
                    blocks.append(_attach(
                        Frame(parse_blocks(inner_lines), opts),
                        pending, callout))
                    i = j
                    continue
                if kind == "endborder":
                    i = j
                    continue
            i = j
            continue

        m = FENCE_RE.match(line)
        if m:
            fence = m.group(1)[0]
            lang = m.group(2)
            fence_indent = _indent(line)
            j = i + 1
            body = []
            while j < n and not re.match(r"^\s*" + fence + r"{3,}\s*$", lines[j]):
                body.append(_strip_indent(lines[j], fence_indent))
                j += 1
            chart_langs = ("chart", "charts", "graph", "viz", "visualization")
            base_lang = lang.strip().lower()
            if base_lang in chart_langs or base_lang.startswith("chart-"):
                opts = dict(pending)
                opts.pop("__chart", None)
                pending.clear()
                if "-" in base_lang:
                    opts.setdefault("type", base_lang.split("-", 1)[1])
                chart = parse_chart_data("\n".join(body), opts)
                blocks.append(_attach(chart, {}, callout))
            else:
                blocks.append(_attach(Code("\n".join(body), lang),
                                      pending, callout))
            i = j + 1
            continue

        m = HEADING_RE.match(line)
        if m:
            blocks.append(_attach(
                Heading(len(m.group(1)), m.group(2).strip()), pending, callout))
            i += 1
            continue

        if stripped.startswith("$$") or stripped.startswith("\\["):
            open_tok = "$$" if stripped.startswith("$$") else "\\["
            close_tok = "$$" if open_tok == "$$" else "\\]"
            first = stripped[len(open_tok):]
            j = i
            parts: list[str] = []
            if close_tok in first:
                parts.append(first.split(close_tok)[0])
                i += 1
            else:
                if first.strip():
                    parts.append(first)
                j = i + 1
                while j < n:
                    if close_tok in lines[j]:
                        parts.append(lines[j].split(close_tok)[0])
                        j += 1
                        break
                    parts.append(lines[j])
                    j += 1
                i = j
            blocks.append(_attach(MathBlock("\n".join(parts).strip()),
                                  pending, callout))
            continue

        if stripped.startswith("\\begin{"):
            env = re.match(r"\\begin\{(\w+\*?)\}", stripped)
            j = i
            body = []
            while j < n:
                body.append(lines[j])
                if "\\end{" in lines[j]:
                    j += 1
                    break
                j += 1
            latex = "\n".join(body)
            if env and env.group(1) in ("equation", "equation*", "displaymath",
                                        "align", "align*", "gather", "gather*"):
                latex = re.sub(r"\\begin\{(equation\*?|displaymath|align\*?|gather\*?)\}", "", latex)
                latex = re.sub(r"\\end\{(equation\*?|displaymath|align\*?|gather\*?)\}", "", latex)
            blocks.append(_attach(MathBlock(latex.strip()), pending, callout))
            i = j
            continue

        # table: header + delimiter row
        if "|" in line and i + 1 < n and TABLE_DELIM_RE.match(lines[i + 1]):
            header = split_table_row(line)
            aligns = []
            for cell in split_table_row(lines[i + 1]):
                cell = cell.strip()
                if cell.startswith(":") and cell.endswith(":"):
                    aligns.append("center")
                elif cell.endswith(":"):
                    aligns.append("right")
                elif cell.startswith(":"):
                    aligns.append("left")
                else:
                    aligns.append("left")
            j = i + 2
            rows = []
            while j < n and "|" in lines[j] and lines[j].strip():
                rows.append(split_table_row(lines[j]))
                j += 1
            blocks.append(_attach(Table(header, aligns, rows), pending, callout))
            i = j
            continue

        if stripped.startswith(">"):
            j = i
            inner = []
            while j < n and lines[j].strip().startswith(">"):
                inner.append(re.sub(r"^\s*>\s?", "", lines[j]))
                j += 1
            blocks.append(_attach(Quote(parse_blocks(inner)), pending, callout))
            i = j
            continue

        m = LIST_RE.match(line)
        if m:
            lst, i = parse_list(lines, i)
            blocks.append(_attach(lst, pending, callout))
            continue

        if re.match(r"^\s*(\*{3,}|_{3,})\s*$", line):
            blocks.append(_attach(Rule(), pending, callout))
            i += 1
            continue

        m = re.match(r"^\s*!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)\s*$", line)
        if m:
            blocks.append(_attach(Image(m.group(1), m.group(2)), pending, callout))
            i += 1
            continue

        bare = bare_image_path(stripped)
        if bare:
            blocks.append(_attach(Image(image_alt(bare), bare), pending,
                                  callout))
            i += 1
            continue

        # paragraph
        para = [stripped]
        i += 1
        while i < n:
            nxt = lines[i]
            s = nxt.strip()
            if not s:
                break
            if (HEADING_RE.match(nxt) or FENCE_RE.match(nxt)
                    or s.startswith(">") or LIST_RE.match(nxt)
                    or s.startswith("$$") or s.startswith("\\[")
                    or s.startswith("<!--")
                    or re.match(r"^\s*(\*{3,}|_{3,})\s*$", nxt)
                    or bare_image_path(s)
                    or (i + 1 < n and "|" in nxt and TABLE_DELIM_RE.match(lines[i + 1]))):
                break
            para.append(s)
            i += 1
        text = ""
        for k, part in enumerate(para):
            if k:
                text += "\n" if para[k - 1].endswith("  ") or para[k - 1].endswith("\\") else " "
            text += part
        text = re.sub(r"\s*\\$", "", text)
        blocks.append(_attach(Para(text), pending, callout))
    return blocks


def parse_list(lines: list[str], i: int, indent: int = -1) -> tuple[ListBlock, int]:
    n = len(lines)
    first = LIST_RE.match(lines[i])
    assert first
    if indent < 0:
        indent = _indent(first.group(1))
    ordered = bool(re.match(r"\d", first.group(2)))
    start = int(re.match(r"(\d+)", first.group(2)).group(1)) if ordered else 1
    items: list[ListItem] = []
    while i < n:
        m = LIST_RE.match(lines[i])
        if not m:
            break
        ind = _indent(m.group(1))
        if ind != indent:
            break
        text = m.group(3)
        checked = None
        cm = re.match(r"\[([ xX])\]\s+(.*)", text)
        if cm:
            checked = cm.group(1).lower() == "x"
            text = cm.group(2)
        i += 1
        cont: list[str] = []
        children: list[Block] = []
        while i < n:
            line = lines[i]
            if not line.strip():
                # A blank line does not end the item if more indented
                # content follows (a second paragraph, code fence, or
                # nested list).  Other indented blocks (quotes, tables,
                # headings, display math) are left to the outer parser.
                j = i + 1
                while j < n and not lines[j].strip():
                    j += 1
                if j < n and _indent(lines[j]) > indent:
                    nxt = lines[j]
                    if (FENCE_RE.match(nxt)
                            or not _looks_like_block_start(nxt.strip())):
                        i = j
                        continue
                break
            mind = _indent(line)
            fence = FENCE_RE.match(line)
            if fence and mind > indent:
                fch = fence.group(1)[0]
                lang = fence.group(2)
                j = i + 1
                body: list[str] = []
                while j < n and not re.match(r"^\s*" + fch + r"{3,}\s*$", lines[j]):
                    body.append(_strip_indent(lines[j], mind))
                    j += 1
                children.append(Code("\n".join(body), lang))
                i = j + 1
                continue
            m2 = LIST_RE.match(line)
            if m2:
                ind2 = _indent(m2.group(1))
                if ind2 > indent:
                    child, i = parse_list(lines, i, ind2)
                    children.append(child)
                    continue
                break
            if mind > indent:
                cont.append(line.strip())
                i += 1
                continue
            break
        items.append(ListItem(" ".join([text] + cont), children, checked))
        if i < n and not lines[i].strip():
            j = i
            while j < n and not lines[j].strip():
                j += 1
            m2 = LIST_RE.match(lines[j]) if j < n else None
            if m2 and _indent(m2.group(1)) >= indent:
                i = j
                if _indent(m2.group(1)) > indent:
                    break
                continue
            break
    return ListBlock(ordered, start, items), i


# --------------------------------------------------------------------------
# reveal steps
# --------------------------------------------------------------------------

#: Values that ask for the next automatic build step instead of a fixed one.
_AUTO_REVEAL = {"auto", "true", "yes", "on", "blocks", "all", "build"}


def _reveal_number(value: object) -> int:
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def resolve_reveals(blocks: list[Block]) -> int:
    """Number ``auto`` reveals in reading order and return the last step.

    Explicit numbers are honoured and the automatic counter starts after the
    largest explicit step, so mixing the two styles never collides.  Steps are
    stored as strings in each block's ``options`` (and as ``ListItem.reveal``)
    where the renderer can read them.
    """

    explicit: list[int] = []

    def inspect(items: list[Block]) -> None:
        for block in items:
            step = _reveal_number(block.options.get("reveal"))
            if step:
                explicit.append(step)
            if isinstance(block, ListBlock):
                for item in block.items:
                    if item.reveal > 0:
                        explicit.append(item.reveal)
                    inspect(item.children)
            inspect(getattr(block, "blocks", []) or [])

    inspect(blocks)
    counter = max(explicit, default=0)
    last = 0

    def number() -> int:
        nonlocal counter
        counter += 1
        return counter

    def apply(items: list[Block]) -> None:
        nonlocal last
        for block in items:
            raw = block.options.get("reveal")
            if raw is not None:
                text = str(raw).strip().lower()
                if text in _AUTO_REVEAL:
                    step = number()
                else:
                    step = _reveal_number(raw)
                if step:
                    block.options["reveal"] = str(step)
                    last = max(last, step)
                else:
                    block.options.pop("reveal", None)
            if isinstance(block, ListBlock) and block.options.pop(
                    "reveal_items", None):
                for item in block.items:
                    item.reveal = item.reveal or number()
                    last = max(last, item.reveal)
                    apply(item.children)
            else:
                block.options.pop("reveal_items", None)
            apply(getattr(block, "blocks", []) or [])

    apply(blocks)
    return last


# --------------------------------------------------------------------------
# deck parsing
# --------------------------------------------------------------------------

# A bare ``@slide`` / ``<!-- slide -->`` splits; directives with options
# configure the slide and are left for parse_deck to interpret.
SLIDE_SPLIT_RE = re.compile(
    r"^\s*(?:-{3,}|<!--\s*(?:slide|new_slide|next)\s*-->)\s*$")


def split_slides(lines: list[str]) -> list[list[str]]:
    slides: list[list[str]] = []
    current: list[str] = []
    fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = not fence
        if not fence and SLIDE_SPLIT_RE.match(line):
            slides.append(current)
            current = []
            continue
        current.append(line)
    slides.append(current)
    return slides


def parse_deck(text: str, fallback_title: str = "Untitled") -> Deck:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _normalize_short_directives(text)
    lines = text.split("\n")
    meta: dict[str, str] = {}
    if lines and lines[0].strip() == "---":
        for j in range(1, min(len(lines), 80)):
            if lines[j].strip() == "---":
                body = [l for l in lines[1:j] if l.strip()]
                if all(re.match(r"^[\w-]+\s*:", l) for l in body):
                    for l in body:
                        key, _, value = l.partition(":")
                        meta[key.strip().lower()] = value.strip().strip("\"'")
                    lines = lines[j + 1:]
                break

    raw_slides = split_slides(lines)
    slides: list[Slide] = []
    for raw in raw_slides:
        notes_parts: list[str] = []
        slide_options: dict[str, str] = {}
        kept: list[str] = []
        i = 0
        while i < len(raw):
            line = raw[i]
            if line.strip().startswith("<!--"):
                comment, j = _read_comment(raw, i)
                directive = parse_directive(comment)
                if directive and directive[0] == "slide":
                    slide_options.update(directive[1])
                elif directive and directive[0] == "notes":
                    m = re.search(r"notes?\s*:\s*(.*?)-->", comment, re.S | re.I)
                    if m:
                        notes_parts.append(m.group(1).strip())
                elif directive:
                    # Block directives (eq/table/callout/columns) must survive
                    # for parse_blocks to see them.
                    kept.extend(raw[i:j])
                else:
                    m = re.search(r"notes?\s*:\s*(.*?)-->", comment, re.S | re.I)
                    if m:
                        notes_parts.append(m.group(1).strip())
                    else:
                        kept.extend(raw[i:j])
                i = j
                continue
            kept.append(line)
            i += 1
        blocks = parse_blocks(kept)
        notes = "\n\n".join(p for p in notes_parts if p)
        # Front-matter defaults: eq_style, table_style, layout, clock, ...
        defaults = {
            key: meta[key]
            for key in ("layout", "clock", "eq_style", "table_style",
                        "width", "fit", "reveal", "transition",
                        "transition_time")
            if key in meta
        }
        defaults.update(slide_options)
        reveal = str(defaults.get("reveal") or "").strip().lower()
        if reveal in _AUTO_REVEAL:
            # A built slide shows its heading immediately; everything after
            # it arrives one click at a time.
            for position, block in enumerate(blocks):
                if position == 0 and isinstance(block, Heading):
                    continue
                if isinstance(block, ListBlock):
                    block.options.setdefault("reveal_items", "true")
                else:
                    block.options.setdefault("reveal", "auto")
        elif reveal in ("items", "item", "bullets", "bullet", "list"):
            for block in blocks:
                if isinstance(block, ListBlock):
                    block.options.setdefault("reveal_items", "true")
        if blocks:
            defaults["reveal_steps"] = str(resolve_reveals(blocks))
        if blocks or notes:
            slides.append(Slide(blocks, notes, defaults))
    if not slides:
        slides = [Slide([Para("(empty deck)")])]

    title = meta.get("title") or ""
    if not title:
        title = slides[0].title or fallback_title
    return Deck(slides, meta, title)
