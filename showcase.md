---
title: The Whole Toolkit — Director's Cut
author: unveil
date: 2026-11-23
theme: midnight
clock: true
footer: unveil
width: full
transition: fade
transition_time: 0.22
---

@slide layout=title section="Grand tour"

# The Whole Toolkit

One markdown file. Every trick in the terminal.

@notes
Welcome. This is not a feature list — it is a stage. Press space to move
through the builds, c to compare any two slides, and a to kill the motion if
the room has a slow projector. The whole deck is one markdown file.
@qnotes

---

@slide layout=top section="Start here"

## How to drive this deck

| Key | What it does |
|:----|:-------------|
| `space` | reveal the next build, then the next slide |
| `←` / `→` | step back / forward through builds |
| `c` | open the two-slide comparator |
| `tab` | switch which compare pane has focus |
| `x` | swap the two panes |
| `[` `]` or digits + `⏎` | pick any slide for the focused pane |
| `J` / `K`, `d` / `u` | scroll a long slide |
| `w` / `f` / `a` | width, fit, transitions |

> Watch the footer: `● 2/5` means "build two of five". It is your runway.

@notes
This is the only slide that looks like a manual. Everything after it is a
demonstration. Remind the room that arrows walk builds backwards too.
@qnotes

---

@slide layout=section section="Part I" subtitle="words, lists, code, decorations"

# I · Words

---

@slide layout=top section="Words"

## A sentence with everything in it

