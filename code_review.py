"""Offline research checks, not a second Strategy Worker or an approval authority."""
from collections import Counter
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from hashlib import sha256
from pathlib import Path

from evidence_review import (CRITERIA, aware, build_packets, canonical, check_authorities,
                             digest, unresolved_draft, validate_draft)
from review_contract import CURRENT_FIELDS, review_problem

VERSION = '1.0.0-code-review'
BOOL_FIELDS = set(CURRENT_FIELDS) - {'market_regime', 'realized_daily_loss_dollars', 'executed_trades_today'}
BOOL_FIELDS |= {'catalyst_material', 'catalyst_verified', 'catalyst_cross_source_verified',
                'trigger_confirmed', 'clean_structure', 'consolidated_data', 'rvol_consolidated'}
ENTRY_MODELS = {'opening_range_premarket_high_break', 'vwap_reclaim_rejection', 'first_clean_pullback'}
SOURCE_KINDS = {'news', 'filing'}


def implementation():
    return VERSION + ';sha256=' + digest({name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ('code_review.py', 'evidence_review.py', 'review_contract.py')})


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('FINITE_NUMBER_REQUIRED')
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('FINITE_NUMBER_REQUIRED') from None
    if not result.is_finite():
        raise ValueError('FINITE_NUMBER_REQUIRED')
    return result


def verified_sources(packet, now):
    validate_draft(packet, unresolved_draft(packet, now), now)
    check_authorities(packet['authority_refs'], packet['captured_at'])
    sources = packet['sources']
    if len({s['source_id'] for s in sources}) != len(sources):
        raise ValueError('DUPLICATE_SOURCE_ID')
    for s in sources:
        if s['source_id'] != digest({'kind': s['kind'], 'raw': s['raw']}) or s['text'] != canonical(s['raw']):
            raise ValueError('SOURCE_CONTENT_MISMATCH')
        if aware(s['recorded_at']) > aware(packet['captured_at']):
            raise ValueError('SOURCE_RECORDED_AFTER_CAPTURE')
    return sources


