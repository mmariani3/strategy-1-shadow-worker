"""Synthetic offline review fixtures, excluded from Strategy #1 evidence."""
from copy import deepcopy
from html import escape
import json
import pytest
from evidence_review import canonical, digest
from research_completeness_review import draft_value
from research_linked import numbered_passages
from research_meaning_review import (meaning_dossier, meaning_template,
    record_meaning_review, render_meaning_review, verify_meaning_html)
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_tiers import case
from test_research_review_view import Page


def review_case(linked_case):
    p,r,d,ref,m = case(linked_case)
    from research_tiers import tier_choices
    d['research']['tier_proposal'].update(mapping_status='PROPOSED', proposed_tier='A', rules=tier_choices(m)['A'])
    dossier = meaning_dossier(p,r,d,ref)
    a = meaning_template(dossier)
    a.update(assessor_id='SYNTHETIC_FIXTURE_AUTHOR', assessor_kind='AI_IMPLEMENTATION_AUTHOR', reviewed_at=NOW)
    return p,r,d,ref,dossier,a


def select(a, dossier, kind):
    item = next(x for x in dossier['items'] if x['kind']==kind)
    return next(d for d in a['decisions'] if d['item_id']==item['item_id']),item


def evidence(draft, path):
    return dict(path=path, value_digest=digest(draft_value(draft,path)))


def support_rule(p,d,decision):
    path=['research','selected_event']
    from research_meaning_review import passage_numbers
    decision.update(relevance='REQUIRED_FOR_SCOPE', finding='SUPPORTED',
        rationale='Author-supplied fixture judgment, not a semantic certification.',
        draft_evidence=[evidence(d,path)], source_passages=sorted(set(passage_numbers(draft_value(d,path)))))


def test_individual_rules_and_all_reason_fields_require_separate_review(linked_case):
    p,r,d,ref,di,a=review_case(linked_case);before=deepcopy((p,r,d,ref))
    assert len([x for x in di['items'] if x['kind']=='RULE_APPLICATION'])==len(d['research']['tier_proposal']['rules'])
    assert len([x for x in di['items'] if x['kind']=='TIMING'])==2
    term=next(x for x in di['items'] if x['kind']=='ECONOMIC_TERM')
    assert term['original_value']==d['economic_inventory']['terms'][0]
    assert all('reason' in term['original_value'][f] for f in ('amounts','conditions','timing','qualifications'))
    result=record_meaning_review(p,r,d,ref,a,NOW)
    assert result['status']=='REVIEW_REQUIRED' and not result['eligible_for_handoff']
    assert result['semantic_acceptance']=='NOT_ESTABLISHED' and (p,r,d,ref)==before
    assert result['trace']==p['trace'] and di['original_versions']['prompt']=='governed-research-v19'


@pytest.mark.parametrize('mutation',['omit','duplicate','unknown','dossier','draft_digest','path','source','duplicate_source','bool_source','string_source','unassigned','future','before_reference','unrelated_term','optional_rule','omission_optional','not_applicable_rule'])
def test_incomplete_or_unbound_assessments_fail_closed(linked_case,mutation):
    p,r,d,ref,di,a=review_case(linked_case);x,_=select(a,di,'RULE_APPLICATION')
    if mutation=='omit':a['decisions'].pop()
    if mutation=='duplicate':a['decisions'].append(deepcopy(x))
    if mutation=='unknown':x['item_id']='0'*64
    if mutation=='dossier':a['dossier_id']='0'*64
    if mutation=='draft_digest':x['draft_evidence'][0]['value_digest']='0'*64
    if mutation=='path':x['draft_evidence'][0]['path']=['missing']
    if mutation=='source':x['source_passages']=[999999]
    if mutation=='duplicate_source':x['source_passages']=[1,1]
    if mutation=='bool_source':x['source_passages']=[True]
    if mutation=='string_source':x['source_passages']=['1']
    if mutation=='unassigned':a['assessor_id']='UNASSIGNED'
    if mutation=='future':a['reviewed_at']='2099-01-01T00:00:00Z'
    if mutation=='before_reference':a['reviewed_at']='2000-01-01T00:00:00Z'
    if mutation=='unrelated_term':
        x,_=select(a,di,'ECONOMIC_TERM');x['draft_evidence']=[evidence(d,['assessment_scope'])]
    if mutation=='optional_rule':x['relevance']='OPTIONAL_CONTEXT'
    if mutation=='omission_optional':
        x,_=select(a,di,'SOURCE_ANCHOR');x.update(finding='MATERIAL_OMISSION', relevance='OPTIONAL_CONTEXT',source_passages=[1])
    if mutation=='not_applicable_rule':x.update(finding='NOT_APPLICABLE',relevance='REQUIRED_FOR_SCOPE',source_passages=[1])
    with pytest.raises(ValueError):record_meaning_review(p,r,d,ref,a,NOW)