**Bold** moves the eye, *italics* soften it, ~~struck text~~ retires it,
`inline code` keeps it honest, and $e^{i\pi}+1=0$ keeps it beautiful.
Links work too: [the terminal is the interface](https://example.com).

> A slide deck should read like a talk, not like a configuration file.

@rule style=dotted label="SOURCE"

```markdown
**Bold** *italic* ~~struck~~ `code` $e^{i\pi}+1=0$
[link](https://example.com) and > a quote
```

---

@slide layout=top section="Lists" reveal=true

## Lists that reveal themselves

1. Collect the raw material
   - screenshots from three tools
   - one very long spreadsheet
   - a napkin sketch
2. Find the shape
   - remove the duplicate story
   - keep the surprising number
   - write the sentence first
3. Build the deck
   - [x] headings
   - [x] charts
   - [ ] rehearsal

@notes
Hands off the keyboard. One press per bullet. This is `reveal=true` on the
slide directive — no per-block markup at all.
@qnotes

---

@slide layout=top section="Code"

## Code that arrives already highlighted

@code title="signal.py"

```python
import numpy as np

def spectrum(signal, window=np.hanning):
    """Return a windowed magnitude spectrum."""
    framed = signal * window(len(signal))
    return np.abs(np.fft.rfft(framed))

if __name__ == "__main__":
    t = np.linspace(0, 1, 48_000)
    print(spectrum(np.sin(2 * np.pi * 440 * t))[:5])
```

---

@slide layout=top section="Callouts"

## Five ways to interrupt yourself

@note title="Note"
A note is a small aside that does not break the rhythm.

@tip title="Tip"
Press `f` to squeeze a crowded slide; press it again to restore the spacing.

@success title="Success"
The equation box fits its content now, even for a four-row matrix.

@warning title="Careful"
A bare `|:---|` inside a table body is text. Use `table: lines=true`.

@danger title="Danger"
Never paste a secret into a deck that gets recorded.

---

@slide layout=top section="Decor"

## Rules for every mood

@rule style=single label="single"

@rule style=double label="double"

@rule style=heavy label="heavy"

@rule style=dashed label="dashed"

@rule style=dotted label="dotted"

@rule style=accent label="accent"

@rule style=gradient label="gradient"

@rule style=thick label="thick" char="◆"

---

@slide layout=top section="Part II" subtitle="tables and columns"

# II · Structure

---

@slide layout=top section="Tables"

## The default table has a border

| Model | Latency | Notes |
|:------|--------:|:------|
| A     | 12 ms   | small  |
| B     | 31 ms   | fast   |
| C     | 7 ms    | tiny   |

Add `lines=true` when every row needs its own rule:

@table title="With row lines" caption="lines=true" lines=true zebra=true

| Sample | Value |
|:-------|------:|
| alpha  | 1     |
| beta   | 2     |
| gamma  | 3     |

---

@slide layout=top section="Tables"

## Three dialects of the same table

@table style=opencode title="opencode"

| Key | Meaning |
|:----|:--------|
| A   | first   |
| B   | second  |

@table style=github title="github"

| Key | Meaning |
|:----|:--------|
| A   | first   |
| B   | second  |

@table style=grid title="grid" compact=true

| Key | Meaning |
|:----|:--------|
| A   | first   |
| B   | second  |

---

@slide layout=top section="Columns"

## Side by side, no wrestling

@columns 2 gap=4 divider=true

### Left brain

- short sentences
- one idea per bullet
- room to breathe

### Right brain

@table style=presentation compact=true

| Signal | Meaning |
|:-------|:--------|
| ↑      | rising  |
| ↓      | falling |

@qcolumns

---

@slide layout=split section="Split slide" gap=3 divider=true

## Two columns, one slide

### The problem

- too many bullets
- tiny text
- audience squinting

### The fix

- `layout=split`
- balanced blocks
- a real divider

### Why it works

`split` keeps the first heading across the top, then divides the remaining
groups by their rendered height. Nothing is cropped.

### Try it

Add `count=3` for three columns, `weights=2/1` to bias them.

---

@slide layout=section section="Part III" subtitle="bars, lines, circles"

# III · Data

---

@slide layout=top section="Charts"

## Bars: two series, one story

@chart type=bar title="Transform cost" caption="lower is better" values=true

| Transform | Build (ms) | Query (ms) |
|:----------|-----------:|-----------:|
| DFT       | 42         | 18         |
| FFT       | 9          | 3          |
| Wavelet   | 21         | 11         |
| Sparse    | 15         | 6          |

---

@slide layout=top section="Charts"

## Columns and lines

@chart type=columns title="Throughput by release" height=5

| Release | r1 | r2 | r3 |
|:--------|---:|---:|---:|
| v1      | 18 | 22 | 27 |
| v2      | 24 | 29 | 34 |
| v3      | 31 | 38 | 41 |

@chart type=line title="Latency over a week" height=5

| Day | p50 | p99 |
|:----|----:|----:|
| Mon | 12  | 40  |
| Tue | 11  | 38  |
| Wed | 14  | 44  |
| Thu | 9   | 31  |

---

@slide layout=top section="Charts"

## Stacked and sparkline

@chart type=stacked title="Where the time goes" percent=true

| Stage   | Parse | Render | Paint |
|:--------|------:|-------:|------:|
| cold    | 12    | 31     | 7     |
| warm    | 4     | 19     | 5     |
| cached  | 1     | 8      | 3     |

@chart type=spark title="Requests per hour" height=3

| Hour | Requests |
|:-----|---------:|
| 08   | 12       |
| 09   | 31       |
| 10   | 48       |
| 11   | 39       |

---

@slide layout=top section="Charts"

## A pie with room to breathe

The faint frame and blank padding are deliberate: a disk needs space.
Try `frame=circle` or `frame=none` in the directive.

@chart type=pie title="Where a day goes" values=true colors="#7aa2f7,#bb9af7,#9ece6a,#e0af68,#f7768e"

| Part    | Hours |
|:--------|------:|
| Sleep   | 8     |
| Work    | 9     |
| Food    | 2     |
| Moving  | 3     |
| Rest    | 2     |

---

@slide layout=top section="Charts"

## A donut with a label

@chart type=donut title="Completion" hole=.6 label=83% frame=circle colors="#9ece6a,#565b78"

| Part     | Value |
|:---------|------:|
| Done     | 83    |
| Left     | 17    |

---

@slide layout=top section="Charts"

## Gauge and scatter

@chart type=gauge title="Battery" min=0 max=100

| Metric  | Value |
|:--------|------:|
| Battery | 72    |

@chart type=scatter title="Size vs. speed" height=5

| Size | ms |
|:-----|---:|
| 1    | 3  |
| 2    | 5  |
| 4    | 9  |
| 8    | 14 |
| 16   | 27 |

---

@slide layout=top section="Charts"

## Data in a fenced block

No table needed — the chart block carries its own data and options.

```chart
type=line
title="Throughput over releases"
height=6
Version,r1,r2,r3,r4
v1,18,22,27,31
v2,24,29,34,41
v3,31,38,44,52
```

---

@slide layout=section section="Part IV" subtitle="integrals, matrices, boxes"

# IV · Math

---

@slide layout=top section="Math"

## Inline and displayed

Inline math sits in the sentence: $\hat{f}(\xi)=\int f(t)e^{-2\pi i\xi t}\,dt$.
Display math gets a box, a title and a number.

@eq style=double title="Euler's identity" number=1

$$
e^{i\pi}+1=0
$$

With Tectonic installed the same source becomes a typeset image; without it
the built-in Unicode typesetter draws this directly.

---

@slide layout=top section="Math"

## A tall construct stays intact

@eq style=rounded title="A matrix and its determinant" number=2

$$
A = \begin{pmatrix}
a_{11} & a_{12} & \cdots & a_{1n} \\
a_{21} & a_{22} & \cdots & a_{2n} \\
\vdots & \vdots & \ddots & \vdots \\
a_{m1} & a_{m2} & \cdots & a_{mn}
\end{pmatrix}
\qquad
\det(A) = \sum_{\sigma \in S_n} \operatorname{sgn}(\sigma) \prod_{i=1}^{n} a_{i,\sigma(i)}
$$

The delimiters line up and the panel width accounts for its own padding.

---

@slide layout=top section="Math"

## A long equation, still on one line

@eq style=square title="2-D Fourier transform" number=3

$$
\int_{-\infty}^{\infty}\int_{-\infty}^{\infty} f(x,y)\,e^{-2\pi i(ux+vy)}\,dx\,dy = F(u,v) = G(u) + H(v) + K(u,v) + L(u,v)
$$

---

@slide layout=top section="Math"

## Every box style

@eq style=card title="card"

$$
\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}
$$

