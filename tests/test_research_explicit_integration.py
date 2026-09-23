"""Offline synthetic infrastructure fixtures; no API credentials or real calls."""
from copy import deepcopy
from hashlib import sha256
from html import escape
import json
import pytest

from evidence_review import canonical, digest
from research_explicit import VERSIONS, prepare_integrated_request, validate_integrated_request
from research_explicit_review import explicit_review, render_explicit_review, export_ledger_review
from research_reviewer import parse_response, ReviewBlocked
from review_attempts import AttemptLedger, execute_once
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_tiers import case
from test_research_explicit_contract import explicit_case


def integrated_case(linked_case):
    p, preview, x, m = explicit_case(linked_case)
    r = prepare_integrated_request(p, m, 'offline-fixture', 12000, 250000, NOW)
    return p, r, x, case(linked_case)[3], preview


class FakeProvider:
    def __init__(self, response): self.response = response; self.calls = 0
    def respond(self, body):
        self.calls += 1
        return deepcopy(self.response)


def test_complete_original_response_attribution_and_idempotent_retry(linked_case):
    p,r,x,ref,preview = integrated_case(linked_case)
    response=reply(x);text=json.dumps(x,indent=3)
    response['output'][0]['content'][0]['text']=text
    provider=FakeProvider(response);path=ledger_path();ledger=AttemptLedger(path,1)
    try:
        first=execute_once(ledger,p,r,provider,lambda:NOW)
        assert execute_once(ledger,p,r,provider,lambda:NOW)==first and provider.calls==1
        assert ledger.events(r['request_id'])['RECEIVED']['payload']==response
        contract=first['research_binding']['explicit_response_contract']
        assert contract['original_response_text']==text and contract['original_draft']==x
        assert contract['trace']==p['trace'] and contract['request_id']==r['request_id']
        assert first['review_artifact']['review']['implementation_version']==VERSIONS[0]
        assert first['review_artifact']['review']['prompt_version']==VERSIONS[1]
        assert first['research_binding']['economic_inventory']['request_id']==r['request_id']
        assert first['research_binding']['extraction_instructions']['prompt_version']==VERSIONS[1]
        assert first['economic_summary'] and not first['eligible_for_handoff']
        assert contract['semantic_acceptance']=='NOT_ESTABLISHED'
        assert validate_integrated_request(p,r)[2]==preview
    finally:ledger.close()
    before=sha256(path.read_bytes()).hexdigest()
    report=export_ledger_review(path,r['request_id'],p,ref)
    assert report['original_provider_response']==response and report['original_draft']==x
    assert sha256(path.read_bytes()).hexdigest()==before


@pytest.mark.parametrize('bad',['missing_rule','missing_term','broken_json','refusal','incomplete','multiple_texts','old_shape'])
def test_invalid_response_preserved_and_not_retried(linked_case,bad):
    p,r,x,_,_=integrated_case(linked_case)
    if bad=='missing_rule':x['rule_applications']=[]
    if bad=='missing_term':x['term_assertions']=[]
    response=reply(x['draft'] if bad=='old_shape' else x)
    if bad=='broken_json':response['output'][0]['content'][0]['text']='{'
    if bad=='refusal':response['output'][0]['content']=[dict(type='refusal',refusal='synthetic')]
    if bad=='incomplete':response['status']='incomplete'
    if bad=='multiple_texts':response['output'][0]['content']*=2
    provider=FakeProvider(response);ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked,match='RESPONSE_VALIDATION_FAILED'):execute_once(ledger,p,r,provider,lambda:NOW)
        events=ledger.events(r['request_id'])
        assert events['RECEIVED']['payload']==response and 'FAILED' in events and 'COMPLETED' not in events
        with pytest.raises(ReviewBlocked,match='PREVIOUS_ATTEMPT_FAILED_NO_RETRY'):execute_once(ledger,p,r,provider,lambda:NOW)
        assert provider.calls==1
    finally:ledger.close()


