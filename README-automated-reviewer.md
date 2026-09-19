# Automated research reviewer

This implements an opt-in OpenAI Responses API client for the packets in [PR #5](https://github.com/mmariani3/strategy-1-shadow-worker/pull/5). It can request a substantive, source-cited research assessment and compare its claims with a separately supplied reference. **It cannot qualify candidates, refresh live approvals, confirm triggers, establish experimental observations or enable execution.**

Phase 1 remains SHADOW. Strategy Rules v0.3 and Experiment Plan v0.5 are unchanged. The review method remains a proposal pending independent semantic assessment and acceptance in the governing Automation Specification. No model/provider subscription, credential, hosted service, live retrieval or deployment is provisioned by this change.

## What the reviewer receives

### Default CLI: factual research v4

The CLI now prepares `1.3.0-automated-research` / `governed-research-v4` requests
through `research_citations.prepare_selection_request`. The old `research_reviewer.prepare_request`
and `research_facts.prepare_fact_request` functions remain explicit v2 and v3 compatibility APIs; old requests/results retain their
original parsers and attribution. No historical output is upgraded or relabeled.

Versions 3 and 4 first ask for five source-backed findings: instrument identity, catalyst
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

Version 4 requires each citation to contain a stable excerpt ID and a verbatim
`supporting_text` clause copied from that excerpt's decoded readable text. The host
checks that the clause actually occurs in the selected excerpt and uniquely in the
original source, then persists its precise encoded quotation and source offsets.
It rejects empty, ambiguous and mismatched selections without repair. Workflow and
market-snapshot fields remain in the complete packet but have no selectable handles.
Publication metadata can support publication facts only. Version 3's gates remain
in force for v4. These checks detect incorrect attribution, **not** whether a real
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

The five model findings are persisted as `fact_findings` alongside the attributed
review artifact; the original provider response stays in the immutable ledger.
No database migration is needed: these are additive JSON payloads in the existing
local ledger. Nothing writes to trading services, the Journal or a broker.

Regression coverage includes decoded quotation/newline handling, workflow-only
claims, missing exhibits/facts, publication-versus-event timestamps, price/snapshot
misuse, unknown/master IDs, capability violations, catalogue tampering, exact input
size, restart recovery and preservation of v1/v2/v3 histories. Version 4 also covers
wrong-passage support, mixed workflow/document citations, publication-versus-event
use, narrow quote offsets, ambiguity, and useful positive assessments. These isolated tests are
infrastructure fixtures, not trades or strategy observations.

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
