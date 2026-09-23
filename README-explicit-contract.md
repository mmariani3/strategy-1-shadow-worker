# Explicit rule and economic assertions: offline preview

The v20 comparison exposed gaps that prompt instructions and literal marker
checks cannot fix by themselves. This opt-in preview makes the missing content
explicitly structured: one explained fact link per selected rule, and one cited
core assertion or unresolved reason per economic term.

This is **prepare/check only**, version `1.0.0-explicit-research-contract` /
`governed-research-v21-preview`. It does not replace the v20 default or integrate
with the provider dispatcher. There is no `--dispatch` option. The existing
dispatcher rejects preview requests before reserving a call.

## Contract and validation

The response has three root fields:

| Field | Requirement | Host validation |
| --- | --- | --- |
| `draft` | Complete v20 draft, unchanged in shape | Existing v20 schema, target, source, fact, tier and economic validation |
| `rule_applications` | Exactly one entry for every selected rule: rule number, explanation, fact index and passages | No missing/duplicate/extra rule; nonblank explanation; fact is an evidenced selected-event catalyst; substantive citations must already belong to that fact |
| `term_assertions` | Exactly one entry for every term: index, status, statement, passages and reason | No missing/duplicate/extra term; RECORDED needs nonblank statement and substantive citations; UNRESOLVED needs empty statement/passages and a nonblank reason |

The core assertion belongs in its own field even when its meaning appears elsewhere
in the answer. A qualitative plan can be recorded without inventing an amount.
An unresolved rule mapping selects no rules and has no rule applications; an
unresolved economic assertion is retained explicitly. These infrastructure
requirements do not force a category, value, trade or new strategy threshold.

Full request validation reconstructs and verifies the exact inherited v20 request,
then checks the preview instruction and schema additions. Complete source input,
governing masters, caller-selected model and 12,000/250,000 test limits are retained.
Oversize preparations fail without truncation. Optional documents stay optional.

The validator returns `STRUCTURE_VALIDATED_REVIEW_REQUIRED`, never approval.
Its report retains the original response text, full extended draft, draft digest,
original economic entries, governing rules, linked facts, complete selected source
wording and structured trace IDs. It does not edit an answer or reclassify an old
provider outcome. All reports remain `INFRASTRUCTURE_EVALUATION` with
`eligible_for_handoff=false` and `semantic_acceptance=NOT_ESTABLISHED`.

## What remains unresolved

Nonblank explanations may still be generic or false. A cited passage can be real
yet fail to support its statement. A core statement can describe the wrong term,
and qualifications can still be omitted. Local tests explicitly demonstrate that
structurally valid nonsense remains review-required. This is not an automated
truth classifier, independent source review or proof of improved model accuracy.

The full preview report is required for review. Existing v20 audit/review tools
do not accept the wrapper automatically. Any future provider integration must
preserve the complete wrapper in the attempt ledger and update review/presentation
tools before use. Do not send a projected v20 draft as though it were the complete
preview response, or route a preview through an old parser by relabeling it.

## Offline commands

Prepare a request without sending it:

```text
python research_explicit_contract.py prepare --packet packet.json \
  --masters masters.json --model gpt-5-mini --max-output-tokens 12000 \
  --max-input-bytes 250000 --output reports
```

Validate a response-text file against its exact prepared request:

```text
python research_explicit_contract.py check --packet packet.json \
  --request explicit-request.json --response-text response-text.json --output reports
```

Both commands write immutable, content-addressed files. Neither reads a key or
calls a provider. Original drafts are not automatically extended: tests use
clearly authored synthetic infrastructure fixtures, not repaired model answers.

Run regressions with `PYTHONPATH=.deps python -m pytest -q` using the appropriate
environment-variable syntax for the shell. Coverage includes exact item sets,
blank fields, wrong fact roles, unrelated/metadata/unknown/duplicate citations,
strict index types, tampered inputs, unresolved states, source wording, unchanged
historical behavior, input limits and dispatcher rejection before reservation.

## Boundaries and changed files

Offline preservation/preparation results:

- **976 tests passed in 218.08 seconds**, including **36 new contract regressions**.
  The targeted contract suite also passed independently (36 tests in 51.54 seconds).

- All **117 original outcomes replay exactly**: 56 research admissions and 61
  rejections. All 22 original ledgers and prior artifact/helper hashes match.
- **18 full requests prepared and verified, none sent**, ranging from 162,964 to
  231,152 bytes. Four preparations (FSI and KDP, both models) exceed 250,000 bytes
  and remain blocked without truncation. FSI newly exceeds the limit because of
  the added contract; KDP was already blocked. No larger limit was assumed.
- All 756 internal schema references across the 18 requests resolve locally.
  This check does not establish provider acceptance of the schema.
- Live revision IDs for all three governing masters matched their stored full text
  before new preparation. Original provider outputs were not augmented or repaired.

Preservation/preparation manifest:
`3545896e978a168a601f675c068c524833bcde6698c30910c15e6a9510b08577`.

Code: `research_explicit_contract.py`. Tests:
`tests/test_research_explicit_contract.py`. Documentation: this file and the link
from `README-structure-audit.md`. No migration is required.

Current live master revision IDs matched the stored full masters before offline
preparation. Historical outcomes use their own frozen authorities. No Strategy
v0.3, Experiment v0.5, risk, eligibility, synced source or Journal changes.
Phase 1 SHADOW and disabled broker execution remain repository boundaries.
Live runtime configuration and Journal state were not checked. No paid provider
response has used this preview; provider schema acceptance is not yet verified.