@pytest.mark.parametrize('bad',['instructions','schema','sources','tools','store','digest','packet','masters'])
def test_tampering_rejected_before_reservation_or_provider(linked_case,bad):
    p,r,x,_,_=integrated_case(linked_case)
    if bad=='instructions':r['body']['input'][0]['content']+='changed'
    if bad=='schema':r['body']['text']['format']['schema']['required']=[]
    if bad=='sources':r['body']['input'][1]['content']+='changed'
    if bad=='tools':r['body']['tools']=[dict(type='web_search')]
    if bad=='store':r['body']['store']=True
    if bad=='packet':r['packet_id']='wrong'
    if bad=='masters':r['masters_digest']='wrong'
    r['request_id']=digest(dict(version=r['implementation_version'],prompt_version=r['prompt_version'],body=r['body']))
    if bad=='digest':r['request_id']='wrong'
    provider=FakeProvider(reply(x));ledger=AttemptLedger(ledger_path(),1)
    try:
        with pytest.raises(ReviewBlocked):execute_once(ledger,p,r,provider,lambda:NOW)
        assert provider.calls==0 and ledger.db.execute('select count(*) from requests').fetchone()[0]==0
    finally:ledger.close()


@pytest.mark.parametrize('state',['reserved','received','provider_unknown'])
def test_interrupted_attempt_recovery_never_redispatches(linked_case,state):
    p,r,x,_,_=integrated_case(linked_case);response=reply(x)
    ledger=AttemptLedger(ledger_path(),1);provider=FakeProvider(response)
    try:
        ledger.claim(r,NOW)
        if state=='received':ledger.record(r['request_id'],'RECEIVED',response,NOW)
        if state=='provider_unknown':ledger.record(r['request_id'],'FAILED',dict(code='PROVIDER_RESULT_UNKNOWN'),NOW)
        if state=='received':assert execute_once(ledger,p,r,provider,lambda:NOW)==parse_response(p,r,response,NOW)
        else:
            with pytest.raises(ReviewBlocked,match='NO_RETRY'):execute_once(ledger,p,r,provider,lambda:NOW)
        assert provider.calls==0
    finally:ledger.close()


def test_competing_connection_cannot_duplicate_dispatch(linked_case):
    p,r,x,_,_=integrated_case(linked_case);path=ledger_path();ledger=AttemptLedger(path,1)
    competitor=AttemptLedger(path,1);other=FakeProvider(reply(x))
    class CompetingProvider(FakeProvider):
        def respond(self,body):
            with pytest.raises(ReviewBlocked,match='AMBIGUOUS_ATTEMPT_NO_RETRY'):
                execute_once(competitor,p,r,other,lambda:NOW)
            return super().respond(body)
    provider=CompetingProvider(reply(x))
    try:
        out=execute_once(ledger,p,r,provider,lambda:NOW)
        assert execute_once(competitor,p,r,other,lambda:NOW)==out
        assert provider.calls==1 and other.calls==0
    finally:ledger.close();competitor.close()


def test_source_report_contains_every_extension_and_full_sources_escaped(linked_case):
    p,r,x,ref,_=integrated_case(linked_case)
    x['rule_applications'][0]['explanation']='<script>unsupported()</script> & explanation'
    x['term_assertions'][0].update(status='UNRESOLVED',statement='',passages=[],reason='Unknown <img src=x onerror=alert(1)>')
    response=reply(x);report=explicit_review(p,r,response,NOW,ref)
    html=render_explicit_review(report)
    assert '<script>' not in html and '<img src=x' not in html
    assert escape(x['rule_applications'][0]['explanation']) in html
    assert render_explicit_review(json.loads(canonical(report)))==html
    for name,kind in [('rule_applications','EXPLICIT_RULE_EXPLANATION'),('term_assertions','EXPLICIT_TERM_ASSERTION')]:
        rows=[i for i in report['items'] if i['kind']==kind]
        assert [i['original_value'] for i in rows]==x[name]
    assert report['captured_sources']==p['sources'] and report['reference']==ref
    assert any(i['kind']=='TIMING' for i in report['items'])
    assert any(i['kind']=='SOURCE_ANCHOR' for i in report['items'])
    assert len({i['item_id'] for i in report['items']})==len(report['items'])
    assert report['status']=='SOURCE_REVIEW_REQUIRED' and not report['eligible_for_handoff']
    report['items']=[]
    with pytest.raises(ValueError,match='DIGEST_MISMATCH'):render_explicit_review(report)


