# Economic-term inventory v16

The v15 comparison showed that a model could cite an entire acquisition paragraph
while omitting the conditional reimbursement and lease-backstop amounts from its
answer. V16 gives those terms an explicit record before the narrative and generates
their economic summary in code, without shortening or paraphrasing the record.

Default prepare-only CLI: `1.15.0-automated-research` / `governed-research-v16`,
implemented in `research_terms.py`. Model selection, full source/master/context,
12,000 output tokens and 250,000 input bytes remain unchanged for the prepared
comparison. No model calls have been made with this version.

## Contract and presentation

The model returns an envelope with two required objects, in this order:

1. `economic_inventory`: the declared economic scope, recorded/unresolved status,
   unresolved issues and term records.
2. `research`: the existing inline-support research contract, including the same
   economic scope, facts, gaps, context and unapproved tier proposal.

Each term has a label, relationship to the selected event, and nature (obligation,
commitment, reported result, forecast or other). Its four facets are explicit:

| Facet | What the model is asked to retain |
| --- | --- |
| `amounts` | Disclosed amount/rate, units, basis/period, payment form and limits |
| `conditions` | Joint or alternative dependencies, elections, approvals, exceptions and restrictions |
| `timing` | Dates or relative deadlines as stated, with separate payment/effective, forecast and reported-period labels |
| `qualifications` | Downside context, attribution, uncertainty, source ambiguity and causal limits |

A facet is `RECORDED`, `UNRESOLVED` or `NOT_APPLICABLE`, with a reason. Recorded
facets require cited entries; the other states have no entries and an explanation.
Unavailable information is not converted to zero or unconditional economics.
An entirely empty inventory must explicitly remain unresolved. None of these
statuses certifies completeness, semantic support or strategy eligibility.

The parser validates the inventory, binds each entry to exact original source
locations, and produces **`economic_summary` at the top level of the saved result**.
It preserves every term, facet, entry, label, time tag and unresolved reason exactly,
including original whitespace. The detailed inventory and source bindings also
remain under `research_binding.economic_inventory` with packet/request identity,
original draft digest and trace IDs. No synthetic candidate/signal/trade IDs are added.

The short `research` narrative may omit detail. **Consumers must present or retain
`economic_summary` alongside it**; the narrative alone is not the full economic
result. `verify_inventory_summary(inventory, summary)` rejects changed or missing
fields, entries, rows, scope, status or unresolved issues. It can verify a persisted
or transported summary against its original inventory; an application discarding
both the inventory and summary is outside this guarantee.

Economic entries require substantive document/news passages; only explicitly
publication-labelled timing entries may use publication metadata. Unknown and
duplicate passage numbers, empty terms, inconsistent facet states, mismatched scope,
and unsupported approval fields fail. The software does not choose economic
materiality or a new strategy category.

## Versions and preserved boundaries

V16 binds its full prompt, envelope schema, packet, source, masters and request
digest before a provider-call reservation. The nested `research` object is an
explicit projection of a **new v16 envelope**, checked by the frozen v15/v14 parser
chain. The original provider envelope is retained unchanged; no saved historical
answer is converted into a v16 model result. Attribution records the new extractor
and the parser implementation actually used.

Source-location audits use version `1.2.0` for v16. Both the inventory and nested
research selections are inspected, with their original paths retained. The
attributed completeness checklist also supports the envelope. Historical v14/v15
audit formats and outcomes remain unchanged. No database migration is required.

**All results remain research-only and ineligible for handoff.** Tier approval,
prospective confirmation, freshness, live market/risk inputs and execution are
still separate gates. No strategy thresholds, source requirements, setups, stops,
targets, position sizing or evidence-eligibility rules changed.

## Offline evidence — September 22, 2026 Pacific

**781 tests passed, including 33 new v16 regressions.** No provider call or credential
access was needed for this work.

