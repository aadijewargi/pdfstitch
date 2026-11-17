import os
import subprocess
import sys

import pytest

from pdfstitch import sendto
from pdfstitch.cli import main
from pdfstitch.inputs import default_output, expand, sort_sources, split_spec
from pdfstitch.merge import MergeError, Source
from pdfstitch.natsort import natural_key

from conftest import outline_tree, widths


# --- natural sort -------------------------------------------------------------


def test_natural_order():
    names = ["scan10.pdf", "Scan2.pdf", "scan1.pdf", "notes.pdf", "scan2b.pdf", "10.pdf", "9.pdf"]
    assert sorted(names, key=natural_key) == [
        "9.pdf", "10.pdf", "notes.pdf", "scan1.pdf", "Scan2.pdf", "scan2b.pdf", "scan10.pdf"
    ]


def test_natural_key_never_compares_int_with_str():
    sorted(["a1", "1a", "", "a", "1", "-"], key=natural_key)  # must not raise


# --- argument parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    "arg,expected",
    [
        ("report.pdf", ("report.pdf", None)),
        ("report.pdf:1-3", ("report.pdf", "1-3")),
        ("report.pdf:odd", ("report.pdf", "odd")),
        ("C:\\docs\\report.pdf", ("C:\\docs\\report.pdf", None)),
        ("C:\\docs\\report.pdf:2-", ("C:\\docs\\report.pdf", "2-")),
        ("C:report.pdf", ("C:report.pdf", None)),
        ("D:5", ("D:5", None)),  # a drive-relative path, not page 5 of "D"
        ("weird:name.pdf", ("weird:name.pdf", None)),
        ("a.pdf:", ("a.pdf:", None)),
    ],
)
def test_split_spec(arg, expected):
    assert split_spec(arg) == expected


def test_existing_file_with_colon_is_not_split(tmp_path, monkeypatch):
    if sys.platform == "win32":
        pytest.skip("colons are not allowed in Windows file names")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "notes:2").write_bytes(b"")
    assert split_spec("notes:2") == ("notes:2", None)


def test_expand_folder_and_glob_in_natural_order(pdf, tmp_path, monkeypatch):
    for name in ["p10.pdf", "p2.pdf", "p1.pdf"]:
        pdf(name, [100])
    (tmp_path / "readme.txt").write_text("not a pdf")
    monkeypatch.chdir(tmp_path)

    by_folder = expand(["."])
    assert [s.path.name for s in by_folder] == ["p1.pdf", "p2.pdf", "p10.pdf"]

    by_glob = expand(["p*.pdf:1"])
    assert [(s.path.name, s.pages) for s in by_glob] == [("p1.pdf", "1"), ("p2.pdf", "1"), ("p10.pdf", "1")]


def test_expand_skips_earlier_output(pdf, tmp_path, monkeypatch):
    for name in ["a.pdf", "merged.pdf", "Merged (2).pdf", "merged-notes.pdf"]:
        pdf(name, [100])
    monkeypatch.chdir(tmp_path)
    skipped = []
    names = [s.path.name for s in expand(["."], skipped=skipped)]
    assert names == ["a.pdf", "merged-notes.pdf"]
    assert sorted(p.name for p in skipped) == ["Merged (2).pdf", "merged.pdf"]
    assert [s.path.name for s in expand(["merged.pdf"])] == ["merged.pdf"]  # explicit wins
    with pytest.raises(MergeError, match="only earlier"):
        expand(["merged.p*"])


def test_cli_singular_page(pdf, tmp_path, capsys):
    a = pdf("a.pdf", [101])
    assert main([str(a), "-n"]) == 0
    out = capsys.readouterr().out
    assert "1 page\n" in out and "= 1 page" in out


def test_expand_errors(tmp_path):
    with pytest.raises(MergeError, match="no files match"):
        expand([str(tmp_path / "*.pdf")])
    with pytest.raises(MergeError, match="no PDF files"):
        expand([str(tmp_path)])


