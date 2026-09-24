"""Offline v20 declaration/entry checks; never source-meaning or trade approval."""
from copy import deepcopy
import json
import re

from evidence_review import canonical, digest
from research_meaning_review import meaning_dossier

VERSION = '1.0.0-research-structure-audit'
# Deliberately narrow declarations, not interpretation of free-form explanations.
# Lists/ranges are not expanded into individual explanations. Numbers in amounts,
# dates, rule 750, or the rules array do not count as an explicit rule 75 marker.
RULE_MARKER = re.compile(r'\brule\s+#?\s*([0-9]+)(?!\w|\.\d)', re.IGNORECASE)
CORE_FACETS = ('amounts', 'conditions', 'timing')


def structure_audit(packet, request, draft, reference):
    if request.get('prompt_version') != 'governed-research-v20':
        raise ValueError('STRUCTURE_AUDIT_REQUIRES_V20')
    dossier = meaning_dossier(packet, request, draft, reference)
    proposal = draft['research']['tier_proposal']
    explanation = proposal['explanation']
    markers = [dict(rule_number=int(m.group(1)), start=m.start(), end=m.end(),
                    text=m.group()) for m in RULE_MARKER.finditer(explanation)]
    declared = {m['rule_number'] for m in markers}
    rows = []

    def add(kind, path, flags, **extra):
        value = draft
        for key in path: value = value[key]
        row = dict(kind=kind, path=path, value_digest=digest(value),
                   original_value=deepcopy(value), flags=flags, **extra)
        row['item_id'] = digest(dict(kind=kind, path=path))
        rows.append(row)

    for item in dossier['items']:
        if item['kind'] != 'RULE_APPLICATION': continue
        n = item['rule_number']
        flags = (['UNRESOLVED_RULE_MAPPING'] if n is None or proposal['mapping_status'] != 'PROPOSED'
                 else ['RULE_DECLARATION_NOT_FOUND'] if n not in declared else [])
        add('RULE_APPLICATION', item['path'], flags, rule_number=n,
            governing_rule=deepcopy(item['governing_rule']),
            explanation=explanation, explanation_digest=digest(explanation),
            declaration_matches=[m for m in markers if m['rule_number'] == n],
            interpretation='Marker presence only; individual explanation and source support still require meaning review.')
    for i, term in enumerate(draft['economic_inventory']['terms']):
        counts = {k:len(term[k]['entries']) for k in CORE_FACETS}
        flags = [] if sum(counts.values()) else ['NO_CORE_TERM_ENTRIES']
        add('ECONOMIC_TERM', ['economic_inventory','terms',i], flags,
            core_entry_counts=counts, qualification_entries=len(term['qualifications']['entries']),
            interpretation='No amounts/conditions/timing entries means the structured core needs review; prose elsewhere may preserve it. Unknown amounts alone are not an error.')
    result = dict(implementation_version=VERSION, packet_id=packet['packet_id'],
        request_id=request['request_id'], draft_digest=digest(draft),
        reference_digest=digest(reference), dossier_id=dossier['dossier_id'],
        original_versions=deepcopy(dossier['original_versions']), trace=deepcopy(dossier['trace']),
        assessment_scope=draft['assessment_scope'], items=rows,
        unselected_rule_markers=[m for m in markers if m['rule_number'] not in proposal['rules']],
        flagged_item_ids=[r['item_id'] for r in rows if r['flags']],
        invalid_selections=deepcopy(dossier['invalid_selections']),
        status='REVIEW_REQUIRED' if any(r['flags'] for r in rows) or dossier['invalid_selections'] else 'NO_STRUCTURAL_FLAGS',
        classification='INFRASTRUCTURE_EVALUATION', eligible_for_handoff=False,
        semantic_acceptance='NOT_ESTABLISHED', original_admission='NOT_EVALUATED_OR_CHANGED',
        api_calls=0,
        limitations=[
            'Literal rule N or rule #N markers only. Alternative wording can be flagged; negation, quotations and generic justifications can still contain markers.',
            'No flags is not an explanation-quality, source-entailment, completeness or approval result.',
            'A core entry can itself contain irrelevant or unsupported prose; source meaning must still be reviewed.',
            'Sparse entries may be appropriate for unavailable data; flags never require inventing values, obtaining optional documents or changing strategy eligibility.',
            'New sidecar only: original requests, parser outcomes, model answers and attributed reviews stay unchanged.'])
    result['report_id'] = digest(result)
    return result


def main():
    import argparse
    from pathlib import Path
    from evidence_pipeline import write_once
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('packet','request','draft','reference','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    inputs = [json.loads(getattr(args,n).read_text(encoding='utf-8'))
              for n in ('packet','request','draft','reference')]
    report = structure_audit(*inputs)
    path = write_once(args.output, 'structure-audit-'+report['report_id']+'.json', canonical(report)+'\n')
    print(canonical(dict(file=str(path), status=report['status'], api_calls=0, eligible_for_handoff=False)))


if __name__ == '__main__': main()
