import json
import random
from pathlib import Path

import pytest

from pdfstitch.ranges import PageSpecError, is_spec, parse, select

CASES = json.loads((Path(__file__).parent / "range_cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[f"{c['spec']!r}@{c['n']}" for c in CASES])
def test_shared_cases(case):
    if case.get("error"):
        with pytest.raises(PageSpecError):
            select(case["spec"], case["n"])
    else:
        assert [i + 1 for i in select(case["spec"], case["n"])] == case["pages"]


def test_none_means_all_pages():
    assert select(None, 3) == [0, 1, 2]


def test_syntax_checked_without_page_count():
    parse("1-3, end, odd")  # fine before the document is known
    with pytest.raises(PageSpecError):
        parse("1--3")


def test_error_mentions_page_count():
    with pytest.raises(PageSpecError, match="has 3 pages"):
        select("5", 3)
    with pytest.raises(PageSpecError, match="has 1 page\\)"):
        select("2", 1)


@pytest.mark.parametrize("text,ok", [("1-3", True), ("odd", True), ("", False), ("x", False), ("\\a.pdf", False)])
def test_is_spec(text, ok):
    assert is_spec(text) is ok


# --- randomized check against a deliberately naive reference -----------------


def naive(items, n):
    """Reference: enumerate every page and test membership the slow, obvious way."""
    out = []
    for kind, a, b in items:
        if kind == "parity":
            out += [p for p in range(1, n + 1) if p % 2 == a]
        else:
            lo, hi = sorted((a, b))
            span = [p for p in range(1, n + 1) if lo <= p <= hi]
            out += span if a <= b else span[::-1]
    return out


@pytest.mark.parametrize("seed", range(20))
def test_random_specs_match_reference(seed):
    rng = random.Random(seed)
    for _ in range(50):
        n = rng.randint(1, 30)
        items, text = [], []
        for _ in range(rng.randint(1, 5)):
            r = rng.random()
            if r < 0.15:
                odd = rng.random() < 0.5
                items.append(("parity", 1 if odd else 0, None))
                text.append("odd" if odd else "even")
            else:
                a, b = rng.randint(1, n), rng.randint(1, n)
                if r < 0.35:
                    items.append(("range", a, a))
                    text.append(str(a))
                elif r < 0.5:
                    items.append(("range", a, n))
                    text.append(f"{a}-")
                elif r < 0.6:
                    items.append(("range", n, b))
                    text.append(f"end-{b}")
                else:
                    items.append(("range", a, b))
                    text.append(f"{a}-{b}")
        spec = ",".join(text)
        assert [i + 1 for i in select(spec, n)] == naive(items, n), spec
