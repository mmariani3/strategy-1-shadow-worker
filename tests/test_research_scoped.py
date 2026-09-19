"""Isolated v6 infrastructure cases. No paid calls or strategy observations."""
from copy import deepcopy
import json

import pytest

from evidence_review import canonical, digest, source, validate_draft
from research_citations import Selection
from research_coverage import prepare_coverage_request
from research_scoped import (AnchoredResolver, ScopedDraft, VERSIONS,
                             prepare_scoped_request)
from research_reviewer import parse_response, ReviewBlocked
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_coverage import draft_for as v5_draft, boundary_packet


def draft_for(p):
    d = v5_draft(p)
    d['materiality_coverage'].update(assessment_scope='Isolated materiality research assessment.',
                                   missing_document_reasons=[])
    return d


@pytest.fixture
def scoped_case(fact_case, masters):
    p, _ = fact_case
    return p, prepare_scoped_request(p, masters, 'offline-fixture', 12000, 250000, NOW)


def repeated_packet(p, text=None):
    p = deepcopy(p)
    text = text or ('Repeated title.\n' + 'First isolated context. '*60 + '\n' +
                    'Repeated title.\n' + 'Second isolated context. '*52)
    s = source('retrieved_document', {'text':text,'other':'Repeated title.'}, NOW)
    p['sources'].append(s)
    p['packet_id'] = digest({k:v for k,v in p.items() if k!='packet_id'})
    return p, s


def anchors(p, s, needle):
    return [(k,r) for k,r in AnchoredResolver(p).catalog.items()
            if r['source_id']==s['source_id'] and r['path']==['text'] and needle in r['text']]


def test_repeated_text_keeps_chosen_occurrence_through_final_artifact(scoped_case, masters):
    p, _ = scoped_case; p,s = repeated_packet(p)
    matches = anchors(p,s,'Repeated title.')
    assert len(matches)==2
    k,row = matches[1]
    req = prepare_scoped_request(p,masters,'offline-fixture',12000,250000,NOW)
    d = draft_for(p)
    selection = dict(excerpt_id=k,supporting_text='Repeated title.')
    d['facts'][0]['evidence'] = [selection]
    d['claims'][0].update(evidence_state='OBSERVED_SUPPORT',evidence=[selection])
    d['materiality_coverage']['evidence'] = [selection]
    before = deepcopy(p)
    result = parse_response(p,req,reply(d),NOW)
    cite = result['review_artifact']['review']['claims'][0]['citations'][0]
    assert cite['start'] > s['text'].find('Repeated title.')
    assert row['start'] <= cite['start'] < row['end']
    assert s['text'][cite['start']:cite['end']] == cite['quote']
    assert result['fact_findings'][0]['citations'][0] == cite
    assert result['materiality_evidence_coverage']['citations'][0]['start']==cite['start']
    assert validate_draft(p,result['review_artifact']['review'],NOW)==result['review_artifact']
    assert result['eligible_for_handoff'] is False and p==before
    # The old contract does not retroactively accept this response.
    old_d=deepcopy(d)
    old_d['materiality_coverage'].pop('assessment_scope')
    old_d['materiality_coverage'].pop('missing_document_reasons')
    old_req=prepare_coverage_request(p,masters,'offline-fixture',12000,250000,NOW)
    with pytest.raises(ReviewBlocked,match='SUPPORT_TEXT_MISSING_OR_AMBIGUOUS'):
        parse_response(p,old_req,reply(old_d),NOW)
    assert old_req['request_id']!=req['request_id']


@pytest.mark.parametrize('text,support', [
    ('ISOLATED title. Repeated title. Repeated title. End.', 'Repeated title.'),
    ('ISOLATED overlapping aaaa end.', 'aaa')])
