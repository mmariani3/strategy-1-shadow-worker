"""Explicit, attributable review; no implicit freshness lifetime or trading threshold."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

MARKET_TZ = ZoneInfo("America/New_York")
CURRENT_FIELDS = (
    "market_regime", "market_context_ok", "data_quality_ok", "consolidated_data_required",
    "liquidity_ok", "participation_ok", "relative_strength_ok", "after_first_minute",
    "price_extended_or_chasing", "major_macro_event_imminent", "missed_trigger",
    "stop_would_widen", "fomo_or_revenge_motive", "target_validated",
    "realized_daily_loss_dollars", "executed_trades_today",
)


class CurrentReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    review_id: UUID
    reviewer: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    data_timestamp: datetime
    reviewed_at: datetime
    valid_until: datetime
    # Explicit judgments of the existing rules, never derived from price alone.
    data_current: Literal[True]
    catalyst_current: Literal[True]
    qualification_current: Literal[True]
    risk_current: Literal[True]
    setup_current: Literal[True]


def as_datetime(value):
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    return dt


def review_problem(candidate, now=None):
    """The reviewer supplies the validity interval; absent/expired review fails closed."""
    now = now or datetime.now(timezone.utc)
    get = candidate.get if isinstance(candidate, dict) else lambda k, default=None: getattr(candidate, k, default)
    try:
        raw = get("current_review")
        if not raw:
            return "CURRENT_REVIEW_REQUIRED"
        review = raw if isinstance(raw, CurrentReview) else CurrentReview.model_validate(raw)
        data, reviewed, until = map(as_datetime, (review.data_timestamp, review.reviewed_at, review.valid_until))
        session = get("session_date")
        if not session:
            return "SESSION_DATE_REQUIRED"
        session = session if isinstance(session, date) else date.fromisoformat(session)
        if any(dt.astimezone(MARKET_TZ).date() != session for dt in (now, data, reviewed, until)):
            return "REVIEW_SESSION_MISMATCH"
        if not data <= reviewed <= now < until:
            return "REVIEW_EXPIRED_OR_CONTRADICTORY"
        if as_datetime(get("data_timestamp")) != data:
            return "REVIEW_DATA_MISMATCH"
        if get("trigger_confirmed"):
            triggered = as_datetime(get("triggered_at") or get("trigger_confirmed_at"))
            if triggered != data or get("confirmation_review_id") != str(review.review_id):
                return "CURRENT_CONFIRMATION_REQUIRED"
        return None
    except (ValueError, TypeError):
        return "REVIEW_INVALID"


def readiness_problem(candidate):
    for name in CURRENT_FIELDS:
        if candidate.get(name) is None:
            return "STRUCTURED_INPUTS_UNRESOLVED"
    if candidate.get("consolidated_data_required") and candidate.get("consolidated_data") is None:
        return "STRUCTURED_INPUTS_UNRESOLVED"
    entry, stop, target = (candidate.get(k) for k in ("entry_price", "stop_price", "target_price"))
    if None not in (entry, stop, target):
        risk = abs(Decimal(str(entry)) - Decimal(str(stop)))
        reward = abs(Decimal(str(target)) - Decimal(str(entry)))
        if risk and Decimal("1.5") <= reward / risk < Decimal("2") and candidate.get("clean_structure") is None:
            return "CLEAN_STRUCTURE_UNRESOLVED"
    return review_problem(candidate)


def evidence_class_problem(experiment_class, data_kind, source, notes=""):
    if experiment_class == "STRATEGY_1" and data_kind != "MARKET":
        return "SYNTHETIC_EVIDENCE_NOT_STRATEGY"
    # Defense in depth for known historical test labels, not a classifier of real news.
    if experiment_class == "STRATEGY_1" and any(
        marker in (str(source) + " " + str(notes)).upper()
        for marker in ("SYNTHETIC", "INFRASTRUCTURE_TEST", "CONTROLLED_TEST", "INFRASTRUCTURE TEST")
    ):
        return "TEST_LABEL_REQUIRES_INFRASTRUCTURE_CLASS"
    return None
