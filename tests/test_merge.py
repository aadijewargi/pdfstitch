import random

import pytest
from pypdf import PdfReader

from pdfstitch import MergeError, Source, merge
from pdfstitch.ranges import select

from conftest import make_pdf, outline_tree, widths


def test_files_in_order(pdf, tmp_path):
    a = pdf("a.pdf", [101, 102])
    b = pdf("b.pdf", [201])
    c = pdf("c.pdf", [301, 302, 303])
    out = tmp_path / "out.pdf"
    merge([Source(a), Source(b), Source(c)], out)
    assert widths(out) == [101, 102, 201, 301, 302, 303]


def test_page_specs_reorder_and_repeat(pdf, tmp_path):
    a = pdf("a.pdf", [101, 102, 103, 104])
    b = pdf("b.pdf", [201, 202, 203])
    out = tmp_path / "out.pdf"
    merge([Source(a, "4,1,1"), Source(b, "end-1"), Source(a, "even")], out)
    assert widths(out) == [104, 101, 101, 203, 202, 201, 102, 104]


def test_same_file_twice(pdf, tmp_path):
    a = pdf("a.pdf", [101, 102])
    out = tmp_path / "out.pdf"
    merge([Source(a), Source(a)], out)
    assert widths(out) == [101, 102, 101, 102]


def test_single_file_extracts_pages(pdf, tmp_path):
    a = pdf("a.pdf", list(range(101, 111)))
    out = tmp_path / "out.pdf"
    merge([Source(a, "3-5")], out)
    assert widths(out) == [103, 104, 105]


def test_bookmark_per_file(pdf, tmp_path):
    a = pdf("intro.pdf", [101, 102])
    b = pdf("body.pdf", [201, 202, 203])
    out = tmp_path / "out.pdf"
    merge([Source(a), Source(b)], out, keep_outlines=False)
    assert outline_tree(out) == [("intro", 0, []), ("body", 2, [])]
    assert PdfReader(str(out)).page_mode == "/UseOutlines"


def test_no_bookmarks(pdf, tmp_path):
    a = pdf("a.pdf", [101], outline=[("Chapter", 0)])
    out = tmp_path / "out.pdf"
    merge([Source(a)], out, bookmarks=False, keep_outlines=False)
    assert outline_tree(out) == []


def test_existing_outlines_nested_and_remapped(pdf, tmp_path):
    a = pdf("a.pdf", [101, 102])
    b = pdf(
        "b.pdf",
        [201, 202, 203, 204],
        outline=[("Part 1", 0, [("1.1", 1)]), ("Part 2", 2, [("2.1", 3)])],
    )
    out = tmp_path / "out.pdf"
    merge([Source(a), Source(b)], out)
    assert outline_tree(out) == [
        ("a", 0, []),
        ("b", 2, [("Part 1", 2, [("1.1", 3, [])]), ("Part 2", 4, [("2.1", 5, [])])]),
    ]


def test_outlines_kept_at_top_level_without_file_bookmarks(pdf, tmp_path):
    a = pdf("a.pdf", [101, 102], outline=[("Start", 0), ("Later", 1)])
    out = tmp_path / "out.pdf"
    merge([Source(a)], out, bookmarks=False)
    assert outline_tree(out) == [("Start", 0, []), ("Later", 1, [])]


def test_outline_entries_for_dropped_pages_are_removed(pdf, tmp_path):
    # "Part 2" points at page 3, which isn't selected, but its child "2.1"
    # points at page 4, which is: the child moves up to the file's level.
    b = pdf(
        "b.pdf",
        [201, 202, 203, 204],
        outline=[("Part 1", 0), ("Part 2", 2, [("2.1", 3)])],
    )
    out = tmp_path / "out.pdf"
    merge([Source(b, "4,1")], out)
    assert outline_tree(out) == [("b", 0, [("Part 1", 1, []), ("2.1", 0, [])])]


def test_duplicated_page_bookmark_points_at_first_copy(pdf, tmp_path):
    a = pdf("a.pdf", [101, 102], outline=[("Two", 1)])
    out = tmp_path / "out.pdf"
    merge([Source(a, "1,2,2")], out, bookmarks=False)
    assert outline_tree(out) == [("Two", 1, [])]


