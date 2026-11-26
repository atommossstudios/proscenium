"""Real LaTeX typesetting for proscenium, powered by Tectonic.

Display math is compiled to a tight standalone PDF, rasterised with
``pdftoppm`` and cached on disk.  The terminal UI then paints the PNG into a
box using the Kitty graphics protocol.  If Tectonic (or ``pdftoppm``) is not
available, or a formula cannot be compiled, callers fall back to the built-in
Unicode typesetter.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import struct
import subprocess
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Bump when the preamble or image post-processing changes so stale cached
# images are not reused.
_VERSION = "3"

# Render at a fixed, crisp resolution.  The TUI scales the result to terminal
# cells, so this only affects sharpness, not layout.
_DPI = 300
_FONT_PT = 12

_PREAMBLE = r"""\documentclass[border=2pt]{standalone}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{bm}
\usepackage{xcolor}
\begin{document}
\pagecolor[HTML]{%(bg)s}
\color[HTML]{%(fg)s}
\fontsize{%(pt)d}{%(leading)d}\selectfont
%(body)s
\end{document}
"""

_ENV_ALIGN = re.compile(r"\\(begin|end)\{(?:align|flalign)\*?\}")
_ENV_GATHER = re.compile(r"\\(begin|end)\{(?:gather|multline)\*?\}")
_ENV_EQUATION = re.compile(r"\\(begin|end)\{equation\*?\}")


@dataclass(frozen=True)
class MathImage:
    """A cached PNG for one display formula."""

    path: Path
    width: int
    height: int


_AVAILABLE: Optional[bool] = None
#: Keys whose compile already failed in this process.  Without this, a deck
#: with several broken formulas runs Tectonic once per occurrence.
_FAILED: set[str] = set()


def reset_failures() -> None:
    """Forget compile failures, e.g. after installing the toolchain."""

    _FAILED.clear()


def available() -> bool:
    """Return True when the external LaTeX pipeline is usable."""

    global _AVAILABLE
    if _AVAILABLE is None:
        _AVAILABLE = bool(shutil.which("tectonic") and shutil.which("pdftoppm"))
    return _AVAILABLE


def cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    path = Path(base) / "proscenium" / "latex"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        header = fh.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", header[16:24])


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_chunks(data: bytes):
    """Yield ``(type, raw_chunk)`` pairs from a PNG byte string."""

    pos = len(_PNG_SIGNATURE)
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        end = pos + 12 + length
        if end > len(data):
            break
        yield ctype, data[pos:end]
        pos = end


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _unfilter_png(raw: bytes, width: int, height: int, bpp: int) -> list[bytes]:
    """Undo PNG row filters.  Only 8-bit, non-interlaced images are used here."""

    stride = width * bpp
    rows: list[bytes] = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        if pos + 1 + stride > len(raw):
            raise ValueError("truncated PNG image data")
        ft = raw[pos]
        cur = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if ft:
            for i in range(stride):
                a = cur[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                if ft == 1:
                    cur[i] = (cur[i] + a) & 0xFF
                elif ft == 2:
                    cur[i] = (cur[i] + b) & 0xFF
                elif ft == 3:
                    cur[i] = (cur[i] + ((a + b) >> 1)) & 0xFF
                elif ft == 4:
                    cur[i] = (cur[i] + _paeth(a, b, c)) & 0xFF
                else:
                    raise ValueError(f"unsupported PNG filter {ft}")
        rows.append(bytes(cur))
        prev = cur
    return rows


def _is_white(px: bytes, i: int, bpp: int) -> bool:
    if bpp >= 3:
        return px[i] >= 250 and px[i + 1] >= 250 and px[i + 2] >= 250
    return px[i] >= 250


def _white_row(row: bytes, bpp: int) -> bool:
    count = len(row) // bpp
    return bool(count) and sum(
        _is_white(row, i * bpp, bpp) for i in range(count)
    ) >= count * 0.95


def _white_column(rows: list[bytes], x: int, bpp: int) -> bool:
    off = x * bpp
    return bool(rows) and all(_is_white(row, off, bpp) for row in rows)


def _chunk(ctype: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + ctype + payload +
            struct.pack(">I", zlib.crc32(ctype + payload) & 0xFFFFFFFF))


def png_has_white_edge(path: Path) -> bool:
    """True when a rasterised formula still has the pdftoppm white edge."""

    data = path.read_bytes()
    if not data.startswith(_PNG_SIGNATURE):
        return False
    for ctype, raw in _png_chunks(data):
        if ctype != b"IHDR":
            continue
        width, height, depth, color, _, _, interlace = struct.unpack(
            ">IIBBBBB", raw[8:8 + 13])
        if depth != 8 or interlace or color not in (2, 6):
            return False
        bpp = 3 if color == 2 else 4
        break
    else:
        return False
    idat = b"".join(raw[8:-4] for ctype, raw in _png_chunks(data)
                   if ctype == b"IDAT")
    try:
        rows = _unfilter_png(zlib.decompress(idat), width, height, bpp)
    except (ValueError, zlib.error):
        return False
    return (_white_row(rows[-1], bpp) or
            _white_column(rows, width - 1, bpp))


def _strip_white_edge(path: Path, bg: str) -> None:
    """Remove the 1px white line pdftoppm adds to the bottom/right edge.

    ``\\pagecolor`` fills the PDF page, but at 300 dpi the fill can stop a
    fraction of a pixel short of the media box.  Poppler then paints that last
    row/column white, which shows up as a bright line beside the formula in
    the terminal.  Cropping it is lossless; the line contains no glyph data.
    """

    # A genuinely white background has no artifact to remove.
    try:
        rgb = tuple(int(bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        rgb = (0, 0, 0)
    if min(rgb) >= 250:
        return

    data = path.read_bytes()
    if not data.startswith(_PNG_SIGNATURE):
        return
    chunks = list(_png_chunks(data))
    ihdr = next((raw for ctype, raw in chunks if ctype == b"IHDR"), None)
    if ihdr is None:
        return
    width, height, depth, color, comp, filt, interlace = struct.unpack(
        ">IIBBBBB", ihdr[8:8 + 13])
    if depth != 8 or interlace or color not in (2, 6):
        return
    bpp = 3 if color == 2 else 4
    idat = b"".join(raw[8:-4] for ctype, raw in chunks if ctype == b"IDAT")
    try:
        rows = _unfilter_png(zlib.decompress(idat), width, height, bpp)
    except (ValueError, zlib.error):
        return

    original = (width, height)
    for _ in range(4):
        if rows and _white_row(rows[-1], bpp):
            rows.pop()
            height -= 1
        else:
            break
    while width > 1 and height and _white_column(rows, width - 1, bpp):
        rows = [row[:width * bpp - bpp] for row in rows]
        width -= 1
    if (width, height) == original or width < 1 or height < 1:
        return

    raw = b"".join(b"\x00" + row for row in rows)
    new_ihdr = struct.pack(">IIBBBBB", width, height, depth, color,
                           comp, filt, interlace)
    out = bytearray(_PNG_SIGNATURE)
    out += _chunk(b"IHDR", new_ihdr)
    for ctype, chunk_data in chunks:
        if ctype in (b"IHDR", b"IDAT", b"IEND"):
            continue
        out += chunk_data
    out += _chunk(b"IDAT", zlib.compress(raw, 9))
    out += _chunk(b"IEND", b"")
    path.write_bytes(bytes(out))


def _key(latex: str, fg: str, bg: str) -> str:
    digest = hashlib.sha256()
    digest.update(
        f"{_VERSION}\0{_DPI}\0{_FONT_PT}\0{fg}\0{bg}\0{latex}".encode("utf-8")
    )
    return digest.hexdigest()[:32]


def _is_binary(src: str, index: int) -> bool:
    prev = index - 1
    while prev >= 0 and src[prev].isspace():
        prev -= 1
    if prev < 0:
        return False
    return src[prev] not in "=+-*/([{,<>&|^_"


def _breakpoints(src: str) -> list[int]:
    """Find top-level places where a long formula may be broken."""

    depth = 0
    left = 0
    i = 0
    out: list[int] = []
    while i < len(src):
        ch = src[i]
        if ch == "\\":
            j = i + 1
            if j < len(src) and src[j].isalpha():
                while j < len(src) and src[j].isalpha():
                    j += 1
            else:
                j = min(len(src), i + 2)
            cmd = src[i:j]
            if cmd == r"\begin":
                return []
            if cmd == r"\left":
                left += 1
            elif cmd == r"\right":
                left = max(0, left - 1)
            elif cmd in (r"\quad", r"\qquad") and depth == 0 and left == 0:
                out.append(i)
            i = j
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif depth == 0 and left == 0:
            if ch == "=":
                out.append(i)
            elif ch in "+-" and _is_binary(src, i):
                out.append(i)
        i += 1
    return out


def _wrap_source(src: str, target_chars: int) -> Optional[str]:
    """Break a long single-line formula at top-level operators."""

    if "\\\\" in src or "\\begin{" in src:
        return None
    cuts = _breakpoints(src)
    if not cuts:
        return None
    cuts = [0] + cuts + [len(src)]
    segments = []
    for a, b in zip(cuts, cuts[1:]):
        piece = src[a:b].strip()
        if piece:
            segments.append(piece)
    if len(segments) < 2:
        return None
    lines: list[str] = []
    current = ""
    for piece in segments:
        if not current:
            current = piece
        elif len(current) + 1 + len(piece) <= target_chars:
            current += " " + piece
        else:
            lines.append(current)
            current = piece
    if current:
        lines.append(current)
    if len(lines) < 2:
        return None
    return r"\begin{gathered}" + r" \\ ".join(lines) + r"\end{gathered}"


def _body(latex: str) -> str:
    """Wrap the formula in the least surprising display-math context.

    The ``standalone`` class dislikes bare display environments such as
    ``align`` and ``\\[...\\]``.  Normalise them to environments that are
    valid inside inline math and wrap everything in ``$...$``.
    """

    src = latex.strip()
    if not src:
        return r"$\displaystyle \,$"
    src = _ENV_ALIGN.sub(r"\\\1{aligned}", src)
    src = _ENV_GATHER.sub(r"\\\1{gathered}", src)
    src = _ENV_EQUATION.sub("", src)
    if "\\\\" in src and "\\begin{" not in src:
        src = r"\begin{gathered}" + src + r"\end{gathered}"
    return r"$\displaystyle " + src + r"$"


def _compile(latex: str, fg: str, bg: str, dest: Path) -> bool:
    """Compile one formula to ``dest``.  Returns False on any failure."""

    root = cache_root()
    tmp = Path(tempfile.mkdtemp(prefix="build-", dir=str(root)))
    try:
        tex = tmp / "doc.tex"
        tex.write_text(
            _PREAMBLE
            % {
                "bg": bg.lstrip("#"),
                "fg": fg.lstrip("#"),
                "pt": _FONT_PT,
                "leading": _FONT_PT + 3,
                "body": _body(latex),
            },
            encoding="utf-8",
        )
        cmd = ["tectonic", "-X", "compile", "--outdir", str(tmp), str(tex)]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
        )
        pdf = tmp / "doc.pdf"
        if proc.returncode != 0 or not pdf.exists():
            return False
        out = tmp / "doc"
        conv = subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r",
                str(_DPI),
                "-singlefile",
                "-aa",
                "yes",
                "-aaVector",
                "yes",
                str(pdf),
                str(out),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
        png = tmp / "doc.png"
        if conv.returncode != 0 or not png.exists():
            return False
        try:
            _strip_white_edge(png, bg)
        except OSError:
            pass
        # os.replace is atomic on the same filesystem, so concurrent readers
        # never see a half-written PNG.
        os.replace(png, dest)
        return True
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _cached(latex: str, fg: str, bg: str) -> Optional[MathImage]:
    key = _key(latex, fg, bg)
    if key in _FAILED:
        return None
    png = cache_root() / f"{key}.png"
    if not png.exists():
        if not _compile(latex, fg, bg, png):
            _FAILED.add(key)
            return None
    try:
        width, height = _png_size(png)
    except (OSError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return MathImage(png, width, height)


def render(latex: str, fg: str, bg: str,
           max_width_px: Optional[int] = None) -> Optional[MathImage]:
    """Return a typeset PNG for ``latex``, or None when it cannot be built.

    When ``max_width_px`` is supplied and the formula is too wide, try a
    version broken at top-level relations/operators.  The renderer can then
    scale the result to fit instead of shrinking a single long line into
    illegibility.
    """

    if not available():
        return None
    image = _cached(latex, fg, bg)
    if image is None or not max_width_px or image.width <= max_width_px:
        return image
    target = max(20, int(len(latex) * max_width_px / image.width * 0.92))
    wrapped = _wrap_source(latex.strip(), target)
    if wrapped:
        candidate = _cached(wrapped, fg, bg)
        if candidate and candidate.width < image.width:
            return candidate
    return image
