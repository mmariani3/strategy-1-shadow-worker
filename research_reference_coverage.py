"""Offline location coverage against supplied reference anchors, never semantic approval.

Read-only sidecar for v14/v15 drafts, including rejected drafts. It does not repair,
reparse for admission, call a model, discover required facts, or modify a request.
"""
import json
from evidence_review import canonical, digest, aware
from research_reviewer import evidence_message
from research_linked import LinkedDraft, VERSIONS, validate_linked_request, numbered_passages

VERSION = '1.0.0-reference-location-audit'


def string_location(value, path, offset=0):
    """Locate a string by JSON path in canonical serialization, without text search."""
    if not path:
        if not isinstance(value, str): raise ValueError('REFERENCE_STRING_REQUIRED')
        return value, offset + 1  # skip opening JSON quote
    part, rest = path[0], path[1:]
    if isinstance(value, dict) and isinstance(part, str) and part in value:
        pos = offset + 1
        for key in sorted(value):
            pos += len(canonical(key)) + 1
            if key == part: return string_location(value[key], rest, pos)
            pos += len(canonical(value[key])) + 1
    elif isinstance(value, list) and type(part) is int and 0 <= part < len(value):
        pos = offset + 1 + sum(len(canonical(x)) + 1 for x in value[:part])
        return string_location(value[part], rest, pos)
    raise ValueError('REFERENCE_PATH_INVALID')


def merged_length(start, end, spans):
    covered = 0; cursor = start
    for a, b in sorted(spans):
        a = max(start, a); b = min(end, b)
        if b > max(cursor, a): covered += b - max(cursor, a)
        cursor = max(cursor, b)
    return covered