def test_duplex_pads_odd_parts_but_not_the_last(pdf, tmp_path):
    a = pdf("a.pdf", [101, 102, 103])  # odd: padded
    b = pdf("b.pdf", [201, 202])  # even: not padded
    c = pdf("c.pdf", [301])  # odd but last: not padded
    out = tmp_path / "out.pdf"
    merge([Source(a), Source(b), Source(c)], out, duplex=True)
    assert widths(out) == [101, 102, 103, 103, 201, 202, 301]
    assert outline_tree(out) == [("a", 0, []), ("b", 4, []), ("c", 6, [])]
    blank = PdfReader(str(out)).pages[3]
    assert blank.extract_text() == ""


def test_title_metadata(pdf, tmp_path):
    a = pdf("a.pdf", [101])
    out = tmp_path / "out.pdf"
    merge([Source(a)], out, title="Quarterly report")
    assert PdfReader(str(out)).metadata.title == "Quarterly report"


def test_encrypted_input(pdf, tmp_path):
    a = pdf("locked.pdf", [101, 102], password="s3cret")
    out = tmp_path / "out.pdf"
    with pytest.raises(MergeError, match="password-protected"):
        merge([Source(a)], out)
    with pytest.raises(MergeError, match="wrong password"):
        merge([Source(a, password="nope")], out)
    merge([Source(a, password="s3cret")], out)
    assert widths(out) == [101, 102]
    assert not PdfReader(str(out)).is_encrypted


def test_refuses_existing_output_unless_forced(pdf, tmp_path):
    a = pdf("a.pdf", [101])
    out = tmp_path / "out.pdf"
    out.write_bytes(b"keep me")
    with pytest.raises(MergeError, match="already exists"):
        merge([Source(a)], out)
    assert out.read_bytes() == b"keep me"
    merge([Source(a)], out, overwrite=True)
    assert widths(out) == [101]


def test_never_overwrites_an_input(pdf):
    a = pdf("a.pdf", [101])
    with pytest.raises(MergeError, match="also an input"):
        merge([Source(a)], a, overwrite=True)
    assert widths(a) == [101]


def test_bad_input_writes_nothing(pdf, tmp_path):
    a = pdf("a.pdf", [101])
    b = pdf("b.pdf", [201, 202])
    out = tmp_path / "out.pdf"
    with pytest.raises(MergeError, match="page 9 does not exist"):
        merge([Source(a), Source(b, "9")], out)
    assert not out.exists()
    assert not list(tmp_path.glob(".pdfstitch-*"))  # no temp file left behind


@pytest.mark.parametrize(
    "setup,message",
    [
        (lambda d: d / "missing.pdf", "file not found"),
        (lambda d: (d / "junk.pdf").write_bytes(b"this is not a pdf") and d / "junk.pdf", "not a readable PDF"),
    ],
)
def test_unreadable_inputs(tmp_path, setup, message):
    with pytest.raises(MergeError, match=message):
        merge([Source(setup(tmp_path))], tmp_path / "out.pdf")


def test_no_inputs(tmp_path):
    with pytest.raises(MergeError, match="no input"):
        merge([], tmp_path / "out.pdf")


def test_missing_output_folder(pdf, tmp_path):
    a = pdf("a.pdf", [101])
    with pytest.raises(MergeError, match="does not exist"):
        merge([Source(a)], tmp_path / "nope" / "out.pdf")


@pytest.mark.parametrize("seed", range(8))
def test_random_merges_match_expected_pages(tmp_path, seed):
    """Brute-force check: random files + random specs, compared page by page."""
    rng = random.Random(seed)
    files = []
    for f in range(rng.randint(1, 4)):
        n = rng.randint(1, 6)
        files.append((make_pdf(tmp_path / f"f{f}.pdf", [100 * (f + 1) + p for p in range(1, n + 1)]), n))
    sources, expected = [], []
    for _ in range(rng.randint(1, 6)):
        path, n = rng.choice(files)
        spec = rng.choice([None, "odd", "end-1", f"{rng.randint(1, n)}-", f"{rng.randint(1, n)},{rng.randint(1, n)}"])
        sources.append(Source(path, spec))
        base = int(path.stem[1:]) + 1
        expected += [100 * base + i + 1 for i in select(spec, n)]
    out = tmp_path / "out.pdf"
    merge(sources, out)
    assert widths(out) == expected
