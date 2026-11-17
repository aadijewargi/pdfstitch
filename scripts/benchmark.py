"""Time pdfstitch on many files and compare output size with the inputs.

Usage: python scripts/benchmark.py FOLDER_WITH_PDFS [COPIES]
Merges every PDF in the folder COPIES times over (default 50).
"""

import sys
import tempfile
import time
from pathlib import Path

from pdfstitch import Source, merge
from pdfstitch.natsort import natural_key

folder = Path(sys.argv[1])
copies = int(sys.argv[2]) if len(sys.argv) > 2 else 50
files = sorted(folder.glob("*.pdf"), key=natural_key)
sources = [Source(f) for _ in range(copies) for f in files]
in_bytes = sum(s.path.stat().st_size for s in sources)

with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "bench.pdf"
    t0 = time.perf_counter()
    planned = merge(sources, out)
    dt = time.perf_counter() - t0
    pages = sum(len(p.indices) for p in planned)
    print(f"{len(sources)} files, {pages} pages: {dt:.2f} s ({pages / dt:.0f} pages/s)")
    print(f"inputs {in_bytes / 1e6:.2f} MB -> output {out.stat().st_size / 1e6:.2f} MB")
