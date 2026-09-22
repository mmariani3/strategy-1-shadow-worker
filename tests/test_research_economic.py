"""Offline v15 protocol tests, not evidence of model compliance or strategy edge."""
from copy import deepcopy
import json
import pytest
from evidence_review import canonical, digest
from research_economic import (VERSIONS, ECONOMIC_INSTRUCTIONS, prepare_economic_request,
    validate_economic_request)
from research_reviewer import parse_response, ReviewBlocked
from research_reference_coverage import audit_reference_coverage
from research_completeness_review import prepare_checklist, record_completeness_review
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_passages import passage_case
from test_research_linked import linked_case, draft_for
from test_research_reference_coverage import fixture


def request_for(p, m):
    return prepare_economic_request(p, m, 'offline-fixture', 12000, 250000, NOW)


def test_versioned_prompt_preserves_entire_source_schema_and_limits(linked_case):
    p, old, m = linked_case; frozen = deepcopy((p, old, m)); r = request_for(p, m)
    assert r['request_id'] != old['request_id']
    assert r['body']['input'][1] == old['body']['input'][1]
    assert r['body']['text'] == old['body']['text']
    assert r['body']['model'] == old['body']['model']
    assert r['body']['max_output_tokens'] == old['body']['max_output_tokens']
    assert r['body']['input'][0]['content'] == old['body']['input'][0]['content']+'\n'+ECONOMIC_INSTRUCTIONS
    assert validate_economic_request(p,r)['strategy']['text'] == m['strategy']['text']
    assert (p,old,m) == frozen
    size = len(canonical(r['body']).encode())
    assert prepare_economic_request(p,m,'offline-fixture',12000,size,NOW) == r
    with pytest.raises(ReviewBlocked,match='INPUT_LIMIT_EXCEEDED_NO_TRUNCATION'):
        prepare_economic_request(p,m,'offline-fixture',12000,size-1,NOW)


