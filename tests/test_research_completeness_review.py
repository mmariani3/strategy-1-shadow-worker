from copy import deepcopy
import json
import pytest
from evidence_review import canonical,digest
from research_completeness_review import prepare_checklist,record_completeness_review,ASPECTS
from test_evidence_review import authorities,snapshot,NOW
from test_research_reviewer import masters,ledger_path
from test_research_facts import fact_case
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_reference_coverage import fixture


def case(linked_case):
    p,r,d,ref,nums=fixture(linked_case)
    assessment=prepare_checklist(p,r,d,ref)
    assessment.update(assessor_id='offline test author',assessor_kind='AI_IMPLEMENTATION_AUTHOR',reviewed_at=NOW)
    return p,r,d,ref,assessment,nums


def test_template_cannot_be_used_as_review(linked_case):
    p,r,d,ref,a,_=case(linked_case)
    template=prepare_checklist(p,r,d,ref)
    assert all(x['status']=='UNRESOLVED' for x in template['aspects'])
    with pytest.raises(ValueError,match='ASSESSOR_REQUIRED'):record_completeness_review(p,r,d,ref,template,NOW)
    out=record_completeness_review(p,r,d,ref,a,NOW)
    assert out['status']=='REVIEW_REQUIRED' and set(out['unresolved_aspects'])==set(ASPECTS)


def test_sufficient_model_label_and_all_citations_do_not_bypass_review(linked_case):
    p,r,d,ref,a,nums=case(linked_case)
    d['materiality_coverage']['status']='SUFFICIENT_FOR_RESEARCH'
    d['context_notes']=[dict(kind='CONDITIONALITY',finding='No fee exists. False prose with valid citation.',passages=nums)]
    a=prepare_checklist(p,r,d,ref);a.update(assessor_id='author',reviewed_at=NOW)
    a['anchors'][0].update(relevance='REQUIRED_FOR_SCOPE',finding='MEANING_ERROR',rationale='The fixture contains a fee; the draft denies it.',
        draft_evidence=[dict(path=['context_notes',0,'finding'],value_digest=digest(d['context_notes'][0]['finding']))])
    for item in a['aspects']:item.update(status='REVIEWED',rationale='Synthetic scope review recorded.')
    original=deepcopy(d);out=record_completeness_review(p,r,d,ref,a,NOW)
    assert out['status']=='REVISIONS_REQUIRED' and out['revision_anchor_ids']==['FEE']
    assert out['summary_completeness']=='NOT_ESTABLISHED' and not out['eligible_for_handoff']
    assert d==original and out['original_coverage_status']=='SUFFICIENT_FOR_RESEARCH'


def test_material_omission_distinct_from_citation_gap(linked_case):
    p,r,d,ref,a,_=case(linked_case)
    a['anchors'][0].update(relevance='REQUIRED_FOR_SCOPE',finding='MATERIAL_OMISSION',rationale='Material fixture fee not included.')
    out=record_completeness_review(p,r,d,ref,a,NOW)
    assert out['assessment']['anchors'][0]['finding']=='MATERIAL_OMISSION'
    a['anchors'][0]['finding']='CITATION_GAP'
    second=record_completeness_review(p,r,d,ref,a,NOW)
    assert second['review_id']!=out['review_id'] and second['status']=='REVISIONS_REQUIRED'
    assert second['unresolved_aspects']  # Never hide other unfinished checks.


def test_scoped_assessor_review_is_never_global_completeness(linked_case):
    p,r,d,ref,a,_=case(linked_case)
    a['anchors'][0].update(relevance='OPTIONAL_CONTEXT',finding='PRESERVED',rationale='Assessor declaration, not machine inference.')
    for item in a['aspects']:item.update(status='NOT_APPLICABLE',rationale='Scope-specific assessor explanation.')
    out=record_completeness_review(p,r,d,ref,a,NOW)
    assert out['status']=='SCOPED_REVIEW_RECORDED'
    assert out['semantic_acceptance']=='NOT_ESTABLISHED' and not out['eligible_for_handoff']
    assert json.loads(canonical(out))==out


@pytest.mark.parametrize('bad',['scope','audit','anchor_missing','anchor_duplicate','aspect_missing','aspect_duplicate',
    'unknown_anchor','draft_hash','draft_path','negative_index','duplicate_evidence','future','naive_time','omission_optional','approval_field'])
def test_mismatches_and_incomplete_checklists_rejected(linked_case,bad):
    p,r,d,ref,a,_=case(linked_case)
    if bad=='scope':a['scope']='different'
    if bad=='audit':a['audit_id']='different'
    if bad=='anchor_missing':a['anchors']=[]
    if bad=='anchor_duplicate':a['anchors']*=2
    if bad=='aspect_missing':a['aspects'].pop()
    if bad=='aspect_duplicate':a['aspects'].append(deepcopy(a['aspects'][0]))
    if bad=='unknown_anchor':a['aspects'][0]['anchor_ids']=['unknown']
    if bad=='draft_hash':a['anchors'][0]['draft_evidence'][0]['value_digest']='0'*64
    if bad=='draft_path':a['anchors'][0]['draft_evidence'][0]['path']=['unknown']
    if bad=='negative_index':a['anchors'][0]['draft_evidence'][0]['path']=['facts',-1]
    if bad=='duplicate_evidence':a['anchors'][0]['draft_evidence']*=2
    if bad=='future':a['reviewed_at']='2099-01-01T00:00:00Z'
    if bad=='naive_time':a['reviewed_at']='2026-09-19T12:00:00'
    if bad=='omission_optional':a['anchors'][0].update(relevance='OPTIONAL_CONTEXT',finding='MATERIAL_OMISSION')
    if bad=='approval_field':a['approved']=True
    with pytest.raises(ValueError):record_completeness_review(p,r,d,ref,a,NOW)


def test_cli_default_prepares_only_and_preserves_originals(linked_case,monkeypatch,capsys):
    from research_completeness_review import main
    p,r,d,ref,a,_=case(linked_case);root=ledger_path().parent
    values={'packet':p,'request':r,'draft':d,'reference':ref,'assessment':a};argv=['review']
    for name,v in values.items():
        path=root/(name+'.json');path.write_text(canonical(v),encoding='utf-8')
        if name!='assessment':argv.extend(['--'+name,str(path)])
    argv.extend(['--output',str(root)]);before={n:(root/(n+'.json')).read_bytes() for n in values}
    monkeypatch.setattr('sys.argv',argv);main();assert json.loads(capsys.readouterr().out)['kind']=='template'
    monkeypatch.setattr('sys.argv',argv+['--assessment',str(root/'assessment.json')]);main()
    result=json.loads(capsys.readouterr().out);assert result['status']=='REVIEW_REQUIRED'
    assert before=={n:(root/(n+'.json')).read_bytes() for n in values}