def test_multiple_occurrences_inside_same_anchor_fail(scoped_case,text,support):
    p,_=scoped_case;p,s=repeated_packet(p,text)
    k,_=anchors(p,s,support)[0]
    with pytest.raises(ReviewBlocked,match='ANCHOR_MISSING_OR_AMBIGUOUS'):
        AnchoredResolver(p).resolve([Selection(excerpt_id=k,supporting_text=support)])


def test_longer_exact_context_disambiguates_without_editing_source(scoped_case):
    p,_=scoped_case;p,s=repeated_packet(p,'First label. Second label. End of isolated fixture.')
    k,_=anchors(p,s,'label.')[0];resolver=AnchoredResolver(p)
    with pytest.raises(ReviewBlocked,match='ANCHOR_MISSING_OR_AMBIGUOUS'):
        resolver.resolve([Selection(excerpt_id=k,supporting_text='label.')])
    result=resolver.resolve([Selection(excerpt_id=k,supporting_text='Second label.')])[0]
    assert s['text'][result['start']:result['end']]=='Second label.'


def test_model_cannot_supply_its_own_offsets(scoped_case):
    p,req=scoped_case;d=draft_for(p)
    d['facts'][0]['evidence'][0]['start']=0
    with pytest.raises(ValueError):parse_response(p,req,reply(d),NOW)


@pytest.mark.parametrize('bad', ['wrong_field','wrong_anchor','altered','unknown','empty','duplicate'])
def test_anchor_does_not_rescue_invalid_citation(scoped_case,bad):
    p,_=scoped_case;p,s=repeated_packet(p)
    k,_=anchors(p,s,'First isolated context.')[0]
    support='Repeated title.'
    if bad=='wrong_field':support='"other":"Repeated title."'
    if bad=='wrong_anchor':support='Second isolated context.'
    if bad=='altered':support='Repeated title!'
    if bad=='unknown':k='Eunknown'
    if bad=='empty':support=' '
    selections=[Selection(excerpt_id=k,supporting_text=support)]
    if bad=='duplicate':selections*=2
    with pytest.raises(ReviewBlocked):AnchoredResolver(p).resolve(selections)


def test_boundary_quote_and_duplicate_via_two_anchors(scoped_case):
    p,_=scoped_case;p,s=boundary_packet(p);resolver=AnchoredResolver(p)
    support='On\nSeptember 17, the fixture issuer published a patent announcement.'
    k=next(k for k,r in resolver.catalog.items() if r['source_id']==s['source_id'] and r['text'].startswith('September 17'))
    prior=next(k for k,r in resolver.catalog.items() if r['source_id']==s['source_id'] and r['text'].endswith('On\n'))
    result=resolver.resolve([Selection(excerpt_id=k,supporting_text=support)])[0]
    assert result['start']<resolver.catalog[k]['start']
    with pytest.raises(ReviewBlocked,match='DUPLICATE_SOURCE_SPAN'):
        resolver.resolve([Selection(excerpt_id=a,supporting_text=support) for a in [prior,k]])


def test_exact_unicode_escape_and_repeated_whole_field_fail_closed(scoped_case):
    p,_=scoped_case
    text='Quoted "A", café 中文 and \\slashes.\n'
    p,s=repeated_packet(p,text+'Isolated padding. '*80+text+'Other isolated padding. '*80)
    k,_=anchors(p,s,text)[-1]
    result=AnchoredResolver(p).resolve([Selection(excerpt_id=k,supporting_text=text)])[0]
    assert result['quote']==canonical(text)[1:-1]
    assert s['text'][result['start']:result['end']]==result['quote']
    p,s=repeated_packet(p,'Isolated small field.')
    replacement=source('retrieved_document',{'text':'Isolated small field.','other':'Isolated small field.'},NOW)
    p['sources'][-1]=replacement;p['packet_id']=digest({k:v for k,v in p.items() if k!='packet_id'})
    assert not any(r['source_id']==replacement['source_id'] for r in AnchoredResolver(p).catalog.values())


