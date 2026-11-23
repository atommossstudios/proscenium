"""Interactive terminal loop for unveil."""

from __future__ import annotations

import base64
import io
import os
import re
import select
import shutil
import signal
import sys
import termios
import time
import tty
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.text import Text

from .md import _reveal_number, parse_deck
from .render import (WIDTH_MODES, Placement, Renderer, _ellipsis,
                     blend_frames, help_page_count, normalize_transition,
                     reveal_glow)
from .theme import get_theme, theme_names

ESC = "\x1b"
SEQ = {
    "\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right", "\x1b[D": "left",
    "\x1bOA": "up", "\x1bOB": "down", "\x1bOC": "right", "\x1bOD": "left",
    "\x1b[H": "home", "\x1b[F": "end", "\x1bOH": "home", "\x1bOF": "end",
    "\x1b[1~": "home", "\x1b[4~": "end", "\x1b[7~": "home", "\x1b[8~": "end",
    "\x1b[5~": "pgup", "\x1b[6~": "pgdn", "\x1b[3~": "delete",
    "\x1b[Z": "backtab",
}


def query_terminal() -> tuple[tuple[int, int], bool]:
    """Ask the terminal for its cell size and Kitty graphics support.

    The reply is read with a short timeout so a terminal that does not
    understand either query simply falls back to the Unicode typesetter.
    """

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return (10, 20), False
    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except termios.error:
        return (10, 20), False
    buf = b""
    try:
        tty.setcbreak(fd)
        out = sys.stdout.fileno()
        os.write(out, b"\x1b_Gi=31,s=1,v=1,a=q,t=d,f=24;AAAA\x1b\\")
        os.write(out, b"\x1b[16t")
        end = time.monotonic() + 0.35
        while time.monotonic() < end:
            ready, _, _ = select.select([fd], [], [], 0.05)
            if ready:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    graphics = b"\x1b_Gi=31;OK" in buf
    match = re.search(rb"\x1b\[6;(\d+);(\d+)t", buf)
    if match:
        cell_h = int(match.group(1))
        cell_w = int(match.group(2))
        return (max(1, cell_w), max(1, cell_h)), graphics
    return (10, 20), graphics


class KeyReader:
    def __init__(self) -> None:
        self.fd = sys.stdin.fileno()
        self.buf = b""

    def poll(self, timeout: float) -> list[str]:
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if not ready:
            return []
        try:
            chunk = os.read(self.fd, 256)
        except OSError:
            return []
        if not chunk:
            return []
        self.buf += chunk
        keys, self.buf = self._parse(self.buf)
        return keys

    @staticmethod
    def _parse(buf: bytes) -> tuple[list[str], bytes]:
        keys: list[str] = []
        i = 0
        n = len(buf)
        while i < n:
            b = buf[i]
            if b == 0x1B:
                matched = False
                for seq, name in SEQ.items():
                    if buf.startswith(seq.encode(), i):
                        keys.append(name)
                        i += len(seq)
                        matched = True
                        break
                if matched:
                    continue
                if i + 1 >= n:
                    break
                if buf[i + 1:i + 2] in (b"[", b"O"):
                    j = i + 2
                    while j < n and not (0x40 <= buf[j] <= 0x7E):
                        j += 1
                    if j >= n:
                        break
                    keys.append("unknown")
                    i = j + 1
                    continue
                keys.append("esc")
                i += 1
                continue
            if b in (0x0A, 0x0D):
                keys.append("enter")
                i += 1
                continue
            if b == 0x20:
                keys.append("space")
                i += 1
                continue
            if b == 0x09:
                keys.append("tab")
                i += 1
                continue
            if b in (0x7F, 0x08):
                keys.append("backspace")
                i += 1
                continue
            if b == 0x03:
                keys.append("ctrl-c")
                i += 1
                continue
            if b < 0x20:
                i += 1
                continue
            # decode a UTF-8 character
            for size in (1, 2, 3, 4):
                if i + size <= n:
                    try:
                        keys.append(buf[i:i + size].decode("utf-8"))
                        i += size
                        break
                    except UnicodeDecodeError:
                        continue
            else:
                i += 1
        return keys, buf[i:]


