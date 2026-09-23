"""Offline export of a completed v21 ledger answer and its full source review."""
from copy import deepcopy
from contextlib import closing
from html import escape
import json
from pathlib import Path
import sqlite3

from evidence_review import canonical, digest
from research_explicit import VERSIONS, validate_integrated_request
from research_meaning_review import meaning_dossier
from research_reviewer import parse_response, ReviewBlocked

VERSION = '1.0.0-explicit-source-review'


def explicit_review(packet, request, response, received_at, reference):
    """Validate the original response; never publish a projection as its answer."""
    _, base, _ = validate_integrated_request(packet, request)
    result = parse_response(packet, request, response, received_at)
    contract = result['research_binding']['explicit_response_contract']
    original = contract['original_draft']
    inherited = meaning_dossier(packet, base, original['draft'], reference)
    items = []
    # Each embedded item is explicitly bound into the full wrapper. The internal
    # v20 request is a validator projection, never a historical/provider request.
    for row in inherited['items']:
        item = deepcopy(row)
        item['path'] = ['draft'] + item['path']
        for fact in item.get('candidate_facts', []):
            fact['path'] = ['draft'] + fact['path']
        item['item_id'] = digest(dict(request_id=request['request_id'], path=item['path'], kind=item['kind'],
            anchor=item.get('anchor')))
        items.append(item)
    for name, kind in (('rule_applications', 'EXPLICIT_RULE_EXPLANATION'), ('term_assertions', 'EXPLICIT_TERM_ASSERTION')):
        for i, row in enumerate(contract[name]):
            path = [name, i]
            items.append(dict(item_id=digest(dict(request_id=request['request_id'], path=path, kind=kind)),
                kind=kind, path=path, original_value=deepcopy(original[name][i]),
                linked_evidence=deepcopy(row), status='SOURCE_REVIEW_REQUIRED',
                question='Does the full source support this statement and its qualifications? Valid links and nonblank text do not prove meaning.'))
    report = dict(implementation_version=VERSION, original_versions=dict(implementation=VERSIONS[0], prompt=VERSIONS[1]),
        request_id=request['request_id'], packet_id=packet['packet_id'], trace=deepcopy(packet['trace']),
        provider_response_id=response['id'], requested_model=request['body']['model'], returned_model=response['model'],
        received_at=received_at, usage=deepcopy(response.get('usage')),
        original_provider_response=deepcopy(response), original_response_text=contract['original_response_text'],
        original_draft=deepcopy(original), draft_digest=digest(original), contract_report=contract,
        items=items, source_catalog=inherited['source_catalog'], full_sources=inherited['full_sources'],
        captured_sources=deepcopy(packet['sources']), reference=deepcopy(reference),
        assessment_scope=original['draft']['assessment_scope'],
        classification='INFRASTRUCTURE_EVALUATION', eligible_for_handoff=False,
        status='SOURCE_REVIEW_REQUIRED', semantic_acceptance='NOT_ESTABLISHED',
        limitations=['No supplied or automatic source judgments. This report is a checklist, not an approval.',
            'Embedded draft checks reuse the frozen v20 validators; the full v21 wrapper and original text are retained.',
            'All captured sources, unindexed continuations and reference anchors remain available. The checklist cannot prove completeness.'])
    report['report_id'] = digest(report)
    return report


def render_explicit_review(report):
    """Inert HTML, exact text only. External source addresses are displayed as text."""
    if report.get('report_id') != digest({k:v for k,v in report.items() if k != 'report_id'}):
        raise ValueError('EXPLICIT_REVIEW_DIGEST_MISMATCH')
    e = lambda x: escape(str(x), quote=True)
    pre = lambda x: '<pre>' + e(json.dumps(x, ensure_ascii=False, indent=2, sort_keys=True)) + '</pre>'
    blocks = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">',
        '<title>Explicit research source review</title><style>body{font:16px/1.5 system-ui;margin:24px auto;max-width:1100px;padding:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{border-top:1px solid #bbb;padding:16px 0}nav a{margin-right:20px}</style></head><body>',
        '<h1>Research answer: source review required</h1>',
        '<p>Infrastructure evaluation only. No semantic acceptance or trading approval.</p>',
        '<nav><a href="#identity">Identity</a><a href="#items">Review checklist</a><a href="#sources">Full sources</a><a href="#answer">Complete original answer</a></nav>',
        '<h2 id="identity">Identity and limits</h2>' + pre({k:report[k] for k in ('report_id','request_id','packet_id','trace','original_versions','provider_response_id','requested_model','returned_model','received_at','usage','limitations')}),
        '<h2>Assessment scope</h2>' + pre(report['assessment_scope']), '<h2 id="items">Review checklist</h2>']
    for item in report['items']:
        blocks.append('<section><h3>' + e(item['kind']) + '</h3>' + pre(item) + '<a href="#sources">Full source and continuations</a></section>')
    blocks.extend(['<h2>Reference anchors</h2>' + pre(report['reference']),
        '<h2 id="sources">Full captured sources, including unindexed text</h2>' + pre(report['captured_sources']),
        '<h2>Decoded substantive text and index gaps</h2>' + pre(report['full_sources']),
        '<h2>All numbered source passages</h2>' + pre(report['source_catalog']),
        '<h2 id="answer">Complete original answer — exact provider text</h2><pre>' + e(report['original_response_text']) + '</pre>',
        '<h2>Complete original provider envelope</h2>' + pre(report['original_provider_response']), '</body></html>'])
    return ''.join(blocks)


def export_ledger_review(ledger_path, request_id, packet, reference):
    # Read-only URI avoids creating a missing ledger or changing historical data.
    with closing(sqlite3.connect(Path(ledger_path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        row = db.execute('select request from requests where id=?', (request_id,)).fetchone()
        if row is None: raise ReviewBlocked('REQUEST_NOT_FOUND')
        request = json.loads(row[0])
        events = {kind:dict(at=at, payload=json.loads(payload)) for kind,at,payload in db.execute(
            'select event_type,at,payload from events where request_id=?', (request_id,))}
    if 'FAILED' in events or 'RECEIVED' not in events or 'COMPLETED' not in events:
        raise ReviewBlocked('COMPLETED_ORIGINAL_RESPONSE_REQUIRED')
    received = events['RECEIVED']
    if parse_response(packet, request, received['payload'], received['at']) != events['COMPLETED']['payload']:
        raise ReviewBlocked('COMPLETION_HISTORY_MISMATCH')
    return explicit_review(packet, request, received['payload'], received['at'], reference)


def main():
    import argparse
    from evidence_pipeline import write_once
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ledger', 'packet', 'reference', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--request-id', required=True)
    args = parser.parse_args()
    read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    report = export_ledger_review(args.ledger, args.request_id, read(args.packet), read(args.reference))
    html = render_explicit_review(report)
    files = dict(report=str(write_once(args.output, 'explicit-review-' + report['report_id'] + '.json', canonical(report)+'\n')),
        html=str(write_once(args.output, 'explicit-review-' + digest(html) + '.html', html)))
    print(canonical(dict(files=files, status=report['status'], api_calls=0, eligible_for_handoff=False)))


if __name__ == '__main__': main()
