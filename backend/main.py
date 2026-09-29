"""Executable entry point for the SAKSHYA backend.

Run the demo server with::

    python main.py

from the ``backend/`` directory (Windows PowerShell or any shell), or with
uvicorn directly::

    uvicorn app:app --host 127.0.0.1 --port 8100
    uvicorn main:app --host 127.0.0.1 --port 8100

Both work: this module re-exports the factory-built ``app`` object.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app, create_app  # noqa: F401  (single shared instance)


def run() -> None:
    import uvicorn

    host = os.environ.get("SAKSHYA_HOST", "127.0.0.1")
    port = int(os.environ.get("SAKSHYA_PORT", "8100"))
    reload = os.environ.get("SAKSHYA_RELOAD", "0") == "1"
    uvicorn.run("main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run()