def audit_reference_coverage(packet, request, draft, reference):
    """Measure exact selected-location overlap, not recall of economic meaning.

    Reference scope/importance is externally authored. A full selected span can
    support false prose; an unselected span can be paraphrased without a citation.
    Neither status admits, rejects or changes the saved research result.
    """
    from research_economic import VERSIONS as ECONOMIC_VERSIONS, validate_economic_request
    from research_terms import VERSIONS as TERMS_VERSIONS, TermsDraft, validate_terms_request
    from research_scope import VERSIONS as SINGLE_SCOPE_VERSIONS, project_draft, validate_scope_request
    from research_typed import VERSIONS as TYPED_VERSIONS, validate_typed_request
    versions = (request.get('implementation_version'), request.get('prompt_version'))
    from research_tiers import VERSIONS as TIER_VERSIONS, validate_tier_request
    if versions == TIER_VERSIONS:
        validate_tier_request(packet, request)
        audit_version = '1.5.0-reference-location-audit'
    elif versions == TYPED_VERSIONS:
        validate_typed_request(packet, request)
        audit_version = '1.4.0-reference-location-audit'
    elif versions == SINGLE_SCOPE_VERSIONS:
        validate_scope_request(packet, request)
        audit_version = '1.3.0-reference-location-audit'
    elif versions == TERMS_VERSIONS:
        validate_terms_request(packet, request)
        audit_version = '1.2.0-reference-location-audit'
    elif versions == ECONOMIC_VERSIONS:
        validate_economic_request(packet, request)
        audit_version = '1.1.0-reference-location-audit'
    elif versions == VERSIONS:
        validate_linked_request(packet, request)
        audit_version = VERSION  # Exact historical output/digest remains reproducible.
    else:
        raise ValueError('REFERENCE_AUDIT_REQUIRES_V14')
    if request['request_id'] != digest(dict(version=versions[0], prompt_version=versions[1], body=request['body'])):
        raise ValueError('REQUEST_DIGEST_MISMATCH')
    evidence_message(packet)
    if versions in (SINGLE_SCOPE_VERSIONS, TYPED_VERSIONS, TIER_VERSIONS):
        d = project_draft(draft)['research']
    elif versions == TERMS_VERSIONS:
        TermsDraft.model_validate(draft)
        d = draft['research']
    else:
        LinkedDraft.model_validate(draft)
        d = draft
    # Inspect original strings, not whitespace-normalized model_dump values.
    if (d['target']['symbol'] != packet['symbol'] or d['materiality_coverage']['subject_symbol'] != packet['symbol']
            or any(c['subject_symbol'] != packet['symbol'] for c in d['claims'])):
        raise ValueError('DRAFT_TARGET_MISMATCH')
    if (not isinstance(reference.get('assessor'), str) or not reference['assessor'].strip()
            or type(reference.get('independent')) is not bool):
        raise ValueError('REFERENCE_ATTRIBUTION_REQUIRED')
    aware(reference['at'])
    cases = [c for c in reference['cases'] if c['packet_id'] == packet['packet_id']]
    if len(cases) != 1 or cases[0]['symbol'] != packet['symbol']:
        raise ValueError('REFERENCE_PACKET_MISMATCH')
    anchors = cases[0]['expectations']
    if not anchors or len({a['id'] for a in anchors}) != len(anchors):
        raise ValueError('REFERENCE_ANCHOR_SET_INVALID')
    catalog = numbered_passages(packet); selected = []; invalid = []

    def walk(value, path=()):
        if isinstance(value, dict):
            if 'passages' in value:
                seen = set()
                for n in value['passages']:
                    row = catalog.get(n)
                    if row is None or n in seen:
                        invalid.append(dict(path=list(path),number=n,reason='UNKNOWN' if row is None else 'DUPLICATE'))
                    else:
                        selected.append(dict(row, model_path=list(path), number=n,
                            model_statement=value.get('statement', value.get('finding'))))
                    seen.add(n)
            for k, v in value.items(): walk(v, path + (k,))
        elif isinstance(value, list):
            for i, v in enumerate(value): walk(v, path + (i,))
    walk(draft)
    sources = {s['source_id']: s for s in packet['sources']}; rows = []
    for a in anchors:
        if not isinstance(a['id'], str) or not a['id'].strip() or not a['expectation'].strip():
            raise ValueError('REFERENCE_ANCHOR_INVALID')
        src = sources.get(a['source_id'])
        if src is None: raise ValueError('REFERENCE_SOURCE_MISMATCH')
        if not isinstance(a['raw_path'], list): raise ValueError('REFERENCE_PATH_INVALID')
        value, base = string_location(src['raw'], a['raw_path'])
        start, end = a['start'], a['end']
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(value)
                or value[start:end] != a['quote']):
            raise ValueError('REFERENCE_SPAN_MISMATCH')
        absolute = base + len(canonical(value[:start])[1:-1])
        quote = canonical(a['quote'])[1:-1]; finish = absolute + len(quote)
        if src['text'][absolute:finish] != quote: raise ValueError('REFERENCE_SERIALIZATION_MISMATCH')
        def overlaps(row):
            return (row['source_id'] == a['source_id'] and row['path'] == a['raw_path']
                and row['start'] < finish and row['end'] > absolute)
        available = [r for r in catalog.values() if overlaps(r)]
        chosen = [r for r in selected if overlaps(r)]
        available_chars = merged_length(absolute, finish, [(r['start'], r['end']) for r in available])
        selected_chars = merged_length(absolute, finish, [(r['start'], r['end']) for r in chosen])
        status = 'FULLY_SELECTED' if selected_chars == len(quote) else 'PARTIALLY_SELECTED' if selected_chars else 'NOT_SELECTED'
        rows.append(dict(anchor=a, canonical_start=absolute, canonical_end=finish,
            location_status=status, catalog_status='FULLY_SELECTABLE' if available_chars == len(quote) else 'PARTIALLY_SELECTABLE' if available_chars else 'NOT_SELECTABLE',
            selected_encoded_characters=selected_chars, anchor_encoded_characters=len(quote),
            selections=[{k:r[k] for k in ('number','passage_id','model_path','model_statement','start','end')} for r in chosen],
            semantic_coverage='NOT_ESTABLISHED'))
    result = dict(implementation_version=audit_version, packet_id=packet['packet_id'], trace=packet['trace'],
        request_id=request['request_id'], draft_digest=digest(draft), reference_digest=digest(reference),
        reference_provenance={k:reference[k] for k in ('assessor','at','independent')},
        reference_scope='SUPPLIED_ANCHORS_ONLY_NOT_COMPLETE_SOURCE_INVENTORY',
        independence_verification='NOT_ESTABLISHED_BY_SOFTWARE', rows=rows, invalid_selections=invalid,
        classification='INFRASTRUCTURE_EVALUATION', eligible_for_handoff=False,
        original_admission='NOT_EVALUATED_OR_CHANGED', semantic_acceptance='NOT_ESTABLISHED',
        limitation='Location overlap only. Citing an anchor does not establish truthful prose or complete context; an uncited anchor is a review flag, not a strategy rule or automatic rejection.')
    result['audit_id'] = digest(result)
    return result


def main():
    import argparse
    from pathlib import Path
    from evidence_pipeline import write_once
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('packet','request','draft','reference','output'): parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args(); read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    result = audit_reference_coverage(read(args.packet),read(args.request),read(args.draft),read(args.reference))
    path = write_once(args.output,'reference-location-'+result['audit_id']+'.json',canonical(result)+'\n')
    print(canonical(dict(path=str(path),audit_id=result['audit_id'],semantic_acceptance='NOT_ESTABLISHED',eligible_for_handoff=False)))


if __name__ == '__main__': main()