def check_structured(raw, source_id, captured_at):
    """Check supplied values independently. Never fill a missing judgment with a default."""
    checks = []

    def add(name, status, detail, fields, values=None, authority='Automation Specification sections 3, 7, 9'):
        checks.append(dict(check=name, status=status, detail=detail, source_id=source_id,
                           fields=fields, values=values, authority=authority))

    missing = [f for f in CURRENT_FIELDS if raw.get(f) is None]
    add('required_inputs', 'UNRESOLVED' if missing else 'PASS',
        'Presence only; supplied judgments are not independently verified.', missing)
    for field in sorted(BOOL_FIELDS):
        value = raw.get(field)
        status = 'UNRESOLVED' if value is None else 'RECORDED_ASSERTION' if type(value) is bool else 'INVALID'
        add('assertion.' + field, status, 'No qualitative judgment inferred or refreshed.', [field], value)
    for field in ('market_data_source', 'trigger_definition', 'materiality_rationale'):
        v = raw.get(field)
        add('presence.' + field, 'PASS' if isinstance(v, str) and v.strip() else 'UNRESOLVED',
            'Nonblank text is not proof of semantic correctness.', [field])
    model = raw.get('entry_model')
    add('approved_entry_model', 'UNRESOLVED' if model is None else 'PASS' if model in ENTRY_MODELS else 'FAIL',
        'Approved model identifier only; setup quality still needs review.', ['entry_model'], model,
        'Strategy Rules section 5')
    regime = raw.get('market_regime')
    add('market_regime_label', 'UNRESOLVED' if regime is None else
        'PASS' if regime in ('Bullish', 'Bearish', 'Mixed', 'Choppy') else 'INVALID',
        'Label validation only.', ['market_regime'], regime, 'Strategy Rules section 3')
    for field, ceiling in [('realized_daily_loss_dollars', Decimal('100')), ('executed_trades_today', Decimal('3'))]:
        value = raw.get(field)
        status = 'UNRESOLVED'
        if value is not None:
            try:
                n = number(value)
                if n < 0 or (field == 'executed_trades_today' and n != n.to_integral_value()):
                    raise ValueError('INVALID_COUNTER')
                status = 'FAIL' if n >= ceiling else 'PASS'
            except ValueError:
                status = 'INVALID'
        add(field, status, 'Checks the supplied counter only; account state has not been refreshed.',
            [field], value, 'Strategy Rules section 6')
    for field in ('data_timestamp', 'catalyst_event_at', 'triggered_at', 'trigger_confirmed_at', 'reviewed_at'):
        value = raw.get(field)
        status = 'UNRESOLVED'
        if value is not None:
            try:
                status = 'PASS' if aware(value) <= aware(captured_at) else 'FAIL'
            except (ValueError, TypeError, AttributeError):
                status = 'INVALID'
        add('timestamp.' + field, status, 'Timezone/order check only; no freshness duration or actual event time inferred.',
            [field], value)
    try:
        problem = review_problem(raw, aware(captured_at))
    except (ValueError, TypeError, AttributeError):
        problem = 'REVIEW_INVALID'
    add('review_contract_at_capture', 'PASS' if problem is None else 'UNRESOLVED',
        problem or 'Supplied review interval matched at capture; it is not a current authorization.',
        ['session_date', 'current_review', 'data_timestamp', 'confirmation_review_id'])
    required, consolidated = raw.get('consolidated_data_required'), raw.get('consolidated_data')
    add('consolidated_requirement', 'UNRESOLVED' if type(required) is not bool else
        'FAIL' if required and consolidated is False else 'UNRESOLVED' if required and consolidated is not True else 'PASS',
        'Checks declarations only; feed provenance and entitlement still need verification.',
        ['consolidated_data_required', 'consolidated_data'])
    feed = raw.get('market_data_source')
    if isinstance(feed, str) and feed.strip().casefold() in ('iex', 'alpaca_iex', 'alpaca iex'):
        add('iex_consolidated_contradiction', 'FAIL' if consolidated is True or raw.get('rvol_consolidated') is True else 'PASS',
            'An explicitly IEX-only source cannot establish consolidated data.',
            ['market_data_source', 'consolidated_data', 'rvol_consolidated'])
    declared_sources = raw.get('catalyst_sources')
    if declared_sources is not None:
        valid = isinstance(declared_sources, list) and all(isinstance(s, dict) for s in declared_sources)
        names = {s.get('source', '').strip().casefold() for s in declared_sources
                 if isinstance(s.get('source'), str) and s['source'].strip()} if valid else set()
        add('distinct_named_sources', 'PASS' if valid and len(names) >= 2 else 'UNRESOLVED',
            'Distinct names do not prove independent reporting or the same underlying event.',
            ['catalyst_sources'], {'distinct_nonblank_names': len(names)})
    geometry_fields = ['direction', 'entry_price', 'stop_price', 'target_price']
    geometry_status, metrics = 'UNRESOLVED', None
    if all(raw.get(f) is not None for f in geometry_fields):
        try:
            entry, stop, target = (number(raw[f]) for f in geometry_fields[1:])
            if min(entry, stop, target) <= 0 or raw['direction'] not in ('LONG', 'SHORT'):
                raise ValueError('INVALID_GEOMETRY_INPUT')
            risk = entry - stop if raw['direction'] == 'LONG' else stop - entry
            reward = target - entry if raw['direction'] == 'LONG' else entry - target
            geometry_status = 'PASS' if risk > 0 and reward > 0 else 'FAIL'
            if geometry_status == 'PASS':
                rr = reward / risk
                qty = min(int((Decimal('50') / risk).to_integral_value(rounding=ROUND_FLOOR)),
                          int((Decimal('10000') / entry).to_integral_value(rounding=ROUND_FLOOR)))
                metrics = dict(risk_per_share=str(risk), reward_per_share=str(reward), planned_rr=str(rr),
                    maximum_qty_at_ruleset_ceilings=qty, dollar_risk=str(qty*risk), notional=str(qty*entry))
                add('reward_risk_floor', 'PASS' if rr >= Decimal('1.5') else 'FAIL',
                    'Arithmetic only; target/stop structural validity is not established.', geometry_fields,
                    str(rr), 'Strategy Rules section 6')
                add('clean_structure_requirement', 'UNRESOLVED' if Decimal('1.5') <= rr < 2 else 'NOT_APPLICABLE',
                    '1.5R–2R requires explicit valid clean-structure assessment; a boolean is not independent proof.',
                    ['clean_structure'], raw.get('clean_structure'), 'Strategy Rules section 6')
                add('position_ceiling', 'PASS' if qty > 0 else 'FAIL',
                    'Maximum arithmetic quantity under v0.3 ceilings, not a selected position or risk approval.',
                    geometry_fields, metrics, 'Strategy Rules section 6; Automation Specification section 5')
        except ValueError:
            geometry_status = 'INVALID'
    add('price_geometry', geometry_status, 'Directional positive-price geometry only.', geometry_fields, metrics,
        'Strategy Rules section 6')
    return checks


