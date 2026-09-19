"""v8 offline infrastructure fixtures. No real observations or provider calls."""
from copy import deepcopy
import json

import pytest

from evidence_review import canonical, digest, validate_draft
from research_citations import selectable_catalog
from research_context import (VERSIONS, FRESHNESS_CAPABILITY, context_schema,
    prepare_context_request, FixedResolver, ExcerptRef)
from research_reviewer import parse_response, ReviewBlocked
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_bounded import draft_for as old_draft
from test_research_scoped import repeated_packet, anchors


def draft_for(p):
    d = old_draft(p)
    symbol = p['symbol']
    for item in d['facts'] + d['claims'] + [d['materiality_coverage']]:
        item['subject_symbol'] = symbol
        item['evidence'] = [dict(excerpt_id=e['excerpt_id']) for e in item['evidence']]
    evidence = deepcopy(d['facts'][0]['evidence'])
    d.update(target=dict(symbol=symbol,instrument_type='STOCK',stock_universe='EVIDENCED',
        rationale='Isolated stock-universe research assertion.',evidence=evidence),
        selected_event=dict(subject_symbol=symbol,description='Isolated merger announcement.',relationship='DIRECT',
            target_link='EVIDENCED',link_rationale='Fixture explicitly names the target.',
            evidence=evidence,link_evidence=evidence))
    return d


def claim(d, criterion):
    return next(c for c in d['claims'] if c['criterion']==criterion)


def material(d):
    d['materiality_coverage'].update(status='SUFFICIENT_FOR_RESEARCH',missing_documents=[],
        evidence=deepcopy(d['target']['evidence']))
    claim(d,'catalyst_materiality_tier').update(evidence_state='OBSERVED_SUPPORT',
        evidence=deepcopy(d['target']['evidence']))
    return d


@pytest.fixture
def context_case(fact_case,masters):
    p,_=fact_case
    return p,prepare_context_request(p,masters,'offline-fixture',12000,250000,NOW)


def test_source_locations_binding_trace_and_replay(context_case):
    p,req=context_case; d=material(draft_for(p)); before=deepcopy(p)
    response=reply(d); calls=[]; path=ledger_path()
    class Provider:
        def respond(self,body):calls.append(body);return response
    ledger=AttemptLedger(path,1)
    try:result=execute_once(ledger,p,req,Provider(),lambda:NOW)
    finally:ledger.close()
    ledger=AttemptLedger(path,1)
    try:
        assert execute_once(ledger,p,req,Provider(),lambda:NOW)==result and len(calls)==1
        assert ledger.events(req['request_id'])['RECEIVED']['payload']==response
    finally:ledger.close()
    assert p==before and not result['eligible_for_handoff']
    binding=result['research_binding']; event_id=binding['selected_event_id']
    assert binding['freshness_capability']==FRESHNESS_CAPABILITY
    assert binding['semantic_verification']=='NOT_ESTABLISHED'
    assert all(x['subject_symbol']==p['symbol'] and x['selected_event_id']==event_id for x in binding['claims'])
    assert result['materiality_evidence_coverage']['selected_event_id']==event_id
    assert all(f['selected_event_id']==event_id for f in result['fact_findings'])
    artifact=result['review_artifact']; review=artifact['review']
    assert validate_draft(p,review,NOW)==artifact
    assert (review['implementation_version'],review['prompt_version'])==VERSIONS
    sources={s['source_id']:s['text'] for s in p['sources']}
    for f in result['fact_findings']:
        for c in f['citations']:assert sources[c['source_id']][c['start']:c['end']]==c['quote']
    assert artifact['trace']==p['trace']


@pytest.mark.parametrize('place',['target','claim','coverage','instrument_fact','event_fact','direct_event'])
def test_wrong_company_rejected_despite_real_quotes(context_case,place):
    p,req=context_case;d=material(draft_for(p))
    if place=='target':d['target']['symbol']='OTHER'
    if place=='claim':claim(d,'catalyst_materiality_tier')['subject_symbol']='OTHER'
    if place=='coverage':d['materiality_coverage']['subject_symbol']='OTHER'
    if place=='instrument_fact':d['facts'][0]['subject_symbol']='OTHER'
    if place=='event_fact':d['facts'][1]['subject_symbol']='OTHER'
    if place=='direct_event':d['selected_event']['subject_symbol']='OTHER'
    with pytest.raises(ReviewBlocked,match='MISMATCH'):parse_response(p,req,reply(d),NOW)


