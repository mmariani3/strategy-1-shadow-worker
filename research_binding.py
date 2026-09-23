"""Opt-in v25 citation references and materiality-summary temporal consistency."""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field, StrictInt, StrictStr
from evidence_review import Strict, canonical, digest
from research_roles import RoleDraft
from research_nature import (VERSIONS as PREVIOUS, INSTRUCTIONS as NATURE_INSTRUCTIONS,
    Nature, prepare_nature_request, validate_nature_request, nature_schema,
    validate_natures, nature_report, nature_checklist, resolve_nature_draft)

VERSIONS = ('1.24.0-automated-research', 'governed-research-v25')
INSTRUCTIONS = NATURE_INSTRUCTIONS.split('The term_classifications schema binds', 1)[0] + '''
v25 CITATION REFERENCES: term_classifications retains term_index, core_nature,
amount_natures and qualification_scope. Do not repeat core_passages or amount
passages in these declarations. term_index identifies the existing term_assertion
with that term_index, NOT its array position. Each amount entry_index identifies
that term's amounts.entries entry. The host binds their complete original source
lists directly, including qualifying continuations; it never selects a subset.
Cover all terms and all amounts entries exactly once. Retain complete citations
on the original assertions and economic entries. Missing citations there remain
invalid. Declarations do not prove source truth or qualification completeness.

MATERIALITY SUMMARY: materiality_term_indices lists every economic term index
exactly once. These references supply the full economic terms and assertions to
the summary, with their original nature, forecast timing, qualifications and
citations. Do not duplicate future economic outcomes into general support clauses
that cannot express FORECAST_PERIOD. No forecast prose is dropped from its term.

For every draft.research.materiality_coverage.support.clauses entry, supply one
materiality_clause_roles entry with clause_index, temporal_scope and reason.
OCCURRED means the whole assertion concerns an occurred event and requires
EVENT_OCCURRENCE. PUBLICATION means document publication timing and requires
PUBLICATION. ATEMPORAL requires NOT_TEMPORAL and no event or forecast time claim.
MARKET_OBSERVATION and CAPTURE retain those existing bases for genuinely observed
market data or source capture metadata; capture is not publication or event time.
PROSPECTIVE and UNRESOLVED cannot remain as general support clauses: preserve a
forecast in its economic term, referenced by materiality_term_indices, or preserve
unresolved information in the existing unresolved fields. Do not invent a time.
Split genuinely mixed event/forecast assertions, preserving every economic fact.
An announcement of a forecast is not realization; late-year, next-quarter or
multi-year expected benefits remain prospective even in a historical document.
Correct timing elsewhere does not cure a false NOT_TEMPORAL summary label.

These are infrastructure consistency checks and review links, not keyword truth
tests. False but mutually consistent declarations still require source review.
No new strategy criterion, numerical threshold, authority or trading eligibility.
'''


class AmountReference(Strict):
    entry_index: StrictInt = Field(ge=0)
    nature: Nature
    reason: StrictStr = Field(min_length=1)


class TermReference(Strict):
    term_index: StrictInt = Field(ge=0)
    core_nature: Nature
    amount_natures: list[AmountReference]
    qualification_scope: StrictStr = Field(min_length=1)


class SummaryTemporalRole(Strict):
    clause_index: StrictInt = Field(ge=0)
    temporal_scope: Literal['OCCURRED', 'PUBLICATION', 'ATEMPORAL', 'MARKET_OBSERVATION', 'CAPTURE', 'PROSPECTIVE', 'UNRESOLVED']
    reason: StrictStr = Field(min_length=1)


class BindingDraft(RoleDraft):
    term_classifications: list[TermReference]
    materiality_term_indices: list[StrictInt]
    materiality_clause_roles: list[SummaryTemporalRole]


def binding_schema(packet, masters):
    schema = BindingDraft.model_json_schema()
    # Preserve inherited source/rule bounds without importing unused v24 types.
    for name, definition in nature_schema(packet, masters)['$defs'].items():
        if name in schema['$defs']:
            schema['$defs'][name] = deepcopy(definition)
    schema['properties']['materiality_term_indices']['items']['minimum'] = 0
    return schema


def prepare_binding_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import authority_texts, ReviewBlocked
    r = prepare_nature_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    content = r['body']['input'][0]['content']
    assert content.endswith('\n' + NATURE_INSTRUCTIONS)
    r['body']['input'][0]['content'] = content[:-len(NATURE_INSTRUCTIONS)] + INSTRUCTIONS
    r['body']['text']['format']['schema'] = binding_schema(packet, authority_texts(packet, masters, now))
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def validate_binding_request(packet, request):
    from research_reviewer import ReviewBlocked
    try:
        if (request['implementation_version'], request['prompt_version']) != VERSIONS: raise ValueError()
        if request['request_id'] != digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=request['body'])): raise ValueError()
        content = request['body']['input'][0]['content']
        if not content.endswith('\n' + INSTRUCTIONS): raise ValueError()
        masters = json.loads(content.split('\nGOVERNING_MASTERS:\n', 1)[1].split('\nCRITERION_REFERENCES:\n', 1)[0])
        if request['body']['text']['format']['schema'] != binding_schema(packet, masters): raise ValueError()
        previous = deepcopy(request)
        previous['implementation_version'], previous['prompt_version'] = PREVIOUS
        previous['body']['input'][0]['content'] = content[:-len(INSTRUCTIONS)] + NATURE_INSTRUCTIONS
        previous['body']['text']['format']['schema'] = nature_schema(packet, masters)
        previous['request_id'] = digest(dict(version=PREVIOUS[0], prompt_version=PREVIOUS[1], body=previous['body']))
        validate_nature_request(packet, previous)
        return masters, previous
    except (KeyError, IndexError, TypeError, ValueError):
        raise ReviewBlocked('BINDING_REQUEST_MISMATCH') from None