def inspect_packet(packet, now):
    sources = verified_sources(packet, now)
    checks, evidence_inventory = [], []
    for source in sources:
        kind, raw, sid = source['kind'], source['raw'], source['source_id']
        if kind in ('qualification_review', 'setup_review', 'candidate_snapshot'):
            if not isinstance(raw, dict):
                raise ValueError('STRUCTURED_SOURCE_INVALID')
            checks.extend(check_structured(raw, sid, packet['captured_at']))
        if kind == 'signal_snapshot':
            if not isinstance(raw.get('decision_inputs'), dict):
                raise ValueError('SIGNAL_INPUTS_INVALID')
            checks.extend(check_structured(raw['decision_inputs'], sid, packet['captured_at']))
        if kind in SOURCE_KINDS:
            # Filing metadata/URL is not a fetched filing body. Headlines remain research evidence.
            has_text = any(isinstance(raw.get(f), str) and raw[f].strip()
                           for f in ('headline_or_event', 'summary', 'text', 'content'))
            timestamp_status = 'UNRESOLVED'
            if raw.get('event_timestamp') is not None:
                try:
                    timestamp_status = 'PASS' if aware(raw['event_timestamp']) <= aware(packet['captured_at']) else 'FAIL'
                except (ValueError, TypeError, AttributeError):
                    timestamp_status = 'INVALID'
            evidence_inventory.append(dict(source_id=sid, kind=kind, has_captured_text=has_text,
                publication_or_filing_date=raw.get('event_timestamp') or raw.get('filing_date'),
                publication_timestamp_order=timestamp_status,
                actual_event_freshness='UNRESOLVED', source_independence='UNRESOLVED',
                full_document_retrieved='NOT_ESTABLISHED'))
    usable = sum(item['has_captured_text'] for item in evidence_inventory)
    route = 'REVIEW_REQUIRED' if usable else 'NEEDS_SOURCE_EVIDENCE'
    if packet['experiment_class'] == 'INFRASTRUCTURE_TEST':
        route = 'EXCLUDED_INFRASTRUCTURE'
    report = dict(implementation_version=implementation(), packet_id=packet['packet_id'],
        checked_at=now, as_of=packet['captured_at'], authority_refs=deepcopy(packet['authority_refs']),
        trace=deepcopy(packet['trace']), symbol=packet['symbol'], experiment_class=packet['experiment_class'],
        checks=checks, evidence_inventory=evidence_inventory, route=route,
        mechanical_integrity='HASHES_AND_SOURCE_TEXT_MATCH',
        gaps=deepcopy(packet['gaps']), discovery_coverage=deepcopy(packet['discovery_coverage']),
        structured_sources_checked=len({c['source_id'] for c in checks}),
        unresolved_criteria=list(CRITERIA), admission='RESEARCH_ONLY', eligible_for_handoff=False,
        execution_enabled=False, model_calls=0, journal_verification='NOT_CHECKED',
        limitations=['PASS refers only to the named mechanical check, never a strategy criterion.',
            'Supplied qualitative assertions, source independence and actual event freshness remain unverified.',
            'No current market/account state refreshed; no prospective confirmation or trade decision generated.',
            'Missing evidence is a retrieval task, not a rejection or proof that no opportunity exists.'])
    report['report_id'] = digest(report)
    return report


