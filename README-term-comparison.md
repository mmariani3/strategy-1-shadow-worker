# v16 provider comparison — September 22, 2026 Pacific

## Result

The economic inventory improves visibility of what a model recorded, but does not
establish reliable extraction. GPT-5.5 passed both structural checks; Mini failed
both with `INVENTORY_SCOPE_MISMATCH`. Source review found revisions necessary in
three answers. No material defect was identified in the fourth answer within the
finite author checklist. **Neither model is accepted for unattended qualification.**

| Historical document | Model | Original structural outcome | Inventory terms | Author source review | Token-based cost USD |
| --- | --- | --- | ---: | --- | ---: |
| WBA | gpt-5-mini | Rejected: scope mismatch | 5 | Revisions required | 0.0316445 |
| WBA | gpt-5.5 | Research draft admitted | 7 | Revisions required: approval wording | 0.4376200 |
| JNPR | gpt-5-mini | Rejected: scope mismatch | 2 | Revisions required | 0.0266075 |
| JNPR | gpt-5.5 | Research draft admitted | 6 | Scoped author review recorded | 0.4349300 |
| **Total** | | **4 calls, no paid retries** | | **No semantic acceptance** | **0.9308020** |

The two admitted outputs' mandatory host summaries preserve **all 13 recorded
terms exactly**, including conditions, timing, qualifications and unresolved text.
This does not recover facts the model omitted before creating its inventory.
Rejected original envelopes remain rejected and unmodified.

## Sources and evaluation design

Source documents were newly captured and had no exact document-body overlap with
the prior 101 provider attempts:

