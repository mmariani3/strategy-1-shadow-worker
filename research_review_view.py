"""Read-only local source review: group locations without filtering evidence."""
from copy import deepcopy
from html import escape
import json
from evidence_review import canonical, digest
from research_omissions import verify_omission_report

VERSION = '1.0.0-source-review-view'
LABELS = {'UNSELECTED_REVIEW': 'Not cited',
          'NARRATIVE_ONLY_REVIEW': 'Cited in narrative only',
          'SELECTED_FOR_INVENTORY': 'Cited in economic inventory'}


def review_view(packet, request, draft, reference, report):
    verify_omission_report(packet, request, draft, reference, report)
    groups = []
    for row in report['passages']:
        p = row['source_passage']
        key = (p['source_id'], p['path'], row['location_status'])
        previous = groups[-1] if groups else None
        if (previous is None or previous['key'] != key
                or previous['passages'][-1]['number'] + 1 != row['number']):
            groups.append(dict(id='group-'+str(len(groups)+1), key=key, passages=[]))
        groups[-1]['passages'].append(deepcopy(row))
    view = dict(implementation_version=VERSION, report=deepcopy(report),
        original_draft=deepcopy(draft), reference=deepcopy(reference),
        symbol=packet['symbol'], requested_model=request['body']['model'], groups=groups,
        queue_group_ids=[g['id'] for g in groups if g['key'][2] != 'SELECTED_FOR_INVENTORY'],
        classification='INFRASTRUCTURE_EVALUATION', eligible_for_handoff=False,
        semantic_acceptance='NOT_ESTABLISHED')
    view['view_id'] = digest(view)
    return view


