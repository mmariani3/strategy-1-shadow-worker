"""Offline author fixtures only; original provider outcomes are never rewritten."""
from copy import deepcopy
import json
import pytest
from evidence_review import canonical, digest
from research_typed import VERSIONS, ROLES, TypedDraft, prepare_typed_request
from research_reviewer import parse_response
from research_scope import verify_source_summary
from research_omissions import omission_report, verify_omission_report, uncovered
from research_reference_coverage import audit_reference_coverage
from research_completeness_review import prepare_checklist
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_scope import make_case


def typed_case(linked_case):
    p, old, d, ref, m = make_case(linked_case)
    return p, prepare_typed_request(p, m, 'offline-fixture', 12000, 250000, NOW), d, ref, m


@pytest.mark.parametrize('topic', list(ROLES))
def test_wrong_topic_role_rejected_while_unresolved_status_stays_available(linked_case, topic):
    p, r, d, _, _ = typed_case(linked_case)
    f = next(f for f in d['research']['facts'] if f['topic'] == topic)
    f['status'] = 'UNRESOLVED'; f['support']['clauses'] = []
    TypedDraft.model_validate(d)  # Missing evidence never forces a false EVIDENCED assertion.
    for role in {'TARGET', 'EVENT', 'PUBLICATION', 'UNRESOLVED'} - {ROLES[topic]}:
        f['subject_role'] = role
        with pytest.raises(ValueError): parse_response(p, r, reply(d), NOW)


@pytest.mark.parametrize('part', ['subject', 'description', 'link', 'catalyst_event', 'event_timing'])
def test_event_support_cannot_be_context_or_other_event(linked_case, part):
    p, r, d, _, _ = typed_case(linked_case)
    event = d['research']['selected_event']
    s = (event['subject']['support'] if part == 'subject' else event['support'] if part == 'description'
         else event['link_support'] if part == 'link' else
         next(f['support'] for f in d['research']['facts'] if f['topic'] == part))
    for relation in ('CONTEXT', 'OTHER_EVENT'):
        s['event_relation'] = relation
        with pytest.raises(ValueError): parse_response(p, r, reply(d), NOW)


@pytest.mark.parametrize('topic,bad', [('event_timing','PUBLICATION'), ('publication_timing','EVENT_OCCURRENCE')])
def test_time_roles_are_constrained_in_both_schema_and_parser(linked_case, topic, bad):
    p, r, d, _, _ = typed_case(linked_case)
    f = next(f for f in d['research']['facts'] if f['topic'] == topic)
    f['support']['clauses'][0]['time_basis'] = bad
    with pytest.raises(ValueError): parse_response(p, r, reply(d), NOW)


def test_schema_fixes_relations_without_unsupported_conditionals(linked_case):
    p, r, d, _, _ = typed_case(linked_case); s = r['body']['text']['format']['schema']
    defs = s['$defs']
    assert len(defs['TypedResearch']['properties']['facts']['items']['anyOf']) == 5
    for topic, role in ROLES.items():
        fact = defs['TypedFact_' + topic]['properties']
        assert fact['topic']['const'] == topic and fact['subject_role']['const'] == role
    assert defs['TypedSelectedSupport']['properties']['event_relation']['const'] == 'SELECTED_EVENT'
    for name in ('TypedEventClause', 'TypedPublicationClause'):
        assert defs[name]['properties']['passages']['items']['minimum'] == 1
    def check(x):
        if isinstance(x, dict):
            assert not set(x) & {'if','then','else','allOf','oneOf','discriminator'}
            if x.get('type') == 'object':
                assert x['additionalProperties'] is False
                assert set(x['required']) == set(x['properties'])
            for v in x.values(): check(v)
        elif isinstance(x, list):
            for v in x: check(v)
    check(s)


