# Offline reference-location review

`research_reference_coverage.py` compares a saved v14–v19 draft's passage selections
with an externally supplied, source-anchored checklist. It makes **zero model calls**
and never reads credentials, changes the saved answer, changes its admission outcome,
qualifies a candidate or writes to trading services. The [default reviewer is now
v19](README-tier-review.md). V14 reports keep their original audit version and
exact output; v15 reports use version 1.1.0, and v16 reports use 1.2.0. V16 audits
inspect the original envelope, including inventory and nested research selections.
Paths retain their `economic_inventory` or `research` prefixes.
V17 audits use version 1.3.0, inspect original paths and validate the root scope.
Historical v14–v16 audits and digests remain unchanged.

V18 uses audit version 1.4.0; v17 outputs also remain unchanged. The separate
`research_omissions.py` report retains full substantive text and exposes uncited,
narrative-only and unindexed source locations for attributed review.

V19 uses audit version 1.5.0 and retains original root/nested paths. V18 outputs
remain unchanged. `research_review_view.py` renders verified omission reports into
local HTML with source/prose columns, navigation and full evidence retention.

This is an evaluation sidecar, not an automatic completeness or accuracy judge.
Its name and statuses describe **locations**, not economic meaning.

## What the check establishes

- Verifies the packet, versioned request digest, prompt/schema/master bindings and draft
  target identity before inspecting selections.
- Verifies each reference's source ID, raw JSON path, exact quote and start/end
  offsets. Computes canonical offsets structurally, including escaped text and
  repeated values; it does not choose a location by searching for matching words.
- Reports `FULLY_SELECTED`, `PARTIALLY_SELECTED` or `NOT_SELECTED` for each supplied
  anchor, and separately whether the anchor was fully/partially/not selectable in
  the existing catalog. Catalog omissions must not be mistaken for model omissions.
- Retains matching model paths/statements, original occurrence IDs, reference
  attribution and input digests. Duplicate/unknown selections are diagnostic flags.
- Writes a new content-addressed report. Every report remains infrastructure-only,
  semantically unverified and ineligible for handoff.

A model can cite a passage and contradict it in prose. It can also paraphrase a
fact while failing to cite the chosen reference occurrence. Therefore full selection
is not a semantic pass, and a missing selection is a review flag rather than proof
of a missing fact or an automatic rejection. The checklist itself may be incomplete;
software does not establish its independence, relevance or governing authority.
No minimum coverage percentage, new strategy rule or required document type exists.

## Usage

```text
python research_reference_coverage.py --packet PRIVATE_PACKET.json --request PRIVATE_V14_REQUEST.json --draft ORIGINAL_DRAFT.json --reference PRIVATE_REFERENCE.json --output PRIVATE_AUDIT_FOLDER
```

`draft` is the original structured model answer, not the provider response envelope
or an edited answer. Accepted and rejected v14 drafts can be inspected if they parse
under the draft schema. This tool does not rerun the admission decision. Unknown
versions or schema-invalid drafts stop explicitly; there is no automatic repair.
The caller must establish provider provenance from its original response/ledger;
an arbitrary supplied JSON file is not authenticated as a model response.

Reference format:

```json
{
  "assessor": "attributed reviewer",
  "at": "2026-09-19T12:00:00+00:00",
  "independent": false,
  "cases": [{
    "packet_id": "actual packet digest",
    "symbol": "actual packet symbol",
    "expectations": [{
      "id": "stable review item",
      "expectation": "The source fact this reviewer wants inspected",
      "source_id": "actual source digest",
      "raw_path": ["text"],
      "start": 0,
      "end": 4,
      "quote": "Text"
    }]
  }]
}
```

Offsets are zero-based character positions in the raw string, with exclusive end.
Keep the reference's original timestamp and attribution. A post-response checklist
must not be presented as a blinded pre-response standard. Sources and originals stay
read-only; use a new output directory for derived infrastructure review artifacts.

## Recorded offline development review

Applied to all four original v14 ABTS/CVI provider answers using the unchanged
pre-response author reference. Original provider-response digests and sixteen ledger
hashes were retained and verified. These are reused development cases, not held-out
or independent acceptance evidence.

| Answer | Fully selected anchors | Partially selected | Not selected |
| --- | ---: | ---: | ---: |
| ABTS / Mini | 3 | 1 | 5 |
| ABTS / GPT-5.5 | 8 | 0 | 1 |
| CVI / Mini | 4 | 1 | 1 |
| CVI / GPT-5.5 | 6 | 0 | 0 |

These counts measure checklist location coverage only. Every supplied anchor was
fully selectable. Both ABTS answers left the reference's noncontingent commitment-fee
passage uncited. Mini additionally missed the specific ABTS conditional-funding,
default-conversion, dilution and document-scope anchors, plus CVI's conditional
warning passage. Some related facts appear elsewhere in its prose or citations;
the report does not label those facts absent solely from anchor coverage.

The prior source review found GPT-5.5's extracted ABTS summary omitted the $7.5M
commitment fee. The sidecar makes its uncited reference clause reproducibly visible.
GPT-5.5/CVI's complete selection of the supplied anchors does **not** establish that
its earnings-category proposal or proposed sales-benchmark prerequisite is correct.
Mini's demand that filings contain the private strategy's tier labels, its primary-
document requirement and its materiality/setup confusion remain semantic findings;
this tool does not pretend to resolve them by word matching.

Validation: **710 tests passed**, including **22 new location-audit regressions**.
Tests cover missing/partial/full selection, deliberately false prose with valid
citations, duplicates, unknown IDs, unselectable legacy text, repeated/escaped
occurrences, request/reference/source tampering and no admission promotion.
All **97 historical outcomes** replay unchanged (43 research admissions, 54 rejections).
No paid requests, production changes, migrations or methodology changes occurred.

## Next review boundary

The [attributed completeness-review stage](README-completeness-review.md) now
records the explicit source/prose judgments below without altering this location
audit or the original model admission. Its results remain infrastructure-only.

Use the flagged passages and corresponding original prose for explicit, attributable
semantic assessment. Decide whether each supplied anchor is relevant to the chosen
scope and whether the answer preserves its meaning and qualifications. Revisions to
an evaluation checklist must retain old versions. Only then consider a separately
authorized comparison on new sources. Neither model is accepted for unattended
qualification, and this report cannot enable it.
