"""Command-line interface: ``pdfstitch a.pdf b.pdf:2-5 scans\\ -o out.pdf``."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__, sendto
from .inputs import default_output, expand, sort_sources
from .merge import MergeError, PlannedFile, merge, plan

EPILOG = r"""
page ranges (append to a file with a colon):
  report.pdf:1-3,7     pages 1 to 3, then page 7
  report.pdf:4-        page 4 to the end
  report.pdf:end-1     every page, last to first
  scan.pdf:odd         odd pages (also: even)

examples:
  pdfstitch cover.pdf report.pdf appendix.pdf -o final.pdf
  pdfstitch scans\ -o scans.pdf                  every PDF in a folder, in name order
  pdfstitch "chapter*.pdf" -o book.pdf --duplex   wildcards work in cmd and PowerShell too
  pdfstitch big.pdf:1-10 -o first-ten.pdf         one file + a range = extract pages
  pdfstitch --install-sendto                      add "Send to > PDF Stitch" in Explorer
"""


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdfstitch",
        description="Combine PDF files, or pick pages out of them, into one PDF.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("inputs", nargs="*", metavar="FILE[:PAGES]",
                   help="PDF files, folders or wildcards, in the order to combine them")
    p.add_argument("-o", "--output", type=Path,
                   help="output file (default: merged.pdf next to the first input)")
    p.add_argument("-f", "--force", action="store_true", help="replace the output file if it exists")
    p.add_argument("--sort", choices=["none", "name", "mtime"], default="none",
                   help="reorder inputs: as given (default), by name (natural order), or oldest first")
    p.add_argument("--no-bookmarks", dest="bookmarks", action="store_false",
                   help="don't add a bookmark for each input file")
    p.add_argument("--no-outlines", dest="outlines", action="store_false",
                   help="drop the bookmarks that the input files already have")
    p.add_argument("--duplex", action="store_true",
                   help="add blank pages so each file starts on a new sheet when printed two-sided")
    p.add_argument("--title", help="title to store in the PDF metadata")
    p.add_argument("--password", help="password for encrypted inputs")
    p.add_argument("-n", "--dry-run", action="store_true", help="show what would be merged, write nothing")
    p.add_argument("--open", action="store_true", help="open the result when done")
    p.add_argument("-q", "--quiet", action="store_true", help="print nothing but errors")
    p.add_argument("--install-sendto", action="store_true",
                   help='Windows: add "PDF Stitch (merge)" to the Explorer Send To menu')
    p.add_argument("--uninstall-sendto", action="store_true", help="Windows: remove that menu entry")
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _summary(planned: Sequence[PlannedFile], duplex: bool) -> str:
    width = max(len(str(p.source.path)) for p in planned)
    lines = []
    total = 0
    for i, item in enumerate(planned):
        taken = len(item.indices)
        pad = duplex and i < len(planned) - 1 and (total + taken) % 2 == 1
        total += taken + (1 if pad else 0)
        what = f"all {item.page_count}" if item.source.pages is None else f"{taken} of {item.page_count}"
        extra = "  + blank" if pad else ""
        lines.append(f"  {str(item.source.path):<{width}}  {what} pages{extra}")
    lines.append(f"  {'':<{width}}  = {total} pages")
    return "\n".join(lines)


def _open_file(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    say = (lambda *a: None) if args.quiet else print

    try:
        if args.install_sendto:
            say(f"Added Send To entry: {sendto.install()}")
            return 0
        if args.uninstall_sendto:
            removed = sendto.uninstall()
            say(f"Removed {removed}" if removed else "No Send To entry was installed.")
            return 0
        if not args.inputs:
            _parser().print_usage(sys.stderr)
            print("pdfstitch: error: give at least one PDF file", file=sys.stderr)
            return 2

        sources = sort_sources(expand(args.inputs, args.password), args.sort)

        if args.dry_run:
            planned = plan(sources)
            out = args.output or default_output(sources)
            say(f"Would write {out}:\n{_summary(planned, args.duplex)}")
            return 0

        out = args.output or default_output(sources)
        planned = merge(
            sources,
            out,
            bookmarks=args.bookmarks,
            keep_outlines=args.outlines,
            duplex=args.duplex,
            title=args.title,
            overwrite=args.force,
        )
        say(f"Wrote {out}\n{_summary(planned, args.duplex)}")
        if args.open:
            _open_file(Path(out))
        return 0
    except (MergeError, OSError) as exc:
        print(f"pdfstitch: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
