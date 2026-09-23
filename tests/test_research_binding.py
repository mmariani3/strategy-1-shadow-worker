"""Synthetic infrastructure cases only. No live provider or Strategy observations."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from evidence_review import canonical, digest
from research_binding import (VERSIONS, INSTRUCTIONS, prepare_binding_request,
    validate_binding_request, citation_projection, binding_report, binding_checklist)
from research_nature import validate_natures
from research_reviewer import parse_response, ReviewBlocked
from research_field_review import field_review, record_field_assessment, ledger_inputs
from research_explicit_review import render_explicit_review
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_nature import nature_case
from test_research_fields import assessment
from test_research_explicit_integration import FakeProvider


def references(x):
    for row in x['term_classifications']:
        row.pop('core_passages')
        for entry in row['amount_natures']: entry.pop('passages')
    x['materiality_term_indices'] = list(range(len(x['draft']['economic_inventory']['terms'])))
    scopes = dict(EVENT_OCCURRENCE='OCCURRED', PUBLICATION='PUBLICATION', NOT_TEMPORAL='ATEMPORAL')
    x['materiality_clause_roles'] = [dict(clause_index=i, temporal_scope=scopes[c['time_basis']],
        reason='Synthetic role annotation, not source truth.') for i, c in
        enumerate(x['draft']['research']['materiality_coverage']['support']['clauses'])]
    return x


def binding_case(linked_case):
    p, old, x, ref, _, m = nature_case(linked_case)
    references(x)
    return p, prepare_binding_request(p, m, 'offline-fixture', 12000, 250000, NOW), x, ref, old, m


def test_full_input_and_frozen_request_reconstruction(linked_case):
    p, r, x, _, old, m = binding_case(linked_case)
    assert validate_binding_request(p, r)[1] == old
    assert r['body']['input'][1:] == old['body']['input'][1:]
    assert r['body']['input'][0]['content'].endswith(INSTRUCTIONS)
    schema = r['body']['text']['format']['schema']
    prior = old['body']['text']['format']['schema']
    assert all(schema['$defs'][k] == v for k, v in prior['$defs'].items() if k in schema['$defs'])
    assert 'core_passages' not in schema['$defs']['TermReference']['properties']
    assert 'passages' not in schema['$defs']['AmountReference']['properties']
    assert schema['additionalProperties'] is False
    size = len(canonical(r['body']).encode())
    assert prepare_binding_request(p, m, 'offline-fixture', 12000, size, NOW) == r
    with pytest.raises(ReviewBlocked, match='NO_TRUNCATION'):
        prepare_binding_request(p, m, 'offline-fixture', 12000, size-1, NOW)


def test_complete_citations_are_bound_by_identity_not_array_position(linked_case):
    _, _, x, _, _, _ = binding_case(linked_case)
    x['term_assertions'].reverse()
    x['term_classifications'].reverse()
    before = deepcopy(x)
    projected = citation_projection(x)
    assertions = {a['term_index']: a for a in x['term_assertions']}
    for row in projected['term_classifications']:
        assert row['core_passages'] == assertions[row['term_index']]['passages']
        for amount in row['amount_natures']:
            assert amount['passages'] == x['draft']['economic_inventory']['terms'][row['term_index']]['amounts']['entries'][amount['entry_index']]['passages']
    assert x == before
    assert projected['draft'] == x['draft'] and projected['term_assertions'] == x['term_assertions']
    # No projected citations leak into the recorded original or its checklist.
    assert all('core_passages' not in item['original_value'] for item in binding_checklist(x, 'fixture') if item['kind']=='ECONOMIC_NATURE_DECLARATION')


@pytest.mark.parametrize('bad', ['missing_term', 'duplicate_term', 'out_of_range', 'boolean',
    'missing_amount', 'duplicate_amount', 'missing_core', 'core_duplicate', 'extra_citations',
    'extra_amount_citations', 'wrong_nature', 'blank_reason', 'blank_scope',
    'summary_missing', 'summary_duplicate', 'summary_boolean', 'summary_negative'])
def test_invalid_references_fail_closed(linked_case, bad):
    _, _, x, _, _, _ = binding_case(linked_case)
    rows = x['term_classifications']; row = next(r for r in rows if r['amount_natures'])
    amount = row['amount_natures'][0]
    if bad == 'missing_term': rows.pop()
    if bad == 'duplicate_term': rows.append(deepcopy(row))
    if bad == 'out_of_range': row['term_index'] = 99999
    if bad == 'boolean': row['term_index'] = True
    if bad == 'missing_amount': row['amount_natures'].pop()
    if bad == 'duplicate_amount': row['amount_natures'].append(deepcopy(amount))
    if bad == 'missing_core': x['term_assertions'].pop()
    if bad == 'core_duplicate': x['term_assertions'].append(deepcopy(x['term_assertions'][0]))
    if bad == 'extra_citations': row['core_passages'] = [1]
    if bad == 'extra_amount_citations': amount['passages'] = [1]
    if bad == 'wrong_nature': amount['nature'] = 'FORECAST' if amount['nature'] != 'FORECAST' else 'REPORTED_RESULT'
    if bad == 'blank_reason': amount['reason'] = ' '
    if bad == 'blank_scope': row['qualification_scope'] = ' '
    if bad == 'summary_missing': x['materiality_term_indices'].pop()
    if bad == 'summary_duplicate': x['materiality_term_indices'].append(x['materiality_term_indices'][0])
    if bad == 'summary_boolean': x['materiality_term_indices'][0] = True
    if bad == 'summary_negative': x['materiality_term_indices'][0] = -1
    with pytest.raises(ValueError): citation_projection(x)


@pytest.mark.parametrize('bad', ['missing', 'duplicate', 'boolean', 'mismatch', 'prospective', 'unresolved', 'blank'])
def test_summary_temporal_conflicts_reject_without_mutation(linked_case, bad):
    _, _, x, _, _, _ = binding_case(linked_case)
    clauses = x['draft']['research']['materiality_coverage']['support']['clauses']
    roles = x['materiality_clause_roles']; assert roles
    if bad == 'missing': roles.pop()
    if bad == 'duplicate': roles.append(deepcopy(roles[0]))
    if bad == 'boolean': roles[0]['clause_index'] = True
    if bad == 'mismatch':
        clauses[0]['time_basis'] = 'NOT_TEMPORAL'; roles[0]['temporal_scope'] = 'OCCURRED'
    if bad == 'prospective':
        clauses[0].update(statement='Future benefits beginning late 2025 and into 2026 and beyond.', time_basis='NOT_TEMPORAL')
        roles[0]['temporal_scope'] = 'PROSPECTIVE'
    if bad == 'unresolved': roles[0]['temporal_scope'] = 'UNRESOLVED'
    if bad == 'blank': roles[0]['reason'] = ' '
    before = deepcopy(x)
    with pytest.raises(ValueError): citation_projection(x)
    assert x == before


def test_linked_forecast_keeps_all_timing_and_qualifications(linked_case):
    p, r, x, _, _, _ = binding_case(linked_case)
    # Existing full economic terms supply summary content without flattening time.
    report = binding_report(p, r, canonical(x))
    assert len(report['materiality_economic_links']) == len(x['draft']['economic_inventory']['terms'])
    for link in report['materiality_economic_links']:
        assert link['term'] == x['draft']['economic_inventory']['terms'][link['term_index']]
        assert link['assertion'] in x['term_assertions']
    # Source meaning cannot be proved by consistent roles; preserve that limit.
    x['materiality_clause_roles'][0]['temporal_scope'] = 'ATEMPORAL'
    x['draft']['research']['materiality_coverage']['support']['clauses'][0].update(
        statement='An anticipated future financial benefit.', time_basis='NOT_TEMPORAL')
    citation_projection(x)
    assert any(i['kind']=='TEMPORAL_CLAUSE' for i in binding_checklist(x, r['request_id']))


@pytest.mark.parametrize('bad', ['instruction', 'schema', 'source', 'authority', 'tools', 'zero_limit', 'bool_limit'])
def test_request_tampering_is_blocked_before_reservation(linked_case, bad):
    p, r, x, _, _, _ = binding_case(linked_case)
    if bad == 'instruction': r['body']['input'][0]['content'] += 'x'
    if bad == 'schema': r['body']['text']['format']['schema']['required'] = []
    if bad == 'source': r['body']['input'][-1]['content'] += 'x'
    if bad == 'authority': r['masters_digest'] = 'x'
    if bad == 'tools': r['body']['tools'] = [dict(type='web_search')]
    if bad == 'zero_limit': r['body']['max_output_tokens'] = 0
    if bad == 'bool_limit': r['body']['max_output_tokens'] = True
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    ledger = AttemptLedger(ledger_path(), 1); provider = FakeProvider(reply(x))
    try:
        with pytest.raises(ReviewBlocked, match='BINDING_REQUEST_MISMATCH'): execute_once(ledger, p, r, provider, lambda: NOW)
        assert provider.calls == 0 and ledger.db.execute('select count(*) from requests').fetchone()[0] == 0
    finally: ledger.close()


def test_failure_preserved_with_no_retry(linked_case):
    p, r, x, _, _, _ = binding_case(linked_case)
    x['materiality_clause_roles'][0]['temporal_scope'] = 'PROSPECTIVE'
    raw = reply(x); provider = FakeProvider(raw); ledger = AttemptLedger(ledger_path(), 1)
    try:
        with pytest.raises(ReviewBlocked, match='RESPONSE_VALIDATION_FAILED'): execute_once(ledger, p, r, provider, lambda: NOW)
        assert ledger.events(r['request_id'])['RECEIVED']['payload'] == raw
        assert 'COMPLETED' not in ledger.events(r['request_id'])
        with pytest.raises(ReviewBlocked): execute_once(ledger, p, r, provider, lambda: NOW)
        assert provider.calls == 1
    finally: ledger.close()


def test_original_review_and_frozen_v24_remain_exact(linked_case):
    p, r, x, ref, old, _ = binding_case(linked_case)
    old_original = citation_projection(x)
    raw = reply(x); raw['output'][0]['content'][0]['text'] = json.dumps(x, indent=2)
    path = ledger_path(); ledger = AttemptLedger(path, 1); provider = FakeProvider(raw)
    try:
        result = execute_once(ledger, p, r, provider, lambda: NOW)
        assert execute_once(ledger, p, r, provider, lambda: NOW) == result and provider.calls == 1
    finally: ledger.close()
    before = sha256(path.read_bytes()).hexdigest()
    assert ledger_inputs(path, r['request_id'], p) == (r, raw, NOW)
    report = field_review(p, r, raw, NOW, ref)
    assert report['original_draft'] == x and report['original_provider_response'] == raw
    assert report['original_response_text'] == raw['output'][0]['content'][0]['text']
    assert report['field_items'] == binding_checklist(x, r['request_id'])
    assert report['implementation_version'] == '1.3.0-summary-binding-review'
    assert result['research_binding']['economic_inventory']['implementation_version'] == VERSIONS[0]
    assert result['research_binding']['materiality_economic_links']
    assert not result['economic_summary']['eligible_for_handoff']
    a = assessment(report, 'SUPPORTED'); a['decisions'][-1]['finding'] = 'REVISION_REQUIRED'
    reviewed = record_field_assessment(p, r, raw, NOW, ref, a, NOW)
    assert reviewed['status'] == 'REVISIONS_REQUIRED' and not reviewed['eligible_for_handoff']
    assert reviewed['semantic_acceptance'] == 'NOT_ESTABLISHED'
    assert render_explicit_review(report) == render_explicit_review(json.loads(canonical(report)))
    assert sha256(path.read_bytes()).hexdigest() == before
    assert parse_response(p, old, reply(old_original), NOW)['research_binding']['explicit_response_contract']['original_draft'] == old_original
    # An actual v24 citation mismatch still fails; the new adapter never repairs it.
    old_original['term_classifications'][0]['core_passages'] = [99999]
    with pytest.raises(ValueError, match='NATURE_SOURCE_BINDING_MISMATCH'): validate_natures(old_original)


def test_unresolved_core_and_empty_summary_do_not_manufacture_evidence(linked_case):
    p, r, x, _, _, _ = binding_case(linked_case)
    x['term_assertions'][0].update(status='UNRESOLVED', statement='', passages=[], reason='Core is unavailable in this synthetic case.')
    projected = citation_projection(x)
    assert projected['term_classifications'][0]['core_passages'] == []
    x['draft']['research']['materiality_coverage']['support']['clauses'] = []
    x['materiality_clause_roles'] = []
    report = binding_report(p, r, canonical(x))
    assert report['materiality_economic_links'][0]['assertion']['status'] == 'UNRESOLVED'
    assert report['original_draft'] == x


def test_references_cannot_bypass_original_source_validation(linked_case):
    p, r, x, _, _, _ = binding_case(linked_case)
    x['term_assertions'][0]['passages'] = [999999]
    # An identical projected list is not evidence: inherited source validation rejects it.
    with pytest.raises(ValueError): binding_report(p, r, canonical(x))


@pytest.mark.parametrize('scope,basis', [('OCCURRED','EVENT_OCCURRENCE'), ('PUBLICATION','PUBLICATION'),
    ('ATEMPORAL','NOT_TEMPORAL'), ('MARKET_OBSERVATION','MARKET_OBSERVATION'), ('CAPTURE','CAPTURE')])
def test_all_existing_general_temporal_bases_remain_representable(linked_case, scope, basis):
    _, _, x, _, _, _ = binding_case(linked_case)
    x['materiality_clause_roles'][0]['temporal_scope'] = scope
    x['draft']['research']['materiality_coverage']['support']['clauses'][0]['time_basis'] = basis
    before = deepcopy(x)
    citation_projection(x)
    assert x == before
