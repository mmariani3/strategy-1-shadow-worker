"""Staging-only, authenticated evidence routes; no database or trading clients.

Fixed October 12 development acceptance only. The desktop controller narrows
this further to one bounded activation. No arbitrary provider URL or symbol list.
"""
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from premarket_collection import MARKET_TZ
from shadow_evidence_workflow import dated_prior_evidence, setup_preview

SERVICE = "srv-dal8abbl550s73cj3jm0"
SYMBOLS = ("SPY", "QQQ", "IWM")  # Infrastructure probes, not a candidate universe.
NOT_BEFORE = datetime(2026, 10, 12, 14, 45, tzinfo=timezone.utc)
EXPIRES = datetime(2026, 10, 13, 0, tzinfo=timezone.utc)
SOURCE_FILES = ("shadow_evidence_api.py", "shadow_evidence_routes.py", "shadow_evidence_workflow.py",
                "prior_session_evidence.py", "setup_evidence.py", "premarket_collection.py", "review_contract.py")
router = APIRouter()


def now():
    return datetime.now(timezone.utc)


def source_hash():
    h = hashlib.sha256()
    for name in SOURCE_FILES:
        h.update(name.encode())
        h.update((Path(__file__).parent/name).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def guard(authorization):
    token = os.getenv("DISCOVERY_SERVICE_TOKEN", "")
    if not token or not authorization or not hmac.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401, "AUTHENTICATION_REQUIRED")
    if (os.getenv("RENDER_SERVICE_ID") != SERVICE or os.getenv("RULESET_VERSION") != "v0.3"
            or not re.fullmatch(r"[0-9a-f]{40}", os.getenv("RENDER_GIT_COMMIT", ""))
            or not NOT_BEFORE <= now() < EXPIRES):
        raise HTTPException(503, "STAGING_IDENTITY_OR_WINDOW_UNVERIFIED")


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: dict
    observations: dict
    previous_packet: dict | None = None


@router.get("/evidence/prior-session")
def previous_session(authorization: str | None = Header(default=None)):
    guard(authorization)
    if not all(os.getenv(k) for k in ("ALPACA_API_KEY", "ALPACA_API_SECRET")):
        raise HTTPException(503, "MARKET_CREDENTIALS_UNAVAILABLE")
    checked = now()
    try:
        headers = {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"],
                   "APCA-API-SECRET-KEY": os.environ["ALPACA_API_SECRET"]}
        envelope = dated_prior_evidence(headers, list(SYMBOLS), checked.astimezone(MARKET_TZ).date(), now=checked)
        return {**envelope, "checked_at": checked.isoformat(), "commit": os.getenv("RENDER_GIT_COMMIT"),
                "source_hash": source_hash(), "scope": "THREE_SYMBOL_DATED_BAR_READ_ONLY_PROBE",
                "full_universe_coverage_verified": False, "premarket_collection_accepted": False}
    except Exception:
        raise HTTPException(503, "EVIDENCE_READ_UNVERIFIED") from None


@router.post("/evidence/setup-preview")
async def preview(request: Request, authorization: str | None = Header(default=None)):
    # Authenticate before parsing; never return validation errors echoing input.
    guard(authorization)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 256 * 1024:
            raise HTTPException(413, "EVIDENCE_PAYLOAD_TOO_LARGE")
    try:
        payload = PreviewRequest.model_validate(json.loads(data))
        result = setup_preview(payload.plan, payload.observations, as_of=now().isoformat(),
                               previous_packet=payload.previous_packet)
        return {**result, "commit": os.getenv("RENDER_GIT_COMMIT"), "source_hash": source_hash()}
    except Exception:
        raise HTTPException(422, "INVALID_EVIDENCE_REQUEST") from None
