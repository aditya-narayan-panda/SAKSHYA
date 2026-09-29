"""SAKSHYA application package.

The FastAPI factory lives in the sibling ``backend/app.py`` module
(``create_app`` / ``app``) per the required ``backend/app.py`` + ``backend/main.py``
entry-point layout.  Because a package directory (``app/``) shadows a same-named
module (``app.py``) on ``sys.path``, this ``__init__`` loads that factory file
by explicit path and re-exports it — so ALL of these resolve to the same object:

* ``uvicorn app:app``        (package attribute, via this file)
* ``uvicorn main:app``       (``backend/main.py`` re-export)
* ``uvicorn app.main:app``   (legacy path, re-export)
* ``from app import create_app``
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_FACTORY_FILE = Path(__file__).resolve().parent.parent / "app.py"
_spec = importlib.util.spec_from_file_location("app._factory", _FACTORY_FILE)
assert _spec is not None and _spec.loader is not None, f"factory not found: {_FACTORY_FILE}"
_factory = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_factory)

create_app = _factory.create_app
app = _factory.app

__all__ = ["app", "create_app"]
