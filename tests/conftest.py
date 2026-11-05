from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import requests
from review_contract import MARKET_TZ


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Unit tests must never contact live services")
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)


@pytest.fixture
def candidate_data():
    now = datetime.now(timezone.utc)
    data = now - timedelta(seconds=3)
    return dict(
        experiment_class="STRATEGY_1", data_kind="MARKET", candidate_id=str(uuid4()),
        session_date=now.astimezone(MARKET_TZ).date().isoformat(),
        symbol="LOCAL", direction="LONG", journal_trade_id="LOCAL-UNIT-ONLY",
        market_data_source="LOCAL_MARKET_FIXTURE", data_timestamp=data.isoformat(), data_quality_ok=True,
        consolidated_data=True, consolidated_data_required=True, market_regime="Mixed",
        market_context_ok=True, liquidity_ok=True, participation_ok=True, relative_strength_ok=True,
        price_extended_or_chasing=False, major_macro_event_imminent=False, target_validated=True,
        stop_would_widen=False, fomo_or_revenge_motive=False, catalyst_summary="Local fixture",
        catalyst_tier="A", catalyst_event_at=data.isoformat(), catalyst_material=True,
        materiality_rationale="Explicit local fixture", catalyst_verified=True, catalyst_cross_source_verified=True,
        catalyst_sources=[dict(source=s, source_type="fixture", headline_or_event="Local fixture", event_timestamp=data.isoformat()) for s in ("A","B")],
        entry_model="first_clean_pullback", trigger_definition="Predefined local level", trigger_price="100",
        trigger_confirmed=False, missed_trigger=False, after_first_minute=True,
        entry_price="100", stop_price="99", target_price="102", realized_daily_loss_dollars="0", executed_trades_today=0,
        current_review=dict(review_id=str(uuid4()), reviewer="unit test", evidence="Local-only complete assessment",
            data_timestamp=data.isoformat(), reviewed_at=(now-timedelta(seconds=2)).isoformat(),
            valid_until=(now+timedelta(seconds=60)).isoformat(),
            data_current=True, catalyst_current=True, qualification_current=True, risk_current=True, setup_current=True))
