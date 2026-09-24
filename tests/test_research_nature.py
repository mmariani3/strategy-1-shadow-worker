"""Synthetic infrastructure checks; declaration consistency is not source truth."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from evidence_review import canonical,digest
from research_nature import (VERSIONS,INSTRUCTIONS,prepare_nature_request,
    validate_nature_request,validate_natures,nature_report,nature_checklist)
from research_reviewer import parse_response,ReviewBlocked
from research_field_review import field_review,record_field_assessment,ledger_inputs
from research_explicit_review import render_explicit_review
from review_attempts import AttemptLedger,execute_once
from test_evidence_review import authorities,snapshot,NOW
from test_research_reviewer import masters,ledger_path
from test_research_facts import fact_case,reply
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_roles import role_case
from test_research_fields import assessment
from test_research_explicit_integration import FakeProvider

def declarations(x):
    assertions={a['term_index']:a for a in x['term_assertions']}
    return [dict(term_index=i,core_nature=t['nature'],core_passages=assertions[i]['passages'],
        amount_natures=[dict(entry_index=j,nature=t['nature'],passages=e['passages'],reason='Synthetic consistency fixture, not truth.') for j,e in enumerate(t['amounts']['entries'])],
        qualification_scope='Read this complete term and its locally applicable qualifications against the source.') for i,t in enumerate(x['draft']['economic_inventory']['terms'])]

def nature_case(linked_case):
    p,old,x,ref,_,m=role_case(linked_case)
    x['term_classifications']=declarations(x)
    r=prepare_nature_request(p,m,'offline-fixture',12000,250000,NOW)
    return p,r,x,ref,old,m

def test_preserves_full_input_and_old_schema_and_unresolved_core(linked_case):
    p,r,x,ref,old,m=nature_case(linked_case)
    assert validate_nature_request(p,r)[1]==old
    assert r['body']['input'][1:]==old['body']['input'][1:]
    assert r['body']['input'][0]['content']==old['body']['input'][0]['content']+'\n'+INSTRUCTIONS
    schema=r['body']['text']['format']['schema'];prior=old['body']['text']['format']['schema']
    assert all(schema['$defs'][k]==v for k,v in prior['$defs'].items())
    assert all(schema['properties'][k]==v for k,v in prior['properties'].items())
    size=len(canonical(r['body']).encode())
    assert prepare_nature_request(p,m,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ReviewBlocked,match='NO_TRUNCATION'):prepare_nature_request(p,m,'offline-fixture',12000,size-1,NOW)
    x['term_assertions'][0].update(status='UNRESOLVED',statement='',passages=[],reason='Core unavailable in this fixture.')
    x['term_classifications'][0]['core_passages']=[]
    validate_natures(x)

@pytest.mark.parametrize('bad',['instruction','schema','source','authority','tools','zero_limit','bool_limit'])
def test_invalid_request_never_reserves_or_calls(linked_case,bad):
    p,r,x,_,_,_=nature_case(linked_case)
    if bad=='instruction':r['body']['input'][0]['content']+='x'
    if bad=='schema':r['body']['text']['format']['schema']['required']=[]
    if bad=='source':r['body']['input'][-1]['content']+='x'
    if bad=='authority':r['masters_digest']='x'
    if bad=='tools':r['body']['tools']=[dict(type='web_search')]
    if bad=='zero_limit':r['body']['max_output_tokens']=0
    if bad=='bool_limit':r['body']['max_output_tokens']=True
    r['request_id']=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=r['body']))
    ledger=AttemptLedger(ledger_path(),1);provider=FakeProvider(reply(x))
    try:
        with pytest.raises(ReviewBlocked,match='NATURE_REQUEST_BINDING_MISMATCH'):execute_once(ledger,p,r,provider,lambda:NOW)
        assert provider.calls==0 and ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()

@pytest.mark.parametrize('bad',['missing_term','duplicate_term','missing_amount','duplicate_amount','bool_index','wrong_core','wrong_amount','core_source','amount_source','duplicate_source','blank_scope','blank_reason','missing_core'])
def test_inconsistent_declarations_fail_closed(linked_case,bad):
    _,_,x,_,_,_=nature_case(linked_case);rows=x['term_classifications'];row=next(v for v in rows if v['amount_natures']);amount=row['amount_natures'][0]
    if bad=='missing_term':rows.pop()
    if bad=='duplicate_term':rows.append(deepcopy(row))
    if bad=='missing_amount':row['amount_natures'].pop()
    if bad=='duplicate_amount':row['amount_natures'].append(deepcopy(amount))
    if bad=='bool_index':row['term_index']=True
    if bad=='wrong_core':row['core_nature']='FORECAST' if row['core_nature']!='FORECAST' else 'REPORTED_RESULT'
    if bad=='wrong_amount':amount['nature']='FORECAST' if amount['nature']!='FORECAST' else 'REPORTED_RESULT'
    if bad=='core_source':row['core_passages']=[999999]
    if bad=='amount_source':amount['passages']=[999999]
    if bad=='duplicate_source':amount['passages']=amount['passages']*2
    if bad=='blank_scope':row['qualification_scope']=' '
    if bad=='blank_reason':amount['reason']=' '
    if bad=='missing_core':x['term_assertions'].pop()
    with pytest.raises(ValueError):validate_natures(x)

def test_mixed_demonstration_and_forecast_split_without_losing_text(linked_case):
    _,_,x,_,_,_=nature_case(linked_case)
    terms=x['draft']['economic_inventory']['terms'];t=terms[0]
    e=deepcopy(next(t for t in terms if t['amounts']['entries'])['amounts']['entries'][0])
    e['statement']='Anticipated future production benefit from the same input.'
    t['nature']='REPORTED_RESULT';t['amounts']['status']='RECORDED';t['amounts']['entries'].append(e)
    x['term_classifications']=declarations(x)
    x['term_classifications'][0]['amount_natures'][-1]['nature']='FORECAST'
    before=deepcopy(x)
    with pytest.raises(ValueError,match='MIXED_ECONOMIC'):validate_natures(x)
    assert x==before
    new=deepcopy(t);new.update(label='Anticipated production benefit',nature='FORECAST')
    new['amounts']['entries']=[t['amounts']['entries'].pop()]
    q=deepcopy(e);q['statement']='Actual future results may differ.'
    new['qualifications'].update(status='RECORDED',entries=[q],reason='Local forecast caution retained.')
    terms.append(new)
    a=deepcopy(x['term_assertions'][0]);a.update(term_index=len(terms)-1,statement=e['statement'],passages=e['passages'])
    x['term_assertions'].append(a);x['term_classifications']=declarations(x)
    validate_natures(x)
    assert terms[-1]['amounts']['entries'][0]==e and terms[-1]['qualifications']['entries'][0]==q
    # Matching false declarations are not entailment checks; the full term must be reviewed.
    assert sum(i['kind']=='COMPLETE_ECONOMIC_TERM' for i in nature_checklist(x,'fixture'))==len(terms)

def test_rejection_keeps_raw_and_does_not_retry(linked_case):
    p,r,x,_,_,_=nature_case(linked_case);x['term_classifications']=[]
    raw=reply(x);provider=FakeProvider(raw);ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ValueError):execute_once(ledger,p,r,provider,lambda:NOW)
        assert ledger.events(r['request_id'])['RECEIVED']['payload']==raw
        with pytest.raises(ReviewBlocked):execute_once(ledger,p,r,provider,lambda:NOW)
        assert provider.calls==1 and 'COMPLETED' not in ledger.events(r['request_id'])
    finally:ledger.close()

def test_original_full_review_attribution_and_history(linked_case):
    p,r,x,ref,old,_=nature_case(linked_case);raw=reply(x)
    raw['output'][0]['content'][0]['text']=json.dumps(x,indent=2)
    path=ledger_path();ledger=AttemptLedger(path,1);provider=FakeProvider(raw)
    try:
        result=execute_once(ledger,p,r,provider,lambda:NOW)
        assert execute_once(ledger,p,r,provider,lambda:NOW)==result and provider.calls==1
    finally:ledger.close()
    before=sha256(path.read_bytes()).hexdigest()
    assert ledger_inputs(path,r['request_id'],p)==(r,raw,NOW)
    report=field_review(p,r,raw,NOW,ref)
    assert report['original_draft']==x and report['original_provider_response']==raw
    assert report['original_response_text']==raw['output'][0]['content'][0]['text']
    assert report['field_items']==nature_checklist(x,r['request_id'])
    assert result['research_binding']['economic_inventory']['implementation_version']==VERSIONS[0]
    assert result['economic_summary']['rows'] and not result['economic_summary']['eligible_for_handoff']
    assert result['review_artifact']['review']['prompt_version']==VERSIONS[1]
    a=assessment(report,'SUPPORTED');a['decisions'][-1]['finding']='REVISION_REQUIRED'
    reviewed=record_field_assessment(p,r,raw,NOW,ref,a,NOW)
    assert reviewed['status']=='REVISIONS_REQUIRED' and not reviewed['eligible_for_handoff']
    assert reviewed['semantic_acceptance']=='NOT_ESTABLISHED' and reviewed['implementation_version']=='1.2.0-economic-nature-review'
    assert render_explicit_review(report)==render_explicit_review(json.loads(canonical(report)))
    assert sha256(path.read_bytes()).hexdigest()==before
    original={k:v for k,v in x.items() if k!='term_classifications'}
    assert parse_response(p,old,reply(original),NOW)['research_binding']['explicit_response_contract']['original_draft']==original