class App:
    def __init__(self, path: str, theme: Optional[str] = None,
                 footer: bool = True, size: Optional[tuple[int, int]] = None,
                 math_italic: Optional[bool] = None,
                 cell_size: tuple[int, int] = (10, 20),
                 graphics: bool = False,
                 math_engine: Optional[str] = None,
                 width_setting: Optional[str] = None,
                 fit: Optional[bool] = None,
                 transition: Optional[str] = None,
                 transition_time: Optional[str] = None):
        self.path = path
        self.footer = footer
        self.math_italic = math_italic
        self.cell_size = cell_size
        self.graphics = graphics
        self.deck = self._load()
        name = theme or self.deck.meta.get("theme") or "midnight"
        self.theme = get_theme(name)
        self.size = size or term_size()
        self.math_engine = (math_engine or self.deck.meta.get("math_engine")
                            or "auto")
        self.index = 0
        self.mode = "slide"
        self.help_page = 0
        self.sel = 0
        self.pending = ""
        self.flash: Optional[str] = None
        self.flash_until = 0.0
        self.blank = False
        self.width_setting = width_setting or str(
            self.deck.meta.get("width") or "full")
        if fit is None:
            fit = str(self.deck.meta.get("fit") or "false").strip().lower() \
                not in ("false", "no", "off", "0")
        self.fit = fit
        self.compare = False
        self.compare_focus = 0
        count = len(self.deck.slides)
        self.compare_indices = [0, min(1, count - 1)]
        self.pane_steps = [0, 0]
        self.reveal_step = 0
        self.transition_name = normalize_transition(
            transition or self.deck.meta.get("transition") or "fade")
        self.animate = self.transition_name != "cut"
        raw_time = transition_time or self.deck.meta.get("transition_time")
        try:
            self.transition_time = max(0.05, min(1.5, float(raw_time or 0.22)))
        except (TypeError, ValueError):
            self.transition_time = 0.22
        self.anim: Optional[dict] = None
        self.last_frame: Optional[list[Text]] = None
        self.last_placements: list[Placement] = []
        self.frame_placements: list[Placement] = []
        self.started = time.monotonic()
        self.mtime = self._mtime()
        self.rebuild()

    def _load(self):
        with open(self.path, "r", encoding="utf-8") as fh:
            text = fh.read()
        stem = os.path.splitext(os.path.basename(self.path))[0]
        return parse_deck(text, stem)

    def _mtime(self) -> int:
        try:
            return os.stat(self.path).st_mtime_ns
        except OSError:
            return 0

    def _renderer(self, width: Optional[int] = None,
                  height: Optional[int] = None,
                  footer: Optional[bool] = None,
                  min_width: int = 20) -> Renderer:
        w = self.size[0] if width is None else width
        h = self.size[1] if height is None else height
        return Renderer(
            self.deck, self.theme, w, h,
            self.footer if footer is None else footer, self.math_italic,
            cell_size=self.cell_size, graphics=self.graphics,
            math_engine=self.math_engine, started=self.started,
            base_dir=os.path.dirname(os.path.abspath(self.path)),
            width_setting=self.width_setting, fit=self.fit,
            min_width=min_width,
        )

    def resize(self, size: tuple[int, int]) -> None:
        if size == self.size:
            return
        self.size = size
        self.rebuild()

    def rebuild(self) -> None:
        self.renderer = self._renderer()
        self.compare_renderers: list[Renderer] = []
        if self.compare and self.size[0] >= 40:
            gap = 1
            left_w = (self.size[0] - gap) // 2
            right_w = self.size[0] - gap - left_w
            pane_h = self.size[1] - 2 if self.footer else self.size[1]
            self.compare_renderers = [
                self._renderer(left_w, pane_h, footer=False, min_width=1),
                self._renderer(right_w, pane_h, footer=False, min_width=1),
            ]

    def reload(self) -> None:
        try:
            deck = self._load()
        except Exception as exc:  # noqa: BLE001
            self.flash = f"reload failed: {exc}"
            self.flash_until = time.monotonic() + 4
            return
        self.deck = deck
        count = len(deck.slides)
        self.index = min(self.index, count - 1)
        self.sel = min(self.sel, count - 1)
        self.compare_indices = [min(i, count - 1) for i in self.compare_indices]
        self.pane_steps = [0, 0]
        self.reveal_step = 0
        self.anim = None
        self.rebuild()
        self.flash = "reloaded"
        self.flash_until = time.monotonic() + 1.2
        self.mtime = self._mtime()

    def check_reload(self) -> bool:
        mtime = self._mtime()
        if mtime and mtime != self.mtime:
            self.reload()
            return True
        return False

    def set_flash(self, msg: str, seconds: float = 1.6) -> None:
        self.flash = msg
        self.flash_until = time.monotonic() + seconds

    # -- navigation, reveal builds and transitions -------------------------

    def next(self) -> None:
        self.index = min(len(self.deck.slides) - 1, self.index + 1)
        self.reveal_step = 0
        self._reset_scroll()

    def prev(self) -> None:
        self.index = max(0, self.index - 1)
        self.reveal_step = 0
        self._reset_scroll()

    def _steps_for(self, index: int) -> int:
        return _reveal_number(
            self.deck.slides[index].options.get("reveal_steps"))

    def _current_index(self) -> int:
        return (self.compare_indices[self.compare_focus] if self.compare
                else self.index)

    def _current_step(self) -> int:
        return self.pane_steps[self.compare_focus] if self.compare \
            else self.reveal_step

    def _set_step(self, step: int) -> None:
        if self.compare:
            self.pane_steps[self.compare_focus] = max(0, step)
        else:
            self.reveal_step = max(0, step)

    def _reset_scroll(self, pane: Optional[int] = None) -> None:
        if self.compare and len(self.compare_renderers) == 2:
            targets = ([self.compare_renderers[pane]] if pane is not None
                       else self.compare_renderers)
        else:
            targets = [self.renderer]
        for renderer in targets:
            renderer.scroll_y = 0

    def _scroll(self, direction: int, page: bool = False) -> None:
        r = (self.compare_renderers[self.compare_focus] if self.compare
             and self.compare_renderers else self.renderer)
        step = max(1, (self.size[1] - 3) // 2) if page else 1
        r.scroll_y = max(0, min(r.max_scroll, r.scroll_y + direction * step))

    def capture(self) -> tuple[list[Text], list[Placement]]:
        if self.last_frame is not None:
            return list(self.last_frame), list(self.last_placements)
        return self.frame(), list(self.frame_placements)

    def _transition_for(self, index: int) -> str:
        raw = (self.deck.slides[index].options.get("transition")
               or self.transition_name or "fade")
        return normalize_transition(raw)

    def start_transition(self, old: Optional[list[Text]] = None,
                         old_placements: Optional[list[Placement]] = None,
                         reveal: bool = False,
                         index: Optional[int] = None) -> None:
        kind = self._transition_for(self._current_index() if index is None
                                    else index)
        if not self.animate or kind == "cut":
            self.anim = None
            return
        if old is None:
            old, old_placements = self.capture()
        self.anim = {
            "old": list(old),
            "old_placements": list(old_placements or []),
            "start": time.monotonic(),
            "duration": min(self.transition_time, 0.18) if reveal
            else self.transition_time,
            "reveal": reveal,
            "kind": kind,
        }

    def _go(self, delta: int, pane: Optional[int] = None) -> None:
        count = len(self.deck.slides)
        if self.compare:
            which = self.compare_focus if pane is None else pane
            current = self.compare_indices[which]
            target = max(0, min(count - 1, current + delta))
            if target == current:
                return
            self.compare_indices[which] = target
            self.pane_steps[which] = 0
            self._reset_scroll(which)
        else:
            target = max(0, min(count - 1, self.index + delta))
            if target == self.index:
                return
            self.index = target
            self.reveal_step = 0
            self._reset_scroll()

    def _jump(self, target: int, pane: Optional[int] = None) -> None:
        count = len(self.deck.slides)
        target = max(0, min(count - 1, target))
        old, placements = self.capture()
        if self.compare:
            which = self.compare_focus if pane is None else pane
            self.compare_indices[which] = target
            self.pane_steps[which] = 0
            self._reset_scroll(which)
        else:
            self.index = target
            self.reveal_step = 0
            self._reset_scroll()
        self.start_transition(old, placements)

    def advance(self) -> None:
        index = self._current_index()
        step = self._current_step()
        steps = self._steps_for(index)
        old, placements = self.capture()
        if step < steps:
            self._set_step(step + 1)
            self.start_transition(old, placements, reveal=True)
        else:
            self._go(1)
            self.start_transition(old, placements)

    def retreat(self) -> None:
        step = self._current_step()
        old, placements = self.capture()
        if step > 0:
            self._set_step(step - 1)
            self.start_transition(old, placements, reveal=True)
        else:
            self._go(-1)
            self.start_transition(old, placements)

    def handle(self, key: str) -> Optional[str]:
        n = len(self.deck.slides)
        if key == "ctrl-c" or key == "q":
            return "quit"
        if self.blank:
            self.blank = False
            return None
        if self.mode == "help":
            pages = help_page_count(*self.size)
            if pages > 1 and key in ("right", "n", "]", "space", "pgdn"):
                self.help_page = (self.help_page + 1) % pages
            elif pages > 1 and key in ("left", "p", "[", "pgup"):
                self.help_page = (self.help_page - 1) % pages
            else:
                self.mode = "slide"
            return None
        if self.mode == "notes":
            if key in ("right", "space", "n"):
                self.next()
                return None
            if key in ("left", "p"):
                self.prev()
                return None
            self.mode = "slide"
            return None
        if self.mode == "overview":
            cols = 3 if self.size[0] >= 88 else 2 if self.size[0] >= 56 else 1
            if key in ("esc", "o", "q"):
                self.mode = "slide"
            elif key in ("right", "l"):
                self.sel = min(n - 1, self.sel + 1)
            elif key in ("left", "h"):
                self.sel = max(0, self.sel - 1)
            elif key in ("down", "j"):
                self.sel = min(n - 1, self.sel + cols)
            elif key in ("up", "k"):
                self.sel = max(0, self.sel - cols)
            elif key in ("home", "g"):
                self.sel = 0
            elif key in ("end", "G"):
                self.sel = n - 1
            elif key in ("enter", "space"):
                self.index = self.sel
                self.compare_indices[0] = self.sel
                self.compare_indices[1] = min(n - 1, self.sel + 1)
                self.pane_steps = [0, 0]
                self.reveal_step = 0
                self.anim = None
                self.mode = "slide"
            return None

        # Left/right move the focused slide in compare view; everywhere else
        # the arrow keys are build-aware next/previous.
        if self.compare and key in ("right", "l"):
            old, places = self.capture()
            self._go(1)
            self.start_transition(old, places)
            return None
        if self.compare and key in ("left", "h"):
            old, places = self.capture()
            self._go(-1)
            self.start_transition(old, places)
            return None
        if key in ("right", "space", "down", "j", "l", "n", "pgdn"):
            self.advance()
            self.pending = ""
            return None
        if key in ("left", "up", "k", "p", "h", "pgup"):
            self.retreat()
            self.pending = ""
            return None
        if key in ("home", "g"):
            self._jump(0)
            self.pending = ""
            return None
        if key in ("end", "G"):
            self._jump(n - 1)
            self.pending = ""
            return None
        if key == "?":
            self.mode = "help"
            self.help_page = 0
            return None
        if key == "o":
            self.mode = "overview"
            self.sel = self._current_index()
            return None
        if key == "s":
            self.mode = "notes"
            return None
        if key == "b":
            self.blank = True
            return None
        if key == "t":
            names = theme_names()
            cur = names.index(self.theme.name) if self.theme.name in names else 0
            self.theme = get_theme(names[(cur + 1) % len(names)])
            self.rebuild()
            self.set_flash(f"theme: {self.theme.name}")
            return None
        if key == "r":
            self.reload()
            return None
        if key == "f":
            self.fit = not self.fit
            self.rebuild()
            self.set_flash(f"fit: {'on' if self.fit else 'off'}")
            return None
        if key == "w":
            cur = (WIDTH_MODES.index(self.width_setting)
                  if self.width_setting in WIDTH_MODES else 0)
            self.width_setting = WIDTH_MODES[(cur + 1) % len(WIDTH_MODES)]
            self.rebuild()
            self.set_flash(f"width: {self.width_setting}")
            return None
        if key == "c":
            if not self.compare and self.size[0] < 40:
                self.set_flash("compare needs 40 columns")
                return None
            if self.compare:
                self.index = self.compare_indices[self.compare_focus]
                self.reveal_step = self.pane_steps[self.compare_focus]
            else:
                self.compare_indices = [self.index, min(n - 1, self.index + 1)]
                self.pane_steps = [self.reveal_step, 0]
                self.reveal_step = 0
            self.compare = not self.compare
            self.compare_focus = 0
            self.anim = None
            self._reset_scroll()
            self.rebuild()
            self.set_flash("compare: on" if self.compare else "compare: off")
            return None
        if key == "tab" and self.compare:
            self.compare_focus = 1 - self.compare_focus
            return None
        if key == "x" and self.compare:
            old, places = self.capture()
            self.compare_indices.reverse()
            self.pane_steps.reverse()
            self._reset_scroll()
            self.start_transition(old, places)
            return None
        if key == "a":
            self.animate = not self.animate
            self.anim = None
            self.set_flash(f"transitions: {'on' if self.animate else 'off'}")
            return None
        if key in ("[", "]"):
            # In compare view these jump the focused pane; otherwise the
            # current slide.  Digits + Enter remain the precise way to jump.
            delta = -10 if key == "[" else 10
            self._jump(self._current_index() + delta,
                       self.compare_focus if self.compare else None)
            self.pending = ""
            return None
        if key == "J":
            self._scroll(1)
            return None
        if key == "K":
            self._scroll(-1)
            return None
        if key == "d":
            self._scroll(1, page=True)
            return None
        if key == "u":
            self._scroll(-1, page=True)
            return None
        # isdecimal() only accepts characters int() can parse; isdigit()
        # also accepts superscripts such as ², which crash int().
        if key.isdecimal():
            self.pending = (self.pending + key)[:3]
            return None
        if key == "backspace":
            self.pending = self.pending[:-1]
            return None
        if key == "enter" and self.pending:
            try:
                target = int(self.pending)
            except ValueError:
                target = 0
            self.pending = ""
            if 1 <= target <= n:
                self._jump(target - 1)
            else:
                self.set_flash(f"no slide {target}")
            return None
        if key == "esc":
            self.pending = ""
            return None
        return None

    def frame(self) -> list[Text]:
        lines, placements = self._render_frame()
        self.frame_placements = placements
        if self.anim is None:
            return lines
        progress = ((time.monotonic() - self.anim["start"])
                    / self.anim["duration"])
        if progress >= 1:
            self.anim = None
            return lines
        if self.anim["reveal"]:
            blended = reveal_glow(self.anim["old"], lines, progress,
                                  self.theme)
            chosen = placements if progress >= 0.3 \
                else self.anim["old_placements"]
        else:
            blended = blend_frames(self.anim["old"], lines, progress,
                                   self.anim["kind"], self.theme)
            chosen = placements if progress >= 0.5 \
                else self.anim["old_placements"]
        self.frame_placements = chosen
        return blended

    def _render_frame(self) -> tuple[list[Text], list[Placement]]:
        self.frame_placements = []
        if self.blank:
            return self.renderer.render_blank(), []
        if self.mode == "help":
            return self.renderer.render_help(self.help_page), []
        if self.mode == "notes":
            return self.renderer.render_notes(self.index), []
        if self.mode == "overview":
            return self.renderer.render_overview(self.sel), []
        flash = None
        if self.pending:
            flash = f"go to slide {self.pending} ↵"
        elif self.flash and time.monotonic() < self.flash_until:
            flash = self.flash
        if not self.compare or len(self.compare_renderers) != 2:
            lines = self.renderer.render_slide(
                self.index, flash, step=self.reveal_step)
            return lines, list(self.renderer.frame_placements)
        return self._compare_frame(flash), list(self.frame_placements)

    def _compare_frame(self, flash: Optional[str]) -> list[Text]:
        """Stitch any two independently rendered and scrolled slide panes."""
        left_r, right_r = self.compare_renderers
        lines, placements = render_compare(
            left_r, right_r, self.compare_indices[0], self.compare_indices[1],
            self.renderer, left_step=self.pane_steps[0],
            right_step=self.pane_steps[1], focus=self.compare_focus,
            flash=flash, footer=self.footer,
        )
        self.frame_placements = placements
        return lines


def term_size() -> tuple[int, int]:
    try:
        size = os.get_terminal_size(sys.stdout.fileno())
        return size.columns, size.lines
    except OSError:
        fallback = shutil.get_terminal_size((100, 30))
        return fallback.columns, fallback.lines


#: path -> (Kitty image id, source fingerprint).  The fingerprint makes an
#: edited or replaced image retransmit instead of showing stale bytes.
_IMAGE_IDS: dict[str, tuple[int, tuple[int, int]]] = {}
_NEXT_IMAGE_ID = 1
_HAD_IMAGES = False
_HAS_DATA = False


def _image_token(path: str) -> tuple[int, int]:
    """Fingerprint an image source for cache invalidation."""

    try:
        stat = os.stat(path)
        return (stat.st_mtime_ns, stat.st_size)
    except OSError:
        return (0, 0)


def _image_id_for(path: str, parts: list[str]) -> int:
    """Return a live Kitty id for *path*, retransmitting when it changed."""

    global _NEXT_IMAGE_ID, _HAS_DATA
    token = _image_token(path)
    entry = _IMAGE_IDS.get(path)
    if entry is not None and entry[1] == token:
        return entry[0]
    if entry is not None:
        parts.append(f"\x1b_Ga=d,d=i,i={entry[0]}\x1b\\")
    image_id = _NEXT_IMAGE_ID
    _NEXT_IMAGE_ID += 1
    _IMAGE_IDS[path] = (image_id, token)
    parts.append(_transmit(path, image_id))
    _HAS_DATA = True
    return image_id


def _transmit(path: str, image_id: int) -> str:
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    chunks = [data[i:i + 4096] for i in range(0, len(data), 4096)] or [""]
    out: list[str] = []
    for i, chunk in enumerate(chunks):
        more = 1 if i < len(chunks) - 1 else 0
        if i == 0:
            params = f"a=t,f=100,i={image_id},q=2,m={more}"
        else:
            params = f"m={more}"
        out.append(f"\x1b_G{params};{chunk}\x1b\\")
    return "".join(out)


def _place(image_id: int, cols: int, rows: int) -> str:
    return (f"\x1b_Ga=p,i={image_id},c={max(1, cols)},r={max(1, rows)},"
            f"C=1,q=2\x1b\\")


def clear_images() -> None:
    global _HAD_IMAGES, _HAS_DATA, _NEXT_IMAGE_ID
    if _HAD_IMAGES or _HAS_DATA:
        # d=A frees the image data as well as the placements.
        sys.stdout.write("\x1b_Ga=d,d=A\x1b\\")
        sys.stdout.flush()
    _HAD_IMAGES = False
    _HAS_DATA = False
    # The terminal no longer knows any of these ids after a=A.
    _IMAGE_IDS.clear()
    _NEXT_IMAGE_ID = 1


def write_frame(lines: list[Text], width: int, height: int,
                placements: Optional[list[Placement]] = None) -> None:
    global _HAD_IMAGES, _HAS_DATA
    buf = io.StringIO()
    console = Console(
        file=buf, force_terminal=True, color_system="truecolor", width=width,
        height=height, legacy_windows=False, highlight=False,
    )
    console.print(Text("\n").join(lines), end="", soft_wrap=True, crop=True)
    parts = ["\x1b[H"]
    if _HAD_IMAGES or placements:
        # Images are not tied to cells, so remove the previous frame's
        # placements before painting the new one.  d=a keeps the transmitted
        # image data, so placements can be re-used without retransmitting.
        parts.append("\x1b_Ga=d,d=a\x1b\\")
        _HAD_IMAGES = False
    parts.append(buf.getvalue())
    parts.append("\x1b[0J")
    for p in placements or []:
        image_id = _image_id_for(p.path, parts)
        parts.append(f"\x1b[{p.line + 1};{p.col + 1}H")
        parts.append(_place(image_id, p.cols, p.rows))
        _HAD_IMAGES = True
    sys.stdout.write("".join(parts))
    sys.stdout.flush()


def render_compare(left_r: Renderer, right_r: Renderer,
                   left_index: int, right_index: int,
                   footer_renderer: Renderer,
                   left_step: int = 0, right_step: int = 0,
                   focus: int = 0, flash: Optional[str] = None,
                   footer: bool = True) -> tuple[list[Text], list[Placement]]:
    """Stitch two independently rendered, independently scrolled slide panes.

    The two renderers may show any slides at any reveal steps; the caller
    decides which slides to put in them.  A header in each pane makes the pair
    unambiguous, and the divider takes the focused pane's accent colour.
    """

    th = footer_renderer.theme
    deck = footer_renderer.deck
    count = len(deck.slides)
    left = left_r.render_slide(left_index, step=left_step)
    right = right_r.render_slide(right_index, step=right_step)

    def header(index: int, active: bool, width: int) -> Text:
        line = Text(style=th.on())
        line.append(f" {index + 1}/{count} ",
                    style=f"bold {'on ' + th.table_head if active else th.dim}")
        line.append(" " + _ellipsis(deck.slides[index].title,
                                    max(4, width - 12)),
                    style=th.fg if active else th.dim)
        if active:
            line.append(" ◀", style=th.accent)
        if line.cell_len < width:
            line.append(" " * (width - line.cell_len), style=th.on())
        return line

    def with_header(lines: list[Text], index: int, active: bool,
                    width: int) -> list[Text]:
        # The pane header already names the slide.  Replace the rendered
        # heading instead of stacking a second copy on top of it.
        title = deck.slides[index].title.strip()

        def clean(text: str) -> str:
            text = re.sub(r"[┃┆│╭╮╰╯─]+$", "", text.strip()).strip()
            return re.sub(r"^[▌▎#>]\s*", "", text).strip()

        needle = title[:max(4, min(12, len(title)))]
        for i, line in enumerate(lines):
            raw = clean(line.plain)
            if not needle or needle not in raw:
                continue
            j = i + 1
            while raw != title and j < len(lines):
                nxt = clean(lines[j].plain)
                candidate = f"{raw} {nxt}".strip()
                if not nxt or not title.startswith(candidate):
                    break
                raw = candidate
                j += 1
            result = list(lines)
            for k in range(j):
                result[k] = Text(" " * width, style=th.on())
            result[0] = header(index, active, width)
            return result
        if lines:
            return [header(index, active, width)] + lines[:-1]
        return [header(index, active, width)]

    left = with_header(left, left_index, focus == 0, left_r.width)
    right = with_header(right, right_index, focus == 1, right_r.width)

    out: list[Text] = []
    for a, b in zip(left, right):
        row = Text(style=th.on())
        row.append_text(a)
        row.append("│", th.accent if focus == 0 else th.accent2)
        row.append_text(b)
        out.append(row)
    total_h = left_r.height + (2 if footer else 0)
    while len(out) < total_h:
        out.append(Text(" " * (left_r.width + 1 + right_r.width),
                        style=th.on()))
    if footer and total_h >= 2:
        focused = left_r if focus == 0 else right_r
        index = left_index if focus == 0 else right_index
        footer_renderer.max_scroll = focused.max_scroll
        footer_renderer.scroll_y = focused.scroll_y
        page = f"{left_index + 1}/{count}  ↔  {right_index + 1}/{count}"
        f1, f2 = footer_renderer._footer_lines(
            index, flash, deck.slides[index],
            left_step if focus == 0 else right_step, page=page)
        out[total_h - 2] = f1
        out[total_h - 1] = f2
    placements = list(left_r.frame_placements) + [
        Placement(p.line, p.col + left_r.width + 1, p.path, p.cols, p.rows)
        for p in right_r.frame_placements
    ]
    return out, placements


def run(path: str, theme: Optional[str] = None, footer: bool = True,
        math_italic: Optional[bool] = None,
        math_engine: Optional[str] = None,
        size: Optional[tuple[int, int]] = None,
        width_setting: Optional[str] = None,
        fit: Optional[bool] = None,
        transition: Optional[str] = None,
        transition_time: Optional[str] = None,
        compare: Optional[tuple[int, int]] = None) -> int:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return dump(path, theme, footer, size=size, math_italic=math_italic,
                    math_engine=math_engine, width_setting=width_setting,
                    fit=fit, transition=transition,
                    transition_time=transition_time, compare=compare)
    cell_size, graphics = query_terminal()
    app = App(path, theme, footer, math_italic=math_italic,
              cell_size=cell_size, graphics=graphics, math_engine=math_engine,
              width_setting=width_setting, fit=fit, transition=transition,
              transition_time=transition_time)
    if compare and app.size[0] >= 40:
        app.compare = True
        app.compare_indices = [max(0, min(len(app.deck.slides) - 1, i))
                               for i in compare]
        app.pane_steps = [0, 0]
        app.rebuild()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    reader = KeyReader()

    def _terminate(signum, frame):  # noqa: ANN001
        raise KeyboardInterrupt

    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _terminate)
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H")
        sys.stdout.flush()
        # Open with a short fade up from an empty stage.
        opening = app.renderer.render_blank()
        app.last_frame = opening
        app.last_placements = []
        app.start_transition(opening, [])
        dirty = True
        last_clock = time.monotonic()
        while True:
            size = term_size()
            if size != app.size:
                app.resize(size)
                dirty = True
            if dirty:
                frame = app.frame()
                placements = list(app.frame_placements)
                write_frame(frame, *app.size, placements)
                app.last_frame = frame
                app.last_placements = placements
                dirty = False
            keys = reader.poll(0.03 if app.anim else 0.20)
            if not keys:
                if app.anim:
                    dirty = True
                if app.check_reload():
                    dirty = True
                if app.flash and time.monotonic() > app.flash_until:
                    app.flash = None
                    dirty = True
                if (app.renderer.clock
                        and time.monotonic() - last_clock >= 1.0):
                    last_clock = time.monotonic()
                    dirty = True
                continue
            for key in keys:
                if app.handle(key) == "quit":
                    return 0
                dirty = True
    except KeyboardInterrupt:
        return 0
    finally:
        clear_images()
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        signal.signal(signal.SIGTERM, previous)


