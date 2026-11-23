"""Tests for image paths and Kitty placements."""

from __future__ import annotations

import struct
import sys
import tempfile
import zlib
from pathlib import Path

from unveil import images
from unveil.md import Image, parse_deck
from unveil.render import Renderer
from unveil.theme import get_theme


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


def _png(width: int, height: int) -> bytes:
    raw = b"".join(b"\x00" + b"\xff\x33\x66" * width
                   for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw))
        + _chunk(b"IEND", b"")
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as root:
        target = Path(root) / "shot.png"
        target.write_bytes(_png(20, 10))
        assert images.image_size(target) == (20, 10)

        deck = parse_deck(
            "---\ntitle: t\n---\n\n# Pictures\n\nshot.png\n\n"
            "<!-- image: shot.png width=30 alt=\"Second\" -->\n",
            "t",
        )
        pictures = [b for b in deck.slides[0].blocks if isinstance(b, Image)]
        assert len(pictures) == 2
        assert pictures[0].src == "shot.png"
        assert pictures[0].alt == "Shot"
        assert pictures[1].options["width"] == "30"

        renderer = Renderer(deck, get_theme("midnight"), 60, 20, True,
                            graphics=True, math_engine="unicode",
                            base_dir=root)
        frame = renderer.render_slide(0)
        assert renderer.frame_placements, renderer.pending
        assert all(Path(p.path).name == "shot.png"
                   for p in renderer.frame_placements)
        assert not any("\ue000" in line.plain for line in frame)

        plain = Renderer(deck, get_theme("midnight"), 60, 20, True,
                         graphics=False, math_engine="unicode",
                         base_dir=root)
        text = "\n".join(line.plain for line in plain.render_slide(0))
        assert "shot.png" in text
        assert "20×10 px" in text

        dumped = Renderer(deck, get_theme("midnight"), 60, 20, True,
                          graphics=False, math_engine="unicode",
                          base_dir=root, dump=True)
        dump_lines = [line.plain.rstrip()
                      for line in dumped.render_slide(0)]
        borders = [line.strip() for line in dump_lines
                   if line.lstrip().startswith("╭")]
        assert borders and max(len(line) for line in borders) < 60, borders

        side = parse_deck(
            "---\ntitle: t\n---\n\n# Side\n\n"
            "<!-- columns: 2 -->\n\n"
            "### Pic\n\nshot.png\n\n"
            "### Words\n\n- left\n- right\n\n"
            "<!-- endcolumns -->\n",
            "t",
        )
        side_renderer = Renderer(side, get_theme("midnight"), 60, 24, True,
                                 graphics=True, math_engine="unicode",
                                 base_dir=root)
        side_frame = side_renderer.render_slide(0)
        assert side_renderer.frame_placements
        assert side_renderer.frame_placements[0].col < 30
        assert any("Words" in line.plain and line.plain.find("Words") > 30
                   for line in side_frame)

        missing = parse_deck("---\ntitle: t\n---\n\n# Missing\n\nnope.png\n",
                             "t")
        missing_renderer = Renderer(
            missing, get_theme("midnight"), 60, 20, True,
            graphics=False, math_engine="unicode", base_dir=root,
        )
        missing_text = "\n".join(
            line.plain for line in missing_renderer.render_slide(0))
        assert "missing file" in missing_text

    print("image: ok")
    return 0


def test_images() -> None:
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
