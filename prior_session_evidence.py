"""Opt-in, read-only dated daily-bar evidence; not a qualification decision.

No caller, route, scheduler or existing collector uses this adapter yet. Relative
snapshot fields are deliberately excluded. Raw closes require corporate-action
and instrument review; they are not asserted to be official auction closes.
"""
from datetime import date, datetime, time as day_time, timedelta, timezone
import time

import requests

from premarket_collection import BARS_URL, CALENDAR_URL, MARKET_TZ, SYMBOL, number, stamp

BATCH_SIZE = 200
MAX_SYMBOLS = 20000
MAX_PAGES = 120
BUDGET_SECONDS = 120


def collect_prior_session_evidence(headers, symbols, session_date, *, now=None, get=None, clock=None):
    """Bounded GETs only. A batch is usable only after complete pagination.

    The budget prevents starting more requests after its deadline. Socket
    timeouts are not a process-level watchdog. No retries or redirects.
    Caller supplies credentials in memory; no response/error text is returned.
    """
    now = now or datetime.now(timezone.utc)
    get, clock = get or requests.get, clock or time.monotonic
    result = {"outcome": "UNAVAILABLE", "items": {}, "feed": "sip", "adjustment": "raw",
              "source": BARS_URL, "timeframe": "1Day", "strategy_eligible": False,
              "review_required": True, "pages_received": 0, "completed_symbols": [],
              "unprocessed_symbols": [], "prior_session": None}
    try:
        if (type(session_date) is not date or now.tzinfo is None
                or now.utcoffset() is None or now.astimezone(MARKET_TZ).date() != session_date):
            raise ValueError()
        if (not isinstance(symbols, (list, tuple)) or not symbols or len(symbols) > MAX_SYMBOLS
                or any(not isinstance(s, str) or not SYMBOL.fullmatch(s) for s in symbols)
                or len(set(symbols)) != len(symbols)):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        result["outcome"] = "INVALID_REQUEST"
        return result
    result.update(session_date=session_date.isoformat(), requested_at=now.isoformat(),
                  unprocessed_symbols=list(symbols))
    result["items"] = {s: {"status": "UNAVAILABLE", "reason": "NOT_COLLECTED"} for s in symbols}
    deadline = clock() + BUDGET_SECONDS

    def read(url, params):
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError()
        response = get(url, headers=headers, params=params,
                       timeout=(min(3, remaining), min(10, remaining)), allow_redirects=False)
        if response.status_code != 200:
            raise ValueError()
        return response.json()

    try:
        calendar_start = session_date - timedelta(days=30)
        calendar = read(CALENDAR_URL, {"start": calendar_start.isoformat(), "end": session_date.isoformat()})
        if not isinstance(calendar, list) or not calendar:
            raise ValueError()
        dates = [date.fromisoformat(row["date"]) for row in calendar]
        if (len(set(dates)) != len(dates) or session_date not in dates
                or any(d < calendar_start or d > session_date for d in dates)):
            raise ValueError()
        previous = max(d for d in dates if d < session_date)
    except Exception:
        # Do not include provider exceptions, URLs with query secrets or payloads.
        result["outcome"] = "CALENDAR_UNAVAILABLE"
        return result
    start = datetime.combine(previous, day_time(), MARKET_TZ)
    end = datetime.combine(previous + timedelta(days=1), day_time(), MARKET_TZ) - timedelta(microseconds=1)
    result.update(prior_session=previous.isoformat(), calendar_source=CALENDAR_URL,
                  requested_start=start.isoformat(), requested_end=end.isoformat(), asof=session_date.isoformat())
    failed = False
    for offset in range(0, len(symbols), BATCH_SIZE):
        batch = list(symbols[offset:offset + BATCH_SIZE])
        pending, seen_tokens = {}, set()
        token = None
        try:
            while True:
                if result["pages_received"] >= MAX_PAGES:
                    raise TimeoutError()
                params = {"symbols": ",".join(batch), "timeframe": "1Day", "feed": "sip",
                          "adjustment": "raw", "asof": session_date.isoformat(), "sort": "asc",
                          "start": start.isoformat(), "end": end.isoformat(), "limit": 10000}
                if token:
                    params["page_token"] = token
                payload = read(BARS_URL, params)
                result["pages_received"] += 1
                if not isinstance(payload, dict) or not isinstance(payload.get("bars"), dict):
                    raise ValueError()
                for symbol, rows in payload["bars"].items():
                    if symbol not in batch or not isinstance(rows, list):
                        raise ValueError()
                    for bar in rows:
                        at = stamp(bar["t"])
                        # Daily bars are timestamped at the start of their NY day.
                        if at != start.astimezone(timezone.utc):
                            raise ValueError()
                        values = {k: number(bar[k], positive=True) for k in ("o", "h", "l", "c")}
                        volume = number(bar["v"])
                        if (int(volume) != volume or values["l"] > min(values["o"], values["c"])
                                or values["h"] < max(values["o"], values["c"]) or values["l"] > values["h"]):
                            raise ValueError()
                        projected = {**values, "v": volume, "t": at.isoformat()}
                        if symbol in pending and pending[symbol] != projected:
                            raise ValueError()
                        pending[symbol] = projected
                token = payload.get("next_page_token")
                if token is None or token == "":
                    break
                if not isinstance(token, str) or len(token) > 4096 or token in seen_tokens:
                    raise ValueError()
                seen_tokens.add(token)
            for symbol in batch:
                bar = pending.get(symbol)
                result["items"][symbol] = (
                    {"status": "RAW_DAILY_CLOSE_REVIEW_REQUIRED", "reason": None,
                     "close": bar["c"], "bar": bar, "session_date": previous.isoformat(),
                     "feed": "sip", "adjustment": "raw", "asof": session_date.isoformat(),
                     "source": BARS_URL, "strategy_eligible": False}
                    if bar else {"status": "UNAVAILABLE", "reason": "NO_BAR_FOR_PRIOR_SESSION"})
            result["completed_symbols"].extend(batch)
        except Exception:
            failed = True
            for symbol in batch:
                result["items"][symbol] = {"status": "UNAVAILABLE", "reason": "BATCH_INCOMPLETE_OR_INVALID"}
            # Fail closed on the first malformed/failed batch; no implicit retry.
            break
    completed = set(result["completed_symbols"])
    result["unprocessed_symbols"] = [s for s in symbols if s not in completed]
    result["outcome"] = "PARTIAL" if failed else "COLLECTION_COMPLETE_REVIEW_REQUIRED"
    return result
