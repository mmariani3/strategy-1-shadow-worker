"""v20 infrastructure fixtures: binding and attribution, not model-accuracy claims."""
from copy import deepcopy
import json
import pytest
from evidence_review import canonical, digest
from research_semantics import (VERSIONS, INSTRUCTIONS, prepare_semantic_request,
    validate_semantic_request)
from research_reviewer import parse_response
from research_completeness_review import prepare_checklist
from research_meaning_review import meaning_dossier
from research_scope import verify_source_summary
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_tiers import case


def test_new_prompt_preserves_complete_inputs_schema_and_original_output(linked_case):
    p,old,d,ref,m=case(linked_case);original=deepcopy(d)
    r=prepare_semantic_request(p,m,'offline-fixture',12000,250000,NOW)
    assert r['body']['input'][1]==old['body']['input'][1]
    assert r['body']['text']==old['body']['text'] and r['body']['tools']==[] and r['body']['store'] is False
    assert r['body']['input'][0]['content']==old['body']['input'][0]['content']+'\n'+INSTRUCTIONS
    assert r['request_id']!=old['request_id'] and r['masters_digest']==old['masters_digest']
    validate_semantic_request(p,r)
    out=parse_response(p,r,reply(d),NOW);verify_source_summary(p,d,out['economic_summary'])
    assert d==original and not out['eligible_for_handoff']
    assert out['review_artifact']['review']['implementation_version']==VERSIONS[0]
    binding=out['research_binding'];assert binding['selection_transport']['catalog_scope']==r['request_id']
    assert binding['economic_inventory']['request_id']==r['request_id']
    assert binding['extraction_instructions']['prompt_version']==VERSIONS[1]
    assert prepare_checklist(p,r,d,ref)['scope']==d['assessment_scope']
    assert meaning_dossier(p,r,d,ref)['original_versions']['prompt']==VERSIONS[1]


@pytest.mark.parametrize('field',['prompt','schema','source','master','tools','version','digest'])
def test_new_requests_are_verified_before_any_reservation(linked_case,field):
    p,_,_,_,m=case(linked_case);r=prepare_semantic_request(p,m,'offline-fixture',12000,250000,NOW)
    if field=='prompt':r['body']['input'][0]['content']=r['body']['input'][0]['content'].replace(INSTRUCTIONS,'')
    if field=='schema':r['body']['text']['format']['schema']['required']=[]
    if field=='source':r['body']['input'][1]['content']+=' changed'
    if field=='master':r['body']['input'][0]['content']=r['body']['input'][0]['content'].replace(canonical(m['strategy']['text']),canonical('Different governing rules'))
    if field=='tools':r['body']['tools']=[dict(type='web_search')]
    if field=='version':r['prompt_version']='governed-research-v19'
    r['request_id']=digest(dict(version=r['implementation_version'],prompt_version=r['prompt_version'],body=r['body']))
    if field=='digest':r['request_id']='0'*64
    class Forbidden:
        def respond(self,body):pytest.fail('Provider must not be called')
    ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ValueError):execute_once(ledger,p,r,Forbidden(),lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()


def test_full_input_limit_and_default_prepare_only_cli(linked_case,monkeypatch,capsys):
    import run_research_reviewer as cli
    p,_,_,_,m=case(linked_case);r=prepare_semantic_request(p,m,'offline-fixture',12000,250000,NOW)
    size=len(canonical(r['body']).encode())
    assert prepare_semantic_request(p,m,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ValueError,match='INPUT_LIMIT_EXCEEDED_NO_TRUNCATION'):
        prepare_semantic_request(p,m,'offline-fixture',12000,size-1,NOW)
    assert cli.prepare_request is prepare_semantic_request
    root=ledger_path().parent
    for name,value in [('packet',p),('masters',m)]:
        (root/(name+'.json')).write_text(json.dumps(value),encoding='utf-8')
    monkeypatch.setattr(cli,'OpenAIReviewer',lambda *a:pytest.fail('No provider'))
    monkeypatch.setattr(cli,'inspect_packet',lambda *a:dict(report_id='fixture',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(root/'packet.json'),'--masters',str(root/'masters.json'),
        '--model','offline-fixture','--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main();assert json.loads(capsys.readouterr().out)['model_calls']==0


def test_historical_route_and_retry_results_are_preserved(linked_case):
    p,old,d,_,m=case(linked_case);original=parse_response(p,old,reply(d),NOW)
    r=prepare_semantic_request(p,m,'offline-fixture',12000,250000,NOW);calls=[]
    class Provider:
        def respond(self,body):calls.append(body);return reply(d)
    path=ledger_path();ledger=AttemptLedger(path,1)
    try:out=execute_once(ledger,p,r,Provider(),lambda:NOW)
    finally:ledger.close()
    ledger=AttemptLedger(path,1)
    try:assert execute_once(ledger,p,r,Provider(),lambda:NOW)==out
    finally:ledger.close()
    assert len(calls)==1 and not out['eligible_for_handoff']
    assert parse_response(p,old,reply(d),NOW)==original


def test_instruction_change_does_not_claim_automated_semantic_detection(linked_case):
    p,_,d,ref,m=case(linked_case);r=prepare_semantic_request(p,m,'offline-fixture',12000,250000,NOW)
    d['economic_inventory']['terms'][0]['conditions']['reason']='An intentionally unsupported inferred condition in this synthetic fixture.'
    # Parser checks shape and source binding; it must not be advertised as an entailment classifier.
    out=parse_response(p,r,reply(d),NOW)
    assert not out['eligible_for_handoff']
    di=meaning_dossier(p,r,d,ref)
    term=next(x for x in di['items'] if x['kind']=='ECONOMIC_TERM')
    assert 'unsupported inferred condition' in term['original_value']['conditions']['reason']
    assert di['semantic_acceptance']=='NOT_ESTABLISHED'
