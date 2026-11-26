"""Tests for release metadata and packaging consistency."""

from __future__ import annotations

import re
from pathlib import Path

import proscenium

ROOT = Path(__file__).parent


def test_version_parity() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match is not None
    # Compare the two sources of truth in the checkout.  An older copy that
    # happens to be installed elsewhere must not break a source-tree test.
    assert match.group(1) == proscenium.__version__ == "1.0.0"


def test_release_files_present() -> None:
    for name in ("LICENSE", "CHANGELOG.md", "README.md", "MANIFEST.in",
                 "demo.md", "formatting.md", "assets/demo.png",
                 "proscenium/py.typed"):
        assert (ROOT / name).is_file(), name


def test_packaging_metadata() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'license = "MIT"' in text
    for marker in ("setuptools>=77", "Programming Language :: Python :: 3.10",
                   "Programming Language :: Python :: 3.13", "[project.urls]",
                   "[project.optional-dependencies]",
                   '[tool.setuptools.package-data]',
                   '[tool.setuptools.data-files]'):
        assert marker in text, marker


if __name__ == "__main__":
    test_version_parity()
    test_release_files_present()
    test_packaging_metadata()
    print("release: ok")
