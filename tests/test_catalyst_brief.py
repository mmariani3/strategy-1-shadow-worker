from copy import deepcopy
import pytest

from catalyst_brief import attach_briefs, SECTIONS, QUESTIONS, source_link
from supervised_preparation import prepare, render, STRATEGY_REVISION
from test_evidence_review import snapshot, authorities, NOW


@pytest.fixture
def research(snapshot, authorities):
    authorities['strategy']['revision_id'] = STRATEGY_REVISION
    snapshot['items'][0]['news_evidence'] = [{'summary':'Company forecasts an increase, subject to demand.', 'url':'https://example.com/source'}]
    report = prepare(snapshot, authorities, deepcopy(authorities), NOW)
    c = report['candidates'][0]
    src = next(s for s in c['sources'] if s['kind'] == 'news')
    b = dict(schema_version=1, packet_id=c['packet_id'], symbol=c['symbol'], trace=c['trace'],
        source_experiment_class=report['experiment_class'], source_snapshot_digest=report['source_snapshot_digest'],
        title='Historical local test', authored_by='Fixture author', authored_at=NOW,
        checked_by='Fixture author', checked_at=NOW, review_scope='AUTHOR_SOURCE_CHECK_NOT_INDEPENDENT',
        event_timing='Synthetic; no market event.', knowledge_limit='Isolated infrastructure fixture.', tier_proposal='UNRESOLVED',
        claims=[dict(id='claim1', text='Company forecasts growth; demand remains a condition.', kind='MANAGEMENT_FORECAST',
            citations=[dict(source_id=src['source_id'], field='summary', start=0, end=len(src['raw']['summary']), excerpt=src['raw']['summary'])],
            source_check='Compared full synthetic passage; forecast preserved.')],
        sections={s:['claim1'] for s in SECTIONS}, limitations=['Independent verification unavailable.'])
    return report, b


def test_attached_brief_preserves_funnel_and_never_approves(research):
    r, b = research
    before = deepcopy((r,b))
    result = attach_briefs(r,[b],NOW)
    brief = result['candidates'][0]['catalyst_brief']
    assert len(result['candidates']) == 2
    assert 'catalyst_brief' not in result['candidates'][1]
    assert brief['current_approval'] == brief['independent_acceptance'] == 'NOT_ESTABLISHED'
    assert not brief['eligible_for_handoff'] and not result['execution_enabled']
    assert result['journal_draft']['rows'] == []
    assert (r,b) == before
    assert result['preparation_id'] != r['preparation_id']
    assert len(result['review_questions']) == 12


@pytest.mark.parametrize('change', ['packet','trace','class','symbol','snapshot','excerpt','offset','source','field','future','naive','blank','unknown_claim','omitted_claim','missing_section','approval','scope','duplicate_claim'])
def test_invalid_brief_bindings_and_approval_fields_refused(research, change):
    r,b = research
    if change == 'packet': b['packet_id'] = 'another'
    if change == 'trace': b['trace'] = {**b['trace'], 'signal_id':'manufactured'}
    if change == 'class': b['source_experiment_class'] = 'STRATEGY_1'
    if change == 'symbol': b['symbol'] = 'WRONG'
    if change == 'snapshot': b['source_snapshot_digest'] = 'different'
    if change == 'excerpt': b['claims'][0]['citations'][0]['excerpt'] = 'Guaranteed growth'
    if change == 'offset': b['claims'][0]['citations'][0]['start'] = 2
    if change == 'source': b['claims'][0]['citations'][0]['source_id'] = 'missing'
    if change == 'field': b['claims'][0]['citations'][0]['field'] = 'unavailable'
    if change == 'future': b['checked_at'] = '2099-01-01T00:00:00Z'
    if change == 'naive': b['checked_at'] = '2026-09-18T14:00:00'
    if change == 'blank': b['authored_by'] = '  '
    if change == 'unknown_claim': b['sections']['Timeline'] = ['unknown']
    if change == 'omitted_claim': b['claims'].append({**b['claims'][0], 'id':'hidden'})
    if change == 'missing_section': del b['sections']['Case against']
    if change == 'approval': b['eligible_for_handoff'] = True
    if change == 'scope': b['review_scope'] = 'INDEPENDENT_ACCEPTANCE'
    if change == 'duplicate_claim': b['claims'].append(deepcopy(b['claims'][0]))
    with pytest.raises(ValueError): attach_briefs(r,[b],NOW)


def test_duplicate_and_no_catalyst_source_rejected(research):
    r,b = research
    with pytest.raises(ValueError): attach_briefs(r,{},NOW)
    with pytest.raises(ValueError): attach_briefs(r,[b,b],NOW)
    src = next(s for s in r['candidates'][0]['sources'] if s['kind']=='discovery_record')
    b['claims'][0]['citations'][0]['source_id'] = src['source_id']
    with pytest.raises(ValueError): attach_briefs(r,[b],NOW)


def test_semantic_accuracy_is_not_inferred_from_matching_passage(research):
    r,b = research
    # Deliberately false inference can have a valid source location. The host must
    # never advertise this structural validation as truth or semantic acceptance.
    b['claims'][0]['text'] = 'The outcome is guaranteed.'
    result = attach_briefs(r,[b],NOW)
    assert result['candidates'][0]['catalyst_brief']['independent_acceptance'] == 'NOT_ESTABLISHED'
    assert not result['eligible_for_handoff']


def test_brief_html_escapes_text_and_exposes_limits(research):
    r,b = research
    b['title'] = '<img src=x onerror=alert(1)>'
    b['limitations'] = ['</script><script>alert(1)</script>']
    html = render(attach_briefs(r,[b],NOW))
    assert '<img src=x' not in html and '&lt;img src=x' in html
    assert 'independent acceptance and current approval are not established' in html
    assert 'target="_blank" rel="noopener noreferrer"' in html
    assert 'No checked research brief attached' in html
    assert 'Save review draft' in html
    for key,_ in QUESTIONS: assert 'id="review-' + key + '"' in html


@pytest.mark.parametrize('url',['javascript:alert(1)','data:text/html,test','http://example.com','https://user:secret@example.com','https://[bad'])
def test_unsafe_links_are_not_rendered(url):
    assert '<a ' not in source_link({'url':url})
