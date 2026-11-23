# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Short directive syntax: `@reveal items`, `@slide layout=title`, the tag
  spelling `<uv slide layout=title>` / `uv<title="skibdi">`, and `q` closers
  such as `@qnotes`, `@qcolumns` and `@qborder`. The original `<!-- ... -->`
  form (and `end...` closers) is still accepted.
- Slides are scrollable instead of cropped, so a slide can hold arbitrarily
  much content. `J`/`K` scroll a line, `d`/`u` half a page; the footer shows
  `↕ n/m` and a scrollbar sits in the right margin.
- Full-width layout by default with `width:` front matter / slide option,
  `--width`, and a `w` key that cycles `full`, `92`, `80%` and `60%`.
- `fit:` front matter, `--fit` / `--no-fit` and an `f` key squeeze inter-block
  spacing, chart heights and image sizes to reduce scrolling.
- Slide-level `layout=split` (alias `two-column`) with balanced columns,
  optional `gap=`, `divider=true` and `weights=`.
- Two-slide compare view via `c`, now able to show **any** two slides. Each
  pane keeps its own scroll position and reveal step; `tab` switches focus,
  `x` swaps panes, `[`/`]` jump ten slides and digits + Enter name a slide.
- Click-to-reveal builds via `<!-- slide: reveal=true -->`, `<!-- reveal: N -->`
  and `<!-- reveal: items -->` (aliases `build` and `step`), including nested
  reveals in frames, callouts and columns. `space`/`→` advance builds before
  changing slides and the footer shows `● n/m`.
- Transitions: `cut`, `fade`, `wipe`, `rise`, `iris`, `blinds` and `dissolve`,
  set in front matter, on a slide or with `--transition`/`--transition-time`.
  `a` toggles motion live; effects are row-level so images and wide glyphs are
  never sliced.
- `--compare A B` opens any comparison interactively or dumps just that pair.
  `--dump-step N` captures an earlier reveal step; dumps otherwise show every
  build.
- `[` / `]` jump ten slides in the focused pane.
- `showcase.md`: a 56-slide Director's Cut exercising every feature of the TUI,
  including builds, transition samples and guided comparisons.
- `columns` blocks now balance groups by rendered height and support `gap=`,
  `divider=` and `weights=`.

### Changed

- The footer now presents ordered metadata chips (section, clock, scroll,
  reveal, page) and keeps the deck title readable; a quiet row separates dense
  content from the progress bar.
- Title slides use a small section kicker, a diamond gradient rule and a
  closing underline so they read as an intentional opening rather than a plain
  centred heading.
- The help overlay adapts to the terminal: full labels when there is room,
  compact labels in two columns when short, and paged compact labels on very
  small screens. `←`/`→` or `[`/`]` turn pages when paging is needed.
- Compare panes replace the rendered slide heading with their pane header, so
  the slide title is not shown twice.

### Fixed

- Large bordered equations no longer get re-wrapped into a broken box: panel
  width accounts for padding and border, and matrix delimiters stay aligned.
- Footer chips no longer overflow 20-column terminals, and the help overlay no
  longer clips its border or later key bindings at 40×20 and 20×8.

## [1.0.0] — 2026-11-21

First stable release.

### Added

- Markdown slide decks rendered with Rich: headings, lists, quotes, code,
  tables, callouts, table of contents, speaker notes, overview and help.
- Real LaTeX display math through Tectonic and `pdftoppm`, cached on disk and
  painted with Kitty graphics. `--math-engine auto|latex|unicode` selects the
  renderer; `--math-upright` switches to upright Unicode glyphs.
- Bordered equation panels with titles/numbers, plus `card`, `clean`,
  `double`, `heavy` and other styles via `<!-- eq: ... -->`.
- Bordered tables (`rounded` by default) with `style=opencode`/`github` for
  pipe tables and `lines=true` for row separators.
- Charts from Markdown tables or fenced `chart` blocks: bar, stacked,
  columns, line, spark, pie, donut, gauge and scatter. Pies and donuts are
  smooth braille circles with their own faint frame and breathing room.
- Images from plain paths, `![alt](path)` or `<!-- image: ... -->`, with PNGs
  sent directly and other formats cached through ImageMagick. Dimension-fitted
  borders and side-by-side placement with `columns`.
- Presentation decorations: `<!-- rule: ... -->` for styled horizontal rules
  and `<!-- border: ... -->` / `<!-- endborder -->` for framed content.
- Hot reload, theme switching, blank screen, `demo.md` and the `formatting.md`
  copy-and-paste tour.

### Fixed

- Pie/donut aspect ratio in terminals and plain-text dumps.
- `--size` now applies to automatic non-TTY dumps.
- Kitty placements retransmit when an image file changes.
- Unicode digits no longer crash the "go to slide" prompt.
- Failed LaTeX compiles are cached for the lifetime of the process.
- Tables/charts nested in columns or callouts use the available width.

## [0.1.0]

Initial development release.
