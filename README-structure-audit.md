# Offline checks for research declarations and sparse entries

The v20 comparison showed two mechanically detectable gaps: Mini selected six
rules while explaining only an acquisition in general terms, and GPT-5.5 created
two economic entries without recording their core expectation. The new standalone
`research_structure_audit.py` flags these patterns on saved v20 answers.

It produces a separate immutable report. It does not change the provider prompt,
schema, parser, original admission, answer or attributed source review.

## Checks and limits

| Check | Behavior | What it cannot establish |
| --- | --- | --- |
| Individual rule declaration | Every selected rule is checked for its explicit `rule N` or `rule #N` marker in the explanation. Each row retains the original explanation, matching offsets and governing rule. | A marker can occur in a quote, negation or generic explanation. Presence does not establish an individual justification or supported rule. |
| Unresolved mapping | An empty/unresolved mapping stays an explicit review item. | The audit never chooses a tier or forces a proposal. |
| Sparse economic entry | Flags a term with zero entries across amounts, conditions and timing, even if it has a label and generic qualifications. | It does not claim the entire answer omitted the fact. Unknown amounts alone are not flagged when another core facet records the plan. |
| Evidence binding | Existing dossier validation checks exact request, source, reference and draft structure. Invalid source selections remain visible and keep the report in review status. | Binding is not semantic correctness. An irrelevant core entry can evade the sparse-entry check. |
| Evidence preservation | Original draft hashes, request/prompt versions, scope, trace IDs and complete checked values remain in a content-addressed report. | No report grants qualification, approval or handoff. |

Declaration matching is deliberately narrow, case-insensitive and integer-specific.
An amount, a number in the rules array, `rule 750` or `rule 75.5` cannot supply a
`rule 75` marker. Lists/ranges are not expanded into individual explanations.
Alternative wording can therefore raise a review flag; this is not a claim that
the explanation is necessarily wrong. v20 explicitly asks for each selected
rule number. Older prompts are rejected by this new audit rather than silently
subjected to that contract.

`REVIEW_REQUIRED` means flags, unresolved mapping or invalid selections were found.
`NO_STRUCTURAL_FLAGS` means only that these narrow patterns were absent. Both
retain `semantic_acceptance=NOT_ESTABLISHED`,
`original_admission=NOT_EVALUATED_OR_CHANGED` and `eligible_for_handoff=false`.
Source-meaning review remains necessary. Do not fill missing data by inference or
turn optional followups into new strategy eligibility rules.

## Saved-answer verification

**940 tests passed in 164.74 seconds**, including 20 new regressions. All **117
saved outcomes replay exactly** (56 research admissions / 61 rejections), with all
22 ledger hashes and earlier artifact/helper hashes unchanged. The two new audit
reports reproduce exactly from saved inputs. No API calls or credentials used.

Private verification manifest:
`7422ebf48815556983ab8bc9acee5ffa23038af84cf5bb39bd2a0b6d2e57964a`.

On the original Salesforce/Informatica v20 answers:

- Mini: six `RULE_DECLARATION_NOT_FOUND` flags. These are missing explicit
  declarations, not six independently established semantic defects. The existing
  attributed review still identifies which selected rules were unsupported.
- GPT-5.5: two `NO_CORE_TERM_ENTRIES` flags, at term indices 4 and 5 (capital-return
  and market-position expectations). The capital-return expectation survives
  elsewhere in the answer; the finding concerns its structured entry.
- Original answers, provider outcomes and attributed review decisions remain
  unchanged. These examples were already seen during development and do not
  establish new model accuracy or independent validation.

## Reproduce without API calls

```text
python research_structure_audit.py --packet packet.json --request request.json \
  --draft original-draft.json --reference reference.json --output reports
```

All four inputs must be the matching saved v20 artifacts. The tool writes
`structure-audit-<report_id>.json`. Identical inputs reproduce the same report;
the existing immutable writer protects a conflicting file. The CLI has no provider,
credential, production-dispatch or Journal-writer path.

Tests: `PYTHONPATH=.deps python -m pytest -q` (set the environment variable using
your shell's syntax). Regression coverage includes numeric collisions, negated
and quoted markers, source/request/reference tampering, malformed draft entries,
sparse terms, legitimately unquantified plans, unchanged admission and repeat CLI
output. Synthetic fixtures are infrastructure tests, not Strategy #1 observations.

## Boundaries and changed files

- Code: `research_structure_audit.py`.
- Regression tests: `tests/test_research_structure_audit.py`.
- Documentation: this file and links in the meaning-review/comparison documents.

New report version: `1.0.0-research-structure-audit`. Existing v20 and meaning-review
versions remain unchanged because their behavior is unchanged. No migration or
production integration is introduced. No API calls, credential access or credit
purchases are needed for this step.

Historical request-bound masters control replay; no current trading decision is
made. Strategy v0.3, Experiment v0.5, synced sources and the Journal are unchanged.
Phase 1 SHADOW and disabled broker execution remain repository boundaries.
Live runtime configuration and live Journal state are not checked by this work.
