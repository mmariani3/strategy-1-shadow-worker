# Public source evidence collection

This adds a local read-only collector between discovery and research review. It consumes an existing full-funnel evidence bundle, fetches **only its recorded public source URLs**, preserves original bytes and source associations, and creates additive research packets. It never writes to trading services, the Journal or a broker, and never calls an AI model.

## Authority and scope

Strategy Rules v0.3, Experiment Plan v0.5 and Automation Specification v0.4 remain the living authorities. Their revisions were rechecked on September 18, 2026 and were unchanged from the prior implementation. No strategy rules, thresholds, trade decisions, confirmation policy, risk limits or observation eligibility are changed. Original bundles, packet IDs, discovery dates, authority references and source records are preserved.

This is **document retrieval**, not new catalyst discovery or qualification. If a record has no source link, it stays `SOURCE_DISCOVERY_REQUIRED`. The collector does not guess a company's investor-relations domain, search for a new event, infer independence from the same ticker, or use a publication/filing date as the underlying catalyst's event time.

## Entry points

Use the existing Python development/journal environment. No additional package or paid service is required.

Offline planning and cached reads (default):

```text
python run_source_collection.py --bundle PRIVATE_BUNDLE.json --output PRIVATE_OUTPUT --store PRIVATE_OUTPUT/captures.sqlite
```

For an explicitly authorized public collection, set `EVIDENCE_USER_AGENT` privately to an identifying application name and real contact email. Then reuse the saved plan:

```text
python run_source_collection.py --bundle PRIVATE_BUNDLE.json --plan PRIVATE_PLAN.json --output PRIVATE_OUTPUT --store PRIVATE_OUTPUT/captures.sqlite --fetch --collection-key UNIQUE_COLLECTION_KEY --max-documents 54 --allow-host www.sec.gov --allow-host www.benzinga.com
```

The listed hosts are the two observed in the September 18 saved scan, not a universal provider configuration. A company release or another news publisher uses the public-text adapter only when its exact host is explicitly allowed and the URL already exists in captured evidence. Subdomains are not implicitly authorized. This collector has no credentials for restricted content.

`--fetch` is required for network access. `--max-documents` bounds unique document attempts per collection key, including failed attempts. Robots requests are additional and reported in `http_requests`. The key's plan, limit, allowed hosts, refresh setting and implementation identity cannot silently change. Reuse the same saved plan/key/store to resume. A reserved but unfinished request remains visibly interrupted rather than being blindly retried. An operator can explicitly authorize a later collection key after inspecting failures.

Without `--refresh`, existing successful captures are reused as **cached snapshots, not refreshed evidence**. A new key with `--refresh` explicitly rechecks versions, using ETag/Last-Modified when available. A 304 preserves original capture time and records a separate check time. A changed document gets a new hash; prior bytes, results and history remain present. No refresh renews a catalyst, qualification or risk approval.

## Adapters and boundaries

- SEC archive adapter validates the captured accession against the filing URL path. It does not equate the accession's filer prefix with issuer CIK or claim that a same-symbol filing verifies a news event.
- Public HTML/plain-text adapter handles accessible news and company-release URLs. It removes scripts/styles from extracted text, records publisher-supplied date metadata as unverified claims, and retains the original response bytes. Extraction completeness and semantic relevance remain unestablished.
- URL guard requires HTTPS, exact allowed hosts, no URL credentials, no nonstandard port and no IP literals. DNS must resolve entirely to global addresses. The socket connects to a validated numeric address while TLS verifies the original hostname, avoiding a second hostname resolution at connection time.
- No cookies, login flow, API keys, ambient proxy authentication, JavaScript execution, recursive crawling or redirect following. Robots restrictions/unavailable policies fail closed. HTTP errors, redirects, access-page indications, oversized/unsupported documents and encoding problems remain explicit.
- Retrieval runs at most one HTTP request per second per process, with bounded time/size. More restrictive site schedules are deferred. This is **not an aggregate multi-host rate limiter**; concurrent hosted rollout must coordinate overall provider limits before activation.
- Default maximum document size is 4,000,000 bytes. Oversized responses are not silently truncated into apparently complete evidence. PDFs, dynamic-only pages, non-identity compression and unsupported encodings require separate future adapters. These are infrastructure resource limits, not strategy thresholds.

