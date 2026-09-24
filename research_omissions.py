"""Offline source-location review queue, never an automatic materiality gate."""
import json
from copy import deepcopy
from evidence_review import canonical, digest
from research_facts import leaves, category, SUBSTANTIVE
from research_linked import numbered_passages
from research_reference_coverage import audit_reference_coverage, string_location

VERSION = '1.0.0-source-omission-queue'


def uncovered(start, end, spans):
    cursor = start; gaps = []
    for a, b in sorted(spans):
        a, b = max(start, a), min(end, b)
        if b <= cursor or a >= end: continue
        if a > cursor: gaps.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < end: gaps.append((cursor, end))
    return gaps


def omission_report(packet, request, draft, reference):
    # Validates immutable request, raw source bindings, envelope and supplied
    # reference. Does not re-admit or change even a rejected provider answer.
    audit = audit_reference_coverage(packet, request, draft, reference)
    catalog = numbered_passages(packet); selections = {}; invalid = []

    def walk(x, path=()):
        if isinstance(x, list):
            for i, value in enumerate(x): walk(value, path + (i,))
        elif isinstance(x, dict):
            if 'passages' in x:
                seen = set()
                for n in x['passages']:
                    if type(n) is not int or n not in catalog or n in seen:
                        invalid.append(dict(path=list(path), number=n)); continue
                    seen.add(n)
                    selections.setdefault(n, []).append(dict(path=list(path),
                        statement=x.get('statement', x.get('finding'))))
            for key, value in x.items(): walk(value, path + (key,))
    walk(draft)
    rows = []
    for n, passage in catalog.items():
        if passage['category'] not in SUBSTANTIVE: continue
        selected = selections.get(n, [])
        inventory = [s for s in selected if s['path'][:1] == ['economic_inventory']]
        state = ('SELECTED_FOR_INVENTORY' if inventory else
                 'NARRATIVE_ONLY_REVIEW' if selected else 'UNSELECTED_REVIEW')
        rows.append(dict(number=n, source_passage=deepcopy(passage),
            selections=selected, inventory_selections=inventory, location_status=state,
            meaning_preserved='NOT_ESTABLISHED', materiality='NOT_ASSESSED'))

    sources = []
    for src in packet['sources']:
        for path, value in leaves(src['raw']):
            if category(src['kind'], path) not in SUBSTANTIVE or not isinstance(value, str): continue
            _, start = string_location(src['raw'], list(path))
            end = start + len(canonical(value)[1:-1])
            available = [r for r in catalog.values() if r['source_id'] == src['source_id'] and r['path'] == list(path)]
            gaps = uncovered(start, end, [(r['start'], r['end']) for r in available])
            sources.append(dict(source_id=src['source_id'], raw_path=list(path), text=value,
                canonical_start=start, canonical_end=end,
                unindexed_spans=[dict(start=a, end=b, quote=src['text'][a:b]) for a, b in gaps],
                catalog_status='UNINDEXED_TEXT_REQUIRES_REVIEW' if gaps else 'FULLY_INDEXED'))

    reference_rows = []
    for row in audit['rows']:
        missing = uncovered(row['canonical_start'], row['canonical_end'],
            [(s['start'], s['end']) for s in row['selections']])
        src = next(s for s in packet['sources'] if s['source_id'] == row['anchor']['source_id'])
        reference_rows.append(dict(anchor=deepcopy(row['anchor']), location_status=row['location_status'],
            unselected_spans=[dict(start=a, end=b, quote=src['text'][a:b]) for a, b in missing],
            materiality='REQUIRES_ATTRIBUTED_SCOPE_REVIEW'))
    result = dict(implementation_version=VERSION, packet_id=packet['packet_id'],
        trace=deepcopy(packet['trace']), request_id=request['request_id'],
        draft_digest=digest(draft), reference_digest=digest(reference), reference_audit_id=audit['audit_id'],
        assessment_scope=draft.get('assessment_scope', draft.get('economic_inventory', {}).get('assessment_scope',
            draft.get('materiality_coverage', {}).get('assessment_scope'))),
        source_texts=sources, passages=rows, reference_rows=reference_rows,
        review_queue=[r['number'] for r in rows if r['location_status'] != 'SELECTED_FOR_INVENTORY'],
        invalid_selections=invalid, original_admission='NOT_EVALUATED_OR_CHANGED',
        classification='INFRASTRUCTURE_EVALUATION', eligible_for_handoff=False,
        semantic_acceptance='NOT_ESTABLISHED', summary_completeness='NOT_ESTABLISHED',
        limitation='All substantive captured text is retained, including unindexed spans. Flags identify location selection only. Boilerplate and optional context remain in the queue; no heuristic or numeric threshold decides relevance. Selected passages can support false prose. No strategy rule, automatic rejection or approval is created.')
    result['report_id'] = digest(result)
    return result


def verify_omission_report(packet, request, draft, reference, report):
    if canonical(omission_report(packet, request, draft, reference)) != canonical(report):
        raise ValueError('OMISSION_REPORT_MISMATCH')


def main():
    import argparse
    from pathlib import Path
    from evidence_pipeline import write_once
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('packet', 'request', 'draft', 'reference', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(); read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    result = omission_report(read(args.packet), read(args.request), read(args.draft), read(args.reference))
    path = write_once(args.output, 'source-omissions-' + result['report_id'] + '.json', canonical(result) + '\n')
    print(canonical(dict(path=str(path), report_id=result['report_id'],
        flagged_passages=len(result['review_queue']), semantic_acceptance='NOT_ESTABLISHED', eligible_for_handoff=False)))


if __name__ == '__main__': main()
