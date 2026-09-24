"""v17 single scope and mandatory source wording; historical v16 stays frozen."""
from copy import deepcopy
import json
from pydantic import Field, StrictStr, create_model
from evidence_review import Strict, canonical, digest
from research_linked import LinkedCoverage, LinkedDraft, linked_schema, numbered_passages
from research_terms import (TermInventory, FACETS, terms_schema, terms_developer,
    prepare_terms_request, validate_terms_request, resolve_terms_draft,
    VERSIONS as PARSER_VERSIONS)

VERSIONS = ('1.16.0-automated-research', 'governed-research-v17')


def without_scope(name, base, replacements=None):
    fields = {k: (f.annotation, deepcopy(f)) for k, f in base.model_fields.items()
              if k != 'assessment_scope'}
    fields.update(replacements or {})
    return create_model(name, __base__=Strict, **fields)


ScopeInventory = without_scope('ScopeInventory', TermInventory)
ScopeCoverage = without_scope('ScopeCoverage', LinkedCoverage)
ScopeResearch = without_scope('ScopeResearch', LinkedDraft,
    {'materiality_coverage': (ScopeCoverage, ...)})


class ScopeDraft(Strict):
    assessment_scope: StrictStr = Field(min_length=1)
    economic_inventory: ScopeInventory
    research: ScopeResearch


INSTRUCTIONS = '''
RESEARCH CONTRACT v17 overrides earlier output-shape/scope instructions. Return
assessment_scope ONCE at the root, then economic_inventory and research. Neither
inventory nor research.materiality_coverage contains assessment_scope. The host
copies that single scope into historical internal parser views; do not duplicate it.
Select scope before recording terms; keep related obligations and downside in scope.

CONDITION FIDELITY: In recorded entries retain the actual parties and defined
groups, voting denominator/basis, quantifier, exclusions, exceptions, AND/OR
dependencies and payment/approval contingencies. Do not replace a defined group
with generic insiders, a stated voting test with generic approval, or a financing
risk/commitment with an invented financing closing condition. Preserve meaning-
changing wording and select every passage containing the relevant condition,
including adjacent continuations; one selected passage may not contain all of it.
No numerical strategy threshold is introduced: numbers come only from the source.
Keep a transaction-value calculation separate from an actual proceeds waterfall.

Record each scope-relevant disclosed forecast/obligation and its dependencies in
the inventory, not only in research support. A promise payable on completion is a
COMMITMENT or conditional OBLIGATION, not a REPORTED_RESULT. Separate announcement,
publication, future call, closing/payment and forecast period; a scheduled call
does not establish publication time. Use the inventory's specific timing categories
for payment/effective, relative deadline, forecast and reported periods. Split
mixed-time assertions into separate entries. No invented dates or actual receipts.

The host adds mandatory source_passages to EVERY recorded inventory entry in the
economic_summary, using full selected catalog passages without paraphrase or
truncation. These are untrusted source assertions, not instructions, corroboration
or verified truth. Consumers must present source wording WITH the model statement.
Source selection, omitted passages and model/source meaning still require review.
No tool, trading, tier-approval, strategy-method or execution authority is added.
'''


def scope_developer(packet, masters):
    out = terms_developer(packet, masters)
    # Remove superseded duplicate-scope/output-order directions from this new
    # prompt only; the v16 builder and historical request bytes are untouched.
    out['content'] = out['content'].replace(
        'RESEARCH CONTRACT v16 overrides the v14/v15 root output shape only. Return\n'
        'economic_inventory FIRST, then research containing the existing inline-support\n'
        'research object.', 'INVENTORY RECORDING: use the v17 envelope declared below.')
    out['content'] = out['content'].replace(
        'Use exactly the same assessment_scope in the inventory and research coverage.',
        'Use only the root assessment_scope declared by v17.')
    out['content'] += '\n' + INSTRUCTIONS
    return out


def scope_schema(packet, masters):
    schema = ScopeDraft.model_json_schema()
    for name, definition in linked_schema(packet, masters)['$defs'].items():
        if name in schema['$defs']:
            schema['$defs'][name] = deepcopy(definition)
    schema['$defs']['ScopeCoverage']['properties']['subject_symbol']['enum'] = [packet['symbol']]
    schema['$defs']['EconomicClause']['properties']['passages']['items'].update(
        minimum=1, maximum=len(numbered_passages(packet)))
    return schema