SEC's published guidance calls for an identified User-Agent, efficient downloads, and no more than 10 requests/second across the user's machines: [Developer Resources](https://www.sec.gov/about/developer-resources), [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data). The application uses a lower per-process rate and does not bypass access restrictions.

## Storage and handoffs

`CaptureStore` creates its private local SQLite schema reproducibly: immutable collection policies, URL reservations, outcomes, and content-addressed raw documents/extracted text. Unique reservations and immediate transactions protect against duplicate fetches under the same key. Identical bytes share one document row while separate URL/candidate associations remain. Hashes detect corruption; they do not authenticate authorship or prove source independence.

The collection report links all original records, including unavailable/deferred records. New packet files are created only where text was captured. They retain `parent_packet_id`, original `discovery_captured_at`, the current collection identity, unchanged run/candidate/signal/journal IDs and each originating source ID. All original source text remains. New documents are marked `available_at_original_scan=NOT_ESTABLISHED`. The new packet's capture time belongs to this later research collection; it is not a retrospective trade confirmation.

The report index lists every resulting packet ID and reruns the offline code checks. Derived packets can be passed individually to the existing research CLI, subject to its authority, size and spending guards. They are **not** replacement full-funnel `evidence_pipeline` bundles and cannot be passed to `plan_bundle` as if they were original snapshots. The original bundle plus collection manifest remains the complete lineage.

Do not commit private captures or source documents to Git. Store contents may contain copyrighted source material and project evidence. No hosted retention, backup or deployment configuration is supplied by this local implementation. No production schema migration is required.

## Initial September 18 acceptance evidence

- Original funnel retained: **112 records**.
- Deduplicated recorded URLs: **54** (22 SEC, 32 news).
- Captured: **53**; one exceeded the 4 MB limit and remains explicitly unavailable.
- Records with captured text for research: **87**; **25** have no source URLs and require additional discovery.
- Repeating the same completed collection: **zero HTTP requests**.
- Explicit SEC conditional recheck: **HTTP 304**, with original capture time preserved.
- Offline model-request size check: **86** records fit the existing 250,000-byte limit; **one** exceeds it; **25** remain missing source evidence. No model requests were sent or charged.

The original scan is still PARTIAL. No candidate has been independently qualified by this work and opportunity count remains unknown. Captured filing covers may refer to exhibits that this nonrecursive collector has not fetched. Article text may contain navigation or unrelated tickers. Longer documents can increase model input costs; retrieval success is not a claim of lower total AI cost. The next review stage must keep relevant, exact evidence with traceable exclusions rather than silently truncate documents or loosen eligibility.

### Subsequent source-readiness review

A separate explicit one-document retry with a recorded 10 MB resource bound captured the missing SEC filing: 4,002,188 original bytes, just over the initial limit. The old failed outcome remains intact. All **54 original URLs** are now captured. This was a local acceptance operation with its own persisted URL/size/attempt policy, not a change to the CLI's 4 MB default or an automatic retry.

The reviewer now uses [lossless source encoding](README-automated-reviewer.md#lossless-source-encoding), eliminating duplicate raw/text copies. All 87 packets from the original 53-document capture fit the existing request limit. Including the newly recovered long filing gives **86 within-limit records, one explicitly held long-document record (FEAM), and 25 records without linked catalyst evidence**, preserving all 112 records. An offline reconstruction check reproduced every packet exactly; cached collection made zero HTTP requests.

A bounded external search was performed for each of the 25 absent-source symbols. Those results are separate, unverified research leads, not automatically attached evidence or proof of a fresh catalyst. Direct issuer/SEC reads confirmed examples of rights, warrants and ETFs among the leads. A current instrument identity, company/event relevance, publication versus event timing, and required source coverage must be established before qualification. Do not turn suffixes, article categories or old search results into new strategy filters.

Eight purposefully selected source-cited reference cases were prepared locally before any separate API-model response: matching events, unrelated news/filing events, missing exhibits, older event dates, instrument identity, earnings previews and absent evidence. They are implementation-author research references, not independent ground truth, a representative accuracy sample or Strategy #1 observations. Seven within-limit model requests were prepared with a non-dispatch placeholder model; the missing-source case remains blocked. No API call or semantic acceptance occurred.

The full repository suite passed **276 tests**, including lossless Unicode/nested-record reconstruction, altered/duplicate source rejection, exact byte boundaries, evidence tampering before call reservation, historical response recovery and version attribution. Long-document interpretation, missing exhibits, new-event verification, independently accepted reference assessment and hosted integration remain unresolved.

## Tests and deployment status

Run `python -m pytest -q`. Tests block sockets/provider calls and cover URL/DNS guards, pinned transport, robots denial, bounded reads, source/accession matching, extraction failures, full-funnel preservation, shared URLs, unchanged/changed versions, interrupted/concurrent reservations, persistent attempt limits, immutable records and additive packet lineage.

Live public-GET acceptance was performed locally only. The collector is not deployed or scheduled. Phase 1 remains SHADOW; broker execution remains disabled by repository design. Current production runtime configuration and live Journal state were not reverified in this work.
