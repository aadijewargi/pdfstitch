"""pdfstitch: combine PDF files, or pick pages out of them, into one PDF."""

__version__ = "0.1.0"

from .merge import MergeError, Source, merge, plan  # noqa: E402
from .ranges import PageSpecError, select  # noqa: E402

__all__ = ["Source", "merge", "plan", "select", "MergeError", "PageSpecError", "__version__"]
