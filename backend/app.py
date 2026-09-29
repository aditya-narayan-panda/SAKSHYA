"""SAKSHYA backend application factory.

This module is the *only* place where the FastAPI application object is
assembled (middleware, routers, lifecycle hooks).  All business logic lives
under ``app/`` (routers, services, crypto, watermark, ledger); this file only
wires those pieces together so ``main.py`` (and uvicorn workers, and the test
suite) can all share one identical configuration.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi.exception_handlers import (
    http_exception_handler as _default_http_handler,
    request_validation_exception_handler as _default_validation_handler,
)
from fastapi.exceptions import HTTPException, RequestValidationError

from app.api import (
    auth,
    dashboard,
    decryption,
    documents,
    investigations,
    ledger_api,
    protection,
    recipients,
    reports,
    system,
)
from app.core.config import APP_ENV, CORS_ORIGINS, IS_PRODUCTION
from app.core.database import init_db
from app.core.key_store import unlock_master_key
from app.crypto.pqc_provider import enforce_pqc
from app.ledger.ledger_state import init_ledger

log = logging.getLogger("sakshya")


def create_app() -> FastAPI:
    app = FastAPI(
        title="SAKSHYA Backend",
        description=(
            "Cryptographic Document Attribution & Provenance System — "
            "fully local / air-gapped. Local auth + SQLite + ML-KEM-768 / "
            "ML-DSA-65 + forensic watermarking + local hash-chain ledger + "
            "local forensic reports. No cloud, no external API at runtime."
        ),
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # --- CORS: explicit local origins only (never "*" with credentials). ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # --- Routers ---
    app.include_router(system.router)
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(documents.router)
    app.include_router(recipients.router)
    app.include_router(protection.router)
    app.include_router(decryption.router)
    app.include_router(ledger_api.router)
    app.include_router(investigations.router)
    app.include_router(reports.router)

    # --- Lifecycle ---
    @app.on_event("startup")
    def on_startup() -> None:
        # Fail-closed boot sequence — any exception here aborts startup (uvicorn exits non-zero):
        #   1. PQC-only: refuse to run unless real ML-KEM-768 / ML-DSA-65 is active (MUST-6)
        #   2. master key: derive from the operator's password; never auto-generated (MUST-8)
        #   3. database + append-only guards (MUST-1)
        #   4. ledger: open the 3 persistent node stores + load their persistent signing keys (MUST-1/2)
        enforce_pqc()
        unlock_master_key()
        init_db()
        init_ledger()
        log.info("SAKSHYA backend started (env=%s, offline=True, PQC-only)", APP_ENV)

    @app.on_event("shutdown")
    def on_shutdown() -> None:
        log.info("SAKSHYA backend shutting down")

    # --- Errors: clean JSON, no tracebacks in demo/production mode. ---
    @app.exception_handler(HTTPException)
    async def _http_handler(request: Request, exc: HTTPException):
        return await _default_http_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        return await _default_validation_handler(request, exc)

    @app.exception_handler(Exception)
    async def _uncaught_handler(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        if IS_PRODUCTION:
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {type(exc).__name__}: {exc}"},
        )

    # --- Root health (bare /health for infra probes; canonical JSON shape). ---
    @app.get("/health", tags=["system"])
    def root_health():
        return {"status": "ok", "service": "SAKSHYA Backend", "offline": True}

    return app


app = create_app()
