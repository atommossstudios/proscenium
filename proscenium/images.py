"""Image discovery, sizing and PNG preparation for Kitty placements.

Proscenium transmits PNG bytes through the Kitty graphics protocol.  Deck authors
can point at any common raster image (or an SVG/PDF); this module reads the
intrinsic size directly from the file header where possible and uses
ImageMagick only to normalise non-PNG sources into a cached PNG.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_VERSION = "1"
_SUFFIXES = {
    ".png", ".apng", ".jpg", ".jpeg", ".jpe", ".gif", ".webp", ".bmp",
    ".tif", ".tiff", ".svg", ".pdf", ".avif", ".heic", ".heif",
}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_HEADER_LIMIT = 512 * 1024


@dataclass(frozen=True)
class PreparedImage:
    """An image ready for transmission, with its pixel dimensions."""

    path: Path
    width: int
    height: int
    converted: bool = False


def cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    path = Path(base) / "proscenium" / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def looks_like_image(path: str) -> bool:
    """Cheap filename check used by the markdown parser."""

    suffix = Path(os.path.expanduser(os.path.expandvars(path))).suffix.lower()
    return suffix in _SUFFIXES


# --------------------------------------------------------------------------
# intrinsic size parsers
# --------------------------------------------------------------------------

def _png_size(data: bytes) -> Optional[tuple[int, int]]:
    if len(data) >= 24 and data[:8] == _PNG_SIGNATURE:
        w, h = struct.unpack(">II", data[16:24])
        return (w, h) if w and h else None
    return None


def _gif_size(data: bytes) -> Optional[tuple[int, int]]:
    if len(data) >= 10 and data[:6] in (b"GIF87a", b"GIF89a"):
        w, h = struct.unpack("<HH", data[6:10])
        return (w, h) if w and h else None
    return None


def _bmp_size(data: bytes) -> Optional[tuple[int, int]]:
    if len(data) >= 26 and data[:2] == b"BM":
        w, h = struct.unpack("<ii", data[18:26])
        return (abs(w), abs(h)) if w and h else None
    return None


_JPEG_SOF = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}


def _jpeg_size(data: bytes) -> Optional[tuple[int, int]]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if marker == 0xDA:  # start of scan; dimensions already found if any
            break
        seglen = struct.unpack(">H", data[i:i + 2])[0]
        if seglen < 2 or i + seglen > len(data):
            break
        if marker in _JPEG_SOF:
            h, w = struct.unpack(">HH", data[i + 3:i + 7])
            return (w, h) if w and h else None
        i += seglen
    return None


def _webp_size(data: bytes) -> Optional[tuple[int, int]]:
    if len(data) < 16 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    kind = data[12:16]
    if kind == b"VP8X" and len(data) >= 30:
        w = int.from_bytes(data[24:27], "little") + 1
        h = int.from_bytes(data[27:30], "little") + 1
        return (w, h)
    if kind == b"VP8 " and len(data) >= 30:
        if data[23:26] != b"\x9d\x01\x2a":
            return None
        w = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        h = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return (w, h) if w and h else None
    if kind == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        b0, b1, b2, b3 = data[21:25]
        w = 1 + (b0 | ((b1 & 0x3F) << 8))
        h = 1 + (((b1 & 0xC0) >> 6) | (b2 << 2) | ((b3 & 0x0F) << 10))
        return (w, h)
    return None


_SVG_NUM = r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?"


def _svg_size(data: bytes) -> Optional[tuple[int, int]]:
    try:
        text = data[:8192].decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return None
    tag = re.search(r"<svg\b[^>]*>", text, re.I | re.S)
    if not tag:
        return None
    attrs = tag.group()
    width = re.search(r"\bwidth\s*=\s*[\"']\s*(" + _SVG_NUM + r")", attrs, re.I)
    height = re.search(r"\bheight\s*=\s*[\"']\s*(" + _SVG_NUM + r")", attrs, re.I)
    if width and height:
        return (max(1, int(float(width.group(1)))),
                max(1, int(float(height.group(1)))))
    viewbox = re.search(
        r"\bviewBox\s*=\s*[\"']\s*[\d.\s+-]+?\s+(" + _SVG_NUM
        + r")\s+(" + _SVG_NUM + r")[\"']", attrs, re.I)
    if viewbox:
        return (max(1, int(float(viewbox.group(1)))),
                max(1, int(float(viewbox.group(2)))))
    return None


_PARSERS = (_png_size, _gif_size, _bmp_size, _jpeg_size, _webp_size, _svg_size)


def _identified_size(path: Path) -> Optional[tuple[int, int]]:
    if shutil.which("magick"):
        args = ["magick", "identify", "-format", "%w %h", str(path)]
    elif shutil.which("identify"):
        args = ["identify", "-format", "%w %h", str(path)]
    else:
        return None
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=10, check=False,
        )
        parts = result.stdout.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return (int(parts[0]), int(parts[1]))
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def image_size(path: Path) -> Optional[tuple[int, int]]:
    """Return the intrinsic ``(width, height)`` of *path*, or None."""

    try:
        with path.open("rb") as fh:
            data = fh.read(_HEADER_LIMIT)
    except OSError:
        return None
    for parser in _PARSERS:
        size = parser(data)
        if size:
            return size
    return _identified_size(path)


# --------------------------------------------------------------------------
# preparation
# --------------------------------------------------------------------------

def resolve_path(path: str, base_dir: Optional[str] = None) -> Path:
    """Expand *path* and resolve relative names against *base_dir*."""

    expanded = os.path.expanduser(os.path.expandvars(str(path).strip()))
    result = Path(expanded)
    if not result.is_absolute() and base_dir:
        result = Path(base_dir) / result
    return result


def _cache_path(src: Path, max_w: int, max_h: int) -> Path:
    try:
        stat = src.stat()
        stamp = f"{src.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        stamp = str(src.resolve())
    key = hashlib.sha1(f"{_VERSION}:{max_w}x{max_h}:{stamp}".encode()).hexdigest()
    return cache_root() / f"{key}.png"


def _converter() -> Optional[str]:
    return shutil.which("magick") or shutil.which("convert")


def prepare_image(path: str, base_dir: Optional[str] = None,
                  max_width_px: Optional[int] = None,
                  max_height_px: Optional[int] = None) -> Optional[PreparedImage]:
    """Return a PNG suitable for Kitty, converting non-PNG sources on demand.

    PNGs are used as-is; Kitty scales them to the reserved cell rectangle, so
    resampling them here would only cost time.  Other formats are converted
    through ImageMagick into the proscenium image cache, optionally shrunk to the
    requested pixel bounds.  Returns None when the file cannot be read or
    converted.
    """

    src = resolve_path(path, base_dir)
    if not src.is_file():
        return None
    size = image_size(src)
    if not size:
        return None
    width, height = size
    if src.suffix.lower() in (".png", ".apng"):
        return PreparedImage(src, width, height)

    tool = _converter()
    if not tool:
        return None

    max_w = max(1, int(max_width_px or width))
    max_h = max(1, int(max_height_px or height))
    out = _cache_path(src, max_w, max_h)
    if out.is_file() and out.stat().st_size > 0:
        cached = image_size(out)
        if cached:
            return PreparedImage(out, cached[0], cached[1], True)

    scale = min(1.0, max_w / width, max_h / height)
    target_w = max(1, round(width * scale))
    target_h = max(1, round(height * scale))
    args = [tool]
    if tool.endswith("magick"):
        args.append(str(src))
        args += ["-auto-orient", "-strip"]
        if (target_w, target_h) != (width, height):
            args += ["-resize", f"{target_w}x{target_h}>"]
        args.append(str(out))
    else:  # ImageMagick 6 `convert`
        args += [str(src), "-auto-orient", "-strip"]
        if (target_w, target_h) != (width, height):
            args += ["-resize", f"{target_w}x{target_h}>"]
        args.append(str(out))
    try:
        result = subprocess.run(args, capture_output=True, timeout=60,
                                check=False)
        if result.returncode != 0 or not out.is_file():
            return None
        converted = image_size(out)
        if not converted:
            return None
    except (OSError, subprocess.SubprocessError):
        return None
    return PreparedImage(out, converted[0], converted[1], True)
