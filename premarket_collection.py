"""Read-only, bounded SIP evidence. No ranking, qualification or execution.

Limits are operational caps, never strategy thresholds. A truncated symbol-sorted
feed cannot support a market-wide activity ranking. Even exhaustive responses
leave instrument eligibility, unusual volume and catalyst review unresolved.
"""
from datetime import datetime, timedelta, timezone
import math
import re
import time
from zoneinfo import ZoneInfo

import requests

ASSETS_URL = "https://paper-api.alpaca.markets/v2/assets"
CALENDAR_URL = "https://paper-api.alpaca.markets/v2/calendar"
BARS_URL = "https://data.alpaca.markets/v2/stocks/bars"
SNAPSHOTS_URL = "https://data.alpaca.markets/v2/stocks/snapshots"
MARKET_TZ = ZoneInfo("America/New_York")
BATCH_SIZE = 100
MAX_ASSETS = 20000
MAX_PAGES = 120
BUDGET_SECONDS = 120
SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9./-]{0,19}\Z")
EXCHANGES = {"AMEX", "ARCA", "BATS", "NYSE", "NASDAQ", "NYSEARCA", "OTC"}


def stamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must be aware")
    return parsed.astimezone(timezone.utc)


def number(value, *, positive=False):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("Invalid number")
    if value < 0 or (positive and value == 0):
        raise ValueError("Invalid number")
    return value


def snapshot_fields(snapshot, start, checked_at, previous_date):
    """Project only numeric/timestamp fields; never retain provider diagnostics."""
    result = {"quote_status": "UNAVAILABLE", "previous_close_status": "UNAVAILABLE"}
    try:
        q = snapshot["latestQuote"]
        qt = stamp(q["t"])
        bid, ask = number(q["bp"], positive=True), number(q["ap"], positive=True)
        if not start <= qt <= checked_at or ask < bid:
            raise ValueError("Invalid quote")
        result.update(quote_status="SESSION_QUOTE_REVIEW_REQUIRED", quote_at=qt.isoformat(),
                      bid=bid, ask=ask, spread=ask-bid,
                      quote_age_seconds=(checked_at-qt).total_seconds())
    except (ValueError, TypeError, KeyError, AttributeError):
        pass
    try:
        bar = snapshot["prevDailyBar"]
        bt = stamp(bar["t"])
        if bt.astimezone(MARKET_TZ).date() != previous_date:
            raise ValueError("Wrong prior session")
        close = number(bar["c"], positive=True)
        result.update(previous_close_status="UNADJUSTED_REVIEW_REQUIRED",
                      previous_close=close, previous_close_at=bt.isoformat())
    except (ValueError, TypeError, KeyError, AttributeError):
        pass
    return result


