# Local source retrieval and catalyst review packets

October 13, 2026. Local implementation only. Final offline suite: 579 passed;
one existing Starlette/AnyIO deprecation warning. No hosted request, deployment,
credential-store access, service activation, schedule change, order or Journal write.
No fresh live infrastructure state is claimed. Governing master references remain
Rules v0.3, Experiment v0.5 and Automation v0.4, as refreshed in
`../tooling/coordinator-review-authorities-2026-10-13.json`.

## Implemented scope

The existing normal Coordinator flow, only within its isolated acceptance context,
requests Alpaca news content and retrieves SEC primary filing documents for already
discovered symbols. SEC retrieval validates the exact HTTPS host, CIK, accession
directory and document filename. It follows at most two directly linked exhibit-99
filenames per filing within that same directory. No arbitrary publisher URL,
company-site crawl, redirect, paid source or new credential scope is used.

News content is provider-supplied; `publisher_url_fetched=false` distinguishes it
from independently retrieved publisher content. Headlines/summaries cannot replace
missing content. SEC filing dates and news update times are not verified event times.
SEC User-Agent must contain a configured contact; the default example contact is
rejected for document retrieval. Real availability and configuration are unverified.

Each lead receives a run/symbol-bound `catalyst-review-packet/v1` in its existing
item JSON. It retains source IDs, URLs, retrieval timestamps, filing identities,
provider attribution, passages, hashes, truncation, unavailable reasons, and
identical-text warnings. Symbol-less news content stays in run coverage. Same-ticker
news and filings remain separate evidence; no same-event match, issuer relationship,
event timestamp, source independence, tier or materiality is approved automatically.
All packets remain SHADOW / REVIEW_REQUIRED / INFRASTRUCTURE_TEST and experiment
ineligible. Failed snapshot fields remain unchanged; dated raw closes remain
separate review-required evidence, not approved reference prices.

## Operational bounds and explicit limitations

- Per run: at most 64 SEC document requests, 512 KiB per document, 8 MiB aggregate
  SEC bytes, within the existing 2,000 total source requests and 06:10 fetch cutoff.
- Combined SEC metadata/document requests are spaced at least 0.2 seconds apart
  in the isolated controller. This is not a distributed limit: other callers must
  remain suspended. HTTP failures, rate limits and ambiguous requests are not retried.
- Per candidate: at most 12 news records and two filings, each with at most two
  matching directly linked exhibits. Omitted IDs/counts are explicit. This cap is
  an infrastructure budget, never a strategy selection criterion.
- Content-bearing news pages use streaming with a 2 MiB cap, at most ten pages
  and the existing 45-second collection limit. Byte/time exhaustion stays partial.
- Each document retains at most 24,000 normalized text characters in ordered
  1,500-character passages. These are leading passages, not relevance-selected
  extracts. Later relevant passages may be missing. Only UTF-8 text/HTML is supported;
  other encodings, PDFs, scanned documents and nonmatching/unlinked exhibits remain
  unavailable or outside scope. Script/hidden content is not executed or retained.
- Full raw and normalized hashes are recorded at retrieval; raw document bytes are
  not persisted. Independent readback verifies retained-text hashes, passage offsets,
  packet hashes, bindings, flags and audit/persistence integrity. It cannot independently
  reconstruct omitted bytes or establish semantic truth/authenticity from a hash.
- Exact duplicate text warns against treating reprints as independent confirmation.
  Different hashes do not prove independence. No semantic deduplication is claimed.
- Existing item/run JSON and audit structure are reused. No hosted schema change
  or storage-capacity/performance acceptance has occurred. Budget/size failures
  remain failures or partial evidence; no truncation is silently called complete.

The implementation follows the SEC's declared-client and fair-access guidance
([official FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions))
and Alpaca's optional news `include_content` field
([official News reference](https://docs.alpaca.markets/us/reference/news-3)).

## Verification and preserved evidence

`tests/test_catalyst_source_evidence.py` adds 42 offline cases. They cover rejected
destinations/identities, header isolation, no retry, MIME/encoding/body limits,
resource closure, hidden text, passage integrity, exhibit scope, caching, source
budgets, duplicate/missing news, packet approval tampering, checks under Python
optimization, news stream bounds, combined SEC pacing/deadlines, and normal
Coordinator persistence with independent readback and prior-row preservation.
All provider/database content is invented test data. No fixture is strategy evidence.

The first targeted run had 111 passes and two pytest fixture setup/teardown errors:
an oversized byte parameter made pytest's current-test environment value exceed
Windows' 32,767-character limit.
Short parameter IDs fixed the fixture naming. That XML is preserved; it was not a
successful run. A subsequent full run passed 575 tests; final cleanup/verifier
regressions bring the final suite to 579 passing tests.

Final results, exact local file hashes and original October 13 file checks:
`../tooling/catalyst-source-local-result-2026-10-13.json`.
Final JUnit: `../tooling/catalyst-source-final-offline-tests-2026-10-13.xml`.
Earlier records are retained without overwriting them.

## Next bounded step and authorization boundary

Review channel-specific source sufficiency and the event/issuer/cross-source
review contract, then implement the local dated launch verifier/controller and
notification failure controls. Real source entitlement/content availability,
PostgreSQL uniqueness/audit behavior, performance, watchdog cleanup and notification
delivery still need a separately authorized bounded rehearsal. A successful partial
integration/storage test must not be relabeled full six-channel discovery acceptance.

The exported application remains locked. Before any hosted work, obtain separate
authorization for the exact reviewed deployment, limited credential reuse, rehearsal
and dated attempt. Previous October 13 credential authorization does not roll forward.
Unattended activation remains blocked while mandatory safeguards are unverified.
Production schedules and ChatGPT weekday oversight should remain paused. Phase 1
is not accepted; Phase 2 is not ready.
