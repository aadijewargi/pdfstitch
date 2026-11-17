"""Test helpers.

Test PDFs are built with pypdf alone (no extra dependencies). Every page is a
blank page with a distinct width, so a merged document can be checked page by
page just by reading the widths back: the page "label" *is* the width.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple, Union

import pytest
from pypdf import PdfReader, PdfWriter

# An outline spec is a list of (title, 0-based page) or (title, page, children).
Outline = Sequence[Union[Tuple[str, int], Tuple[str, int, "Outline"]]]


def make_pdf(
    path: Path,
    widths: Iterable[int],
    outline: Optional[Outline] = None,
    password: Optional[str] = None,
) -> Path:
    writer = PdfWriter()
    for w in widths:
        writer.add_blank_page(width=w, height=500)

    def add(items: Outline, parent=None) -> None:
        for entry in items:
            node = writer.add_outline_item(entry[0], entry[1], parent=parent)
            if len(entry) == 3:
                add(entry[2], node)  # type: ignore[arg-type]

    if outline:
        add(outline)
    if password is not None:
        writer.encrypt(password, algorithm="RC4-128")
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


def widths(path: Path) -> List[int]:
    return [round(float(p.mediabox.width)) for p in PdfReader(str(path)).pages]


def outline_tree(path: Path) -> list:
    """Outline as nested [(title, 0-based page, [children...]), ...]."""
    reader = PdfReader(str(path))

    def walk(nodes) -> list:
        out: list = []
        for node in nodes:
            if isinstance(node, list):
                title, page, _ = out[-1]
                out[-1] = (title, page, walk(node))
            else:
                out.append((str(node.title), reader.get_destination_page_number(node), []))
        return out

    return walk(reader.outline)


@pytest.fixture
def pdf(tmp_path):
    """Factory: ``pdf("a.pdf", [101, 102])`` writes a test PDF and returns its path."""

    def factory(name: str, ws: Iterable[int], **kw) -> Path:
        return make_pdf(tmp_path / name, ws, **kw)

    return factory