@eq style=clean title="clean" align=left

$$
\frac{d}{dx}\left(x^n\right)=nx^{n-1}
$$

@eq style=heavy title="heavy" number=4

$$
\sum_{k=1}^{n} k = \frac{n(n+1)}{2}
$$

---

@slide layout=top section="Math"

## Several rows in one box

@eq style=rounded title="Wave equation" number=5 pad=2

$$
\frac{\partial^2 u}{\partial t^2} = c^2 \nabla^2 u \\
u(x,0) = f(x), \qquad \frac{\partial u}{\partial t}(x,0) = g(x)
$$

@rule style=dotted label="ALIGN AND PAD ARE OPTIONS"

---

@slide layout=section section="Part V" subtitle="pictures and proportions"

# V · Pictures

---

@slide layout=top section="Images"

## A path is enough

assets/demo.png

The border fits the image dimensions, and a plain-text dump shows a
proportional placeholder with the resolved size.

@image assets/demo.png width=26 caption="320 × 160 px" title="The demo asset"

---

@slide layout=top section="Images"

## A picture beside its explanation

@columns 2 gap=3

### The picture

@image assets/demo.png width=18 height=6 caption="in a column"

### The explanation

- paths resolve relative to the deck
- PNG goes straight to Kitty
- other formats go through ImageMagick
- dumps show a placeholder instead

@qcolumns

---

@slide layout=top section="Images"

## A framed picture and a rule

@border style=rounded title="Figure 1"

@image assets/demo.png width=24 caption="framed, with a caption"

@qborder

@rule style=double label="END OF FIGURE"

---

@slide layout=section section="Part VI" subtitle="click, build, reveal"

# VI · Builds

---

@slide layout=top section="Builds" reveal=true transition=wipe

## The case for doing less at once

They remember three things from a talk, not thirty. Builds let the room read,
nod, and then meet the next idea on its own.

1. Say the sentence
2. Let it land
3. Show the evidence

@chart type=bar title="Recall after a talk" values=true

| Format  | Recall |
|:--------|-------:|
| one wall of text | 12 |
| three quiet builds | 61 |

> Press `space` four times. The arrows walk it backwards.

@notes
This slide uses slide-level reveal=true, so the bullets, chart and quote each
get their own click. The transition into the slide is a wipe — notice it.
@qnotes

---

@slide layout=top section="Builds"

## Explicit choreography

