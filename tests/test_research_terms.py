"""Offline infrastructure regressions; source-derived fixtures are not model runs."""
from copy import deepcopy
import json
import pytest
from evidence_review import canonical, digest
from research_terms import (VERSIONS, FACETS, INSTRUCTIONS, prepare_terms_request,
    validate_terms_request, inspect_inventory, inventory_summary, verify_inventory_summary)
from research_reviewer import parse_response, ReviewBlocked
from research_linked import numbered_passages
from research_reference_coverage import audit_reference_coverage
from research_completeness_review import prepare_checklist, record_completeness_review
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_passages import passage_case
from test_research_linked import linked_case, draft_for
from test_research_reference_coverage import fixture


def make_case(linked_case):
    p,old,d,ref,nums=fixture(linked_case,
        'Fiduciary out is subject to expense reimbursement up to $150,000. '
        'Following closing, the company assumes approximately $700,000 of lease obligations '
        'and provides a letter of credit within thirty days. No completed closing is established.')
    m=linked_case[2]
    def facet(text,basis='NOT_TEMPORAL'):
        return dict(status='RECORDED',reason='Source-derived infrastructure fixture, not model evidence.',
            entries=[dict(statement=text,time_basis=basis,passages=nums)])
    term=dict(label='  Conditional acquisition costs\n',event_relation='SELECTED_EVENT',nature='OBLIGATION',
        amounts=facet('Up to $150,000 reimbursement; approximately $700,000 lease obligations.'),
        conditions=facet('Reimbursement only upon fiduciary out; lease backstop follows closing.'),
        timing=facet('Letter of credit within thirty days following closing.','RELATIVE_DEADLINE'),
        qualifications=facet('No completed closing is established.'))
    inv=dict(assessment_scope=d['materiality_coverage']['assessment_scope'],status='RECORDED_UNVERIFIED',
        unresolved=['Source review still required.'],terms=[term])
    r=prepare_terms_request(p,m,'offline-fixture',12000,250000,NOW)
    return p,r,dict(economic_inventory=inv,research=d),ref,m,old


def test_lossless_host_summary_preserves_all_fields_and_original_strings(linked_case):
    p,r,d,ref,m,old=make_case(linked_case);original=deepcopy(d)
    out=parse_response(p,r,reply(d),NOW); summary=out['economic_summary']
    assert summary['rows'][0]['label']=='  Conditional acquisition costs\n'
    for f in FACETS:assert summary['rows'][0][f]==d['economic_inventory']['terms'][0][f]
    verify_inventory_summary(d['economic_inventory'],summary)
    b=out['research_binding']['economic_inventory']
    assert b['trace']==p['trace'] and b['original_draft_digest']==digest(original)
    assert b['request_id']==r['request_id'] and b['summary']==summary
    assert b['semantic_completeness']=='NOT_ESTABLISHED' and not out['eligible_for_handoff']
    for row in b['citations']:
        for c in row['citations']:
            src=next(s for s in p['sources'] if s['source_id']==c['source_id'])
            assert src['text'][c['start']:c['end']]==c['quote']
    assert d==original
    assert out['research_binding']['support_review']['implementation_version']=='1.13.0-automated-research'
    assert out['review_artifact']['review']['prompt_version']==VERSIONS[1]


@pytest.mark.parametrize('change',['amount','condition','date','qualifier','drop_row','unresolved','scope','status','type_identity'])
def test_summary_loss_or_changed_meaning_rejected(linked_case,change):
    _,_,d,_,_,_=make_case(linked_case);inv=d['economic_inventory'];s=inventory_summary(inv)
    facet={'amount':'amounts','condition':'conditions','date':'timing','qualifier':'qualifications'}.get(change)
    if facet:s['rows'][0][facet]['entries'][0]['statement']='Meaning changed or detail omitted.'
    elif change=='drop_row':s['rows']=[]
    elif change=='unresolved':s['unresolved']=[]
    elif change=='scope':s['assessment_scope']='Different scope'
    elif change=='status':s['status']='APPROVED'
    elif change=='type_identity':s['rows'][0]['term_index']=False  # Equal to 0 in Python, not JSON.
    with pytest.raises(ValueError,match='ECONOMIC_SUMMARY_RETENTION_MISMATCH'):verify_inventory_summary(inv,s)


