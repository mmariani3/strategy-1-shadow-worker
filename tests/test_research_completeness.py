"""Offline infrastructure regressions. No genuine Strategy observations or APIs."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from evidence_review import canonical, digest, source
from research_facts import SUBSTANTIVE
from research_linked import numbered_passages
from research_completeness import (VERSIONS, INSTRUCTIONS, prepare_completeness_request,
    validate_completeness_request, coverage_projection, completeness_report, completeness_checklist)
from research_reviewer import parse_response, ReviewBlocked
from research_field_review import field_review, record_field_assessment, ledger_inputs
from research_explicit_review import render_explicit_review
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_binding import binding_case
from test_research_fields import assessment
from test_research_explicit_integration import FakeProvider


def complete_case(linked_case):
    p, old, x, ref, _, m = binding_case(linked_case)
    numbers = [n for n, row in numbered_passages(p).items() if row['category'] in SUBSTANTIVE]
    x['economic_source_coverage'] = [dict(passages=numbers, role='CORE',
        term_indices=list(range(len(x['term_assertions']))), reason='Synthetic scope assignment, not source truth.')]
    return p, prepare_completeness_request(p, m, 'offline-fixture', 12000, 250000, NOW), x, ref, old, m


def test_full_input_old_request_and_schema_binding(linked_case):
    p, r, x, _, old, m = complete_case(linked_case)
    assert validate_completeness_request(p, r)[1] == old
    assert r['body']['input'][1:] == old['body']['input'][1:]
    assert r['body']['input'][0]['content'] == old['body']['input'][0]['content'] + '\n' + INSTRUCTIONS
    schema = r['body']['text']['format']['schema']
    assert all(schema['$defs'][k] == v for k, v in old['body']['text']['format']['schema']['$defs'].items())
    assert set(schema['required']) == set(schema['properties'])
    assert all(d.get('additionalProperties') is False for d in schema['$defs'].values() if d.get('type') == 'object')
    size = len(canonical(r['body']).encode())
    assert prepare_completeness_request(p, m, 'offline-fixture', 12000, size, NOW) == r
    with pytest.raises(ReviewBlocked, match='NO_TRUNCATION'):
        prepare_completeness_request(p, m, 'offline-fixture', 12000, size-1, NOW)


@pytest.mark.parametrize('bad', ['missing', 'duplicate', 'metadata', 'unknown', 'bool', 'float',
    'term_missing', 'term_duplicate', 'term_negative', 'term_unknown', 'term_bool', 'blank_reason',
    'label_only', 'caution_only', 'unresolved_core', 'context_term', 'unresolved_sufficient', 'extra_field'])
def test_incomplete_or_invalid_accounting_fails_closed(linked_case, bad):
    p, _, x, _, _, _ = complete_case(linked_case)
    group = x['economic_source_coverage'][0]
    if bad == 'missing': group['passages'].pop()
    if bad == 'duplicate': group['passages'].append(group['passages'][0])
    if bad == 'metadata': group['passages'].append(next(n for n,r in numbered_passages(p).items() if r['category'] not in SUBSTANTIVE))
    if bad == 'unknown': group['passages'].append(999999)
    if bad == 'bool': group['passages'][0] = True
    if bad == 'float': group['passages'][0] = 1.0
    if bad == 'term_missing': group['term_indices'] = []
    if bad == 'term_duplicate': group['term_indices'] *= 2
    if bad == 'term_negative': group['term_indices'][0] = -1
    if bad == 'term_unknown': group['term_indices'][0] = 999999
    if bad == 'term_bool': group['term_indices'][0] = True
    if bad == 'blank_reason': group['reason'] = ' '
    if bad == 'label_only': group.update(role='CONTEXT', term_indices=[])
    if bad == 'caution_only': group['role'] = 'QUALIFICATION'
    if bad == 'unresolved_core': x['term_assertions'][0].update(status='UNRESOLVED', statement='', passages=[], reason='Unavailable.')
    if bad == 'context_term': group['role'] = 'CONTEXT'
    if bad == 'unresolved_sufficient':
        x['economic_source_coverage'].append(dict(passages=[group['passages'].pop()], role='UNRESOLVED', term_indices=[], reason='Unknown relevance.'))
        x['draft']['research']['materiality_coverage']['status'] = 'SUFFICIENT_FOR_RESEARCH'
    if bad == 'extra_field': group['approved'] = True
    before = deepcopy(x)
    with pytest.raises(ValueError): coverage_projection(p, x)
    assert x == before


@pytest.mark.parametrize('role', ['CONTEXT', 'OUT_OF_SCOPE', 'UNRESOLVED', 'QUALIFICATION'])
def test_exclusions_and_uncertainty_are_retained_for_review(linked_case, role):
    p, _, x, _, _, _ = complete_case(linked_case)
    group = x['economic_source_coverage'][0]
    row = dict(passages=[group['passages'].pop()], role=role,
        term_indices=[0] if role == 'QUALIFICATION' else [], reason='Synthetic disclosed scope/uncertainty.')
    x['economic_source_coverage'].append(row)
    if role == 'UNRESOLVED': x['draft']['research']['materiality_coverage']['status'] = 'UNRESOLVED'
    coverage_projection(p, x)
    items = completeness_checklist(x, 'fixture')
    assert items[-1]['original_value'] == row and items[-1]['status'] == 'SOURCE_REVIEW_REQUIRED'


def test_unresolved_assertion_never_gets_invented_core(linked_case):
    p, _, x, _, _, _ = complete_case(linked_case)
    x['term_assertions'][0].update(status='UNRESOLVED', statement='', passages=[], reason='Unavailable.')
    x['economic_source_coverage'][0]['term_indices'].remove(0)
    if not x['economic_source_coverage'][0]['term_indices']:
        x['economic_source_coverage'][0]['role'] = 'UNRESOLVED'
        x['draft']['research']['materiality_coverage']['status'] = 'UNRESOLVED'
    before = deepcopy(x)
    coverage_projection(p, x)
    assert x == before


def test_qualitative_effects_survive_broad_labels_and_caution_topics(linked_case):
    p, old, m = deepcopy(linked_case)
    headline = 'Approval supports margin expansion opportunity and substantially increases peak output capacity. '
    raw = 'INFRASTRUCTURE FIXTURE ONLY. ' + headline + headline + 'Benefits are anticipated; actual results may differ.'
    added = source('retrieved_document', dict(text=raw), NOW)
    p['sources'].append(added)
    p['packet_id'] = digest({k:v for k,v in p.items() if k != 'packet_id'})
    p, r, x, _, _, _ = complete_case((p, old, m))
    # A coarse paraphrase can still be incomplete. Host links must not erase the
    # declared core source meaning even when the free-text assertion is weak.
    x['draft']['economic_inventory']['terms'][0]['label'] = 'Margin and capacity benefits'
    x['term_assertions'][0]['statement'] = 'The warning lists margin and capacity as forward-looking topics.'
    before = deepcopy(x)
    report = completeness_report(p, r, canonical(x))
    passages = report['economic_core_source_links'][0]['source_passages']
    exact = [s for s in passages if s['source_id'] == added['source_id']]
    assert ''.join(s['text'] for s in exact) == raw
    repeated = [s for s in exact if s['text'] == headline]
    assert len(repeated) == 2 and repeated[0]['passage_id'] != repeated[1]['passage_id']
    for s in exact: assert added['text'][s['start']:s['end']] == s['quote']
    for link in report['materiality_economic_links']:
        assert link['core_source_links'] == report['economic_core_source_links']
        assert link['term'] == x['draft']['economic_inventory']['terms'][link['term_index']]
    assert x == before and report['original_draft'] == x
    # An incorrect exclusion can still pass: explicitly test, never advertise
    # passage accounting as semantic completeness or autonomous acceptance.
    group = x['economic_source_coverage'][0]
    excluded = [s['number'] for s in exact]
    group['passages'] = [n for n in group['passages'] if n not in excluded]
    x['economic_source_coverage'].append(dict(passages=excluded, role='OUT_OF_SCOPE', term_indices=[], reason='Deliberately false synthetic exclusion.'))
    coverage_projection(p, x)
    assert completeness_checklist(x, r['request_id'])[-1]['original_value']['role'] == 'OUT_OF_SCOPE'


@pytest.mark.parametrize('bad', ['instruction', 'schema', 'source', 'authority', 'tools', 'zero_limit', 'bool_limit'])
def test_tampering_never_reserves_or_calls(linked_case, bad):
    p, r, x, _, _, _ = complete_case(linked_case)
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
        with pytest.raises(ReviewBlocked, match='COMPLETENESS_REQUEST_MISMATCH'): execute_once(ledger, p, r, provider, lambda: NOW)
        assert provider.calls == 0 and ledger.db.execute('select count(*) from requests').fetchone()[0] == 0
    finally: ledger.close()


def test_original_attribution_assessment_and_no_retry(linked_case):
    p, r, x, ref, old, _ = complete_case(linked_case)
    previous = coverage_projection(p, x)
    raw = reply(x); raw['output'][0]['content'][0]['text'] = json.dumps(x, indent=2)
    provider = FakeProvider(raw); path = ledger_path(); ledger = AttemptLedger(path, 1)
    try:
        result = execute_once(ledger, p, r, provider, lambda: NOW)
        assert execute_once(ledger, p, r, provider, lambda: NOW) == result and provider.calls == 1
    finally: ledger.close()
    before = sha256(path.read_bytes()).hexdigest()
    assert ledger_inputs(path, r['request_id'], p) == (r, raw, NOW)
    report = field_review(p, r, raw, NOW, ref)
    assert report['original_draft'] == x and report['original_provider_response'] == raw
    assert report['original_response_text'] == raw['output'][0]['content'][0]['text']
    assert report['field_items'] == completeness_checklist(x, r['request_id'])
    assert report['implementation_version'] == '1.4.0-source-coverage-review'
    binding = result['research_binding']
    assert binding['economic_inventory']['implementation_version'] == VERSIONS[0]
    assert binding['economic_core_source_links'] and binding['materiality_economic_links'][0]['core_source_links']
    assert result['review_artifact']['review']['prompt_version'] == VERSIONS[1]
    assert binding['explicit_response_contract']['trace'] == p['trace']
    assert not result['eligible_for_handoff'] and not result['economic_summary']['eligible_for_handoff']
    a = assessment(report, 'SUPPORTED'); a['decisions'][-1]['finding'] = 'REVISION_REQUIRED'
    judged = record_field_assessment(p, r, raw, NOW, ref, a, NOW)
    assert judged['status'] == 'REVISIONS_REQUIRED' and judged['semantic_acceptance'] == 'NOT_ESTABLISHED'
    assert render_explicit_review(report) == render_explicit_review(json.loads(canonical(report)))
    assert sha256(path.read_bytes()).hexdigest() == before
    assert parse_response(p, old, reply(previous), NOW)['research_binding']['explicit_response_contract']['original_draft'] == previous


def test_missing_source_failure_is_immutable_and_not_retried(linked_case):
    p, r, x, _, _, _ = complete_case(linked_case)
    x['economic_source_coverage'][0]['passages'].pop()
    raw = reply(x); provider = FakeProvider(raw); ledger = AttemptLedger(ledger_path(), 1)
    try:
        with pytest.raises(ReviewBlocked, match='RESPONSE_VALIDATION_FAILED'): execute_once(ledger, p, r, provider, lambda: NOW)
        assert ledger.events(r['request_id'])['RECEIVED']['payload'] == raw
        assert 'COMPLETED' not in ledger.events(r['request_id'])
        with pytest.raises(ReviewBlocked, match='PREVIOUS_ATTEMPT_FAILED_NO_RETRY'): execute_once(ledger, p, r, provider, lambda: NOW)
        assert provider.calls == 1
    finally: ledger.close()
