# unveil

Markdown slide decks in the terminal, with real typeset math.

`unveil` turns a single `.md` file into a full-screen presentation. Headings,
tables, code and LaTeX are laid out for a terminal — no browser, no slide
framework. Display math is compiled with **real LaTeX** (Tectonic) and painted
into the slide with the Kitty graphics protocol, so fractions, roots,
matrices and integrals have proper TeX spacing and Computer Modern shapes.

```
┌─ The transform ─────────────────────────────────────┐
│                                                     │
│        ⌠∞                                           │
│  f̂(ξ) = ⎮  f(t) e^(−2πiξt) dt                       │
│        ⌡−∞                                          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

The ASCII sketch above is the fallback. In a graphics-capable terminal the
box contains a crisp LaTeX-rendered image instead.

## Install

```sh
cd unveil
pip install -e .
unveil demo.md
```

Or run it straight from the checkout:

```sh
python3 -m unveil demo.md
```

A guided formatting showcase is also included:

```sh
python3 -m unveil formatting.md
```

For a long, feature-by-feature Director's Cut — every table style, chart type,
equation box, layout mode, image form, reveal build, transition and keyboard
control in one 56-slide deck — run:

```sh
python3 -m unveil showcase.md
```

Installed wheels ship all three example decks and `assets/demo.png` under
`<prefix>/share/doc/unveil/`; a source checkout has them at the repository
root.

Requires Python 3.10+ and [Rich](https://github.com/Textualize/rich).

For real LaTeX display math, install Tectonic and Poppler:

```sh
pkg install tectonic poppler      # Termux
# or: cargo install tectonic; apt install poppler-utils
```

`unveil` uses `tectonic` and `pdftoppm`. If either is missing, or the
terminal does not support Kitty graphics, it falls back to the built-in
Unicode typesetter automatically. The first compile of a new formula downloads
the TeX packages it needs and is cached afterwards in
`~/.cache/unveil/latex`. Set `XDG_CACHE_HOME` to move both caches (LaTeX and
converted images); image conversions live in `~/.cache/unveil/images`. A
formula that fails to compile is remembered for the rest of the process, so a
deck full of broken equations does not launch Tectonic once per formula.

## Deck syntax

Slides are separated by a line containing `---`, or by
`@slide`. A `---` block is front matter only when it is the very
first thing in the file and contains `key: value` lines.

```markdown
---
title: The Shape of a Signal
author: Ada Lovelace
theme: midnight
---

# The Shape of a Signal

Fourier, fast transforms, and why your headphones lie to you

---

## The transform

For a signal $f(t)$, the Fourier transform is

$$
\hat{f}(\xi) = \int_{-\infty}^{\infty} f(t)\, e^{-2\pi i \xi t}\,dt
$$
```

Everything else is ordinary Markdown:

- `#`…`######` headings (a title slide is detected from an H1 plus a little
  supporting text)
