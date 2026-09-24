# v20 fresh-source provider comparison

Follow-up: [offline declaration and sparse-entry checks](README-structure-audit.md)
now detect the two structural patterns in these unchanged answers without API calls.

## Result

Two complete provider calls on one new historical primary-source document passed
the technical parser. Source review still requires work: Mini repeated unsupported
rule selections and citation/qualification defects. GPT-5.5 selected the acquisition
rule alone and preserved timing and major deal risks, but two sparse economic
entries remain unresolved. Neither answer is approved for qualification or handoff.

| Model returned | Input / output tokens | Usage-derived cost | Technical result | Attributed meaning review |
| --- | --- | --- | --- | --- |
| gpt-5-mini-2025-08-07 | 41,370 / 9,540 | $0.02942250 | Research draft available | REVISIONS_REQUIRED |
| gpt-5.5-2026-04-23 | 41,370 / 7,027 | $0.41766000 | Research draft available | REVIEW_REQUIRED |

Total **$0.44708250**, two calls, no retries, no repair calls. Output usage includes
reasoning tokens; no cached-input discount was reported. Prices checked against
the official [Mini](https://developers.openai.com/api/docs/models/gpt-5-mini) and
[GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5) pages: respectively
$0.25/$2 and $5/$30 per million input/output tokens. Conservative pre-dispatch
allowance was $1.41973450. No tests or source text were shortened to fit credits.

## Frozen design and authority

- Capture: complete [Salesforce/Informatica announcement filed as Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1108524/000119312525126271/d866821dex991.htm), dated May 27, 2025. CRM buyer scope, historical extraction only.
- Eight source anchors and their expectations were fixed before outputs. Complete
  captured text was checked for exact-body overlap with the prior corpus.
- Current Strategy v0.3, Experiment v0.5 and Automation v0.4 live revisions matched
  the full stored masters before preparation. Those full masters are bound into
  both requests; synced source files were not edited.
- Runtime: local `9e9fd5729a5566d6f46c8662719fc7804fe03763`, equivalent GitHub
  `c656817d2ca38d2d80bad4debe7b4876f164dac2`, tree
  `33ed59e8e2708d4c614d634ea064a7320686abb7`.
- Implementation `1.19.0-automated-research`, prompt `governed-research-v20`;
  unchanged v19 schema and 12,000 output-token / 250,000 input-byte limits.
  Actual request sizes: 178,238 and 178,235 bytes. No truncation or substitutions.
- Synthetic local adapter remains `INFRASTRUCTURE_TEST`, classified by the normal
  routing check as `EXCLUDED_INFRASTRUCTURE`. Candidate, signal and journal-trade
  IDs stay null; original synthetic run ID persists. The isolated harness does
  not run production discovery or write the Journal.

Exact capture HTML SHA-256:
`52a71c75aa01227e692f0ab291f80d00a881b6e3e8a22cae4081763c8a8cfc18`.

## Source-review findings

| Finding | Mini | GPT-5.5 | Remaining work |
| --- | --- | --- | --- |
| Individual rule meaning | Selects all six Tier A rows. Earnings surprise, customer win, issued regulatory decision and industry shock are unsupported. Strategic-category explanation unresolved. | Selects acquisition rule 75 only, with event-specific explanation. | Prompt instructions alone do not prevent unsupported Mini selections. Do not auto-approve a valid tier label. |
| Event/publication timing | Retains announcement date without calling the next-day conference call its publication time. | Explicitly separates dateline, unavailable clock time and future call. | One historical date example does not validate prospective freshness. |
| Terms and citation continuations | Meaning of headline value/consideration mostly retained, but selected passages omit necessary continuations for net value, closing conditions and consent. Financing-risk statement lacks its specific source selection. | Preserves full adjacent support for principal terms. | Per-assertion source completeness still needs review. |
| Scoped downside | Generic uncertainty omits relevant fee, litigation and transaction-cost consequences; requesting later filings does not preserve already disclosed risks. | Retains broad deal downside and relevant continuation text. | Importance remains an attributed scope judgment, not a keyword threshold. |
| Economic inventory | One combined term also carries citation/qualification defects. | Capital-return and market-position entries have labels and generic caution but no substantive expectation entry. Capital-return expectation is preserved elsewhere in the answer. | Two structured entries are unresolved, not alleged whole-answer omissions or false assertions. |

Each answer has 17 meaning-review items. Mini records 10 revision items and one
unresolved item; GPT-5.5 records zero revision items and two unresolved items.
These counts overlap across rules, terms and source anchors: **they are not unique
defect counts, accuracy scores or a model leaderboard**. Review version remains
`1.0.1-source-meaning-review`. Every judgment retains author attribution, time,
exact draft paths/hashes and source passages. Original answers were not repaired.

The Mini answer also asks for fuller agreement/financing documents than its narrow
announced-terms question requires, and describes later filings as independent
corroboration. These are unapproved research followups, not new strategy gates.
The stronger answer treats further filings as optional context. Neither establishes
independent same-event corroboration or live catalyst eligibility.

## Verification and reproduction

- All **117 outcomes replay exactly: 56 research admissions / 61 rejections**.
  This includes the unchanged 115 earlier outcomes (54 admissions / 61 rejections).
- All 21 earlier ledger hashes, prior frozen artifacts and previous implementation
  helpers match. The new ledger makes 22 retained ledgers.
- Exact-body overlap check covered 296 prior packet files, with no match.
- Both new source-location audits, omission reports, meaning dossiers, assessments,
  reviews and saved HTML regenerate exactly, including assessment serialization.
- Prior implementation test result remains **920 passed, 44 new regressions**.
  This comparison changes documentation only; the full suite was not rerun.
- No paid call is needed to replay stored responses or re-run the review CLI in
  [README-meaning-review.md](README-meaning-review.md). Preserve original draft
  ordering for historical report compatibility. The private campaign folder
  `semantic-comparison-20260922` retains plan, complete sources/masters, original
  requests/responses, usage, ledger, reviewer decisions and evidence manifests.

Verification manifest:
`463a2d431455a22aeea65ec0917ef6782ba766d1d654bf7211d953292b2c0015`.
Author-review manifest:
`f450804c1188ce189b0c409b9faedef10681f2d84f5703fc5577b1a2f815b3c4`.
- Browser visual inspection is not claimed. HTML structural/escaping and exact
  saved-file regeneration checks passed; the earlier local-file preview policy
  restriction remains.

## Limits, credits and next step

This is one historical convenience document, with no same-document v19 control
and an implementation-author review. It is new to the local evaluation corpus,
not necessarily new to model training. The result cannot establish representative
accuracy, causal prompt improvement, unattended qualification or profitability.
The v19 answers and every earlier failure remain preserved.

Billing showed $2.39 before and after the test, with auto-reload off; the display
had not reflected this spend. The conservative usage-derived remaining estimate
is **$1.92444825**, not an exact verified account balance. No purchase or billing
setting changed. Verify credits before another paid batch; do not reduce test
coverage to stretch the balance.

Next work should address individual-rule explanations and incomplete structured
economic entries with targeted offline checks, followed by a separately budgeted
evaluation if needed. Do not treat this comparison as deployment acceptance.
The 18 previously prepared v20 historical requests remain unsent; KDP still exceeds
the unchanged complete-input limit.

No strategy/experiment methodology, observation eligibility, risk limit, source
master, Journal, runtime configuration or deployment changed. Phase 1 SHADOW and
disabled broker execution remain repository boundaries. **Live runtime configuration
and Journal state were not checked.** PR #9 remains a stacked, unmerged draft.
