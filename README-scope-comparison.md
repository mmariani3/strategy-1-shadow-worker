# v17 provider comparison — September 22, 2026 Pacific

**The single-scope format worked in all four answers, but unattended research is
not accepted.** Both GPT-5.5 answers passed technical validation. Both Mini answers
failed other contract checks. A source review found omissions in one admitted
GPT-5.5 answer; the other preserved the material terms within the finite checklist.
This was an implementation-author review, not independent acceptance.

## Frozen comparison

- Two complete historical SEC exhibit bodies, new to the prior 105-outcome corpus:
  [Union Pacific / Norfolk Southern, July 29, 2025](https://www.sec.gov/Archives/edgar/data/100885/000119312525167154/d64537dex991.htm)
  and [Repare / Xeno, November 14, 2025](https://www.sec.gov/Archives/edgar/data/1808158/000119312525283314/d39095dex991.htm).
- Both models received each source and the same governing masters. No truncation,
  reduced limits, answer repairs, prompt changes during dispatch, or paid retries.
- Same model names: `gpt-5-mini`, `gpt-5.5`. Same limits: 250,000 input bytes and
  12,000 output tokens per call. Prepared bodies: 215,749 / 215,746 bytes for NSC;
  217,402 / 217,399 bytes for RPTX, Mini / GPT-5.5 respectively.
- Twenty-one source anchors (eight NSC, thirteen RPTX) and the reference were
  frozen before responses. The reviewer was the implementation author, aware of
  earlier model results; models may have training familiarity with these releases.
- Runtime: `1.16.0-automated-research` / `governed-research-v17`.
  Tested local commit `f93886a3c7aabf4857f4dc92ea050a8218fa3f56`; GitHub equivalent
  `5cd11a383ed24fc948cee9dc2dbf2a07276004e5`; matching tree
  `8ce33ebc71c43a729427e5ab175d037100c64914`. Runtime remained unchanged throughout.

All fixtures are `INFRASTRUCTURE_TEST`, classified `INFRASTRUCTURE_EVALUATION`,
with explicit synthetic run IDs and null candidate, signal and journal-trade IDs.
Session and phase fields are schema placeholders, not evidence of a premarket scan.
The ordinary CLI correctly excludes them. An isolated harness called the same
request validator, durable ledger, transport and parser with the infrastructure
classification retained. **This does not test production discovery dispatch.**

## Results

| Historical document | Model | Original technical result | Source review | API cost |
| --- | --- | --- | --- | ---: |
| NSC | GPT-5 mini | Rejected: `FACT_ROLE_MISMATCH` | Revisions required | $0.03199575 |
| NSC | GPT-5.5 | Research draft available | Revisions required | $0.53553500 |
| RPTX | GPT-5 mini | Rejected: `CLAUSE_EVENT_SCOPE_MISMATCH` | Revisions required | $0.03584025 |
| RPTX | GPT-5.5 | Research draft available | Scoped author review recorded | $0.57420500 |
| **Total** | **4 calls** | **2 admissions / 2 rejections** | **No independent acceptance** | **$1.17757600** |

“Admission” means the answer passes the technical contract and can be retained as
research. It is not factual approval, strategy qualification or permission to trade.
One successful finite checklist does not establish model accuracy or profitability.

### Concrete findings

**Mini / NSC:** `document_coverage` uses `PUBLICATION` where the contract requires
`TARGET`. The answer also uses the investor-call time as publication timing,
classifies a stock-price reference date as publication, mixes forecast leverage
with reported results, and omits disclosed economic details. It describes linked
company materials as if captured, although only the exhibit and pointer were supplied.

**GPT-5.5 / NSC:** consideration, enterprise-value basis, reverse termination fee,
funding, dilution and forecast financial effects are retained. However, the
expected STB application within six months and specific legal-defense,
indemnification and liability costs are absent from the chosen transaction scope.
Those passages were not selected, so the exact source-wording summary cannot
recover them. The reviewer recorded `APPROVAL_TIMING` and `DOWNSIDE` revisions.

**Mini / RPTX:** selected-event subject support is tagged `CONTEXT`, triggering
rejection. Its prose retains the estimated cash payment and deductions, but calls
that future estimate `REPORTED_RESULT`. Named partnership/program applicability
is shortened, and one conditions clause flattens distinct pre-closing agreement,
pre-closing negotiation and post-closing CVR categories. It omits the insider
voting undertaking and concrete litigation/cost/liability risks. Both shareholder
vote thresholds and the interested-party exclusion were retained.

**GPT-5.5 / RPTX:** twelve terms preserve the cash estimate and deductions, five
separate CVR streams, named parties, percentage schedules, receipt deadlines,
the special Polq prior-negotiation condition, both shareholder voting tests,
court approval, termination fee and insider voting undertaking. Material downside
is retained. No material source-meaning defect was identified within this checklist.
Full contract interpretation, exhaustive coverage and independent acceptance remain
unestablished. Some time labels are still less precise than the accompanying prose.

## Retention and verification

| Check | Evidence | Limitation |
| --- | --- | --- |
| One scope per answer | All four original envelopes use one root scope; no duplicate-scope rejection | Two other contract failures remain |
| Full selected source wording | Exact `verify_source_summary` comparison for both admitted outputs, covering all 20 recorded terms | Unselected facts and false paraphrases are not repaired |
| Original outcomes preserved | All 109 outcomes replay: 49 exact admitted outputs and 60 unchanged rejections; all 18 prior ledger hashes unchanged | Historical results remain historical |
| Attributed source reviews | Four location audits and four author reviews reproduce exactly; no invalid passage numbers | Location overlap is not semantic correctness |
| Runtime tests | Existing unchanged v17 runtime has 813 passing tests, including 32 v17 regressions | Suite was not rerun for this documentation-only comparison step |
| Governing authority | Three live master revisions reread and matched the full frozen masters | No methodology or numerical policy changes |
| No strategy evidence leakage | Infrastructure class retained; CLI exclusion and null downstream IDs verified | No live discovery, Journal or production runtime verification |

Raw HTTP bodies, complete extracted texts, sources, reference, requests, original
provider responses, rejections, usage, author decisions and hash manifests are
retained privately under `scope-comparison-20260922`. The report does not publish
private masters, credentials or raw ledgers.

- Diagnostic: `ce6ce0513f2a02ec0f5efd966e8b18562effe59c9828acb03d7e63f541126d70`.
- Author review: `6e30b40af7cfc3f3ac69490cf70210ea62675064096843ff471a94706b07d671`.
- Verification: `507c7e4bc702ca91a58541ab689926bb204451c488130f646f790346a0f2faee`.

## Cost and next work

Before dispatch, billing showed $4.88 with auto-reload off. The conservative
running balance was $4.869198; the frozen allowance was $3.14201275. Actual cost
above is calculated from returned input/cached/output usage at the verified
[Mini](https://developers.openai.com/api/docs/models/gpt-5-mini) and
[GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5) rates. The resulting
conservative balance estimate is **$3.691622**, subject to other usage and billing
timing. A post-test billing refresh still showed $4.88, so it had not visibly
reflected this comparison. No credit purchase or billing change was made.

Next engineering work should be offline: constrain topic-specific role and
event-relation choices, and evaluate how a separate source-coverage review can
surface omitted terms. Do not introduce a new strategy qualification gate,
repair saved answers, or claim that citation coverage proves meaning. This
comparison does not authorize another paid run or model change.

Only this report and links from the v17 contract/reviewer documentation changed
in the repository. No runtime code or tests changed. PR9 remains a stacked draft
on PR8, unmerged. Phase 1 SHADOW and disabled broker execution remain repository
boundaries. Nothing was deployed; production settings, Journal state, synced
sources, Strategy v0.3 and Experiment v0.5 were not modified.
