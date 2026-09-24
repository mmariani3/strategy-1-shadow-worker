"""Evidence retention and untrusted-text handling in offline HTML review."""
from copy import deepcopy
from html import escape
from html.parser import HTMLParser
import json
import pytest
from evidence_review import canonical
from research_omissions import omission_report
from research_review_view import review_view, render_view, verify_review_html
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_scope import make_case


class Page(HTMLParser):
    def __init__(self):super().__init__();self.tags=[];self.ids=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag);a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'href' in a:self.links.append(a['href'])


def test_grouping_retains_every_location_original_text_and_neighbor_navigation(linked_case):
    p,r,d,ref,_=make_case(linked_case);report=omission_report(p,r,d,ref);original=deepcopy((p,r,d,ref,report))
    view=review_view(p,r,d,ref,report);rows=[x for g in view['groups'] for x in g['passages']]
    assert rows==report['passages'] and (p,r,d,ref,report)==original
    assert [row['number'] for g in view['groups'] if g['id'] in view['queue_group_ids'] for row in g['passages']]==report['review_queue']
    html=render_view(view);verify_review_html(p,r,d,ref,report,html)
    for src in report['source_texts']:assert escape(src['text'],quote=True) in html
    for row in rows:assert escape(row['source_passage']['text'],quote=True) in html
    assert 'Original admission is not evaluated or changed' in html and 'No trading approval' in html
    page=Page();page.feed(html)
    assert len(page.ids)==len(set(page.ids))
    assert all(h.startswith('#') and h[1:] in page.ids for h in page.links)
    assert not set(page.tags)&{'script','iframe','form','img','object','embed'}


@pytest.mark.parametrize('attack',['<script>alert(1)</script>','</pre><img src=x onerror=alert(1)>','javascript:alert(1)','“Unicode” & <b>repeated</b>'])
def test_source_and_model_markup_is_inert_text(linked_case,attack):
    from test_research_reference_coverage import fixture
    p,r,d,ref,nums=fixture(linked_case,attack+' A conditional payment. '+attack)
    d['limitations'].append(attack)
    report=omission_report(p,r,d,ref);html=render_view(review_view(p,r,d,ref,report))
    assert escape(attack,quote=True) in html
    page=Page();page.feed(html)
    assert not set(page.tags)&{'script','img','iframe','form','b'}
    assert "default-src &#39;none&#39;" in html


@pytest.mark.parametrize('mutation',['drop_passage','source_text','queue','trace'])
def test_tampered_report_is_rejected_before_display(linked_case,mutation):
    p,r,d,ref,_=make_case(linked_case);report=omission_report(p,r,d,ref)
    if mutation=='drop_passage':report['passages'].pop()
    if mutation=='source_text':report['source_texts'][0]['text']='fake'
    if mutation=='queue':report['review_queue']=[]
    if mutation=='trace':report['trace']['candidate_id']='invented'
    with pytest.raises(ValueError,match='OMISSION_REPORT_MISMATCH'):review_view(p,r,d,ref,report)


def test_changed_html_detected_and_cli_writes_immutable_artifact(linked_case,monkeypatch,capsys):
    import research_review_view as cli
    p,r,d,ref,_=make_case(linked_case);report=omission_report(p,r,d,ref)
    html=render_view(review_view(p,r,d,ref,report))
    with pytest.raises(ValueError,match='SOURCE_REVIEW_VIEW_MISMATCH'):verify_review_html(p,r,d,ref,report,html.replace('No trading approval','Approved'))
    root=ledger_path().parent;argv=['view']
    for name,value in [('packet',p),('request',r),('draft',d),('reference',ref),('report',report)]:
        path=root/(name+'.json');path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');argv+=['--'+name,str(path)]
    argv+=['--output',str(root)];monkeypatch.setattr('sys.argv',argv)
    cli.main();first=json.loads(capsys.readouterr().out)
    cli.main();assert json.loads(capsys.readouterr().out)==first
    from pathlib import Path
    assert Path(first['path']).read_text(encoding='utf-8')==html


def test_unindexed_spans_and_narrative_only_prose_stay_visible(linked_case,monkeypatch):
    import research_omissions as omissions
    from research_linked import numbered_passages
    p,r,d,ref,_=make_case(linked_case);cat=numbered_passages(p)
    nums=d['economic_inventory']['terms'][0]['amounts']['entries'][0]['passages']
    d['economic_inventory']['terms']=[];d['economic_inventory']['status']='UNRESOLVED'
    d['research']['context_notes'].append(dict(kind='CONDITIONALITY',finding='Only narrative description',passages=nums))
    # Simulate a catalog hole; full source text must still be in the view.
    monkeypatch.setattr(omissions,'numbered_passages',lambda p:{n:v for n,v in cat.items() if n!=nums[0]})
    report=omissions.omission_report(p,r,d,ref);view=review_view(p,r,d,ref,report);html=render_view(view)
    assert any(s['unindexed_spans'] for s in report['source_texts'])
    assert 'Unindexed serialized spans requiring review' in html
    assert 'Cited in narrative only' in html and 'Only narrative description' in html
    assert view['semantic_acceptance']=='NOT_ESTABLISHED' and not view['eligible_for_handoff']
