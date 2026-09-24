# v21 paired provider retest — September 23, 2026

The integrated explicit-response format was sent once to GPT-5 Mini and once to
GPT-5.5, using the same full historical Salesforce/Informatica source and original
packet used by the prior v20 comparison. **GPT-5.5 produced a structurally valid
research draft whose targeted source checks were supported by the implementation
author. Mini was rejected and still misrepresented several strategy rule meanings.**

This is infrastructure evaluation, not Strategy #1 evidence or approval for
unattended qualification. No trade, execution, Journal entry, production change,
merge or deployment resulted.

## Frozen inputs and limits

- Full [May 27, 2025 SEC Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1108524/000119312525126271/d866821dex991.htm), CRM buyer scope, original captured text preserved.
- Original infrastructure packet and eight source anchors from the v20 comparison.
  The anchors were originally written before v20 outputs; this v21 test is
  deliberately a repeat of a case used to design the new contract.
- Current live revision IDs of Strategy Rules, Experiment Plan and Automation
  Specification matched the stored complete masters before preparation.
- Runtime: local commit `175dc9ca890e3816af541d2c9ec0aa229a27752d`, identical tree
  `0fddbdf46bfb1a0347a09dc8c76c0b882cb65a87` to GitHub commit
  `f008282bae341486609fa3f26c93bd9872017d13`.
- `1.20.0-automated-research` / `governed-research-v21`; two isolated calls,
  12,000 maximum output tokens and 250,000 maximum input bytes. Requests were
  181,399 and 181,396 bytes. No truncation, retries, repairs or extra paid calls.
- Each internally reconstructed v20 request exactly matches its earlier request.
  Previous model outputs and reviewer judgments were not sent to either model.
- Conservative allowance $1.43632975, within the disclosed $1.44 campaign budget.
  The live billing page showed $1.94 before dispatch; a lower usage-derived
  estimate was used for the budget check. Auto-reload remained off.

## Results and reported usage

| Model returned | Input tokens | Output tokens | Calculated cost | Original result |
| --- | ---: | ---: | ---: | --- |
| `gpt-5-mini-2025-08-07` | 41,961 | 11,278 | $0.03304625 | Rejected: `EMPTY_ECONOMIC_TERM` |
| `gpt-5.5-2026-04-23` | 41,961 | 8,483 | $0.46429500 | Research draft available; never eligible for handoff |
| Total | | | **$0.49734125** | Two provider-completed responses |

Both APIs accepted the new request schema and returned completed responses. API
completion is distinct from host validation and source correctness. Costs use
reported usage and the rechecked official [Mini](https://developers.openai.com/api/docs/models/gpt-5-mini)
and [GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5) rates; cached input was zero.

### Mini: failed outcome retained

The embedded new-debt term has no entries in any of its four facets, so the
existing validator rejects it. The explicit unresolved assertion does not cure
that empty embedded placeholder. Supplemental inspection also found three rule
applications citing passages absent from their referenced catalyst fact. These
later diagnostics do not change the original first failure.

The source review found a substantive failure beyond the structure error:
Mini selected rules 72–77 and invented acquisition-related meanings for several.
For example, it called rule 72 an acquisition category, although the governing
rule is earnings/guidance surprise. It similarly treated payment, board and
shareholder mechanics as support for customer-win, regulatory-decision and
industry-shock categories. Rule 75's underlying acquisition category is supported;
the other claimed mappings cannot inherit that support.

The answer also omitted citation continuations for net equity value, closing
conditions and no-further-stockholder-action language. Generic caution did not
preserve disclosed termination-fee, legal-proceeding, transaction-cost and
financing downside relevant to its chosen scope. These defects were neither
repaired nor hidden by the failed parser outcome.

### GPT-5.5: targeted author checks supported

- Selects rule 75 alone and explains the actual acquisition category using its
  selected-event catalyst fact and the correct passages.
- Retains net equity value, specified stock classes and cash-per-share
  consideration, conditional expected close, already-delivered consent and
  future funding without inventing lender commitments.
- Supplies a separate funding assertion citing the cash-plus-new-debt plan.
  Unknown financing terms stay unresolved.
- Records the capital-return expectation explicitly, including its source
  passage, instead of leaving only a label and generic caution.
- Records strategic integration and market-position claims as forecasts,
  distinguishing market size from Salesforce revenue and preserving integration risk.
- Keeps May 27 publication/dateline evidence distinct from the May 28 scheduled
  earnings call and retains non-GAAP, forecast and deal-risk qualifications.

The attributed checklist contains 30 Mini items and 22 GPT-5.5 items. Mini has
21 revision-marked items and two unresolved items; GPT-5.5 has no revision or
unresolved finding in these targeted checks. Items overlap, and these counts
are **not accuracy rates or independent acceptance scores**.

## Evidence integrity and remaining limits

Original provider envelopes, exact answer text, complete wrappers, failures,
trace IDs, request versions, source passages and author judgments are stored
separately in immutable local artifacts. The failed Mini response remains
failed; no successful export was fabricated for it. Its supplemental review
explicitly preserves the failed admission.

All **119 saved outcomes replay as recorded: 57 research admissions and 62
rejections**. The original 117 outcomes are unchanged, and all 23 ledger hashes
match. Preservation/review verification manifest:
`7bf41db455f4decd05303a5d75e281f8ee0e8a31b35fec257e11e78ed8b5ea65`.

GPT-5.5's read-only ledger export includes all 22 review items, full captured
sources, continuations and the original response. JSON round trips and HTML
regeneration match. All author evidence paths and selected passages are bound
to the unchanged original draft and source. Browser visual/mobile usability was
not verified.

This is one historical convenience case, one response per model/version, and
review by the implementation author with prior-output exposure. It is not
held-out evidence, does not isolate causal improvement from sampling, and
cannot establish general reliability or profitability. Both results remain
`INFRASTRUCTURE_EVALUATION`, `eligible_for_handoff=false`, with independent
semantic acceptance not established. Fresh-source and separate review remain
necessary before broader reliability claims.

No runtime code changed in this provider-test step. The previously verified
1,004-test suite is unchanged. Live production configuration and Journal state
were not inspected. Phase 1 SHADOW and disabled broker execution remain the
repository boundaries; Strategy v0.3 and Experiment v0.5 methodology is unchanged.
