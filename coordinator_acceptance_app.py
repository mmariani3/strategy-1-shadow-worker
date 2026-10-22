"""Restricted entry point into discovery_coordinator.run_scan, NOT another scan.

The exported app is deliberately LOCKED. No date, credentials, controller,
watchdog or notification evidence is supplied by this local-only package.
Hosted admission must be independently implemented/reviewed before deployment.
"""
from fastapi import FastAPI, HTTPException, Security, Header
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

import discovery_coordinator as coordinator


def create_app(verified_controls_factory=None, *, preflight_service=None):
    if preflight_service is not None and verified_controls_factory is not None:
        raise ValueError('READ_ONLY_REHEARSAL_CANNOT_ENABLE_SCAN')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def restrict_routes(request, call_next):
        if (request.method, request.url.path) not in {
            ("GET", "/health"), ("GET", "/acceptance/preflight"), ("POST", "/scan/run-once")}:
            return JSONResponse({"detail": "ACCEPTANCE_ROUTE_DISABLED"}, status_code=403)
        return await call_next(request)

    @app.get("/health")
    def health():
        return {"mode": "SHADOW", "broker_execution_enabled": False,
                "qualification_routes": False, "journal_routes": False,
                "automatic_promotion": False, "strategy_evidence_eligible": False,
                "launch_verifier_installed": verified_controls_factory is not None,
                "readiness": "NOT_HOSTED_ACCEPTED"}

    @app.get("/acceptance/preflight")
    def preflight(authorization: str | None = Header(default=None)):
        if preflight_service is None:
            raise HTTPException(503, "READ_ONLY_PREFLIGHT_NOT_CONFIGURED")
        try:
            return preflight_service.check(authorization)
        except HTTPException as exc:
            from coordinator_runtime_preflight import PreflightFailure
            from coordinator_service_adapters import safe_steps
            if type(exc) is PreflightFailure:
                raise HTTPException(503, {"code":"READ_ONLY_PREFLIGHT_UNAVAILABLE",
                    "diagnostics":safe_steps(exc.diagnostics)}) from None
            raise HTTPException(exc.status_code,"READ_ONLY_PREFLIGHT_UNAVAILABLE") from None
        except Exception:
            raise HTTPException(503,"READ_ONLY_PREFLIGHT_UNAVAILABLE") from None

    @app.post("/scan/run-once")
    def scan(req: coordinator.ScanRequest,
             credentials: HTTPAuthorizationCredentials | None = Security(coordinator.bearer)):
        coordinator.require_auth(credentials)
        if verified_controls_factory is None:
            raise HTTPException(503, "HOSTED_ADMISSION_NOT_IMPLEMENTED")
        # A future factory MUST verify real dated isolation, exact code,
        # watchdog readiness and notification admission; this app can't do so.
        try:
            controls = verified_controls_factory()
            with controls.activate():
                return coordinator.run_scan(req, credentials)
        except HTTPException as exc:
            # Only a fixed code leaves this boundary. Provider and DB bodies,
            # validation diagnostics and credentials never become a response.
            raise HTTPException(exc.status_code, "ACCEPTANCE_FAILED_RECONCILE_READ_ONLY") from None
        except Exception:
            raise HTTPException(502, "ACCEPTANCE_AMBIGUOUS_RECONCILE_READ_ONLY") from None

    return app


app = create_app()


def create_rehearsal_app():
    """Explicit future deployment factory: read-only preflight, scan stays locked."""
    import os
    from pathlib import Path
    import requests
    from coordinator_runtime_preflight import from_deployed_environment
    probes=from_deployed_environment(os.environ,directory=Path(__file__).parent,session=requests.Session())
    return create_app(preflight_service=probes)
