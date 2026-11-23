"""A small LaTeX math typesetter for character cells.

Renders a useful subset of LaTeX into 2D boxes (fractions, radicals, scripts,
scaled delimiters, matrices, aligned equations, big operators) and into a flat
Unicode form for inline math.

The public entry points are :func:`render_block` and :func:`render_inline`.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------
# width helpers
# --------------------------------------------------------------------------

def swidth(s: str) -> int:
    """Display width of a string in terminal cells."""
    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        w += 2 if unicodedata.east_asian_width(ch) in "WF" else 1
    return w


def pad_to(s: str, width: int) -> str:
    return s + " " * max(0, width - swidth(s))


def center_in(s: str, width: int) -> str:
    left = max(0, (width - swidth(s)) // 2)
    return " " * left + s + " " * max(0, width - swidth(s) - left)


# --------------------------------------------------------------------------
# boxes
# --------------------------------------------------------------------------

@dataclass
class Box:
    """A rectangle of text with a baseline row index."""

    lines: list[str] = field(default_factory=lambda: [""])
    baseline: int = 0

    def __post_init__(self) -> None:
        if not self.lines:
            self.lines = [""]
        self.baseline = max(0, min(self.baseline, len(self.lines) - 1))

    @property
    def width(self) -> int:
        return max((swidth(line) for line in self.lines), default=0)

    @property
    def height(self) -> int:
        return len(self.lines)

    @property
    def ascent(self) -> int:
        return self.baseline

    @property
    def descent(self) -> int:
        return self.height - self.baseline - 1

    def normalized(self) -> "Box":
        w = self.width
        return Box([pad_to(line, w) for line in self.lines], self.baseline)


EMPTY = Box([""], 0)


def hcat(boxes: list[Box], gap: int = 0) -> Box:
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return EMPTY
    ascent = max(b.ascent for b in boxes)
    descent = max(b.descent for b in boxes)
    height = ascent + descent + 1
    out = [""] * height
    for i, box in enumerate(boxes):
        if i and gap:
            for r in range(height):
                out[r] += " " * gap
        offset = ascent - box.ascent
        for r in range(height):
            src = r - offset
            line = box.lines[src] if 0 <= src < box.height else ""
            out[r] += pad_to(line, box.width)
    return Box(out, ascent)


def vcat(boxes: list[Box], gap: int = 0, align: str = "center") -> Box:
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return EMPTY
    width = max(b.width for b in boxes)
    lines: list[str] = []
    baseline = 0
    for i, box in enumerate(boxes):
        if i and gap:
            lines.extend([""] * gap)
        for line in box.lines:
            if align == "left":
                lines.append(pad_to(line, width))
            elif align == "right":
                lines.append(" " * max(0, width - swidth(line)) + line)
            else:
                lines.append(center_in(line, width))
        if i == 0:
            baseline = len(lines) - box.height + box.baseline
    return Box(lines, baseline)


def shift_down(box: Box, rows: int) -> Box:
    return Box([""] * rows + box.lines, box.baseline + rows)


# --------------------------------------------------------------------------
# symbols
# --------------------------------------------------------------------------

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ϵ", "zeta": "ζ", "eta": "η", "theta": "θ",
    "vartheta": "ϑ", "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ",
    "nu": "ν", "xi": "ξ", "omicron": "ο", "pi": "π", "varpi": "ϖ",
    "varkappa": "ϰ",
    "rho": "ρ", "varrho": "ϱ", "sigma": "σ", "varsigma": "ς", "tau": "τ",
    "upsilon": "υ", "phi": "φ", "varphi": "ϕ", "chi": "χ", "psi": "ψ",
    "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ",
    "Psi": "Ψ", "Omega": "Ω",
}

# Lowercase Greek is italic in standard LaTeX; capitals stay upright.
GREEK_ITALIC = {
    "alpha": "𝛼", "beta": "𝛽", "gamma": "𝛾", "delta": "𝛿",
    "epsilon": "𝜀", "varepsilon": "𝜖", "zeta": "𝜁", "eta": "𝜂",
    "theta": "𝜃", "vartheta": "𝜗", "iota": "𝜄", "kappa": "𝜅",
    "varkappa": "𝜘", "lambda": "𝜆", "mu": "𝜇", "nu": "𝜈", "xi": "𝜉",
    "omicron": "𝜊", "pi": "𝜋", "varpi": "𝜛", "rho": "𝜌", "varrho": "𝜚",
    "sigma": "𝜎", "varsigma": "𝜍", "tau": "𝜏", "upsilon": "𝜐",
    "phi": "𝜑", "varphi": "𝜙", "chi": "𝜒", "psi": "𝜓", "omega": "𝜔",
}

# Mathematical italic Latin.  Note the gap at U+1D455: italic h is U+210E.
MATH_ITALIC: dict[str, str] = {}
for _i in range(26):
    MATH_ITALIC[chr(ord("A") + _i)] = chr(0x1D434 + _i)
    _lower = ord("a") + _i
    if _i < 7:
        MATH_ITALIC[chr(_lower)] = chr(0x1D44E + _i)
    elif _i == 7:
        MATH_ITALIC["h"] = "\u210e"
    else:
        MATH_ITALIC[chr(_lower)] = chr(0x1D456 + _i - 8)
MATH_ASCII = {v: k for k, v in MATH_ITALIC.items()}

SYMBOLS = {
    # relations
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠",
    "approx": "≈", "equiv": "≡", "sim": "∼", "simeq": "≃", "cong": "≅",
    "propto": "∝", "ll": "≪", "gg": "≫", "subset": "⊂", "supset": "⊃",
    "subseteq": "⊆", "supseteq": "⊇", "nsubseteq": "⊈", "in": "∈",
    "notin": "∉", "ni": "∋", "perp": "⊥", "parallel": "∥", "mid": "∣",
    "nmid": "∤", "models": "⊨", "vdash": "⊢", "dashv": "⊣", "asymp": "≍",
    "doteq": "≐", "prec": "≺", "succ": "≻", "preceq": "≼", "succeq": "≽",
    "lt": "<", "gt": ">", "nless": "≮", "ngtr": "≯", "not=": "≠",
    # arrows
    "to": "→", "rightarrow": "→", "leftarrow": "←", "gets": "←",
    "leftrightarrow": "↔", "Rightarrow": "⇒", "Leftarrow": "⇐",
    "Leftrightarrow": "⇔", "implies": "⟹", "impliedby": "⟸", "iff": "⟺",
    "longrightarrow": "⟶", "longleftarrow": "⟵", "longmapsto": "⟼",
    "mapsto": "↦", "uparrow": "↑", "downarrow": "↓", "updownarrow": "↕",
    "hookrightarrow": "↪", "hookleftarrow": "↩", "rightharpoonup": "⇀",
    "rightleftharpoons": "⇌", "nearrow": "↗", "searrow": "↘",
    "swarrow": "↙", "nwarrow": "↖", "rightsquigarrow": "⇝",
    # binary operators
    "pm": "±", "mp": "∓", "times": "×", "div": "÷", "cdot": "·",
    "ast": "∗", "star": "⋆", "circ": "∘", "bullet": "•", "cup": "∪",
    "cap": "∩", "setminus": "∖", "smallsetminus": "∖", "wedge": "∧",
    "land": "∧", "vee": "∨", "lor": "∨", "oplus": "⊕", "ominus": "⊖",
    "otimes": "⊗", "oslash": "⊘", "odot": "⊙", "sqcup": "⊔", "sqcap": "⊓",
    "uplus": "⊎", "wr": "≀", "diamond": "⋄", "triangleleft": "◁",
    "triangleright": "▷", "bigtriangleup": "△", "bigtriangledown": "▽",
    # misc
    "infty": "∞", "partial": "∂", "nabla": "∇", "emptyset": "∅",
    "varnothing": "∅", "forall": "∀", "exists": "∃", "nexists": "∄",
    "neg": "¬", "lnot": "¬", "top": "⊤", "bot": "⊥", "angle": "∠",
    "measuredangle": "∡", "triangle": "△", "square": "□", "blacksquare": "■",
    "degree": "°", "prime": "′", "ell": "ℓ", "hbar": "ℏ", "hslash": "ℏ",
    "aleph": "ℵ", "beth": "ℶ", "wp": "℘", "Re": "ℜ", "Im": "ℑ",
    "imath": "ı", "jmath": "ȷ", "surd": "√", "checkmark": "✓",
    "dag": "†", "dagger": "†", "ddag": "‡", "ddagger": "‡",
    "S": "§", "P": "¶", "copyright": "©", "pounds": "£", "euro": "€",
    "colon": ":", "therefore": "∴", "because": "∵",
    # dots
    "ldots": "…", "dots": "…", "cdots": "⋯", "vdots": "⋮", "ddots": "⋱",
    "iddots": "⋰", "dotsb": "⋯", "dotsc": "…",
    # delimiters
    "langle": "⟨", "rangle": "⟩", "lceil": "⌈", "rceil": "⌉",
    "lfloor": "⌊", "rfloor": "⌋", "lvert": "|", "rvert": "|",
    "lVert": "‖", "rVert": "‖", "vert": "|", "Vert": "‖",
    "lbrack": "[", "rbrack": "]", "lbrace": "{", "rbrace": "}",
    "backslash": "\\", "slash": "/",
    # escaped punctuation
    "%": "%", "&": "&", "#": "#", "_": "_", "$": "$", "{": "{", "}": "}",
    " ": " ",
}

BIG_OPS = {
    "sum": ("∑", True), "prod": ("∏", True), "coprod": ("∐", True),
    "int": ("∫", False), "iint": ("∬", False), "iiint": ("∭", False),
    "oint": ("∮", False), "oiint": ("∯", False),
    "bigcup": ("⋃", True), "bigcap": ("⋂", True), "bigvee": ("⋁", True),
    "bigwedge": ("⋀", True), "bigoplus": ("⨁", True), "bigotimes": ("⨂", True),
    "bigodot": ("⨀", True), "biguplus": ("⨄", True), "bigsqcup": ("⨆", True),
}

INTEGRAL_CHARS = {"∫", "∬", "∭"}

FUNCTIONS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan",
    "sinh", "cosh", "tanh", "coth", "log", "ln", "lg", "exp", "max", "min",
    "sup", "inf", "lim", "limsup", "liminf", "det", "dim", "ker", "deg",
    "gcd", "hom", "arg", "Pr", "mod",
}

LIMIT_FUNCTIONS = {"lim", "limsup", "liminf", "max", "min", "sup", "inf",
                   "det", "gcd", "Pr"}

# Characters that become real superscripts/subscripts when possible.
SUP_MAP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶",
    "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻", "=": "⁼",
    "(": "⁽", ")": "⁾", "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ",
    "f": "ᶠ", "g": "ᵍ", "h": "ʰ", "i": "ⁱ", "j": "ʲ", "k": "ᵏ", "l": "ˡ",
    "m": "ᵐ", "n": "ⁿ", "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ", "t": "ᵗ",
    "u": "ᵘ", "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ", " ": " ",
}
SUB_MAP = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆",
    "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋", "=": "₌",
    "(": "₍", ")": "₎", "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ",
    "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "r": "ᵣ",
    "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ", " ": " ",
}

BLACKBOARD = {
    "R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ", "P": "ℙ",
    "H": "ℍ", "E": "𝔼", "F": "𝔽", "A": "𝔸", "B": "𝔹", "D": "𝔻",
}

DELIM_NAMES = {
    "(": "(", ")": ")", "[": "[", "]": "]", "|": "|", ".": "",
    "\\{": "{", "\\}": "}", "\\langle": "⟨", "\\rangle": "⟩",
    "\\lceil": "⌈", "\\rceil": "⌉", "\\lfloor": "⌊", "\\rfloor": "⌋",
    "\\|": "‖", "\\Vert": "‖", "\\vert": "|", "\\lVert": "‖",
    "\\rVert": "‖", "/": "/", "\\backslash": "\\",
}


# --------------------------------------------------------------------------
# nodes
# --------------------------------------------------------------------------

class Node:
    pass


@dataclass
class Sym(Node):
    ch: str
    kind: str = "ord"  # ord, bin, rel, open, close, punct


@dataclass
class Row(Node):
    items: list[Node]


@dataclass
class Frac(Node):
    num: Node
    den: Node
    bar: bool = True


@dataclass
class Sqrt(Node):
    body: Node
    index: Optional[Node] = None


@dataclass
class Script(Node):
    base: Node
    sup: Optional[Node] = None
    sub: Optional[Node] = None


@dataclass
class Text(Node):
    text: str
    style: str = "upright"
    func: bool = False


@dataclass
class BigOp(Node):
    ch: str
    sup: Optional[Node] = None
    sub: Optional[Node] = None
    limits: bool = True
    func: bool = False


@dataclass
class Delim(Node):
    left: str
    right: str
    body: Node


@dataclass
class Matrix(Node):
    rows: list[list[Node]]
    kind: str = "matrix"


@dataclass
class Accent(Node):
    body: Node
    char: str


@dataclass
class Space(Node):
    width: int


@dataclass
class Binom(Node):
    n: Node
    k: Node


@dataclass
class Boxed(Node):
    body: Node


@dataclass
class Brace(Node):
    body: Node
    under: bool = True
    label: Optional[Node] = None


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------

class Parser:
    def __init__(self, src: str, italic: bool = True):
        self.s = src
        self.i = 0
        self.n = len(src)
        self.italic = italic

    def literal(self, ch: str) -> "Sym":
        """Turn a source character into a math symbol (variables italic)."""
        if ch == "-":
            ch = "\u2212"
        elif ch == "*":
            ch = "\u2217"
        elif self.italic and ch in MATH_ITALIC:
            ch = MATH_ITALIC[ch]
        return Sym(ch, classify(ch))

    def peek(self) -> str:
        return self.s[self.i] if self.i < self.n else ""

    def take(self) -> str:
        ch = self.peek()
        self.i += 1
        return ch

    def skip_ws(self) -> None:
        while self.i < self.n and self.s[self.i] in " \t\n\r":
            self.i += 1

    def parse(self) -> Node:
        return self.parse_row()

    def parse_row(self, stops: tuple[str, ...] = ()) -> Node:
        items: list[Node] = []
        while self.i < self.n:
            ch = self.peek()
            if ch in stops:
                break
            if ch == "}":
                break
            if ch in " \t\n\r":
                self.i += 1
                continue
            if ch == "{":
                self.i += 1
                node = self.parse_row(("}",))
                self.i += 1  # closing brace
                items.append(node)
                continue
            if ch in "^_":
                self.i += 1
                arg = self.parse_atom()
                base = items.pop() if items else Sym("")
                if isinstance(base, Script):
                    if ch == "^":
                        base.sup = arg
                    else:
                        base.sub = arg
                    items.append(base)
                else:
                    items.append(
                        Script(base, arg if ch == "^" else None,
                               arg if ch == "_" else None)
                    )
                continue
            if ch == "'":
                self.i += 1
                items.append(Sym("′", "ord"))
                continue
            if ch == "&" or self.s.startswith("\\\\", self.i):
                break
            if self.s.startswith("\\end", self.i):
                break
            if "\\right" in stops and self.s.startswith("\\right", self.i):
                break
            if ch == "\\":
                items.append(self.parse_command())
                continue
            self.i += 1
            items.append(self.literal(ch))
        return Row(items)

    def parse_atom(self) -> Node:
        self.skip_ws()
        if self.i >= self.n:
            return Row([])
        ch = self.peek()
        if ch == "{":
            self.i += 1
            node = self.parse_row(("}",))
            if self.peek() == "}":
                self.i += 1
            return node
        if ch == "\\":
            return self.parse_command()
        self.i += 1
        return self.literal(ch)

    def read_group(self) -> Node:
        self.skip_ws()
        if self.peek() != "{":
            return self.parse_atom()
        self.i += 1
        node = self.parse_row(("}",))
        if self.peek() == "}":
            self.i += 1
        return node

    def _upright_group(self) -> Node:
        """Read a group without turning its letters italic."""
        old = self.italic
        self.italic = False
        try:
            return self.read_group()
        finally:
            self.italic = old

    def read_raw_group(self) -> str:
        self.skip_ws()
        if self.peek() != "{":
            if self.i < self.n:
                self.i += 1
                return self.s[self.i - 1]
            return ""
        self.i += 1
        depth = 1
        start = self.i
        while self.i < self.n and depth:
            ch = self.s[self.i]
            if ch == "\\":
                self.i += 2
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    text = self.s[start:self.i]
                    self.i += 1
                    return text
            self.i += 1
        return self.s[start:self.i]

    @staticmethod
    def _unescape(s: str) -> str:
        for a, b in (("\\{", "{"), ("\\}", "}"), ("\\%", "%"), ("\\_", "_"),
                     ("\\&", "&"), ("\\$", "$"), ("\\#", "#"), ("\\ ", " "),
                     ("\\\\", "\\")):
            s = s.replace(a, b)
        return s

    def read_delim(self) -> str:
        self.skip_ws()
        if self.i >= self.n:
            return ""
        if self.s[self.i] == "\\":
            start = self.i
            self.i += 1
            while self.i < self.n and (self.s[self.i].isalpha()):
                self.i += 1
            if self.i == start + 1 and self.i < self.n:
                self.i += 1
            return self.s[start:self.i]
        ch = self.take()
        return ch

    def parse_command(self) -> Node:
        assert self.peek() == "\\"
        self.i += 1
        start = self.i
        if self.i < self.n and self.s[self.i].isalpha():
            while self.i < self.n and self.s[self.i].isalpha():
                self.i += 1
            name = self.s[start:self.i]
        else:
            name = self.take()

        if name == "frac" or name == "dfrac" or name == "tfrac" or name == "cfrac":
            return Frac(self.read_group(), self.read_group())
        if name == "binom" or name == "dbinom" or name == "tbinom":
            return Binom(self.read_group(), self.read_group())
        if name == "sqrt":
            index = None
            self.skip_ws()
            if self.peek() == "[":
                self.i += 1
                index = self.parse_row(("]",))
                if self.peek() == "]":
                    self.i += 1
            return Sqrt(self.read_group(), index)
        if name in ("text", "textrm", "textnormal", "mbox", "textit", "textbf"):
            return Text(self._unescape(self.read_raw_group()), name)
        if name == "operatorname":
            node = self._upright_group()
            return Text(flat(node), "upright", func=True)
        if name in ("mathrm", "mathup", "rm"):
            node = self._upright_group()
            return Text(flat(node), "upright")
        if name == "mathbf":
            return Text(flat(self._upright_group()), "bold")
        if name in ("boldsymbol", "bm"):
            return Text(flat(self.read_group()), "bold")
        if name in ("mathbb",):
            raw = flat(self._upright_group())
            return Text("".join(BLACKBOARD.get(c, c) for c in raw), "bb")
        if name in ("mathcal", "mathscr", "mathfrak"):
            raw = flat(self._upright_group())
            script = {
                "A": "𝒜", "B": "ℬ", "C": "𝒞", "D": "𝒟", "E": "ℰ", "F": "ℱ",
                "G": "𝒢", "H": "ℋ", "I": "ℐ", "J": "𝒥", "K": "𝒦", "L": "ℒ",
                "M": "ℳ", "N": "𝒩", "O": "𝒪", "P": "𝒫", "Q": "𝒬", "R": "ℛ",
                "S": "𝒮", "T": "𝒯", "U": "𝒰", "V": "𝒱", "W": "𝒲", "X": "𝒳",
                "Y": "𝒴", "Z": "𝒵",
            }
            return Text("".join(script.get(c, c) for c in raw), "cal")
        if name in ("mathit", "mathnormal"):
            return Text(flat(self.read_group()), "italic")
        if name in ("mathsf", "mathtt"):
            return Text(flat(self._upright_group()), "upright")
        if name in ("overline", "bar"):
            return Accent(self.read_group(), "─")
        if name == "underline":
            return Accent(self.read_group(), "_")
        if name in ("hat", "widehat"):
            return Accent(self.read_group(), "ˆ")
        if name in ("tilde", "widetilde"):
            return Accent(self.read_group(), "˜")
        if name == "vec":
            return Accent(self.read_group(), "→")
        if name in ("dot", "ddot", "breve", "check", "acute", "grave"):
            return Accent(self.read_group(), {"dot": "˙", "ddot": "¨",
                                              "breve": "˘", "check": "ˇ",
                                              "acute": "´", "grave": "ˋ"}[name])
        if name == "boxed":
            return Boxed(self.read_group())
        if name == "left":
            left = self.read_delim()
            body = self.parse_row(("\\right",))
            right = ""
            if self.s.startswith("\\right", self.i):
                self.i += len("\\right")
                right = self.read_delim()
            return Delim(left, right, body)
        if name == "right":
            # Only reached when unbalanced; swallow the delimiter.
            return Delim("", self.read_delim(), Row([]))
        if name in ("big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl",
                    "Bigr", "biggl", "biggr", "Biggl", "Biggr"):
            return self.parse_atom()
        if name == "begin":
            env = self.read_raw_group()
            return self.parse_environment(env)
        if name == "end":
            env = self.read_raw_group()
            return Row([])
        if name == "not":
            nxt = self.parse_atom()
            mapping = {"=": "≠", "∈": "∉", "⊂": "⊄", "⊆": "⊈", "≡": "≢",
                       "<": "≮", ">": "≯", "≈": "≉", "∣": "∤"}
            if isinstance(nxt, Sym):
                return Sym(mapping.get(nxt.ch, nxt.ch + "\u0338"), "rel")
            return nxt
        if name in ("quad",):
            return Space(2)
        if name in ("qquad",):
            return Space(4)
        if name == "," or name == ":" or name == ";" or name == "thinspace":
            return Space(1 if name != ";" else 2)
        if name == "!":
            return Space(-1)
        if name in ("displaystyle", "textstyle", "scriptstyle", "scriptscriptstyle",
                    "limits", "nolimits", "nonumber", "notag", "label", "tag"):
            if name in ("label", "tag"):
                self.read_raw_group()
            return Row([])
        if name in ("hspace", "hspace*", "phantom", "vphantom", "hphantom"):
            self.read_raw_group()
            return Row([])
        if name in BIG_OPS:
            ch, limits = BIG_OPS[name]
            return BigOp(ch, limits=limits)
        if name in LIMIT_FUNCTIONS:
            return BigOp(name, limits=True, func=True)
        if name in ("underbrace", "overbrace"):
            return Brace(self.read_group(), under=(name == "underbrace"))
        if name in FUNCTIONS:
            return Text(name, "upright", func=True)
        if name in GREEK:
            if self.italic and name in GREEK_ITALIC:
                return Sym(GREEK_ITALIC[name])
            return Sym(GREEK[name])
        if name in SYMBOLS:
            ch = SYMBOLS[name]
            return Sym(ch, classify(ch))
        if name in ("pmod", "bmod"):
            arg = self.read_group() if name == "pmod" else Row([])
            txt = " (mod " + flat(arg) + ")" if name == "pmod" else " mod "
            return Text(txt, "upright")
        # Unknown command: show its name upright so nothing silently vanishes.
        return Text(name, "upright")

    def parse_environment(self, env: str) -> Node:
        kind = env.rstrip("*")
        if kind in ("array", "matrix*", "smallmatrix"):
            pass
        # optional column spec for array
        self.skip_ws()
        if kind == "array" and self.peek() == "{":
            self.read_raw_group()
        rows: list[list[Node]] = []
        row: list[Node] = []
        while self.i < self.n:
            self.skip_ws()
            if self.s.startswith("\\end", self.i):
                # consume \end{...}
                self.i += 4
                if self.peek() == "{":
                    self.read_raw_group()
                break
            if self.s.startswith("\\\\", self.i):
                self.i += 2
                self.skip_ws()
                if self.peek() == "[":
                    # row spacing spec
                    j = self.s.find("]", self.i)
                    if j != -1:
                        self.i = j + 1
                rows.append(row)
                row = []
                continue
            if self.peek() == "&":
                self.i += 1
                row.append(Row([]))
                continue
            node = self.parse_row(stops=("&",))
            row.append(node)
            if self.peek() == "&":
                self.i += 1
        if row:
            rows.append(row)
        return Matrix(rows, kind)


def classify(ch: str) -> str:
    if ch in "+−-±∓×÷·∗⋆∘•∪∩∖∧∨⊕⊗⊙⊎":
        return "bin"
    if ch in "=≠≈≉≡≢<≤>≥≪≫∼≃≅∝⊂⊃⊆⊇∈∉∋→←↔⇒⇐⇔⟹⟸⟺↦⟶⟵⊢⊨":
        return "rel"
    if ch in "([{⟨⌈⌊":
        return "open"
    if ch in ")]}⟩⌉⌋":
        return "close"
    if ch in ",;":
        return "punct"
    return "ord"


# --------------------------------------------------------------------------
# box renderer
# --------------------------------------------------------------------------

def _center_lines(box: Box, width: int) -> list[str]:
    return [center_in(line, width) for line in box.lines]


def _attach(base: Box, sup: Optional[Box], sub: Optional[Box],
            overlap: bool = False) -> Box:
    """Attach scripts to a base.

    With ``overlap`` the scripts sit on the first and last rows of a tall base
    (as LaTeX does for integrals and scaled delimiters) instead of adding extra
    rows above and below it.
    """
    col = max(sup.width if sup else 0, sub.width if sub else 0)
    top = -base.ascent
    bottom = base.descent
    sup_off = None
    sub_off = None
    tall = overlap and base.height > 1
    if sup:
        if tall:
            # The bottom of the superscript shares the top row of the base.
            sup_off = -base.ascent - sup.descent
        else:
            # Sit above the top of the base, not just above its baseline.
            sup_off = -(base.ascent + sup.descent + 1)
        top = min(top, sup_off - sup.ascent)
    if sub:
        if tall:
            # The top of the subscript shares the bottom row of the base.
            sub_off = base.descent - sub.ascent
        else:
            # Hang below the bottom of the base.
            sub_off = base.descent + sub.ascent + 1
        bottom = max(bottom, sub_off + sub.descent)
    height = bottom - top + 1
    baseline = -top
    lines = [""] * height
    for r in range(height):
        abs_row = top + r
        base_row = abs_row + base.ascent
        cell = ""
        if 0 <= base_row < base.height:
            cell = base.lines[base_row]
        cell = pad_to(cell, base.width)
        scell = " " * col
        if sup and sup_off is not None:
            srow = abs_row - sup_off + sup.ascent
            if 0 <= srow < sup.height:
                # Scripts start where the base ends, so their left edge is
                # always one predictable cell after the base glyph.
                scell = pad_to(sup.lines[srow], col)
        if sub and sub_off is not None:
            srow = abs_row - sub_off + sub.ascent
            if 0 <= srow < sub.height:
                subline = pad_to(sub.lines[srow], col)
                # prefer superscript when both occupy a row
                if scell.strip() == "":
                    scell = subline
        lines[r] = (cell + scell).rstrip()
    return Box(lines, baseline)


def _stack_aligned(boxes: list[Box], gap: int = 0) -> Box:
    """Stack boxes on a shared baseline instead of on their top edges."""
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return EMPTY
    ascent = max(b.ascent for b in boxes)
    descent = max(b.descent for b in boxes)
    row_h = ascent + descent + 1
    width = max(b.width for b in boxes)
    lines: list[str] = []
    for i, box in enumerate(boxes):
        if i and gap:
            lines.extend([""] * gap)
        offset = ascent - box.ascent
        block = [""] * row_h
        for r in range(box.height):
            block[offset + r] = box.lines[r]
        lines.extend(pad_to(line, width) for line in block)
    return Box(lines, ascent)


def _tall_integral(ch: str, height: int = 3) -> Box:
    """Build a display-size integral from the Unicode extension pieces."""
    count = {"∫": 1, "∬": 2, "∭": 3}.get(ch, 1)
    lines: list[str] = []
    for r in range(height):
        if r == 0:
            lines.append("⌠" * count)
        elif r == height - 1:
            lines.append("⌡" * count)
        else:
            lines.append("⎮" * count)
    return Box(lines, height // 2)


def _scaled_delim(ch: str, height: int, baseline: int) -> Box:
    if not ch:
        return Box([""] * max(1, height), min(baseline, max(0, height - 1)))
    if height <= 1:
        return Box([ch], 0)
    pairs = {
        "(": ("⎛", "⎜", "⎝"), ")": ("⎞", "⎟", "⎠"),
        "[": ("⎡", "⎢", "⎣"), "]": ("⎤", "⎥", "⎦"),
        "{": ("⎧", "⎪", "⎩"), "}": ("⎫", "⎪", "⎭"),
        "|": ("│", "│", "│"), "‖": ("║", "║", "║"),
        "⌈": ("⌈", "│", "⌊"), "⌉": ("⌉", "│", "⌋"),
        "⌊": ("│", "│", "⌊"), "⌋": ("│", "│", "⌋"),
        "⟨": ("⎛", "⎜", "⎝"), "⟩": ("⎞", "⎟", "⎠"),
    }
    top, mid, bot = pairs.get(ch, (ch, ch, ch))
    lines = [mid] * height
    lines[0] = top
    lines[-1] = bot
    if ch in "{}" and 0 < baseline < height - 1:
        lines[baseline] = "⎨" if ch == "{" else "⎬"
    return Box(lines, baseline)


def _has_edge_space(box: Box, left: bool) -> bool:
    """True when every non-empty row already has a space on that edge."""
    for line in box.lines:
        if not line:
            continue
        if left and not line.startswith(" "):
            return False
        if not left and not line.endswith(" "):
            return False
    return True


def _make_matrix(node: Matrix, display: bool, tight: bool = False) -> Box:
    kind = node.kind
    rows: list[list[Box]] = []
    for raw_row in node.rows:
        rows.append([render(n, display, tight) for n in raw_row])
    if not rows:
        return EMPTY
    ncols = max(len(r) for r in rows)
    colw = [0] * ncols
    for r in rows:
        for j, cell in enumerate(r):
            colw[j] = max(colw[j], cell.width)
    aligned = kind in ("aligned", "align", "split")
    cases = kind == "cases"
    row_boxes: list[Box] = []
    for r in rows:
        parts: list[Box] = []
        for j in range(ncols):
            cell = r[j] if j < len(r) else Box([""], 0)
            w = colw[j]
            if aligned or cases:
                padded = Box([pad_to(line, w) for line in cell.lines],
                             cell.baseline)
            else:
                padded = Box([center_in(line, w) for line in cell.lines],
                             cell.baseline)
            parts.append(padded)
        row_boxes.append(hcat(parts, gap=2))
    if aligned and ncols > 1:
        body = _align_columns(rows, colw, gap=1, first_right=True,
                              row_gap=1)
    elif cases and ncols > 1:
        body = _align_columns(rows, colw, gap=2, first_right=False,
                              row_gap=0)
    else:
        body = _stack_aligned(row_boxes, gap=0)
    body = Box(body.lines, (body.height - 1) // 2)
    if kind == "cases":
        brace = _scaled_delim("{", body.height, body.baseline)
        return hcat([brace, Box([" "] * body.height, body.baseline), body])
    wraps = {
        "pmatrix": ("(", ")"), "bmatrix": ("[", "]"),
        "Bmatrix": ("{", "}"), "vmatrix": ("|", "|"),
        "Vmatrix": ("‖", "‖"), "matrix": ("", ""), "smallmatrix": ("", ""),
        "aligned": ("", ""), "align": ("", ""), "split": ("", ""),
        "gathered": ("", ""), "array": ("", ""), "cases": ("", ""),
    }
    left, right = wraps.get(kind, ("", ""))
    if not left and not right:
        return body
    lb = _scaled_delim(left, body.height, body.baseline)
    rb = _scaled_delim(right, body.height, body.baseline)
    pad = Box([" "] * body.height, body.baseline)
    return hcat([lb, pad, body, pad, rb])


def _align_columns(rows: list[list[Box]], colw: list[int], gap: int,
                   first_right: bool = True, row_gap: int = 0) -> Box:
    """Lay out an aligned environment on a common baseline."""
    out_rows: list[Box] = []
    for r in rows:
        parts = []
        for j, w in enumerate(colw):
            cell = r[j] if j < len(r) else Box([""], 0)
            if j == 0 and first_right:
                padded = Box([" " * max(0, w - swidth(line)) + line
                              for line in cell.lines], cell.baseline)
            else:
                padded = Box([pad_to(line, w) for line in cell.lines],
                             cell.baseline)
            parts.append(padded)
        out_rows.append(hcat(parts, gap=gap))
    return _stack_aligned(out_rows, gap=row_gap)


def render(node: Node, display: bool = True, tight: bool = False) -> Box:
    if isinstance(node, Row):
        boxes: list[Box] = []
        prev: Optional[Node] = None
        prev_unary = False
        for item in node.items:
            box = render(item, display, tight)
            gap = 0
            if not tight and prev is not None:
                if _needs_space(prev, item) and not prev_unary:
                    gap = 1
                elif _is_integral(prev) and _is_integral(item):
                    # Keep repeated integral signs from touching their limits.
                    gap = 1
            kind = _kind(item)
            unary = kind == "bin" and (
                prev is None or prev_unary
                or _kind(prev) in ("open", "rel", "bin", "op")
            )
            if gap:
                boxes.append(Box([" " * gap], 0))
            boxes.append(box)
            prev = item
            prev_unary = unary
        return hcat(boxes)
    if isinstance(node, Sym):
        return Box([node.ch], 0)
    if isinstance(node, Text):
        return Box([node.text], 0)
    if isinstance(node, Space):
        if node.width <= 0:
            return Box([""], 0)
        return Box([" " * node.width], 0)
    if isinstance(node, Frac):
        num = render(node.num, False, False)
        den = render(node.den, False, False)
        width = max(num.width, den.width) + 2
        lines = _center_lines(num, width)
        lines.append("─" * width)
        lines.extend(_center_lines(den, width))
        return Box(lines, len(num.lines))
    if isinstance(node, Sqrt):
        body = render(node.body, display, tight)
        w = body.width
        # A radical is a check mark at the baseline with an overbar; the
        # vertical stroke above/below it carries the sign through tall bodies.
        lines = [" " + "─" * w]
        for i, line in enumerate(body.lines):
            lines.append(("√" if i == body.baseline else "│") + pad_to(line, w))
        box = Box(lines, body.baseline + 1)
        if node.index is not None:
            raw = flat(node.index).replace(" ", "")
            compact = _compact_script(raw, SUP_MAP)
            if compact:
                # ³√x reads like a real root and keeps the index on the
                # baseline instead of adding a row above the radical.
                idx_lines = ([""] * box.baseline + [compact]
                             + [""] * (box.height - box.baseline - 1))
                return hcat([Box(idx_lines, box.baseline), box])
            idx = render(node.index, False, True)
            pad = max(0, box.height - idx.height)
            idx_box = Box(idx.lines + [""] * pad, box.baseline)
            return hcat([idx_box, box])
        return box
    if isinstance(node, Script):
        if isinstance(node.base, BigOp):
            op = node.base
            merged = BigOp(op.ch, node.sup or op.sup, node.sub or op.sub,
                           op.limits, op.func)
            return render(merged, display, tight)
        if isinstance(node.base, Brace):
            br = node.base
            return render(Brace(br.body, br.under, node.sub or node.sup),
                          display, tight)
        base = render(node.base, display, tight)
        sup = render(node.sup, False, True) if node.sup else None
        sub = render(node.sub, False, True) if node.sub else None
        # Unicode has compact superscript glyphs for digits, signs and most
        # lowercase letters.  Use them whenever the whole script maps, which
        # keeps the baseline clean; otherwise fall back to a real 2D script.
        if base.height == 1:
            sup_text = sub_text = None
            if node.sup is not None:
                raw = flat(node.sup).replace(" ", "")
                sup_text = _compact_script(raw, SUP_MAP)
            if node.sub is not None:
                raw = flat(node.sub).replace(" ", "")
                sub_text = _compact_subscript(raw)
            if ((node.sup is None or sup_text is not None)
                    and (node.sub is None or sub_text is not None)):
                text = (base.lines[0].rstrip() + (sup_text or "")
                        + (sub_text or ""))
                return Box([text], 0)
        # Scaled delimiters and integrals are tall: put the scripts on their
        # top/bottom rows rather than pushing the whole line taller.
        overlap = (isinstance(node.base, Delim)
                   or (isinstance(node.base, Matrix)
                       and node.base.kind in ("pmatrix", "bmatrix",
                                              "Bmatrix", "vmatrix",
                                              "Vmatrix")))
        return _attach(base, sup, sub, overlap=overlap)
    if isinstance(node, BigOp):
        sup = render(node.sup, False, True) if node.sup else None
        sub = render(node.sub, False, True) if node.sub else None
        if display and node.ch in ("∫", "∬", "∭"):
            base = _tall_integral(node.ch)
            return _attach(base, sup, sub, overlap=True)
        if display and node.limits and (sup or sub):
            op_box = Box([node.ch], 0)
            parts: list[Box] = []
            if sup:
                parts.append(sup)
            op_index = len(parts)
            parts.append(op_box)
            if sub:
                parts.append(sub)
            width = max(p.width for p in parts)
            lines: list[str] = []
            baseline = 0
            for i, part in enumerate(parts):
                if i == op_index:
                    baseline = len(lines)
                lines.extend(_center_lines(part, width))
            return Box(lines, baseline)
        return _attach(Box([node.ch], 0), sup, sub)
    if isinstance(node, Delim):
        body = render(node.body, display, tight)
        left = DELIM_NAMES.get(node.left, node.left)
        right = DELIM_NAMES.get(node.right, node.right)
        parts = []
        if left:
            parts.append(_scaled_delim(left, body.height, body.baseline))
            if body.height > 1 and not _has_edge_space(body, True):
                # Tall bodies (integrals, matrices) need breathing room so
                # the delimiter does not touch the first glyph of the body.
                parts.append(Box([" "] * body.height, body.baseline))
        parts.append(body)
        if right:
            if body.height > 1 and not _has_edge_space(body, False):
                parts.append(Box([" "] * body.height, body.baseline))
            parts.append(_scaled_delim(right, body.height, body.baseline))
        return hcat(parts)
    if isinstance(node, Matrix):
        return _make_matrix(node, display, tight)
    if isinstance(node, Accent):
        body = render(node.body, display, tight)
        w = body.width
        if node.char == "_":
            return Box(body.lines + ["─" * w], body.baseline)
        if node.char == "─":
            return Box(["─" * w] + body.lines, body.baseline + 1)
        mark = node.char
        row = center_in(mark, w)
        return Box([row] + body.lines, body.baseline + 1)
    if isinstance(node, Binom):
        n = render(node.n, False, True)
        k = render(node.k, False, True)
        # stacked without a bar
        width = max(n.width, k.width) + 2
        lines = _center_lines(n, width) + _center_lines(k, width)
        box = Box(lines, (len(lines) - 1) // 2)
        lb = _scaled_delim("(", box.height, box.baseline)
        rb = _scaled_delim(")", box.height, box.baseline)
        return hcat([lb, box, rb])
    if isinstance(node, Boxed):
        body = render(node.body, display, tight)
        w = body.width
        lines = ["┌" + "─" * (w + 2) + "┐"]
        lines += ["│ " + pad_to(line, w) + " │" for line in body.lines]
        lines.append("└" + "─" * (w + 2) + "┘")
        return Box(lines, body.baseline + 1)
    if isinstance(node, Brace):
        body = render(node.body, display, tight)
        w = body.width
        if w <= 1:
            bar = "⏟" if node.under else "⏞"
        else:
            bar = ("╰" + "─" * (w - 2) + "╯") if node.under else \
                  ("╭" + "─" * (w - 2) + "╮")
        label = render(node.label, False, True) if node.label else None
        lw = label.width if label else 0
        width = max(w, lw)
        lab_lines = _center_lines(label, width) if label else []
        if node.under:
            lines = [center_in(line, width) for line in body.lines]
            lines.append(center_in(bar, width))
            lines += lab_lines
            return Box(lines, body.baseline)
        lines = lab_lines + [center_in(bar, width)]
        lines += [center_in(line, width) for line in body.lines]
        return Box(lines, body.baseline + len(lab_lines) + 1)
    return EMPTY


def _is_integral(node: Node) -> bool:
    if isinstance(node, BigOp):
        return node.ch in INTEGRAL_CHARS
    if isinstance(node, Script) and isinstance(node.base, BigOp):
        return node.base.ch in INTEGRAL_CHARS
    return False


def _needs_space(a: Node, b: Node) -> bool:
    ka = _kind(a)
    kb = _kind(b)
    if kb == "open" and ka not in ("rel", "bin"):
        return False
    if ka == "open" or kb == "close":
        return False
    if kb == "punct":
        return False
    if kb in ("rel", "bin", "op"):
        return True
    if ka in ("func", "rel", "bin"):
        return True
    if ka == "op":
        # Side limits already separate an integral from the next term.
        return not _is_integral(a)
    if kb == "func" and ka not in ("open", "punct"):
        return True
    if ka == "punct":
        return True
    def _brace_like(n: Node) -> bool:
        return (isinstance(n, Brace)
                or (isinstance(n, Script) and isinstance(n.base, Brace)))
    if _brace_like(a) and _brace_like(b):
        return True
    return False


def _kind(node: Node) -> str:
    if isinstance(node, Sym):
        return node.kind
    if isinstance(node, BigOp):
        return "func" if node.func else "op"
    if isinstance(node, Text):
        return "func" if node.func else "ord"
    if isinstance(node, Script):
        base = node.base
        if isinstance(base, BigOp):
            return "func" if base.func else "op"
        if isinstance(base, Text) and base.func:
            return "func"
    return "ord"


# --------------------------------------------------------------------------
# flat (inline) renderer
# --------------------------------------------------------------------------

def _ascii_math(s: str) -> str:
    """Strip mathematical italic styling for Unicode script mapping."""
    return "".join(MATH_ASCII.get(ch, ch) for ch in s)


def _map_script(s: str, mapping: dict[str, str]) -> Optional[str]:
    values = set(mapping.values())
    out = []
    for ch in s:
        if ch in mapping:
            out.append(mapping[ch])
        elif ch in values:
            # A nested script is already in its compact form (x^{n^2}).
            out.append(ch)
        else:
            return None
    return "".join(out)


def _compact_script(s: str, mapping: dict[str, str]) -> Optional[str]:
    s = _ascii_math(s).replace(" ", "").replace("−", "-")
    if not s:
        return None
    return _map_script(s, mapping)


def _compact_subscript(s: str) -> Optional[str]:
    """Subscripts may use letters: matrix indices like a_{1n} stay on one row."""
    s = _ascii_math(s).replace(" ", "").replace("−", "-")
    if not s:
        return None
    return _map_script(s, SUB_MAP)


def _wrap_flat(s: str) -> str:
    if not s:
        return s
    if len(s) == 1:
        return s
    if s[0] in "([{" and s[-1] in ")]}":
        return s
    if s.isascii() and s.isalnum():
        return s
    return "(" + s + ")"


def flat(node: Node) -> str:
    if isinstance(node, Row):
        out = []
        prev = None
        prev_unary = False
        for item in node.items:
            kind = _kind(item)
            unary = kind == "bin" and (
                prev is None or prev_unary
                or _kind(prev) in ("open", "rel", "bin", "op")
            )
            if (prev is not None and _needs_space(prev, item)
                    and not prev_unary):
                out.append(" ")
            out.append(flat(item))
            prev = item
            prev_unary = unary
        return "".join(out)
    if isinstance(node, Sym):
        return node.ch
    if isinstance(node, Text):
        return node.text
    if isinstance(node, Space):
        return " " * max(0, node.width)
    if isinstance(node, Frac):
        return _wrap_flat(flat(node.num)) + "/" + _wrap_flat(flat(node.den))
    if isinstance(node, Sqrt):
        body = flat(node.body)
        idx = flat(node.index) if node.index else ""
        pre = "" if not idx else _map_script(_ascii_math(idx), SUP_MAP) or "^" + idx
        return pre + "√" + _wrap_flat(body)
    if isinstance(node, Script):
        base = flat(node.base)
        if isinstance(node.base, (Frac, Sqrt)):
            base = "(" + base + ")"
        if node.sub is not None:
            raw = flat(node.sub).replace(" ", "")
            mapped = _compact_subscript(raw)
            base += mapped if mapped is not None else "_" + _wrap_flat(raw)
        if node.sup is not None:
            raw = flat(node.sup).replace(" ", "")
            mapped = _compact_script(raw, SUP_MAP)
            base += mapped if mapped is not None else "^" + _wrap_flat(raw)
        return base
    if isinstance(node, BigOp):
        out = node.ch
        if node.sub is not None:
            raw = flat(node.sub).replace(" ", "")
            mapped = _compact_subscript(raw)
            out += mapped if mapped is not None else "_" + _wrap_flat(raw)
        if node.sup is not None:
            raw = flat(node.sup).replace(" ", "")
            mapped = _compact_script(raw, SUP_MAP)
            out += mapped if mapped is not None else "^" + _wrap_flat(raw)
        return out
    if isinstance(node, Delim):
        left = DELIM_NAMES.get(node.left, node.left)
        right = DELIM_NAMES.get(node.right, node.right)
        return left + flat(node.body) + right
    if isinstance(node, Matrix):
        rows = []
        for row in node.rows:
            rows.append(", ".join(flat(c) for c in row))
        kind = node.kind
        left, right = {
            "pmatrix": ("(", ")"), "bmatrix": ("[", "]"),
            "Bmatrix": ("{", "}"), "vmatrix": ("|", "|"),
            "Vmatrix": ("‖", "‖"), "cases": ("{", ""),
        }.get(kind, ("", ""))
        return left + "; ".join(rows) + right
    if isinstance(node, Accent):
        body = flat(node.body)
        return {
            "─": body + "\u0304", "ˆ": body + "\u0302", "˜": body + "\u0303",
            "→": body + "\u20d7", "˙": body + "\u0307", "¨": body + "\u0308",
            "˘": body + "\u0306", "ˇ": body + "\u030c", "´": body + "\u0301",
            "ˋ": body + "\u0300", "_": body,
        }.get(node.char, body)
    if isinstance(node, Binom):
        return "C(" + flat(node.n) + ", " + flat(node.k) + ")"
    if isinstance(node, Boxed):
        return "[" + flat(node.body) + "]"
    if isinstance(node, Brace):
        body = flat(node.body)
        if node.label is not None:
            return body + "_{" + flat(node.label) + "}"
        return body
    return ""


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------

def render_block(latex: str, italic: bool = True,
                 tight: bool = False) -> list[str]:
    """Render display math to a list of lines (left-trimmed uniformly)."""
    parser = Parser(latex.strip(), italic=italic)
    rows: list[Box] = []
    while parser.i < parser.n:
        node = parser.parse_row()
        rows.append(render(node, True, tight))
        parser.skip_ws()
        if parser.s.startswith("\\\\", parser.i):
            parser.i += 2
            continue
        break
    if not rows:
        return [""]
    if len(rows) == 1:
        box = rows[0]
    else:
        width = max(b.width for b in rows)
        lines: list[str] = []
        for i, b in enumerate(rows):
            lines.extend(_center_lines(b, width))
            if i != len(rows) - 1:
                lines.append("")
        box = Box(lines, len(lines) // 2)
    return strip_common_indent(box.lines)


def render_inline(latex: str, italic: bool = True) -> str:
    parser = Parser(latex.strip(), italic=italic)
    node = parser.parse()
    return flat(node).strip()


# --------------------------------------------------------------------------
# line wrapping
# --------------------------------------------------------------------------

_RELATION_TOKENS = (
    "\\le", "\\leq", "\\ge", "\\geq", "\\ne", "\\neq", "\\approx",
    "\\equiv", "\\sim", "\\simeq", "\\cong", "\\propto", "\\to",
    "\\rightarrow", "\\Rightarrow", "\\Leftrightarrow", "\\iff",
    "\\mapsto", "\\in", "\\notin", "\\subset", "\\subseteq",
)
_BINARY_TOKENS = ("\\pm", "\\mp", "\\times", "\\cdot", "\\div")
_WIDE_TOKENS = ("\\qquad", "\\quad")


def _top_level_breaks(src: str) -> list[tuple[int, int, str, int]]:
    """Find places where a display equation may be broken.

    The returned tuples are ``(start, end, token, priority)``.  Priority 0 is
    a relation (break before it), priority 1 a binary operator or a wide
    space.  Braces, ``\\left...\\right`` and environments protect their
    contents.
    """
    depth = 0
    left_depth = 0
    env = 0
    i = 0
    prev = "start"
    out: list[tuple[int, int, str, int]] = []
    while i < len(src):
        ch = src[i]
        if ch == "\\":
            if src.startswith("\\left", i):
                left_depth += 1
                i += 5
                prev = "open"
                continue
            if src.startswith("\\right", i):
                left_depth = max(0, left_depth - 1)
                i += 6
                prev = "other"
                continue
            if src.startswith("\\begin", i):
                env += 1
                i += 6
                prev = "other"
                continue
            if src.startswith("\\end", i):
                env = max(0, env - 1)
                i += 4
                prev = "other"
                continue
            j = i + 1
            if j < len(src) and src[j].isalpha():
                while j < len(src) and src[j].isalpha():
                    j += 1
            else:
                j = min(len(src), i + 2)
            name = src[i:j]
            if depth == 0 and left_depth == 0 and env == 0:
                if name in _RELATION_TOKENS:
                    out.append((i, j, name, 0))
                elif name in _BINARY_TOKENS:
                    out.append((i, j, name, 1))
                elif name in _WIDE_TOKENS:
                    out.append((i, j, name, 2))
            i = j
            prev = "other"
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif depth == 0 and left_depth == 0 and env == 0:
            if ch in "=<>":
                out.append((i, i + 1, ch, 0))
            elif ch in "+-−" and prev not in ("op", "open", "start"):
                out.append((i, i + 1, ch, 1))
        if not ch.isspace():
            if ch in "=<>+-−":
                prev = "op"
            elif ch in "([{,":
                prev = "open"
            else:
                prev = "other"
        i += 1
    return out


def _split_on(src: str,
              breaks: list[tuple[int, int, str, int]]) -> list[tuple[str, str]]:
    """Split into ``(chunk, preceding_operator)`` pairs."""
    pieces: list[tuple[str, str]] = []
    last = 0
    op = ""
    for start, end, token, _prio in breaks:
        chunk = src[last:start].strip()
        pieces.append((chunk, op))
        op = token
        last = end
    pieces.append((src[last:].strip(), op))
    return [(chunk, op) for chunk, op in pieces if chunk or op]


def _wrap_binary(src: str, width: int, italic: bool,
                 tight: bool = False) -> list[str]:
    breaks = [b for b in _top_level_breaks(src) if b[3] == 1]
    if not breaks:
        # No safe break point: leave the expression intact.  A slightly wide
        # line is much prettier than slicing a fraction or matrix in half.
        return render_block(src, italic, tight)
    pieces = _split_on(src, breaks)
    sources: list[str] = []
    cur = pieces[0][0]
    for chunk, op in pieces[1:]:
        candidate = (cur + " " + op + " " + chunk).strip()
        if max((swidth(line) for line in render_block(candidate, italic,
                                                      tight)),
               default=0) <= width:
            cur = candidate
        else:
            sources.append(cur)
            # A leading binary operator is parsed as unary, so ask for an
            # explicit thin space to keep the same breathing room as the
            # previous line.
            if op in ("+", "-", "−", "\\pm", "\\mp", "\\times", "\\cdot",
                      "\\div"):
                cur = (op + " \\, " + chunk).strip()
            else:
                cur = (op + " " + chunk).strip()
    sources.append(cur)
    out: list[str] = []
    for k, source in enumerate(sources):
        rendered = render_block(source, italic, tight)
        prefix = "" if k == 0 else "  "
        out.extend(prefix + line if line.strip() else line
                   for line in rendered)
    return out


def _split_rows(src: str) -> list[str]:
    """Split on top-level ``\\\\`` row separators (not inside environments)."""
    rows: list[str] = []
    depth = 0
    env = 0
    i = 0
    start = 0
    while i < len(src):
        if src.startswith("\\begin", i):
            env += 1
            i += 6
            continue
        if src.startswith("\\end", i):
            env = max(0, env - 1)
            i += 4
            continue
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif ch == "\\" and depth == 0 and env == 0:
            if src.startswith("\\\\", i):
                rows.append(src[start:i].strip())
                i += 2
                start = i
                continue
        i += 1
    rows.append(src[start:].strip())
    return [row for row in rows if row]


def _wrap_once(latex: str, width: int, italic: bool,
               tight: bool) -> list[str]:
    lines = render_block(latex, italic, tight)
    if max((swidth(line) for line in lines), default=0) <= width:
        return lines

    breaks = _top_level_breaks(latex)
    wide = [b for b in breaks if b[3] == 2]
    if wide:
        pieces = _split_on(latex, wide)
        out: list[str] = []
        for k, (chunk, op) in enumerate(pieces):
            source = chunk if k == 0 else (op + " " + chunk).strip()
            if k:
                out.append("")
            out.extend(render_block_wrapped(source, width, italic, tight))
        return out

    relations = [b for b in breaks if b[3] == 0]
    if relations:
        pieces = _split_on(latex, relations)
        out: list[str] = []
        prev_height = 0
        for k, (chunk, op) in enumerate(pieces):
            source = chunk if k == 0 else (op + " " + chunk).strip()
            rendered = _wrap_binary(source, max(4, width - (2 if k else 0)),
                                    italic, tight)
            if k and prev_height > 1:
                # Keep a tall first line (an integral, a fraction, ...) from
                # crowding the continuation beneath it.
                out.append("")
            prefix = "" if k == 0 else "  "
            out.extend(prefix + line if line.strip() else line
                       for line in rendered)
            prev_height = len(rendered)
        return out
    return _wrap_binary(latex, width, italic, tight)


def render_block_wrapped(latex: str, width: int, italic: bool = True,
                         tight: bool = False) -> list[str]:
    """Render display math, wrapping long equations at sensible points."""
    latex = latex.strip()
    width = max(4, width)

    rows = _split_rows(latex)
    if len(rows) > 1:
        out: list[str] = []
        for k, row in enumerate(rows):
            if k:
                out.append("")
            out.extend(render_block_wrapped(row, width, italic, tight))
        return out

    modes = (True,) if tight else (False, True)
    results: list[list[str]] = []
    for mode in modes:
        lines = _wrap_once(latex, width, italic, mode)
        if max((swidth(line) for line in lines), default=0) <= width:
            return lines
        results.append(lines)
    return min(results, key=lambda ls: max((swidth(line) for line in ls),
                                           default=0))


def strip_common_indent(lines: list[str]) -> list[str]:
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    if not indents:
        return [""]
    cut = min(indents)
    return [line[cut:].rstrip() for line in lines]