- [WBA acquisition announcement, March 6, 2025](https://corporate.walgreens.com/news-and-stories/press-releases/2025/wba-definitive-agreement-acquired-by-sycamore-partners/).
- [HPE/Juniper announcement, January 9, 2024, SEC exhibit](https://www.sec.gov/Archives/edgar/data/1043604/000119312524005659/d107225dex991.htm).

These are selected historical acquisition releases, not live scans or a
representative sample of catalyst types. Full captured text, navigation and
governing masters were retained. No truncation or reduced test allowance.
Request sizes were 168,792/168,789 bytes for WBA and 170,460/170,457 for JNPR
(Mini/GPT-5.5); limits remained **250,000 input bytes and 12,000 output tokens**.

The source-only author reference froze **16 anchors** before model responses.
Subsequent assessment compared the original inventory, narrative and support
clauses with those anchors. Anchor relevance depends on the answer's declared
scope; optional context is not automatically treated as an omission. No new
numerical completeness threshold or strategy rule was introduced.

The implementation author performed this review. It is **not independent
acceptance**: the author saw search snippets about later outcomes, excluded them
from the model inputs and source judgments, and models may already know these
historical transactions. The currently served pages do not establish unchanged
historical content or availability at the original announcement time.

Local adapters explicitly use `INFRASTRUCTURE_TEST`. Synthetic run/item IDs are
marked as such; phase/session fields are schema placeholders, not market-session
observations. Candidate, signal and journal IDs are null. All results are
`INFRASTRUCTURE_EVALUATION` and ineligible for handoff or Strategy #1 evidence.

### Capture and harness limitations

- WBA raw HTTP bytes survived a local capture-metadata construction error. Its
  original response headers were lost; retained HTML was parsed as UTF-8. This
  recovery is recorded in the capture, without overwriting the body.
- HPE's issuer-site robots request timed out twice. Its public SEC exhibit was
  captured instead; no access restriction was bypassed.
- The ordinary discovery CLI correctly returned `EXCLUDED_INFRASTRUCTURE`, with
  zero requests/reservations/calls. A wrapper initially mislabeled that return as
  draft availability. The misleading zero-call summary is retained with an
  explicit correction and an empty-ledger hash.
- A separately frozen local provider-test harness then used the existing
  `execute_once` ledger, provider, frozen requests and parser. It asserts fixture
  exclusion and null handoff IDs. **This tests the provider path, not discovery CLI
  dispatch.** Production CLI behavior and repository runtime code were unchanged.

## Findings and next corrections

| Finding | Concrete evidence | Current protection / next correction | Remaining limitation |
| --- | --- | --- | --- |
| Redundant scopes differ | Both Mini envelopes use different inventory/narrative scope strings | Existing equality guard rejects before admission; design a single authoritative scope representation in a separately versioned change | Do not repair historical answers or relax the guard on these results. |
| Economic type and attribution errors | WBA Mini labels a future closing payment a reported result and conflates transaction valuation components with contingent-payment deductions | Preserve original failure; require source-grounded type/condition review and targeted offline regressions | Valid passages do not establish accurate prose. |
| Conditions shorten despite full citations | WBA GPT-5.5 retains unaffiliated shareholder approval but omits majority-of-votes-cast and the exact Pessina-or-Sycamore exclusion | Author review records `APPROVALS` revision; preserve actual decision-relevant condition wording | Host retention reproduces omissions faithfully. |
| Chosen scope is not fully inventoried | JNPR Mini declares synergy scope but records only consideration and financing; leverage forecast/dependencies disappear | Review source-to-inventory coverage before promoting any method | A finite checklist is not an exhaustive source inventory. |
| Event, publication and call times become confused | JNPR Mini places conference-call timing under publication timing; actual announcement date is absent | Keep separate source roles and assess semantic time tags offline | A valid time-category enum does not prove the choice is correct. |
| Stronger answer remains a limited result | JNPR GPT-5.5 retains consideration, funding, relative forecast periods, leverage dependencies and downside; no material defect found within its scoped checklist | Record `SCOPED_REVIEW_RECORDED`, not acceptance | Two selected events and author review cannot establish reliability. |
| Summary may drop already recorded fields | Both admitted summaries verified exact against original inventories: 7+6 terms | Existing deterministic projection and verifier work on these provider outputs | Neither false assertions nor missing terms are fixed by lossless copying. |

The acquisition-price and timing findings above are historical source-extraction
checks, not investment recommendations or retrospective executions. Source
details and exact original-draft paths are preserved in the private attributed
reviews; citation coverage is reported separately from meaning.

## Reproducibility and cost

- **781 tests passed** (`PYTHONPATH=.deps python -m pytest -q`, 45.82 seconds).
- **105 total saved outcomes replay unchanged:** 47 research admissions and 58
  rejections. This includes all 101 prior outcomes and four new calls.
- Prior 17 ledger hashes unchanged; new provider ledger contains exactly four
  reserved calls and four durable received responses, recorded before validation.
- Four source-location audits and four attributed reviews reproduced exactly.
  Every admitted summary passed exact JSON retention verification. No migration.
- Runtime: local `a5998982213db9db227919a2d6c420cc229e0177`; GitHub
  `17b804c6259dd786d71c84394713df612f309f1e`; matching tree
  `638a465eb1f989015599152d9928dc71a4721f39`.
- Frozen plan SHA-256:
  `e19737fa00a8ebb642ad0103fa65be6ac64a300f50cd2cd46ebf6582be4bae75`.
- Verification ID:
  `7309db69ea450af589e9cac53697e76717465f83d303440554ce99a96d6a7977`.

Official rates were rechecked for [gpt-5-mini](https://developers.openai.com/api/docs/models/gpt-5-mini)
and [gpt-5.5](https://developers.openai.com/api/docs/models/gpt-5.5).
Costs use returned input/cached/output tokens and published rates, not settled
invoices. Live balance before testing was $5.81, with auto-reload off; the
conservative four-call allowance was $2.649043. The post-test UI still displayed
$5.81, so it had not reflected the full cost. Allowing one cent for rounding and
subtracting this run gives an estimated remaining **$4.869198**, assuming no
unrelated spending. No credits were purchased or billing settings changed.

## Boundaries and publication

This step changes documentation only: this report and the link from
`README-term-inventory.md`. Local evaluation helpers and private evidence are not
production application changes. No methodology, risk, observation eligibility,
synced `sources/`, Journal or broker settings changed. The living Strategy v0.3,
Experiment v0.5 and Automation v0.4 revisions were reread and matched the stored
full masters.

Draft PR #9 remains stacked on #8 and unmerged. No deployment or execution
enablement. SHADOW and disabled broker execution remain repository boundaries;
**live runtime configuration and Journal state were not reverified.**

Next work is an offline, versioned correction for scope duplication and faithful
condition/time recording, followed by targeted checks before another paid run.
These sources and four model outputs are now development evidence, not a fresh
independent acceptance set.