@pytest.mark.parametrize('bad',['instructions','schema','source','authority','tools','store','digest','version','packet'])
def test_request_tampering_never_reserves_or_calls(linked_case,bad):
    p,r,d,_,m,_=make_case(linked_case)
    if bad=='instructions':r['body']['input'][0]['content']=r['body']['input'][0]['content'].replace(INSTRUCTIONS,'')
    if bad=='schema':r['body']['text']['format']['schema']['required']=[]
    if bad=='source':r['body']['input'][1]['content']+='changed'
    if bad=='authority':r['body']['input'][0]['content']=r['body']['input'][0]['content'].replace(canonical(m['strategy']['text']),canonical('Invented authority'))
    if bad=='tools':r['body']['tools']=[dict(type='web_search')]
    if bad=='store':r['body']['store']=True
    if bad=='packet':r['packet_id']='0'*64
    if bad=='version':r['prompt_version']='governed-research-v15'
    r['request_id']=digest(dict(version=r['implementation_version'],prompt_version=r['prompt_version'],body=r['body']))
    if bad=='digest':r['request_id']='0'*64
    class Forbidden:
        def respond(self,body):raise AssertionError('Provider forbidden')
    ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ValueError):execute_once(ledger,p,r,Forbidden(),lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()


@pytest.mark.parametrize('bad',['empty','false_state','unknown','duplicate','bool','metadata','scope','empty_reason','extra_approval','duplicate_term'])
def test_inventory_contract_rejects_invalid_or_unbound_terms(linked_case,bad):
    p,r,d,_,_,_=make_case(linked_case);inv=d['economic_inventory'];term=inv['terms'][0]
    entry=term['amounts']['entries'][0]
    if bad=='empty':term['amounts']['entries']=[]
    if bad=='false_state':term['amounts']['status']='NOT_APPLICABLE'
    if bad=='unknown':entry['passages']=[999999]
    if bad=='duplicate':entry['passages']*=2
    if bad=='bool':entry['passages']=[True]
    if bad=='metadata':entry['passages']=[next(n for n,v in numbered_passages(p).items() if v['category']=='PUBLICATION_METADATA')]
    if bad=='scope':inv['assessment_scope']='Different economic scope'
    if bad=='empty_reason':inv['unresolved']=[' ']
    if bad=='extra_approval':inv['approved']=True
    if bad=='duplicate_term':inv['terms'].append(deepcopy(term))
    with pytest.raises(ValueError):parse_response(p,r,reply(d),NOW)


def test_unknown_inventory_is_explicit_not_no_costs_and_research_gates_remain(linked_case):
    p,r,d,_,_,_=make_case(linked_case)
    d['economic_inventory'].update(status='UNRESOLVED',terms=[],unresolved=['Cannot establish terms from captured evidence.'])
    out=parse_response(p,r,reply(d),NOW)
    assert out['economic_summary']['status']=='UNRESOLVED' and not out['eligible_for_handoff']
    d['economic_inventory']['unresolved']=[]
    with pytest.raises(ValueError,match='INVENTORY_UNRESOLVED_REASON_REQUIRED'):parse_response(p,r,reply(d),NOW)
    p,r,d,_,_,_=make_case(linked_case)
    d['research']['claims'][0]['evidence_state']='OBSERVED_SUPPORT'
    with pytest.raises(ValueError):parse_response(p,r,reply(d),NOW)


def test_false_inventory_and_omitted_terms_cannot_establish_semantics(linked_case):
    p,r,d,ref,_,_=make_case(linked_case)
    d['economic_inventory']['terms'][0]['amounts']['entries'][0]['statement']='No fee is owed. Deliberately false.'
    out=parse_response(p,r,reply(d),NOW)
    assert out['economic_summary']['semantic_completeness']=='NOT_ESTABLISHED'
    assert not out['eligible_for_handoff']
    audit=audit_reference_coverage(p,r,d,ref)
    assert audit['implementation_version']=='1.2.0-reference-location-audit'
    assert audit['rows'][0]['location_status']=='FULLY_SELECTED'
    assessment=prepare_checklist(p,r,d,ref)
    assert assessment['anchors'][0]['draft_evidence'][0]['path'][0]=='research'
    assessment.update(assessor_id='Synthetic test author',assessor_kind='AI_IMPLEMENTATION_AUTHOR',reviewed_at=NOW)
    assessment['anchors'][0].update(relevance='REQUIRED_FOR_SCOPE',finding='MEANING_ERROR',rationale='False prose with valid source locations.')
    review=record_completeness_review(p,r,d,ref,assessment,NOW)
    assert review['status']=='REVISIONS_REQUIRED' and not review['eligible_for_handoff']


def test_full_source_limits_frozen_legacy_and_durable_replay(linked_case):
    p,r,d,_,m,old=make_case(linked_case)
    assert r['body']['input'][1]==old['body']['input'][1]
    assert r['body']['model']==old['body']['model'] and r['body']['max_output_tokens']==12000
    size=len(canonical(r['body']).encode())
    with pytest.raises(ValueError,match='INPUT_LIMIT_EXCEEDED_NO_TRUNCATION'):
        prepare_terms_request(p,m,'offline-fixture',12000,size-1,NOW)
    assert prepare_terms_request(p,m,'offline-fixture',12000,size,NOW)==r
    before=parse_response(p,old,reply(d['research']),NOW);calls=[];response=reply(d);original=deepcopy(response)
    class Provider:
        def respond(self,body):calls.append(body);return response
    path=ledger_path();ledger=AttemptLedger(path,1)
    try:out=execute_once(ledger,p,r,Provider(),lambda:NOW)
    finally:ledger.close()
    ledger=AttemptLedger(path,1)
    try:assert execute_once(ledger,p,r,Provider(),lambda:NOW)==out
    finally:ledger.close()
    assert len(calls)==1 and response==original
    assert parse_response(p,old,reply(d['research']),NOW)==before
    assert 'economic_summary' not in before


def test_cli_default_prepares_new_contract_without_provider(linked_case,monkeypatch,capsys):
    import run_research_reviewer as cli
    # Historical v16 CLI behavior remains pinned as the default evolves.
    monkeypatch.setattr(cli,'prepare_request',prepare_terms_request)
    p,_,_,_,m,_=make_case(linked_case);root=ledger_path().parent
    for name,v in [('p',p),('m',m)]: (root/(name+'.json')).write_text(canonical(v),encoding='utf-8')
    def forbidden(*a,**k):raise AssertionError('No credential or provider access')
    monkeypatch.setattr(cli,'OpenAIReviewer',forbidden)
    monkeypatch.setattr(cli,'inspect_packet',lambda *a:dict(report_id='fixture',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(root/'p.json'),'--masters',str(root/'m.json'),
        '--model','offline-fixture','--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main();out=json.loads(capsys.readouterr().out)
    assert out['model_calls']==0 and not out['eligible_for_handoff']
    from pathlib import Path
    assert json.loads(Path(out['request_file']).read_text())['prompt_version']==VERSIONS[1]
