"""Bounded source documents and review packets; never catalyst approval.

Transport is injected, has no implicit credentials, and may fetch only validated
SEC archive paths. Provider news is parsed as supplied data, never crawled.
Source text is untrusted evidence, not instructions or executable HTML.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit, urljoin

from setup_evidence import digest

SCHEMA = "catalyst-review-packet/v1"
MAX_DOCUMENTS = 64
MAX_BODY_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARS = 24000
PASSAGE_CHARS = 1500
MAX_NEWS_PER_PACKET = 12
MAX_FILINGS_PER_SYMBOL = 2
MAX_EXHIBITS_PER_FILING = 2
ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z")
FILENAME = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,180}\.(?:htm|html|txt)\Z", re.I)


class EvidenceError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise EvidenceError(code)


def secure_sec_url(metadata):
    cik = str(metadata.get("issuer_cik", ""))
    accession = metadata.get("accession", "")
    require(re.fullmatch(r"[0-9]{1,10}", cik) and int(cik) > 0
            and isinstance(accession, str) and ACCESSION.fullmatch(accession), "SEC_IDENTITY_INVALID")
    url = metadata.get("url", "")
    require(isinstance(url, str), "SEC_URL_INVALID")
    parts = urlsplit(url)
    folder = f"/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
    name = parts.path[len(folder):] if parts.path.startswith(folder) else ""
    require(parts.scheme == "https" and parts.netloc == "www.sec.gov" and not parts.query
            and not parts.fragment and FILENAME.fullmatch(name) and ".." not in name,
            "SEC_URL_INVALID")
    return url, folder


class TextParser(HTMLParser):
    """Extract visible text only; no script, CSS, iframe, or link execution."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.stack = []
        self.parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        style = re.sub(r"\s+", "", (attrs.get("style") or "").lower())
        hidden = (tag in {"script", "style", "noscript", "iframe", "svg", "ix:hidden"}
                  or "hidden" in attrs or "display:none" in style or "visibility:hidden" in style)
        if tag not in {"br", "hr", "img", "meta", "link", "input", "wbr", "source"}:
            self.stack.append((tag, hidden))
            self.hidden_depth += int(hidden)
        if not self.hidden_depth:
            if tag in {"p", "div", "tr", "td", "br", "li", "h1", "h2", "h3"}:
                self.parts.append(" ")
            if tag == "a" and isinstance(attrs.get("href"), str):
                self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, -1, -1):
            if self.stack[i][0] == tag:
                self.hidden_depth -= sum(int(hidden) for _, hidden in self.stack[i:])
                del self.stack[i:]
                break
        if not self.hidden_depth:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden_depth:
            self.parts.append(data)


def document_record(raw, *, source_id, source_url, source_kind, retrieved_at, html=True):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BODY_BYTES, "DOCUMENT_BODY_LIMIT_OR_EMPTY")
    try:
        decoded = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise EvidenceError("DOCUMENT_ENCODING_UNSUPPORTED") from None
    parser = TextParser()
    if html:
        parser.feed(decoded)
        parser.close()
        text = " ".join("".join(parser.parts).split())
    else:
        text = " ".join(decoded.split())
    require(bool(text), "DOCUMENT_TEXT_EMPTY")
    retained = text[:MAX_TEXT_CHARS]
    passages = [{"start": start, "end": min(start+PASSAGE_CHARS, len(retained)),
                 "text": retained[start:start+PASSAGE_CHARS]} for start in range(0, len(retained), PASSAGE_CHARS)]
    record = {"source_id": source_id, "source_url": source_url, "source_kind": source_kind,
              "status": "CONTENT_RETRIEVED_REVIEW_REQUIRED", "retrieved_at": retrieved_at,
              "raw_sha256": hashlib.sha256(raw).hexdigest(),
              "normalized_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
              "retained_text_sha256": hashlib.sha256(retained.encode()).hexdigest(),
              "body_bytes": len(raw), "normalized_text_chars": len(text),
              "retained_text_chars": len(retained), "text_truncated": len(text) > len(retained),
              "passages": passages, "passage_selection": "LEADING_TEXT_IN_DOCUMENT_ORDER_NOT_RELEVANCE_RANKED",
              "untrusted_source_content": True, "content_retrieval_proves_catalyst": False,
              "event_timestamp_verified": False, "issuer_relationship_verified": False,
              "same_event_verified": False, "source_independence_verified": False}
    return record, parser.links