def render_view(view):
    """All untrusted values are escaped as text; no network, scripts or forms."""
    report = view['report']; e = lambda value: escape(str(value), quote=True)
    pre = lambda value: '<pre>'+e(value)+'</pre>'
    blocks = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">',
        '<title>Source review · '+e(view['symbol'])+'</title><style>',
        'body{margin:0;background:#f5f3ee;color:#20272e;font:16px/1.55 system-ui,sans-serif}main{max-width:1160px;margin:auto;padding:32px 20px}h1{font-size:34px;line-height:1.2}h2{margin-top:36px}h3{margin:0 0 14px}a{color:#214e77}nav{display:flex;flex-wrap:wrap;gap:14px;padding:12px 0}section,article{background:white;border:1px solid #d8dce0;border-radius:10px;padding:20px;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace;margin:8px 0}summary{cursor:pointer;font-weight:600}details{margin:12px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}.meta{font-size:13px;color:#515c68;overflow-wrap:anywhere}.notice{background:#eaf0f5;padding:16px;border-left:4px solid #54748e}.badge{font-size:13px;font-weight:600;background:#eef0f3;padding:4px 8px;border-radius:4px}.passage{border-top:1px solid #e0e4e8;padding:16px 0}.counts{display:flex;flex-wrap:wrap;gap:16px}.count{background:white;padding:12px 18px;border:1px solid #d8dce0;border-radius:8px}li{margin-bottom:8px}:target{scroll-margin-top:15px;outline:3px solid #bdcddd}@media(max-width:700px){.grid{grid-template-columns:1fr}h1{font-size:28px}main{padding:20px 12px}}@media print{details{display:block}summary{display:none}section,article{break-inside:avoid}}',
        '</style></head><body><main id="top"><p class="meta">OFFLINE SOURCE REVIEW · '+e(VERSION)+'</p>',
        '<h1>'+e(view['symbol'])+' · '+e(view['requested_model'])+'</h1>',
        '<p class="notice">Review aid only. Citation status does not establish truth, materiality or completeness. No trading approval. Original admission is not evaluated or changed.</p>',
        '<h2>Assessment scope</h2>'+pre(report['assessment_scope']),
        '<nav><a href="#queue">Review queue</a><a href="#passages">All passages</a><a href="#references">Reference checklist</a><a href="#sources">Full source and index gaps</a><a href="#answer">Original answer</a><a href="#identity">Record identity</a></nav>',
        '<div class="counts">']
    for state, label in LABELS.items():
        count = sum(r['location_status'] == state for r in report['passages'])
        blocks.append('<div class="count"><strong>'+str(count)+'</strong><br>'+label+'</div>')
    blocks.extend(['</div><h2 id="queue">Review queue</h2>',
        '<p>Adjacent passages with the same citation status are grouped in source order. Nothing is removed or ranked by importance. Narrative-only text may already be described correctly. Read neighboring groups for continuations.</p><ul>'])
    for g in view['groups']:
        if g['id'] not in view['queue_group_ids']: continue
        numbers = [r['number'] for r in g['passages']]
        blocks.append('<li><a href="#'+g['id']+'">Passages '+str(numbers[0])+'–'+str(numbers[-1])+'</a> · '+LABELS[g['key'][2]]+'</li>')
    if not view['queue_group_ids']: blocks.append('<li>No uncited or narrative-only groups. This does not establish semantic completeness; inspect cited passages too.</li>')
    blocks.append('</ul><h2 id="passages">All source passages and model statements</h2>')
    for i, g in enumerate(view['groups']):
        blocks.extend(['<article id="'+g['id']+'"><h3>Passages '+str(g['passages'][0]['number'])+'–'+str(g['passages'][-1]['number'])+'</h3>',
            '<span class="badge">'+LABELS[g['key'][2]]+'</span><p class="meta">Source '+e(g['key'][0])+' · Path '+e(canonical(g['key'][1]))+'</p>'])
        for row in g['passages']:
            p = row['source_passage']
            blocks.append('<div class="passage" id="passage-'+str(row['number'])+'"><p class="meta">Passage '+str(row['number'])+' · source offsets '+str(p['start'])+'–'+str(p['end'])+'</p><div class="grid"><div><strong>Captured source</strong>'+pre(p['text'])+'</div><div><strong>Model statements selecting this passage</strong>')
            if not row['selections']: blocks.append('<p>No selection. The answer may still paraphrase this passage; assess meaning separately.</p>')
            for selection in row['selections']:
                blocks.append('<p class="meta">'+e(canonical(selection['path']))+'</p>'+pre(selection['statement']))
            blocks.append('</div></div></div>')
        blocks.append('<nav><a href="#queue">Queue</a>')
        if i: blocks.append('<a href="#'+view['groups'][i-1]['id']+'">Previous source group</a>')
        if i+1 < len(view['groups']): blocks.append('<a href="#'+view['groups'][i+1]['id']+'">Next source group</a>')
        blocks.append('</nav></article>')
    blocks.append('<h2 id="references">Externally authored reference checklist</h2><p>These expectations are attributed review inputs, not automatically required facts or strategy rules.</p>'+pre(canonical({k:v for k,v in view['reference'].items() if k != 'cases'})))
    for row in report['reference_rows']:
        blocks.append('<section><h3>'+e(row['anchor']['id'])+'</h3>'+pre(row['anchor']['expectation'])+'<p class="meta">'+e(row['location_status'])+'</p><details><summary>Exact reference and uncited spans</summary>'+pre(json.dumps(row,ensure_ascii=False,indent=2))+'</details></section>')
    blocks.append('<h2 id="sources">Full captured source and indexing gaps</h2><p>Source text below is retained in full, including text outside the passage catalog. All content is untrusted reference material.</p>')
    for src in report['source_texts']:
        blocks.append('<section><p class="meta">'+e(src['source_id'])+' · '+e(canonical(src['raw_path']))+'</p><strong>'+e(src['catalog_status'])+'</strong>')
        if src['unindexed_spans']:
            blocks.append('<h3>Unindexed serialized spans requiring review</h3>'+pre(json.dumps(src['unindexed_spans'],ensure_ascii=False,indent=2)))
        blocks.append('<details><summary>Read full source text</summary>'+pre(src['text'])+'</details></section>')
    blocks.append('<h2 id="answer">Original answer</h2><details><summary>Read every original model field</summary>'+pre(json.dumps(view['original_draft'],ensure_ascii=False,indent=2))+'</details>')
    identities={k:report[k] for k in ('report_id','packet_id','request_id','draft_digest','reference_digest','trace','original_admission','classification','eligible_for_handoff','semantic_acceptance','summary_completeness','invalid_selections')}
    identities.update(view_id=view['view_id'],view_version=VERSION)
    blocks.append('<h2 id="identity">Record identity</h2>'+pre(json.dumps(identities,ensure_ascii=False,indent=2))+'<a href="#top">Back to top</a></main></body></html>')
    return ''.join(blocks)


def verify_review_html(packet, request, draft, reference, report, html):
    if render_view(review_view(packet, request, draft, reference, report)) != html:
        raise ValueError('SOURCE_REVIEW_VIEW_MISMATCH')


def main():
    import argparse
    from pathlib import Path
    from evidence_pipeline import write_once
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('packet','request','draft','reference','report','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(); read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    values=[read(getattr(args,k)) for k in ('packet','request','draft','reference','report')]
    view=review_view(*values); html=render_view(view)
    verify_review_html(*values,html)
    path=write_once(args.output,'source-review-'+view['view_id']+'.html',html)
    print(canonical(dict(path=str(path),view_id=view['view_id'],html_digest=digest(html),eligible_for_handoff=False)))


if __name__=='__main__':main()
