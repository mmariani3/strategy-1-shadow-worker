"""Synthetic offline field regressions; no paid calls or strategy observations."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from evidence_review import canonical,digest
from research_fields import (VERSIONS,INSTRUCTIONS,prepare_field_request,
    validate_field_request,field_checklist)
from research_field_review import field_review,record_field_assessment,ledger_inputs
from research_explicit_review import render_explicit_review
from research_reviewer import parse_response,ReviewBlocked
from review_attempts import AttemptLedger,execute_once
from test_evidence_review import authorities,snapshot,NOW
from test_research_reviewer import masters,ledger_path
from test_research_facts import fact_case,reply
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_explicit_contract import explicit_case
from test_research_explicit_integration import integrated_case,FakeProvider


def setup_case(linked_case):
    p,old,x,ref,preview=integrated_case(linked_case)
    x['draft']['research']['materiality_coverage']['support']['clauses']=deepcopy(
        x['draft']['research']['selected_event']['support']['clauses'])
    m=explicit_case(linked_case)[3]
    r=prepare_field_request(p,m,'offline-fixture',12000,250000,NOW)
    return p,r,x,ref,old,m


def assessment(report,finding='UNRESOLVED'):
    from research_facts import SUBSTANTIVE
    source=next(s['number'] for s in report['source_catalog'] if s['category'] in SUBSTANTIVE)
    return dict(report_id=report['report_id'],assessor_id='offline-test-assessor',
        assessor_kind='AI_IMPLEMENTATION_AUTHOR',reviewed_at=NOW,
        limitations=['Synthetic fixture, not source truth or independent review.'],
        decisions=[dict(item_id=i['item_id'],value_digest=i['value_digest'],finding=finding,
            rationale='Fixture judgment; substantive source review remains an external responsibility.',
            source_numbers=[source]) for i in report['field_items']])


def test_versioned_full_input_preservation_exact_limit_and_historical_replay(linked_case):
    p,r,x,ref,old,m=setup_case(linked_case)
    before=parse_response(p,old,reply(x),NOW)
    assert validate_field_request(p,r)[1]==old
    assert r['body']['text']==old['body']['text'] and r['body']['input'][1:]==old['body']['input'][1:]
    assert r['body']['input'][0]['content']==old['body']['input'][0]['content']+'\n'+INSTRUCTIONS
    assert r['body']['tools']==[] and r['body']['store'] is False
    size=len(canonical(r['body']).encode())
    assert prepare_field_request(p,m,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ReviewBlocked,match='NO_TRUNCATION'):prepare_field_request(p,m,'offline-fixture',12000,size-1,NOW)
    from run_research_reviewer import prepare_request
    from research_semantics import prepare_semantic_request
    assert prepare_request is prepare_semantic_request
    assert parse_response(p,old,reply(x),NOW)==before


def test_v22_full_attribution_and_ledger_retry(linked_case):
    p,r,x,ref,old,m=setup_case(linked_case);raw=reply(x);text=json.dumps(x,indent=2)
    raw['output'][0]['content'][0]['text']=text
    provider=FakeProvider(raw);path=ledger_path();ledger=AttemptLedger(path,1)
    try:
        out=execute_once(ledger,p,r,provider,lambda:NOW)
        assert execute_once(ledger,p,r,provider,lambda:NOW)==out and provider.calls==1
    finally:ledger.close()
    assert out['review_artifact']['review']['prompt_version']==VERSIONS[1]
    binding=out['research_binding'];contract=binding['explicit_response_contract']
    assert contract['original_response_text']==text and contract['original_draft']==x
    assert contract['request_id']==r['request_id'] and contract['field_items']==field_checklist(x,r['request_id'])
    assert binding['economic_inventory']['implementation_version']==VERSIONS[0]
    assert binding['field_review_status']=='SOURCE_REVIEW_REQUIRED' and not out['eligible_for_handoff']
    assert out['economic_summary']
    before=sha256(path.read_bytes()).hexdigest()
    assert ledger_inputs(path,r['request_id'],p)==(r,raw,NOW)
    report=field_review(p,r,raw,NOW,ref)
    assert report['request_id']==r['request_id'] and report['original_versions']['prompt']==VERSIONS[1]
    assert report['contract_report']==contract and report['original_provider_response']==raw
    assert sha256(path.read_bytes()).hexdigest()==before


@pytest.mark.parametrize('where',['instructions','schema','source','tools','masters'])
def test_tampering_fails_before_dispatch(linked_case,where):
    p,r,x,ref,old,m=setup_case(linked_case)
    if where=='instructions':r['body']['input'][0]['content']+='changed'
    if where=='schema':r['body']['text']['format']['schema']['required']=[]
    if where=='source':r['body']['input'][1]['content']+='changed'
    if where=='tools':r['body']['tools']=[dict(type='web_search')]
    if where=='masters':r['masters_digest']='wrong'
    r['request_id']=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=r['body']))
    provider=FakeProvider(reply(x));ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked,match='FIELD_REQUEST_BINDING_MISMATCH'):execute_once(ledger,p,r,provider,lambda:NOW)
        assert provider.calls==0 and ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()


def test_semantic_counterexamples_are_retained_reviewed_and_never_auto_approved(linked_case):
    p,r,x,ref,old,m=setup_case(linked_case)
    # Representative semantic mistakes from the preserved ADMA review. These
    # intentionally valid strings cannot be adjudicated by schema or keywords.
    term=x['draft']['economic_inventory']['terms'][0]
    term['conditions']['entries'][0]['statement']='Future benefits are forward-looking and actual results may differ.'
    clause=x['draft']['research']['materiality_coverage']['support']['clauses'][0]
    clause.update(statement='Approval was announced; benefits are expected next year.',time_basis='EVENT_OCCURRENCE')
    term['amounts']['reason']='No denominator is given despite the stated same-input comparison.'
    original=deepcopy(x);raw=reply(x)
    report=field_review(p,r,raw,NOW,ref);a=assessment(report,'SUPPORTED')
    paths=[['draft','economic_inventory','terms',0,'conditions'],
        ['draft','research','materiality_coverage','support','clauses',0],
        ['draft','economic_inventory','terms',0,'amounts']]
    for item,decision in zip(report['field_items'],a['decisions']):
        if item['path'] in paths:decision.update(finding='REVISION_REQUIRED',rationale='Source reviewer flags facet meaning, mixed time basis or imprecise comparison basis.')
    result=record_field_assessment(p,r,raw,NOW,ref,a,NOW)
    assert result['status']=='REVISIONS_REQUIRED' and len(result['revision_item_ids'])>=3
    assert result['semantic_acceptance']=='NOT_ESTABLISHED' and not result['eligible_for_handoff']
    assert result['original_report']['original_draft']==x==original
    assert result['original_admission']=='NOT_CHANGED'
    invalid=deepcopy(x)
    invalid['draft']['research']['materiality_coverage']['support']['clauses'][0]['time_basis']='FORECAST_PERIOD'
    with pytest.raises(ValueError):parse_response(p,r,reply(invalid),NOW)
    # Corrected examples are separate synthetic drafts, never patched history.
    revised=deepcopy(x);term=revised['draft']['economic_inventory']['terms'][0]
    term['conditions'].update(status='UNRESOLVED',entries=[],reason='No term-specific conditions are disclosed in the supplied source.')
    term['amounts']['reason']='Comparison basis is disclosed; absolute baseline quantities are unavailable.'
    clauses=revised['draft']['research']['materiality_coverage']['support']['clauses']
    clauses[0]['statement']='Approval was announced.'
    term['nature']='FORECAST'
    term['timing'].update(status='RECORDED',reason='Future benefits retain their forecast period.',
        entries=[dict(statement='Benefits are expected next year.',time_basis='FORECAST_PERIOD',passages=clauses[0]['passages'])])
    new_report=field_review(p,r,reply(revised),NOW,ref)
    assert new_report['report_id']!=report['report_id']
    assert any(i['original_value'].get('time_basis')=='FORECAST_PERIOD' for i in new_report['field_items'])
    assert new_report['original_draft']['draft']['economic_inventory']['terms'][0]['timing']['entries'][0]['statement']=='Benefits are expected next year.'
    with pytest.raises(ValueError,match='FIELD_REPORT_MISMATCH'):record_field_assessment(p,r,reply(revised),NOW,ref,a,NOW)


@pytest.mark.parametrize('bad',['missing','duplicate','digest','source','metadata','bool_source','blank','time','assessor','report'])
def test_assessment_binding_and_complete_coverage_fail_closed(linked_case,bad):
    p,r,x,ref,old,m=setup_case(linked_case);raw=reply(x);report=field_review(p,r,raw,NOW,ref)
    a=assessment(report)
    if bad=='missing':a['decisions'].pop()
    if bad=='duplicate':a['decisions'].append(deepcopy(a['decisions'][0]))
    if bad=='digest':a['decisions'][0]['value_digest']='0'*64
    if bad=='source':a['decisions'][0]['source_numbers']=[99999]
    if bad=='metadata':a['decisions'][0]['source_numbers']=[next(s['number'] for s in report['source_catalog'] if s['category']=='PUBLICATION_METADATA')]
    if bad=='bool_source':a['decisions'][0]['source_numbers']=[True]
    if bad=='blank':a['decisions'][0]['rationale']=' '
    if bad=='time':a['reviewed_at']='2001-01-01T00:00:00Z'
    if bad=='assessor':a['assessor_id']='UNASSIGNED'
    if bad=='report':a['report_id']='wrong'
    with pytest.raises(ValueError):record_field_assessment(p,r,raw,NOW,ref,a,NOW)


@pytest.mark.parametrize('version',['v21','v22'])
def test_exhaustive_fields_escaping_and_unresolved_never_become_approval(linked_case,version):
    p,r,x,ref,old,m=setup_case(linked_case)
    if version=='v21':r=old
    x['draft']['economic_inventory']['terms'][0]['conditions']['reason']='<script>bad()</script>'
    raw=reply(x);report=field_review(p,r,raw,NOW,ref)
    fields=report['field_items'];terms=x['draft']['economic_inventory']['terms']
    assert len([i for i in fields if i['kind']=='CONDITION_FACET'])==len(terms)
    assert len([i for i in fields if i['kind']=='FACET_REASON'])==4*len(terms)
    paths=[i['path'] for i in fields if i['kind']=='TEMPORAL_CLAUSE']
    assert ['draft','research','materiality_coverage','support','clauses',0] in paths
    assert len({i['item_id'] for i in report['items']})==len(report['items'])
    html=render_explicit_review(report)
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert render_explicit_review(json.loads(canonical(report)))==html
    assert report['captured_sources']==p['sources']
    for finding,status in [('UNRESOLVED','SOURCE_REVIEW_REQUIRED'),('SUPPORTED','FIELD_REVIEW_RECORDED')]:
        recorded=record_field_assessment(p,r,raw,NOW,ref,assessment(report,finding),NOW)
        assert recorded['status']==status and recorded['semantic_acceptance']=='NOT_ESTABLISHED'
        assert not recorded['eligible_for_handoff']


def test_failed_response_and_unknown_attempt_stay_failed_no_retry(linked_case):
    p,r,x,ref,old,m=setup_case(linked_case);x['term_assertions']=[]
    path=ledger_path();ledger=AttemptLedger(path,1);provider=FakeProvider(reply(x))
    try:
        with pytest.raises(ReviewBlocked):execute_once(ledger,p,r,provider,lambda:NOW)
        with pytest.raises(ReviewBlocked,match='NO_RETRY'):execute_once(ledger,p,r,provider,lambda:NOW)
        assert provider.calls==1 and 'RECEIVED' in ledger.events(r['request_id'])
    finally:ledger.close()
    with pytest.raises(ReviewBlocked,match='COMPLETED_ORIGINAL'):ledger_inputs(path,r['request_id'],p)


def test_offline_cli_export_and_assessment_are_read_only(linked_case,monkeypatch,capsys):
    import research_field_review as cli
    p,r,x,ref,old,m=setup_case(linked_case);path=ledger_path();root=path.parent
    raw=reply(x);ledger=AttemptLedger(path,1)
    try:execute_once(ledger,p,r,FakeProvider(raw),lambda:NOW)
    finally:ledger.close()
    report=field_review(p,r,raw,NOW,ref);a=assessment(report)
    for name,value in [('packet',p),('reference',ref),('assessment',a)]:
        (root/(name+'.json')).write_text(canonical(value),encoding='utf-8')
    args=['field-review','--ledger',str(path),'--packet',str(root/'packet.json'),
        '--reference',str(root/'reference.json'),'--request-id',r['request_id'],
        '--output',str(root/'reports'),'--assessment',str(root/'assessment.json')]
    monkeypatch.setattr('sys.argv',args)
    monkeypatch.setattr('review_attempts.utc_now',lambda:NOW)
    before=sha256(path.read_bytes()).hexdigest()
    cli.main();first=json.loads(capsys.readouterr().out)
    cli.main();assert json.loads(capsys.readouterr().out)==first
    assert first['status']=='SOURCE_REVIEW_REQUIRED' and first['api_calls']==0
    assert sha256(path.read_bytes()).hexdigest()==before
    monkeypatch.setattr('sys.argv',args+['--dispatch'])
    with pytest.raises(SystemExit):cli.main()
