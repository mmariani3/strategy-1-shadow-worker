"""Author-created offline infrastructure fixtures; never repaired provider answers."""
from copy import deepcopy
import json
import pytest
from evidence_review import canonical, digest
from research_scope import (VERSIONS, INSTRUCTIONS, prepare_scope_request, project_draft,
    source_summary, verify_source_summary)
from research_reviewer import parse_response
from research_linked import numbered_passages
from research_reference_coverage import audit_reference_coverage
from research_completeness_review import prepare_checklist, record_completeness_review
from review_attempts import execute_once, AttemptLedger
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_passages import passage_case
from test_research_linked import linked_case, draft_for
from test_research_reference_coverage import fixture


def make_case(linked_case):
    text=('Closing requires approval by a majority of votes cast by shareholders unaffiliated '
          'with Founder A or Buyer B AND required regulatory approval. Financing is not a '
          'closing condition. Payment of $10 per share is due only upon closing. '
          'An additional contingent right may expire worthless. The call tomorrow is not publication time.')
    p,old,d,ref,nums=fixture(linked_case,text)
    def facet(statement,basis='NOT_TEMPORAL'):
        return dict(status='RECORDED',reason='Source-authored infrastructure fixture.',
            entries=[dict(statement=statement,time_basis=basis,passages=nums)])
    term=dict(label='Conditional payment',event_relation='SELECTED_EVENT',nature='COMMITMENT',
        amounts=facet('$10 per share.'),conditions=facet('Shareholder approval.'),
        timing=facet('Payment only upon closing.','PAYMENT_OR_EFFECTIVE'),
        qualifications=facet('Contingent right may expire worthless.'))
    scope=d['materiality_coverage'].pop('assessment_scope')
    draft=dict(assessment_scope=scope,economic_inventory=dict(status='RECORDED_UNVERIFIED',
        unresolved=['Independent semantic review pending.'],terms=[term]),research=d)
    r=prepare_scope_request(p,linked_case[2],'offline-fixture',12000,250000,NOW)
    return p,r,draft,ref,linked_case[2]


def test_one_scope_and_unabridged_conditions_visible_despite_short_model_prose(linked_case):
    p,r,d,ref,m=make_case(linked_case);original=deepcopy(d)
    d['assessment_scope']='  '+d['assessment_scope']+'\n'
    original=deepcopy(d);out=parse_response(p,r,reply(d),NOW)
    summary=out['economic_summary'];verify_source_summary(p,d,summary)
    entry=summary['rows'][0]['conditions']['entries'][0]
    assert entry['statement']=='Shareholder approval.'
    words=' '.join(x['text'] for x in entry['source_passages'])
    for key in ('majority of votes cast','Founder A or Buyer B','AND required regulatory','not a','only upon closing','expire worthless'):
        assert key in words
    assert summary['assessment_scope']==d['assessment_scope'] and summary['scope_origin']==['assessment_scope']
    assert not out['eligible_for_handoff'] and summary['semantic_completeness']=='NOT_ESTABLISHED'
    binding=out['research_binding']['economic_inventory']
    assert binding['original_draft_digest']==digest(original) and binding['trace']==p['trace']
    assert binding['request_id']==r['request_id'] and binding['original_inventory']==d['economic_inventory']
    assert d==original
    schema=r['body']['text']['format']['schema'];assert 'assessment_scope' in schema['required']
    assert not any('assessment_scope' in s.get('properties',{}) for s in schema['$defs'].values())
    assert schema['$defs']['ScopeCoverage']['properties']['subject_symbol']['enum']==[p['symbol']]


@pytest.mark.parametrize('bad',['inventory_scope','coverage_scope','missing_scope','blank_scope','number_scope','unknown_passage','bool_passage','metadata','extra_approval'])
def test_bad_new_envelopes_fail_closed(linked_case,bad):
    p,r,d,_,_=make_case(linked_case)
    if bad=='inventory_scope':d['economic_inventory']['assessment_scope']=d['assessment_scope']
    if bad=='coverage_scope':d['research']['materiality_coverage']['assessment_scope']=d['assessment_scope']
    if bad=='missing_scope':d.pop('assessment_scope')
    if bad=='blank_scope':d['assessment_scope']=' \n'
    if bad=='number_scope':d['assessment_scope']=1
    if bad=='unknown_passage':d['economic_inventory']['terms'][0]['conditions']['entries'][0]['passages']=[999999]
    if bad=='bool_passage':d['economic_inventory']['terms'][0]['conditions']['entries'][0]['passages']=[True]
    if bad=='metadata':d['economic_inventory']['terms'][0]['conditions']['entries'][0]['passages']=[next(n for n,v in numbered_passages(p).items() if v['category']=='PUBLICATION_METADATA')]
    if bad=='extra_approval':d['research']['claims'][0]['evidence_state']='OBSERVED_SUPPORT'
    with pytest.raises(ValueError):parse_response(p,r,reply(d),NOW)


@pytest.mark.parametrize('bad',['drop_source','shorten_source','change_party','source_id','model_text','scope','drop_term','type_identity'])
def test_loss_or_tampering_of_mandatory_source_wording_rejected(linked_case,bad):
    p,r,d,_,_=make_case(linked_case);s=parse_response(p,r,reply(d),NOW)['economic_summary']
    entry=s['rows'][0]['conditions']['entries'][0]
    if bad=='drop_source':entry.pop('source_passages')
    if bad=='shorten_source':entry['source_passages'][0]['text']='Approval.'
    if bad=='change_party':entry['source_passages'][0]['quote']='Different voter group'
    if bad=='source_id':entry['source_passages'][0]['source_id']='0'*64
    if bad=='model_text':entry['statement']='Unconditional payment'
    if bad=='scope':s['assessment_scope']='Changed'
    if bad=='drop_term':s['rows']=[]
    if bad=='type_identity':s['rows'][0]['term_index']=False
    with pytest.raises(ValueError,match='SOURCE_WORDING_SUMMARY_MISMATCH'):verify_source_summary(p,d,s)


