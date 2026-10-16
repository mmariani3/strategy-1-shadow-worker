"""Bounded source collection; feed exhaustion never means strategy coverage."""
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
import re
import json
import time
from zoneinfo import ZoneInfo

import requests

NEWS_URL = "https://data.alpaca.markets/v1beta1/news"
ISM_URL = "https://www.ismworld.org/supply-management-news-and-reports/reports/rob-report-calendar/"
FOREX_FACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
NEWS_MAX_PAGES = 10
NEWS_BUDGET_SECONDS = 45


class NewsBudgetError(ValueError):
    pass


def collect_news(headers, hours, *, end=None, get=None, clock=None, include_content=False):
    get, clock = get or requests.get, clock or time.monotonic
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    params = {"start": start.isoformat(), "end": end.isoformat(),
              "sort": "desc", "limit": 50, "include_content": "true" if include_content else "false"}
    deadline = clock() + NEWS_BUDGET_SECONDS
    articles, ids, tokens = [], set(), set()
    pages, outcome = 0, "PAGE_LIMIT"
    # Token and provider diagnostics are deliberately absent from returned metadata.
    for _ in range(NEWS_MAX_PAGES):
        remaining = deadline - clock()
        if remaining <= 0:
            outcome = "TIME_BUDGET"
            break
        try:
            response = get(NEWS_URL, headers=headers, params=dict(params),
                           timeout=(min(3, remaining), min(10, remaining)),
                           **({"stream": True} if include_content else {}),
                           allow_redirects=False)
            if response.status_code != 200:
                if include_content:
                    response.close()
                outcome = "PROVIDER_UNAVAILABLE"
                break
            if include_content:
                # Bound content-bearing responses before decoding/parsing.
                try:
                    raw = bytearray()
                    for chunk in response.iter_content(16384):
                        if clock() >= deadline:
                            raise NewsBudgetError("TIME_BUDGET")
                        if len(raw)+len(chunk) > 2*1024*1024:
                            raise NewsBudgetError("BODY_LIMIT")
                        raw.extend(chunk)
                    body = json.loads(raw)
                finally:
                    response.close()
            else:
                body = response.json()
            batch = body["news"]
            token = body.get("next_page_token")
            if (not isinstance(batch, list) or len(batch) > 50
                    or (token is not None and not isinstance(token, str))):
                raise ValueError("Malformed news response")
            # Validate the page before adding any of it.
            for article in batch:
                if (not isinstance(article, dict) or type(article.get("id")) not in (int, str)
                        or not str(article["id"]) or not isinstance(article.get("symbols"), list)
                        or any(not isinstance(s, str) for s in article["symbols"])):
                    raise ValueError("Malformed article")
            pages += 1
            for article in batch:
                key = str(article["id"])
                if key not in ids:
                    ids.add(key)
                    articles.append(article)
            if not token:
                outcome = "FEED_EXHAUSTED"
                break
            if token in tokens:
                outcome = "REPEATED_PAGE_TOKEN"
                break
            tokens.add(token)
            params["page_token"] = token
        except NewsBudgetError as exc:
            outcome = str(exc)
            break
        except Exception:
            outcome = "PROVIDER_UNAVAILABLE"
            break
    return {"news": articles, "collection": {
        "source": "ALPACA_NEWS", "requested_start": start.isoformat(),
        "requested_end": end.isoformat(), "pages_received": pages,
        "unique_articles": len(articles), "outcome": outcome,
        "feed_exhausted": outcome == "FEED_EXHAUSTED",
        "full_discovery_coverage": False,
        "sort_basis": "PROVIDER_UPDATED_AT",
        "event_freshness_verified": False,
        "content_requested": include_content,
    }}