- **bold**, *italic*, ~~strike~~, `code`, [links](https://example.com)
- ordered, unordered, nested and `- [x]` task lists
- fenced code blocks with syntax highlighting (also inside list items)
- GFM tables with left/center/right alignment, with bordered table styles
- charts, pie/donut charts, gauges and sparklines from tables or fenced data
- `> blockquotes`
- images inserted from a bare path, `![alt](path)` or `@image path`
- speaker notes: `@notes ...`

### Directives

Presentation features are configured with short `@` directives (or the
tag-style `<uv ...>` form). A directive affects the slide it appears on, or
the block that immediately follows it. The older `<!-- ... -->` comments still
work, so existing decks keep rendering unchanged:

```markdown
@slide layout=section section="Part I" subtitle="Foundations"
@eq style=double title="Identity" number=1 align=center
@table title="Results" caption="lower is better" zebra=false
@chart type=bar title="Results" caption="lower is better"
@image assets/overview.png width=30
@code title="solution.py"
@warning title="Careful"
@columns 2 ... @qcolumns
@border style=double title="Framed" ... @qborder
@rule style=double label="SECTION"
@reveal 2
@reveal items
@slide reveal=true transition=wipe
*** 
@toc title="Roadmap" start=1
```

The tag spelling is the same thing, if you prefer it:

```markdown
<uv slide layout=section section="Part I">
<uv reveal items>
<uv columns> ... <uv qcolumns>
<uv notes> ... <uv qnotes>
```

`uv<title="skibdi">` is accepted as a compact slide directive too.

Directives have aliases so you can write what feels natural: `layout`/`section`
for `slide`, `math`/`formula`/`equation` for `eq`, `tbl`/`tabular` for `table`,
`img`/`figure`/`picture` for `image`, `graph`/`viz`/`chart` for `chart`,
`cols` for `columns`, `colbreak`/`endcol` for `endcolumns`, and
`agenda`/`contents`/`outline` for `toc`, and `build`/`step` for `reveal`. Bare
admonition names such as `@tip` are aliases for `callout`.
`frame`/`panel` alias `border`. Closers use `q`: `@qnotes`, `@qcolumns` and
`@qborder` (or `<uv qnotes>` etc.). The older `end...` names still work.

`@slide ...` sets `layout` (`default`, `center`, `top`, `left`,
`title`, `section`/`divider`, `split`), a footer `section` label, and an
optional `subtitle`. A `section` slide renders a large centered divider; its
heading becomes the title and a following paragraph (or `subtitle`) becomes the
subtitle. `title`/`hero` forces the gradient title-slide layout. `split` (alias
`two-column`) puts the first heading across the top and balances the remaining
blocks into two side-by-side columns. It also accepts `width=`, `gap=`,
`weights=` (for example `2/1`) and `divider=true`.

Front matter can set defaults for all slides: `eq_style`, `table_style`,
`chart_type`, `image_width`, `image_height`, `layout`, `theme`, `title`,
`author`, `date`, `footer`, `clock: true`, `math_engine`, `width`, `fit`,
`reveal`, `transition` and `transition_time`.
Individual theme
colours can be overridden with top-level front-matter keys such as
`accent: "#ff6b6b"`, `bg`, `fg`, `math`, `border`, `good`, `bad`, `dim`,
`code_bg` or `table_head`.

Front matter is only parsed when the file starts with a `---` block of
`key: value` lines. Malformed values are ignored rather than aborting the
deck; an unknown `theme:` falls back to `midnight`, while an invalid `--theme`
on the command line exits with status 2. Layout aliases are `section` and
`divider` for section slides, `title` and `hero` for title slides.

#### Equation boxes

`@eq ...` styles the next `$$...$$` display formula:

| Key | Values |
|:----|:-------|
| `style` | `rounded` (default), `square`, `double`, `heavy`, `simple`, `minimal`, `markdown`, `accent`, `card`, `clean`, `none` |
| `title` | text shown in the top border (or as a kicker for `card`) |
| `number` | equation number shown at bottom right, e.g. `(1)` |
| `align` | `center` (default), `left`, `right` |
| `pad` | vertical padding rows, `0`–`3` |
| `border` | explicit border colour |
| `color` | explicit math colour |

The default `rounded` style is a proper panel with the title embedded in the
top border and the number in the bottom-right corner. `double`, `square` and
`heavy` are stronger variants. `card` (alias `clean`) is available when you want
a borderless accent rule instead. `\boxed{...}` renders its own frame, so unveil
skips the outer box. Both the LaTeX and Unicode math paths share these options.

#### Tables

`@table ...` styles the next GFM table:

| Key | Values |
|:----|:-------|
| `style` | `rounded` (default), `square`, `grid`, `double`, `heavy`, `minimal`, `simple`, `markdown`, `opencode`, `github`, `presentation`, `borderless` |
| `lines` / `row_lines` | `true`/`false` draw separators between every row (aliases `rowlines`, `dividers`) |
| `title` / `caption` | table heading and footnote |
| `title_align` / `caption_align` | `left`, `center`, `right` |
| `zebra` | `true`/`false` alternating row shading |
| `header` | `true`/`false` header row |
| `compact` | `true`/`false` drop horizontal cell padding |
| `expand` | `true`/`false` stretch to the content width |
| `width` | maximum render width |
| `border` | explicit border colour |

`default` is an alias for `rounded`; `clean` is an alias for `presentation`;
`markdown`, `opencode` and `github` all draw pipe-style tables.

The default `rounded` style draws a full border and a header rule, but **not**
lines between data rows. Add `lines=true` (or use `style=grid`) when you want a
separator after every row:

```markdown
@table lines=true caption="one row per sample"

| Sample | Value |
|:-------|------:|
| a      | 1     |
| b      | 2     |
```

`opencode`/`github` use the `| --- |` pipe style; `presentation` is the quiet
borderless hairline style. Writing `|:---|` rows *inside* the table body only
adds literal dashed text rows — it is not GFM syntax for row lines.

#### Charts and data visualisation

`@chart ...` turns the next GFM table into a chart. The first column
holds category labels; every remaining column is a series named by the header:

```markdown
@chart type=bar title="Transform cost" caption="lower is better"

| Transform | Build (ms) | Query (ms) |
|:----------|-----------:|-----------:|
| DFT       | 42         | 18         |
| FFT       | 9          | 3          |
```

You can also keep the data in a fenced block. A first row of text is used as
series names; `key=value` lines set options:

````markdown
```chart
type=line
title=Throughput over releases
height=6
Version,r1,r2,r3,r4
v1,18,22,27,31
v2,24,29,34,41
```
````

Supported `type` values are:

| Type | Aliases | What it draws |
|:-----|:--------|:--------------|
| `bar` | `hbar`, `bars` (default) | horizontal bars with eighth-block ends |
| `stacked` | `stack` | horizontal composition bars |
| `columns` | `vbar`, `column`, `cols` | vertical bars with a dotted plot grid |
| `line` | `lines`, `area` | multi-series line plot |
| `spark` | `sparkline` | compact trend per series |
| `pie` | `circle` | shaded/ coloured pie with percentages |
| `donut` | `ring`, `doughnut` | pie with a labelled hole |
| `gauge` | `meter`, `bullet` | single progress value against `max` |
| `scatter` | `xy`, `points` | x/y points from numeric labels |

Useful options:

| Key | Meaning |
|:----|:--------|
| `title` / `caption` | panel heading and footnote |
| `height` | plot rows for `line`, `columns`, `scatter` and pie diameter, `3`–`10` |
| `aspect` | pie/donut width-to-height character ratio; default follows the terminal cell, `1` for square text dumps |
| `frame` | pie/donut frame: `box` (default rounded), `square`, `circle`, `none` |
| `pad` | blank cells between a pie/donut and its frame, `0`–`3` (default `1`) |
| `frame_color` | colour of the quiet pie/donut frame |
| `legend_gap` | spaces between a pie/donut and its legend (default `6`) |
| `width` | maximum panel width |
| `colors` | comma-separated colours for pie segments, series or categories |
| `legend` | `true`/`false` (automatic for multiple series and pies) |
| `percent` | `true`/`false` show series shares in the legend |
| `values` | `true`/`false` show raw values on pies and bar charts |
| `sort` | `asc`, `desc`, or `top` by the first series |
| `top` | keep only the first N categories |
| `series` | 1-based index or header name used by pie/donut/gauge/scatter |
| `min` / `max` | gauge range (default `0`–`100`) |
| `hole` | donut hole radius fraction, `0.25`–`0.75` (default `0.55`) |
| `label` | centre text for a donut |
| `border` | explicit border colour |

Pies and donuts include a faint frame and a blank margin by default so the
disk has room to breathe. Set `frame=circle` for a dotted ring instead, or
`frame=none` for a bare disk.

#### Images

The shortest form is just a path on its own line. Relative paths resolve
against the deck file, and paths with spaces can be quoted:

```markdown
assets/overview.png
"assets/another shot.png"

![Diagram](assets/diagram.svg)

@image assets/hero.jpg width=40 caption="the setup"
```

In a Kitty graphics terminal the image is transmitted as a PNG and painted into
a border that hugs the picture's natural dimensions. PNGs are sent directly;
other formats are converted with ImageMagick (`magick` or `convert`) and cached
under `~/.cache/unveil/images`. `--dump` and non-graphics terminals show a
proportional placeholder box with the resolved size instead.

Image directives accept `title`, `caption`, `width`, `height`, `style` (any
border style), `border`, `fill`, `alt` and `src`/`path`. Put an image inside
`@columns 2` to place it beside text.

#### Callouts and columns

`@note`, `@tip`, `@success`, `@warning`,
`@danger` and `@quote` wrap the next block in a coloured
admonition. `title=` sets the heading; `kind=` can be used with the generic
`@callout`.

`@columns 2` (or `3`/`4`) groups following blocks into side-by-side
columns until `@qcolumns`. A heading starts a new group so it stays
with the blocks it introduces; groups are then split into contiguous, roughly
balanced segments, so no column is left empty. `gap=` (1–4) sets the gutter,
`divider=true` draws a rule between columns, and `weights=2/1` makes one column
wider than another. Images work in columns too, which is the easiest way to put
a picture next to a few bullets.

#### Rules and borders

`@rule ...` draws a horizontal rule; `***` and `___` still work for the
plain version. Styles are `single`, `double`, `heavy`, `thick`, `dashed`,
`dotted`, `accent` and `gradient`. `label=` puts text in the middle, `width=`
sets the length, `align=` moves it, and `char=` overrides the glyph.

```markdown
@rule style=double label="PART TWO"

@rule style=dotted width=40
```

`@border ...` wraps the following blocks in a Rich panel until
`@qborder`, or just the next paragraph if you leave the closer off
out. `style=` accepts `rounded`, `square`, `double`, `heavy`, `simple`,
`minimal`, `presentation`, `markdown`, `accent`; `title=`, `caption=` and
`border=` set the label and colour. Aliases: `frame`, `panel`.

```markdown
@border style=double title="Key point" caption="read this"
A paragraph, list, code block, table or image.
@qborder
```

#### Reveals and builds

A build pauses on one slide instead of turning it into many slides. Put
`reveal=true` on the slide directive to reveal everything after the first
heading, one click at a time; lists arrive item by item:

```markdown
@slide reveal=true

## The three ideas

- first
- second
- third
```

For finer control, number steps yourself or reveal just a list:

```markdown
@reveal 1
The opening claim.

@reveal 2
The evidence.

@reveal items

- each line gets its own step
- nested blocks follow their item
```

`@reveal`, `@build N` and `@step N` also work.
Explicit and automatic numbers can be mixed; automatic steps start after the
highest explicit number. Hidden blocks are removed from the layout rather than
drawn as blanks, and the footer shows `● n/m` on built slides. `space` and `→`
walk forward through the steps and then to the next slide; `←` walks back.

Reveals work inside callouts, columns and `@border` frames, so a
container can stay put while its children arrive.

#### Transitions

Slide changes are animated by default:

```markdown
---
title: A talk
transition: fade
transition_time: 0.22
---

@slide transition=wipe

## A new section
```

The effects are `cut`, `fade`, `wipe`, `rise`, `iris`, `blinds` and `dissolve`.
Aliases include `none`/`off` (`cut`), `crossfade` (`fade`), `up` (`rise`),
`center` (`iris`) and `noise` (`dissolve`). A per-slide `transition=` overrides
the deck default. Effects are applied to whole rendered rows, so wide glyphs,
LaTeX placements and images never tear. Press `a` to turn motion off for the
session; `--transition` and `--transition-time` override the deck settings.

`@toc` (aliases `agenda`, `outline`) renders an agenda of slide titles
with the current slide marked. `start=` skips leading slides and `max=` limits
the number shown.

### Math

Inline math uses `$...$`; display math uses `$$...$$`, `\[...\]`, or a bare
`\begin{...}` environment.

```markdown
The identity $e^{i\pi} + 1 = 0$ is short.

$$
\begin{aligned}
\sum_{k=0}^{n} ar^k &= a\frac{1-r^{n+1}}{1-r} \\
\frac{d}{dx}\left[\sin x\right] &= \cos x
\end{aligned}
$$
```

**Display math is real LaTeX.** Each display block is compiled by Tectonic to
a tight PDF, rasterised at 300 dpi, cached, and placed inside a rounded frame
using the terminal's Kitty graphics protocol. That means real TeX spacing,
Computer Modern glyphs, proper big operators, `\begin{aligned}` alignment,
`\begin{cases}`, matrices, `\boxed`, `\text`, `\operatorname`, accents and
anything else the LaTeX packages provide. The formula is coloured from the
current theme, and the image background matches the slide so it blends in.

When a formula is wider than the content column, `unveil` first tries to break
it at top-level relations (`=`, `\le`, `\to`, …) and binary operators (`+`,
`-`, …) into a `gathered` display. If it still does not fit, the image is
scaled down to the available width. Tall matrices and fractions are scaled to
fit the slide height rather than cropped.

Inline math (`$...$`) stays in the text flow and uses the built-in Unicode
typesetter, so it can wrap inside paragraphs, lists and table cells without
turning the whole slide into an image. Variables and lowercase Greek use
Unicode math italics; scripts collapse to real Unicode glyphs whenever the
whole script maps (`x^2` → `𝑥²`, `r^{n+1}` → `𝑟ⁿ⁺¹`). If your terminal font
lacks those glyphs, pass `--math-upright` or put `math: upright` in the front
matter.

The Unicode typesetter remains available for every display formula too. It
draws integrals from the Unicode extension pieces (`⌠ ⎮ ⌡`), scales
delimiters, aligns `aligned` rows on a shared baseline, wraps long equations
at top-level operators, and never slices a tall fraction or matrix in half.
It is used automatically when LaTeX or graphics support is unavailable, or
when you ask for it with `--math-engine unicode` / `math_engine: unicode`.

## Keys

| Key | Action |
|:----|:-------|
| `→` `space` `j` `n` | reveal next build, then next slide |
| `←` `k` `p` | step back through builds, then previous slide |
| `g` / `G` | first / last slide |
| `[` / `]` | jump 10 slides back / forward in the focused pane |
| digits then `⏎` | jump to slide in the focused pane |
| `o` | slide overview (arrows move, `⏎` jumps) |
| `s` | speaker notes (`n`/`p` move while open) |
| `J` / `K` | scroll current slide down / up |
| `d` / `u` | scroll current slide half a page |
| `w` | cycle content width (`full`, `92`, `80%`, `60%`) |
| `f` | toggle fit-to-terminal squeezing |
| `c` | toggle two-slide compare view |
| `tab` | switch which compare pane is focused |
| `x` | swap the two compare panes |
| `a` | toggle transitions |
| `b` | blank the screen (any key returns) |
| `t` | cycle theme |
| `r` | reload the file from disk |
| `?` | help (`←`/`→` or `[`/`]` turn pages on small terminals) |
| `q` | quit |

The deck reloads automatically when the file changes. The alternate screen,
cursor and terminal modes are restored on exit, including on `SIGTERM`.

## Themes

`midnight` (default), `gruvbox`, `nord`, `dracula`, `paper`, `mono`.

Set one in front matter (`theme: nord`), with `--theme`, or cycle at runtime
with `t`.

## CLI

```
unveil DECK.md [--theme NAME] [--no-footer] [--math-upright]
               [--math-engine auto|latex|unicode] [--width WIDTH] [--fit|--no-fit]
               [--transition NAME] [--transition-time SECONDS]
               [--compare A B]
unveil DECK.md --list
unveil DECK.md --dump [--size 100x30] [--width WIDTH] [--fit|--no-fit]
                      [--dump-step N] [--compare A B]
```

`--list` prints slide titles. `--dump` prints every slide as plain text at a
fixed size, which is handy for piping, snapshots and tests. `--size WxH`
(default `100x30`, minimum `20x8`) only affects `--dump` and the automatic
dump; the interactive player always follows the terminal window. `--dump` uses
the Unicode typesetter because plain text cannot carry images. When **either**
stdin or stdout is not a TTY, `unveil` dumps automatically and still honours
`--size`.

`--math-engine auto` (the default) uses LaTeX when Tectonic, Poppler and
Kitty graphics are all available, and falls back to Unicode otherwise.
`--math-engine latex` asks for LaTeX but still falls back silently if any of
those pieces is missing or a formula fails to compile — there is no loud
error, so check the output if you need to be sure. `--math-engine unicode`
forces the built-in typesetter. The same choice can be made in front matter
with `math_engine: latex`.

`--width` accepts `full`, `92`, a percentage such as `80%`, or a cell count;
it overrides the deck's `width:` front matter. `--fit` / `--no-fit` similarly
override `fit:` and control whether spacing and visuals are squeezed to reduce
scrolling. Both keys work in the live player too (`w` and `f`).

`--transition NAME` and `--transition-time SECONDS` override the deck's
transition settings. `--compare A B` opens the interactive comparator on any
two slide numbers, or dumps only that comparison when used with `--dump`.
Comparison needs at least 40 columns in both modes. `--dump-step N` selects a
reveal step for dumps; by default every dump shows the final build so no
content is hidden.

Exit codes: `0` on success or a clean quit, `1` when the deck path cannot be
read, and `2` for invalid command-line arguments (including an unknown
`--theme`).

## Layout notes

Content uses the full terminal width by default, with a one-cell margin. Set
`width: 92` (or `width: 80%`, or a cell count) in front matter or a slide
directive to narrow it; `w` cycles the same choices live. Headings, paragraphs
and lists are left-aligned; tables, code, math and images are centered.
`layout=top`/`left` disables vertical centering.

Slides are **scrollable**, so a slide can hold arbitrarily much text, code,
charts and images. Nothing is truncated: `J`/`K` move one line, `d`/`u` half a
page, and a scrollbar in the right margin plus `↕ n/m` in the footer show the
position. `fit: true` (or `f`) squeezes inter-block spacing, chart heights and
image sizes to reduce how much scrolling is needed; it never hides content.

For dense slides, `layout=split` balances blocks into two columns, while `c`
opens a compare view showing this slide and the next one side by side. Any two
slides can be compared: use `←`/`→` to change the focused pane, `[`/`]` to jump
ten slides, digits + Enter to name a slide, `tab` to switch focus, and `x` to
swap panes. Each pane keeps its own scroll position and reveal step; `tab`
chooses which one the scroll and build keys move. `--compare A B` starts there.

The footer carries the deck title, key hints, a section label (when the slide
sets one), an elapsed clock (when `clock: true` is in front matter) and the
slide number; the second row is a progress bar. Narrow panes drop the hints
first and the footer still works down to very small widths.

## Terminal support

- **Graphics:** inline images and rasterised LaTeX use the Kitty graphics
  protocol. Kitty is the only supported terminal for graphics; other terminals
  get the Unicode math fallback and proportional image placeholders. tmux
  needs passthrough enabled (`set -g allow-passthrough on`).
- **POSIX only:** the interactive loop uses `termios` and `tty`, so Linux,
  macOS and Termux are supported; Windows is not.
- **Fonts:** charts use braille characters and box drawing. A font with good
  braille coverage (for example JetBrains Mono or Cascadia Code) makes pie and
  donut charts look smooth.
- **Colours:** true-colour terminals give the best result. `NO_COLOR` is not
  currently honoured; use theme `mono` for a greyscale presentation.

## Accessibility

`--dump` produces plain Unicode text with no graphics escapes, which is the
best input for screen readers and for capturing slides into documents. Charts
keep their numeric legends in dump mode, and images keep their path, pixel
size and caption. If you rely on colour to distinguish series, add explicit
labels in the legend or use `--theme mono`.

## License

MIT — see [LICENSE](LICENSE). Example decks are included under the same
license.
