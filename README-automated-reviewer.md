# Automated research reviewer

The default request contract is now [v19: tier references and readable source
review](README-tier-review.md). This update was tested offline only; historical
provider comparisons below retain their original versions and outcomes.

This implements an opt-in OpenAI Responses API client for the packets in [PR #5](https://github.com/mmariani3/strategy-1-shadow-worker/pull/5). It can request a substantive, source-cited research assessment and compare its claims with a separately supplied reference. **It cannot qualify candidates, refresh live approvals, confirm triggers, establish experimental observations or enable execution.**

Phase 1 remains SHADOW. Strategy Rules v0.3 and Experiment Plan v0.5 are unchanged. The review method remains a proposal pending independent semantic assessment and acceptance in the governing Automation Specification. No model/provider subscription, credential, hosted service, live retrieval or deployment is provisioned by this change.

## What the reviewer receives

For a zero-API-cost review of saved v14–v17 answers, see [offline reference-location
review](README-reference-coverage.md). It flags uncited source checklist passages
without changing the reviewer, historical outcomes or semantic-approval boundaries.

### Historical v17 CLI: one scope and source wording

The historical v17 default was `1.16.0-automated-research` / `governed-research-v17`, prepared by
`research_scope.prepare_scope_request`. One root scope replaces duplicate fields.
The mandatory economic summary retains each entry and adds its full selected
source passages. Consumers must present source wording with model statements.
See [contract, offline verification and limits](README-single-scope.md).
Zero v17 provider calls; no claim of improved model accuracy.

### Preserved economic-term inventory v16

The prior contract is `1.15.0-automated-research` / `governed-research-v16`, prepared by
`research_terms.prepare_terms_request`. An explicit inventory precedes the nested
research object; the host generates a lossless `economic_summary`. Consumers must
retain/present that summary alongside the concise narrative. Amounts, conditions,
timing and qualifications cannot be silently dropped from recorded terms, but
omissions during extraction and semantic errors still require source review.
See [v16 contract, 781-test verification and limits](README-term-inventory.md).
The [four-call v16 comparison](README-term-comparison.md) remains unchanged.

### Preserved economic extraction v15

The prior version is `1.14.0-automated-research` / `governed-research-v15`, prepared by
`research_economic.prepare_economic_request`. It adds scope-specific source/prose
checks for economic terms, fees, conditions, timing, counterevidence and unsupported
prerequisites. The existing inline-support schema and frozen v14 parser remain in
use. See [v15 changes, tests and limitations](README-economic-review.md).
Its four-call comparison still found material omissions in technically admitted drafts.

### Preserved inline numbered support v14

The prior contract is `1.13.0-automated-research` / `governed-research-v14`, prepared by
`research_linked.prepare_linked_request`. Each finding contains its own support
clauses with bounded integer passage numbers. The host derives stable passage IDs,
parent excerpt references and support paths from those selections. Gap scope/index
and rule references are also derived. The model no longer copies long hashes or
maintains a second, potentially inconsistent parent-reference list. Invalid numbers,
duplicates within a clause, forbidden legacy fields, unsupported timing/subject
claims, altered requests and automatic tier approvals still fail closed.

The adapter uses the frozen v13 checks on a deterministic internal representation
of **new v14 responses only**. It does not convert historical responses. The saved
v1-v13 outcomes and parsers remain intact. Full source/master/context content and
original occurrence offsets are retained. Valid references still cannot establish
entailment, completeness, necessary gaps or appropriate tier mapping. All proposals
remain unapproved and all results remain research-only, ineligible for handoff.

Offline verification: **688 tests passed**, including 30 new regressions; all 93
saved provider outcomes replay unchanged across fifteen unchanged ledgers.

#### Completed paired development comparison, September 19, 2026 (Pacific)

The already-used ABTS/CVI documents and unchanged source-backed reference were
frozen before four new calls. This is not a held-out accuracy test, independent
review or Strategy #1 evidence. Full masters/source/context and the original
12,000-output-token / 250,000-input-byte allowances were retained. There were no
retries, response repairs or runtime changes during the campaign.

| Case | Model | Technical outcome | Usage-priced cost |
| --- | --- | --- | ---: |
| ABTS | Mini | Rejected: substantive-source category check | $0.02886700 |
| ABTS | GPT-5.5 | Research draft admitted; semantically unverified | $0.35740000 |
| CVI | Mini | Rejected: selected-event scope mismatch | $0.02861450 |
| CVI | GPT-5.5 | Research draft admitted; semantically unverified | $0.37186000 |

All four completed; total **$0.78674150**. All 398 passage selections referenced
existing locations (including repeats); this is not an accuracy score. The two
GPT-5.5 drafts passed structural checks versus zero in the preceding v13 campaign.
Two reused cases cannot establish a reliable improvement rate or deployment readiness.

Selected source-backed author findings (not an exhaustive independent review):

- Mini/ABTS incorrectly expected the issuer filing to use the private strategy's
  tier labels, confused rule and source numbers, and required later funding facts
  without establishing that they were necessary for reported agreement significance.
- Mini/CVI separated July29 from September18, but still treated primary documents
  and setup approval as mandatory materiality gaps and cited headlines for workflow
  metadata. The scope check rejected its context-labelled gap support.
- GPT-5.5/ABTS retained adjacent conditional financing/default/180-day passages,
  commitment-versus-proceeds and stated dilution, with optional exhibit followup.
  It left tier mapping unresolved. It omitted the $7.5M noncontingent commitment
  fee from extracted findings: structural admission does not establish completeness.
- GPT-5.5/CVI separated event/publication dates and other issuers, preserved technical
  context, and proposed the earnings/guidance category for a reported sales surprise.
  That proposal remains NOT_APPROVED; semantic fit and whether the proposed sales
  benchmark gap is indispensable remain unverified, not new strategy prerequisites.

All **97 saved outcomes** replay unchanged: 43 historical research admissions and
54 rejections across sixteen unchanged ledgers. Neither model is accepted for
unattended qualification. Next work should use these saved outputs for completeness
and semantic review before a new paid, held-out comparison.

Tested runtime: local `5706ae376ac1e36a2f67a808db405adf5738529e`, GitHub
`138a7e362099f246237402a874b649574b1c090d`, matching tree
`08a6301b89652ed9d50ab4736fdd5b520e0f267f`. Original reference SHA-256:
`80715eca302555c43c65b83a0ba17de8a0adf0effc96fbb7f4480b62e8722055`.
The private evaluation package retains requests, responses, ledger, frozen inputs,
eleven attributable author findings and final verification. Historical v13 records
below are unchanged; no prior rejection was promoted.

Estimated remaining API credit is **$1.82520425**, assuming no unrelated usage.
The live billing page returned an authentication error, so this is accounting from
the prior conservative balance, not a verified live balance. No further paid calls
are scheduled. A comparable full four-call conservative allowance would exceed this
estimate; restore billing visibility and replenish before such a campaign, without
reducing test content or limits. No purchase or billing-setting change was made.

### Historical occurrence-specific passages and tier proposals v13

The preserved v13 implementation is `1.12.0-automated-research` / `governed-research-v13`, prepared by
`research_passages.prepare_passage_request`. Models select fixed passage IDs;
the host copies exact text and occurrence-specific source offsets. Repeated text
at different locations has different IDs. No quotation retyping, ellipsis repair,
punctuation normalization or occurrence guessing is permitted. Passage boundaries
are mechanical presentation aids, sometimes splitting abbreviations or sentences;
adjacent context and full source text remain available. The inherited excerpt
catalog still cannot index a whole excerpt that is duplicated; such text remains
visible in the complete source, and no completeness guarantee is made.

Tier suggestions must select a literal category from the versioned Strategy master
and identify supporting fact paths. Discovery channels cannot substitute for tier
definitions. Every mapping is `NOT_APPROVED`; the materiality/tier assessment must
remain `INSUFFICIENT_EVIDENCE` because no automatic semantic mapping method has
been accepted. Useful facts and narrow research coverage are still retained. This
is an adapter capability boundary, not a change to Strategy #1 qualification.
Exact source/rule locations cannot prove entailment, relevance or completeness.

The request preserves full masters, original source text and all non-source
context. Master identities, hashes, the derived rule catalog, schema and prompt
are checked before call reservation. Versioned replay preserves older behavior;
no migration, source rewriting or outcome relabeling is performed.

Validation: **658 tests**, including **34 new passage/tier regressions**. All
**89 prior provider outcomes (41 admitted research results, 48 rejections)** replay
unchanged across fourteen ledger hashes. New tests cover repeated occurrences,
Unicode/escaping, forbidden model quotes/offsets, missing/incorrect rule bindings,
unsupported positive/negative tier approval, prompt/catalog tampering and replay.
Even a semantically wrong mapping to a real rule remains explicitly unapproved.

#### Completed v13 unused-source comparison

Two previously undispatched source families, ABTS and CVI, were checked with both
Mini and GPT-5.5. Selection excluded all prior request packets, substantive source
IDs and exact document-body overlaps across fourteen ledgers. Full sources,
complete non-source context, all masters, expectations, requests and runtime were
frozen before dispatch. This was author-reviewed infrastructure evaluation, not
independent semantic acceptance or Strategy #1 evidence.

Runtime local commit `21e402d9f49afb60f26bc4b0617d636f16f74cb0`, GitHub commit
`8eed03a743724c8fc6724cb23df97509d590c182`, matching tree
`44146a74de466d6b65eae0cb1edbb92a4c7d03c6`. The final full test run passed **658**.
Reference SHA-256: `80715eca302555c43c65b83a0ba17de8a0adf0effc96fbb7f4480b62e8722055`.

| Case | Model | First blocking check | Usage-priced cost |
| --- | --- | --- | ---: |
| ABTS | Mini | Missing required support paths | $0.02795050 |
| ABTS | GPT-5.5 | Unknown passage ID | $0.54311000 |
| CVI | Mini | Missing required support paths | $0.02682600 |
| CVI | GPT-5.5 | Parent-excerpt / passage coverage mismatch | $0.47253000 |

All four provider responses completed and remained rejected. Total cost:
**$1.07041650**, using the verified standard rates for
[Mini](https://developers.openai.com/api/docs/models/gpt-5-mini) and
[GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5). Both models retained
12,000 output tokens / 250,000 input bytes. No retries, response repair, output
substitution, source truncation or runtime changes occurred during the campaign.

Mini's two responses omitted five and four required support paths respectively.
They also selected irrelevant passages and again treated missing primary documents
or complete exhibits as necessary materiality facts despite captured information.
For CVI, Mini selected the September article but put the July issuer-result date
into selected-event timing and cited a CEO utilization passage lacking that date.

GPT-5.5 / ABTS distinguished agreement dates, conditional later funding, the
equity-line commitment, fee and expected dilution; full exhibits were optional.
It left the tier unresolved instead of creating a corporate-action Tier B.
It nevertheless used two unknown passage IDs (six selections), had additional
parent-excerpt mismatches, and put publication timing into an event-timing support
record. Some selected fragments omitted a qualifier present in adjacent source
text. Its extracted context also omitted the note's default-plus-180-day conversion
condition. Useful descriptive research is not complete validated support.

GPT-5.5 / CVI kept the technical warning separate from older corporate results and
other issuers and identified shared publisher origin. It proposed an explicitly
unapproved Tier C with an actual governing-rule reference. Its 80 selected passage
IDs existed, but its gap support did not cover every declared parent excerpt.
The need for demonstrated market impact or underlying RSI rankings remains a
reviewable claim, not a new Strategy prerequisite. Choosing the explicitly scoped
warning as a research event is not itself an error or approval of an RSI strategy.

In total **253 of 259 passage selections** referenced existing exact locations.
These counts include repeats and **are not factual-accuracy scores**. The contract
eliminates model-authored quotation text but still burdens the model with long IDs,
redundant parent-excerpt references and adjacent-fragment selection. Neither model
is accepted for unattended qualification. Future work should simplify that binding
contract before another paid campaign, without weakening source checks.

Read-only final replay preserved all **93 outcomes: 41 admitted research results
and 52 rejections**, with fifteen unchanged ledger hashes. New ledger SHA-256:
`81796fca87e1ba0cf1f074aad191ee323bda5525347b9a309a9d3eb03505634f`.
The private package includes all four raw responses, source-linked author findings,
full inputs and structural diagnostics. No schema migration or historical relabeling
is needed. No Journal, schedule, broker or production configuration was changed;
live runtime configuration was not reverified. The PR remains a draft, unmerged.

### Historical v12: readable clause support

The historical version is `1.11.0-automated-research` / `governed-research-v12`, prepared
by `research_readable.prepare_readable_request`. It retains the v11 safeguards
below and fixes its quote representation contract: the model copies the exact
readable `selectable_excerpts[id].text`; the host deterministically JSON-encodes
that substring to recover original source offsets. Both readable and encoded
quotes persist. No whitespace normalization, fuzzy matching or semantic repair.
The full suite passes **624 tests**, including 31 support-contract and 16 readable
quote regressions. A fixture explicitly preserves v11 rejection while v12 accepts
the correctly specified readable representation; no real old outcome is upgraded.

The first v11 fresh-case campaign used previously untested VWAV and PH packets,
each with Mini and GPT-5.5, and cost **$0.77193025**. All four provider responses
completed and remained blocked: Mini twice omitted required support paths;
GPT-5.5 twice failed quote matching. v11 incorrectly asked for an encoded quote
field absent from the visible excerpt catalog. This implementation defect makes
those rejections unsuitable as model-quality scores. Original v11 requests,
responses, parser behavior and outcomes remain frozen; v12 does not relabel them.
Ledger SHA-256: `c567ab3986719f6fe0726f0c8fc740494fa4b9fc5530b37b194fee5c63f6e7e2`.

Source inspection also found actual Mini issues: treating missing exhibits as
materiality prerequisites, mixing event occurrence with future effectiveness,
and positive materiality labels inconsistent with its own incomplete/Tier C
explanations. GPT-5.5 preserved more chronology and optional-document distinctions;
that is author review, not independent acceptance. No model is approved for
unattended qualification. A new-version check of these cases is development
compatibility, not a fresh or independent holdout.

#### v12 development compatibility results

Four actual-CLI calls on frozen runtime tree
`47dfbc91c09cb02a938a7ee11028d68e67f47b95`, full masters/packets and the unchanged
12,000-output-token / 250,000-input-byte allowances, no retries or response repairs:

| Case | Model | Outcome | Usage-priced cost |
| --- | --- | --- | ---: |
| VWAV | Mini | Blocked: readable quote mismatch | $0.02603175 |
| VWAV | GPT-5.5 | Structurally admitted research draft; exact replay | $0.39874500 |
| PH | Mini | Blocked: readable quote mismatch | $0.02278150 |
| PH | GPT-5.5 | Blocked: quotation occurs twice within its excerpt | $0.34471000 |

All four provider responses completed. v12 cost **$0.79226725**; both campaigns
cost **$1.56419750**. Rates were reread from the official
[Mini](https://developers.openai.com/api/docs/models/gpt-5-mini) and
[GPT-5.5](https://developers.openai.com/api/docs/models/gpt-5.5) pages before calls.
There were 99 individual quote selections; 90 located a unique readable span.
This location count is not an accuracy or semantic-acceptance score. In particular,
GPT-5.5's blocked PH quote is real, but its repeated occurrence makes the offset
ambiguous. It was not treated as fabrication or silently repaired.

Author source assessment against the reference frozen before the original v11
dispatch found:

- GPT-5.5 / VWAV preserves filing, prior approvals and future effect/trading dates;
  treats exhibits as optional context; and retains no-assurance/risk language.
  Its proposed **Tier B-type corporate-action classification is not established
  by an explicit governing Tier B category**. Furnished/not-filed status also
  should not be used as the reason a source is absent or not independent.
- Mini still inserts ellipses or changes punctuation in exact quotations,
  overstates document prerequisites, changes gap assessment scope, and conflates
  verification with narrow materiality. Its PH Form 4 document route is not
  established by the captured article or masters.
- GPT-5.5 / PH separates trade/publication dates, keeps materiality and verification
  unresolved and preserves conditional attention. The necessity of additional
  context remains reviewable; observed repricing/attention cannot become a new
  universal prerequisite for a plausible catalyst.

These are selected implementation-author findings, not exhaustive independent
semantic validation. v12 cases are reused development cases. **Neither model is
accepted for unattended qualification**, including the one structurally admitted
research draft. No output is eligible for handoff.

Final read-only replay preserved **89 provider outcomes (41 admitted research
results, 48 rejections), with all fourteen ledger hashes unchanged**. The v12
ledger SHA-256 is `e4b2f9a0f7acf70fad16a07ff9d17130f46bf778a3351646eb68e01f9888bd68`.
The full suite remains **624 passing tests**. No production runtime, master,
Journal, schedule or execution setting changed; live runtime was not reverified.

### Clause support and host abstentions introduced in v11

The historical v11 CLI prepared `1.10.0-automated-research` / `governed-research-v11`
through `research_support.prepare_support_request`. Historical v1-v10 parsing
and provider records are unchanged. This is a research proposal, not an accepted
automated qualification method.

- Source-bearing findings require a support record with atomic clauses, exact
  contiguous quotes within selected excerpts, declared event relationship and
  time basis. The host checks complete citation/path coverage and quote offsets.
  Event timing cannot declare publication/market time or use metadata as event
  evidence. Declared other-event support cannot satisfy selected-event facts/gaps.
- Context notes retain quoted conditionality, expectations, counterevidence,
  causal limits and provenance. Gap reviews explain what is already established
  and why a missing fact matters to the identical narrow assessment scope.
  Document proposals remain optional and without strategy authority.
- Models author only the two research claims. The host appends nine explicit
  freshness/operational abstentions, each marked `HOST_CAPABILITY_BOUNDARY` in
  the research binding. Corporate approval documents cannot replace current
  trading approval inputs, and preferred ADV is not hardened into a cutoff.
- Exact quotes **do not prove entailment**, correct event attribution, complete
  qualifiers or necessary gaps. Declared labels and all remaining prose still
  need semantic review. Tests demonstrate this limit. All outputs remain
  `RESEARCH_ONLY`, with `eligible_for_handoff=false`.

Initial validation: **608 tests pass (31 new v11 regressions)**. Read-only replay
preserves all **81 historical provider outcomes (40 admitted research results,
41 rejections), with twelve unchanged ledger hashes**. No schema migration is
needed: new versioned JSON is distinct from old records. Full model context must
be supplied to evaluators separately from source evidence; see the method proposal.

### Historical typed event subjects v10

The historical v10 CLI prepared `1.9.0-automated-research` /
`governed-research-v10` through `research_subjects.prepare_subject_request`.
This is an infrastructure proposal with offline checks and a four-call provider
compatibility check. **Independent semantic acceptance has not occurred**.

The v9 FXY responses named the Bank of Japan in prose but left the required
read-through ticker field null. v10 records an event subject with a kind, name,
optional symbol and substantive citations. ISSUER requires a name and symbol;
ORGANIZATION and ECONOMIC_EVENT require a name and forbid a symbol; UNKNOWN
cannot establish an event link or evidenced event facts. Direct events still
require the target issuer; read-through events retain a separately cited subject
and economic link. Facts explicitly identify TARGET, EVENT or PUBLICATION roles.

This does not authorize ETFs, currency trusts or another strategy. The target's
stock-universe gate, limited materiality/verification scope, insufficient
freshness/eight operational criteria and no-execution boundary remain. A known
organization can be recorded in research without becoming an eligible instrument.
Names, kinds and economic links remain model assertions requiring semantic review.

Subject IDs bind to the packet and typed declaration. Event IDs bind to the full
typed event; all fact, claim, coverage and gap/follow-up references retain those
IDs. A host-only compatibility key permits unchanged v9 validation internally;
it is removed from all persisted subject fields and is never a security ticker.
Historical v1–v9 parsers and records are not migrated or relabeled.

The source-backed author review also found:

- LRCX's reported investment is a plan. Financial significance can remain an
  unresolved question, but binding/funded/formally approved status is not a
  universal strategy prerequisite. Event timing remains a separate unresolved
  freshness issue rather than automatically a narrow materiality requirement.
- GIPR's captured filing already describes the bounded suspension/delisting stay
  and a contingent intention to seek a further extension. Assess that context
  before calling it missing. Additional economic significance may remain unknown.

v10 prompts state these distinctions explicitly. No prose filter can prove them:
tests deliberately demonstrate that a plausible but unnecessary gap or wrong
entity name can still be structurally admissible and remains semantically
unverified. The private review addendum does not alter old model responses,
reference expectations, tier decisions, observation eligibility or masters, and
is **author review, not independent acceptance**.

Validation: **577 tests passed, including 39 v10 regressions**. Tests cover named
non-ticker subjects, absent/metadata/duplicate subject evidence, issuer/unknown
conflicts, wrong fact roles, stock-universe and operational boundaries, stable
typed IDs and gap links, optional follow-ups, lossless inputs/schema limits,
prebilling tampering, default CLI without credentials and durable historical
replay. Read-only replay preserves all 77 provider outcomes (38 admitted research
results and 39 rejections); eleven ledger hashes are unchanged. The initial offline
pass prepared twelve reused development requests losslessly at 87,638–93,883
bytes, with no API calls or credential access during that pass.

#### v10 provider compatibility check — September 19, 2026

Four of those requests were subsequently dispatched through the unchanged actual
CLI: FXY and IREN, each with Mini and GPT-5.5. Full sources/masters and the existing
12,000-output-token / 250,000-input-byte allowances were retained. The scope,
reference, runtime tree and eleven previous ledger hashes were frozen before
dispatch. These are reused development cases, not independent acceptance cases.

| Case | Model | Local result | Usage-priced cost |
| --- | --- | --- | ---: |
| FXY | GPT-5 mini | Blocked: `FACT_ROLE_MISMATCH` | $0.02019675 |
| FXY | GPT-5.5 | Research draft; exact replay | $0.25065500 |
| IREN | GPT-5 mini | Blocked: `FACT_ROLE_MISMATCH` | $0.01880375 |
| IREN | GPT-5.5 | Research draft; exact replay | $0.22658500 |

All four provider responses completed; there were no retries, substitutions,
repairs or runtime changes. Total usage-priced cost was **$0.51624050**. Both
models named Bank of Japan as ORGANIZATION without a ticker and IREN Ltd. as
ISSUER with IREN. Mini assigned incorrect roles to document-coverage facts and
was blocked. GPT-5.5's two results retain `eligible_for_handoff=false`; no internal
compatibility key leaked. All 165 individual excerpt selections resolved,
including repeated occurrences. This checks locations, not semantic correctness.
Exact replay preserves both admissions and both rejections; all eleven earlier
ledger hashes remain unchanged. New ledger SHA-256:
`2b6dd98345fc1438c59bef8a5cf040ee9c4714c0a68b39c5b0fd0d5b2fa476ff`.

Source-backed implementation-author review found:

- **Mini / FXY:** conflates publication metadata with event clock time, asserts
  materiality for an unresolved non-stock target, and bundles primary documents
  and corroboration into materiality gaps. Positive materiality also conflicts
  with its own incomplete coverage.
- **Mini / IREN:** preserves the conditional approval and unresolved event date,
  but asserts positive materiality despite incomplete coverage and treats absent
  primary documents as prerequisites. The Tier A assessment is not established.
- **GPT-5.5 / FXY:** keeps BOJ separate from FXY, does not establish stock-universe
  eligibility or materiality, and separates reported event date from publication
  time. Its proposed need for full instrument mechanics remains unestablished;
  further documents cannot authorize a currency-trust strategy.
- **GPT-5.5 / IREN:** separately selects the JPMorgan analyst action, preserves
  September 14 versus September 18 publication, and treats original analyst
  notes as optional. Its narrow Tier B research is consistent with captured
  reporting and the catalyst framework, without trade or freshness authority.

All four drafts leave freshness and eight operational criteria insufficient;
none establishes independent same-event verification. These admission counts
are not accuracy scores. Author review is not independent semantic acceptance.
LRCX/GIPR v10 prompt behavior was not tested in this small scope. No database
migration, production/Journal write, merge or deployment occurred. Independent
source-backed assessment and approved live policy/adapters remain outstanding;
neither model is accepted for unattended qualification.

### Historical evidence gaps and follow-ups v9

The explicit v9 preparer uses `1.8.0-automated-research` / `governed-research-v9`
through `research_gaps.prepare_gap_request`. Offline regressions and a bounded
12-call provider comparison are complete. **Independent semantic acceptance has
not occurred.**

The v8 comparison below exposed two admitted semantic problems: treating absent
independent corroboration as an observed failure, and requiring an absent legal
opinion without establishing a necessary economic fact. v9 changes the research
contract rather than relabeling those historical results:

- `same_event_verification=OBSERVED_FAILURE` is unavailable in this component:
  it has no approved contradiction adjudicator. Missing corroboration, shared
  origin, different events and proposed conflicts remain insufficient, with an
  explicit `verification_basis` retained for later review. Proposed positive
  corroboration keeps the existing two-substantive-source gate and still does
  not prove independence. This is a software capability limit, not a change to
  the masters' source requirements or strategy rejection rules.
- Coverage identifies **missing facts** with their relevance and the limitation
  of captured evidence. Genuine gaps still block non-insufficient materiality.
  Declaring coverage sufficient with a gap, or incomplete solely because a
  document is absent, is rejected.
- Documents are separately recorded as proposed follow-ups with a question,
  reason and optional link to a factual gap. The host marks every one
  `PROPOSAL_ONLY_NOT_AN_APPROVED_REQUIREMENT`. A document suggestion cannot alone
  block an otherwise supported narrow research assessment. No automatic
  retrieval, approved document mandate, or strategy prerequisite is created.
- Gaps and follow-ups retain exact citations, target/event context and stable
  content-bound gap IDs. Compatibility fields from historical validators do
  not leak into v9 persisted records as `missing_documents` requirements.
- Target/event binding citation choices are restricted to substantive source
  excerpts in the provider schema as well as locally. Publication metadata is
  still available for publication facts. Both full source packets and governing
  masters remain lossless; schema/input limits fail without truncation.

The target/ETF, fixed excerpt, freshness, non-catalyst, scope, trace, no-retry and
research-only boundaries from v8 remain. Historical v1–v8 parsers/results retain
their original attribution and outcomes. The CLI compatibility test for v8 now
selects its old preparer explicitly.

Validation: **538 tests passed, including 49 v9 regressions**. Tests reproduce an
old structurally admissible two-source failure and show v9 rejects it while v8
replay stays identical; optional follow-ups do not block narrow materiality, real
gaps do; required-document injection, gap linkage/authority tampering, invalid
source categories and prebilling schema tampering fail closed. Read-only replay
preserves 65 actual-provider outcomes (33 admitted, 32 non-admitted), with ten
unchanged ledger hashes. Twelve full v9 development requests prepare without
dispatch. New unused-source cases and author references are prepared locally;
these are infrastructure research, not Strategy #1 observations.

**Remaining limitation:** these gates cannot prove a model's prose, proposed gap,
economic significance, or positive corroboration judgment. A model can still
describe an unnecessary gap in plausible language. Those declarations remain
unverified; a document's necessary status is never approved by this adapter.
Independent semantic review remains outstanding; fresh provider results follow.
Neither model is accepted for unattended qualification. No database migration,
production configuration change, Journal write, merge or deployment is included.

#### v9 provider comparison — 2026-09-19

Six previously unused historical packets (IREN, LRCX, AAPL, GIPR, FXY, TER), each
with Mini and GPT-5.5, produced twelve complete provider responses. Full source
and master inputs, runtime, 12,000 output tokens, 250,000 input bytes and author
references were frozen before dispatch. No retries, repair, model substitution,
input shortening or runtime changes occurred.

| Case | Mini local result | GPT-5.5 local result |
| --- | --- | --- |
| IREN | `MATERIALITY_COVERAGE_NOT_SUFFICIENT` | Admitted research draft |
| LRCX | `BINDING_SUBSTANTIVE_EVIDENCE_REQUIRED` | Admitted research draft |
| AAPL | `FOLLOWUP_GAP_REFERENCE_INVALID` | Admitted research draft |
| GIPR | `COVERAGE_SUFFICIENCY_CONFLICT` | Admitted research draft |
| FXY | `FOLLOWUP_GAP_REFERENCE_INVALID` | `READ_THROUGH_SUBJECT_REQUIRED` |
| TER | `DUPLICATE_SOURCE_SPAN` | Admitted research draft |

Five admitted drafts replay exactly; seven rejections remain rejected. All ten
historical ledgers are unchanged. Cumulative history is 77 provider outcomes,
38 admitted and 39 blocked under their original versions. All 375 individual
excerpt selections resolve to source locations, including repeated occurrences;
this does not waive duplicate-span validation or prove semantic correctness.
All twelve keep freshness and eight non-catalyst criteria insufficient, same-event
verification insufficient and handoff eligibility false. Persisted follow-ups
carry nonbinding proposal authority. Missing corroboration never becomes an
observed failure in this set.

Author review found GPT-5.5 better preserved analyst dates, planned versus actual
events, optional documents and the historical TER earnings event. This is a
small-set finding, not an accuracy or acceptance score. LRCX/GIPR gap necessity
still needs independent review; GIPR's captured bounded suspension/delisting stay
was not assessed. FXY prose names the BOJ but leaves the structured underlying
subject null, so it is blocked. Mini still invents document requirements, mixes
operational checks into materiality, conflates publication with event timing in
some cases and borrows old earnings significance for a television recommendation.
Some requested numerical/secondary-event facts are unassessed in both models;
those remain NOT_ESTABLISHED. Exact sources and cautious labels alone do not
validate the judgments.

Calculated cost: **$1.46127450** (Mini $0.11123450; GPT-5.5 $1.35004000), using
returned token usage and checked official prices. Returned models were
`gpt-5-mini-2025-08-07` and `gpt-5.5-2026-04-23`. Runtime local commit
`f9464a3595a3e4cc75234de13c0707a44b605a90` matches GitHub implementation commit
`c095c22ecf7cb9e21a06e2745f2c6fe9a1d18450` at tree
`e1320e59f9902e4e7a95d7545301939991beef7f`. Ledger SHA-256:
`7bc8463dc4ef3882847d040f5d28125266039e0d79a116f8909fc0eb6ae9e486`.

The six packet IDs, substantive source IDs and captured document-body hashes
were unused in the prior 65 paid requests and distinct across the six. Shared
session and generic source boilerplate remain correlated. Thirty per-case author
expectations and four common expectations were frozen before responses; source
claims remain untrusted historical inputs. Private packets, masters, credentials,
raw responses and assessments remain local. Independent semantic review and
approved handling of non-company event subjects remain next steps, using saved
responses without further API calls. No strategy eligibility is established.

### Historical target and event research v8

The explicit v8 preparer uses `1.7.0-automated-research` / `governed-research-v8` through
`research_context.prepare_context_request`. Offline regressions and a bounded
12-call provider test are complete. **Independent semantic acceptance has not occurred.**

The response identifies the packet's target symbol/instrument, its stock-universe
evidence, and one selected event with its actual subject. Direct events must name
the target; read-through events identify the other subject and separately cite the
economic link to the target. Every claim and materiality assessment names the
target. Instrument/event facts are checked against the corresponding subject.
Non-insufficient conclusions require evidenced stock-universe and event-link
declarations with substantive citations. ETF/warrant/right/unknown declarations
cannot establish the stock universe. They can still produce unresolved research
facts; this does not authorize an ETF strategy or reject a trade automatically.

The host derives a content-bound selected-event ID and preserves it with claim,
fact and coverage scope plus the packet's existing trace IDs. This is identity
within the research artifact, not a verified global event identifier. Scope/link
labels remain model assertions: a model can still attach incorrect prose to a
correct symbol, or claim that irrelevant text proves a link. These structural
checks **do not establish semantic truth, economic significance or eligibility**.

`catalyst_freshness` must remain `INSUFFICIENT_EVIDENCE` in v8. The component has
no approved freshness-policy evaluator or accepted current-review input. It keeps
observed event dates separately from publication dates but cannot pass or fail
freshness from those dates. A future policy adapter needs its own governed review;
there is no new age cutoff, same-day-only rule or change to Strategy Rules. The
eight existing non-catalyst capability restrictions remain unchanged.

For citations the model selects only `[{excerpt_id}]`. The host attaches the
**entire exact selected excerpt**, with original source ID and offsets. It does
not generate, repair or search for a rewritten quotation. Multiple adjacent
excerpts can be selected separately; no cross-field stitching occurs. Unknown,
padded or duplicate IDs and model-supplied quotes/offsets are rejected. Whole
excerpts can contain irrelevant context, so valid citation location does not prove
entailment. Complete original packet text remains lossless and visible, including
repeated text that the unchanged catalogue cannot index uniquely.

The packet-specific schema binds citation choices and target symbols. Schema,
evidence and packet binding are checked before reservation/provider dispatch and
again on response parsing. Full inputs, existing byte/output limits and no-retry
behavior remain. The new single prompt contract separates event occurrence from
materiality and required documents from optional corroboration. Removing generated
quote repetitions may improve output completeness. All twelve fresh provider
responses completed in the development retest below; this does not establish
reliability on independent cases or prove the output-limit failure cannot recur.

Historical v1–v7 requests use their original parsers and preserve original outcomes.
No failed historical response is converted into v8 or relabeled as accepted. The
single document/reason list and all legacy substantive-category, coverage and
same-event source gates remain. A two-source implementation restriction does not
change the masters' most-direct-credible-source rule into a universal news-source
count requirement.

Offline validation: **489 tests passed**, including 55 v8 regressions. Read-only
replay preserved all 53 saved outcomes: 27 exact admitted results, 26 rejections,
nine unchanged ledger hashes. Twelve full requests for the six development cases
prepare without truncation at 83,678–98,442 bytes, with unchanged model choices and
12,000 output-token allowance. Those twelve requests were subsequently sent in the
frozen provider comparison below. These are infrastructure checks,
not Strategy #1 evidence or independent assessment. No schema migration is needed;
the new binding data lives in versioned local JSON. No merge/deployment or live
configuration verification is included.

The strict JSON schema uses the documented required fields, closed objects,
definitions and bounded enums in [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
checked September 19, 2026. Actual schema compatibility was exercised by the
bounded provider test below.

### v8 provider comparison: development regressions, September 19, 2026

The actual CLI sent the twelve frozen requests for PANW, FBRT, AIEQ, SDST, LCID
and GEV, each to `gpt-5-mini` and `gpt-5.5`. Full packets and living masters,
12,000 output tokens and 250,000 input bytes were retained. Runtime, prompts and
inputs stayed frozen; no retries, repairs or substitutions occurred. Living
Strategy v0.3, Experiment v0.5 and Automation v0.4 revisions were reread and matched.

| Model | Completed provider responses | Admitted research drafts | Calculated cost |
| --- | ---: | ---: | ---: |
| Mini | 6/6 | 0/6 | $0.10629025 |
| GPT-5.5 | 6/6 | 6/6 | $1.309635 |
| Total | 12/12 | 6/12 | $1.41592525 |

All **283/283 fixed excerpt selections** resolved exactly to original source
locations. This is location integrity, not semantic accuracy; whole-excerpt
selection counts are not directly comparable with historical generated clauses.
All twelve kept freshness and the eight non-catalyst criteria insufficient.
Both models preserved AIEQ as an ETF with unresolved stock-universe eligibility.
Mini's earlier LCID output-limit failure did not recur in this sample.

Mini PANW/FBRT/AIEQ/LCID failed substantive-source binding because publication
metadata was selected for target/event evidence. SDST/GEV failed contradictory
coverage declarations: sufficient research plus necessary missing documents.
Other Mini reasoning issues remain, including event/publication confusion,
unsupported document requirements and unjustified catalyst-tier conclusions.

Technical admission does not establish semantic correctness. GPT-5.5 still:

- Requires the SDST legal opinion without identifying the necessary economic
  fact it would resolve; absence alone does not justify that requirement.
- Marks GEV same-event verification `OBSERVED_FAILURE` because independent
  corroboration is missing. Missing corroboration should remain insufficient,
  rather than being promoted to an observed contradictory outcome.
- Omits some secondary-event dates, deadlines and numerical distinctions from
  the unchanged author rubric. v8 selects one event; an unassessed secondary
  event is recorded as NOT_ESTABLISHED, not automatically incorrect.

The original 30 per-case expectations and four common expectations were retained
and annotated against immutable responses. They are author assessments on reused,
correlated development cases (PANW/FBRT share an article), **not independent
acceptance, representative accuracy or Strategy #1 evidence**. Neither model is
accepted for unattended operation. Do not relax evidence gates to improve counts.

All six admitted results replay exactly; all nine prior ledger hashes are
unchanged. Across all campaigns there are now 65 preserved outcomes: 33 admitted
research drafts and 32 non-admitted responses. Calculated cumulative testing cost
is $7.7711474. Runtime is unchanged from the previously verified 489-test tree
`da252669d47b9cac1ff4a0bce76f60afd22193ae` (local `a2b9794258a04d9926f291dd826392ae682f7503`,
GitHub `d41f1bc57a54eaa8e00dfe6b81febd428d445591`); this results update changes only
documentation. Private packets, responses, ledgers and author annotations remain
local. No merge, deployment, Journal write or execution occurred. Live production
configuration was not reverified.

### Historical factual research v3–v7

The explicit `research_bounded.prepare_bounded_request` prepares historical
`1.6.0-automated-research` / `governed-research-v7` requests. The old `research_reviewer.prepare_request`,
`research_facts.prepare_fact_request`, `research_citations.prepare_selection_request`, and
`research_coverage.prepare_coverage_request` and `research_scoped.prepare_scoped_request`
remain explicit v2–v6 compatibility APIs; all old requests/results retain their
original parsers and attribution. No historical output is upgraded or relabeled.

Versions 3 through 7 first ask for five source-backed findings: instrument identity, catalyst
event, actual event/announcement timing, publication timing, and document coverage
(including referenced exhibits absent from the capture). It then assesses catalyst
freshness, materiality and same-event evidence. Workflow fields remain visible but
cannot substantiate positive/negative catalyst findings. Missing review fields are
insufficient evidence, not an observed failure.

This **document-only research adapter** cannot establish market context, liquidity,
participation, setup, risk, prospective confirmation, current approvals or macro
clearance. Code requires these assessments to remain unresolved, even if the model
claims otherwise. Their corresponding accepted measurement/review adapters are not
implemented here. This restricts software capability; it does not change strategy
rules, live Worker inputs or experimental eligibility.

Versions 5 through 7 require each citation to contain a stable excerpt ID and a verbatim
`supporting_text` clause. The ID anchors the quote: it must overlap that excerpt,
but may extend through neighboring excerpts in the **same original source field**.
Version 5 requires whole-source uniqueness. Versions 6 and 7 permit repeated text only
when exactly one occurrence within the original field overlaps the selected anchor.
Two occurrences overlapping the same anchor still fail, including overlapping
substrings. A longer exact clause may disambiguate them; no location is guessed.
The server carries the derived offsets through final claim validation instead of
searching again for the first matching string. The model cannot supply offsets.
It cannot cross JSON fields, documents, or disjoint passages. This handles sentences
split by the catalogue without changing the catalogue, source text or old offsets.
Different source spans can share one anchor ID; an identical source span repeated
within one finding/claim/coverage assessment is rejected, including via a second ID.
The result records precise quote offsets and each anchor in `citation_selection_audit`.
No normalization, fuzzy matching, automatic quote repair or silent deduplication occurs.
Workflow and
market-snapshot fields remain in the complete packet but have no selectable handles.
Publication metadata can support publication facts only. Version 3's gates remain
in force for v5/v6/v7, with duplicate detection applied to exact spans. These checks detect incorrect attribution, **not** whether a real
quotation logically supports the conclusion; semantic review is still required.

The host derives each handle from the original source ID and character offsets.
Handles cannot refer to packet IDs or
governing-master IDs. Full lossless source text remains in the request; the catalogue
is an auxiliary index, not a summary or completeness claim. Repeated spans that
cannot uniquely map remain visible but unindexed. The catalogue increases request
size; the existing explicit byte limit includes it and still fails without truncation.

Code rejects non-unresolved catalyst claims citing only workflow/publication data,
freshness claims with unresolved event timing, materiality claims with unresolved
instrument/event/document coverage, and same-event claims with fewer than two distinct
substantive source IDs. Two IDs do **not** prove source independence. Source category
classification, fact status consistency and exact quotations do **not** prove semantic
truth. Every accepted result remains a research draft requiring independent review.

#### Materiality coverage is separate from a fact about missing documents

An EVIDENCED `document_coverage` finding may correctly say an exhibit is missing.
Versions 5 and 6 require a separate `materiality_coverage` object with `status`,
`missing_documents`, `rationale`, and source-cited `evidence`. Status is one of
`SUFFICIENT_FOR_RESEARCH`, `INCOMPLETE`, or `UNRESOLVED`. The first requires no
declared missing required documents and at least one substantive citation; INCOMPLETE
requires named missing documents. Publication/workflow metadata cannot establish
coverage. Missing or inconsistent declarations fail closed.

Version 6 additionally requires `assessment_scope` and `missing_document_reasons`
(one `{document, reason}` for every named missing document). Blank scope, unexplained
documents, duplicate names, or inconsistent mappings fail. Reasons must identify
which necessary fact the missing document establishes and why captured evidence
cannot establish it. The prompt separates optional corroboration and other criterion
gaps from materiality prerequisites. It does not invent a blanket original-note,
SEC-filing or primary-source requirement, and does not waive a document required
by the governing rules or the actual economic conclusion. Reputable reporting of
an attributable analyst action can support a limited research assessment; it does
not automatically clear freshness, verification, watchlist or trade requirements.
Code checks that explanations are present and consistent, **not** that their logic
is correct. The fresh provider check below exercises this contract; independent
semantic acceptance remains outstanding.

Either a positive or negative materiality conclusion requires sufficient coverage
plus the existing fact prerequisites. Incomplete or unresolved coverage still permits
useful facts and unresolved criteria to be recorded. The declaration is persisted in
`materiality_evidence_coverage` with semantic verification NOT_ESTABLISHED: these
checks cannot detect a document the model omitted from its missing-document list,
prove economic significance, or independently verify that its declared coverage
is sufficient. This is a research evidence gate, not a strategy approval or changed
threshold. Coverage from v3/v4 is never implicitly promoted to the new status.

#### Offline v6 verification

All 33 saved original outcomes replay unchanged: 17 accepted results reproduce
exactly and 16 failures remain rejected, with unchanged original ledger hashes.
On the latest four saved responses, 55/57 individual selections pass the v6
resolver. The GPT-5.5 KALU headline is uniquely anchored and resolves; the TRUG
ticker label remains ambiguous within its anchor and correctly fails. Mini's
nonexistent KALU handle still fails. No old response or source text was repaired.

Separate derived engineering probes add explicitly author-supplied scope/reason
placeholders to exercise the new schema and final offsets. KALU GPT-5.5 and TRUG
Mini pass those structural probes; the other two fail as above. They are not new
v6 provider responses, corrected historical outcomes or semantic acceptance.
This offline pass makes zero API calls. Original v5 results remain authoritative
for those original requests, including their failures.

#### v7 format corrections and offline verification (September 19, 2026)

The two v6 Mini failures below motivate format-only changes:

- The strict response schema enumerates every selectable excerpt ID from this
  packet. The full packet and catalogue remain identical to v6. Unknown IDs still
  fail local validation, and selecting a known ID does not bypass exact quotation,
  source-field, ambiguity, category or fact checks. The schema is checked against
  the packet before ledger reservation and again during response parsing.
- The provider returns one `missing_documents: [{document, reason}]` list and no
  separate `missing_document_reasons` field. Both compatibility fields in the saved
  coverage record are derived from that single list. The original response is
  retained unchanged. No fuzzy name matching, repair or historical conversion is
  performed. Blank/duplicate documents, blank reasons, missing scope and conflicting
  coverage still fail. Scope, necessary evidence and all substantive v6 requirements
  remain unchanged; a nonempty reason is still not independent semantic verification.

The schema rejects an empty catalogue or the documented enum limits (1,000 total
enum values; over 250 values in a string enum with more than 15,000 characters).
It never trims IDs or packet content to fit. The existing complete-request byte
limit also applies. This can block large packets before dispatch; it is not a
strategy threshold. Limits were checked against [Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs)
on September 19, 2026.

**434 tests passed**, including 31 v7 regressions covering packet-specific schemas,
limit boundaries, rehashed schema tampering before billing, exact source locations,
document/reason consistency, substantive gates, durable replay, and CLI preparation
without credentials or provider calls. All 37 saved provider outcomes retained
their original parsers and results: 19 exact successful replays and 18 rejections.
All seven original ledger files had identical before/after hashes.

The offline v7 implementation pass made zero paid calls. At that point live
compatibility of the new enum schema and fresh model performance were unverified.
The four-request comparison below uses
the same KALU/TRUG development cases, models, 12,000-token output allowance and
250,000-byte input limit; it was prepared separately before dispatch. No passing
offline check establishes semantic acceptance, profitability or trading eligibility.
No database migration is needed for these versioned local JSON records.

#### Fresh v7 provider regression (September 19, 2026)

Four actual-CLI calls completed at runtime commit
`f75ea5357f16d80d6ad69b7c9644968679b84c1d`, with unchanged models, development
cases, limits and transport settings. No retry or response repair occurred.

| Case | Model | Contract result | Exact selections |
|---|---|---|---:|
| KALU | GPT-5 Mini | Rejected: publication metadata used as event evidence | 12/12 |
| KALU | GPT-5.5 | Research draft admitted | 11/11 |
| TRUG | GPT-5 Mini | Research draft admitted | 17/17 |
| TRUG | GPT-5.5 | Research draft admitted | 19/19 |

The provider accepted the new enum schema in all four requests. All 59 selected
quotations resolve exactly, and neither invalid-ID nor duplicate-document-name
failures recurred in this small sample. The three admitted outputs replay exactly.
All 37 earlier outcomes remain unchanged; eight ledgers now contain 41 outcomes
(22 admitted, 19 rejected). These are contract outcomes, not semantic accuracy.

Mini KALU still mistook publication metadata for event time; the existing source
category gate rejected it. It also claimed same-event support using a summary
that lists other stocks and does not mention KALU. Mini TRUG still invented a
universal primary/SEC/partner-document requirement despite passing the contract.
GPT-5.5 preserved conditional financing, limited KALU Tier B scope and unresolved
verification, without the previous unsupported common-share detail. Its TRUG
freshness support is only at the reported-Friday date level, not current approval
or original-scan availability. Its missing-document reasoning also invokes
contingency resolution; the strategy does not universally require an announced
transaction to have closed. Necessity and scope therefore still need semantic review.

Calculated cost: **$0.529519**. Both models used their original limits, and all
four calls recorded 10/180-second transport v2 settings. The existing 434-test
result applies to the unchanged runtime; this follow-up is documentation-only.
No result qualifies a trade, enables unattended operation or establishes strategy
profitability. The cases are development regressions, not independent validation.

#### Broader v7 unused-case comparison (September 19, 2026)

Twelve subsequent authorized actual-CLI calls compared Mini and GPT-5.5 on six
previously unused packets/captured bodies, with source-backed author references
frozen before responses and withheld from models. Models, complete masters,
12,000 output-token allowance, 250,000-byte request limit and transport v2 remained
unchanged. No retry, repair, substitution or runtime change occurred.

| Case | Mini contract outcome | GPT-5.5 contract outcome |
|---|---|---|
| PANW | Rejected: quotation location (17/24 exact) | Rejected: quotation location (12/13 exact) |
| FBRT | Rejected: source category (15/15 exact) | Research draft admitted (18/18 exact) |
| AIEQ | Rejected: quotation location (14/15 exact) | Research draft admitted (19/19 exact) |
| SDST | Rejected: quotation location (13/15 exact) | Research draft admitted (15/15 exact) |
| LCID | Incomplete: 12,000 output-token limit | Research draft admitted (17/17 exact) |
| GEV | Rejected: event fact unresolved (21/21 exact) | Research draft admitted (17/17 exact) |

Five admitted results replay exactly; all remain ineligible for handoff. Eight
historical ledgers are byte-identical to the frozen plan. There are 53 preserved
outcomes (27 admitted drafts, 26 non-admitted); these are not accuracy scores.
The eleven complete drafts contain 178/189 exactly resolved selections. No
unknown-ID or duplicate-document-name failure appeared in complete drafts.
The incomplete LCID response was preserved without partial-JSON repair or scoring.

Semantic findings remain material. Mini assessed Netflix instead of target AIEQ,
invented freshness interpretations, and retained unsupported universal primary
document requirements. GPT-5.5 correctly separated AIEQ from Netflix but still
marked Netflix freshness supported inside the AIEQ candidate record; its rationale
caveat does not establish target-level freshness or ETF universe eligibility.
Both models omitted the full older/newer SDST notice-deadline distinction. Useful
GPT-5.5 results preserved limited FBRT analyst scope, SDST financing capacity versus
proceeds, Lucid plans/targets versus realized results, and GE Vernova forecasts
versus reported backlog. Date knowledge alone did not clear freshness on those
four stronger-model cases.

All 30 frozen case-specific expectations per model and four common expectations
per case were assessed separately as SATISFIED, VIOLATED or NOT_ESTABLISHED, with
original response evidence. Assessment is by the implementation author; these
are selected challenge cases from one scan, not independent acceptance or a
representative session. PANW/FBRT intentionally share an article within the set.
Exact quote location does not prove entailment, materiality or policy correctness.
The two-source implementation prerequisite must not become a new universal
two-independent-news-source strategy rule. Governing source rules still control.

Calculated cost: **$1.7096175** (Mini $0.1418775; GPT-5.5 $1.5677400).
Returned models: `gpt-5-mini-2025-08-07`, `gpt-5.5-2026-04-23`.
The pre-run commit was GitHub `3c8c75a548b145167efb4d0581a5439077b06728`,
matching local `1cb6a793225aad942500b8904d7a163b354c986d` at tree
`bc25f75f9e7d75939dfdeda3cba8ba479148ad01`. Runtime is unchanged from the
434-test implementation; this results update is documentation only.

Neither model is accepted for unattended use. Target/event binding, approved
freshness inputs, quotation reliability and independent semantic acceptance remain
outstanding. No production configuration, master, Journal, signal, broker, schedule,
deployment or execution changed. Live runtime configuration was not reverified.

#### Fresh v6 provider regression (September 19, 2026)

Four unchanged-limit CLI calls on the previously tested KALU/TRUG cases completed
at commit `baf4a34a01ebc6f36071839796e2c7f2b76a6075`. GPT-5.5 passed both contracts
with 29/29 exact selections, gave a limited Tier B KALU assessment, and kept TRUG
materiality/freshness unresolved. Mini's KALU response still used an invalid ID
three times; its TRUG citations matched, but duplicated document-name fields
differed and failed the required mapping. No repair or retry occurred.

Mini stopped demanding an original note for KALU, but retained unsupported
universal primary/corroborating-document requirements for TRUG. The stronger
model's missing-document reasons were more specific; they are not independently
verified, and its TRUG common-share wording exceeds the article's generic stock
description. All outputs remain research-only and ineligible for handoff.

Calculated cost: $0.4754808 across four calls. This is a development regression,
not independent accuracy evidence. Both admitted results replay exactly. The
403-test result applies to the unchanged runtime; this later update is documentation
only. Additional API tests require checking balance/cost without weakening test
models, cases or limits to fit an insufficient balance.

The five model findings are persisted as `fact_findings` alongside the attributed
review artifact; the original provider response stays in the immutable ledger.
No database migration is needed: these are additive JSON payloads in the existing
local ledger. Nothing writes to trading services, the Journal or a broker.

Regression coverage includes decoded quotation/newline handling, workflow-only
claims, missing exhibits/facts, publication-versus-event timestamps, price/snapshot
misuse, unknown/master IDs, capability violations, catalogue tampering, exact input
size, restart recovery and preservation of v1/v2/v3/v4 histories. Version 4 also covers
wrong-passage support, mixed workflow/document citations, publication-versus-event
use, narrow quote offsets, ambiguity, and useful positive assessments. These isolated tests are
infrastructure fixtures, not trades or strategy observations. Version 5 adds exact
cross-boundary source spans, distinct quotes sharing anchors, repeated source-span
rejection, separate completeness status, missing-document conflicts and useful
research-only outputs with incomplete evidence. It has been checked offline against
saved v4 responses and in a bounded four-call v5 provider regression on MEDS/BIAF.
GPT-5.5 passed both cases; Mini passed BIAF and was rejected for two altered MEDS
quotations. All four declared incomplete materiality coverage and kept materiality
unresolved. This development-informed sample is not independent accuracy evidence
and does not test a real provider's sufficient-coverage conclusion. Two Mini calls
took more than 60 seconds end-to-end using the acceptance transport's 180-second
read timeout. The CLI now defaults to the same 180-second read timeout, configurable
with `--read-timeout-seconds`. This is a socket read timeout, not a total request
deadline or guarantee of success. The client uses a fixed endpoint, ignores ambient
proxy/netrc settings, disallows redirects, and makes no automatic retries. A timeout
keeps the reserved attempt blocked even if a later invocation requests more time.
New calls persist `TRANSPORT_CONFIGURED` with `openai-responses-http-v2` and the
actual timeout settings before dispatch, without credentials. Historical requests
and responses are not relabeled; the v5 research prompt/parser are unchanged.

- The complete text of the three governing masters, with matching document IDs, versions, revisions and content digests. This text comes from a separate authorized document read, not discovery sources or model output.
- Every source in one immutable evidence packet, clearly separated as untrusted data. Source instructions cannot add tools or broker permissions.
- The review criteria and a strict structured-output schema. Model output contains assessments, rationales and exact source quotes only. The program assigns the packet identity, actual returned model, implementation/prompt version, timestamps and trace IDs.

The client supplies no tools, uses a fixed HTTPS endpoint, disables redirects and does not follow evidence URLs. It sets `store=false`, which is not a claim of zero provider retention. Quotes must uniquely match their source; the program calculates offsets. A refusal, truncated/incomplete response, tool output, missing criterion, false/ambiguous citation or extra approval field blocks the result.

Matching citations establish provenance only. A supported claim can still be wrong; all outputs remain `RESEARCH_ONLY`, `eligible_for_handoff=false`, `semantic_verification=NOT_ESTABLISHED`. Existing snapshot approvals are not refreshed. This initial reviewer assesses captured evidence retrospectively and cannot produce prospective confirmation.

### Lossless source encoding

Reviewer implementation `1.1.0-automated-research` / prompt `governed-research-v2` sends each source's complete `text` once. That field already contains the canonical JSON representation of `raw`; sending both duplicated the same evidence. Before omitting the redundant `raw` field from the transport view, the code verifies matching representations, unique source IDs, source digests, and exact reconstruction of every original packet field and its digest. Original packet files, source text, citation offsets, IDs, trace, timestamps, negative evidence and full governing masters remain unchanged. Nothing is summarized, selected by keyword or silently truncated.

Request identity changes with the explicitly versioned encoding. `review_attempts.py` checks the exact version-appropriate evidence message before reserving a call. Supported v1 historical requests/results retain their own implementation and prompt attribution and can recover saved responses without a new provider call. Unknown/mismatched versions fail closed; an existing ledger's call budget is not reset. This is transport compatibility, not acceptance of model accuracy or a change to strategy methodology.

Measured on the September 18 research collection: TEN's request fell from 402,869 to 232,450 UTF-8 bytes, below the existing 250,000-byte limit. After recovering a separate long FEAM filing, its complete request is still 661,821 bytes and remains blocked. Source collection and model-request limits are different; neither is a token count, cost estimate or model-context guarantee. The API continues to receive developer instructions and untrusted user evidence as separate inputs, consistent with [OpenAI text-generation documentation](https://developers.openai.com/api/docs/guides/text).

## Private master manifest

Each entry of the `strategy`, `experiment`, `automation` object has:

```text
document_id, version, revision_id, read_at, text, text_sha256
```

Use the actual full document text, SHA-256 of its UTF-8 bytes and truthful read time. IDs/versions/revisions must match the packet. Re-read changed masters and capture new evidence under their actual revisions; never rewrite old attribution. A digest detects content changes, not whether a supplied export is authentic or complete. The authorized capture process remains responsible for that provenance.

## Prepare without making an API call

The CLI first runs [offline code checks](README-code-review.md). Records with no captured catalyst text are held for evidence retrieval; infrastructure records are excluded from this ordinary research route. Both stop before request preparation or credential access, even with `--dispatch`. For the full funnel, use `run_code_review.py` first. Passing a code check never establishes semantic qualification.

Use the existing development/journal Python environment; this adds no package dependency.

```text
python run_research_reviewer.py --packet PRIVATE_PACKET.json --masters PRIVATE_MASTERS.json --model SELECTED_MODEL_ID --max-output-tokens 6000 --max-input-bytes 250000 --output PRIVATE_OUTPUT
```

The model must be explicitly selected and its availability/cost verified before dispatch. The token/byte values above are infrastructure resource limits, not strategy thresholds. Oversized inputs are rejected rather than silently truncated. Preparation writes a complete reviewable request and makes zero model calls.

## Explicit model test

Supply `OPENAI_API_KEY` through private runtime secret storage. Do not paste it in chat, command arguments, the master manifest, the ledger or git. Append:

```text
--dispatch --ledger PRIVATE_OUTPUT/attempts.sqlite --max-calls 1
```

`--dispatch` permits a potentially billable request. Do not use it before account/model/budget approval. The ledger's fixed call budget persists across restarts; it cannot be silently raised. Output-token limits and byte limits bound each configured request, but this is **not a dollar spending cap**, and a different ledger has a separate budget. Confirm prices and provider-side spending controls separately. No batch of the full discovery funnel is automatically dispatched.

## Attempt history and recovery

The private SQLite ledger uses full synchronous writes and a committed reservation before the HTTP request. A second process cannot send the same request while that reservation exists. A timeout or crash before a durably saved response leaves an unresolved barrier; the program never automatically repeats that request. Failures consume the reserved call slot because provider billing may have occurred.

Received responses are saved before local validation. A restart can validate that saved response without another API call. Completed results are verified against the original saved response and reused. Append-only request/event records preserve prior attribution; no application update/delete operation is offered. SQLite is local private storage, not a multi-host hosted queue or a cryptographic audit service. Do not remove a ledger to bypass an ambiguous-attempt barrier. Resolve it against provider records before explicitly authorizing any new attempt.

The CLI prints only status, IDs, paths and fixed error types. Provider error bodies and credentials are not printed. The ledger/request files contain sensitive strategy/source material and successful provider output, so they require appropriate filesystem permissions and retention controls.

## Independent assessment

For saved v14 drafts, use the [offline completeness-review procedure](README-completeness-review.md)
to record scoped judgments about fees, conditions, timing and counterevidence.
This separate author-review record does not establish independent acceptance and
does not change the model prompt or historical admission results.

`review_evaluation.compare` validates both review artifacts and requires a separately attributed, source-backed reference. It records criterion denominators, agreement/disagreement, model abstentions, unresolved references and supported claims that the reference does not support. It retains both rationales and artifact IDs.

Assessor identity, method version, whether the reference preceded the model response, and independence limitations must be supplied. The comparison rejects self-attribution but cannot verify real-world assessor independence. It introduces no passing percentage. A schema-valid result or high agreement count cannot activate the reviewer.

```text
python review_evaluation.py --packet PRIVATE_PACKET.json --model-result PRIVATE_MODEL_RESULT.json --reference PRIVATE_REFERENCE_ARTIFACT.json --provenance PRIVATE_REFERENCE_PROVENANCE.json --output PRIVATE_OUTPUT
```

The reference uses the existing validated review-artifact format, with exact source-span citations. Provenance fields are `assessor_id`, `method_version`, boolean `created_before_model_response`, and an `independence_limitations` list. A timing declaration that contradicts artifact timestamps is rejected. Reference source truth and independence still require external assessment.

Before acceptance, use the cases in [REVIEW-METHOD-PROPOSAL.md](REVIEW-METHOD-PROPOSAL.md), freeze the source-backed references separately from model outputs, inspect all unsupported positives and disagreements, and preserve unresolved cases. Engineering mocks are not independent semantic assessment, Strategy #1 evidence, trades or retrospective opportunities.

## Verification and remaining work

Run `python -m pytest -q`. Tests use isolated fixtures and mocked provider responses only: full-master binding, source separation, request limits, refusals/incomplete outputs, citation/criterion checks, attribution, concurrency, durable reservation, lost replies, local response recovery and reference comparison. They do not establish provider/model accuracy or live API compatibility.

A live API test still requires a securely configured key, selected model and bounded approved spend. Independent review, current measurement/retrieval adapters, accepted live freshness/review policy, hosted credentials/storage and notification delivery remain outstanding. No production configuration or governing master is changed here.

API contract: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs). Checked September 18, 2026. Runtime compatibility must still be verified against the selected accessible model.
## Latest provider comparison

See [v17 provider comparison](README-scope-comparison.md): four calls cost
$1.177576; both GPT-5.5 answers passed technical validation and both Mini answers
were rejected for other contract errors. One admitted answer still omitted
source terms. No independent semantic acceptance or unattended qualification.

## v18 provider comparison

The [v18 paired comparison](README-typed-comparison.md) records four new historical
infrastructure answers, their original outcomes, attributed source review and cost.
It does not approve either model for unattended qualification.
