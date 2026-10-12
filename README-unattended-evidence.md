# Previous-session and setup evidence development — October 12, 2026

This package advances the mostly unattended Strategy #1 workflow. It adds an
explicit-date daily-bar reader and a pure setup-evidence builder. The October 12
follow-up connects them through shared authenticated evidence routes in Discovery
and a separate isolated staging app. They remain disconnected from scans,
qualification, evaluation, execution and database writes. The initial local
verification JSON records the earlier standalone state; the follow-up acceptance
plan records current readiness. No hosted result is implied by either document.

## Base and authority

The base is an isolated export of Git tree
`997de5b45e9b3162d2ad9b8616c0fb27a65b542e`, previously verified as the tree of
October 12's deployed commit `ae23b497021cba9b1649165246f801836bff5664`.
The original `discovery-run-reporting` checkout and its staged/unstaged work are
untouched. This directory is an exported development package, not a Git clone.
The follow-up changes only this copy of `discovery_coordinator.py` to include the
staging-only router; other original base files remain unchanged.
The archive is `../tooling/unattended-evidence-base.zip`; the final verification
record compares every exported base file to that archive.

The live Rules v0.3, Experiment v0.5 and Automation Specification v0.4 were read
for this work. Their respective authorities remain unchanged. This package
does not redefine qualification, trigger confirmation, research eligibility,
rollout approval or freshness/participation thresholds.

## What Monday established

The saved `../tooling/october12-scheduled-outcome.json` reports a passing isolated
collection/storage test with 4,286 acknowledged and independently verified
items. Its run remains PARTIAL and ineligible as Strategy #1 evidence. Cleanup
was verified then; this development package did not recheck live infrastructure.

The calendar selected October 9 as the previous session. All 4,286 snapshot
previous closes were unavailable: 4,282 had the wrong session and four had no
valid previous daily bar. In 4,281 snapshots, `dailyBar` carried October 9 while
`prevDailyBar` did not. This establishes the date mismatch that caused rejection;
it does not establish Alpaca's internal rollover timing. Monday's data, labels,
acceptance rule and result files are preserved. No `dailyBar` substitution or
retrospective correction of Monday's records has been made.

## Explicit-date reader

`prior_session_evidence.collect_prior_session_evidence(headers, symbols,
session_date, now=..., get=..., clock=...)` is an opt-in read-only adapter.

It reads the paper exchange calendar, selects the greatest open date before the
requested current session, and queries historical bars with explicit `1Day`,
`sip`, `raw`, `asof`, and New York date boundaries. It handles symbol-sorted
pagination, validates exact daily timestamps and OHLCV, and publishes a batch
only after pagination is exhausted. Missing symbols remain unavailable; a bad
or incomplete batch cannot promote its earlier pages. Previously completed
batches are retained with an explicit PARTIAL outcome. Errors are sanitized.

Operational caps are 200 symbols per batch, 20,000 symbols total, 120 pages and
a 120-second budget for starting requests. Socket timeouts do not replace a
process watchdog. There are no retries, redirects, writes, credential loaders,
snapshot fallbacks or automatic gap/qualification decisions.

Returned values are **raw prior-session daily-bar closes requiring review**.
They are not asserted to be official auction closes. Instrument identity,
corporate actions and symbol changes remain review requirements. A complete
collection can still contain missing bars and does not imply strategy readiness.

