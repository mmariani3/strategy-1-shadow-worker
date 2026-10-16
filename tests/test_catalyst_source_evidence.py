"""Invented public-document fixtures only; all HTTP is injected/offline."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import catalyst_source_evidence as s
import discovery_coordinator as d
from coordinator_acceptance_controls import Controls, DATABASE, SERVICE
from coordinator_acceptance_verify import verify, verify_packet
from discovery_collection import collect_news
from setup_evidence import digest
from test_coordinator_acceptance import wired, run, NOW, REQUEST

BASE = "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/"
META = {"issuer_cik": "0000000001", "accession": "0000000001-26-000001", "url": BASE+"filing.htm",
        "form": "8-K", "filing_date": "2026-10-12"}


class Document:
    def __init__(self, body=b"<p>Invented issuer statement.</p>", status=200, mime="text/html"):
        self.body, self.status_code, self.closed = body, status, False
        self.headers = {"Content-Type": mime}

    def iter_content(self, size):
        for i in range(0, len(self.body), size):
            yield self.body[i:i+size]

    def close(self):
        self.closed = True


def collector(response=None):
    calls = []
    def get(url, **kw):
        calls.append((url, kw))
        return response or Document()
    return s.SourceCollector(get=get, sec_headers={"User-Agent": "Offline Test offline@research.test",
        "APCA-API-KEY-ID": "NEVER_FORWARD", "Authorization": "NEVER_FORWARD"}, now=lambda: NOW), calls


def packet(c, news=(), filings=()):
    return c.packet(run_key="OFFLINE_KEY", symbol="TEST", news_evidence=list(news), sec_evidence=list(filings))


@pytest.mark.parametrize("url", [
    "http://www.sec.gov/Archives/edgar/data/1/000000000126000001/filing.htm",
    "https://attacker.invalid/filing.htm", BASE+"../filing.htm", BASE+"%2e%2e/filing.htm",
    BASE+"filing.htm?secret=bad", BASE+"filing.htm#fragment", BASE+"folder/filing.htm",
    BASE.replace("www.sec.gov", "user:password@www.sec.gov")+"filing.htm",
    BASE.replace("www.sec.gov", "www.sec.gov:443")+"filing.htm",
    BASE.replace("/data/1/", "/data/2/")+"filing.htm", BASE+"filing.pdf"])
def test_unsafe_destination_never_fetched(url):
    c, calls = collector()
    result = c.filing_documents(dict(META, url=url))
    assert result["documents"][0]["status"] == "UNAVAILABLE" and calls == []


@pytest.mark.parametrize("change", [{"issuer_cik": "0"}, {"issuer_cik": "-1"},
    {"issuer_cik": "a"}, {"accession": "invalid"}, {"accession": None}])
def test_bad_identity_never_fetched(change):
    c, calls = collector()
    assert c.filing_documents(dict(META, **change))["documents"][0]["status"] == "UNAVAILABLE"
    assert not calls


def test_sec_provenance_only_declared_headers_cache_and_unverified_semantics():
    response = Document()
    c, calls = collector(response)
    p = packet(c, filings=[META])
    assert verify_packet(p, run_key="OFFLINE_KEY", symbol="TEST")
    r = p["sources"][0]
    assert r["accession"] == META["accession"] and r["issuer_cik"] == "1"
    assert r["raw_sha256"] == hashlib.sha256(response.body).hexdigest()
    assert r["filing_date_is_event_timestamp"] is False
    assert not r["same_event_verified"] and not p["qualification_created"]
    assert response.closed and len(calls) == 1
    assert set(calls[0][1]["headers"]) == {"User-Agent", "Accept"}
    assert calls[0][1]["stream"] and calls[0][1]["allow_redirects"] is False
    packet(c, filings=[META])
    assert len(calls) == 1


@pytest.mark.parametrize("body,status,mime,reason", [
    (b"redirect", 302, "text/html", "DOCUMENT_HTTP_UNAVAILABLE"),
    (b"rate limit", 429, "text/html", "DOCUMENT_HTTP_UNAVAILABLE"),
    (b"PDF", 200, "application/pdf", "DOCUMENT_TYPE_UNSUPPORTED"),
    (b"\xff", 200, "text/html", "DOCUMENT_ENCODING_UNSUPPORTED"),
    (b"<script>untrusted instructions</script>", 200, "text/html", "DOCUMENT_TEXT_EMPTY"),
    (b"a"*(s.MAX_BODY_BYTES+1), 200, "text/plain", "DOCUMENT_BODY_LIMIT")],
    ids=["redirect", "rate-limit", "pdf", "encoding", "empty-visible", "oversize"])
def test_unavailable_no_retry_and_response_closed(body, status, mime, reason):
    response = Document(body, status, mime)
    c, calls = collector(response)
    assert packet(c, filings=[META])["sources"][0]["reason"] == reason
    packet(c, filings=[META])
    assert len(calls) == 1 and response.closed


def test_hidden_text_and_passage_offsets():
    raw = b'<script>BAD</script><style>BAD</style><p hidden>BAD</p><div style="display: none">BAD</div><p style>GOOD</p><ix:hidden>BAD</ix:hidden>'
    c, _ = collector(Document(raw))
    p = packet(c, filings=[META])
    assert p["sources"][0]["passages"] == [{"start": 0, "end": 4, "text": "GOOD"}]
    assert verify_packet(p, run_key="OFFLINE_KEY", symbol="TEST")


def test_truncation_explicit_and_integrity_verified():
    c, _ = collector(Document(b"x"*30000, mime="text/plain"))
    p = packet(c, filings=[META])
    r = p["sources"][0]
    assert r["text_truncated"] and r["retained_text_chars"] == 24000 and r["normalized_text_chars"] == 30000
    assert verify_packet(p, run_key="OFFLINE_KEY", symbol="TEST")
    r["passages"][0]["end"] += 1
    p["packet_sha256"] = digest({k:v for k,v in p.items() if k != "packet_sha256"})
    assert not verify_packet(p, run_key="OFFLINE_KEY", symbol="TEST")


def test_exhibits_bounded_same_accession_and_no_arbitrary_crawl():
    raw = b'<p>Primary</p><a href="ex99-1.htm">1</a><a href="ex99-2.htm">2</a><a href="ex99-3.htm">3</a><a href="https://attacker.invalid/ex99.htm">bad</a><a href="../ex99.htm">bad</a>'
    c, calls = collector(Document(raw))
    result = c.filing_documents(META)
    assert [u for u,_ in calls] == [META["url"], BASE+"ex99-1.htm", BASE+"ex99-2.htm"]
    assert result["linked_exhibits_not_retrieved"] == [BASE+"ex99-3.htm"]
    assert result["exhibit_search_complete"] is False and len(result["documents"]) == 3


@pytest.mark.parametrize("guard", ["contact", "documents", "bytes"])
def test_document_budget_and_contact_fail_before_network(guard):
    c, calls = collector()
    if guard == "contact": c.headers["User-Agent"] = "contact@example.com"
    if guard == "documents": c.calls = s.MAX_DOCUMENTS
    if guard == "bytes": c.bytes_read = s.MAX_TOTAL_BYTES
    assert packet(c, filings=[META])["sources"][0]["status"] == "UNAVAILABLE"
    assert not calls


def test_transport_and_close_failures_redacted():
    c, calls = collector()
    def bad(*a, **kw): raise RuntimeError("PRIVATE_DIAGNOSTIC")
    c.get = bad
    p = packet(c, filings=[META])
    assert p["sources"][0]["reason"] == "DOCUMENT_TRANSPORT_OR_DEADLINE"
    assert "PRIVATE_DIAGNOSTIC" not in json.dumps(p)
    response = Document()
    response.close = bad
    c, _ = collector(response)
    assert packet(c, filings=[META])["sources"][0]["reason"] == "DOCUMENT_CLOSE_FAILED"


def test_news_reprints_missing_content_and_unrelated_sources_not_verified():
    c, calls = collector()
    c.index_news([{"id": 1, "content": "<p>Unrelated invented event</p>", "symbols": ["TEST"]},
                  {"id": 2, "content": "<p>Unrelated invented event</p>", "symbols": ["TEST"]},
                  {"id": 3, "summary": "Summary must not stand in for document", "symbols": ["TEST"]}])
    p = packet(c, news=[{"alpaca_news_id": n} for n in (1,2,3,4)], filings=[META])
    assert p["identical_text_groups"] == [["ALPACA_NEWS:1", "ALPACA_NEWS:2"]]
    assert p["sources"][2]["reason"] == "NEWS_CONTENT_UNAVAILABLE"
    assert p["sources"][3]["reason"] == "NEWS_ID_NOT_COLLECTED"
    assert all(not r["same_event_verified"] for r in p["sources"])
    assert verify_packet(p, run_key="OFFLINE_KEY", symbol="TEST")
    assert len(calls) == 1  # No news URL is fetched.


def test_news_parse_once_and_packet_caps(monkeypatch):
    c, _ = collector()
    article = {"id": 1, "content": "<p>offline content</p>", "symbols": ["A", "B"]}
    c.index_news([article])
    monkeypatch.setattr(s, "document_record", lambda *a, **kw: pytest.fail("must reuse parsed article"))
    c.index_news([article])
    p = packet(c, news=[{"alpaca_news_id": n} for n in range(15)])
    assert len(p["sources"]) == 12 and len(p["unretrieved_news_ids"]) == 3


@pytest.mark.parametrize("field", ["same_event_verified", "automatic_promotion", "strategy_evidence_eligible"])
def test_rehashed_packet_cannot_claim_approval(field):
    c, _ = collector()
    p = packet(c)
    p[field] = True
    p["packet_sha256"] = digest({k:v for k,v in p.items() if k != "packet_sha256"})
    assert not verify_packet(p, run_key="OFFLINE_KEY", symbol="TEST")


def test_verification_still_rejects_when_python_assertions_disabled():
    namespace = {}
    path = Path(__file__).resolve().parents[1]/"coordinator_acceptance_verify.py"
    exec(compile(path.read_text(), str(path), "exec", optimize=2), namespace)
    c, _ = collector()
    p = packet(c)
    p["automatic_promotion"] = True
    p["packet_sha256"] = digest({k:v for k,v in p.items() if k != "packet_sha256"})
    assert not namespace["verify_packet"](p, run_key="OFFLINE_KEY", symbol="TEST")


def test_content_news_request_stream_bounded_and_closed():
    calls = []
    response = Document(json.dumps({"news":[{"id":1,"symbols":["TEST"],"content":"<p>Test</p>"}]}).encode())
    def get(url, **kw): calls.append(kw); return response
    result = collect_news({}, 24, end=NOW, get=get, include_content=True)
    assert result["collection"]["feed_exhausted"] and response.closed
    assert calls[0]["params"]["include_content"] == "true" and calls[0]["stream"]
    response.body = b"x"*(2*1024*1024+1)
    result = collect_news({}, 24, end=NOW, get=get, include_content=True)
    assert result["news"] == [] and result["collection"]["outcome"] == "BODY_LIMIT"


def test_content_news_error_response_is_closed():
    response = Document(status=429)
    result = collect_news({}, 24, end=NOW, get=lambda *a, **kw: response, include_content=True)
    assert result["news"] == [] and response.closed
    assert result["collection"]["outcome"] == "PROVIDER_UNAVAILABLE"


def test_document_total_bytes_and_stream_failure():
    c, _ = collector(Document(b"bounded text"))
    c.bytes_read = s.MAX_TOTAL_BYTES-1
    assert packet(c, filings=[META])["sources"][0]["reason"] == "DOCUMENT_BODY_LIMIT"
    response = Document()
    def broken(*a):
        yield b"partial"
        raise TimeoutError("PRIVATE_DIAGNOSTIC")
    response.iter_content = broken
    c, _ = collector(response)
    p = packet(c, filings=[META])
    assert p["sources"][0]["status"] == "UNAVAILABLE" and response.closed
    assert "PRIVATE_DIAGNOSTIC" not in json.dumps(p)


def test_rate_limit_wait_cannot_overrun_deadline():
    tick, wall, calls = [0.0], [NOW], []
    c = Controls(session_date=NOW.date(), implementation="OFFLINE", now=lambda: wall[0],
        clock=lambda: tick[0], sleep=lambda _: pytest.fail("cannot sleep past deadline"),
        transport=lambda *a, **kw: calls.append(a) or Document())
    c.admit(d.ScanRequest(**REQUEST), service=SERVICE, database=DATABASE, ruleset="v0.3")
    c.source_get(META["url"])
    wall[0] = NOW.replace(minute=9, second=59, microsecond=950000)
    with pytest.raises(HTTPException):
        c.source_get(META["url"])
    assert len(calls) == 1


def test_rate_limit_combines_metadata_and_document_hosts():
    tick, calls, sleeps = [0.0], [], []
    def sleep(seconds): sleeps.append(seconds); tick[0] += seconds
    def transport(*a, **kw): calls.append((a, tick[0])); return Document()
    c = Controls(session_date=NOW.date(), implementation="OFFLINE", now=lambda: NOW,
        clock=lambda: tick[0], sleep=sleep, transport=transport)
    c.admit(d.ScanRequest(**REQUEST), service=SERVICE, database=DATABASE, ruleset="v0.3")
    c.source_get("https://data.sec.gov/submissions/CIK0000000001.json")
    c.source_get(META["url"])
    c.source_get("https://data.sec.gov/submissions/CIK0000000002.json")
    assert len(calls) == 3 and sleeps == [0.2, 0.2]


def test_coordinator_packet_persistence_readback_and_prior_preservation(wired, monkeypatch):
    before = wired.db.snapshot()
    monkeypatch.setattr(d, "SEC_USER_AGENT", "Offline Test offline@research.test")
    monkeypatch.setattr(d, "fetch_recent_sec", lambda *a: [deepcopy(META)])
    calls = []
    def get(url, **kw): calls.append(url); return Document()
    monkeypatch.setattr(d, "source_get", get)
    original_news = d.fetch_news
    def news(*a):
        result = original_news(*a)
        result["news"][0]["content"] = "<p>Invented earnings story; not the same event as the filing.</p>"
        result["news"].append({"id":99,"symbols":[],"content":"<p>Unassigned macro story</p>"})
        return result
    monkeypatch.setattr(d, "fetch_news", news)
    result = run(wired)
    assert result.status_code == 200, result.text
    after = wired.db.snapshot()
    report = verify(before, after, run_key=wired.controls[0].run_key, implementation="OFFLINE_IMPLEMENTATION")
    assert report["passed"], report
    assert calls == [META["url"]]  # Same filing reused across two candidate packets.
    notes = json.loads(wired.db.runs[-1]["notes"])
    assert notes["coverage"]["unassigned_news_content"][0]["source_id"] == "ALPACA_NEWS:99"
    assert notes["coverage"]["source_documents"]["full_source_coverage"] is False
    item = next(r for r in wired.db.items if r.get("symbol") == "S00000")
    p = item["mover_snapshot"]["catalyst_review_packet"]
    assert len(p["sources"]) == 2 and p["same_event_verified"] is False
    assert item["mover_snapshot"]["premarket_activity"]["gap_percent_unadjusted"] is None
