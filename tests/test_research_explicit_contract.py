"""Synthetic infrastructure-only contract tests. No provider calls or repairs."""
from copy import deepcopy
import json
import pytest
from evidence_review import canonical,digest
from research_explicit_contract import (VERSIONS,INSTRUCTIONS,prepare_explicit_request,
    validate_explicit_request,validate_explicit_draft)
from research_semantics import prepare_semantic_request
from research_tiers import tier_choices
from research_meaning_review import passage_numbers
from research_linked import numbered_passages
from research_facts import SUBSTANTIVE
from research_reviewer import parse_response
from review_attempts import AttemptLedger,execute_once
from test_evidence_review import authorities,snapshot,NOW
from test_research_reviewer import masters,ledger_path
from test_research_facts import fact_case,reply
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_tiers import case


def explicit_case(linked_case):
    p,_,d,ref,m=case(linked_case)
    n=tier_choices(m)['A'][0];d['research']['tier_proposal'].update(
        mapping_status='PROPOSED',proposed_tier='A',rules=[n],fact_topics=['catalyst_event'])
    i=next(i for i,f in enumerate(d['research']['facts']) if f['topic']=='catalyst_event')
    nums=sorted(set(passage_numbers(d['research']['facts'][i]['support'])))
    x=dict(draft=d,rule_applications=[dict(rule_number=n,explanation='Synthetic explanation requiring source review.',fact_index=i,passages=nums)],term_assertions=[dict(term_index=0,status='RECORDED',statement='Conditional payment stated by the source.',passages=d['economic_inventory']['terms'][0]['amounts']['entries'][0]['passages'],reason='Source meaning still requires review.')])
    r=prepare_explicit_request(p,m,'offline-fixture',12000,250000,NOW)
    return p,r,x,m


def test_full_inputs_original_output_and_complete_source_wording_retained(linked_case):
    p,r,x,m=explicit_case(linked_case);old=prepare_semantic_request(p,m,'offline-fixture',12000,250000,NOW)
    assert r['body']['input'][1]==old['body']['input'][1] and r['body']['tools']==[] and r['body']['store'] is False
    assert r['body']['input'][0]['content']==old['body']['input'][0]['content']+'\n'+INSTRUCTIONS
    text=json.dumps(x,indent=2);original=deepcopy(x)
    result=validate_explicit_draft(p,r,text)
    assert result['original_response_text']==text and result['original_draft']==x==original
    assert result['trace']==p['trace'] and not result['eligible_for_handoff']
    assert result['semantic_acceptance']=='NOT_ESTABLISHED' and result['prompt_version']==VERSIONS[1]
    cat=numbered_passages(p)
    for row in result['rule_applications']+result['term_assertions']:
        for s in row['source_passages']:assert s==dict(number=s['number'],**cat[s['number']])
    _,base=validate_explicit_request(p,r);assert base==old
    assert not parse_response(p,old,reply(x['draft']),NOW)['eligible_for_handoff']


@pytest.mark.parametrize('bad',['missing_rule','duplicate_rule','wrong_rule','blank_explanation','wrong_fact','unlinked_source','unknown_source','duplicate_source','metadata_source','bool_rule','string_fact','extra_approval'])
def test_rule_link_and_exact_set_fail_closed(linked_case,bad):
    p,r,x,m=explicit_case(linked_case);a=x['rule_applications'][0]
    if bad=='missing_rule':x['rule_applications']=[]
    if bad=='duplicate_rule':x['rule_applications'].append(deepcopy(a))
    if bad=='wrong_rule':a['rule_number']=99999
    if bad=='blank_explanation':a['explanation']=' \n'
    if bad=='wrong_fact':a['fact_index']=next(i for i,f in enumerate(x['draft']['research']['facts']) if f['topic']=='publication_timing')
    if bad=='unlinked_source':a['passages']=[next(n for n,v in numbered_passages(p).items() if v['category'] in SUBSTANTIVE and n not in a['passages'])]
    if bad=='unknown_source':a['passages']=[999999]
    if bad=='duplicate_source':a['passages']*=2
    if bad=='metadata_source':a['passages']=[next(n for n,v in numbered_passages(p).items() if v['category']=='PUBLICATION_METADATA')]
    if bad=='bool_rule':a['rule_number']=True
    if bad=='string_fact':a['fact_index']=str(a['fact_index'])
    if bad=='extra_approval':a['approved']=True
    with pytest.raises(ValueError):validate_explicit_draft(p,r,canonical(x))


@pytest.mark.parametrize('bad',['missing','duplicate','index','blank_statement','empty_sources','unknown_sources','metadata','bool_index','blank_reason','unresolved_statement','unresolved_sources'])
def test_core_term_contract_fail_closed(linked_case,bad):
    p,r,x,m=explicit_case(linked_case);a=x['term_assertions'][0]
    if bad=='missing':x['term_assertions']=[]
    if bad=='duplicate':x['term_assertions'].append(deepcopy(a))
    if bad=='index':a['term_index']=99
    if bad=='blank_statement':a['statement']=' \n'
    if bad=='empty_sources':a['passages']=[]
    if bad=='unknown_sources':a['passages']=[999999]
    if bad=='metadata':a['passages']=[next(n for n,v in numbered_passages(p).items() if v['category']=='PUBLICATION_METADATA')]
    if bad=='bool_index':a['term_index']=False
    if bad=='blank_reason':a['reason']=' \n'
    if bad.startswith('unresolved_'):
        a.update(status='UNRESOLVED',statement='',passages=[])
        if bad=='unresolved_statement':a['statement']='Contradictory assertion'
        else:a['passages']=[1]
    with pytest.raises(ValueError):validate_explicit_draft(p,r,canonical(x))


