"""Natural ("human") sort order, so ``scan2.pdf`` comes before ``scan10.pdf``."""

from __future__ import annotations

import re
from pathlib import PurePath
from typing import List, Tuple, Union

__all__ = ["natural_key"]

_CHUNK = re.compile(r"(\d+)")


def natural_key(name: Union[str, PurePath]) -> Tuple[Tuple[int, int, str], ...]:
    """Sort key that compares digit runs as numbers and text case-insensitively.

    Each chunk becomes ``(kind, number, text)`` so that numbers and text never
    get compared with each other (which would raise ``TypeError``). Ties
    between ``"007"`` and ``"7"`` are broken by the original text, which
    keeps the order total and deterministic.
    """
    text = name.name if isinstance(name, PurePath) else str(name)
    key: List[Tuple[int, int, str]] = []
    for i, chunk in enumerate(_CHUNK.split(text)):
        if not chunk:
            continue
        if i % 2:  # odd positions of re.split with a capture group are the digits
            key.append((0, int(chunk), chunk))
        else:
            key.append((1, 0, chunk.casefold()))
    return tuple(key)