@reveal 1

Every build has a number. This one is step one.

@reveal 2

Step two can be a sentence, a callout, a chart — anything.

@chart type=columns title="Appears at step three" values=true reveal=3

| Moment | Impact |
|:-------|-------:|
| first  | 18     |
| second | 42     |
| third  | 71     |

@reveal 4

@warning title="Step four"
Explicit numbers and automatic builds can be mixed freely.

@notes
Four explicit steps. The chart carries reveal=3 in its own directive.
@qnotes

---

@slide layout=top section="Builds"

## Reveal a list, not a whole slide

The heading is already here. The list arrives one line at a time.

@reveal items

- `@reveal items` before a list
- each item claims the next number
- nested blocks follow their item
- `space` walks the whole sequence

@rule style=dotted label="THE FOOTER KNOWS WHERE YOU ARE"

---

@slide layout=top section="Builds"

## A build inside a frame

@border style=double title="Nested reveals work too"

@reveal 1

First line inside the frame.

@reveal 2

Second line inside the same frame.

@qborder

The container stays put; only its children arrive.

---

@slide layout=section section="Part VII" subtitle="motion with restraint"

# VII · Motion

---

@slide layout=top section="Motion" transition=fade

## fade

The default: the old frame dims to the background, the new one brightens up.

@table style=presentation compact=true

| Phase | What you see |
|:------|:-------------|
| 0–50% | the old slide receding |
| 50%   | a breath of empty stage |
| 50–100% | the new slide arriving |

---

@slide layout=top section="Motion" transition=wipe

## wipe

Top-down. Good for a new section, or for a slide that is a list of steps.

@chart type=spark title="A clean edge" height=3

| Rows | Reveal |
|:-----|-------:|
| 1    | 2      |
| 2    | 6      |
| 3    | 12     |
| 4    | 20     |

---

@slide layout=top section="Motion" transition=rise

## rise

Bottom-up. Use it when the conclusion should feel like it is climbing.

@rule style=gradient label="UPWARD"

```
transition: rise
```

Set it in front matter for the whole deck, or on a single `@slide`.

---

@slide layout=top section="Motion" transition=iris

## iris

An opening circle from the centre. The most theatrical option — use sparingly.

@chart type=donut title="Focus" hole=.6 label=100% frame=circle

| Part  | Value |
|:------|------:|
| Focus | 100   |

---

@slide layout=top section="Motion" transition=blinds

## blinds

Alternating bands arrive in sequence. It reads as structure rather than flash.

| Band | Starts at |
|:-----|----------:|
| even rows | 0% |
| odd rows  | 28% |

@rule style=dotted label="BAND HEIGHT: 3 ROWS"

---

@slide layout=top section="Motion" transition=dissolve

## dissolve

A deterministic sparkle from old to new. Row-level, so wide glyphs and Kitty
images never tear.

@chart type=pie title="Noise, but tidy" values=true

| Part | Value |
|:-----|------:|
| old  | 44    |
| new  | 56    |

---

@slide layout=top section="Motion" transition=cut

## cut

No animation. Perfect for a dense reference slide you want to appear instantly.

Press `a` to turn all motion off for the rest of the session; press it again to
bring it back. `transition: none` in front matter does the same at author time.

@notes
Some rooms hate motion. There is no shame in cutting it entirely.
@qnotes

---

@slide layout=section section="Part VIII" subtitle="any two slides, side by side"

# VIII · Compare

---

@slide layout=top section="Compare"

## Compare any two slides

Press `c`. The divider shows which pane is focused; the header names the slide.

| Key | In compare view |
|:----|:----------------|
| `←` `→` | change the focused pane's slide |
| `tab` | switch focus to the other pane |
| `[` `]` | jump the focused pane 10 slides |
| digits + `⏎` | type any slide number for that pane |
| `x` | swap the two panes |
| `J` / `K` | scroll only the focused pane |
| `space` | reveal builds in the focused pane |

Each pane keeps its own scroll position and reveal step.

---

@slide layout=top section="Compare"

## Left: the raw numbers

This is slide 47 in the deck: two series, four transforms.

@chart type=bar title="Transform cost" values=true

