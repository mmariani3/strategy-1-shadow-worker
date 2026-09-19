# Automated research reviewer

This implements an opt-in OpenAI Responses API client for the packets in [PR #5](https://github.com/mmariani3/strategy-1-shadow-worker/pull/5). It can request a substantive, source-cited research assessment and compare its claims with a separately supplied reference. **It cannot qualify candidates, refresh live approvals, confirm triggers, establish experimental observations or enable execution.**

Phase 1 remains SHADOW. Strategy Rules v0.3 and Experiment Plan v0.5 are unchanged. The review method remains a proposal pending independent semantic assessment and acceptance in the governing Automation Specification. No model/provider subscription, credential, hosted service, live retrieval or deployment is provisioned by this change.

## What the reviewer receives

### Default CLI: factual research v7

The CLI now prepares `1.6.0-automated-research` / `governed-research-v7` requests
through `research_bounded.prepare_bounded_request`. The old `research_reviewer.prepare_request`,
`research_facts.prepare_fact_request`, `research_citations.prepare_selection_request`, and
`research_coverage.prepare_coverage_request` and `research_scoped.prepare_scoped_request`
remain explicit v2–v6 compatibility APIs; old requests/results retain their
original parsers and attribution. No historical output is upgraded or relabeled.

Versions 3 through 7 first ask for five source-backed findings: instrument identity, catalyst
event, actual event/announcement timing, publication timing, and document coverage
(including referenced exhibits absent from the capture). It then assesses catalyst
freshness, materiality and same-event evidence. Workflow fields remain visible but
cannot substantiate positive/negative catalyst findings. Missing review fields are
insufficient evidence, not an observed failure.

This **document-only research adapter** cannot establish market context, liquidity,
participation, setup, risk, prospective confirmation, current approvals or macro
clearance. Code requires these assessments to remain unresolved, even if the model
claims otherwise. Their corresponding accepted measurement/review adapters are not
implemented here. This restricts software capability; it does not change strategy
rules, live Worker inputs or experimental eligibility.

Versions 5 through 7 require each citation to contain a stable excerpt ID and a verbatim
`supporting_text` clause. The ID anchors the quote: it must overlap that excerpt,
but may extend through neighboring excerpts in the **same original source field**.
Version 5 requires whole-source uniqueness. Versions 6 and 7 permit repeated text only
when exactly one occurrence within the original field overlaps the selected anchor.
Two occurrences overlapping the same anchor still fail, including overlapping
substrings. A longer exact clause may disambiguate them; no location is guessed.
The server carries the derived offsets through final claim validation instead of
searching again for the first matching string. The model cannot supply offsets.
It cannot cross JSON fields, documents, or disjoint passages. This handles sentences
split by the catalogue without changing the catalogue, source text or old offsets.
Different source spans can share one anchor ID; an identical source span repeated
within one finding/claim/coverage assessment is rejected, including via a second ID.
The result records precise quote offsets and each anchor in `citation_selection_audit`.
No normalization, fuzzy matching, automatic quote repair or silent deduplication occurs.
Workflow and
market-snapshot fields remain in the complete packet but have no selectable handles.
Publication metadata can support publication facts only. Version 3's gates remain
in force for v5/v6/v7, with duplicate detection applied to exact spans. These checks detect incorrect attribution, **not** whether a real
quotation logically supports the conclusion; semantic review is still required.

The host derives each handle from the original source ID and character offsets.
Handles cannot refer to packet IDs or
governing-master IDs. Full lossless source text remains in the request; the catalogue
is an auxiliary index, not a summary or completeness claim. Repeated spans that
cannot uniquely map remain visible but unindexed. The catalogue increases request
size; the existing explicit byte limit includes it and still fails without truncation.

Code rejects non-unresolved catalyst claims citing only workflow/publication data,
freshness claims with unresolved event timing, materiality claims with unresolved
instrument/event/document coverage, and same-event claims with fewer than two distinct
substantive source IDs. Two IDs do **not** prove source independence. Source category
classification, fact status consistency and exact quotations do **not** prove semantic
truth. Every accepted result remains a research draft requiring independent review.

#### Materiality coverage is separate from a fact about missing documents

An EVIDENCED `document_coverage` finding may correctly say an exhibit is missing.
Versions 5 and 6 require a separate `materiality_coverage` object with `status`,
`missing_documents`, `rationale`, and source-cited `evidence`. Status is one of
`SUFFICIENT_FOR_RESEARCH`, `INCOMPLETE`, or `UNRESOLVED`. The first requires no
declared missing required documents and at least one substantive citation; INCOMPLETE
requires named missing documents. Publication/workflow metadata cannot establish
coverage. Missing or inconsistent declarations fail closed.

Version 6 additionally requires `assessment_scope` and `missing_document_reasons`
(one `{document, reason}` for every named missing document). Blank scope, unexplained
documents, duplicate names, or inconsistent mappings fail. Reasons must identify
which necessary fact the missing document establishes and why captured evidence
cannot establish it. The prompt separates optional corroboration and other criterion
gaps from materiality prerequisites. It does not invent a blanket original-note,
SEC-filing or primary-source requirement, and does not waive a document required
by the governing rules or the actual economic conclusion. Reputable reporting of
an attributable analyst action can support a limited research assessment; it does
not automatically clear freshness, verification, watchlist or trade requirements.
Code checks that explanations are present and consistent, **not** that their logic
is correct. The fresh provider check below exercises this contract; independent
semantic acceptance remains outstanding.

Either a positive or negative materiality conclusion requires sufficient coverage
plus the existing fact prerequisites. Incomplete or unresolved coverage still permits
useful facts and unresolved criteria to be recorded. The declaration is persisted in
`materiality_evidence_coverage` with semantic verification NOT_ESTABLISHED: these
checks cannot detect a document the model omitted from its missing-document list,
prove economic significance, or independently verify that its declared coverage
is sufficient. This is a research evidence gate, not a strategy approval or changed
threshold. Coverage from v3/v4 is never implicitly promoted to the new status.

#### Offline v6 verification

All 33 saved original outcomes replay unchanged: 17 accepted results reproduce
exactly and 16 failures remain rejected, with unchanged original ledger hashes.
On the latest four saved responses, 55/57 individual selections pass the v6
resolver. The GPT-5.5 KALU headline is uniquely anchored and resolves; the TRUG
ticker label remains ambiguous within its anchor and correctly fails. Mini's
nonexistent KALU handle still fails. No old response or source text was repaired.

Separate derived engineering probes add explicitly author-supplied scope/reason
placeholders to exercise the new schema and final offsets. KALU GPT-5.5 and TRUG
Mini pass those structural probes; the other two fail as above. They are not new
v6 provider responses, corrected historical outcomes or semantic acceptance.
This offline pass makes zero API calls. Original v5 results remain authoritative
for those original requests, including their failures.

#### v7 format corrections and offline verification (September 19, 2026)

The two v6 Mini failures below motivate format-only changes:

- The strict response schema enumerates every selectable excerpt ID from this
  packet. The full packet and catalogue remain identical to v6. Unknown IDs still
  fail local validation, and selecting a known ID does not bypass exact quotation,
  source-field, ambiguity, category or fact checks. The schema is checked against
  the packet before ledger reservation and again during response parsing.
- The provider returns one `missing_documents: [{document, reason}]` list and no
  separate `missing_document_reasons` field. Both compatibility fields in the saved
  coverage record are derived from that single list. The original response is
  retained unchanged. No fuzzy name matching, repair or historical conversion is
  performed. Blank/duplicate documents, blank reasons, missing scope and conflicting
  coverage still fail. Scope, necessary evidence and all substantive v6 requirements
  remain unchanged; a nonempty reason is still not independent semantic verification.

The schema rejects an empty catalogue or the documented enum limits (1,000 total
enum values; over 250 values in a string enum with more than 15,000 characters).
It never trims IDs or packet content to fit. The existing complete-request byte
limit also applies. This can block large packets before dispatch; it is not a
strategy threshold. Limits were checked against [Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs)
on September 19, 2026.

**434 tests passed**, including 31 v7 regressions covering packet-specific schemas,
limit boundaries, rehashed schema tampering before billing, exact source locations,
document/reason consistency, substantive gates, durable replay, and CLI preparation
without credentials or provider calls. All 37 saved provider outcomes retained
their original parsers and results: 19 exact successful replays and 18 rejections.
All seven original ledger files had identical before/after hashes.

The offline v7 implementation pass made zero paid calls. At that point live
compatibility of the new enum schema and fresh model performance were unverified.
The four-request comparison below uses
the same KALU/TRUG development cases, models, 12,000-token output allowance and
250,000-byte input limit; it was prepared separately before dispatch. No passing
offline check establishes semantic acceptance, profitability or trading eligibility.
No database migration is needed for these versioned local JSON records.

#### Fresh v7 provider regression (September 19, 2026)

Four actual-CLI calls completed at runtime commit
`f75ea5357f16d80d6ad69b7c9644968679b84c1d`, with unchanged models, development
cases, limits and transport settings. No retry or response repair occurred.

| Case | Model | Contract result | Exact selections |
|---|---|---|---:|
| KALU | GPT-5 Mini | Rejected: publication metadata used as event evidence | 12/12 |
| KALU | GPT-5.5 | Research draft admitted | 11/11 |
| TRUG | GPT-5 Mini | Research draft admitted | 17/17 |
| TRUG | GPT-5.5 | Research draft admitted | 19/19 |

The provider accepted the new enum schema in all four requests. All 59 selected
quotations resolve exactly, and neither invalid-ID nor duplicate-document-name
failures recurred in this small sample. The three admitted outputs replay exactly.
All 37 earlier outcomes remain unchanged; eight ledgers now contain 41 outcomes
(22 admitted, 19 rejected). These are contract outcomes, not semantic accuracy.

Mini KALU still mistook publication metadata for event time; the existing source
category gate rejected it. It also claimed same-event support using a summary
that lists other stocks and does not mention KALU. Mini TRUG still invented a
universal primary/SEC/partner-document requirement despite passing the contract.
GPT-5.5 preserved conditional financing, limited KALU Tier B scope and unresolved
verification, without the previous unsupported common-share detail. Its TRUG
freshness support is only at the reported-Friday date level, not current approval
or original-scan availability. Its missing-document reasoning also invokes
contingency resolution; the strategy does not universally require an announced
transaction to have closed. Necessity and scope therefore still need semantic review.

Calculated cost: **$0.529519**. Both models used their original limits, and all
four calls recorded 10/180-second transport v2 settings. The existing 434-test
result applies to the unchanged runtime; this follow-up is documentation-only.
No result qualifies a trade, enables unattended operation or establishes strategy
profitability. The cases are development regressions, not independent validation.

#### Fresh v6 provider regression (September 19, 2026)

Four unchanged-limit CLI calls on the previously tested KALU/TRUG cases completed
at commit `baf4a34a01ebc6f36071839796e2c7f2b76a6075`. GPT-5.5 passed both contracts
with 29/29 exact selections, gave a limited Tier B KALU assessment, and kept TRUG
materiality/freshness unresolved. Mini's KALU response still used an invalid ID
three times; its TRUG citations matched, but duplicated document-name fields
differed and failed the required mapping. No repair or retry occurred.

Mini stopped demanding an original note for KALU, but retained unsupported
universal primary/corroborating-document requirements for TRUG. The stronger
model's missing-document reasons were more specific; they are not independently
verified, and its TRUG common-share wording exceeds the article's generic stock
description. All outputs remain research-only and ineligible for handoff.

Calculated cost: $0.4754808 across four calls. This is a development regression,
not independent accuracy evidence. Both admitted results replay exactly. The
403-test result applies to the unchanged runtime; this later update is documentation
only. Additional API tests require checking balance/cost without weakening test
models, cases or limits to fit an insufficient balance.

The five model findings are persisted as `fact_findings` alongside the attributed
review artifact; the original provider response stays in the immutable ledger.
No database migration is needed: these are additive JSON payloads in the existing
local ledger. Nothing writes to trading services, the Journal or a broker.

Regression coverage includes decoded quotation/newline handling, workflow-only
claims, missing exhibits/facts, publication-versus-event timestamps, price/snapshot
misuse, unknown/master IDs, capability violations, catalogue tampering, exact input
size, restart recovery and preservation of v1/v2/v3/v4 histories. Version 4 also covers
wrong-passage support, mixed workflow/document citations, publication-versus-event
use, narrow quote offsets, ambiguity, and useful positive assessments. These isolated tests are
infrastructure fixtures, not trades or strategy observations. Version 5 adds exact
cross-boundary source spans, distinct quotes sharing anchors, repeated source-span
rejection, separate completeness status, missing-document conflicts and useful
research-only outputs with incomplete evidence. It has been checked offline against
saved v4 responses and in a bounded four-call v5 provider regression on MEDS/BIAF.
GPT-5.5 passed both cases; Mini passed BIAF and was rejected for two altered MEDS
quotations. All four declared incomplete materiality coverage and kept materiality
unresolved. This development-informed sample is not independent accuracy evidence
and does not test a real provider's sufficient-coverage conclusion. Two Mini calls
took more than 60 seconds end-to-end using the acceptance transport's 180-second
read timeout. The CLI now defaults to the same 180-second read timeout, configurable
with `--read-timeout-seconds`. This is a socket read timeout, not a total request
deadline or guarantee of success. The client uses a fixed endpoint, ignores ambient
proxy/netrc settings, disallows redirects, and makes no automatic retries. A timeout
keeps the reserved attempt blocked even if a later invocation requests more time.
New calls persist `TRANSPORT_CONFIGURED` with `openai-responses-http-v2` and the
actual timeout settings before dispatch, without credentials. Historical requests
and responses are not relabeled; the v5 research prompt/parser are unchanged.

- The complete text of the three governing masters, with matching document IDs, versions, revisions and content digests. This text comes from a separate authorized document read, not discovery sources or model output.
- Every source in one immutable evidence packet, clearly separated as untrusted data. Source instructions cannot add tools or broker permissions.
- The review criteria and a strict structured-output schema. Model output contains assessments, rationales and exact source quotes only. The program assigns the packet identity, actual returned model, implementation/prompt version, timestamps and trace IDs.

The client supplies no tools, uses a fixed HTTPS endpoint, disables redirects and does not follow evidence URLs. It sets `store=false`, which is not a claim of zero provider retention. Quotes must uniquely match their source; the program calculates offsets. A refusal, truncated/incomplete response, tool output, missing criterion, false/ambiguous citation or extra approval field blocks the result.

Matching citations establish provenance only. A supported claim can still be wrong; all outputs remain `RESEARCH_ONLY`, `eligible_for_handoff=false`, `semantic_verification=NOT_ESTABLISHED`. Existing snapshot approvals are not refreshed. This initial reviewer assesses captured evidence retrospectively and cannot produce prospective confirmation.

### Lossless source encoding

Reviewer implementation `1.1.0-automated-research` / prompt `governed-research-v2` sends each source's complete `text` once. That field already contains the canonical JSON representation of `raw`; sending both duplicated the same evidence. Before omitting the redundant `raw` field from the transport view, the code verifies matching representations, unique source IDs, source digests, and exact reconstruction of every original packet field and its digest. Original packet files, source text, citation offsets, IDs, trace, timestamps, negative evidence and full governing masters remain unchanged. Nothing is summarized, selected by keyword or silently truncated.

Request identity changes with the explicitly versioned encoding. `review_attempts.py` checks the exact version-appropriate evidence message before reserving a call. Supported v1 historical requests/results retain their own implementation and prompt attribution and can recover saved responses without a new provider call. Unknown/mismatched versions fail closed; an existing ledger's call budget is not reset. This is transport compatibility, not acceptance of model accuracy or a change to strategy methodology.

Measured on the September 18 research collection: TEN's request fell from 402,869 to 232,450 UTF-8 bytes, below the existing 250,000-byte limit. After recovering a separate long FEAM filing, its complete request is still 661,821 bytes and remains blocked. Source collection and model-request limits are different; neither is a token count, cost estimate or model-context guarantee. The API continues to receive developer instructions and untrusted user evidence as separate inputs, consistent with [OpenAI text-generation documentation](https://developers.openai.com/api/docs/guides/text).

## Private master manifest

Each entry of the `strategy`, `experiment`, `automation` object has:

```text
document_id, version, revision_id, read_at, text, text_sha256
```

Use the actual full document text, SHA-256 of its UTF-8 bytes and truthful read time. IDs/versions/revisions must match the packet. Re-read changed masters and capture new evidence under their actual revisions; never rewrite old attribution. A digest detects content changes, not whether a supplied export is authentic or complete. The authorized capture process remains responsible for that provenance.

## Prepare without making an API call

The CLI first runs [offline code checks](README-code-review.md). Records with no captured catalyst text are held for evidence retrieval; infrastructure records are excluded from this ordinary research route. Both stop before request preparation or credential access, even with `--dispatch`. For the full funnel, use `run_code_review.py` first. Passing a code check never establishes semantic qualification.

Use the existing development/journal Python environment; this adds no package dependency.

```text
python run_research_reviewer.py --packet PRIVATE_PACKET.json --masters PRIVATE_MASTERS.json --model SELECTED_MODEL_ID --max-output-tokens 6000 --max-input-bytes 250000 --output PRIVATE_OUTPUT
```

The model must be explicitly selected and its availability/cost verified before dispatch. The token/byte values above are infrastructure resource limits, not strategy thresholds. Oversized inputs are rejected rather than silently truncated. Preparation writes a complete reviewable request and makes zero model calls.

## Explicit model test

Supply `OPENAI_API_KEY` through private runtime secret storage. Do not paste it in chat, command arguments, the master manifest, the ledger or git. Append:

```text
--dispatch --ledger PRIVATE_OUTPUT/attempts.sqlite --max-calls 1
```

`--dispatch` permits a potentially billable request. Do not use it before account/model/budget approval. The ledger's fixed call budget persists across restarts; it cannot be silently raised. Output-token limits and byte limits bound each configured request, but this is **not a dollar spending cap**, and a different ledger has a separate budget. Confirm prices and provider-side spending controls separately. No batch of the full discovery funnel is automatically dispatched.

## Attempt history and recovery

The private SQLite ledger uses full synchronous writes and a committed reservation before the HTTP request. A second process cannot send the same request while that reservation exists. A timeout or crash before a durably saved response leaves an unresolved barrier; the program never automatically repeats that request. Failures consume the reserved call slot because provider billing may have occurred.

Received responses are saved before local validation. A restart can validate that saved response without another API call. Completed results are verified against the original saved response and reused. Append-only request/event records preserve prior attribution; no application update/delete operation is offered. SQLite is local private storage, not a multi-host hosted queue or a cryptographic audit service. Do not remove a ledger to bypass an ambiguous-attempt barrier. Resolve it against provider records before explicitly authorizing any new attempt.

The CLI prints only status, IDs, paths and fixed error types. Provider error bodies and credentials are not printed. The ledger/request files contain sensitive strategy/source material and successful provider output, so they require appropriate filesystem permissions and retention controls.

## Independent assessment

`review_evaluation.compare` validates both review artifacts and requires a separately attributed, source-backed reference. It records criterion denominators, agreement/disagreement, model abstentions, unresolved references and supported claims that the reference does not support. It retains both rationales and artifact IDs.

Assessor identity, method version, whether the reference preceded the model response, and independence limitations must be supplied. The comparison rejects self-attribution but cannot verify real-world assessor independence. It introduces no passing percentage. A schema-valid result or high agreement count cannot activate the reviewer.

```text
python review_evaluation.py --packet PRIVATE_PACKET.json --model-result PRIVATE_MODEL_RESULT.json --reference PRIVATE_REFERENCE_ARTIFACT.json --provenance PRIVATE_REFERENCE_PROVENANCE.json --output PRIVATE_OUTPUT
```

The reference uses the existing validated review-artifact format, with exact source-span citations. Provenance fields are `assessor_id`, `method_version`, boolean `created_before_model_response`, and an `independence_limitations` list. A timing declaration that contradicts artifact timestamps is rejected. Reference source truth and independence still require external assessment.

Before acceptance, use the cases in [REVIEW-METHOD-PROPOSAL.md](REVIEW-METHOD-PROPOSAL.md), freeze the source-backed references separately from model outputs, inspect all unsupported positives and disagreements, and preserve unresolved cases. Engineering mocks are not independent semantic assessment, Strategy #1 evidence, trades or retrospective opportunities.

## Verification and remaining work

Run `python -m pytest -q`. Tests use isolated fixtures and mocked provider responses only: full-master binding, source separation, request limits, refusals/incomplete outputs, citation/criterion checks, attribution, concurrency, durable reservation, lost replies, local response recovery and reference comparison. They do not establish provider/model accuracy or live API compatibility.

A live API test still requires a securely configured key, selected model and bounded approved spend. Independent review, current measurement/retrieval adapters, accepted live freshness/review policy, hosted credentials/storage and notification delivery remain outstanding. No production configuration or governing master is changed here.

API contract: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs). Checked September 18, 2026. Runtime compatibility must still be verified against the selected accessible model.
