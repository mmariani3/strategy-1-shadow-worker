# Condition and forecast field review

The preserved ADMA answer passed structural validation but put forecast
classification in a recorded condition and combined occurred/forecast content
under one occurrence label. This change adds opt-in v22 instructions and an
attributed, source-bound review of every condition facet, facet explanation and
temporal clause. Historical answers are never repaired or rescored in place.

## What changed

| Finding | Change | Remaining limit |
| --- | --- | --- |
| Forecast classification mistaken for a condition | Conditions must describe a source-disclosed dependency of the particular term. Forecast classification/caution goes in qualifications. Undisclosed conditions remain unresolved with empty entries. Each condition facet receives a review item. | Software checks structure and records supplied judgments; it cannot prove that prose states a genuine dependency. |
| Mixed occurred and future content in a summary | Keep occurred-event clauses separate from forecast benefits. General support does not permit `FORECAST_PERIOD`; preserve future benefits in a forecast economic term and its timing entries, core assertion and qualifications, with expectation context where needed. Every temporal clause is inventoried, including materiality summaries. | A schema-valid label can still be semantically wrong and requires source review. |
| Imprecise denominator/unknown wording | Explain missing absolute baseline quantities separately from an already-disclosed comparison basis. Do not invent hypothetical prerequisite classes. Review every facet explanation alongside its entries. | Correct source meaning still needs an attributed assessment. |
| Manual findings previously required a bespoke private report | New read-only export and assessment recorder bind an exact complete set of field decisions to original values, source passages, reviewer identity and timestamps. Revisions and unresolved decisions remain visible. | This focused review does not replace the existing rule, assertion, completeness and other source checks. |

## Version and compatibility

- New opt-in route: `1.21.0-automated-research` / `governed-research-v22`.
- The complete v21 response schema, full source/authority inputs and limits are
  retained. No incompatible forecast enum is added to general support clauses.
- v21, its preview, all older request paths and the v20 CLI default remain frozen.
  Exact suffix, digest, schema, authority and evidence validation occurs before
  dispatch reservation. Internal v21 projections are validators only, never
  provider answers or rewritten historical requests.
- The original full answer and current version attribution remain in the
  research result. Its condition/timing checklist starts `SOURCE_REVIEW_REQUIRED`.
- The new review exporter accepts original v21 and v22 records. The older v21
  exporter continues producing its exact historical output.
- No automatic provider entrypoint, credentials, migration, production change,
  merge or deployment is introduced. An explicitly supplied provider can still
  call the opt-in route through the existing runner.

## Review behavior

The field report contains all original source text and provider output, existing
rule/term/anchor checks, and these additional items:

1. Each complete condition facet, including an unresolved or not-applicable one.
2. Every amounts/conditions/timing/qualifications explanation alongside its entries.
3. Every statement carrying a temporal basis anywhere in the full answer.

The assessment recorder rebuilds the report from its original inputs. It requires
one decision for every field item, with the exact value digest, named assessor,
assessor kind, valid review time, rationale and substantive source selections.
Missing, duplicate, stale, unknown-source and metadata-only decisions fail closed.

- Any `REVISION_REQUIRED` decision yields `REVISIONS_REQUIRED`.
- Any `UNRESOLVED` decision, or an empty field inventory, retains `SOURCE_REVIEW_REQUIRED`.
- Only a complete set of supported judgments yields `FIELD_REVIEW_RECORDED`.

Even the last status means only that the assessor's judgments were recorded.
Every result remains `semantic_acceptance=NOT_ESTABLISHED`,
`eligible_for_handoff=false`, and `INFRASTRUCTURE_EVALUATION`. Software does not
certify assessor independence or truth. The original admission is unchanged.

## Offline use

```text
python research_field_review.py --ledger attempts.sqlite --request-id ID --packet packet.json --reference reference.json --output reports
python research_field_review.py --ledger attempts.sqlite --request-id ID --packet packet.json --reference reference.json --assessment assessment.json --output reports
```

The first command exports immutable JSON and escaped, inert HTML. The second
also records the supplied assessment as a new artifact. Both open the attempt
ledger read-only, verify its completed original response and make zero API calls.
Failed, incomplete or inconsistent histories cannot be presented as completed.

An assessment contains `report_id`, `assessor_id`, `assessor_kind`, `reviewed_at`,
`limitations`, and `decisions`. Each decision contains `item_id`, `value_digest`,
`finding` (`SUPPORTED`, `REVISION_REQUIRED`, `UNRESOLVED`), `rationale`, and
`source_numbers`. These are review judgments, not self-asserted model approval.

## Validation and evidence

`tests/test_research_fields.py` covers frozen-request reconstruction and limits,
version attribution, complete original-answer retention, retry safeguards,
tampering before provider access, all-field coverage, immutable source/value
bindings, unresolved decisions, rejected histories, offline CLI operation,
escaping, and report regeneration.

Synthetic counterexamples represent the preserved semantic defects. Tests verify
that attributed revision findings survive and cannot become approval. Separate
synthetic corrected examples move future benefits into supported forecast fields
without dropping them. They are not repaired provider responses and do not
measure real model performance. No strategy thresholds are introduced.

Full test and historical replay results from implementation are recorded below.
The subsequent [bounded v22 provider test](README-field-provider.md) established
API acceptance but retained source-meaning defects; general output reliability
has not been established.

## Changed files and boundaries

New `research_fields.py` implements the opt-in instructions, exact request binding
and complete field inventory. New `research_field_review.py` exports/records
attributed field review. `research_reviewer.py`, `review_attempts.py` and
`evidence_review.py` register the new version. The new regression file and this
document describe the behavior and limitations.

No Strategy v0.3 or Experiment v0.5 methodology, risk limits, setups, triggers,
stops, targets or observation eligibility changes. Synced sources and Journal
state are untouched. Phase 1 SHADOW and broker-disabled repository boundaries
remain; live runtime configuration and live Journal state were not verified.

## Completed verification

- **1,026 tests passed in 721.27 seconds**, including the **22 new regressions**.
  The focused file also passed separately. The full run retained its output and
  verified that every tested Python source hash stayed unchanged during the run.
- All **120 saved outcomes replay exactly: 58 admissions / 62 rejections**, with
  all **24 ledger hashes** and prior source/review artifacts unchanged.
- The original ADMA answer yields **42 field items**. A post-output
  implementation-author assessment records **four overlapping revision items**
  covering its condition facet, mixed temporal clause and imprecise wording.
  This is explicitly attributed author review informed by the preserved separate
  source-first assessment; it does not become independent review through software.
- Three complete v22 requests were prepared, **none sent**. Sizes are
  142,588–184,458 bytes under the unchanged 250,000-byte input ceiling; output
  allowance remains 12,000 tokens. Each internal v21 request exactly matches its
  original. Model answers and reviewer judgments are not inserted into requests.
- The three current living-master revisions matched their full stored texts.
- **Zero API calls and zero credential access** in this implementation step.

Offline replay and field-review manifest:
`7acc414d4fea4ddda774ad5786e372028fcff3ec2028eff366878aae822112e6`.

Reproduce with the repository's existing test environment:

```text
python -m pytest -q tests/test_research_fields.py
python -m pytest -q
```

The subsequent [bounded v22 test and source review](README-field-provider.md)
preserves the first real answer and its remaining revision findings. Passing
offline tests does not establish correct real model output.