def citation_projection(original):
    """v25 references resolve to whole original fields, never to guessed sources."""
    parsed = BindingDraft.model_validate(original)
    terms = original['draft']['economic_inventory']['terms']
    expected = list(range(len(terms)))
    if sorted(x.term_index for x in parsed.term_classifications) != expected:
        raise ValueError('EXACT_TERM_REFERENCE_SET_REQUIRED')
    if sorted(x['term_index'] for x in original['term_assertions']) != expected:
        raise ValueError('EXACT_CORE_ASSERTION_SET_REQUIRED')
    if sorted(parsed.materiality_term_indices) != expected:
        raise ValueError('EXACT_SUMMARY_TERM_SET_REQUIRED')
    assertions = {x['term_index']: x for x in original['term_assertions']}
    projection = deepcopy({k: v for k, v in original.items()
        if k not in ('materiality_term_indices', 'materiality_clause_roles')})
    for row in projection['term_classifications']:
        term = terms[row['term_index']]
        if sorted(x['entry_index'] for x in row['amount_natures']) != list(range(len(term['amounts']['entries']))):
            raise ValueError('EXACT_AMOUNT_REFERENCE_SET_REQUIRED')
        row['core_passages'] = deepcopy(assertions[row['term_index']]['passages'])
        for amount in row['amount_natures']:
            amount['passages'] = deepcopy(term['amounts']['entries'][amount['entry_index']]['passages'])
    validate_natures(projection)
    clauses = original['draft']['research']['materiality_coverage']['support']['clauses']
    if sorted(x.clause_index for x in parsed.materiality_clause_roles) != list(range(len(clauses))):
        raise ValueError('EXACT_SUMMARY_ROLE_SET_REQUIRED')
    bases = dict(OCCURRED='EVENT_OCCURRENCE', PUBLICATION='PUBLICATION', ATEMPORAL='NOT_TEMPORAL',
        MARKET_OBSERVATION='MARKET_OBSERVATION', CAPTURE='CAPTURE')
    for row in parsed.materiality_clause_roles:
        if not row.reason.strip(): raise ValueError('SUMMARY_ROLE_REASON_REQUIRED')
        if row.temporal_scope not in bases:
            raise ValueError('SUMMARY_REQUIRES_ECONOMIC_TERM_OR_UNRESOLVED_FIELD')
        if clauses[row.clause_index]['time_basis'] != bases[row.temporal_scope]:
            raise ValueError('SUMMARY_TEMPORAL_ROLE_MISMATCH')
    return projection


def summary_links(original):
    assertions = {x['term_index']: x for x in original['term_assertions']}
    return [dict(term_index=i, term=deepcopy(original['draft']['economic_inventory']['terms'][i]),
        assertion=deepcopy(assertions[i])) for i in original['materiality_term_indices']]


def binding_checklist(original, request_id):
    items = nature_checklist({k: v for k, v in original.items()
        if k not in ('materiality_term_indices', 'materiality_clause_roles')}, request_id)
    for key in ('materiality_term_indices', 'materiality_clause_roles'):
        value = original[key]
        row = dict(kind='SUMMARY_BINDING', path=[key], original_value=deepcopy(value), value_digest=digest(value),
            question='Do the full summary clauses and referenced complete terms preserve source meaning, timing, qualifiers and uncertainty? Consistent declarations do not prove truth.',
            status='SOURCE_REVIEW_REQUIRED')
        row['item_id'] = digest(dict(request_id=request_id, kind=row['kind'], path=row['path'], value_digest=row['value_digest']))
        items.append(row)
    return items


def binding_report(packet, request, text):
    _, previous = validate_binding_request(packet, request)
    original = json.loads(text)
    projected = citation_projection(original)
    report = nature_report(packet, previous, canonical(projected))
    report.update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1], request_id=request['request_id'],
        original_draft=original, original_response_text=text, draft_digest=digest(original),
        field_items=binding_checklist(original, request['request_id']),
        term_classifications=deepcopy(original['term_classifications']),
        materiality_economic_links=summary_links(original), materiality_clause_roles=deepcopy(original['materiality_clause_roles']),
        citation_binding='WHOLE_ORIGINAL_FIELD_REFERENCES', declared_summary_timing='CHECKED_NOT_SOURCE_TRUTH')
    report['limitations'].append('Summary role checks cannot detect mutually consistent false prose. Linked complete terms and all summary clauses require source review.')
    del report['report_id']; report['report_id'] = digest(report)
    return report


def resolve_binding_draft(packet, request, text):
    _, previous = validate_binding_request(packet, request)
    report = binding_report(packet, request, text)
    result = resolve_nature_draft(packet, previous, canonical(citation_projection(report['original_draft'])))
    binding = result[-1]
    binding['selection_transport']['catalog_scope'] = request['request_id']
    binding['extraction_instructions'].update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1],
        instruction_digest=digest(request['body']['input'][0]['content']), request_id=request['request_id'],
        field_meaning_contract='WHOLE_CITATION_REFERENCES_AND_SUMMARY_TIMING_V1')
    binding['economic_inventory'].update(implementation_version=VERSIONS[0], request_id=request['request_id'])
    binding['explicit_response_contract'] = report
    binding['materiality_economic_links'] = deepcopy(report['materiality_economic_links'])
    return result
