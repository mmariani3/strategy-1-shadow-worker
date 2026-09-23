"""v19 restricts proposed-tier references to the governing tier's catalog rows."""
from copy import deepcopy
import json
from evidence_review import canonical, digest
from research_linked import numbered_rules
from research_typed import (TypedDraft, typed_schema, typed_developer,
    prepare_typed_request, validate_typed_request, resolve_typed_draft,
    VERSIONS as PARSER_VERSIONS)

VERSIONS = ('1.18.0-automated-research', 'governed-research-v19')
INSTRUCTIONS = '''
RESEARCH CONTRACT v19 retains v18's envelope and source/field requirements.
Choose a proposed tier only when the source facts substantively fit a governing
category. For PROPOSED A/B/C, every rules number must be a catalog row labelled
with that same tier. General guidance, headings and other-tier rows are not
proposed-tier references. They remain in the full masters for context.
If uncertain, use UNRESOLVED mapping and tier; do not force a proposal to satisfy
the schema. The host restricts reference choices, never chooses a tier, approves
its meaning, changes strategy categories or repairs your answer.
'''


def tier_choices(masters):
    rows = numbered_rules(masters)
    return {tier: [n for n, row in rows.items() if row['tier'] == tier]
            for tier in ('A', 'B', 'C')}


def tier_schema(packet, masters):
    schema = typed_schema(packet, masters)
    base = deepcopy(schema['$defs']['LinkedTier'])
    branches = []
    for tier, numbers in tier_choices(masters).items():
        if not numbers: continue  # Never invent a category or a selectable number.
        branch = deepcopy(base); props = branch['properties']
        props['proposed_tier'] = dict(type='string', const=tier)
        props['mapping_status'] = dict(type='string', const='PROPOSED')
        props['rules'] = dict(type='array', minItems=1,
                             items=dict(type='integer', enum=numbers))
        branches.append(branch)
    unresolved = deepcopy(base)
    unresolved['properties']['proposed_tier'] = dict(type='string', const='UNRESOLVED')
    unresolved['properties']['mapping_status'] = dict(type='string', const='UNRESOLVED')
    branches.append(unresolved)
    schema['$defs']['LinkedTier'] = dict(anyOf=branches)
    return schema


def tier_developer(packet, masters):
    out = typed_developer(packet, masters)
    out['content'] += '\n' + INSTRUCTIONS
    return out


def prepare_tier_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import authority_texts, ReviewBlocked
    r = prepare_typed_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    m = authority_texts(packet, masters, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0] = tier_developer(packet, m)
    r['body']['text']['format']['schema'] = tier_schema(packet, m)
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def parser_request(packet, request, masters):
    r = deepcopy(request)
    r['implementation_version'], r['prompt_version'] = PARSER_VERSIONS
    r['body']['input'][0] = typed_developer(packet, masters)
    r['body']['text']['format']['schema'] = typed_schema(packet, masters)
    r['request_id'] = digest(dict(version=PARSER_VERSIONS[0], prompt_version=PARSER_VERSIONS[1], body=r['body']))
    return r


def validate_tier_request(packet, request):
    from research_reviewer import ReviewBlocked
    try:
        if ((request['implementation_version'], request['prompt_version']) != VERSIONS
                or request['packet_id'] != packet['packet_id']
                or request['request_id'] != digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=request['body']))):
            raise ValueError()
        m = json.loads(request['body']['input'][0]['content'].split('\nGOVERNING_MASTERS:\n', 1)[1].split('\nCRITERION_REFERENCES:\n', 1)[0])
        internal = parser_request(packet, request, m)
        validate_typed_request(packet, internal)
        if (request['body']['input'] != [tier_developer(packet, m), internal['body']['input'][1]]
                or request['body']['text']['format'] != dict(type='json_schema', name='research_assessment', strict=True, schema=tier_schema(packet, m))):
            raise ValueError()
    except (KeyError, IndexError, TypeError, ValueError):
        raise ReviewBlocked('TIER_REQUEST_BINDING_MISMATCH') from None
    return m


def validate_tier_selection(draft, masters):
    TypedDraft.model_validate(draft)  # Strict integer and envelope checks first.
    tier = draft['research']['tier_proposal']
    if tier['mapping_status'] == 'PROPOSED':
        allowed = tier_choices(masters).get(tier['proposed_tier'], [])
        if not tier['rules'] or any(n not in allowed for n in tier['rules']):
            raise ValueError('PROPOSED_TIER_REFERENCE_MISMATCH')
    elif tier['proposed_tier'] != 'UNRESOLVED':
        raise ValueError('UNRESOLVED_TIER_CONFLICT')


def resolve_tier_draft(packet, request, text):
    m = validate_tier_request(packet, request)
    validate_tier_selection(json.loads(text), m)
    result = resolve_typed_draft(packet, parser_request(packet, request, m), text)
    binding = result[-1]
    binding['selection_transport']['catalog_scope'] = request['request_id']
    binding['extraction_instructions'].update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1],
        instruction_digest=digest(INSTRUCTIONS), request_id=request['request_id'],
        tier_reference_contract='GOVERNING_TIER_LABELS_ONLY_V1')
    binding['economic_inventory'].update(implementation_version=VERSIONS[0], request_id=request['request_id'])
    return result
