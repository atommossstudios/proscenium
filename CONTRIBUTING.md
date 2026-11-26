# Contributing to proscenium

Thanks for helping make terminal presentations feel good.

## Quick setup

```sh
git clone https://github.com/atommossstudios/proscenium.git
cd proscenium
python -m pip install -e '.[dev]'
python -m pytest -q
python -m proscenium demo.md
```

## Before opening a PR

- Keep changes Python/Rich-only in the core renderer.
- Add a test for any parser or layout change.
- Run `python -m pytest -q` and `python -m build`.
- Update `README.md` / `formatting.md` when syntax changes.
- Keep the Unicode fallback working without Tectonic or graphics support.

## Ideas worth contributing

- New chart types and table styles.
- Terminal-specific polish for fonts and colour capabilities.
- Example decks for talks, teaching and lightning demos.
- Issue reports with a small `.md` deck, terminal name and `--dump` output.

MIT licensed. Be kind, be specific, have fun.