def plan_bundle(bundle, now, review_slots=0):
    """All records retained. A slot is proposed research work, never permission to spend."""
    if type(review_slots) is not int or review_slots < 0:
        raise ValueError('NONNEGATIVE_REVIEW_SLOTS_REQUIRED')
    packets = bundle['packets']
    if not packets:
        if bundle['run']['candidates_discovered'] != 0:
            raise ValueError('INCOMPLETE_FUNNEL')
    elif len({p['packet_id'] for p in packets}) != len(packets):
        raise ValueError('DUPLICATE_PACKET')
    # Rebuild from original records to validate completeness and cross-packet lineage.
    items, candidates, signals = [], [], []
    for packet in packets:
        sources = verified_sources(packet, now)
        if packet['authority_refs'] != packets[0]['authority_refs']:
            raise ValueError('MIXED_AUTHORITIES')
        if packet['captured_at'] != bundle['snapshot_captured_at']:
            raise ValueError('CAPTURE_MISMATCH')
        for source in sources:
            kind, raw = source['kind'], source['raw']
            if kind == 'discovery_run' and raw != bundle['run']:
                raise ValueError('RUN_MISMATCH')
            if kind == 'discovery_record': items.append(raw)
            if kind == 'candidate_snapshot': candidates.append(raw)
            if kind == 'signal_snapshot': signals.append(raw)
    snapshot = dict(run=bundle['run'], items=items, candidates=candidates, signals=signals,
                    captured_at=bundle['snapshot_captured_at'])
    if digest(snapshot) != bundle['source_snapshot_digest']:
        raise ValueError('SNAPSHOT_DIGEST_MISMATCH')
    if packets:
        rebuilt = build_packets(snapshot, packets[0]['authority_refs'], bundle['snapshot_captured_at'])
        if {p['packet_id']: p for p in rebuilt} != {p['packet_id']: p for p in packets}:
            raise ValueError('PACKET_LINEAGE_MISMATCH')
        if bundle['authority_digest'] != digest(packets[0]['authority_refs']):
            raise ValueError('AUTHORITY_DIGEST_MISMATCH')
    else:
        # Empty runs still need a finalized, attributable capture; no opportunities inferred.
        if (bundle['run'].get('status') not in ('COMPLETE', 'PARTIAL', 'DATA_UNAVAILABLE')
                or bundle['run'].get('experiment_class') not in ('STRATEGY_1', 'INFRASTRUCTURE_TEST')
                or bundle['run'].get('ruleset_version') != 'v0.3'
                or not aware(bundle['run']['created_at']) <= aware(bundle['snapshot_captured_at']) <= aware(now)):
            raise ValueError('INVALID_EMPTY_RUN')
    reports = [inspect_packet(p, now) for p in sorted(packets, key=lambda p: p['trace']['source_discovery_item_id'])]
    remaining = review_slots
    for report in reports:
        if report['route'] == 'REVIEW_REQUIRED':
            report['proposed_action'] = 'RESEARCH_REVIEW_SLOT' if remaining else 'DEFERRED_BUDGET_UNREVIEWED'
            remaining = max(0, remaining - 1)
        else:
            report['proposed_action'] = report['route']
        # Re-hash after adding routing; no prior report is rewritten.
        report['report_id'] = digest({k: v for k, v in report.items() if k != 'report_id'})
    result = dict(implementation_version=implementation(), source_bundle_digest=digest(bundle),
        checked_at=now, run_id=bundle['run']['id'], session_date=bundle['run']['session_date'],
        total_records=len(reports), proposed_review_slots=review_slots,
        counts=dict(Counter(r['proposed_action'] for r in reports)), reports=reports,
        selection_order='source_discovery_item_id; budget order is not opportunity ranking',
        admission='RESEARCH_ONLY', eligible_for_handoff=False, execution_enabled=False,
        model_calls=0, opportunity_count='UNKNOWN', semantic_review_complete=False,
        journal_verification='NOT_CHECKED')
    result['plan_id'] = digest(result)
    return result
