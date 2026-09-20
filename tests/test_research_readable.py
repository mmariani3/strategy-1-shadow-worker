"""Readable/encoded representation regressions. Infrastructure fixtures only."""
from copy import deepcopy
import json
import pytest
from evidence_review import canonical,digest,source
from research_citations import selectable_catalog
from research_readable import VERSIONS,prepare_readable_request
from research_support import prepare_support_request
from research_reviewer import parse_response,ReviewBlocked
from review_attempts import AttemptLedger,execute_once
from test_evidence_review import authorities,snapshot,NOW
from test_research_reviewer import masters,ledger_path
from test_research_facts import fact_case,reply
from test_research_support import draft_for as encoded_draft


def draft_for(p):
    d=encoded_draft(p); catalog=selectable_catalog(p)
    for s in d['support']:
        for c in s['clauses']:
            for q in c['quotes']:q['quote']=catalog[q['excerpt_id']]['text']
    return d


@pytest.fixture
def readable_case(fact_case,masters):
    p,_=fact_case
    return p,prepare_readable_request(p,masters,'offline-fixture',12000,250000,NOW)


@pytest.mark.parametrize('quote',['First line.\nSecond line.', 'First\r\nSecond', 'Quoted "A" and \\literal\\path',
    'Unicode café 中文 curly “quotes”.', 'A literal \\n is not a newline.', '  Preserve surrounding spaces.  '])
def test_readable_quotes_map_exactly_without_normalization(fact_case,masters,quote):
    p,_=fact_case;p=deepcopy(p)
    src=source('retrieved_document',{'text':quote+' Trailing context.'},NOW)
    p['sources'].append(src);p['packet_id']=digest({k:v for k,v in p.items() if k!='packet_id'})
    r=prepare_readable_request(p,masters,'offline-fixture',12000,250000,NOW);d=draft_for(p)
    handle=next(k for k,v in selectable_catalog(p).items() if v['source_id']==src['source_id'] and v['path']==['text'])
    d['context_notes']=[dict(kind='PROVENANCE',finding='Synthetic quoted provenance example.',quotes=[dict(excerpt_id=handle,quote=quote)])]
    out=parse_response(p,r,reply(d),NOW);review=out['research_binding']['support_review'];note=review['context_notes'][0]
    assert note['quotes'][0]['quote']==quote and note['citations'][0]['readable_quote']==quote
    cite=note['citations'][0];assert src['text'][cite['start']:cite['end']]==canonical(quote)[1:-1]==cite['quote']
    assert review['quote_contract']=='READABLE_EXACT_QUOTE_V1' and review['implementation_version']==VERSIONS[0]
    assert not out['eligible_for_handoff'] and review['semantic_verification']=='NOT_ESTABLISHED'


@pytest.mark.parametrize('bad',['double_encoded','changed_space','wrong_anchor','blank','duplicate','invented'])
def test_no_repairs_or_fuzzy_matching(readable_case,bad):
    p,r=readable_case;d=draft_for(p);q=d['support'][0]['clauses'][0]['quotes'][0]
    if bad=='double_encoded':q['quote']=canonical(q['quote'])[1:-1]
    if bad=='changed_space':q['quote']=q['quote'].replace(' ', '  ',1)
    if bad=='wrong_anchor':q['excerpt_id']=next(k for k,v in selectable_catalog(p).items() if v['category']=='PUBLICATION_METADATA')
    if bad=='blank':q['quote']=' '
    if bad=='duplicate':d['support'][0]['clauses'][0]['quotes']*=2
    if bad=='invented':q['quote']='Unreported prospective confirmation.'
    with pytest.raises(ValueError):parse_response(p,r,reply(d),NOW)


def test_prompt_uses_visible_readable_field_and_full_metadata(readable_case,masters):
    p,r=readable_case;prompt=r['body']['input'][0]['content']
    assert "excerpt's quote string" not in prompt
    assert 'selectable_excerpts[excerpt_id].text' in prompt
    view=json.loads(r['body']['input'][-1]['content'].split('\n',1)[1])
    assert all('quote' not in row and 'text' in row for row in view['selectable_excerpts'].values())
    for s in view['packet']['sources']:s['raw']=json.loads(s['text'])
    assert view['packet']==p
    size=len(canonical(r['body']).encode())
    assert prepare_readable_request(p,masters,'offline-fixture',12000,size,NOW)==r
    with pytest.raises(ReviewBlocked,match='INPUT_LIMIT_EXCEEDED'):
        prepare_readable_request(p,masters,'offline-fixture',12000,size-1,NOW)


def test_ambiguous_within_excerpt_remains_blocked(fact_case,masters):
    p,_=fact_case;p=deepcopy(p)
    src=source('retrieved_document',{'text':'Repeated. Other context. Repeated.'},NOW)
    p['sources'].append(src);p['packet_id']=digest({k:v for k,v in p.items() if k!='packet_id'})
    d=draft_for(p);handle=next(k for k,v in selectable_catalog(p).items() if v['source_id']==src['source_id'])
    d['context_notes']=[dict(kind='OTHER_EVENT',finding='Ambiguous quotation.',quotes=[dict(excerpt_id=handle,quote='Repeated.')])]
    r=prepare_readable_request(p,masters,'offline-fixture',12000,250000,NOW)
    with pytest.raises(ReviewBlocked,match='READABLE_QUOTE_MISSING_OR_AMBIGUOUS'):parse_response(p,r,reply(d),NOW)


def test_v11_original_failure_and_v12_durable_result_are_distinct(readable_case,masters):
    p,r=readable_case;d=draft_for(p)
    old=prepare_support_request(p,masters,'offline-fixture',12000,250000,NOW)
    with pytest.raises(ReviewBlocked,match='CLAUSE_QUOTE_MISSING_OR_AMBIGUOUS'):parse_response(p,old,reply(d),NOW)
    calls=[]
    class Provider:
        def respond(self,body):calls.append(body);return reply(d)
    path=ledger_path();ledger=AttemptLedger(path,1)
    try:out=execute_once(ledger,p,r,Provider(),lambda:NOW)
    finally:ledger.close()
    ledger=AttemptLedger(path,1)
    try:assert execute_once(ledger,p,r,Provider(),lambda:NOW)==out and len(calls)==1
    finally:ledger.close()
    with pytest.raises(ReviewBlocked,match='CLAUSE_QUOTE_MISSING_OR_AMBIGUOUS'):parse_response(p,old,reply(d),NOW)
    assert out['review_artifact']['review']['implementation_version']==VERSIONS[0]


def test_default_cli_prepares_without_provider(readable_case,masters,monkeypatch,capsys):
    import run_research_reviewer as cli
    assert cli.prepare_request is prepare_readable_request
    p,_=readable_case;root=ledger_path().parent
    (root/'p.json').write_text(canonical(p),encoding='utf-8');(root/'m.json').write_text(canonical(masters),encoding='utf-8')
    def forbidden(*a,**k):raise AssertionError('No credentials/provider')
    monkeypatch.setattr(cli,'OpenAIReviewer',forbidden)
    monkeypatch.setattr(cli,'inspect_packet',lambda *a:dict(report_id='isolated-infrastructure',route='REVIEW_REQUIRED'))
    monkeypatch.setattr('sys.argv',['review','--packet',str(root/'p.json'),'--masters',str(root/'m.json'),'--model','offline-fixture',
        '--max-output-tokens','12000','--max-input-bytes','250000','--output',str(root)])
    cli.main();assert json.loads(capsys.readouterr().out)['model_calls']==0