@pytest.mark.parametrize('bad',['instructions','authority','source','schema','tools','store','digest','version','packet'])
def test_tampered_requests_stop_before_reservation(linked_case,bad):
    p,_,m=linked_case;r=request_for(p,m)
    if bad=='instructions':r['body']['input'][0]['content']=r['body']['input'][0]['content'].replace(ECONOMIC_INSTRUCTIONS,'')
    if bad=='authority':r['body']['input'][0]['content']=r['body']['input'][0]['content'].replace(canonical(m['strategy']['text']),canonical('New invented rules'))
    if bad=='source':r['body']['input'][1]['content']+='Truncated or altered source'
    if bad=='schema':r['body']['text']['format']['strict']=False
    if bad=='tools':r['body']['tools']=[dict(type='web_search')]
    if bad=='store':r['body']['store']=True
    if bad=='version':r['prompt_version']='governed-research-v14'
    if bad=='packet':r['packet_id']='0'*64
    r['request_id']=digest(dict(version=r['implementation_version'],prompt_version=r['prompt_version'],body=r['body']))
    if bad=='digest':r['request_id']='0'*64
    class Forbidden:
        def respond(self,body):raise AssertionError('No provider permitted')
    ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ValueError):execute_once(ledger,p,r,Forbidden(),lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()


def test_durable_result_records_actual_prompt_and_parser(linked_case):
    p,old,m=linked_case;r=request_for(p,m);draft=draft_for(p,m);raw=reply(draft);before=deepcopy(raw);calls=[]
    class Provider:
        def respond(self,body):calls.append(body);return raw
    path=ledger_path();ledger=AttemptLedger(path,1)
    try:out=execute_once(ledger,p,r,Provider(),lambda:NOW)
    finally:ledger.close()
    ledger=AttemptLedger(path,1)
    try:assert execute_once(ledger,p,r,Provider(),lambda:NOW)==out
    finally:ledger.close()
    assert len(calls)==1 and raw==before
    review=out['review_artifact']['review'];binding=out['research_binding']
    assert (review['implementation_version'],review['prompt_version'])==VERSIONS
    assert binding['support_review']['implementation_version']==old['implementation_version']
    assert binding['selection_transport']['catalog_scope']==r['request_id']
    assert binding['extraction_instructions']['compliance']=='NOT_ESTABLISHED'
    assert binding['tier_review']['approval']=='NOT_APPROVED' and not out['eligible_for_handoff']
    assert out['review_artifact']['trace']==p['trace']
    historical=parse_response(p,old,before,NOW)
    assert historical['prompt_version']=='governed-research-v14'
    assert 'extraction_instructions' not in historical['research_binding']


@pytest.mark.parametrize('bad',['tier_approval','event_time','no_source','invalid_selection'])
def test_new_prompt_does_not_weaken_existing_gates(linked_case,bad):
    p,_,m=linked_case;r=request_for(p,m);d=draft_for(p,m)
    if bad=='tier_approval':next(c for c in d['claims'] if c['criterion']=='catalyst_materiality_tier')['evidence_state']='OBSERVED_SUPPORT'
    if bad=='event_time':next(f for f in d['facts'] if f['topic']=='event_timing')['support']['clauses'][0]['time_basis']='PUBLICATION'
    if bad=='no_source':next(f for f in d['facts'] if f['topic']=='catalyst_event')['support']['clauses']=[]
    if bad=='invalid_selection':d['context_notes']=[dict(kind='CONDITIONALITY',finding='Synthetic condition',passages=[999999])]
    with pytest.raises(ValueError):parse_response(p,r,reply(d),NOW)


@pytest.mark.parametrize('missing',[True,False])
def test_source_omission_and_false_prose_still_need_attributed_review(linked_case,missing):
    p,old,d,ref,nums=fixture(linked_case,'Fee $12M; Earned on signing even if funding is not drawn.')
    m=linked_case[2];r=request_for(p,m)
    d['materiality_coverage']['status']='SUFFICIENT_FOR_RESEARCH'
    d['materiality_coverage']['support']=deepcopy(d['selected_event']['support'])
    if not missing:d['context_notes']=[dict(kind='CONDITIONALITY',finding='No fee is owed. Deliberately false.',passages=nums)]
    original=deepcopy(d);out=parse_response(p,r,reply(d),NOW)
    assert not out['eligible_for_handoff']
    assert out['research_binding']['extraction_instructions']['semantic_completeness']=='NOT_ESTABLISHED'
    old_audit=audit_reference_coverage(p,old,d,ref)
    new_audit=audit_reference_coverage(p,r,d,ref)
    assert new_audit['rows']==old_audit['rows']
    assert new_audit['request_id']==r['request_id'] and new_audit['implementation_version']=='1.1.0-reference-location-audit'
    assert old_audit['implementation_version']=='1.0.0-reference-location-audit'
    assessment=prepare_checklist(p,r,d,ref)
    assessment.update(assessor_id='Synthetic offline test author',assessor_kind='AI_IMPLEMENTATION_AUTHOR',reviewed_at=NOW)
    assessment['anchors'][0].update(relevance='REQUIRED_FOR_SCOPE',finding='MATERIAL_OMISSION' if missing else 'MEANING_ERROR',rationale='Explicit synthetic source/prose assessment.')
    report=record_completeness_review(p,r,d,ref,assessment,NOW)
    assert report['status']=='REVISIONS_REQUIRED' and not report['eligible_for_handoff']
    assert d==original and report['original_admission']=='NOT_EVALUATED_OR_CHANGED'


def test_default_cli_prepares_v15_without_provider_or_credentials(linked_case,monkeypatch,capsys):
    import run_research_reviewer as cli
    assert cli.prepare_request is prepare_economic_request
    p,_,m=linked_case;root=ledger_path().parent
    (root/'p.json').write_text(canonical(p),encoding='utf-8');(root/'m.json').write_text(canonical(m),encoding='utf-8')
    def forbidden(*a,**k):raise AssertionError('No provider or credentials')
    monkeypatch.setattr(cli,'OpenAIReviewer',forbidden)
    monkeypatch.setattr(cli,'inspect_packet',lambda *a:dict(report_id='fixture',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(root/'p.json'),'--masters',str(root/'m.json'),
        '--model','offline-fixture','--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main();result=json.loads(capsys.readouterr().out)
    prepared=json.loads(__import__('pathlib').Path(result['request_file']).read_text())
    assert result['model_calls']==0 and prepared['prompt_version']==VERSIONS[1]
