"""Isolated entrypoint for one read-only staging evidence acceptance.

Deliberately imports no Discovery/Worker/Orchestrator/DB/execution application.
The same router is included by Discovery, but this app exposes only evidence.
"""
import os
from fastapi import FastAPI
from shadow_evidence_routes import router, source_hash, EXPIRES, SYMBOLS

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(router)


@app.get("/health")
def health():
    return {"ok": True, "application": "SHADOW_EVIDENCE_ACCEPTANCE", "version": "0.1.0",
            "commit": os.getenv("RENDER_GIT_COMMIT"), "source_hash": source_hash(),
            "mode": "SHADOW", "broker_execution_enabled": False, "journal_routes": False,
            "qualification_routes": False, "scan_routes": False, "database_access": False,
            "automatic_confirmation": False, "strategy_eligible": False,
            "expires_at": EXPIRES.isoformat(), "probe_symbols": list(SYMBOLS)}