def test_sort_sources(tmp_path):
    a, b = tmp_path / "b10.pdf", tmp_path / "b9.pdf"
    a.write_bytes(b"")
    b.write_bytes(b"")
    os.utime(a, (1_000, 1_000))
    os.utime(b, (2_000, 2_000))
    srcs = [Source(a), Source(b)]
    assert [s.path.name for s in sort_sources(srcs, "name")] == ["b9.pdf", "b10.pdf"]
    assert [s.path.name for s in sort_sources(srcs, "mtime")] == ["b10.pdf", "b9.pdf"]
    assert sort_sources(srcs, "none") == srcs


def test_default_output_does_not_clobber(tmp_path):
    src = [Source(tmp_path / "a.pdf")]
    assert default_output(src) == tmp_path / "merged.pdf"
    (tmp_path / "merged.pdf").write_bytes(b"")
    (tmp_path / "merged (2).pdf").write_bytes(b"")
    assert default_output(src) == tmp_path / "merged (3).pdf"


# --- end to end ---------------------------------------------------------------


def test_cli_merge(pdf, tmp_path, capsys):
    a = pdf("a.pdf", [101, 102])
    b = pdf("b.pdf", [201, 202, 203])
    out = tmp_path / "out.pdf"
    assert main([str(a), f"{b}:3,1", "-o", str(out), "--title", "T"]) == 0
    assert widths(out) == [101, 102, 203, 201]
    text = capsys.readouterr().out
    assert "2 pages\n" in text and "2 of 3 pages" in text and "= 4 pages" in text


def test_cli_default_output_next_to_first_input(pdf, tmp_path):
    a = pdf("a.pdf", [101])
    assert main([str(a), str(a), "-q"]) == 0
    assert widths(tmp_path / "merged.pdf") == [101, 101]
    assert main([str(a), "-q"]) == 0
    assert (tmp_path / "merged (2).pdf").exists()


def test_cli_dry_run_writes_nothing(pdf, tmp_path, capsys):
    a = pdf("a.pdf", [101, 102, 103])
    b = pdf("b.pdf", [201])
    assert main([str(a), str(b), "--duplex", "-n"]) == 0
    assert "+ blank" in capsys.readouterr().out
    assert not (tmp_path / "merged.pdf").exists()


def test_cli_flags(pdf, tmp_path):
    a = pdf("a.pdf", [101], outline=[("Inner", 0)])
    out = tmp_path / "out.pdf"
    assert main([str(a), "-o", str(out), "--no-bookmarks", "--no-outlines", "-q"]) == 0
    assert outline_tree(out) == []
    assert main([str(a), "-o", str(out), "-q"]) == 1  # exists, no --force
    assert main([str(a), "-o", str(out), "-f", "-q"]) == 0
    assert outline_tree(out) == [("a", 0, [("Inner", 0, [])])]


def test_cli_errors_are_friendly(tmp_path, capsys):
    assert main([str(tmp_path / "nope.pdf")]) == 1
    assert "pdfstitch: error:" in capsys.readouterr().err
    assert main([]) == 2


def test_python_dash_m(pdf, tmp_path):
    a = pdf("a.pdf", [101])
    out = tmp_path / "out.pdf"
    result = subprocess.run(
        [sys.executable, "-m", "pdfstitch", str(a), "-o", str(out)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert widths(out) == [101]


# --- Windows "Send to" entry -------------------------------------------------


def test_sendto_install_and_uninstall(tmp_path):
    folder = tmp_path / "Microsoft" / "Windows" / "SendTo"
    folder.mkdir(parents=True)
    target = sendto.install(appdata=str(tmp_path), python=r"C:\Python313\python.exe")
    assert target == folder / sendto.SCRIPT_NAME
    data = target.read_bytes()
    assert b'"C:\\Python313\\python.exe" -m pdfstitch --sort name --open %*\r\n' in data
    assert b"\n" not in data.replace(b"\r\n", b"")  # CRLF only
    assert sendto.uninstall(appdata=str(tmp_path)) == target
    assert sendto.uninstall(appdata=str(tmp_path)) is None


def test_sendto_needs_appdata(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    with pytest.raises(OSError, match="APPDATA"):
        sendto.sendto_dir()