@pytest.mark.parametrize('state',['OBSERVED_SUPPORT','OBSERVED_FAILURE'])
def test_scoped_sufficiency_passes_structurally_without_clearing_other_criteria(scoped_case,state):
    p,req=scoped_case;d=draft_for(p)
    d['materiality_coverage'].update(status='SUFFICIENT_FOR_RESEARCH',
        evidence=d['facts'][0]['evidence'],assessment_scope='Isolated named analyst-action assessment only.')
    next(c for c in d['claims'] if c['criterion']=='catalyst_materiality_tier').update(
        evidence_state=state,evidence=d['facts'][0]['evidence'])
    r=parse_response(p,req,reply(d),NOW)
    assert r['materiality_evidence_coverage']['missing_document_reasons']==[]
    assert r['materiality_evidence_coverage']['semantic_verification']=='NOT_ESTABLISHED'
    assert r['review_artifact']['review']['claims'][0]['assessment']=='UNRESOLVED'
    assert not r['eligible_for_handoff']


@pytest.mark.parametrize('bad',['blank_scope','missing_scope','unexplained','wrong_document',
    'empty_reason','duplicate_document','duplicate_reason','sufficient_missing','missing_contract'])
def test_coverage_requires_specific_consistent_document_reasons(scoped_case,bad):
    p,req=scoped_case;d=draft_for(p);c=d['materiality_coverage']
    c.update(status='INCOMPLETE',missing_documents=['Exhibit 99.1'],
             missing_document_reasons=[dict(document='Exhibit 99.1',reason='Needed to measure reported revenue; cover does not contain results.')])
    if bad=='blank_scope':c['assessment_scope']=' '
    if bad=='missing_scope':c.pop('assessment_scope')
    if bad=='unexplained':c['missing_document_reasons']=[]
    if bad=='wrong_document':c['missing_document_reasons'][0]['document']='Another document'
    if bad=='empty_reason':c['missing_document_reasons'][0]['reason']=' '
    if bad=='duplicate_document':c['missing_documents']*=2
    if bad=='duplicate_reason':c['missing_document_reasons']*=2
    if bad=='sufficient_missing':c.update(status='SUFFICIENT_FOR_RESEARCH',evidence=d['facts'][0]['evidence'])
    if bad=='missing_contract':d.pop('materiality_coverage')
    with pytest.raises(ValueError):parse_response(p,req,reply(d),NOW)


@pytest.mark.parametrize('state',['OBSERVED_SUPPORT','OBSERVED_FAILURE'])
def test_known_missing_document_still_blocks_materiality(scoped_case,state):
    p,req=scoped_case;d=draft_for(p)
    d['materiality_coverage'].update(status='INCOMPLETE',missing_documents=['Financial terms'],
        missing_document_reasons=[dict(document='Financial terms',reason='Necessary economics are absent.')])
    r=parse_response(p,req,reply(d),NOW)
    assert r['materiality_evidence_coverage']['missing_document_reasons'][0]['document']=='Financial terms'
    next(c for c in d['claims'] if c['criterion']=='catalyst_materiality_tier').update(
        evidence_state=state,evidence=d['facts'][0]['evidence'])
    with pytest.raises(ReviewBlocked,match='MATERIALITY_COVERAGE_NOT_SUFFICIENT'):
        parse_response(p,req,reply(d),NOW)


@pytest.mark.parametrize('bad',['capability','missing_fact','single_source','missing_topic','metadata'])
def test_existing_capability_fact_and_source_gates_survive(scoped_case,bad):
    p,req=scoped_case;d=draft_for(p)
    if bad=='capability':next(c for c in d['claims'] if c['criterion']=='liquidity').update(evidence_state='OBSERVED_SUPPORT',evidence=d['facts'][0]['evidence'])
    if bad=='missing_fact':
        d['facts'][2]['status']='UNRESOLVED'
        d['claims'][0].update(evidence_state='OBSERVED_SUPPORT',evidence=d['facts'][0]['evidence'])
    if bad=='single_source':next(c for c in d['claims'] if c['criterion']=='same_event_verification').update(evidence_state='OBSERVED_SUPPORT',evidence=d['facts'][0]['evidence'])
    if bad=='missing_topic':d['facts'].pop()
    if bad=='metadata':
        k,r=next((k,r) for k,r in AnchoredResolver(p).catalog.items() if r['category']=='PUBLICATION_METADATA')
        d['materiality_coverage']['evidence']=[dict(excerpt_id=k,supporting_text=r['text'])]
    with pytest.raises(ValueError):parse_response(p,req,reply(d),NOW)


