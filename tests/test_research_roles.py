"""Synthetic role consistency regressions; declarations are not source truth."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from evidence_review import canonical,digest
from research_roles import (VERSIONS,INSTRUCTIONS,prepare_role_request,validate_role_request,
    validate_roles,role_checklist,role_report)
from research_reviewer import parse_response,ReviewBlocked
from research_field_review import field_review,record_field_assessment,ledger_inputs
from research_explicit_review import render_explicit_review
from review_attempts import AttemptLedger,execute_once
from test_evidence_review import authorities,snapshot,NOW
from test_research_reviewer import masters,ledger_path
from test_research_facts import fact_case,reply
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_fields import setup_case,assessment
from test_research_explicit_integration import FakeProvider


def role_case(linked_case):
    p,old,x,ref,_,m=setup_case(linked_case)
    conditions=[]
    for i,t in enumerate(x['draft']['economic_inventory']['terms']):
        for j,e in enumerate(t['conditions']['entries']):
            e.update(statement='Completion is subject to the disclosed approval.',time_basis='NOT_TEMPORAL')
            conditions.append(dict(term_index=i,entry_index=j,role='DEPENDENCY',
                prerequisite='Disclosed approval',dependent_outcome='Completion',temporal_scope='ATEMPORAL',
                passages=e['passages'],reason='Synthetic declaration; source meaning remains unverified.'))
    passages=x['draft']['research']['selected_event']['support']['clauses'][0]['passages']
    x['draft']['research']['context_notes']=[dict(kind='CAUSAL_LIMIT',finding='Actual results may differ.',passages=passages)]
    followups=x['draft']['research']['materiality_coverage']['document_followups']
    x['meaning_contract']=dict(conditions=conditions,contexts=[dict(context_index=0,role='CAUTION',passages=passages,
        reason='Generic caution is not an observed adverse result.')],followups=[dict(followup_index=i,
        verification_policy='GOVERNING_MASTERS_UNCHANGED',scope_note='Extra research document does not waive governing verification.') for i,_ in enumerate(followups)])
    r=prepare_role_request(p,m,'offline-fixture',12000,250000,NOW)
    return p,r,x,ref,old,m


def test_full_request_and_original_answer_identity(linked_case):
    p,r,x,ref,old,m=role_case(linked_case)
    assert validate_role_request(p,r)[1]==old
    assert r['body']['input'][1:]==old['body']['input'][1:]
    assert r['body']['input'][0]['content']==old['body']['input'][0]['content']+'\n'+INSTRUCTIONS
    schema=r['body']['text']['format']['schema'];old_schema=old['body']['text']['format']['schema']
    assert all(schema['$defs'][k]==v for k,v in old_schema['$defs'].items())
    assert all(schema['properties'][k]==v for k,v in old_schema['properties'].items())
    assert schema['required']==old_schema['required']+['meaning_contract']
    size=len(canonical(r['body']).encode())
    assert prepare_role_request(p,m,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ReviewBlocked,match='NO_TRUNCATION'):prepare_role_request(p,m,'offline-fixture',12000,size-1,NOW)
    from run_research_reviewer import prepare_request
    from research_semantics import prepare_semantic_request
    assert prepare_request is prepare_semantic_request
    raw=reply(x);text=json.dumps(x,indent=2);raw['output'][0]['content'][0]['text']=text
    result=parse_response(p,r,raw,NOW);binding=result['research_binding'];contract=binding['explicit_response_contract']
    assert contract['original_response_text']==text and contract['original_draft']==x and contract['draft_digest']==digest(x)
    assert contract['field_items']==role_checklist(x,r['request_id']) and not result['eligible_for_handoff']
    assert binding['economic_inventory']['implementation_version']==VERSIONS[0] and result['economic_summary']
    assert result['review_artifact']['review']['prompt_version']==VERSIONS[1]
    # All prior v22 parsing stays intact and no original response is transformed in place.
    projection={k:v for k,v in x.items() if k!='meaning_contract'}
    assert parse_response(p,old,reply(projection),NOW)['research_binding']['explicit_response_contract']['original_draft']==projection


@pytest.mark.parametrize('change',['instructions','schema','source','masters','tools','output_limit'])
def test_request_tampering_before_reservation(linked_case,change):
    p,r,x,ref,old,m=role_case(linked_case)
    if change=='instructions':r['body']['input'][0]['content']+='x'
    if change=='schema':r['body']['text']['format']['schema']['required']=[]
    if change=='source':r['body']['input'][-1]['content']+='x'
    if change=='masters':r['masters_digest']='x'
    if change=='tools':r['body']['tools']=[dict(type='web_search')]
    if change=='output_limit':r['body']['max_output_tokens']=0
    r['request_id']=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=r['body']))
    ledger=AttemptLedger(ledger_path(),1);provider=FakeProvider(reply(x))
    try:
        with pytest.raises(ReviewBlocked,match='ROLE_REQUEST_BINDING_MISMATCH'):execute_once(ledger,p,r,provider,lambda:NOW)
        assert provider.calls==0 and ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()


@pytest.mark.parametrize('role',['CAUSAL_ATTRIBUTION','FORECAST_CLASSIFICATION','GENERIC_CAUTION','UNRESOLVED'])
def test_nonconditions_fail_closed_without_repair(linked_case,role):
    p,r,x,ref,old,m=role_case(linked_case)
    x['meaning_contract']['conditions'][0]['role']=role
    original=deepcopy(x)
    with pytest.raises(ValueError,match='NONDEPENDENCY_RECORDED_AS_CONDITION'):role_report(p,r,canonical(x))
    assert x==original


@pytest.mark.parametrize('basis,scope',[('EVENT_OCCURRENCE','OCCURRED'),('FORECAST_PERIOD','PROSPECTIVE'),('NOT_TEMPORAL','ATEMPORAL')])
def test_genuine_condition_time_bases_and_contradictions(linked_case,basis,scope):
    p,r,x,ref,old,m=role_case(linked_case)
    row=x['meaning_contract']['conditions'][0];entry=x['draft']['economic_inventory']['terms'][row['term_index']]['conditions']['entries'][row['entry_index']]
    row['temporal_scope']=scope;entry['time_basis']=basis
    validate_roles(x)
    entry['time_basis']='CAPTURE'
    with pytest.raises(ValueError,match='CONDITION_TEMPORAL_ROLE_MISMATCH'):validate_roles(x)


@pytest.mark.parametrize('bad',['missing_condition','duplicate_condition','missing_context','duplicate_context','source','bool_index','blank_prerequisite','blank_reason','missing_contract','unknown_followup','waive_verification'])
def test_exact_role_sets_and_evidence_bindings(linked_case,bad):
    _,_,x,_,_,_=role_case(linked_case);c=x['meaning_contract']
    if bad=='missing_condition':c['conditions'].pop()
    if bad=='duplicate_condition':c['conditions'].append(deepcopy(c['conditions'][0]))
    if bad=='missing_context':c['contexts'].pop()
    if bad=='duplicate_context':c['contexts'].append(deepcopy(c['contexts'][0]))
    if bad=='source':c['contexts'][0]['passages']=[99999]
    if bad=='bool_index':c['conditions'][0]['term_index']=True
    if bad=='blank_prerequisite':c['conditions'][0]['prerequisite']=' '
    if bad=='blank_reason':c['contexts'][0]['reason']=' '
    if bad=='missing_contract':x.pop('meaning_contract')
    if bad=='unknown_followup':c['followups'].append(dict(followup_index=999,verification_policy='GOVERNING_MASTERS_UNCHANGED',scope_note='Unknown'))
    if bad=='waive_verification':c['followups'].append(dict(followup_index=0,verification_policy='NOT_REQUIRED',scope_note='Waived'))
    with pytest.raises(ValueError):validate_roles(x)


def test_result_forecast_and_caution_categories_are_distinct(linked_case):
    _,_,x,_,_,_=role_case(linked_case);note=x['draft']['research']['context_notes'][0];role=x['meaning_contract']['contexts'][0]
    note['kind']='EXPECTATIONS';role['role']='REPORTED_RESULT'
    with pytest.raises(ValueError,match='REPORTED_RESULT_REQUIRES_FACT'):validate_roles(x)
    role['role']='FORECAST';validate_roles(x)
    note['kind']='COUNTEREVIDENCE';role['role']='CAUTION'
    with pytest.raises(ValueError,match='CONTEXT_ROLE_MISMATCH'):validate_roles(x)
    role['role']='OBSERVED_COUNTEREVIDENCE';validate_roles(x)
    # Declarations are not a semantic judge: lying consistently still requires review.
    assert 'field_items' not in x


def test_original_rejected_response_retained_without_retry(linked_case):
    p,r,x,ref,old,m=role_case(linked_case);x['meaning_contract']['conditions'][0]['role']='CAUSAL_ATTRIBUTION'
    raw=reply(x);provider=FakeProvider(raw);ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ValueError):execute_once(ledger,p,r,provider,lambda:NOW)
        assert ledger.events(r['request_id'])['RECEIVED']['payload']==raw
        with pytest.raises(ReviewBlocked):execute_once(ledger,p,r,provider,lambda:NOW)
        assert provider.calls==1 and 'COMPLETED' not in ledger.events(r['request_id'])
    finally:ledger.close()


def test_complete_review_ledger_and_assessment_preserve_original(linked_case):
    p,r,x,ref,old,m=role_case(linked_case);raw=reply(x);provider=FakeProvider(raw);path=ledger_path();ledger=AttemptLedger(path,1)
    try:
        result=execute_once(ledger,p,r,provider,lambda:NOW)
        assert execute_once(ledger,p,r,provider,lambda:NOW)==result and provider.calls==1
    finally:ledger.close()
    before=sha256(path.read_bytes()).hexdigest()
    assert ledger_inputs(path,r['request_id'],p)==(r,raw,NOW)
    report=field_review(p,r,raw,NOW,ref)
    assert report['original_draft']==x and report['original_provider_response']==raw
    assert report['original_response_text']==raw['output'][0]['content'][0]['text']
    assert report['contract_report']==result['research_binding']['explicit_response_contract']
    assert report['original_versions']['prompt']==VERSIONS[1]
    assert report['field_items']==role_checklist(x,r['request_id'])
    assert {'CONTEXT_MEANING','ROLE_DECLARATION'} <= {i['kind'] for i in report['field_items']}
    a=assessment(report,'SUPPORTED')
    recorded=record_field_assessment(p,r,raw,NOW,ref,a,NOW)
    assert recorded['status']=='FIELD_REVIEW_RECORDED' and recorded['semantic_acceptance']=='NOT_ESTABLISHED'
    assert not recorded['eligible_for_handoff'] and recorded['implementation_version']=='1.1.0-condition-context-review'
    a['decisions'].pop()
    with pytest.raises(ValueError,match='EXACT_FIELD_REVIEW_SET_REQUIRED'):record_field_assessment(p,r,raw,NOW,ref,a,NOW)
    assert render_explicit_review(report)==render_explicit_review(json.loads(canonical(report)))
    assert sha256(path.read_bytes()).hexdigest()==before
