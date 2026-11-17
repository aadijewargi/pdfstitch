"""Windows Explorer integration: a "Send to > PDF Stitch" menu entry.

Explorer's Send To menu runs any ``.bat`` file placed in the user's SendTo
folder, passing the selected files as arguments. The batch file calls this
same Python interpreter, so it keeps working inside a virtual environment or
a pipx install. Explorer passes the selection in an unpredictable order, so
the entry sorts by name.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

__all__ = ["sendto_dir", "script_text", "install", "uninstall", "SCRIPT_NAME"]

SCRIPT_NAME = "PDF Stitch (merge).bat"


def sendto_dir(appdata: Optional[str] = None) -> Path:
    appdata = appdata or os.environ.get("APPDATA")
    if not appdata:
        raise OSError("APPDATA is not set; the Send To menu only exists on Windows")
    return Path(appdata) / "Microsoft" / "Windows" / "SendTo"


def script_text(python: Optional[str] = None) -> str:
    python = python or sys.executable
    # %* forwards every selected file. If the merge fails, pause so the
    # console window stays open long enough to read the message.
    return (
        "@echo off\r\n"
        "rem Created by pdfstitch --install-sendto. Delete this file to remove the menu entry.\r\n"
        f'"{python}" -m pdfstitch --sort name --open %*\r\n'
        "if errorlevel 1 pause\r\n"
    )


def install(appdata: Optional[str] = None, python: Optional[str] = None) -> Path:
    folder = sendto_dir(appdata)
    if not folder.is_dir():
        raise OSError(f"SendTo folder not found: {folder}")
    target = folder / SCRIPT_NAME
    # newline="" keeps the CRLF line endings that cmd.exe expects.
    with open(target, "w", encoding="utf-8", newline="") as fh:
        fh.write(script_text(python))
    return target


def uninstall(appdata: Optional[str] = None) -> Optional[Path]:
    target = sendto_dir(appdata) / SCRIPT_NAME
    if target.exists():
        target.unlink()
        return target
    return None