def dump(path: str, theme: Optional[str] = None, footer: bool = True,
         size: Optional[tuple[int, int]] = None,
         math_italic: Optional[bool] = None,
         math_engine: Optional[str] = None,
         width_setting: Optional[str] = None,
         fit: Optional[bool] = None,
         transition: Optional[str] = None,
         transition_time: Optional[str] = None,
         compare: Optional[tuple[int, int]] = None,
         step: Optional[int] = None) -> int:
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    stem = os.path.splitext(os.path.basename(path))[0]
    deck = parse_deck(text, stem)
    name = theme or deck.meta.get("theme") or "midnight"
    width, height = size or (100, 30)
    if compare and width < 40:
        sys.stderr.write("compare needs 40 columns\n")
        return 2
    engine = math_engine or deck.meta.get("math_engine") or "auto"
    renderer = Renderer(
        deck, get_theme(name), width, height, footer, math_italic,
        graphics=False, math_engine=engine,
        base_dir=os.path.dirname(os.path.abspath(path)), dump=True,
        width_setting=width_setting or deck.meta.get("width"),
        fit=(fit if fit is not None else str(deck.meta.get("fit") or "false")
             .strip().lower() not in ("false", "no", "off", "0")),
    )
    base = dict(graphics=False, math_engine=engine, dump=True,
                min_width=1,  # compare panes may be narrower than 20 cells
                base_dir=os.path.dirname(os.path.abspath(path)),
                width_setting=width_setting or deck.meta.get("width"),
                fit=(fit if fit is not None
                     else str(deck.meta.get("fit") or "false")
                     .strip().lower() not in ("false", "no", "off", "0")))
    if compare:
        gap = 1
        left_w = (width - gap) // 2
        right_w = width - gap - left_w
        pane_h = height - 2 if footer else height
        left_r = Renderer(deck, renderer.theme, left_w, pane_h, False,
                          math_italic, **base)
        right_r = Renderer(deck, renderer.theme, right_w, pane_h, False,
                           math_italic, **base)
        lines, _ = render_compare(
            left_r, right_r, max(0, min(len(deck.slides) - 1, compare[0])),
            max(0, min(len(deck.slides) - 1, compare[1])), renderer,
            footer=footer)
        sys.stdout.write("\n".join(line.plain for line in lines) + "\n")
        return 0
    out = []
    for i in range(len(deck.slides)):
        steps = _reveal_number(deck.slides[i].options.get("reveal_steps"))
        out.append("\n".join(line.plain for line in renderer.render_slide(
            i, step=steps if step is None else step)))
        out.append("")
    sys.stdout.write("\n".join(out))
    return 0
