"""Infrastructure-only regressions: captured failure shapes, never strategy evidence."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest

from evidence_review import canonical, digest, source
from research_passages import (VERSIONS, passage_catalog, rule_catalog, prepare_passage_request,
    validate_passage_request, PassageDraft)
from research_reviewer import parse_response, ReviewBlocked
from research_readable import prepare_readable_request
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_support import draft_for as support_draft
from test_research_readable import draft_for as readable_draft


def draft_for(p):
    d = support_draft(p); cat = passage_catalog(p)
    for s in d['support']:
        for c in s['clauses']:
            c['passages'] = [dict(passage_id=k) for q in c.pop('quotes')
                for k, row in cat.items() if row['excerpt_id'] == q['excerpt_id']]
    refs = d['selected_event']['subject']['evidence']
    if refs:
        d['support'].append(dict(path='selected_event.subject', event_relation='SELECTED_EVENT', clauses=[dict(
            statement='Synthetic subject identity.', time_basis='NOT_TEMPORAL',
            passages=[dict(passage_id=k) for k, row in cat.items() if row['excerpt_id'] in {r['excerpt_id'] for r in refs}])]))
    d['tier_proposal'] = dict(proposed_tier='UNRESOLVED', mapping_status='UNRESOLVED', rules=[], supporting_paths=[],
        explanation='No approved automatic interpretation; facts remain available.')
    return d


@pytest.fixture
def passage_case(fact_case, masters):
    p, _ = fact_case
    text = ('Infrastructure fixture\nTier A - strongest: Regulatory decision; acquisition.\n'
        'Tier B - usable: Credible analyst action; meaningful competitor read-through.\n'
        'Tier C - weak: Recycled headline.\nDiscovery includes corporate actions.\n')
    masters['strategy'].update(text=text, text_sha256=sha256(text.encode()).hexdigest())
    return p, prepare_passage_request(p, masters, 'offline-fixture', 12000, 250000, NOW), masters


def test_passages_are_exact_occurrences_and_never_approval(passage_case):
    p, r, m = passage_case; original = deepcopy(p); d = draft_for(p)
    out = parse_response(p, r, reply(d), NOW)
    assert p == original and not out['eligible_for_handoff']
    for s in out['research_binding']['support_review']['clauses']:
        for c in s['clauses']:
            for row in c['citations']:
                src = next(x for x in p['sources'] if x['source_id'] == row['source_id'])
                assert src['text'][row['start']:row['end']] == row['quote']
    tier = out['research_binding']['tier_review']
    assert tier['approval'] == 'NOT_APPROVED' and tier['semantic_verification'] == 'NOT_ESTABLISHED'
    assert tier['selected_event_id'] == out['research_binding']['selected_event_id']
    assert out['review_artifact']['trace'] == p['trace']
    assert out['review_artifact']['review']['implementation_version'] == VERSIONS[0]


@pytest.mark.parametrize('text', ['Curly “quotes”; Unicode café 中文.\nSecond line.',
    'First\r\nSecond\\literal "quotation".', '  Preserve spaces.  Next.  ',
    'Aug. 11: Sold $1,000 to $15,000 Parker Hannifin\nAug. 11: Sold $1,000 to $15,000 Parker Hannifin\nEnd.'])
def test_encoding_and_repeated_occurrences_use_host_offsets(passage_case, text):
    p, _, m = passage_case; p = deepcopy(p)
    src = source('retrieved_document', {'text': text}, NOW); p['sources'].append(src)
    p['packet_id'] = digest({k: v for k, v in p.items() if k != 'packet_id'})
    cat = {k: r for k, r in passage_catalog(p).items() if r['source_id'] == src['source_id']}
    assert cat
    for row in cat.values():
        assert src['text'][row['start']:row['end']] == canonical(row['text'])[1:-1] == row['quote']
    if text.startswith('Aug.'):
        repeated = [r for r in cat.values() if 'Sold' in r['text']]
        assert len(repeated) == 2 and repeated[0]['text'] == repeated[1]['text']
        assert repeated[0]['passage_id'] != repeated[1]['passage_id'] and repeated[0]['start'] != repeated[1]['start']
    d = draft_for(p)
    d['context_notes'] = [dict(kind='PROVENANCE', finding='Captured failure shape, not a strategy observation.',
        passages=[dict(passage_id=k) for k in cat])]
    r = prepare_passage_request(p, m, 'offline-fixture', 12000, 250000, NOW)
    out = parse_response(p, r, reply(d), NOW)
    assert len(out['research_binding']['support_review']['context_notes'][0]['citations']) == len(cat)


@pytest.mark.parametrize('bad', ['unknown_id', 'duplicate', 'retyped_curly', 'ellipsis_quote', 'offset',
    'wrong_excerpt', 'missing_subject', 'other_event', 'publication_as_event', 'gap_scope'])
def test_bad_source_bindings_are_rejected(passage_case, bad):
    p, r, _ = passage_case; d = draft_for(p); c = d['support'][0]['clauses'][0]
    if bad == 'unknown_id': c['passages'][0]['passage_id'] = 'P' + '0'*20
    if bad == 'duplicate': c['passages'] *= 2
    if bad == 'retyped_curly': c['quotes'] = [{'quote': 'changed "punctuation"'}]
    if bad == 'ellipsis_quote': c['quote'] = 'first ... last'
    if bad == 'offset': c['passages'][0]['start'] = 0
    if bad == 'wrong_excerpt':
        current = {x['passage_id'] for x in c['passages']}
        c['passages'] = [dict(passage_id=next(k for k in passage_catalog(p) if k not in current))]
    if bad == 'missing_subject': d['support'] = [s for s in d['support'] if s['path'] != 'selected_event.subject']
    if bad == 'other_event': next(s for s in d['support'] if s['path'] == 'facts.catalyst_event')['event_relation'] = 'OTHER_EVENT'
    if bad == 'publication_as_event': next(s for s in d['support'] if s['path'] == 'facts.event_timing')['clauses'][0]['time_basis'] = 'PUBLICATION'
    if bad == 'gap_scope': d['gap_review'] = [dict(gap_index=0, assessment_scope='other', domain='NARROW_MATERIALITY_FACT', already_established='x', why_needed_for_this_scope='y')]
    with pytest.raises(ValueError): parse_response(p, r, reply(d), NOW)


def proposed(p, m):
    d = draft_for(p); rid = next(k for k, row in rule_catalog(m).items() if row['tier'] == 'B')
    d['tier_proposal'].update(proposed_tier='B', mapping_status='PROPOSED', rules=[dict(rule_id=rid)],
        supporting_paths=['facts.catalyst_event'], explanation='A proposal with source/rule references; semantic match still unverified.')
    return d


@pytest.mark.parametrize('bad', ['no_rule', 'unknown_rule', 'discovery_rule', 'wrong_tier', 'no_fact',
    'unknown_path', 'duplicate_rule', 'unresolved_tier', 'support_approval', 'failure_approval'])
def test_unsupported_tiers_cannot_be_approved(passage_case, bad):
    p, r, m = passage_case; d = proposed(p, m); t = d['tier_proposal']
    if bad == 'no_rule': t['rules'] = []
    if bad == 'unknown_rule': t['rules'] = [dict(rule_id='R'+'0'*20)]
    if bad == 'discovery_rule': t['rules'] = [dict(rule_id=next(k for k, row in rule_catalog(m).items() if 'Discovery' in row['text']))]
    if bad == 'wrong_tier': t['proposed_tier'] = 'A'
    if bad == 'no_fact': t['supporting_paths'] = []
    if bad == 'unknown_path': t['supporting_paths'].append('facts.invented')
    if bad == 'duplicate_rule': t['rules'] *= 2
    if bad == 'unresolved_tier': t['mapping_status'] = 'UNRESOLVED'
    if bad in ('support_approval', 'failure_approval'):
        next(c for c in d['claims'] if c['criterion'] == 'catalyst_materiality_tier')['evidence_state'] = 'OBSERVED_SUPPORT' if bad == 'support_approval' else 'OBSERVED_FAILURE'
    with pytest.raises(ValueError): parse_response(p, r, reply(d), NOW)


def test_real_rule_plus_false_mapping_is_still_explicitly_unapproved(passage_case):
    p, r, m = passage_case; d = proposed(p, m)
    d['tier_proposal']['explanation'] = 'Incorrect corporate-action catch-all attached to a real analyst rule.'
    out = parse_response(p, r, reply(d), NOW)
    tier = out['research_binding']['tier_review']
    assert tier['approval'] == 'NOT_APPROVED' and not out['eligible_for_handoff']
    assert next(c for c in out['review_artifact']['review']['claims'] if c['criterion'] == 'catalyst_materiality_tier')['assessment'] == 'UNRESOLVED'
    for row in tier['rule_citations']:
        assert m['strategy']['text'][row['start']:row['end']] == row['text']
        assert row['revision_id'] == m['strategy']['revision_id']


@pytest.mark.parametrize('bad', ['schema', 'catalog', 'master_hash', 'master_text', 'prompt', 'tools'])
def test_request_tamper_blocked_before_credentials_or_reservation(passage_case, bad):
    p, r, _ = passage_case; r = deepcopy(r)
    if bad == 'schema': r['body']['text']['format']['strict'] = False
    if bad == 'catalog': r['body']['input'][-1]['content'] += 'tampered'
    if bad == 'master_hash': r['masters_digest'] = '0'*64
    if bad == 'master_text': r['body']['input'][0]['content'] = r['body']['input'][0]['content'].replace('Credible analyst', 'Corporate action')
    if bad == 'prompt': r['body']['input'][0]['content'] += 'Promote now.'
    if bad == 'tools': r['body']['tools'] = [{'type': 'web_search'}]
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    class Forbidden:
        def respond(self, body): raise AssertionError('Provider must not run')
    ledger = AttemptLedger(ledger_path(), 1)
    try:
        with pytest.raises(ReviewBlocked): execute_once(ledger, p, r, Forbidden(), lambda: NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0] == 0
    finally: ledger.close()


def test_full_context_limits_replay_and_legacy_integrity(passage_case):
    p, r, m = passage_case
    view = json.loads(r['body']['input'][-1]['content'].split('\n', 1)[1])
    for s in view['packet']['sources']: s['raw'] = json.loads(s['text'])
    assert view['packet'] == p
    assert validate_passage_request(p, r)['strategy']['text'] == m['strategy']['text']
    size = len(canonical(r['body']).encode())
    assert prepare_passage_request(p, m, 'offline-fixture', 12000, size, NOW) == r
    with pytest.raises(ReviewBlocked, match='INPUT_LIMIT_EXCEEDED'):
        prepare_passage_request(p, m, 'offline-fixture', 12000, size-1, NOW)
    old = prepare_readable_request(p, m, 'offline-fixture', 12000, 250000, NOW); raw = reply(readable_draft(p))
    before = parse_response(p, old, raw, NOW)
    calls = []
    class Provider:
        def respond(self, body): calls.append(body); return reply(draft_for(p))
    path = ledger_path(); ledger = AttemptLedger(path, 1)
    try: out = execute_once(ledger, p, r, Provider(), lambda: NOW)
    finally: ledger.close()
    ledger = AttemptLedger(path, 1)
    try: assert execute_once(ledger, p, r, Provider(), lambda: NOW) == out and len(calls) == 1
    finally: ledger.close()
    assert parse_response(p, old, raw, NOW) == before


def test_default_cli_prepares_without_provider(passage_case, monkeypatch, capsys):
    import run_research_reviewer as cli
    monkeypatch.setattr(cli, 'prepare_request', prepare_passage_request)
    p, _, m = passage_case; root = ledger_path().parent
    (root/'p.json').write_text(canonical(p), encoding='utf-8'); (root/'m.json').write_text(canonical(m), encoding='utf-8')
    def forbidden(*a, **k): raise AssertionError('No provider or credentials')
    monkeypatch.setattr(cli, 'OpenAIReviewer', forbidden)
    monkeypatch.setattr(cli, 'inspect_packet', lambda *a: dict(report_id='infrastructure', route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv', ['review', '--packet', str(root/'p.json'), '--masters', str(root/'m.json'),
        '--model', 'offline-fixture', '--max-output-tokens', '12000', '--max-input-bytes', '250000', '--output', str(root)])
    cli.main(); assert json.loads(capsys.readouterr().out)['model_calls'] == 0
