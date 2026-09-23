# Explicit responses in the research test runner

The opt-in `1.20.0-automated-research` / `governed-research-v21` route connects
the explicit response contract to the existing attempt ledger and an offline
source-review export. The v20 command-line default is unchanged. Frozen
`governed-research-v21-preview` requests remain unsupported by the dispatcher;
they must not be relabeled or sent as integrated requests.

## Behavior and verification checklist

| Finding | Implementation | Regression evidence |
| --- | --- | --- |
| Complete response must survive parsing | `research_explicit.py`, `research_reviewer.py`: original provider text and full wrapper retained in the required `research_binding.explicit_response_contract`; inherited checks use only an internal embedded projection | Pretty-printed original text, all extension fields, source links, trace and implementation attribution survive completion and replay |
| Invalid input must not reserve a call | `review_attempts.py`: exact request binding before reservation | Instructions, schema, sources, tools, storage setting, packet, master digest and request digest mutations fail before the provider |
| Failures must remain failures | Existing ledger records full RECEIVED response before validation and immutable FAILED outcome | Missing extensions, malformed JSON, refusal, incomplete response, multiple texts and old-shaped answer remain failed; no repair or retry |
| Retries and competing callers must not duplicate calls | Existing reservation and immutable event rules, applied to v21 | Completed replay returns exactly; received-only interruption recovers locally; ambiguous attempts stop; competing connections cannot both dispatch |
| Review must display every new assertion | `research_explicit_review.py`: read-only ledger export, JSON and inert HTML | Every rule explanation and term assertion, unresolved reasons, linked full passages, embedded timing/rule/term checklist and reference anchors are retained |
| Full sources and historical evidence must remain available | Captured originals, decoded substantive text, index gaps and complete catalog included | Escaping, JSON round-trip regeneration, original ledger hash preservation; historical replay performed separately |
| Historical versions and defaults must stay frozen | New version route and one added permitted review prompt version in `evidence_review.py` | Existing preview rejection and v20 default tests remain in place |

Tests are in `tests/test_research_explicit_integration.py`, alongside the frozen
preview and historical suites. All new responses are explicitly authored
synthetic infrastructure fixtures, not augmented or repaired model answers.
No database migration is required: existing request and event JSON stores the
complete response without schema changes.

Verified offline: **1,004 tests passed in 305.02 seconds**, including 28 new
integration regressions. All 117 saved outcomes replay unchanged (56 research
admissions, 61 rejections); all 22 original ledger hashes and previous evidence
artifacts match. Eighteen complete integrated requests were prepared but not sent
(163,025–231,213 bytes), with all 756 schema references resolved locally. FSI and
KDP remain blocked for both models under the unchanged 250,000-byte ceiling.
Current live revision IDs for all three masters matched before preparation.

Preservation/preparation manifest:
`9ba4b044b5405d0084f137af947b0b91ffdb969a99df350739ac36c20eb6cfb3`.

## Opt-in preparation and runner

Use `research_explicit.prepare_integrated_request` with the complete evidence
packet, current matching masters, explicitly selected model and unchanged limits.
Pass that request to `review_attempts.execute_once` with an isolated attempt
ledger and the chosen provider. Offline tests inject a fake provider. No new
automatic dispatch switch or credential-loading entrypoint has been added.

The registered runner route can invoke a real provider if a caller deliberately
supplies one. This change only tests that route offline. A paid trial still needs
a concrete budget, credit check, full input validation and separate authorization.

## Export a completed ledger answer without API calls

```text
python research_explicit_review.py --ledger attempts.sqlite \
  --request-id REQUEST_ID --packet packet.json --reference reference.json \
  --output reports
```

The command opens the ledger read-only, requires its original RECEIVED and
COMPLETED events, reparses at the original received timestamp and compares the
entire saved completion. It writes immutable, content-addressed JSON and HTML.
It cannot dispatch, read credentials, repair failures or create missing ledgers.
Failed/ambiguous attempts remain in the ledger and cannot be exported as successful
reviews. Existing historical review tools continue to use their original formats.

## Limits and boundaries

This export is a source-review checklist, not recorded adjudication. It does not
automatically approve assertions or establish independent review. The existing
v20 attributed-assessment recorder is not advertised as accepting v21 wrappers.
Valid citations and filled fields still permit false, generic or incomplete prose.
Provider schema acceptance and real v21 answer quality remain unverified.

No API calls, keys, billing settings, production services, Journal entries or
synced sources are needed for this offline step. No Strategy #1 v0.3 or Experiment
Plan v0.5 methodology, risk limits or eligibility changes. SHADOW and disabled
broker execution remain repository boundaries; live runtime configuration has
not been verified. No merge or deployment is included.