def test_schema_lossless_packet_limits_and_version_routing(scoped_case,masters):
    p,req=scoped_case
    from run_research_reviewer import prepare_request
    assert prepare_request is prepare_scoped_request
    view=json.loads(req['body']['input'][-1]['content'].split('\n',1)[1])
    for s in view['packet']['sources']:s['raw']=json.loads(s['text'])
    assert view['packet']==p and view['citation_policy']=='UNIQUE_ANCHORED_SAME_FIELD_OCCURRENCE_V2'
    schema=ScopedDraft.model_json_schema()
    assert schema['additionalProperties'] is False
    assert all(v['additionalProperties'] is False and set(v['required'])==set(v['properties']) for v in schema['$defs'].values())
    size=len(canonical(req['body']).encode('utf-8'))
    assert prepare_request(p,masters,'offline-fixture',12000,size,NOW)==req
    with pytest.raises(ReviewBlocked,match='INPUT_LIMIT'):prepare_request(p,masters,'offline-fixture',12000,size-1,NOW)


def test_replay_and_evidence_tamper_before_dispatch(scoped_case):
    p,req=scoped_case;ledger=AttemptLedger(ledger_path(),1);calls=[]
    class Provider:
        def respond(self,body):calls.append(body);return reply(draft_for(p))
    try:
        bad=deepcopy(req);bad['body']['input'][-1]['content']+='altered'
        bad['request_id']=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=bad['body']))
        with pytest.raises(ReviewBlocked,match='EVIDENCE_MISMATCH'):execute_once(ledger,p,bad,Provider(),lambda:NOW)
        assert not calls and ledger.db.execute('select count(*) from requests').fetchone()[0]==0
        result=execute_once(ledger,p,req,Provider(),lambda:NOW)
        assert execute_once(ledger,p,req,Provider(),lambda:NOW)==result and len(calls)==1
    finally:ledger.close()


@pytest.mark.parametrize('mock_review_route',[False,True])
def test_cli_prepares_v6_without_loading_a_key_or_calling_provider(scoped_case,masters,monkeypatch,capsys,mock_review_route):
    import run_research_reviewer as cli
    p,_=scoped_case;root=ledger_path().parent
    packet_file=root/'packet.json';master_file=root/'masters.json'
    packet_file.write_text(canonical(p),encoding='utf-8')
    master_file.write_text(canonical(masters),encoding='utf-8')
    def forbidden(*args,**kwargs):raise AssertionError('Preparation must not load a key or dispatch')
    monkeypatch.setattr(cli,'OpenAIReviewer',forbidden)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    if mock_review_route:
        # Exercise CLI preparation without relabeling the infrastructure fixture.
        monkeypatch.setattr(cli,'inspect_packet',lambda *args:dict(
            report_id='isolated-mocked-review-route',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(packet_file),'--masters',str(master_file),
        '--model','offline-fixture','--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main()
    printed=json.loads(capsys.readouterr().out)
    if not mock_review_route:
        assert printed['status']=='EXCLUDED_INFRASTRUCTURE' and printed['model_calls']==0
        return
    assert printed['status']=='PREPARED_NOT_SENT' and printed['model_calls']==0
    request=json.loads(__import__('pathlib').Path(printed['request_file']).read_text(encoding='utf-8'))
    assert (request['implementation_version'],request['prompt_version'])==VERSIONS
