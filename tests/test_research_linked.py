"""New-contract infrastructure fixtures only; never repaired historical outcomes."""
from copy import deepcopy
import json
import pytest
from evidence_review import canonical, digest
from research_linked import (VERSIONS, numbered_passages, numbered_rules,
    prepare_linked_request, validate_linked_request)
from research_reviewer import parse_response, ReviewBlocked
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import NOW, authorities, snapshot
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_passages import passage_case, draft_for as old_fixture


def draft_for(p, m):
    # Transform a synthetic fixture, never a saved provider response.
    d = old_fixture(p); support = {s['path']: s for s in d.pop('support')}
    numbers = {r['passage_id']: n for n, r in numbered_passages(p).items()}
    def attach(item, path, key='support', evidence='evidence'):
        item.pop(evidence)
        s = support.get(path, dict(event_relation='SELECTED_EVENT', clauses=[]))
        item[key] = {k: deepcopy(s[k]) for k in ('event_relation', 'clauses')}
        for c in item[key]['clauses']: c['passages'] = [numbers[r['passage_id']] for r in c['passages']]
    attach(d['target'], 'target.rationale')
    attach(d['selected_event']['subject'], 'selected_event.subject')
    attach(d['selected_event'], 'selected_event.description')
    attach(d['selected_event'], 'selected_event.link_rationale', 'link_support', 'link_evidence')
    for x in d['facts']: attach(x, 'facts.' + x['topic'])
    for x in d['claims']: attach(x, 'claims.' + x['criterion'])
    coverage = d['materiality_coverage']; attach(coverage, 'materiality_coverage.rationale')
    gaps = {g['gap_index']: g for g in d.pop('gap_review')}
    for field in ('evidence_gaps', 'document_followups'):
        for i, x in enumerate(coverage[field]):
            attach(x, f'materiality_coverage.{field}.{i}')
            if field == 'evidence_gaps':
                x.update({k: gaps[i][k] for k in ('already_established', 'why_needed_for_this_scope')})
    for n in d['context_notes']: n['passages'] = [numbers[r['passage_id']] for r in n['passages']]
    d['tier_proposal']['fact_topics'] = []
    d['tier_proposal'].pop('supporting_paths')
    return d


@pytest.fixture
def linked_case(passage_case):
    p, _, m = passage_case
    return p, prepare_linked_request(p, m, 'offline-fixture', 12000, 250000, NOW), m


def test_single_selection_derives_parents_and_durable_replay(linked_case):
    p, r, m = linked_case; d = draft_for(p, m); calls = []
    # A passage can support two clauses without duplicating its parent.
    d['selected_event']['support']['clauses'] *= 2
    class Provider:
        def respond(self, body): calls.append(body); return reply(d)
    path = ledger_path(); ledger = AttemptLedger(path, 1)
    try: out = execute_once(ledger, p, r, Provider(), lambda: NOW)
    finally: ledger.close()
    assert json.loads(canonical(out)) == out
    ledger = AttemptLedger(path, 1)
    try: assert execute_once(ledger, p, r, Provider(), lambda: NOW) == out and len(calls) == 1
    finally: ledger.close()
    b = out['research_binding']; assert not out['eligible_for_handoff']
    assert b['support_review']['implementation_version'] == VERSIONS[0]
    assert b['support_review']['parent_references'] == 'HOST_DERIVED_FROM_SELECTED_PASSAGES'
    assert b['support_review']['semantic_verification'] == 'NOT_ESTABLISHED'
    assert b['tier_review']['approval'] == 'NOT_APPROVED'
    assert out['review_artifact']['review']['implementation_version'] == VERSIONS[0]
    assert out['review_artifact']['trace'] == p['trace']
    for s in b['support_review']['clauses']:
        for c in s['clauses']:
            for row in c['citations']:
                src = next(x for x in p['sources'] if x['source_id'] == row['source_id'])
                assert src['text'][row['start']:row['end']] == row['quote']


@pytest.mark.parametrize('bad', [0, -1, 999999, True, 1.0, '1', None])
def test_invalid_numbers_rejected(linked_case, bad):
    p, r, m = linked_case; d = draft_for(p, m)
    d['selected_event']['support']['clauses'][0]['passages'] = [bad]
    with pytest.raises(ValueError): parse_response(p, r, reply(d), NOW)


@pytest.mark.parametrize('bad', ['duplicate', 'parent', 'path', 'gap_review', 'empty_subject',
    'empty_fact', 'event_relation', 'publication_as_event', 'approval', 'extra_claim', 'offset'])
def test_inherited_gates_and_no_legacy_fields(linked_case, bad):
    p, r, m = linked_case; d = draft_for(p, m)
    c = d['selected_event']['support']['clauses'][0]
    if bad == 'duplicate': c['passages'] *= 2
    if bad == 'parent': d['selected_event']['evidence'] = []
    if bad == 'path': d['selected_event']['support']['path'] = 'other'
    if bad == 'gap_review': d['gap_review'] = []
    if bad == 'empty_subject': d['selected_event']['subject']['support']['clauses'] = []
    if bad == 'empty_fact': next(x for x in d['facts'] if x['topic'] == 'catalyst_event')['support']['clauses'] = []
    if bad == 'event_relation': d['selected_event']['support']['event_relation'] = 'OTHER_EVENT'
    if bad == 'publication_as_event': next(x for x in d['facts'] if x['topic'] == 'event_timing')['support']['clauses'][0]['time_basis'] = 'PUBLICATION'
    if bad == 'approval': next(x for x in d['claims'] if x['criterion'] == 'catalyst_materiality_tier')['evidence_state'] = 'OBSERVED_SUPPORT'
    if bad == 'extra_claim': d['claims'].append(deepcopy(d['claims'][0]))
    if bad == 'offset': c['start'] = 0
    with pytest.raises(ValueError): parse_response(p, r, reply(d), NOW)