def test_matching_tier_and_shared_proposal_do_not_establish_rule_support(linked_case):
    p,r,d,ref,di,a=review_case(linked_case);x,_=select(a,di,'RULE_APPLICATION')
    x.update(finding='SUPPORTED',relevance='REQUIRED_FOR_SCOPE',source_passages=[1])
    with pytest.raises(ValueError,match='INDIVIDUAL_RULE_FACT_SUPPORT_REQUIRED'):record_meaning_review(p,r,d,ref,a,NOW)
    support_rule(p,d,x)
    out=record_meaning_review(p,r,d,ref,a,NOW)
    assert out['status']=='REVIEW_REQUIRED' and out['semantic_acceptance']=='NOT_ESTABLISHED'
    # A reviewer can make a false judgment; software claims binding, not truth.
    x['rationale']='Deliberately false reviewer prose retained for attribution.'
    assert record_meaning_review(p,r,d,ref,a,NOW)['assessment']==a


def test_timing_and_assumed_condition_defects_are_recorded_without_answer_repair(linked_case):
    p,r,d,ref,di,a=review_case(linked_case)
    x,item=select(a,di,'ECONOMIC_TERM')
    from research_meaning_review import passage_numbers
    x.update(finding='MEANING_ERROR',relevance='REQUIRED_FOR_SCOPE',
        rationale='Fixture review distinguishes an existing commitment from future funding and refuses an inferred closing condition.',
        source_passages=sorted(set(passage_numbers(item['original_value']))))
    original=canonical(d);out=record_meaning_review(p,r,d,ref,a,NOW)
    assert out['status']=='REVISIONS_REQUIRED' and out['revision_item_ids']==[item['item_id']]
    assert canonical(d)==original and out['original_admission']=='NOT_EVALUATED_OR_CHANGED'


def test_source_continuations_and_unselected_risk_survive_display(linked_case):
    p,r,d,ref,di,a=review_case(linked_case)
    for facet in ('amounts','conditions','timing','qualifications'):
        for entry in d['economic_inventory']['terms'][0][facet]['entries']:
            entry['passages']=entry['passages'][:1]
    di=meaning_dossier(p,r,d,ref);a=meaning_template(di)
    a.update(assessor_id='SYNTHETIC_FIXTURE_AUTHOR',assessor_kind='AI_IMPLEMENTATION_AUTHOR',reviewed_at=NOW)
    html=render_meaning_review(p,r,d,ref,a,NOW);verify_meaning_html(p,r,d,ref,html,a,NOW)
    for src in di['full_sources']:assert escape(src['text'],quote=True) in html
    for item in di['items']:
        if item['kind']=='SOURCE_ANCHOR':assert escape(item['anchor']['quote'],quote=True) in html
    assert 'Adjacent context only' in html and 'Read full captured source and all continuations' in html
    assert 'rule_id' in html and 'No automatic acceptance or trading approval' in html
    page=Page();page.feed(html)
    assert len(page.ids)==len(set(page.ids))
    assert all(h.startswith('#') and h[1:] in page.ids for h in page.links)
    assert not set(page.tags)&{'script','iframe','form','img','object','embed'}
    with pytest.raises(ValueError,match='MEANING_HTML_MISMATCH'):
        verify_meaning_html(p,r,d,ref,html.replace('No automatic acceptance','Approved'),a,NOW)


