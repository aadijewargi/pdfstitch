"""Turn command-line arguments into an ordered list of :class:`Source` objects.

Two things here exist mainly for Windows:

* ``cmd.exe`` and PowerShell do not expand wildcards for native programs, so
  ``pdfstitch *.pdf`` would otherwise receive the literal text ``*.pdf``.
  We expand globs ourselves, in natural order.
* Windows paths contain a colon (``C:\\scans\\a.pdf``), so the ``file:pages``
  suffix is only split off when what follows the *last* colon is a valid
  page spec and the file part is not a bare drive letter.
"""

from __future__ import annotations

import glob
import os
import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .merge import MergeError, Source
from .natsort import natural_key
from .ranges import is_spec

__all__ = ["split_spec", "expand", "sort_sources", "default_output"]

_GLOB_CHARS = re.compile(r"[*?\[]")
_DRIVE = re.compile(r"^[A-Za-z]$")


def split_spec(arg: str) -> Tuple[str, Optional[str]]:
    """Split ``"report.pdf:1-3"`` into ``("report.pdf", "1-3")``.

    A path that exists as written is never split, so a file literally named
    ``odd`` or ``notes:2`` still works.
    """
    if os.path.exists(arg) or ":" not in arg:
        return arg, None
    path, spec = arg.rsplit(":", 1)
    if not path or _DRIVE.match(path) or not is_spec(spec):
        return arg, None
    return path, spec


def _pdfs_in(folder: Path) -> List[Path]:
    found = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
    return sorted(found, key=natural_key)


def expand(args: Sequence[str], password: Optional[str] = None) -> List[Source]:
    """Expand files, folders and wildcards into sources, keeping argument order.

    Within one folder or one wildcard, files come out in natural order. A
    page spec written after a folder or wildcard applies to every file it
    expands to (``scans\\*.pdf:1`` takes page 1 of each scan).
    """
    sources: List[Source] = []
    for arg in args:
        target, spec = split_spec(arg)
        path = Path(target)
        if path.is_dir():
            matches = _pdfs_in(path)
            if not matches:
                raise MergeError(f"{target}: no PDF files in this folder")
        elif not path.exists() and _GLOB_CHARS.search(target):
            matches = sorted(
                (Path(p) for p in glob.glob(target) if Path(p).is_file()), key=natural_key
            )
            if not matches:
                raise MergeError(f"{target}: no files match")
        else:
            matches = [path]
        sources.extend(Source(m, spec, password) for m in matches)
    return sources


def sort_sources(sources: List[Source], how: str) -> List[Source]:
    """Reorder sources: ``"none"`` (as given), ``"name"`` (natural) or ``"mtime"`` (oldest first)."""
    if how == "none":
        return list(sources)
    if how == "name":
        return sorted(sources, key=lambda s: natural_key(s.path))
    if how == "mtime":
        return sorted(sources, key=lambda s: (s.path.stat().st_mtime, natural_key(s.path)))
    raise ValueError(f"unknown sort order {how!r}")


def default_output(sources: Sequence[Source], name: str = "merged.pdf") -> Path:
    """``merged.pdf`` next to the first input, or ``merged (2).pdf`` etc. if taken."""
    folder = sources[0].path.resolve().parent if sources else Path.cwd()
    stem, suffix = os.path.splitext(name)
    candidate = folder / name
    n = 2
    while candidate.exists():
        candidate = folder / f"{stem} ({n}){suffix}"
        n += 1
    return candidate