def test_unresolved_does_not_force_rules_values_or_approval(linked_case):
    p,r,x,m=explicit_case(linked_case)
    x['draft']['research']['tier_proposal'].update(mapping_status='UNRESOLVED',proposed_tier='UNRESOLVED',rules=[],fact_topics=[])
    x['rule_applications']=[]
    x['term_assertions'][0].update(status='UNRESOLVED',statement='',passages=[],reason='Core assertion requires further source review.')
    out=validate_explicit_draft(p,r,canonical(x))
    assert not out['eligible_for_handoff'] and out['term_assertions'][0]['source_passages']==[]


def test_structurally_valid_nonsense_never_becomes_semantic_approval(linked_case):
    p,r,x,m=explicit_case(linked_case)
    x['rule_applications'][0]['explanation']='A label alone is deliberately inadequate in this fixture.'
    x['term_assertions'][0]['statement']='An intentionally unsupported statement.'
    out=validate_explicit_draft(p,r,canonical(x))
    assert out['status']=='STRUCTURE_VALIDATED_REVIEW_REQUIRED' and out['semantic_acceptance']=='NOT_ESTABLISHED'


@pytest.mark.parametrize('bad',['instructions','schema','source','tools','store','digest','version'])
def test_full_request_binding_and_dispatch_rejection(linked_case,bad):
    p,r,x,m=explicit_case(linked_case)
    if bad=='instructions':r['body']['input'][0]['content']+='tampered'
    if bad=='schema':r['body']['text']['format']['schema']['required']=[]
    if bad=='source':r['body']['input'][1]['content']+='tampered'
    if bad=='tools':r['body']['tools']=[dict(type='web_search')]
    if bad=='store':r['body']['store']=True
    if bad=='version':r['prompt_version']='governed-research-v20'
    r['request_id']=digest(dict(version=r['implementation_version'],prompt_version=r['prompt_version'],body=r['body']))
    if bad=='digest':r['request_id']='0'*64
    with pytest.raises(ValueError):validate_explicit_request(p,r)


def test_preview_cannot_use_existing_dispatcher_or_change_default(linked_case):
    import run_research_reviewer as cli
    p,r,x,m=explicit_case(linked_case);ledger=AttemptLedger(ledger_path(),1)
    class Forbidden:
        def respond(self,body):pytest.fail('Preview must not dispatch')
    try:
        with pytest.raises(ValueError):execute_once(ledger,p,r,Forbidden(),lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()
    assert cli.prepare_request is prepare_semantic_request


def test_full_size_limits_and_schema_required_fields(linked_case):
    p,r,x,m=explicit_case(linked_case);size=len(canonical(r['body']).encode())
    assert prepare_explicit_request(p,m,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ValueError,match='INPUT_LIMIT_EXCEEDED_NO_TRUNCATION'):
        prepare_explicit_request(p,m,'offline-fixture',12000,size-1,NOW)
    schema=r['body']['text']['format']['schema']
    assert set(schema['required'])=={'draft','rule_applications','term_assertions'}
    for name in ('RuleApplication','TermAssertion'):
        obj=schema['$defs'][name];assert obj['additionalProperties'] is False and set(obj['required'])==set(obj['properties'])


def test_cli_prepare_and_check_have_no_dispatch_option(linked_case,monkeypatch,capsys):
    import research_explicit_contract as cli
    p,r,x,m=explicit_case(linked_case);root=ledger_path().parent
    for name,value in [('packet',p),('masters',m),('request',r),('response',x)]:
        (root/(name+'.json')).write_text(canonical(value),encoding='utf-8')
    base=['contract','prepare','--packet',str(root/'packet.json'),'--masters',str(root/'masters.json'),'--model','offline-fixture','--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)]
    # Fixture authorities are historical; use their explicit timestamp offline.
    monkeypatch.setattr('review_attempts.utc_now',lambda:NOW)
    monkeypatch.setattr('sys.argv',base);cli.main();prepared=json.loads(capsys.readouterr().out)
    assert prepared['status']=='PREPARED_NOT_SENT' and prepared['api_calls']==0
    monkeypatch.setattr('sys.argv',base+['--dispatch'])
    with pytest.raises(SystemExit):cli.main()
    capsys.readouterr()
    monkeypatch.setattr('sys.argv',['contract','check','--packet',str(root/'packet.json'),'--request',str(root/'request.json'),'--response-text',str(root/'response.json'),'--output',str(root)])
    cli.main();first=json.loads(capsys.readouterr().out);cli.main()
    assert json.loads(capsys.readouterr().out)==first and first['api_calls']==0