| Finding | Implementation / test evidence | Changed files | Remaining limitation |
| --- | --- | --- | --- |
| Summary drops amounts, conditions or dates | Four facet records; deterministic summary; nine loss/tamper variants rejected; exact strings retained through durable replay | `research_terms.py`, `tests/test_research_terms.py` | Terms omitted before inventory creation cannot be recovered automatically. |
| Categories masquerade as extracted economics | Explicit cited entries, term nature and detailed time tags; unresolved facets retain their reasons | Same | Correct category, numerical claim, attribution and qualifier interpretation still need source review. |
| Invalid references or scope | Ten invalid-inventory variants rejected, including metadata-as-economic-proof, scope mismatch and duplicate terms | Same | Valid source locations do not prove entailment. |
| New request could bypass authority checks | Nine tamper variants stop before reservation; default CLI prepares without provider access | `research_terms.py`, `review_attempts.py`, `run_research_reviewer.py`, tests | Future provider compliance and output-size behavior are untested. |
| New envelope could weaken old gates | Frozen nested parser; attempted tier approval still fails; exact historical replay | `research_reviewer.py`, `evidence_review.py`, tests | No independent semantic acceptance. |
| Review tools might lose nested provenance | Versioned location audit and completeness paths; original false-prose fixture remains semantically unaccepted | `research_reference_coverage.py`, `research_completeness_review.py`, tests | Finite author checklists are not exhaustive source review. |
| Historical default tests accidentally change meaning | Historical CLI test explicitly pins v15; new CLI test asserts v16 | `tests/test_research_economic.py`, new tests | No historical failure relabeled as a success. |

All **101 saved provider outcomes** replay unchanged: **45 research admissions and
56 rejections**, across 17 unchanged ledger hashes. The four v15 source-location
audits and four attributed reviews reproduce exactly. The original evidence package
hashes were verified before and after inspection.

Four v16 requests were prepared from the existing DAIC/FSI development sources only:

| Source | Mini request bytes | GPT-5.5 request bytes | Status |
| --- | ---: | ---: | --- |
| DAIC | 210,071 | 210,068 | Prepared, not sent |
| FSI | 235,009 | 235,006 | Prepared, not sent |

Additional **author-created transport fixtures**, using exact frozen DAIC and FSI
source paragraphs, verify retention of the acquisition costs, contract duration /
minimum revenue and contingent R&D amounts. Deliberately dropping each facet is
rejected. These fixtures are not model extractions, repaired answers, fresh
evaluation cases or Strategy #1 observations. The prior rejected answers remain
rejected; the prior admitted but incomplete answers remain semantically unverified.

Private offline verification ID:
`c4a04e996726012edba32861afcea705236cb2dfa99e407762c5ee0e8145e322`.

## Subsequent provider comparison

The separately budgeted v16 comparison is now complete: four calls cost an
estimated $0.930802. Mini failed both scope-equality checks; GPT-5.5 passed both
structural checks, but one of its answers still omitted approval mechanics.
All 13 terms in the admitted outputs were retained exactly. See the
[provider comparison, source review and limitations](README-term-comparison.md).
The offline results above remain attributed to the earlier zero-call step.

## What this does and does not establish

Once a term is recorded, the host summary cannot silently shorten it. A model can
still omit a term entirely, choose an inappropriate scope, record false information,
mis-tag dates, or contradict the inventory in the narrative. A deliberate false-prose
regression demonstrates that valid citations and perfect retention do not establish
truth. Semantic completeness remains `NOT_ESTABLISHED`, even for a fully populated
inventory. This follows the documented distinction between schema adherence and
[mistakes in structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs#handling-mistakes).

Any additional paid comparison needs separately frozen, attributable source
references, unchanged full testing limits and a verified budget. The prepared
DAIC/FSI cases and the subsequent WBA/JNPR comparison are now development material,
not fresh independent acceptance evidence. The comparison does not establish
unattended qualification reliability.

Living master revisions were reread and unchanged: Strategy v0.3, Experiment v0.5,
Automation v0.4. No merge, production deployment, Journal write, broker enablement,
synced-source edit or billing change occurred. Phase 1 SHADOW and disabled execution
remain repository boundaries. **Live runtime configuration and Journal state were
not reverified.**
