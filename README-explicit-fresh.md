# v21 fresh-source review — September 23, 2026

One GPT-5.5 response on a new historical source passed structural validation.
A separate, source-first AI review supported the central account but identified
two semantic field problems and wording caveats. **This is research evidence
about the software, not approval for unattended qualification or Strategy #1
evidence.** The original answer remains unchanged.

## Frozen test

- Complete [ADMA April 28, 2025 SEC Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1368514/000114036125015881/ef20048038_ex99-1.htm), issuer scope.
  The URL and captured text hash did not occur in the 119 previous provider
  attempts. This is a historical convenience example, not training-held-out data.
- Text SHA-256: `8fe8df43d18cea93c1c6f789b9a536e7ffc88bdc86fb2f4f33c7bce31ce4a162`.
  Raw HTML and complete extracted text are retained without truncation.
- A separate Codex sub-agent received only the source and complete governing
  masters for its first assessment. Its 14 source anchors and nine governing-rule
  anchors were frozen before dispatch. It did not see prior model outputs,
  parent conclusions or implementation files during that stage. Neither its
  reference nor any prior answer was sent to the API model.
- Original reference hash:
  `5bb824f95a87996a6e3c63db9dfec6da96289e48334730eca31077e337b44cc1`.
- Live revision IDs for all three governing masters matched their stored full
  texts. Strategy v0.3, Experiment v0.5 and Automation v0.4 remain the authority.
- Runtime local commit `151911b2eac5404a6a84c5d056b6cf1dda3f1643`, tree
  `1c4bf7eb323768d262d55936318b3c37fa92a12a`, matching GitHub commit
  `bdf247a99e10706be0c6f3001e6a11794cee2712`.
- `1.20.0-automated-research` / `governed-research-v21`; one call, no retries,
  repairs or extra provider calls. Input 139,529 bytes, unchanged 250,000-byte
  ceiling and 12,000 maximum output tokens. Full authorities and source retained.
- Maximum campaign allowance $1.75; calculated conservative allowance $1.157645.
  Pre-test billing UI showed $11.44 and auto-reload off. No billing settings changed.

## Original result and separate review

Returned model: `gpt-5.5-2026-04-23`. Reported usage: 29,870 input tokens,
6,967 output tokens (including 3,067 reasoning tokens), zero cached input.
Calculated cost: **$0.35836**, using the rechecked official
[GPT-5.5 rates](https://developers.openai.com/api/docs/models/gpt-5.5).
Host outcome: `RESEARCH_DRAFT_AVAILABLE`, research only, no handoff.

The separate reviewer checked all 24 exported checklist items and all 30
statement clauses against the full source and citation continuations. These
overlapping checks are not an accuracy score or a statistical sample.

### Supported central account

The answer selects rule 74, regulatory decision, and explains the actual rule
meaning. It preserves the issuer-reported process approval, approximate 20%
yield improvement from the same plasma input, ASCENIV/BIVIGAM scope, forecast
economic benefits and late-2025/2026 timing. Forecast cautions and unknown
approval details remain explicit. It does not promote background pipeline or
existing approvals into new catalysts. No material economic omission was
identified within its stated scope; optional promotional/background omissions
were recorded separately. SEC hosting is not independent FDA corroboration.

### Findings retained against the original answer

| Finding | Exact original location | Why it matters |
| --- | --- | --- |
| Forecast classification recorded as a condition | `draft.economic_inventory.terms[2].conditions` | The field is `RECORDED`, but its clause describes forward-looking classification and causal linkage, not an operational contingency. The answer does not establish a condition. |
| Mixed time basis | `draft.research.materiality_coverage.support.clauses[0].time_basis` | One summary joins an announced event with forecast benefits but labels the entire clause `EVENT_OCCURRENCE`. Its prose and dedicated forecast timing elsewhere are correct; this is a localized metadata error. |
| Imprecise missing-information wording | `draft.economic_inventory.terms[1].amounts.reason` and `terms[2].conditions.reason` | “No denominator” is too broad because the comparative same-input basis is given; absolute baseline quantities are missing. Listed hypothetical prerequisite classes are not established conditions. |

These findings were not repaired in the saved response. A valid schema and
source links cannot establish that a clause belongs in its assigned field.
The separate assessment retains supported checks, optional omissions and
uncertainties alongside the defects. It assigns no global acceptance threshold.

## Preservation and verification

- All **120 original outcomes replay exactly: 58 research admissions and 62
  rejections**. The earlier 119 outcomes remain unchanged; all **24 ledger hashes**
  match.
- Complete provider envelope, exact original text, full wrapper, model/version
  identity, source packet, reference and separately attributed review are retained.
- Review evidence is checked against exact original draft paths and source spans.
  The read-only JSON/HTML export regenerates exactly. Visual/mobile usability
  was not tested.
- The source-first reference is never rewritten after the answer arrives.
  Historical failures, judgments and request-bound masters remain preserved.
- Packet `a2faa8e92c6bd756e29ea7370178b5ea97170ae1f85ec8011856e0720d2074d2`;
  request `540fbde60bcea6056fa8c23cb12e21ec126c2eb8ce55c144c85c07fda70adb23`.
  Synthetic run ID is retained; candidate, signal and journal-trade IDs remain
  null because this test creates none of those records.
- The repository change for this step is documentation only. The previously
  verified 1,004-test runtime is unchanged; that suite was not rerun for these
  documentation changes.

Private reproducibility artifacts are in `explicit-fresh-20260923`: frozen plan
and inputs, immutable attempt ledger, original response, exported review,
source-first reference, separate findings, replay manifest and final integrity
manifest. No credential is included in repository documentation.

Review/integrity verification manifest:
`74c6d241be67057bb2426c494bb0cdad06b8b8ffa284243e16e69dfe278deeb1`.
Separate assessment hash:
`9f7020e6064214964d0c796139eb301e979f12f1eb29f442ebe7c316a67e6a3c`.

## Boundaries and remaining work

Separate AI review reduces exposure to prior conclusions; shared-model and
historical-source limitations remain. One source cannot establish general
reliability, profitability or independent human acceptance.

All artifacts remain `INFRASTRUCTURE_EVALUATION`, `eligible_for_handoff=false`.
No current catalyst, Strategy observation, trade, retrospective execution or
Journal entry is created. No strategy methodology, risk, observation eligibility,
synced source, production configuration, merge or deployment changes. Phase 1
SHADOW and disabled broker execution remain repository boundaries. **Live runtime
configuration and Journal state were not checked.**

Next work is to address condition/forecast field separation and mixed temporal
claims with offline regressions, preserving this answer as the failing semantic
example. That is a new implementation step; this report does not claim those
issues have been fixed or authorize another paid test.
