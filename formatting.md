---
title: Formatting tour
author: unveil
theme: midnight
---

@slide layout=title section="Guide" subtitle="copy the small snippets, see the result"

# Formatting, simply

A short tour of what you can type

---

@slide layout=top section="Start"

## How a deck works

- One `.md` file is one talk
- A line with `---` starts the next slide
- A line starting with `@` sets options; for example: `@table lines=true`

@rule style=dotted label="PLAIN WORDS"

A short line starting with `@` is called a **directive**. You can also write
`<uv ...>` if you prefer tags; the older `<!-- ... -->` form still works.
The rest of this deck shows you where to put them.

---

@slide layout=top section="Text"

## Text

@rule style=dotted label="TYPE THIS"

```markdown
**bold**   *italic*   ~~old~~
`code`   [a link](https://example.com)
> a quote
Inline math: $e^{i\pi}+1=0$
```

@rule style=dotted label="YOU GET"

**bold**   *italic*   ~~old~~

`code`   [a link](https://example.com)

> a quote

Inline math: $e^{i\pi}+1=0$

---

@slide layout=top section="Lists"

## Lists

@rule style=dotted label="TYPE THIS"

```markdown
- first
- second
  - nested item
- [x] done
- [ ] not done
```

@rule style=dotted label="YOU GET"

- first
- second
  - nested item
- [x] done
- [ ] not done

---

@slide layout=top section="Tables"

## Tables with lines between rows

@rule style=dotted label="TYPE THIS"

Put `table: lines=true` just above the table.

@rule style=dotted label="YOU GET"

@table title="Scores" caption="lines=true" lines=true

| Name | Score |
|:-----|------:|
| Ana  | 10    |
| Bo   | 8     |

---

@slide layout=top section="Tables"

## Two table styles

`style=opencode` gives you pipes. `style=grid` gives you every line.

@table style=opencode title="pipes"

| Key | Meaning |
|:----|:--------|
| A   | first   |
| B   | second  |

@table style=grid title="grid"

| Key | Meaning |
|:----|:--------|
| A   | first   |
| B   | second  |

---

@slide layout=top section="Decor"

## Lines

Put one of these before `***`, or just write the directive on its own line.

@rule style=single label="single"

@rule style=double label="double"

@rule style=heavy label="heavy"

@rule style=dotted label="dotted"

@rule style=accent label="gradient"

---

@slide layout=top section="Decor"

## Borders around content

Wrap anything in a frame. Try `style=square`, `double`, `heavy`, or
`presentation`.

@border style=double title="A double frame" caption="plain markdown inside"
This text is inside a border.

- it can hold lists
- tables
- code
- even images
@qborder

---

@slide layout=top section="Code"

## Code

@code title="hello.py"

```python
def hello(name):
    print(f"hello, {name}")

hello("terminal")
```

---

@slide layout=top section="Callouts"

## Callouts

@note title="Note"
Use a note for a small aside.

@tip title="Tip"
Press `?` in the presentation to see every key.

@warning title="Careful"
Writing `|:---|` inside a table body is just text. Use `lines=true`.

---

@slide layout=top section="Math"

## Math

Inline math stays in the sentence: $e^{i\pi}+1=0$.

@eq style=double title="Euler's identity" number=1

$$
e^{i\pi}+1=0
$$

Change `style=` to `square`, `heavy`, or `card`.

---

@slide layout=top section="Charts"

## A chart from a table

@chart type=bar title="Build cost" caption="lower is better" values=true

| Step   | ms |
|:-------|---:|
| parse  | 12 |
| render | 31 |
| paint  | 7  |

---

@slide layout=top section="Charts"

## A circle

The disk gets a faint frame and space around it. Try `frame=circle` too.

@chart type=pie title="Four equal parts" colors="#7aa2f7,#bb9af7,#9ece6a,#e0af68"

| Part  | Value |
|:------|------:|
| One   | 25    |
| Two   | 25    |
| Three | 25    |
| Four  | 25    |

---

@slide layout=top section="Charts"

## A donut

@chart type=donut title="Four parts" hole=.6 label=100% colors="#7aa2f7,#bb9af7,#9ece6a,#e0af68"

| Part  | Hours |
|:------|------:|
| One   | 10    |
| Two   | 20    |
| Three | 30    |
| Four  | 40    |

---

@slide layout=top section="Images"

## Images

Just put a path on its own line. The border fits the image shape.

@image assets/demo.png width=20 height=6 caption="320x160 px"

---

@slide layout=top section="Builds"

## Reveal a list, one click at a time

@rule style=dotted label="TYPE THIS"

```markdown
@reveal items
- first click
- second click
- third click
```

@rule style=dotted label="YOU GET"

Press `space` once per line; `←` walks back. The footer shows `● 1/3`.

@reveal items

- first click
- second click
- third click

To build a whole slide, use `@slide reveal=true` instead.

---

@slide layout=top section="Motion" transition=wipe

## Motion and comparison

This slide arrived with a **wipe**. Try these in front matter or on one slide:

- `transition: fade` — the default
- `@slide transition=rise` — one slide, one effect
- `transition_time: 0.3` — slower motion

Press `c` for compare view. `tab` switches panes, `x` swaps them, and digits
plus Enter name any slide in the focused pane. Press `a` to stop all motion.

---

@slide layout=top section="Images"

## Image beside text

Use `columns: 2`. Put the image in one column and the words in the other.

@columns 2

### Picture

@image assets/demo.png width=14 height=5 caption="demo asset"

### Words

- short sentences
- a few bullets
- no wrestling with layout

@qcolumns

---

@slide layout=top section="Reference"

## Cheat sheet

| To do this | Type this |
|:-----------|:----------|
| new slide | `---` |
| row lines | `@table lines=true` |
| styled line | `@rule style=double label="..."` |
| framed block | `@border style=double` + `@qborder` |
| circle chart | `@chart type=pie` |
| side by side | `@columns 2` + `@qcolumns` |
| reveal a list | `@reveal items` + list |
| build a slide | `@slide reveal=true` |
| animate a slide | `@slide transition=wipe` |
| compare slides | `c`, `tab`, digits + Enter |

---

@slide layout=center section="End"

# That is it

Run it again with `python3 -m unveil formatting.md`

@notes
The point of this deck is to be copied. Every slide shows the small piece of
Markdown that produces it.
@qnotes