@pytest.mark.parametrize('bad', ['schema','prompt','evidence','authority','tools','store','packet','version','digest'])
def test_request_changes_fail_before_any_reservation(linked_case, bad):
    p, r, d, _, m = typed_case(linked_case)
    if bad == 'schema': r['body']['text']['format']['schema']['required'] = []
    if bad == 'prompt': r['body']['input'][0]['content'] += 'Changed instructions'
    if bad == 'evidence': r['body']['input'][1]['content'] += 'Changed source'
    if bad == 'authority': r['body']['input'][0]['content'] = r['body']['input'][0]['content'].replace(canonical(m['strategy']['text']),canonical('Invented rule'))
    if bad == 'tools': r['body']['tools'] = [{'type':'web_search'}]
    if bad == 'store': r['body']['store'] = True
    if bad == 'packet': r['packet_id'] = '0'*64
    if bad == 'version': r['prompt_version'] = 'governed-research-v17'
    r['request_id'] = digest(dict(version=r['implementation_version'],prompt_version=r['prompt_version'],body=r['body']))
    if bad == 'digest': r['request_id'] = '0'*64
    class Forbidden:
        def respond(self,body): raise AssertionError('Provider forbidden')
    ledger = AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ValueError): execute_once(ledger,p,r,Forbidden(),lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0] == 0
    finally: ledger.close()


def test_duplicate_topic_rejected_and_original_answer_replays_exactly(linked_case):
    p,r,d,ref,m = typed_case(linked_case); original = deepcopy(d); calls=[]
    bad = deepcopy(d); bad['research']['facts'][0] = deepcopy(bad['research']['facts'][1])
    with pytest.raises(ValueError,match='TYPED_FACT_SET_MISMATCH'): parse_response(p,r,reply(bad),NOW)
    class Provider:
        def respond(self,body): calls.append(body); return reply(d)
    path=ledger_path(); ledger=AttemptLedger(path,1)
    try: out=execute_once(ledger,p,r,Provider(),lambda:NOW)
    finally: ledger.close()
    ledger=AttemptLedger(path,1)
    try: assert execute_once(ledger,p,r,Provider(),lambda:NOW) == out
    finally: ledger.close()
    assert len(calls)==1 and d==original and not out['eligible_for_handoff']
    assert out['research_binding']['extraction_instructions']['request_id'] == r['request_id']
    assert out['research_binding']['economic_inventory']['implementation_version'] == VERSIONS[0]
    verify_source_summary(p,d,out['economic_summary'])
    assert audit_reference_coverage(p,r,d,ref)['implementation_version']=='1.4.0-reference-location-audit'
    assert prepare_checklist(p,r,d,ref)['scope']==d['assessment_scope']
    size=len(canonical(r['body']).encode())
    assert prepare_typed_request(p,m,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ValueError,match='INPUT_LIMIT_EXCEEDED_NO_TRUNCATION'):
        prepare_typed_request(p,m,'offline-fixture',12000,size-1,NOW)


def test_omission_queue_separates_narrative_inventory_and_uncited_without_repair(linked_case):
    p,r,d,ref,m=typed_case(linked_case)
    nums=d['economic_inventory']['terms'][0]['amounts']['entries'][0]['passages']
    d['economic_inventory']['terms']=[];d['economic_inventory']['status']='UNRESOLVED'
    before=deepcopy(d); report=omission_report(p,r,d,ref)
    assert all(next(row for row in report['passages'] if row['number']==n)['location_status']=='UNSELECTED_REVIEW' for n in nums)
    assert d==before and report['reference_rows'][0]['unselected_spans']
    d['research']['context_notes'].append(dict(kind='CONDITIONALITY',finding='No fee, deliberately false.',passages=nums))
    report=omission_report(p,r,d,ref)
    assert all(next(row for row in report['passages'] if row['number']==n)['location_status']=='NARRATIVE_ONLY_REVIEW' for n in nums)
    assert not report['reference_rows'][0]['unselected_spans']
    assert report['semantic_acceptance']=='NOT_ESTABLISHED' and not report['eligible_for_handoff']
    verify_omission_report(p,r,d,ref,report)
    report['review_queue']=[]
    with pytest.raises(ValueError,match='OMISSION_REPORT_MISMATCH'):verify_omission_report(p,r,d,ref,report)