def test_full_input_limit_and_no_change_to_default_or_preview(linked_case):
    from run_research_reviewer import prepare_request
    from research_semantics import prepare_semantic_request
    p,r,x,_,preview=integrated_case(linked_case);m=explicit_case(linked_case)[3]
    assert prepare_request is prepare_semantic_request
    with pytest.raises(ReviewBlocked,match='UNSUPPORTED_REQUEST_VERSION'):parse_response(p,preview,reply(x),NOW)
    size=len(canonical(r['body']).encode())
    assert prepare_integrated_request(p,m,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ReviewBlocked,match='INPUT_LIMIT_EXCEEDED_NO_TRUNCATION'):
        prepare_integrated_request(p,m,'offline-fixture',12000,size-1,NOW)


def test_export_cli_is_read_only_and_repeatable(linked_case,monkeypatch,capsys):
    import research_explicit_review as cli
    p,r,x,ref,_=integrated_case(linked_case);path=ledger_path();root=path.parent
    ledger=AttemptLedger(path,1)
    try:execute_once(ledger,p,r,FakeProvider(reply(x)),lambda:NOW)
    finally:ledger.close()
    for n,v in [('packet',p),('reference',ref)]: (root/(n+'.json')).write_text(canonical(v),encoding='utf-8')
    args=['review','--ledger',str(path),'--request-id',r['request_id'],'--packet',str(root/'packet.json'),
        '--reference',str(root/'reference.json'),'--output',str(root)]
    before=sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr('sys.argv',args);cli.main();a=json.loads(capsys.readouterr().out)
    cli.main();assert json.loads(capsys.readouterr().out)==a
    assert a['api_calls']==0 and sha256(path.read_bytes()).hexdigest()==before
    monkeypatch.setattr('sys.argv',args+['--dispatch'])
    with pytest.raises(SystemExit):cli.main()


def test_transport_exception_is_attributed_and_never_retried(linked_case):
    p,r,x,_,_=integrated_case(linked_case);ledger=AttemptLedger(ledger_path(),1)
    class Unknown(FakeProvider):
        def respond(self,body):
            self.calls+=1
            raise TimeoutError('synthetic timeout after possible remote acceptance')
    provider=Unknown(None)
    try:
        with pytest.raises(ReviewBlocked,match='PROVIDER_RESULT_UNKNOWN_NO_RETRY'):
            execute_once(ledger,p,r,provider,lambda:NOW)
        with pytest.raises(ReviewBlocked,match='PREVIOUS_ATTEMPT_FAILED_NO_RETRY'):
            execute_once(ledger,p,r,provider,lambda:NOW)
        assert provider.calls==1 and 'RECEIVED' not in ledger.events(r['request_id'])
    finally:ledger.close()


@pytest.mark.parametrize('state',['reserved','received','failed','false_completion'])
def test_incomplete_or_mismatched_history_cannot_export_as_success(linked_case,state):
    p,r,x,ref,_=integrated_case(linked_case);path=ledger_path();ledger=AttemptLedger(path,1)
    try:
        ledger.claim(r,NOW)
        if state!='reserved':ledger.record(r['request_id'],'RECEIVED',reply(x),NOW)
        if state=='failed':ledger.record(r['request_id'],'FAILED',dict(code='RESPONSE_VALIDATION_FAILED'),NOW)
        if state=='false_completion':ledger.record(r['request_id'],'COMPLETED',dict(eligible_for_handoff=True),NOW)
    finally:ledger.close()
    before=sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ReviewBlocked,match='COMPLET'):
        export_ledger_review(path,r['request_id'],p,ref)
    assert sha256(path.read_bytes()).hexdigest()==before
