---
title: IMPOSSIBLE
author: Atom Moss Studios
theme: midnight
transition: fade
transition_time: 0.18
animation: none
---

@slide layout=title animation=type animation_time=1.1

# IMPOSSIBLE

Things a terminal should not be able to do.

A live demo made of nothing but characters, cached PNGs and stubbornness.
No browser. No slide app. No video.

@notes
Press space. Every character you see is painted by the terminal in real time.
@qnotes

---

@slide animation=draw animation_time=0.8

## A frame drawn one column at a time

The bright edge is a cursor. The rest is Rich text with every style span still
attached — nothing is pre-rendered into an image.

@border style=double title="drawn, not printed"

| 01 | 02 | 03 | 04 | 05 | 06 | 07 |
|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| ⇢  | ⇢  | ⇢  | ⇢  | ⇢  | ⇢  | ⇢  |

@qborder

---

@slide animation=type animation_time=0.9

## This whole slide is being typed

Not a status line. Not a one-line gimmick. Every heading, table cell and code
token is revealed character by character, in reading order.

```python
for character in slide:
    terminal.paint(character)
```

The cursor blinks between strokes, then vanishes when the last glyph lands.

---

@slide animation=slide animation_time=0.7

## Objects arrive from off-stage

Press space and watch each object glide in. These are reveal builds, so the
stage stays put while only the new object moves.

@reveal items

- a bullet slides in from the left
- the next one follows, independently
- columns, frames and images can do the same
- nothing is cropped to fake the motion

@notes
The animation is a pure transform on the finished Rich frame. Build keys keep
unchanged rows exactly where they are.
@qnotes

---

@slide animation=rise animation_time=0.85

## Charts rise from below the fold

@chart type=bar title="Render cost" caption="milliseconds per frame — lower is better"

| Effect       | Build | Paint |
|:-------------|------:|------:|
| typewriter   | 4     | 6     |
| slide-in     | 5     | 7     |
| draw         | 6     | 9     |
| spark        | 11    | 14    |

The bars are eighth-block glyphs. The motion is a rigid frame translation with
cubic easing.

---

@slide animation=grow animation_time=0.8

## A pie chart blooming from the centre

@chart type=pie title="Where the time goes" caption="a complete 100x30 frame"

| Stage        | Share |
|:-------------|------:|
| typesetting  | 42    |
| rasterising  | 28    |
| composition  | 18    |
| painting     | 12    |

Braille dots give each slice a smooth ring. No graphics protocol required.

---

@slide animation=draw animation_time=0.95

## Mathematics, revealed stroke by stroke

@eq style=double title="The transform" number=1

$$
\hat{f}(\xi)=\int_{-\infty}^{\infty} f(t)\,e^{-2\pi i\xi t}\,dt
$$

With Tectonic and Kitty graphics this is a real LaTeX image. Here it is the
built-in Unicode typesetter — same frame, same animation.

---

@slide animation=spark animation_time=0.9

## A table, cell by cell

@table style=double lines=true title="Terminals are renderers" caption="every cell is addressable"

| Layer      | Glyphs | Colour | Motion |
|:-----------|:------:|:------:|:------:|
| text       | ✓      | ✓      | ✓      |
| borders    | ✓      | ✓      | ✓      |
| braille    | ✓      | ✓      | ✓      |
| Kitty PNG  | —      | ✓      | ✓      |

The spark effect uses a stable per-cell order, so replays look identical.

---

@slide animation=slide-right animation_time=0.8

## Images fly in from the right

@image assets/demo.png width=38 caption="a real PNG, placed inside the text frame"

In a Kitty terminal the placement itself travels with the frame. Everywhere
else the proportional placeholder box moves instead. Same deck, same syntax.

---

@slide animation=pop animation_time=0.7

## Columns that snap into place

@columns 2

### Left stage

- easing with a slight overshoot
- the frame settles like a spring
- headings travel with their blocks

### Right stage

- reveal builds work inside columns
- images can sit beside prose
- the layout is still pure Markdown

@qcolumns

---

@slide layout=section animation=grow transition=wipe animation_time=0.6

## INTERMISSION

Still plain text. Still one file.

---

@slide animation=type animation_time=0.75

## Wait — that was real math?

Display formulas are compiled by Tectonic, rasterised by Poppler and painted
with the Kitty graphics protocol. The cache lives in
`~/.cache/proscenium/latex`.

$$
\begin{aligned}
\nabla \cdot \mathbf{E} &= \frac{\rho}{\varepsilon_0} \\
\nabla \cdot \mathbf{B} &= 0
\end{aligned}
$$

No Tectonic? The Unicode fallback draws the same operator spacing with `⌠⎮⌡`.

---

@slide animation=draw animation_time=0.8

## Compare any two slides in one frame

Press `c` to split the stage. `tab` switches panes; `x` swaps them. Each pane
keeps its own scroll position and reveal step.

| Key     | Action                       |
|:--------|:-----------------------------|
| `c`     | open or close compare view   |
| `tab`   | focus the other pane         |
| `x`     | swap panes                   |
| `1…9`   | jump to a slide              |

Start anywhere with `proscenium impossible.md --compare 5 9`.

---

@slide animation=spark animation_time=0.8

## It is all one Markdown file

```markdown
@slide layout=title animation=type
@reveal items
@chart type=pie title="Where the time goes"
@anim slide-right
@image assets/demo.png width=38
@qnotes
```

Directives read like stage directions. The old `<!-- ... -->` comments and
`<uv ...>` tags still work, so existing decks keep rendering.

---

@slide layout=title animation=fade animation_time=0.7

# YOUR TURN

```sh
pip install git+https://github.com/atommossstudios/proscenium.git
proscenium impossible.md
```

Press `?` for every key. Press `s` for the speaker notes you just watched.

@notes
If you only remember one command: `proscenium impossible.md`. Thank you.
@qnotes