def test_unindexed_unicode_and_repeated_source_text_is_not_silently_lost(linked_case,monkeypatch):
    import research_omissions as module
    from test_research_reference_coverage import fixture
    p,r,d,ref,nums=fixture(linked_case,'Quoted “risk”\\details\nRepeat. Repeat. Payment is conditional.')
    from research_linked import numbered_passages
    original=numbered_passages(p)
    # Simulate a catalog hole to ensure the report exposes indexing limits.
    monkeypatch.setattr(module,'numbered_passages',lambda packet:{n:v for n,v in original.items() if n not in nums})
    out=omission_report(p,r,d,ref)
    src=next(s for s in out['source_texts'] if s['source_id']==ref['cases'][0]['expectations'][0]['source_id'])
    assert src['text']==ref['cases'][0]['expectations'][0]['quote']
    assert src['catalog_status']=='UNINDEXED_TEXT_REQUIRES_REVIEW' and src['unindexed_spans']
    assert out['summary_completeness']=='NOT_ESTABLISHED'


def test_exact_inventory_citation_still_does_not_approve_false_prose(linked_case):
    p,r,d,ref,_=typed_case(linked_case)
    d['economic_inventory']['terms'][0]['conditions']['entries'][0]['statement']='No approval required, deliberately false.'
    out=parse_response(p,r,reply(d),NOW);report=omission_report(p,r,d,ref)
    assert not out['eligible_for_handoff'] and report['semantic_acceptance']=='NOT_ESTABLISHED'
    assert any(row['location_status']=='SELECTED_FOR_INVENTORY' for row in report['passages'])
    assert uncovered(0,10,[(0,3),(2,5),(8,12)])==[(5,8)]


@pytest.mark.parametrize('bad',['source_wording','queue','trace','draft_binding','reference_binding','semantic_status'])
def test_saved_omission_report_cannot_drop_or_relabel_evidence(linked_case,bad):
    p,r,d,ref,_=typed_case(linked_case);report=omission_report(p,r,d,ref)
    if bad=='source_wording':report['source_texts'][0]['text']='Altered source'
    if bad=='queue':report['passages']=[]
    if bad=='trace':report['trace']['candidate_id']='Invented candidate'
    if bad=='draft_binding':report['draft_digest']='0'*64
    if bad=='reference_binding':report['reference_digest']='0'*64
    if bad=='semantic_status':report['semantic_acceptance']='ACCEPTED'
    with pytest.raises(ValueError,match='OMISSION_REPORT_MISMATCH'):verify_omission_report(p,r,d,ref,report)


def test_evidence_gap_cannot_be_tagged_as_unrelated_context():
    from research_typed import TypedGap
    data={k:'Offline gap fixture' for k in ('missing_fact','why_material','captured_evidence_limit','already_established','why_needed_for_this_scope')}
    data['support']=dict(event_relation='SELECTED_EVENT',clauses=[])
    TypedGap.model_validate(data)
    data['support']['event_relation']='CONTEXT'
    with pytest.raises(ValueError):TypedGap.model_validate(data)


def test_historical_cli_prepares_v18_without_provider(linked_case,monkeypatch,capsys):
    import run_research_reviewer as cli
    monkeypatch.setattr(cli, "prepare_request", prepare_typed_request)
    assert cli.prepare_request is prepare_typed_request
    p,_,_,_,m=typed_case(linked_case); root=ledger_path().parent
    for name,value in [('p',p),('m',m)]: (root/(name+'.json')).write_text(canonical(value),encoding='utf-8')
    def forbidden(*a,**k):raise AssertionError('Provider forbidden')
    monkeypatch.setattr(cli,'OpenAIReviewer',forbidden)
    monkeypatch.setattr(cli,'inspect_packet',lambda *a:dict(report_id='fixture',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(root/'p.json'),'--masters',str(root/'m.json'),
        '--model','offline-fixture','--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main(); result=json.loads(capsys.readouterr().out)
    assert result['model_calls']==0 and not result['eligible_for_handoff']