@pytest.mark.parametrize('state',['OBSERVED_SUPPORT','OBSERVED_FAILURE'])
@pytest.mark.parametrize('date_reason',['same-day','one day before discovery','Wednesday before Friday publication'])
def test_dates_never_replace_missing_freshness_policy(context_case,state,date_reason):
    p,req=context_case;d=draft_for(p)
    claim(d,'catalyst_freshness').update(evidence_state=state,rationale=date_reason,evidence=d['target']['evidence'])
    with pytest.raises(ReviewBlocked,match='FRESHNESS_POLICY_ADAPTER_UNAVAILABLE'):
        parse_response(p,req,reply(d),NOW)


def test_dates_preserved_when_freshness_unresolved(context_case):
    p,req=context_case;d=draft_for(p)
    d['facts'][2]['finding']='Announcement September 17; agreement August 1; exact clock time unknown.'
    result=parse_response(p,req,reply(d),NOW)
    assert result['fact_findings'][2]['finding']==d['facts'][2]['finding']
    assert result['review_artifact']['review']['claims'][0]['assessment']=='UNRESOLVED'


@pytest.mark.parametrize('instrument',['ETF','WARRANT','RIGHT','OTHER','UNKNOWN'])
def test_nonstock_universe_cannot_be_declared_established(context_case,instrument):
    p,req=context_case;d=draft_for(p);d['target']['instrument_type']=instrument
    with pytest.raises(ReviewBlocked,match='STOCK_UNIVERSE_NOT_ESTABLISHED'):
        parse_response(p,req,reply(d),NOW)


def test_etf_holding_facts_do_not_qualify_target(context_case):
    p,req=context_case;d=draft_for(p)
    d['target'].update(instrument_type='ETF',stock_universe='UNRESOLVED')
    d['selected_event'].update(subject_symbol='HOLDING',relationship='READ_THROUGH',target_link='UNRESOLVED')
    for fact in d['facts'][1:3]:fact['subject_symbol']='HOLDING'
    result=parse_response(p,req,reply(d),NOW)
    assert result['research_binding']['selected_event']['subject_symbol']=='HOLDING'
    assert not result['eligible_for_handoff']
    d=material(d)
    with pytest.raises(ReviewBlocked,match='TARGET_EVENT_BINDING_UNRESOLVED'):
        parse_response(p,req,reply(d),NOW)


@pytest.mark.parametrize('bad',['no_link','no_link_citation','same_subject','no_subject','unrelated','metadata_link','unknown_target'])
def test_readthrough_requires_explicit_target_link(context_case,bad):
    p,req=context_case;d=material(draft_for(p));e=d['selected_event']
    e.update(subject_symbol='PEER',relationship='READ_THROUGH')
    for fact in d['facts'][1:3]:fact['subject_symbol']='PEER'
    if bad=='no_link':e['target_link']='UNRESOLVED'
    if bad=='no_link_citation':e['link_evidence']=[]
    if bad=='same_subject':e['subject_symbol']=p['symbol']
    if bad=='no_subject':e['subject_symbol']=None
    if bad=='unrelated':e['relationship']='UNRELATED'
    if bad=='unknown_target':d['target']['stock_universe']='UNRESOLVED'
    if bad=='metadata_link':
        k=next(k for k,r in selectable_catalog(p).items() if r['category']=='PUBLICATION_METADATA')
        e['link_evidence']=[dict(excerpt_id=k)]
    with pytest.raises(ReviewBlocked):parse_response(p,req,reply(d),NOW)


def test_readthrough_research_path_retains_actual_subject(context_case):
    p,req=context_case;d=material(draft_for(p))
    d['selected_event'].update(subject_symbol='PEER',relationship='READ_THROUGH')
    for fact in d['facts'][1:3]:fact['subject_symbol']='PEER'
    result=parse_response(p,req,reply(d),NOW)
    assert result['research_binding']['target']['symbol']==p['symbol']
    assert result['research_binding']['selected_event']['subject_symbol']=='PEER'
    assert result['research_binding']['semantic_verification']=='NOT_ESTABLISHED'
    assert not result['eligible_for_handoff']  # Structural declarations do not prove economic read-through.