@pytest.mark.parametrize('bad',['instruction','schema','source','authority','tools','store','digest','version','packet'])
def test_altered_requests_fail_before_call_reservation(linked_case,bad):
    p,r,d,_,m=make_case(linked_case)
    if bad=='instruction':r['body']['input'][0]['content']=r['body']['input'][0]['content'].replace(INSTRUCTIONS,'')
    if bad=='schema':r['body']['text']['format']['schema']['required']=[]
    if bad=='source':r['body']['input'][1]['content']+='altered'
    if bad=='authority':r['body']['input'][0]['content']=r['body']['input'][0]['content'].replace(canonical(m['strategy']['text']),canonical('Invented rules'))
    if bad=='tools':r['body']['tools']=[dict(type='web_search')]
    if bad=='store':r['body']['store']=True
    if bad=='packet':r['packet_id']='0'*64
    if bad=='version':r['prompt_version']='governed-research-v16'
    r['request_id']=digest(dict(version=r['implementation_version'],prompt_version=r['prompt_version'],body=r['body']))
    if bad=='digest':r['request_id']='0'*64
    class Forbidden:
        def respond(self,body):raise AssertionError('Provider forbidden')
    ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ValueError):execute_once(ledger,p,r,Forbidden(),lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()


def test_new_projection_does_not_repair_historical_scope_failure(linked_case):
    from test_research_terms import make_case as old_case
    p,r,d,_,_,_=old_case(linked_case)
    d['economic_inventory']['assessment_scope']='Different scope'
    with pytest.raises(ValueError,match='INVENTORY_SCOPE_MISMATCH'):parse_response(p,r,reply(d),NOW)
    with pytest.raises(ValueError):project_draft(d)


@pytest.mark.parametrize('scope_whitespace',[False,True])
def test_source_locations_do_not_certify_false_or_omitted_conditions(linked_case,scope_whitespace):
    p,r,d,ref,m=make_case(linked_case)
    if scope_whitespace:d['assessment_scope']='  '+d['assessment_scope']+'\n'
    d['economic_inventory']['terms'][0]['conditions']['entries'][0]['statement']='No approval required. Deliberately false.'
    out=parse_response(p,r,reply(d),NOW)
    assert out['economic_summary']['semantic_completeness']=='NOT_ESTABLISHED' and not out['eligible_for_handoff']
    audit=audit_reference_coverage(p,r,d,ref);assert audit['implementation_version']=='1.3.0-reference-location-audit'
    assert audit['rows'][0]['location_status']=='FULLY_SELECTED'
    assessment=prepare_checklist(p,r,d,ref)
    assert assessment['scope']==d['assessment_scope']
    assessment.update(assessor_id='Offline author fixture',assessor_kind='AI_IMPLEMENTATION_AUTHOR',reviewed_at=NOW)
    assessment['anchors'][0].update(relevance='REQUIRED_FOR_SCOPE',finding='MEANING_ERROR',rationale='False model prose despite full quoted source.')
    assert record_completeness_review(p,r,d,ref,assessment,NOW)['status']=='REVISIONS_REQUIRED'


def test_durable_exact_replay_and_unchanged_full_limits(linked_case):
    p,r,d,_,m=make_case(linked_case);original=deepcopy(d);calls=[]
    size=len(canonical(r['body']).encode())
    assert prepare_scope_request(p,m,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ValueError,match='INPUT_LIMIT_EXCEEDED_NO_TRUNCATION'):prepare_scope_request(p,m,'offline-fixture',12000,size-1,NOW)
    class Provider:
        def respond(self,body):calls.append(body);return reply(d)
    path=ledger_path();ledger=AttemptLedger(path,1)
    try:out=execute_once(ledger,p,r,Provider(),lambda:NOW)
    finally:ledger.close()
    ledger=AttemptLedger(path,1)
    try:assert execute_once(ledger,p,r,Provider(),lambda:NOW)==out
    finally:ledger.close()
    assert len(calls)==1 and d==original


def test_historical_cli_single_scope_without_provider(linked_case,monkeypatch,capsys):
    import run_research_reviewer as cli
    monkeypatch.setattr(cli,'prepare_request',prepare_scope_request)
    assert cli.prepare_request is prepare_scope_request
    p,_,_,_,m=make_case(linked_case);root=ledger_path().parent
    for name,v in [('p',p),('m',m)]: (root/(name+'.json')).write_text(canonical(v),encoding='utf-8')
    def forbidden(*a,**k):raise AssertionError('Provider forbidden')
    monkeypatch.setattr(cli,'OpenAIReviewer',forbidden)
    monkeypatch.setattr(cli,'inspect_packet',lambda *a:dict(report_id='fixture',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(root/'p.json'),'--masters',str(root/'m.json'),
        '--model','offline-fixture','--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main();out=json.loads(capsys.readouterr().out)
    assert out['model_calls']==0 and not out['eligible_for_handoff']
    from pathlib import Path
    assert json.loads(Path(out['request_file']).read_text())['prompt_version']==VERSIONS[1]
