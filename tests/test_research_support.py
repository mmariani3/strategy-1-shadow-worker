"""Infrastructure regressions based on the separate review; no trading evidence."""
from copy import deepcopy
import json
import pytest

from evidence_review import canonical, digest, CRITERIA
from research_support import (VERSIONS, HOST_REASONS, RESEARCH_CRITERIA, SupportDraft,
    prepare_support_request, support_schema)
from research_subjects import prepare_subject_request
from research_reviewer import parse_response, ReviewBlocked
from research_citations import selectable_catalog
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_subjects import draft_for as old_draft
from test_research_gaps import gap, followup


def add_support(p, d):
    catalog = selectable_catalog(p)
    paths = [('target.rationale', d['target']['evidence']),
        ('selected_event.description', d['selected_event']['evidence']),
        ('selected_event.link_rationale', d['selected_event']['link_evidence']),
        ('materiality_coverage.rationale', d['materiality_coverage']['evidence'])]
    paths += [('facts.' + f['topic'], f['evidence']) for f in d['facts']]
    paths += [('claims.' + c['criterion'], c['evidence']) for c in d['claims']]
    for field in ('evidence_gaps', 'document_followups'):
        paths += [(f'materiality_coverage.{field}.{i}', item['evidence']) for i, item in enumerate(d['materiality_coverage'][field])]
    d['support'] = [dict(path=path, event_relation='SELECTED_EVENT', clauses=[dict(statement='Isolated infrastructure clause.',
        time_basis='EVENT_OCCURRENCE' if path == 'facts.event_timing' else 'PUBLICATION' if path == 'facts.publication_timing' else 'NOT_TEMPORAL',
        quotes=[dict(excerpt_id=e['excerpt_id'], quote=catalog[e['excerpt_id']]['quote']) for e in evidence])])
        for path, evidence in paths if evidence]
    return d


def draft_for(p, supported=False):
    d = old_draft(p, supported)
    d['claims'] = [c for c in d['claims'] if c['criterion'] in RESEARCH_CRITERIA]
    d.update(support=[], gap_review=[], context_notes=[])
    return add_support(p, d)


@pytest.fixture
def support_case(fact_case, masters):
    p, _ = fact_case
    return p, prepare_support_request(p, masters, 'offline-fixture', 12000, 250000, NOW)


def test_exact_quote_offsets_and_host_attribution(support_case):
    p, r = support_case; d = draft_for(p, True); before = deepcopy(p)
    # An actual substring, not an invented analyst-action clause.
    q = next(s for s in d['support'] if s['path'] == 'selected_event.description')['clauses'][0]['quotes'][0]
    assert 'announced' in q['quote']; q['quote'] = 'announced'
    out = parse_response(p, r, reply(d), NOW)
    assert p == before and not out['eligible_for_handoff']
    b = out['research_binding']; assert b['semantic_verification'] == 'NOT_ESTABLISHED'
    for s in b['support_review']['clauses']:
        for c in s['clauses']:
            for row in c['citations']:
                source = next(x for x in p['sources'] if x['source_id'] == row['source_id'])
                assert source['text'][row['start']:row['end']] == row['quote']
    for claim in out['review_artifact']['review']['claims']:
        if claim['criterion'] in HOST_REASONS:
            assert claim['rationale'] == HOST_REASONS[claim['criterion']]
            assert claim['assessment'] == 'UNRESOLVED' and claim['citations'] == []
    assert {x['criterion'] for x in b['claims'] if x['authored_by'] == 'HOST_CAPABILITY_BOUNDARY'} == set(HOST_REASONS)
    assert set(HOST_REASONS) | set(RESEARCH_CRITERIA) == set(CRITERIA)
    assert out['review_artifact']['review']['implementation_version'] == VERSIONS[0]


@pytest.mark.parametrize('bad', ['invented_quote', 'wrong_excerpt', 'omitted_item', 'duplicate_item', 'extra_item',
    'other_event', 'publication_as_event', 'market_as_event', 'event_as_publication', 'duplicate_quote', 'whitespace_quote'])
def test_observed_citation_and_timing_failures_are_blocked(support_case, bad):
    p, r = support_case; d = draft_for(p)
    s = next(s for s in d['support'] if s['path'] == 'facts.event_timing'); c = s['clauses'][0]
    if bad == 'invented_quote': c['quotes'][0]['quote'] = 'JPMorgan raised its price forecast.'
    if bad == 'wrong_excerpt': c['quotes'][0]['excerpt_id'] = next(k for k in selectable_catalog(p) if k != c['quotes'][0]['excerpt_id'])
    if bad == 'omitted_item': d['support'].remove(s)
    if bad == 'duplicate_item': d['support'].append(deepcopy(s))
    if bad == 'extra_item': s['path'] = 'claims.current_data_and_approvals'
    if bad == 'other_event': s['event_relation'] = 'OTHER_EVENT'
    if bad == 'publication_as_event': c['time_basis'] = 'PUBLICATION'
    if bad == 'market_as_event': c['time_basis'] = 'MARKET_OBSERVATION'
    if bad == 'event_as_publication': next(x for x in d['support'] if x['path'] == 'facts.publication_timing')['clauses'][0]['time_basis'] = 'EVENT_OCCURRENCE'
    if bad == 'duplicate_quote': c['quotes'] *= 2
    if bad == 'whitespace_quote': c['quotes'][0]['quote'] = ' '
    with pytest.raises(ValueError): parse_response(p, r, reply(d), NOW)