@pytest.mark.parametrize('bad',['unknown_id','padded_id','duplicate','supporting_text','offset','missing_topic','duplicate_criterion','capability','metadata','coverage','blank_reason'])
def test_existing_evidence_gates_survive(context_case,bad):
    p,req=context_case;d=draft_for(p)
    if bad=='unknown_id':d['facts'][0]['evidence']=[dict(excerpt_id='Eforeign')]
    if bad=='padded_id':d['facts'][0]['evidence'][0]['excerpt_id']=' '+d['facts'][0]['evidence'][0]['excerpt_id']+' '
    if bad=='duplicate':d['facts'][0]['evidence']*=2
    if bad=='supporting_text':d['facts'][0]['evidence'][0]['supporting_text']='Fabricated quotation'
    if bad=='offset':d['facts'][0]['evidence'][0]['start']=0
    if bad=='missing_topic':d['facts'].pop()
    if bad=='duplicate_criterion':d['claims'][-1]=deepcopy(d['claims'][0])
    if bad=='capability':claim(d,'liquidity').update(evidence_state='OBSERVED_SUPPORT',evidence=d['target']['evidence'])
    if bad=='metadata':
        k=next(k for k,r in selectable_catalog(p).items() if r['category']=='PUBLICATION_METADATA')
        d['facts'][2]['evidence']=[dict(excerpt_id=k)]
    if bad in ('coverage','blank_reason'):
        material(d);d['materiality_coverage'].update(status='INCOMPLETE',missing_documents=[dict(document='Terms',reason='Required unknown economics.')])
        if bad=='blank_reason':d['materiality_coverage']['missing_documents'][0]['reason']=' '
    with pytest.raises(ValueError):parse_response(p,req,reply(d),NOW)


def test_fixed_excerpts_preserve_unicode_repeated_text_and_adjacent_locations(context_case,masters):
    p,_=context_case;p,s=repeated_packet(p)
    keys=[k for k,r in anchors(p,s,'Repeated title.')]
    assert len(keys)==2
    req=prepare_context_request(p,masters,'offline-fixture',12000,250000,NOW)
    d=draft_for(p);d['facts'][0]['evidence']=[dict(excerpt_id=k) for k in keys]
    result=parse_response(p,req,reply(d),NOW)
    citations=result['fact_findings'][0]['citations']
    assert len(citations)==2 and citations[1]['start']>citations[0]['start']
    for k,c in zip(keys,citations):
        row=selectable_catalog(p)[k]
        assert (c['quote'],c['start'],c['end'])==(row['quote'],row['start'],row['end'])
    unicode_key=next(k for k,r in selectable_catalog(p).items() if '中文' in r['text'])
    resolved=FixedResolver(p).resolve([ExcerptRef(excerpt_id=unicode_key)])
    assert '\\"A\\"' in resolved[0]['quote'] and '中文' in resolved[0]['quote']


def test_changed_event_has_distinct_binding_without_rewriting_prior_artifact(context_case):
    p,req=context_case;d=draft_for(p)
    first=parse_response(p,req,reply(d),NOW);frozen=deepcopy(first)
    d['selected_event']['description']='A separate isolated management event, not the merger.'
    second=parse_response(p,req,reply(d),NOW)
    assert first==frozen
    assert first['research_binding']['selected_event_id']!=second['research_binding']['selected_event_id']
    assert first['review_artifact']['trace']==second['review_artifact']['trace']==p['trace']


def test_no_event_keeps_target_research_unresolved(context_case):
    p,req=context_case;d=draft_for(p)
    d['selected_event'].update(subject_symbol=None,relationship='UNRESOLVED',target_link='UNRESOLVED',evidence=[],link_evidence=[])
    for f in d['facts'][1:3]:f.update(subject_symbol=None,status='UNRESOLVED',evidence=[])
    r=parse_response(p,req,reply(d),NOW)
    assert all(c['assessment']=='UNRESOLVED' for c in r['review_artifact']['review']['claims'])
    assert r['research_binding']['selected_event']['subject_symbol'] is None


def test_same_event_source_gate_not_weakened(context_case):
    p,req=context_case;d=draft_for(p)
    claim(d,'same_event_verification').update(evidence_state='OBSERVED_SUPPORT',evidence=d['target']['evidence'])
    with pytest.raises(ReviewBlocked,match='SAME_EVENT_REQUIRES_DISTINCT_SOURCES'):
        parse_response(p,req,reply(d),NOW)


