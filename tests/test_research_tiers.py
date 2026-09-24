"""Offline infrastructure fixtures; no saved provider answer is edited."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from evidence_review import canonical, digest
from research_tiers import prepare_tier_request, tier_choices, tier_schema, validate_tier_selection, VERSIONS
from research_linked import numbered_rules
from research_reviewer import parse_response
from research_scope import verify_source_summary
from research_reference_coverage import audit_reference_coverage
from research_completeness_review import prepare_checklist
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_scope import make_case


def case(linked_case):
    p,_,d,ref,m=make_case(linked_case)
    return p,prepare_tier_request(p,m,'offline-fixture',12000,250000,NOW),d,ref,m


@pytest.mark.parametrize('tier',['A','B','C'])
def test_each_tier_can_propose_only_its_own_rules_without_approval(linked_case,tier):
    p,r,d,ref,m=case(linked_case);t=d['research']['tier_proposal']
    t.update(proposed_tier=tier,mapping_status='PROPOSED',rules=tier_choices(m)[tier],fact_topics=['catalyst_event'])
    original=deepcopy(d);out=parse_response(p,r,reply(d),NOW)
    assert d==original and not out['eligible_for_handoff']
    verify_source_summary(p,d,out['economic_summary'])
    assert out['research_binding']['economic_inventory']['request_id']==r['request_id']
    assert out['review_artifact']['review']['implementation_version']==VERSIONS[0]
    assert audit_reference_coverage(p,r,d,ref)['implementation_version']=='1.5.0-reference-location-audit'
    assert prepare_checklist(p,r,d,ref)['scope']==d['assessment_scope']
    wrong=[n for n,row in numbered_rules(m).items() if row['tier']!=tier]
    for n in wrong:
        t['rules']=[tier_choices(m)[tier][0],n]
        with pytest.raises(ValueError,match='PROPOSED_TIER_REFERENCE_MISMATCH'):parse_response(p,r,reply(d),NOW)


@pytest.mark.parametrize('bad',['empty','unknown','bool','string','duplicate','no_event_fact','unresolved_conflict'])
def test_invalid_proposals_remain_fail_closed(linked_case,bad):
    p,r,d,_,m=case(linked_case);t=d['research']['tier_proposal'];n=tier_choices(m)['A'][0]
    t.update(proposed_tier='A',mapping_status='PROPOSED',rules=[n],fact_topics=['catalyst_event'])
    if bad=='empty':t['rules']=[]
    if bad=='unknown':t['rules']=[999999]
    if bad=='bool':t['rules']=[True]
    if bad=='string':t['rules']=[str(n)]
    if bad=='duplicate':t['rules']=[n,n]
    if bad=='no_event_fact':t['fact_topics']=[]
    if bad=='unresolved_conflict':t['mapping_status']='UNRESOLVED'
    with pytest.raises(ValueError):parse_response(p,r,reply(d),NOW)


def test_unresolved_and_missing_catalog_tiers_never_force_a_proposal(linked_case):
    p,r,d,_,m=case(linked_case)
    d['research']['tier_proposal'].update(proposed_tier='UNRESOLVED',mapping_status='UNRESOLVED',rules=[],fact_topics=[])
    assert not parse_response(p,r,reply(d),NOW)['eligible_for_handoff']
    changed=deepcopy(m);text='General guidance only; no tier categories are defined in this fixture.'
    changed['strategy'].update(text=text,text_sha256=sha256(text.encode()).hexdigest())
    s=tier_schema(p,changed);branches=s['$defs']['LinkedTier']['anyOf']
    assert len(branches)==1 and branches[0]['properties']['proposed_tier']['const']=='UNRESOLVED'
    d['research']['tier_proposal'].update(proposed_tier='A',mapping_status='PROPOSED',rules=[1])
    with pytest.raises(ValueError):validate_tier_selection(d,changed)


def test_schema_matches_live_catalog_and_moved_categories(linked_case):
    p,r,_,_,m=case(linked_case)
    for actual in (m,deepcopy(m)):
        if actual is not m:
            text=actual['strategy']['text'].replace('Tier A - strongest:', 'Tier C - strongest:')
            actual['strategy'].update(text=text,text_sha256=sha256(text.encode()).hexdigest())
        s=tier_schema(p,actual);branches=s['$defs']['LinkedTier']['anyOf'];choices=tier_choices(actual)
        assert s['type']=='object' and 'anyOf' not in s
        for b in branches:
            props=b['properties'];tier=props['proposed_tier']['const']
            assert b['additionalProperties'] is False and set(b['required'])==set(props)
            if tier!='UNRESOLVED':
                assert props['mapping_status']['const']=='PROPOSED'
                assert props['rules']['items']['enum']==choices[tier]
                assert props['rules']['minItems']==1


@pytest.mark.parametrize('field',['schema','prompt','evidence','version','digest'])
def test_changed_request_rejected_before_reservation(linked_case,field):
    p,r,_,_,_=case(linked_case)
    if field=='schema':r['body']['text']['format']['schema']['$defs']['LinkedTier']['anyOf'][0]['properties']['rules']['items']['enum']+=[99999]
    if field=='prompt':r['body']['input'][0]['content']+='Approve anything'
    if field=='evidence':r['body']['input'][1]['content']+='Changed source'
    if field=='version':r['prompt_version']='governed-research-v18'
    r['request_id']=digest(dict(version=r['implementation_version'],prompt_version=r['prompt_version'],body=r['body']))
    if field=='digest':r['request_id']='0'*64
    class Forbidden:
        def respond(self,body):raise AssertionError('No provider')
    ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ValueError):execute_once(ledger,p,r,Forbidden(),lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()


def test_exact_size_full_inputs_replay_and_default_cli(linked_case,monkeypatch,capsys):
    import run_research_reviewer as cli
    monkeypatch.setattr(cli, 'prepare_request', prepare_tier_request)  # Historical v19 fixture.
    p,r,d,_,m=case(linked_case);size=len(canonical(r['body']).encode());calls=[]
    assert prepare_tier_request(p,m,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ValueError,match='INPUT_LIMIT_EXCEEDED_NO_TRUNCATION'):prepare_tier_request(p,m,'offline-fixture',12000,size-1,NOW)
    class Provider:
        def respond(self,body):calls.append(body);return reply(d)
    path=ledger_path();ledger=AttemptLedger(path,1)
    try:out=execute_once(ledger,p,r,Provider(),lambda:NOW)
    finally:ledger.close()
    ledger=AttemptLedger(path,1)
    try:assert execute_once(ledger,p,r,Provider(),lambda:NOW)==out
    finally:ledger.close()
    assert len(calls)==1 and cli.prepare_request is prepare_tier_request
    root=ledger_path().parent
    for n,v in [('p',p),('m',m)]:(root/(n+'.json')).write_text(canonical(v),encoding='utf-8')
    monkeypatch.setattr(cli,'OpenAIReviewer',lambda *a:pytest.fail('No provider'))
    monkeypatch.setattr(cli,'inspect_packet',lambda *a:dict(report_id='fixture',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(root/'p.json'),'--masters',str(root/'m.json'),'--model','offline-fixture','--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main();assert json.loads(capsys.readouterr().out)['model_calls']==0