@pytest.mark.parametrize('criterion', sorted(HOST_REASONS))
def test_model_cannot_author_operational_or_freshness_claims(support_case, criterion):
    p, r = support_case; d = draft_for(p)
    d['claims'].append(dict(criterion=criterion, subject_symbol=p['symbol'], evidence_state='INSUFFICIENT_EVIDENCE',
        rationale='Require SEC corporate approval; prices moved after publication; ADV preference is mandatory.', evidence=[]))
    with pytest.raises(ValueError): parse_response(p, r, reply(d), NOW)


@pytest.mark.parametrize('bad', ['missing', 'duplicate', 'scope', 'domain', 'negative'])
def test_gap_necessity_review_is_bound_to_precise_scope(support_case, bad):
    p, r = support_case; d = draft_for(p); cv = d['materiality_coverage']
    cv.update(status='INCOMPLETE', evidence_gaps=[gap()])
    d['gap_review'] = [dict(gap_index=0, assessment_scope=cv['assessment_scope'], domain='NARROW_MATERIALITY_FACT',
        already_established='The reported numerator.', why_needed_for_this_scope='The proposed dilution percentage needs its denominator.')]
    assert not parse_response(p, r, reply(d), NOW)['eligible_for_handoff']
    if bad == 'missing': d['gap_review'] = []
    if bad == 'duplicate': d['gap_review'] *= 2
    if bad == 'scope': d['gap_review'][0]['assessment_scope'] = 'Current trading authorization'
    if bad == 'domain': d['gap_review'][0]['domain'] = 'PRIMARY_DOCUMENT_REQUIRED'
    if bad == 'negative': d['gap_review'][0]['gap_index'] = -1
    with pytest.raises(ValueError): parse_response(p, r, reply(d), NOW)


def test_optional_followups_and_context_are_preserved_not_promoted(support_case):
    p, r = support_case; d = draft_for(p, True)
    d['materiality_coverage']['document_followups'] = [followup()]
    quote = deepcopy(d['support'][0]['clauses'][0]['quotes'])
    d['context_notes'] = [dict(kind='CONDITIONALITY', finding='Infrastructure example only; requires semantic review.', quotes=quote)]
    out = parse_response(p, r, reply(d), NOW)
    assert out['materiality_evidence_coverage']['status'] == 'SUFFICIENT_FOR_RESEARCH'
    assert out['materiality_evidence_coverage']['document_followups'][0]['authority'] == 'PROPOSAL_ONLY_NOT_AN_APPROVED_REQUIREMENT'
    assert out['research_binding']['support_review']['context_notes'][0]['finding'] == d['context_notes'][0]['finding']


def test_true_quote_does_not_prove_entailment_or_gap_necessity(support_case):
    p, r = support_case; d = draft_for(p)
    d['support'][0]['clauses'][0]['statement'] = 'Unsupported claim attached to a real quote.'
    out = parse_response(p, r, reply(d), NOW)
    assert out['research_binding']['support_review']['semantic_verification'] == 'NOT_ESTABLISHED'
    assert not out['eligible_for_handoff']


def test_complete_inputs_limits_schema_and_prebilling_binding(support_case, masters):
    p, r = support_case
    view = json.loads(r['body']['input'][-1]['content'].split('\n', 1)[1])['packet']
    for s in view['sources']: s['raw'] = json.loads(s['text'])
    assert view == p  # Includes non-source metadata, not only sources.
    size = len(canonical(r['body']).encode())
    assert prepare_support_request(p, masters, 'offline-fixture', 12000, size, NOW) == r
    with pytest.raises(ReviewBlocked, match='INPUT_LIMIT_EXCEEDED'):
        prepare_support_request(p, masters, 'offline-fixture', 12000, size-1, NOW)
    tampered = deepcopy(r); tampered['body']['text']['format']['strict'] = False
    tampered['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=tampered['body']))
    class Forbidden:
        def respond(self, body): raise AssertionError('No provider call')
    ledger = AttemptLedger(ledger_path(), 1)
    try:
        with pytest.raises(ReviewBlocked): execute_once(ledger, p, tampered, Forbidden(), lambda: NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0] == 0
    finally: ledger.close()


def test_v11_replay_does_not_relabel_v10(support_case, masters):
    p, r = support_case; old = old_draft(p)
    old_req = prepare_subject_request(p, masters, 'offline-fixture', 12000, 250000, NOW)
    old_result = parse_response(p, old_req, reply(old), NOW)
    calls = []
    class Provider:
        def respond(self, body): calls.append(body); return reply(draft_for(p))
    path = ledger_path(); ledger = AttemptLedger(path, 1)
    try: out = execute_once(ledger, p, r, Provider(), lambda: NOW)
    finally: ledger.close()
    ledger = AttemptLedger(path, 1)
    try: assert execute_once(ledger, p, r, Provider(), lambda: NOW) == out and len(calls) == 1
    finally: ledger.close()
    assert parse_response(p, old_req, reply(old), NOW) == old_result


def test_default_cli_remains_prepare_only(support_case, masters, monkeypatch, capsys):
    import run_research_reviewer as cli
    assert cli.prepare_request is prepare_support_request
    p, _ = support_case; root = ledger_path().parent
    (root/'p.json').write_text(canonical(p), encoding='utf-8')
    (root/'m.json').write_text(canonical(masters), encoding='utf-8')
    def forbidden(*args, **kwargs): raise AssertionError('No provider/credentials')
    monkeypatch.setattr(cli, 'OpenAIReviewer', forbidden)
    monkeypatch.setattr(cli, 'inspect_packet', lambda *a: dict(report_id='isolated-infrastructure', route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv', ['review', '--packet', str(root/'p.json'), '--masters', str(root/'m.json'),
        '--model', 'offline-fixture', '--max-output-tokens', '12000', '--max-input-bytes', '250000', '--output', str(root)])
    cli.main(); assert json.loads(capsys.readouterr().out)['model_calls'] == 0