class CalendarTables(HTMLParser):
    """Only table cells, without scripts/navigation or inferred business dates."""
    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row, self.cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def parse_ism_calendar(document, session_date):
    parser = CalendarTables()
    parser.feed(document)
    # Require the explicit month AND year. An old page cannot silently pass.
    month_label = session_date.strftime("%B %Y")
    matches = []
    for table in parser.tables:
        header = next((r for r in table if len(r) == 3 and r[0] == "Month"), None)
        if not header or "Manufacturing" not in header[1] or "Services" not in header[2]:
            continue
        matches.extend(r for r in table if len(r) == 3 and r[0] == month_label)
    if len(matches) != 1:
        raise ValueError("ISM target month missing or ambiguous")
    events = []
    for name, cell in zip(("Manufacturing PMI", "Services PMI"), matches[0][1:]):
        match = re.fullmatch(r"(\d{1,2})\s*\*{0,3}", cell)
        if not match:
            raise ValueError("ISM date format changed")
        release_date = date(session_date.year, session_date.month, int(match[1]))
        if release_date == session_date:
            events.append({
                "source": "ISM", "source_type": "official_economic_release_calendar",
                "release_name": "ISM " + name, "release_date": release_date.isoformat(),
                "source_url": ISM_URL,
                # ISM labels its generic time EST; do not silently infer DST offsets.
                "release_time": None, "time_zone": None,
                "time_verification_status": "REVIEW_REQUIRED",
                "major_or_imminent": None,
            })
    return events


def collect_ism_calendar(session_date, *, get=None):
    response = (get or requests.get)(ISM_URL, timeout=(3, 10), allow_redirects=False)
    if response.status_code != 200 or len(response.content) > 2_000_000:
        raise ValueError("ISM calendar unavailable")
    return parse_ism_calendar(response.text, session_date)


def parse_weekly_calendar(body, session_date, *, checked_at):
    """A secondary weekly inventory, never a complete calendar or risk decision."""
    market_zone = ZoneInfo("America/New_York")
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise ValueError("Calendar check needs an aware timestamp")
    today = checked_at.astimezone(market_zone).date()
    week_start = today - timedelta(days=(today.weekday() + 1) % 7)
    week_end = week_start + timedelta(days=7)
    if not week_start <= session_date < week_end:
        raise ValueError("Weekly feed cannot verify another week's session")
    if not isinstance(body, list) or not body or len(body) > 1000:
        raise ValueError("Weekly feed missing or malformed")
    result, seen = [], set()
    for item in body:
        if not isinstance(item, dict):
            raise ValueError("Malformed calendar event")
        if any(not isinstance(item.get(k), str) or not item[k].strip()
               for k in ("title", "country", "date", "impact")):
            raise ValueError("Incomplete calendar event")
        scheduled = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
        if scheduled.tzinfo is None or scheduled.utcoffset() is None:
            raise ValueError("Ambiguous provider timezone")
        local_date = scheduled.astimezone(market_zone).date()
        if not week_start <= local_date < week_end:
            raise ValueError("Stale or mixed-week calendar")
        if local_date != session_date:
            continue
        key = (item["title"], item["country"], scheduled.isoformat())
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "source": "FOREX_FACTORY", "source_type": "secondary_economic_calendar",
            "source_url": FOREX_FACTORY_URL,
            "release_name": item["title"], "release_date": local_date.isoformat(),
            "provider_scheduled_at": scheduled.isoformat(),
            "provider_currency": item["country"], "provider_impact_label": item["impact"],
            "checked_at": checked_at.isoformat(), "major_or_imminent": None,
            "time_verification_status": "REVIEW_REQUIRED",
            "source_note": "Provider schedule may be approximate or revised. Impact label is not a Strategy #1 decision."
        })
    # Retain conflicting times rather than silently choosing one.
    counts = {}
    for event in result:
        key = (event["release_name"], event["provider_currency"])
        counts[key] = counts.get(key, 0) + 1
    for event in result:
        event["same_name_multiple_times"] = counts[(event["release_name"], event["provider_currency"])] > 1
    return result


def collect_weekly_calendar(session_date, *, get=None):
    checked_at = datetime.now(timezone.utc)
    with (get or requests.get)(FOREX_FACTORY_URL, timeout=(3, 10), allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise ValueError("Weekly calendar unavailable")
        raw = bytearray()
        for chunk in response.iter_content(65536):
            raw.extend(chunk)
            if len(raw) > 1_000_000:
                raise ValueError("Weekly calendar too large")
    import json
    return parse_weekly_calendar(json.loads(raw), session_date, checked_at=checked_at)
