"""Page-range parsing.

A page spec is a comma-separated list of items, resolved against a document
with ``n`` pages. Pages are numbered from 1, as in every PDF viewer.

=============  ==============================================
Item           Meaning
=============  ==============================================
``5``          page 5
``3-7``        pages 3, 4, 5, 6, 7
``7-3``        pages 7, 6, 5, 4, 3 (descending ranges reverse)
``4-``         page 4 to the last page
``end``        the last page (usable anywhere a number is)
``odd``        pages 1, 3, 5, ...
``even``       pages 2, 4, 6, ...
=============  ==============================================

An empty spec selects every page. Items are kept in the order written and
repeats are allowed, so ``1,1,2`` duplicates page 1. Whitespace and letter
case are ignored.

Parsing happens in two steps so that a spec can be checked for syntax before
the document is opened: :func:`parse` turns text into a tuple of items, and
:func:`resolve` turns those items into 0-based page indices for a document
of a given length.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

__all__ = ["PageSpecError", "parse", "resolve", "select", "is_spec"]

END = "end"

Bound = Union[int, str]  # a 1-based page number, or END


class PageSpecError(ValueError):
    """Raised for a malformed page spec or a page outside the document."""


@dataclass(frozen=True)
class _Range:
    start: Bound
    stop: Bound


@dataclass(frozen=True)
class _Parity:
    odd: bool


_Item = Union[_Range, _Parity]

_BOUND = r"(?:\d+|end)"
_ITEM_RE = re.compile(rf"^(?P<a>{_BOUND})(?:(?P<dash>-)(?P<b>{_BOUND})?)?$")


def _bound(token: str, item: str) -> Bound:
    if token == END:
        return END
    value = int(token)
    if value < 1:
        raise PageSpecError(f"page numbers start at 1, got {item!r}")
    return value


def parse(spec: Optional[str]) -> Tuple[_Item, ...]:
    """Parse ``spec`` into items without knowing the page count.

    Raises :class:`PageSpecError` on bad syntax. ``None`` or an empty string
    means "all pages" and parses to ``(_Range(1, END),)``.
    """
    if spec is None or not spec.strip():
        return (_Range(1, END),)
    items: List[_Item] = []
    for raw in spec.split(","):
        item = re.sub(r"\s+", "", raw).lower()
        if not item:
            raise PageSpecError(f"empty item in page spec {spec!r}")
        if item in ("odd", "even"):
            items.append(_Parity(odd=item == "odd"))
            continue
        m = _ITEM_RE.match(item)
        if not m:
            raise PageSpecError(f"cannot read {raw.strip()!r} in page spec {spec!r}")
        start = _bound(m["a"], item)
        if m["dash"] is None:
            stop: Bound = start
        elif m["b"] is None:
            stop = END
        else:
            stop = _bound(m["b"], item)
        items.append(_Range(start, stop))
    return tuple(items)


def resolve(items: Sequence[_Item], n_pages: int) -> List[int]:
    """Turn parsed items into 0-based page indices for an ``n_pages`` document."""
    if n_pages < 1:
        raise PageSpecError("document has no pages")

    def number(b: Bound) -> int:
        value = n_pages if b == END else int(b)
        if value > n_pages:
            noun = "page" if n_pages == 1 else "pages"
            raise PageSpecError(f"page {value} does not exist (document has {n_pages} {noun})")
        return value

    out: List[int] = []
    for item in items:
        if isinstance(item, _Parity):
            first = 1 if item.odd else 2
            out.extend(p - 1 for p in range(first, n_pages + 1, 2))
            continue
        a, b = number(item.start), number(item.stop)
        step = 1 if b >= a else -1
        out.extend(p - 1 for p in range(a, b + step, step))
    return out


def select(spec: Optional[str], n_pages: int) -> List[int]:
    """Parse and resolve in one step: ``select("2-3", 5) == [1, 2]``."""
    return resolve(parse(spec), n_pages)


def is_spec(text: str) -> bool:
    """True if ``text`` is a syntactically valid, non-empty page spec."""
    if not text.strip():
        return False
    try:
        parse(text)
    except PageSpecError:
        return False
    return True