def test_full_packet_masters_schema_and_input_boundaries(context_case,masters):
    p,req=context_case;before=deepcopy(p);body=req['body'];schema=body['text']['format']['schema']
    assert all(s.get('additionalProperties') is False and set(s['required'])==set(s['properties']) for s in schema['$defs'].values())
    assert schema['$defs']['ExcerptRef']['properties']['excerpt_id']['enum']==sorted(selectable_catalog(p))
    assert set(schema['$defs']['ExcerptRef']['properties'])=={'excerpt_id'}
    assert schema['$defs']['Target']['properties']['symbol']['enum']==[p['symbol']]
    view=json.loads(body['input'][-1]['content'].split('\n',1)[1])['packet']
    for s in view['sources']:s['raw']=json.loads(s['text'])
    assert view==p==before
    manifest=json.loads(body['input'][0]['content'].split('GOVERNING_MASTERS:\n',1)[1].split('\nCRITERION_REFERENCES:',1)[0])
    assert all(manifest[k]['text']==v['text'] for k,v in masters.items())
    assert body['max_output_tokens']==12000 and body['tools']==[] and body['store'] is False
    size=len(canonical(body).encode())
    assert prepare_context_request(p,masters,'offline-fixture',12000,size,NOW)==req
    with pytest.raises(ReviewBlocked,match='INPUT_LIMIT_EXCEEDED_NO_TRUNCATION'):
        prepare_context_request(p,masters,'offline-fixture',12000,size-1,NOW)


@pytest.mark.parametrize('tamper',['target_enum','citation_enum','format','evidence','packet_id'])
def test_request_binding_checked_before_reservation(context_case,tamper):
    p,req=context_case;req=deepcopy(req)
    fmt=req['body']['text']['format']
    if tamper=='target_enum':fmt['schema']['$defs']['Target']['properties']['symbol']['enum']=['OTHER']
    if tamper=='citation_enum':fmt['schema']['$defs']['ExcerptRef']['properties']['excerpt_id']['enum'].append('Eforeign')
    if tamper=='format':fmt['strict']=False
    if tamper=='evidence':req['body']['input'][-1]['content']+='tampered'
    if tamper=='packet_id':req['packet_id']='other'
    req['request_id']=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=req['body']))
    class Forbidden:
        def respond(self,body):raise AssertionError('Network forbidden')
    ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked):execute_once(ledger,p,req,Forbidden(),lambda:NOW)
        assert ledger.db.execute('select count(*) from requests').fetchone()[0]==0
        with pytest.raises(ReviewBlocked):parse_response(p,req,reply(draft_for(p)),NOW)
    finally:ledger.close()


@pytest.mark.parametrize('count,width',[(0,21),(715,21),(1001,5)])
def test_catalog_limit_fails_without_truncation(context_case,monkeypatch,count,width):
    import research_context as module
    p,_=context_case;handles={('E'+str(i).zfill(width-1)):{} for i in range(count)}
    monkeypatch.setattr(module,'selectable_catalog',lambda p:handles)
    with pytest.raises(ReviewBlocked):context_schema(p)
    assert len(handles)==count


def test_incomplete_provider_response_not_repaired_or_retried(context_case):
    p,req=context_case;response=reply(draft_for(p));response['status']='incomplete'
    response['incomplete_details']={'reason':'max_output_tokens'};response['output'][0]['content'][0]['text']='{"claims":'
    calls=[]
    class Provider:
        def respond(self,body):calls.append(body);return response
    ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked,match='RESPONSE_VALIDATION_FAILED'):execute_once(ledger,p,req,Provider(),lambda:NOW)
        with pytest.raises(ReviewBlocked,match='PREVIOUS_ATTEMPT_FAILED_NO_RETRY'):execute_once(ledger,p,req,Provider(),lambda:NOW)
        assert len(calls)==1 and ledger.events(req['request_id'])['RECEIVED']['payload']==response
    finally:ledger.close()


@pytest.mark.parametrize('mock_review_route',[False,True])
def test_explicit_v8_cli_compatibility_no_dispatch(context_case,masters,monkeypatch,capsys,mock_review_route):
    import run_research_reviewer as cli
    monkeypatch.setattr(cli,'prepare_request',prepare_context_request)
    p,_=context_case;root=ledger_path().parent
    pf=root/'packet.json';mf=root/'masters.json'
    pf.write_text(canonical(p),encoding='utf-8');mf.write_text(canonical(masters),encoding='utf-8')
    def forbidden(*args,**kwargs):raise AssertionError('Credential/provider use forbidden')
    monkeypatch.setattr(cli,'OpenAIReviewer',forbidden);monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    if mock_review_route:monkeypatch.setattr(cli,'inspect_packet',lambda *args:dict(report_id='isolated-mock',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(pf),'--masters',str(mf),'--model','offline-fixture',
        '--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main();result=json.loads(capsys.readouterr().out)
    assert result['model_calls']==0 and not result['eligible_for_handoff']
    if mock_review_route:
        req=json.loads(__import__('pathlib').Path(result['request_file']).read_text())
        assert (req['implementation_version'],req['prompt_version'])==VERSIONS
    else:assert result['status']=='EXCLUDED_INFRASTRUCTURE'
