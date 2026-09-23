# Declared condition and context roles (v23)

## Problem and behavior

The [preserved v22 ADMA answer](README-field-provider.md) passed structural
validation while treating causal attribution as a realization condition. It also
labeled forecast attribution as an occurred event and a demonstrated result as
an expectation. More instructions did not prevent these errors.

Opt-in v23 adds a required `meaning_contract` to the complete existing response.
It declares the role of every condition entry and context note, and the authority
scope of every proposed document follow-up. Contradictory declared roles fail
closed. Source text, original responses and economic content remain reviewable.

**This checks declared consistency, not source truth.** A model can still label
an incorrect statement consistently. Neither schema acceptance nor a recorded
assessment establishes semantic acceptance or trading eligibility.
[Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs)
also distinguishes schema conformance from content mistakes.

## Corrections and limits

| Finding | Change | Regression evidence | Remaining limitation |
| --- | --- | --- | --- |
| Attribution/caution recorded as a condition | Require the role, prerequisite, dependent outcome, matching passages and reason. Non-dependencies cannot occupy conditions. Missing conditions stay unresolved. | Four non-dependency roles, blank prerequisites, missing/duplicate declarations and source mismatches rejected; preserved ADMA counterexample exercised offline. | A falsely declared dependency still needs source review. No keyword truth detector. |
| Prospective condition labeled occurred | Condition temporal scope must match its existing time basis. Completed, prospective and atemporal conditions remain representable. | All three compatible pairs accepted; contradictory time labels rejected. | The declared scope can itself be wrong. All temporal clauses still require review. |
| Reported result labeled expectation; caution labeled counterevidence | Context roles must match categories. Reported results belong in facts/economic terms; forecasts remain expectations; generic caution uses causal-limit context. | Both contradictions rejected; genuine forecast and observed-counterevidence declarations remain possible. | Placement must not discard facts. Completeness and source truth still need review. |
| Optional follow-up wording could waive verification | Every follow-up declares `GOVERNING_MASTERS_UNCHANGED` and explains scope. | Missing/out-of-range follow-ups and incompatible policy values rejected; complete prose included in review. | A constant cannot prove the prose respects policy. Governing masters control verification. |
| New checks could alter history | Separate opt-in version; exact original wrapper/text retained. Internal projections are validators only. | Original identity, source preservation, version attribution, retries, failed-response retention and attributed review tests; full historical replay. | No real v23 provider acceptance or output quality has been demonstrated. |

## Contract and changed files

Versions: `1.22.0-automated-research` / `governed-research-v23`.
The root retains `draft`, `rule_applications` and `term_assertions`, adding:

- `meaning_contract.conditions`: exact `(term_index, entry_index)` coverage,
  declared role, prerequisite, dependent outcome, temporal scope, matching
  passage numbers and reason. Unknown conditions require no invented entry.
- `meaning_contract.contexts`: exact `context_index` coverage, role, matching
  passages and reason. A standalone reported result belongs in existing facts or
  economic terms rather than an expectation note.
- `meaning_contract.followups`: exact `followup_index` coverage, governing-policy
  preservation and scope note. Extra research documents cannot waive required
  catalyst/watchlist verification.

Indices are strict integers. `research_roles.py` implements request preparation,
binding, consistency checks and the review inventory. `research_reviewer.py`,
`review_attempts.py` and `evidence_review.py` register the opt-in version. Request
tampering fails before reservation/provider access, including nonpositive output
limits. Oversized input fails without truncation.

`research_field_review.py` exports and records v23 decisions for every condition,
facet reason, temporal clause, declaration, context note and document follow-up.
The full original provider envelope, text, wrapper, usage and versions remain.
New reports/assessments use `1.1.0-condition-context-review`; historical v21/v22
reports retain their exact outputs and attribution. Its existing CLI is read-only:

```text
python research_field_review.py --ledger attempts.sqlite --request-id ID --packet packet.json --reference reference.json --output reports
python research_field_review.py --ledger attempts.sqlite --request-id ID --packet packet.json --reference reference.json --assessment assessment.json --output reports
```

The recorder rejects missing, duplicate, stale and incorrectly bound decisions.
Even an all-supported assessment retains `semantic_acceptance=NOT_ESTABLISHED`
and `eligible_for_handoff=false`. It never modifies original admission/history.

No automatic provider entrypoint or credential loading is added. The research CLI
still defaults to v20. Explicitly supplied providers may use v23 through the
opt-in runner with existing one-attempt protections.

## Verification

- **1,054 tests passed in 860.32 seconds**, including **28 new regressions**.
  The focused file also passed separately. All 102 tested Python source hashes
  remained unchanged during the full run; its complete output is retained.
- All **121 outcomes replay exactly: 59 research admissions / 62 rejections**,
  across 25 unchanged ledgers. Prior source, output and review hashes match.
- The complete v22 ADMA report and attributed assessment regenerate exactly.
- Three full v23 requests prepared, **none sent**: 147,846-189,718 bytes, under
  the unchanged 250,000-byte input ceiling and 12,000-output-token maximum. Each
  reconstructs its original v22 request exactly; prior judgments are not inputs.
- All three living-master revisions matched their stored complete texts.
- Zero paid calls and zero credential access in this step.

Replay/fixture manifest:
`39d5957d41440daac63eff19bc802f12129106859a5a6622e813d59ee33d5e01`.
Full-suite result manifest:
`5e6508d7a33624be85ee6eda2155d328eb595571c5e36062554c35a0cc5c9075`.

The private source exercise preserves the full v22 answer and creates separately
labeled **author-constructed infrastructure examples**. Explicit causal, result
and caution annotations reproduce rejection. A separate corrected example passes
structural checks while retaining identical core economic assertions and evidenced
facts. This is not model output, repaired history or measured model improvement.

Reproduction:

```text
python -m pytest -q tests/test_research_roles.py
python -m pytest -q
```

## Boundaries and next evidence

No merge, deployment, execution enablement, Journal writes, synced-source edits,
migration, Strategy v0.3 or Experiment v0.5 methodology/risk/setup/trigger/stop/
target/eligibility changes. Phase 1 SHADOW and broker-disabled repository boundaries
remain. Live runtime configuration and live Journal state were not verified.

The next evidence step, if authorized, is a bounded v23 provider test followed by
source review. New API schema acceptance, output-token sufficiency and source
quality remain unverified. Existing test limits have not been reduced.
