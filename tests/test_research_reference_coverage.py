"""Location-only regression fixtures, excluded from strategy evidence."""
from copy import deepcopy
import json
import pytest
from evidence_review import canonical, digest, source
from research_linked import prepare_linked_request, numbered_passages
from research_reference_coverage import audit_reference_coverage, string_location
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case
from test_research_passages import passage_case
from test_research_linked import linked_case, draft_for


def fixture(linked_case, text='Fee $7.5M; Not contingent on funding.'):
    p, _, m = deepcopy(linked_case)
    src = source('retrieved_document', {'text':text}, NOW); p['sources'].append(src)
    p['packet_id'] = digest({k:v for k,v in p.items() if k != 'packet_id'})
    r = prepare_linked_request(p,m,'offline-fixture',12000,250000,NOW)
    d = draft_for(p,m)
    reference = dict(assessor='SYNTHETIC_FIXTURE_AUTHOR',at=NOW,independent=False,cases=[dict(packet_id=p['packet_id'],symbol=p['symbol'],expectations=[dict(
        id='FEE',expectation='Retain fee and conditionality for this fixture.',source_id=src['source_id'],raw_path=['text'],start=0,end=len(text),quote=text)])])
    nums = [n for n,row in numbered_passages(p).items() if row['source_id']==src['source_id']]
    return p,r,d,reference,nums


def test_uncited_reference_is_flag_not_admission_change(linked_case):
    p,r,d,ref,nums=fixture(linked_case); before=deepcopy((p,r,d,ref))
    out=audit_reference_coverage(p,r,d,ref); row=out['rows'][0]
    assert row['location_status']=='NOT_SELECTED' and row['catalog_status']=='FULLY_SELECTABLE'
    assert out['original_admission']=='NOT_EVALUATED_OR_CHANGED'
    assert out['semantic_acceptance']=='NOT_ESTABLISHED' and not out['eligible_for_handoff']
    assert (p,r,d,ref)==before and json.loads(canonical(out))==out
    assert audit_reference_coverage(p,r,d,ref)==out


def test_fully_cited_false_statement_does_not_pass_semantic_review(linked_case):
    p,r,d,ref,nums=fixture(linked_case)
    original='  No fee exists. Deliberately false prose.\n'
    d['context_notes']=[dict(kind='OTHER_EVENT',finding=original,passages=nums)]
    out=audit_reference_coverage(p,r,d,ref)
    assert out['rows'][0]['location_status']=='FULLY_SELECTED'
    assert out['rows'][0]['semantic_coverage']=='NOT_ESTABLISHED' and not out['eligible_for_handoff']
    assert out['rows'][0]['selections'][0]['model_statement']==original
    assert out['reference_scope']=='SUPPLIED_ANCHORS_ONLY_NOT_COMPLETE_SOURCE_INVENTORY'


def test_partial_and_duplicate_selections_do_not_inflate_coverage(linked_case):
    p,r,d,ref,nums=fixture(linked_case)
    d['context_notes']=[dict(kind='CONDITIONALITY',finding='Only first part cited.',passages=[nums[0],nums[0],999999])]
    out=audit_reference_coverage(p,r,d,ref);row=out['rows'][0]
    assert row['location_status']=='PARTIALLY_SELECTED'
    assert row['selected_encoded_characters'] < row['anchor_encoded_characters']
    assert [x['reason'] for x in out['invalid_selections']]==['DUPLICATE','UNKNOWN']


@pytest.mark.parametrize('value,path', [({'z':'repeat','a':['repeat',{'quoted"key':'x\\\n“é”'}]},['a',1,'quoted"key']),
    (['same','same'],[1]),({'same':'same'},['same']),('root',[])])
def test_json_path_locations_without_ambiguous_text_search(value,path):
    text,start=string_location(value,path)
    assert canonical(value)[start:start+len(canonical(text)[1:-1])]==canonical(text)[1:-1]
    if value==['same','same']:assert start==9


def test_repeated_passage_specific_occurrence_and_escaping(linked_case):
    text='Fee “é”\\value; Fee “é”\\value; End.'
    p,r,d,ref,nums=fixture(linked_case,text)
    start=text.index('Fee',1); end=text.index(';',start)
    ref['cases'][0]['expectations'][0].update(start=start,end=end,quote=text[start:end])
    d['context_notes']=[dict(kind='PROVENANCE',finding='First occurrence only.',passages=[nums[0]])]
    assert audit_reference_coverage(p,r,d,ref)['rows'][0]['location_status']=='NOT_SELECTED'
    d['context_notes'][0]['passages']=[nums[1]]
    out=audit_reference_coverage(p,r,d,ref);row=out['rows'][0]
    assert row['location_status']=='FULLY_SELECTED'
    src=next(s for s in p['sources'] if s['source_id']==row['anchor']['source_id'])
    assert src['text'][row['canonical_start']:row['canonical_end']]==canonical(text[start:end])[1:-1]


def test_unindexable_text_distinguished_from_model_selection(linked_case):
    p,r,d,ref,nums=fixture(linked_case,'X'*2400)
    assert not nums
    ref['cases'][0]['expectations'][0].update(end=10,quote='X'*10)
    row=audit_reference_coverage(p,r,d,ref)['rows'][0]
    assert row['catalog_status']=='NOT_SELECTABLE' and row['location_status']=='NOT_SELECTED'


@pytest.mark.parametrize('bad',['packet','symbol','source','path','negative','bool','quote','duplicate','assessor','request','draft_target','source_tamper'])
def test_misattributed_or_modified_inputs_fail_closed(linked_case,bad):
    p,r,d,ref,_=fixture(linked_case);c=ref['cases'][0];a=c['expectations'][0]
    if bad=='packet':c['packet_id']='wrong'
    if bad=='symbol':c['symbol']='OTHER'
    if bad=='source':a['source_id']='missing'
    if bad=='path':a['raw_path']=['not_there']
    if bad=='negative':a['start']=-1
    if bad=='bool':a['start']=False
    if bad=='quote':a['quote']='changed'
    if bad=='duplicate':c['expectations'].append(deepcopy(a))
    if bad=='assessor':ref['assessor']=''
    if bad=='request':r['body']['input'][0]['content']+='edited'
    if bad=='draft_target':d['target']['symbol']='OTHER'
    if bad=='source_tamper':p['sources'][0]['text']+='edited'
    with pytest.raises(ValueError):audit_reference_coverage(p,r,d,ref)


def test_cli_preserves_inputs_and_writes_repeatable_report(linked_case,monkeypatch,capsys):
    from research_reference_coverage import main
    p,r,d,ref,_=fixture(linked_case);root=ledger_path().parent
    files={'packet':p,'request':r,'draft':d,'reference':ref}
    argv=['audit']
    for name,value in files.items():
        path=root/(name+'.json');path.write_text(canonical(value),encoding='utf-8')
        argv.extend(['--'+name,str(path)])
    argv.extend(['--output',str(root)])
    before={name:(root/(name+'.json')).read_bytes() for name in files}
    monkeypatch.setattr('sys.argv',argv)
    main();first=json.loads(capsys.readouterr().out)
    main();assert json.loads(capsys.readouterr().out)==first
    assert first['eligible_for_handoff'] is False
    assert before=={name:(root/(name+'.json')).read_bytes() for name in files}