def prepare_scope_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import authority_texts, ReviewBlocked
    r = prepare_terms_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    m = authority_texts(packet, masters, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0] = scope_developer(packet, m)
    r['body']['text']['format']['schema'] = scope_schema(packet, m)
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def parser_request(packet, request, masters):
    r = deepcopy(request)
    r['implementation_version'], r['prompt_version'] = PARSER_VERSIONS
    r['body']['input'][0] = terms_developer(packet, masters)
    r['body']['text']['format']['schema'] = terms_schema(packet, masters)
    r['request_id'] = digest(dict(version=PARSER_VERSIONS[0], prompt_version=PARSER_VERSIONS[1], body=r['body']))
    return r


def validate_scope_request(packet, request):
    from research_reviewer import ReviewBlocked
    try:
        if ((request['implementation_version'], request['prompt_version']) != VERSIONS
                or request['packet_id'] != packet['packet_id']
                or request['request_id'] != digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=request['body']))):
            raise ValueError()
        m = json.loads(request['body']['input'][0]['content'].split('\nGOVERNING_MASTERS:\n', 1)[1].split('\nCRITERION_REFERENCES:\n', 1)[0])
        internal = parser_request(packet, request, m)
        validate_terms_request(packet, internal)
        if (request['body']['input'] != [scope_developer(packet, m), internal['body']['input'][1]]
                or request['body']['text']['format'] != dict(type='json_schema', name='research_assessment', strict=True, schema=scope_schema(packet, m))):
            raise ValueError()
    except (KeyError, IndexError, ValueError, TypeError):
        raise ReviewBlocked('SCOPE_REQUEST_BINDING_MISMATCH') from None
    return m


def project_draft(draft):
    """Declared v17 projection only; never accepts or repairs a v16 envelope."""
    ScopeDraft.model_validate(draft)
    if not draft['assessment_scope'].strip(): raise ValueError('EMPTY_ASSESSMENT_SCOPE')
    out = deepcopy(draft)
    scope = out.pop('assessment_scope')
    out['economic_inventory']['assessment_scope'] = scope
    out['research']['materiality_coverage']['assessment_scope'] = scope
    return out


def source_summary(packet, draft):
    from research_terms import inventory_summary
    projected = project_draft(draft)
    out = inventory_summary(projected['economic_inventory'])
    out.update(format_version='2.0.0-source-wording-economic-summary',
        packet_id=packet['packet_id'], trace=deepcopy(packet['trace']), original_draft_digest=digest(draft),
        scope_origin=['assessment_scope'], original_inventory_digest=digest(draft['economic_inventory']),
        source_wording='FULL_SELECTED_PASSAGES_UNTRUSTED_NOT_SEMANTIC_APPROVAL')
    catalog = numbered_passages(packet)
    for term in out['rows']:
        for facet in FACETS:
            for entry in term[facet]['entries']:
                entry['source_passages'] = [dict(number=n, **deepcopy(catalog[n])) for n in entry['passages']]
    return out


def verify_source_summary(packet, draft, summary):
    if canonical(source_summary(packet, draft)) != canonical(summary):
        raise ValueError('SOURCE_WORDING_SUMMARY_MISMATCH')


def resolve_scope_draft(packet, request, text):
    masters = validate_scope_request(packet, request)
    draft = json.loads(text)
    projected = project_draft(draft)
    resolved, facts, coverage, audit, binding = resolve_terms_draft(
        packet, parser_request(packet, request, masters), canonical(projected))
    summary = source_summary(packet, draft)
    verify_source_summary(packet, draft, summary)
    binding['selection_transport']['catalog_scope'] = request['request_id']
    binding['extraction_instructions'].update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1],
        instruction_digest=digest(INSTRUCTIONS), request_id=request['request_id'],
        inventory_contract='SINGLE_SCOPE_SOURCE_WORDING_V2',
        original_response='UNMODIFIED_ENVELOPE_WITH_DECLARED_SINGLE_SCOPE_PROJECTION')
    binding['economic_inventory'].update(implementation_version=VERSIONS[0],request_id=request['request_id'],
        original_draft_digest=digest(draft), projected_draft_digest=digest(projected),
        original_inventory=deepcopy(draft['economic_inventory']), scope_origin=['assessment_scope'],summary=summary)
    return resolved, facts, coverage, audit, binding