def test_gap_scope_host_attached_without_semantic_approval(linked_case):
    p, r, m = linked_case; d = draft_for(p, m); coverage = d['materiality_coverage']
    coverage.update(status='INCOMPLETE')
    # Use the established fixture structure for gaps; inspect its schema fields.
    from research_gaps import EvidenceGap
    assert set(EvidenceGap.model_fields) == {'missing_fact', 'why_material', 'captured_evidence_limit', 'evidence'}
    coverage['evidence_gaps'] = [dict(missing_fact='Synthetic missing amount', why_material='Synthetic scope needs amount',
        captured_evidence_limit='Amount absent in this fixture', already_established='Event identity',
        why_needed_for_this_scope='Synthetic narrow question', support=deepcopy(d['selected_event']['support']))]
    out = parse_response(p, r, reply(d), NOW)
    g = out['research_binding']['support_review']['gap_review'][0]
    assert g['gap_index'] == 0 and g['assessment_scope'] == coverage['assessment_scope']
    assert g['domain'] == 'NARROW_MATERIALITY_FACT' and not out['eligible_for_handoff']


@pytest.mark.parametrize('bad', ['schema', 'catalog', 'master_hash', 'master_text', 'prompt', 'tools', 'store'])
def test_tamper_before_provider_and_ledger(linked_case, bad):
    p, r, m = linked_case; r = deepcopy(r)
    if bad == 'schema': r['body']['text']['format']['strict'] = False
    if bad == 'catalog': r['body']['input'][1]['content'] += 'changed'
    if bad == 'master_hash': r['masters_digest'] = '0'*64
    if bad == 'master_text': r['body']['input'][0]['content'] = r['body']['input'][0]['content'].replace('Credible analyst', 'Corporate action')
    if bad == 'prompt': r['body']['input'][0]['content'] += 'Promote now.'
    if bad == 'tools': r['body']['tools'] = [{'type': 'web_search'}]
    if bad == 'store': r['body']['store'] = True
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    class Forbidden:
        def respond(self, body): raise AssertionError('Provider must not run')
    ledger = AttemptLedger(ledger_path(), 1)
    try:
        with pytest.raises(ReviewBlocked): execute_once(ledger, p, r, Forbidden(), lambda: NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0] == 0
    finally: ledger.close()


def test_full_context_and_bounds(linked_case):
    p, r, m = linked_case
    view = json.loads(r['body']['input'][1]['content'].split('\n', 1)[1])
    for s in view['packet']['sources']: s['raw'] = json.loads(s['text'])
    assert view['packet'] == p and validate_linked_request(p, r)['strategy']['text'] == m['strategy']['text']
    assert numbered_passages(p) == numbered_passages(deepcopy(p))
    count = len(numbered_passages(p))
    item = r['body']['text']['format']['schema']['$defs']['NumberedClause']['properties']['passages']['items']
    assert item == dict(type='integer', minimum=1, maximum=count)
    size = len(canonical(r['body']).encode())
    assert prepare_linked_request(p, m, 'offline-fixture', 12000, size, NOW) == r
    with pytest.raises(ReviewBlocked, match='INPUT_LIMIT_EXCEEDED'):
        prepare_linked_request(p, m, 'offline-fixture', 12000, size-1, NOW)


def test_rule_binding_is_not_semantic_acceptance(linked_case):
    p, r, m = linked_case; d = draft_for(p, m)
    number = next(n for n, row in numbered_rules(m).items() if row['tier'] == 'B')
    d['tier_proposal'].update(proposed_tier='B', mapping_status='PROPOSED', rules=[number],
        fact_topics=['catalyst_event'], explanation='Deliberately false corporate-action catch-all interpretation.')
    out = parse_response(p, r, reply(d), NOW)
    assert out['research_binding']['tier_review']['approval'] == 'NOT_APPROVED'
    assert not out['eligible_for_handoff']
    for invalid in (0, 99999, True, '1'):
        d['tier_proposal']['rules'] = [invalid]
        with pytest.raises(ValueError): parse_response(p, r, reply(d), NOW)


def test_default_cli_stays_prepare_only(linked_case, monkeypatch, capsys):
    import run_research_reviewer as cli
    # Preserve the historical v14 CLI regression under its actual prompt version.
    monkeypatch.setattr(cli, 'prepare_request', prepare_linked_request)
    p, _, m = linked_case; root = ledger_path().parent
    (root/'p.json').write_text(canonical(p), encoding='utf-8'); (root/'m.json').write_text(canonical(m), encoding='utf-8')
    def forbidden(*a, **k): raise AssertionError('No provider or credentials')
    monkeypatch.setattr(cli, 'OpenAIReviewer', forbidden)
    monkeypatch.setattr(cli, 'inspect_packet', lambda *a: dict(report_id='infrastructure', route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv', ['review', '--packet', str(root/'p.json'), '--masters', str(root/'m.json'),
        '--model', 'offline-fixture', '--max-output-tokens', '12000', '--max-input-bytes', '250000', '--output', str(root)])
    cli.main(); assert json.loads(capsys.readouterr().out)['model_calls'] == 0
