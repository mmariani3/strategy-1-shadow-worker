# Single scope and source wording — research contract v17

The v16 comparison rejected both Mini responses because two independently written
scope strings differed. An admitted GPT-5.5 response also shortened a voting
condition despite citing the source. New requests use
`1.16.0-automated-research` / `governed-research-v17` to address these distinct problems.

## One scope

The provider returns exactly these root fields:

```text
assessment_scope
economic_inventory   # status, unresolved, terms; no scope field
research             # existing research fields; coverage has no scope field
```

Duplicate scopes are forbidden, even if identical. The host projects the single
root value into fields required by its frozen v16 internal parser. This is
declared only for new v17 envelopes. Original envelope/inventory, request, trace,
and original/projected digests remain attributable. **No historical answer is
repaired or reclassified.** The new prompt removes superseded v16 scope directions.

## Source wording remains visible

Every recorded entry in the mandatory `economic_summary` contains the model's
original statement/time category/passage numbers plus host-generated
`source_passages`: full selected catalog text, serialized source quote, source
identity/path, offsets and passage identity. No selected passage is paraphrased
or shortened.

For example, “shareholder approval” may omit the source's voting majority and
excluded parties. When that full paragraph is selected, both the model wording
and original condition remain visible. Consumers must present the source wording
with the statement and retain the economic summary alongside the narrative.
`verify_source_summary(packet, original_draft, summary)` rejects lost or altered
fields, source wording, attribution and JSON types.

The prompt asks for exact defined groups, voting basis, quantifiers, exclusions,
AND/OR dependencies, approval exceptions and conditional payments. It distinguishes
commitments from realized results and announcement/publication from calls,
closing/payment and forecast periods. Numbers must come from source evidence;
no numerical strategy threshold is introduced.

**This does not guarantee complete selection or correct interpretation.**
Unselected passages are not recovered. False model prose may coexist with correct
source wording. Quotes are untrusted evidence, not instructions, corroboration or
verified truth. Semantic completeness remains `NOT_ESTABLISHED`; no qualification,
tier approval or handoff follows. No hosted display integration is claimed.

## Findings, checks and changed files

**813 tests passed, including 32 new v17 regressions.** Full command:
`PYTHONPATH=.deps python -m pytest -q` (58.61 seconds).

| Finding | Change / offline evidence | Files | Remaining limitation |
| --- | --- | --- | --- |
| Duplicate scopes disagree | Single root field; missing, blank, wrong-type and duplicate scopes rejected; original whitespace retained through summary/review | `research_scope.py`, `tests/test_research_scope.py` | Model may choose an inappropriate scope. |
| Condition wording disappears | Full selected passages beside every entry; eight loss/tamper cases reject removed wording, changed source/parties, altered claims and dropped terms | Same | Unselected conditions and false prose still require review. |
| Payment types/time roles confused | Explicit recording instructions and preserved source context | Same | Provider compliance has not been tested. |
| New shape weakens gates | Nine request-tamper variants stop before reservation; nine malformed-envelope variants rejected; frozen nested parsers and tier gate | `research_reviewer.py`, `review_attempts.py`, `evidence_review.py`, new tests | No new semantic qualification method. |
| Attribution/audit drift | Location audit v1.3.0 uses original paths; checklist uses root scope; trace and original/projected digests retained | `research_reference_coverage.py`, `research_completeness_review.py`, new tests | Author review is not independent acceptance. |
| Default changes historical meaning | Prepare-only v17 default; historical v16 CLI test pins its builder; original response survives durable replay | `run_research_reviewer.py`, `tests/test_research_terms.py`, new tests | No live consumer rollout. |

All **105 saved provider outcomes** replay unchanged: **47 technical research
admissions and 58 rejections**, across 18 unchanged provider ledgers. Eight location
audits and eight attributed reviews from v15/v16 reproduce exactly. Original
source, request, response and review hashes remain unchanged.

Eight v17 requests were prepared only, preserving full masters/evidence and the
same models, 12,000 output tokens and 250,000 input bytes:

| Development source | Mini bytes | GPT-5.5 bytes |
| --- | ---: | ---: |
| WBA | 170,802 | 170,799 |
| JNPR | 172,470 | 172,467 |
| DAIC | 212,081 | 212,078 |
| FSI | 237,019 | 237,016 |

These reused sources are development material, not independent acceptance cases.
Offline fixtures are author-created infrastructure tests, never new model answers
or Strategy #1 observations. **Zero paid calls and $0 API cost for this step.**

Offline history/preparation verification ID:
`6443166d49323ea481fb046639d6e493bdb045fea87f470336f003d5e95fa5ce`.

## Boundaries

No migration, strategy/risk/observation-eligibility change, synced-source edit,
Journal write, deployment or execution enablement. Living Strategy v0.3, Experiment
v0.5 and Automation v0.4 revisions were reread and unchanged. SHADOW and disabled
broker execution remain repository boundaries; **live runtime configuration and
Journal state were not reverified**.

The [v16 comparison](README-term-comparison.md) remains the original measured
result. No v17 accuracy or unattended qualification approval is claimed. A future
paid test needs fresh source references and a checked budget.