The implementation follows the official
[historical bars reference](https://docs.alpaca.markets/us/reference/stockbars)
for explicit feed, adjustment, date parameters and pagination. The
[Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) describes
New York daily-bar timestamps and historical symbol mapping. The
[snapshot reference](https://docs.alpaca.markets/us/reference/stocksnapshots-1)
describes relative daily fields; those fields are not the adapter's source.

**Still unverified:** actual authenticated hosted responses from this new
adapter, coverage/latency for the real universe, corporate-action treatment for
strategy use, and storage/integration of this separate evidence. Offline
fixtures cannot establish these. Do not alter the completed October 12 run to
test them.

## Setup evidence

`setup_evidence.build_setup_evidence(plan, observations, as_of=...,
previous_packet=...)` performs no I/O. It accepts an already specified approved
entry-model identifier, trigger and entry levels, structural rationale, stop,
target, invalidation conditions and source reference. It never chooses them.

The plan requires candidate/symbol/session identity, a prospective `recorded_at`,
and authority versions. Quotes and completed nonoverlapping bars require symbol,
SIP feed, an explicit non-delayed claim, source reference, event and receipt
times. Market samples before plan creation, future samples, different sessions,
wrong symbols, IEX, malformed prices and expired declared validity are rejected.
Source/feed claims are retained as claims, not independently authenticated facts.

Measurements include spread, observed OHLC/volume, risk/share and reward/risk.
Volume is only the sum of supplied bars; complete coverage and participation are
not inferred. A last close above a trigger is an observation, never confirmation.
VWAP, RVOL, relative strength, hold/retest and structural validity are not invented
from insufficient samples. Risk arithmetic does not approve levels or sizing.

Older catalyst or structural documents may be supplied separately as
`supporting_evidence`, with source reference, summary, available/received times
and the review fields they inform. These remain unreviewed source claims. They
cannot substitute for prospective trigger evidence. Full source collection,
verification and research-review acceptance remain separate work.

Every existing CurrentReview/current-condition requirement is mapped to needed
evidence and left UNRESOLVED. No default freshness lifetime is created. A declared
expiry can cause rejection, but a future expiry does not approve freshness.
Plan changes and changed market/context evidence alter their respective hashes;
hashes are content identities, not signatures or proof of review. Review reuse
is always false in this prototype. A separate accepted review must explicitly
bind to the current inputs before eventual integration.

All packets are labeled INFRASTRUCTURE_TEST and strategy-ineligible, with broker
execution and automatic confirmation disabled. No CurrentReview, candidate,
signal, live observation or order is created. The caller must not relabel these
prototype packets to bypass the governing workflow.

## Verification and next integration gates

New tests cover calendar holidays/DST, explicit session selection, malformed or
wrong-date bars, pagination failures/overlap, bounded requests, missing symbols,
source/time/feed mismatches, completed bars, duplicate volume, expired validity,
changed setup, context-source preservation, and attempts to inject approvals.
The inherited test suite blocks live HTTP. See the final local verification JSON
for the exact test result and base-file integrity comparison.

The evidence-route integration is now implemented and tested in both apps.
`shadow_evidence_api:app` is the isolated deployment entrypoint: health, one
fixed SPY/QQQ/IWM prior-session read route and a pure setup preview route. The
three ETFs are infrastructure probes, not discovered candidates. The preview
route cannot persist, qualify, promote or call the Worker. Authentication is
checked before parsing; oversized/invalid payloads receive sanitized errors.
Service identity, Rules version, commit presence and the October 12 window are
checked before evidence use. The desktop controller additionally pins the exact
deployment and source hash, verifies all other services suspended/off, requires
fresh launch evidence and renewed bounded credential authorization, starts a
separate suspension watchdog before resume, and durably claims each attempt.
The hosted negative preview uses empty inputs, not a manufactured market setup.

`shadow_evidence_workflow.attach_prior_evidence` is a pure attachment helper: it
preserves original snapshot dates, close-unavailable reasons and gap fields, and
adds a separate review-only namespace. It is not wired into historical records
or normal scans. Content hashes bind inputs; they are not signatures or source
verification. A prior-session result does not prove current quote freshness.

Remaining work includes normal collection/persistence integration after this
isolated acceptance, source-backed reviewer semantic
acceptance and full discovery coverage, and test restart/duplicate behavior.
A subsequent explicitly bounded hosted acceptance must validate the new dated
lookup and persistence prospectively. The complete unattended SHADOW lifecycle
and governing paper-execution rollout gates remain prerequisites to automated
paper orders. This package sets neither a first-trade date nor a new run schedule.
