"""Backwards-compatible import path for the FastAPI application.

The canonical factory now lives in the top-level ``app.py``
(``backend/app.py::create_app``).  This module keeps the historical
``uvicorn app.main:app`` / ``from app.main import app`` path working by
re-exporting the same factory-built object.
"""

from app import app, create_app  # noqa: F401  (re-export)

__all__ = ["app", "create_app"]