| Transform | Build (ms) | Query (ms) |
|:----------|-----------:|-----------:|
| DFT       | 42         | 18         |
| FFT       | 9          | 3          |
| Wavelet   | 21         | 11         |
| Sparse    | 15         | 6          |

@notes
Try it live: press c here — slide 48 is already on the right. Press tab, then
arrow keys or digits + Enter, to step either side anywhere.
@qnotes

---

@slide layout=top section="Compare"

## Right: the story those numbers tell

This is slide 48. Put it beside slide 47 and the argument is visible at a glance.

@chart type=bar title="After the rewrite" values=true

| Transform | Build (ms) | Query (ms) |
|:----------|-----------:|-----------:|
| DFT       | 42         | 18         |
| FFT       | 6          | 2          |
| Wavelet   | 14         | 7          |
| Sparse    | 9          | 4          |

@table style=presentation compact=true

| Claim | Evidence |
|:------|:---------|
| faster | bars, right pane |
| smaller | footer, both panes |

---

@slide layout=top section="Compare"

## Three comparisons worth trying

1. **47 ↔ 48** — raw numbers against the rewrite
2. **5 ↔ 34** — a quiet list against a full build
3. **1 ↔ 56** — how the story opens against how it ends

Type `c`, then digits + `⏎` for the left pane, `tab`, digits + `⏎` for the
right. Nothing is limited to neighbouring slides.

---

@slide layout=section section="Part IX" subtitle="a deck that adapts to you"

# IX · Living deck

---

@slide layout=top section="Scrolling"

## There is no height limit

A slide can be as long as the thought it carries. Nothing is cropped: scroll
with `J` / `K`, or `d` / `u` for half a page. The footer shows where you are.

1. Sampling — turn the air into numbers
2. Windowing — keep the edges honest
3. Transforms — change the point of view
4. Filters — keep what matters
5. Compression — throw away the invisible
6. Transmission — move it cheaply
7. Decoding — rebuild the same story
8. Playback — put it back in the air
9. Measurement — did anyone notice?
10. Iteration — do it again, faster
11. Documentation — write it down
12. Rehearsal — say it out loud
13. Timing — find the long pauses
14. Feedback — listen to the room
15. Revision — cut a third of it
16. Rehearsal again — it always helps
17. Sleep — the best editor
18. Final pass — fix the one typo
19. Stage check — cables, fonts, terminal
20. Deep breath — you know this
21. Present — one slide at a time
22. Questions — the best part
23. Notes — save them for next time
24. Archive — keep the source
25. Share — someone else will learn

@rule style=dotted label="SCROLL TO THE BOTTOM"

---

@slide layout=top section="Fit and width" width=60 fit=true

## Squeezed into sixty columns

This slide opts into `width=60` and `fit=true`. The gaps tighten, charts get
shorter and images shrink, so more of the story fits without scrolling.
Press `w` to cycle widths and `f` to toggle squeezing, live.

@chart type=bar title="Before / after fitting" values=true

| Slide | Lines |
|:------|------:|
| loose | 31    |
| fit   | 19    |

---

@slide layout=top section="Themes"

## Six ways to dress the same slide

Themes are `midnight`, `gruvbox`, `nord`, `dracula`, `paper` and `mono`.
Set one in front matter with `theme: nord`, choose it with `--theme`, or
cycle through them live with `t`. `mono` is the greyscale choice.

@table style=presentation compact=true

| Theme | Mood |
|:------|:-----|
| midnight | cool and quiet |
| gruvbox | warm paper |
| nord | blue-grey |
| dracula | violet neon |
| paper | light and calm |
| mono | no colour at all |

---

@slide layout=top section="Notes"

## The notes are yours alone

Press `s` on this slide. The audience sees the slide; you see the script.

@notes
Slow down here. Mention that everything in this deck is one markdown file,
that transitions and reveal steps are just comments, and that the file reloads
with r if you edit it during the talk. Then take a question.
@qnotes

---

@slide layout=center section="End"

# That is everything

One file. No slides app. No browser.

@notes
Thank them. The source is showcase.md, next to demo.md and formatting.md.
Invite them to copy a slide they liked.
@qnotes

---

@slide layout=title section="Thank you" transition=iris

# Thank you

Questions? Press `?` for help, `c` to compare, or `q` to leave.