def test_injected_review_text_is_inert_and_changed_source_is_rejected(linked_case):
    p,r,d,ref,di,a=review_case(linked_case)
    a['decisions'][0]['rationale']='</pre><script>alert(1)</script>'
    html=render_meaning_review(p,r,d,ref,a,NOW)
    assert escape(a['decisions'][0]['rationale'],quote=True) in html and '<script>' not in html
    ref['cases'][0]['expectations'][0]['quote']='replacement'
    with pytest.raises(ValueError):record_meaning_review(p,r,d,ref,a,NOW)


def test_empty_rule_selection_is_explicit_pending_review(linked_case):
    p,r,d,ref,_,_=review_case(linked_case)
    d['research']['tier_proposal'].update(rules=[],proposed_tier='UNRESOLVED',mapping_status='UNRESOLVED')
    di=meaning_dossier(p,r,d,ref)
    rows=[i for i in di['items'] if i['kind']=='RULE_APPLICATION']
    assert len(rows)==1 and rows[0]['rule_number'] is None


@pytest.mark.parametrize('kind',['TIMING','ECONOMIC_TERM','SOURCE_ANCHOR'])
def test_resolved_judgment_requires_source_and_original_draft_binding(linked_case,kind):
    p,r,d,ref,di,a=review_case(linked_case);x,_=select(a,di,kind)
    x.update(finding='SUPPORTED',relevance='REQUIRED_FOR_SCOPE')
    with pytest.raises(ValueError,match='MEANING_SOURCE_EVIDENCE_REQUIRED'):
        record_meaning_review(p,r,d,ref,a,NOW)


def test_even_fully_supplied_judgments_never_become_approval(linked_case):
    p,r,d,ref,di,a=review_case(linked_case)
    from research_meaning_review import passage_numbers
    for item,x in zip(di['items'],a['decisions']):
        if item['kind']=='RULE_APPLICATION':support_rule(p,d,x)
        else:
            numbers=passage_numbers(item['original_value'])
            x.update(finding='SUPPORTED',relevance='REQUIRED_FOR_SCOPE',source_passages=sorted(set(numbers)) or [1])
    out=record_meaning_review(p,r,d,ref,a,NOW)
    assert out['status']=='ATTRIBUTED_REVIEW_RECORDED' and not out['eligible_for_handoff']
    assert out['semantic_acceptance']=='NOT_ESTABLISHED' and out['assessor_independence']=='NOT_ESTABLISHED_BY_SOFTWARE'


@pytest.mark.parametrize('mutation',['draft','request','reference','trace'])
def test_changed_review_inputs_cannot_reuse_an_assessment(linked_case,mutation):
    p,r,d,ref,di,a=review_case(linked_case)
    if mutation=='draft':d['economic_inventory']['terms'][0]['timing']['reason']='changed'
    if mutation=='request':r['body']['input'][0]['content']+=' changed'
    if mutation=='reference':ref['assessor']='different reviewer'
    if mutation=='trace':p['trace']['run_id']='changed'
    with pytest.raises(ValueError):record_meaning_review(p,r,d,ref,a,NOW)


def test_cli_is_reproducible_immutable_and_never_calls_a_provider(linked_case,monkeypatch,capsys):
    import research_meaning_review as cli
    p,r,d,ref,_,a=review_case(linked_case);root=ledger_path().parent;argv=['meaning-review']
    for name,value in [('packet',p),('request',r),('draft',d),('reference',ref),('assessment',a)]:
        path=root/(name+'.json');path.write_text(json.dumps(value),encoding='utf-8');argv+=['--'+name,str(path)]
    argv+=['--output',str(root)];monkeypatch.setattr('sys.argv',argv)
    monkeypatch.setattr('review_attempts.utc_now',lambda:NOW)
    monkeypatch.setattr('review_attempts.execute_once',lambda *args:pytest.fail('No provider execution'))
    cli.main();first=json.loads(capsys.readouterr().out)
    cli.main();assert json.loads(capsys.readouterr().out)==first
    assert first['api_calls']==0 and first['eligible_for_handoff'] is False


def test_saved_assessment_key_order_does_not_change_html(linked_case):
    p,r,d,ref,_,a=review_case(linked_case)
    html=render_meaning_review(p,r,d,ref,a,NOW)
    saved=json.loads(canonical(a))
    assert render_meaning_review(p,r,d,ref,saved,NOW)==html
    verify_meaning_html(p,r,d,ref,html,saved,NOW)
