"""The merge engine: plan which pages to take from each file, then write them."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from . import ranges

__all__ = ["Source", "PlannedFile", "MergeError", "plan", "merge"]

PathLike = Union[str, "os.PathLike[str]"]


class MergeError(Exception):
    """A problem with an input or output file, worded for the person running the tool."""


@dataclass
class Source:
    """One input: a PDF and, optionally, which of its pages to take."""

    path: Path
    pages: Optional[str] = None  # page spec, see pdfstitch.ranges; None = all
    password: Optional[str] = None

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    @property
    def label(self) -> str:
        return self.path.stem


@dataclass
class PlannedFile:
    source: Source
    page_count: int  # pages in the input document
    indices: List[int]  # 0-based pages to take, in order
    reader: PdfReader = field(repr=False)


def _open(source: Source) -> PdfReader:
    path = source.path
    if not path.is_file():
        raise MergeError(f"{path}: file not found")
    try:
        reader = PdfReader(str(path))
    except (PdfReadError, OSError, ValueError) as exc:
        raise MergeError(f"{path}: not a readable PDF ({exc})") from exc
    if reader.is_encrypted:
        try:
            ok = reader.decrypt(source.password or "")
        except Exception as exc:  # missing crypto backend, unsupported algorithm, ...
            raise MergeError(f"{path}: cannot decrypt ({exc})") from exc
        if not ok:
            hint = "wrong password" if source.password else "it is password-protected; pass --password"
            raise MergeError(f"{path}: {hint}")
    return reader


def plan(sources: Sequence[Source]) -> List[PlannedFile]:
    """Open every input and resolve its page spec, without writing anything.

    All files are checked before any output is produced, so a typo in the
    last file's page range doesn't leave a half-written result behind.
    """
    if not sources:
        raise MergeError("no input files")
    planned = []
    for source in sources:
        reader = _open(source)
        n = len(reader.pages)
        try:
            indices = ranges.select(source.pages, n)
        except ranges.PageSpecError as exc:
            raise MergeError(f"{source.path}: {exc}") from exc
        planned.append(PlannedFile(source, n, indices, reader))
    return planned


def _page_index(reader: PdfReader, node: Any) -> Optional[int]:
    try:
        return reader.get_destination_page_number(node)
    except Exception:
        return None


def _copy_outline(
    reader: PdfReader,
    nodes: Iterable[Any],
    writer: PdfWriter,
    parent: Any,
    page_map: Dict[int, int],
) -> bool:
    """Copy a source outline, re-pointing entries at the merged document.

    pypdf represents an outline as a flat list where a nested list holds the
    children of the item just before it. Entries whose target page was not
    selected are dropped; their children (if any survive) move up a level.
    Returns True if anything was copied.
    """
    copied = False
    previous = None
    for node in nodes:
        if isinstance(node, list):
            target = previous if previous is not None else parent
            copied = _copy_outline(reader, node, writer, target, page_map) or copied
            continue
        src = _page_index(reader, node)
        if src is None or src not in page_map:
            previous = None
            continue
        title = str(node.get("/Title", "")) or "(untitled)"
        previous = writer.add_outline_item(title, page_map[src], parent=parent)
        copied = True
    return copied


def _unique_temp(dirpath: Path) -> Path:
    fd, name = tempfile.mkstemp(prefix=".pdfstitch-", suffix=".pdf", dir=str(dirpath))
    os.close(fd)
    return Path(name)


def merge(
    sources: Sequence[Source],
    output: PathLike,
    *,
    bookmarks: bool = True,
    keep_outlines: bool = True,
    duplex: bool = False,
    title: Optional[str] = None,
    overwrite: bool = False,
) -> List[PlannedFile]:
    """Merge ``sources`` into ``output`` and return the plan that was carried out.

    bookmarks
        Add one top-level bookmark per input file, named after the file.
    keep_outlines
        Carry over each input's own bookmarks (nested under the file's
        bookmark when ``bookmarks`` is on).
    duplex
        Insert a blank page after any part with an odd page count, so every
        file starts on a front side when printed double-sided.
    title
        Document title stored in the PDF metadata.
    overwrite
        Allow replacing an existing output file. Inputs are never overwritten.
    """
    out = Path(output)
    out_resolved = out.resolve()
    for s in sources:
        if s.path.exists() and s.path.resolve() == out_resolved:
            raise MergeError(f"output {out} is also an input; choose another name")
    if out.exists() and not overwrite:
        raise MergeError(f"{out} already exists (use --force to replace it)")
    if not out_resolved.parent.is_dir():
        raise MergeError(f"folder {out_resolved.parent} does not exist")

    planned = plan(sources)

    writer = PdfWriter()
    has_outline = False
    for i, item in enumerate(planned):
        start = len(writer.pages)
        writer.append(item.reader, pages=item.indices, import_outline=False)

        page_map: Dict[int, int] = {}
        for offset, src in enumerate(item.indices):
            page_map.setdefault(src, start + offset)

        parent = None
        if bookmarks and item.indices:
            parent = writer.add_outline_item(item.source.label, start)
            has_outline = True
        if keep_outlines and item.reader.outline:
            before = has_outline
            has_outline = _copy_outline(item.reader, item.reader.outline, writer, parent, page_map) or before

        is_last = i == len(planned) - 1
        if duplex and not is_last and (len(writer.pages) - start) % 2 == 1:
            box = writer.pages[-1].mediabox
            writer.add_blank_page(width=float(box.width), height=float(box.height))

    if title:
        writer.add_metadata({"/Title": title})
    writer.add_metadata({"/Producer": "pdfstitch (pypdf)"})
    if has_outline:
        writer.page_mode = "/UseOutlines"  # open with the bookmarks panel showing

    # Write to a temporary file in the same folder, then swap it into place,
    # so a crash or full disk never leaves a truncated PDF under the real name.
    tmp = _unique_temp(out_resolved.parent)
    try:
        with open(tmp, "wb") as fh:
            writer.write(fh)
        os.replace(tmp, out_resolved)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return planned
