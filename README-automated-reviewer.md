# Automated research reviewer

This implements an opt-in OpenAI Responses API client for the packets in [PR #5](https://github.com/mmariani3/strategy-1-shadow-worker/pull/5). It can request a substantive, source-cited research assessment and compare its claims with a separately supplied reference. **It cannot qualify candidates, refresh live approvals, confirm triggers, establish experimental observations or enable execution.**

Phase 1 remains SHADOW. Strategy Rules v0.3 and Experiment Plan v0.5 are unchanged. The review method remains a proposal pending independent semantic assessment and acceptance in the governing Automation Specification. No model/provider subscription, credential, hosted service, live retrieval or deployment is provisioned by this change.

## What the reviewer receives

- The complete text of the three governing masters, with matching document IDs, versions, revisions and content digests. This text comes from a separate authorized document read, not discovery sources or model output.
- Every source in one immutable evidence packet, clearly separated as untrusted data. Source instructions cannot add tools or broker permissions.
- The review criteria and a strict structured-output schema. Model output contains assessments, rationales and exact source quotes only. The program assigns the packet identity, actual returned model, implementation/prompt version, timestamps and trace IDs.

The client supplies no tools, uses a fixed HTTPS endpoint, disables redirects and does not follow evidence URLs. It sets `store=false`, which is not a claim of zero provider retention. Quotes must uniquely match their source; the program calculates offsets. A refusal, truncated/incomplete response, tool output, missing criterion, false/ambiguous citation or extra approval field blocks the result.

Matching citations establish provenance only. A supported claim can still be wrong; all outputs remain `RESEARCH_ONLY`, `eligible_for_handoff=false`, `semantic_verification=NOT_ESTABLISHED`. Existing snapshot approvals are not refreshed. This initial reviewer assesses captured evidence retrospectively and cannot produce prospective confirmation.

## Private master manifest

Each entry of the `strategy`, `experiment`, `automation` object has:

```text
document_id, version, revision_id, read_at, text, text_sha256
```

Use the actual full document text, SHA-256 of its UTF-8 bytes and truthful read time. IDs/versions/revisions must match the packet. Re-read changed masters and capture new evidence under their actual revisions; never rewrite old attribution. A digest detects content changes, not whether a supplied export is authentic or complete. The authorized capture process remains responsible for that provenance.

## Prepare without making an API call

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
