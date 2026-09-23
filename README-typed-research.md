# Constrained research labels and offline omission review — v18

Historical v18 record. The current default is [v19](README-tier-review.md);
the results and version-specific behavior below are retained as originally tested.

The subsequent [four-call provider comparison](README-typed-comparison.md) tested
this unchanged runtime. All new field shapes passed; one separate tier-mapping
rejection and content-review defects remain. The offline results below are preserved.

The v17 comparison found two Mini contract failures and economically relevant
omissions in an admitted GPT-5.5 answer. This change moves existing field
relationships into the provider schema and adds a separate source-location review
queue. It does not repair prior answers or grant unattended qualification.

## New requests

The default prepare-only CLI now builds `1.17.0-automated-research` /
`governed-research-v18` requests. The single-scope envelope and full selected-source
economic summary remain unchanged.

- Each fact topic has its correct fixed role: identity/document coverage use
  TARGET; catalyst/event timing use EVENT; publication timing uses PUBLICATION.
  Missing evidence still uses status UNRESOLVED. Role identifies the field's
  subject, not evidence confidence.
- Selected-event description, subject and link, catalyst/event-time facts and
  evidence gaps restrict support to SELECTED_EVENT. Context remains available in
  the separate context fields.
- Event-time clauses allow EVENT_OCCURRENCE; publication-time clauses allow
  PUBLICATION. These choices cannot establish that the accompanying prose is true.
- Five topic-specific schema branches express these constraints; local validation
  enforces them too. Duplicate/missing topics fail locally. Unknown subjects and
  unavailable support are not converted into evidenced assertions.
- Request validation binds the complete schema, instructions, masters and source
  before a call is reserved. Original answer bytes are passed unchanged through
  the frozen v17 parser. Version attribution and request identity remain v18.

The schema uses nested `anyOf`, constants and bounded arrays, following the
[official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs)
checked September 22, 2026 Pacific. No paid request tested provider compatibility
or model compliance in this step. Historical v17 builders/parsers remain unchanged.

## Offline omission report

```text
python research_omissions.py --packet packet.json --request request.json \
  --draft original-draft.json --reference reference.json --output reports
```

The report validates the original source/request/reference bindings and preserves:

1. All substantive captured source text, including exact serialized spans outside
   the citation index. Missing indexing cannot silently look like complete coverage.
2. Every indexed substantive passage with source identity, path, offsets and full
   wording, plus paths to any model statements selecting it.
3. Separate statuses for inventory selections, narrative-only selections and
   unselected passages. The latter two form a review queue.
4. Exact unselected spans within the externally supplied reference anchors.
5. Original packet, trace, request, draft and reference identities. The exact
   verifier detects changed text, lost rows, changed IDs or a false acceptance label.

The CLI writes an immutable artifact and makes no provider calls. It can inspect
saved rejected answers without changing their admission outcome. A reference is
required and retains its author's attribution; this does not create an independent
source reviewer.

**Flags are not omissions proven material.** Optional context and boilerplate
remain visible; hundreds of flags are possible. No risk-keyword heuristic,
selection percentage or numerical strategy threshold filters the queue. A model
can cite every passage and still misstate it. A passage can also be paraphrased
without a citation. The report does not approve, reject or qualify trades.

## Findings, fixes and limits

**847 tests passed in 77.29 seconds**, including 34 new v18/omission regressions.
The full suite ran offline with `PYTHONPATH=.deps python -m pytest -q`.

| Finding | Change | Evidence | Remaining limitation |
| --- | --- | --- | --- |
| Mini used PUBLICATION for document coverage | Topic-specific fixed role | Incorrect role variants fail local validation; fixed role remains compatible with unresolved status | Actual v18 model compliance untested |
| Mini tagged an event subject CONTEXT | Selected-event support constrained | Subject/description/link/event fact and gap regressions | Correct label cannot prove correct event meaning |
| Time categories disagree with fact topic | Topic-specific clause types | Publication/event-time mismatches rejected | A future call can still be wrongly described as publication in prose |
| Selected economic terms omit source details | Source queue separates uncited and narrative-only passages | Original NSC GPT-5.5 six-month STB filing window and legal-defense cost passages flagged | All flags need attributed materiality review |
| Catalog gaps could hide text | Complete substantive text and unindexed spans retained | Unicode, repeated text and simulated index-hole regression; actual NSC index gap exposed | Capture completeness itself remains unproven |
| Retrospective repair could change evidence | Frozen historical routes and read-only reports | 109 original outcomes replay unchanged; all 19 ledger hashes unchanged; 24 exact historical sidecars | Old rejections remain rejected |
| Larger schema could force reduced inputs | Unchanged full-source and master input, fail closed on size | 12 requests prepared only across NSC/RPTX/WBA/JNPR/DAIC/FSI, about 176–242 KB | Future sources may exceed 250,000 bytes and must not be truncated |

Both saved Mini answers fail the new narrow shape checks, while both saved GPT-5.5
answers satisfy those shape checks. This is a diagnostic against historical text,
**not four new v18 responses or changed admission outcomes**. No model accuracy
improvement is claimed.

Offline verification: `a21bc2163fb753e892cf364c75666f33a76fe7ed23dce4c632095aafca7acab8`.
The private `typed-offline-20260922` folder contains the request preparations,
four omission reports, master revision check and manifests. Source documents,
original responses and private masters are not published in this PR.

## Changed files and boundaries

- `research_typed.py`: v18 schema, request/response validation and attribution.
- `research_omissions.py`: offline queue, exact verifier and CLI.
- `research_reviewer.py`, `review_attempts.py`, `evidence_review.py`,
  `run_research_reviewer.py`: explicit v18 routing and default preparation.
- `research_reference_coverage.py`, `research_completeness_review.py`: v18 audit
  routing with original envelope paths; historical outputs unchanged.
- `tests/test_research_typed.py`: new infrastructure regressions;
  `tests/test_research_scope.py`: historical CLI case pins its v17 builder.
- Reviewer/reference documentation links to this contract.

No schema migration. No paid calls, credential access, source retrieval, strategy
observations, Journal writes, model substitution, deployment or broker enablement.
Strategy v0.3, Experiment v0.5 and Automation v0.4 live revisions were reread and
unchanged. Phase 1 SHADOW and disabled broker execution remain repository boundaries;
live runtime configuration and Journal state were not checked in this step.

Independent semantic acceptance, omission relevance and unattended qualification
remain unresolved. Any future paid comparison needs fresh sources, frozen review
references and an explicit budget; these development cases are not held-out evidence.