def collect_premarket(headers, session_date, *, phase="PREMARKET", now=None, get=None, clock=None):
    """Collect completed 1-minute SIP bars from 04:00 ET to a fixed cutoff.

    Only today's pre-open session is supported. No retrospective replacement,
    delayed feed fallback, retries, redirects, or raw error text. Requests have
    connect/read timeouts; the budget prevents new requests after its deadline,
    rather than promising a hard process-level wall-clock kill.
    """
    now, get, clock = now or datetime.now(timezone.utc), get or requests.get, clock or time.monotonic
    items = {}
    meta = {"source": "ALPACA_SIP_1MIN", "feed": "sip", "adjustment": "raw",
            "full_discovery_coverage": False, "universe_source": "ALPACA_ACTIVE_US_EQUITY",
            "instrument_eligibility": "REVIEW_REQUIRED", "bars_pages_received": 0,
            "universe_symbols": [], "completed_symbols": [], "no_bars_symbols": [],
            "unprocessed_symbols": [], "excluded_otc_symbols": [],
            "outcome": "UNAVAILABLE", "collection_started_at": now.isoformat()}
    result = {"items": items, "collection": meta}
    if now.tzinfo is None or now.utcoffset() is None:
        meta["outcome"] = "INVALID_CHECK_TIME"
        return result
    local = now.astimezone(MARKET_TZ)
    start = local.replace(hour=4, minute=0, second=0, microsecond=0)
    cutoff = local.replace(second=0, microsecond=0)
    if (phase != "PREMARKET" or local.date() != session_date or cutoff <= start
            or (local.hour, local.minute) >= (9, 30)):
        meta["outcome"] = "OUTSIDE_CURRENT_PREMARKET"
        return result
    meta.update(requested_start=start.isoformat(), completed_minute_cutoff=cutoff.isoformat(),
                budget_seconds=BUDGET_SECONDS, page_limit=MAX_PAGES)
    started = clock()
    deadline = started + BUDGET_SECONDS

    def read(url, params):
        remaining = deadline-clock()
        if remaining <= 0:
            raise TimeoutError()
        response = get(url, headers=headers, params=dict(params), allow_redirects=False,
                       timeout=(min(3, remaining), min(10, remaining)))
        if response.status_code != 200:
            raise ValueError("Provider unavailable")
        return response.json()

    try:
        calendar = read(CALENDAR_URL, {"start": (session_date-timedelta(days=30)).isoformat(),
                                       "end": session_date.isoformat()})
        if not isinstance(calendar, list) or len(calendar) > 31:
            raise ValueError("Invalid calendar")
        dates = [datetime.strptime(row["date"], "%Y-%m-%d").date() for row in calendar]
        if len(set(dates)) != len(dates) or any(d > session_date for d in dates):
            raise ValueError("Invalid calendar dates")
        today = [row for row in calendar if row["date"] == session_date.isoformat()]
        if len(today) != 1:
            meta["outcome"] = "NOT_A_TRADING_SESSION"
            return result
        market_open = datetime.combine(session_date, datetime.strptime(today[0]["open"], "%H:%M").time(), MARKET_TZ)
        if now >= market_open:
            meta["outcome"] = "OUTSIDE_CURRENT_PREMARKET"
            return result
        previous_date = max(d for d in dates if d < session_date)
        meta["previous_session_date"] = previous_date.isoformat()
        assets = read(ASSETS_URL, {"status": "active", "asset_class": "us_equity"})
        if not isinstance(assets, list) or not assets or len(assets) > MAX_ASSETS:
            raise ValueError("Invalid or oversized universe")
        universe = {}
        for asset in assets:
            symbol = asset["symbol"]
            if (not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol)
                    or symbol in universe or asset.get("class") != "us_equity"
                    or asset.get("status") != "active" or asset.get("exchange") not in EXCHANGES):
                raise ValueError("Invalid universe entry")
            universe[symbol] = asset["exchange"]
        meta["excluded_otc_symbols"] = sorted(s for s, ex in universe.items() if ex == "OTC")
        symbols = sorted(s for s, ex in universe.items() if ex != "OTC")
        meta["universe_symbols"] = symbols
        meta["unprocessed_symbols"] = list(symbols)
    except TimeoutError:
        meta["outcome"] = "TIME_BUDGET"
        return result
    except Exception:
        meta["outcome"] = "UNIVERSE_OR_CALENDAR_UNAVAILABLE"
        return result

    outcome = "FEED_EXHAUSTED"
    for offset in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[offset:offset+BATCH_SIZE]
        aggregates, seen, tokens = {}, {}, set()
        params = {"symbols": ",".join(batch), "timeframe": "1Min", "feed": "sip",
                  "adjustment": "raw", "sort": "asc", "limit": 10000,
                  "asof": session_date.isoformat(), "start": start.isoformat(),
                  # Provider end is inclusive. Exclude the still-forming minute.
                  "end": (cutoff-timedelta(microseconds=1)).isoformat()}
        complete = False
        try:
            while meta["bars_pages_received"] < MAX_PAGES:
                body = read(BARS_URL, params)
                rows, token = body["bars"], body.get("next_page_token")
                if (not isinstance(rows, dict) or set(rows)-set(batch)
                        or any(not isinstance(v, list) for v in rows.values())
                        or sum(len(v) for v in rows.values()) > 10000
                        or (token is not None and (not isinstance(token, str) or len(token) > 8192))):
                    raise ValueError("Malformed bars")
                validated = []
                for symbol, bars in rows.items():
                    for bar in bars:
                        t = stamp(bar["t"])
                        if not start <= t < cutoff or t.second or t.microsecond:
                            raise ValueError("Out of window bar")
                        o,h,l,c = (number(bar[k], positive=True) for k in ("o","h","l","c"))
                        v = number(bar["v"])
                        if not l <= min(o,c) <= max(o,c) <= h or int(v) != v:
                            raise ValueError("Invalid OHLCV")
                        validated.append((symbol,t,(o,h,l,c,v)))
                for symbol,t,values in validated:
                    key = (symbol,t)
                    if key in seen:
                        if seen[key] != values:
                            raise ValueError("Conflicting duplicate bar")
                        continue
                    seen[key] = values
                    aggregates.setdefault(symbol, {})[t] = values
                meta["bars_pages_received"] += 1
                if not token:
                    complete = True
                    break
                if token in tokens:
                    outcome = "REPEATED_PAGE_TOKEN"
                    break
                tokens.add(token)
                params["page_token"] = token
            if not complete and outcome == "FEED_EXHAUSTED":
                outcome = "PAGE_LIMIT"
        except TimeoutError:
            outcome = "TIME_BUDGET"
        except Exception:
            outcome = "BAR_PROVIDER_UNAVAILABLE"

        # Partial sums are labelled; they are never presented as complete volume.
        for symbol, bars in aggregates.items():
            first, last = min(bars), max(bars)
            volume = sum(values[4] for values in bars.values())
            items[symbol] = {"source": "ALPACA_SIP_1MIN", "feed": "sip",
                "premarket_usable": False, "verification_status": "REVIEW_REQUIRED",
                "instrument_eligibility": "REVIEW_REQUIRED", "exchange": universe[symbol],
                "requested_start": start.isoformat(), "completed_minute_cutoff": cutoff.isoformat(),
                "collection_started_at": now.isoformat(), "first_bar_at": first.isoformat(),
                "last_bar_at": last.isoformat(), "last_bar_close": bars[last][3],
                "last_bar_age_seconds": (now-last).total_seconds(),
                "observed_volume": volume, "premarket_volume": volume if complete else None,
                "bar_collection_status": "FEED_EXHAUSTED" if complete else outcome,
                "bars_received": len(bars), "high": max(v[1] for v in bars.values()),
                "low": min(v[2] for v in bars.values()), "rvol": None, "average_daily_volume": None,
                "unusual_volume": None, "liquidity_ok": None, "gap_percent_unadjusted": None,
                "quote_status": "UNAVAILABLE", "previous_close_status": "UNAVAILABLE"}
        if complete:
            meta["completed_symbols"].extend(batch)
            meta["no_bars_symbols"].extend(s for s in batch if s not in aggregates)
            meta["unprocessed_symbols"] = symbols[offset+len(batch):]
        if aggregates:
            try:
                snapshots = read(SNAPSHOTS_URL, {"symbols": ",".join(sorted(aggregates)), "feed": "sip"})
                if not isinstance(snapshots, dict) or set(snapshots)-set(aggregates):
                    raise ValueError("Malformed snapshots")
                for symbol in aggregates:
                    checked_at = now + timedelta(seconds=max(0, clock()-started))
                    quote_cutoff = min(checked_at, market_open-timedelta(microseconds=1))
                    fields = snapshot_fields(snapshots.get(symbol, {}), start, quote_cutoff, previous_date)
                    fields["snapshot_checked_at"] = checked_at.isoformat()
                    items[symbol].update(fields)
                    if "previous_close" in fields:
                        items[symbol]["gap_percent_unadjusted"] = (items[symbol]["last_bar_close"]/fields["previous_close"]-1)*100
            except Exception:
                # Bar evidence remains valid when the optional snapshot fails.
                pass
        if not complete:
            break
    meta.update(outcome=outcome, symbols_with_bars=len(items),
                snapshot_symbols_with_quote=sum("quote_at" in row for row in items.values()),
                snapshot_symbols_with_previous_close=sum("previous_close" in row for row in items.values()))
    return result