def unavailable(source_id, kind, reason, *, source_url=None):
    return {"source_id": source_id, "source_kind": kind, "source_url": source_url,
            "status": "UNAVAILABLE", "reason": reason, "passages": [],
            "event_timestamp_verified": False, "issuer_relationship_verified": False,
            "same_event_verified": False, "source_independence_verified": False}


class SourceCollector:
    def __init__(self, *, get, sec_headers, now=None):
        self.get = get
        # Copy only the SEC-specific User-Agent. Never forward broker credentials.
        self.headers = {"User-Agent": sec_headers.get("User-Agent", ""), "Accept": "text/html,text/plain"}
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.calls = 0
        self.bytes_read = 0
        self.cache = {}
        self.news = {}

    def _document(self, metadata, role):
        identity = str(metadata.get("accession", "UNKNOWN"))
        try:
            url, folder = secure_sec_url(metadata)
        except (EvidenceError, ValueError, TypeError):
            return unavailable("SEC:INVALID", "SEC_FILING", "SEC_IDENTITY_OR_URL_INVALID"), []
        source_id = "SEC:"+identity+":"+url.rsplit("/", 1)[-1]
        if url in self.cache:
            return deepcopy(self.cache[url])
        result, links = None, []
        response = None
        try:
            contact = self.headers["User-Agent"]
            require(bool(re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+", contact))
                    and "example.com" not in contact.lower(), "SEC_CONTACT_UNCONFIGURED")
            require(self.calls < MAX_DOCUMENTS and self.bytes_read < MAX_TOTAL_BYTES, "DOCUMENT_BUDGET_EXHAUSTED")
            self.calls += 1
            response = self.get(url, headers=self.headers.copy(), stream=True,
                                timeout=(3, 10), allow_redirects=False)
            require(response.status_code == 200, "DOCUMENT_HTTP_UNAVAILABLE")
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            require(content_type in {"text/html", "text/plain", "application/xhtml+xml"}, "DOCUMENT_TYPE_UNSUPPORTED")
            chunks = bytearray()
            for chunk in response.iter_content(16384):
                require(isinstance(chunk, bytes), "DOCUMENT_BODY_INVALID")
                self.bytes_read += len(chunk)
                require(self.bytes_read <= MAX_TOTAL_BYTES and len(chunks)+len(chunk) <= MAX_BODY_BYTES,
                        "DOCUMENT_BODY_LIMIT")
                chunks.extend(chunk)
            result, links = document_record(bytes(chunks), source_id=source_id, source_url=url,
                source_kind="SEC_FILING", retrieved_at=self.now().isoformat(), html=content_type != "text/plain")
            result.update(document_role=role, issuer_cik=str(int(str(metadata["issuer_cik"]))),
                          accession=identity, form=metadata.get("form"), filing_date=metadata.get("filing_date"),
                          filing_date_is_event_timestamp=False)
        except EvidenceError as exc:
            result = unavailable(source_id, "SEC_FILING", str(exc), source_url=url)
        except Exception:
            result = unavailable(source_id, "SEC_FILING", "DOCUMENT_TRANSPORT_OR_DEADLINE", source_url=url)
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    # Cleanup diagnostics are untrusted and may contain headers.
                    result = unavailable(source_id, "SEC_FILING", "DOCUMENT_CLOSE_FAILED", source_url=url)
                    links = []
        self.cache[url] = deepcopy((result, links))
        return result, links

    def filing_documents(self, metadata):
        primary, links = self._document(metadata, "PRIMARY_DOCUMENT")
        records = [primary]
        selected = []
        if primary["status"] == "CONTENT_RETRIEVED_REVIEW_REQUIRED":
            for href in links:
                # Only directly linked exhibit 99 filenames under the same
                # accession. No index discovery or arbitrary issuer-site crawl.
                url = urljoin(metadata["url"], href)
                child = dict(metadata, url=url)
                try:
                    secure_sec_url(child)
                except (EvidenceError, ValueError, TypeError):
                    continue
                name = url.rsplit("/", 1)[-1]
                if re.search(r"(?:ex(?:hibit)?[-_]?99|99[-_.]?[12])", name, re.I) and url not in selected:
                    selected.append(url)
            for url in selected[:MAX_EXHIBITS_PER_FILING]:
                record, _ = self._document(dict(metadata, url=url), "LINKED_EXHIBIT_REVIEW_REQUIRED")
                records.append(record)
        return {"documents": records, "linked_exhibits_identified": len(selected),
                "linked_exhibits_not_retrieved": selected[MAX_EXHIBITS_PER_FILING:],
                "exhibit_search_complete": False,
                "limitation": "Only directly linked matching exhibit filenames; other exhibits may exist."}

    def index_news(self, articles):
        for article in articles:
            source_id = "ALPACA_NEWS:"+str(article.get("id"))
            if source_id in self.news:
                continue
            content = article.get("content")
            record = unavailable(source_id, "PROVIDER_NEWS_CONTENT", "NEWS_CONTENT_UNAVAILABLE",
                                 source_url=article.get("url"))
            if isinstance(content, str) and content.strip():
                try:
                    record, _ = document_record(content.encode(), source_id=source_id, source_url=article.get("url"),
                        source_kind="PROVIDER_NEWS_CONTENT", retrieved_at=self.now().isoformat())
                except EvidenceError as exc:
                    record = unavailable(source_id, "PROVIDER_NEWS_CONTENT", str(exc), source_url=article.get("url"))
            record.update(provider="ALPACA_NEWS", attributed_source=article.get("source") or article.get("author"),
                          published_at=article.get("created_at"), updated_at=article.get("updated_at"),
                          headline=article.get("headline"), declared_symbols=deepcopy(article.get("symbols", [])),
                          publisher_url_fetched=False)
            self.news[source_id] = record

    def packet(self, *, run_key, symbol, news_evidence, sec_evidence):
        news_ids = list(dict.fromkeys("ALPACA_NEWS:"+str(n.get("alpaca_news_id")) for n in news_evidence))
        sources = [deepcopy(self.news.get(key, unavailable(key, "PROVIDER_NEWS_CONTENT", "NEWS_ID_NOT_COLLECTED")))
                   for key in news_ids[:MAX_NEWS_PER_PACKET]]
        filing_details = []
        for metadata in sec_evidence[:MAX_FILINGS_PER_SYMBOL]:
            result = self.filing_documents(metadata)
            sources.extend(result["documents"])
            filing_details.append({k: v for k, v in result.items() if k != "documents"})
        # Keep duplicate content as evidence, with an explicit independence warning.
        groups = {}
        for source in sources:
            key = source.get("normalized_text_sha256")
            if key:
                groups.setdefault(key, []).append(source["source_id"])
        packet = {"schema": SCHEMA, "run_key": run_key, "symbol": symbol,
            "experiment_class": "INFRASTRUCTURE_TEST", "strategy_evidence_eligible": False,
            "mode": "SHADOW", "status": "REVIEW_REQUIRED", "sources": sources,
            "unretrieved_news_ids": news_ids[MAX_NEWS_PER_PACKET:],
            "unretrieved_filing_count": max(0, len(sec_evidence)-MAX_FILINGS_PER_SYMBOL),
            "filing_collection": filing_details,
            "identical_text_groups": [ids for ids in groups.values() if len(ids) > 1],
            "independence_warning": "Identical/reprinted text is not independent confirmation; different text does not prove independence.",
            "review_questions": ["Do source passages describe the same underlying event and issuer?",
                "Is the underlying event time within the required discovery window?",
                "Are the sources independent, or reprints of one originating statement?",
                "Do sources conflict, omit a material qualification, or discuss different events?",
                "For analyst actions, which firm/action is directly attributable?",
                "For sector events, what source supports the direct company relationship?"],
            "same_event_verified": False, "source_independence_verified": False,
            "issuer_relationship_verified": False, "event_timestamp_verified": False,
            "qualification_created": False, "automatic_promotion": False,
            "full_discovery_accepted": False}
        packet["packet_sha256"] = digest(packet)
        return packet

    def summary(self):
        records = [r[0] for r in self.cache.values()]
        return {"document_requests": self.calls, "document_bytes_read": self.bytes_read,
                "unique_sec_documents": len(records), "news_records": len(self.news),
                "sec_status_counts": dict(Counter(r["status"] for r in records)),
                "sec_unavailable_reasons": dict(Counter(r.get("reason") for r in records if r["status"] == "UNAVAILABLE")),
                "news_status_counts": dict(Counter(r["status"] for r in self.news.values())),
                "max_documents": MAX_DOCUMENTS, "max_body_bytes": MAX_BODY_BYTES,
                "max_total_bytes": MAX_TOTAL_BYTES, "full_source_coverage": False}
