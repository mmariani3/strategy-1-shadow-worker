"""Opt-in v26 source coverage and lossless qualitative economic source links."""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field, StrictInt, StrictStr
from evidence_review import Strict, canonical, digest
from research_facts import SUBSTANTIVE
from research_linked import numbered_passages
from research_binding import (VERSIONS as PREVIOUS, BindingDraft, binding_schema,
    prepare_binding_request, validate_binding_request, citation_projection,
    binding_report, binding_checklist, resolve_binding_draft)

VERSIONS = ('1.25.0-automated-research', 'governed-research-v26')
INSTRUCTIONS = '''
v26 QUALITATIVE ECONOMIC COMPLETENESS: Read the entire source, including headlines
and qualifying continuations. Preserve each substantive economic assertion in the
selected event scope, including qualitative direction, magnitude and scope even
when no numerical amount is disclosed. A topic name, broad benefit label, or list
of topics in a forward-looking warning is not the underlying economic assertion.
Unknown numbers do not erase disclosed qualitative effects. Do not turn a
forecast into a realized result or use headline tense to override local caution.

Supply economic_source_coverage as groups of numbered substantive passages
(category DOCUMENT_TEXT or NEWS_TEXT). Cover each such number exactly once across
all groups, even if it is background or outside the selected scope. Do not include
metadata. Each group has passages, role, term_indices and a specific reason.
CORE means a substantive economic assertion in the selected scope; identify every
affected economic term. QUALIFICATION means only locally relevant qualifications
or dependencies; identify the affected terms. CONTEXT and OUT_OF_SCOPE explain
why the passage supplies no selected economic core and use no term indices.
UNRESOLVED preserves an uncertain classification without claiming completeness;
use no term indices and do not declare SUFFICIENT_FOR_RESEARCH.

Read fragments together: punctuation and chunk boundaries do not establish atomic
meaning. A passage containing both a core assertion and caution belongs to CORE;
retain all needed continuations, timing, conditions and qualifications in its
complete term as before. Every recorded term core needs at least one CORE group.
If the core is unavailable, retain its UNRESOLVED assertion rather than inventing
one. Preserve distinct qualitative effects in term_assertions, not only in labels
or caution fields. Do not misclassify a selected economic claim as background
merely because it is qualitative, promotional, unquantified or forward-looking.

The host retains each declared CORE passage verbatim alongside its complete terms
and in their materiality links. These are attributed source claims, not verified
outcomes. No keywords identify economic truth. A false scope classification or
incomplete interpretation can still pass structural checks; all coverage groups,
including exclusions, require source review. No trading eligibility is granted.
'''


class SourceCoverage(Strict):
    passages: list[StrictInt] = Field(min_length=1)
    role: Literal['CORE', 'QUALIFICATION', 'CONTEXT', 'OUT_OF_SCOPE', 'UNRESOLVED']
    term_indices: list[StrictInt]
    reason: StrictStr = Field(min_length=1)


class CompletenessDraft(BindingDraft):
    economic_source_coverage: list[SourceCoverage]


def completeness_schema(packet, masters):
    schema = CompletenessDraft.model_json_schema()
    schema['$defs'].update(deepcopy(binding_schema(packet, masters)['$defs']))
    schema['$defs']['SourceCoverage']['properties']['passages']['items'].update(
        minimum=1, maximum=len(numbered_passages(packet)))
    schema['$defs']['SourceCoverage']['properties']['term_indices']['items']['minimum'] = 0
    schema['properties']['materiality_term_indices']['items']['minimum'] = 0
    return schema


def prepare_completeness_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import authority_texts, ReviewBlocked
    r = prepare_binding_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0]['content'] += '\n' + INSTRUCTIONS
    r['body']['text']['format']['schema'] = completeness_schema(packet, authority_texts(packet, masters, now))
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def validate_completeness_request(packet, request):
    from research_reviewer import ReviewBlocked
    try:
        if (request['implementation_version'], request['prompt_version']) != VERSIONS: raise ValueError()
        if request['request_id'] != digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=request['body'])): raise ValueError()
        content = request['body']['input'][0]['content']
        if not content.endswith('\n' + INSTRUCTIONS): raise ValueError()
        masters = json.loads(content.split('\nGOVERNING_MASTERS:\n', 1)[1].split('\nCRITERION_REFERENCES:\n', 1)[0])
        if request['body']['text']['format']['schema'] != completeness_schema(packet, masters): raise ValueError()
        previous = deepcopy(request)
        previous['implementation_version'], previous['prompt_version'] = PREVIOUS
        previous['body']['input'][0]['content'] = content[:-len('\n' + INSTRUCTIONS)]
        previous['body']['text']['format']['schema'] = binding_schema(packet, masters)
        previous['request_id'] = digest(dict(version=PREVIOUS[0], prompt_version=PREVIOUS[1], body=previous['body']))
        validate_binding_request(packet, previous)
        return masters, previous
    except (KeyError, IndexError, TypeError, ValueError):
        raise ReviewBlocked('COMPLETENESS_REQUEST_MISMATCH') from None


def coverage_projection(packet, original):
    parsed = CompletenessDraft.model_validate(original)
    projected = deepcopy({k: v for k, v in original.items() if k != 'economic_source_coverage'})
    citation_projection(projected)
    catalog = numbered_passages(packet)
    expected = {n for n, row in catalog.items() if row['category'] in SUBSTANTIVE}
    supplied = [n for group in parsed.economic_source_coverage for n in group.passages]
    if len(supplied) != len(set(supplied)) or set(supplied) != expected:
        raise ValueError('EXACT_SUBSTANTIVE_PASSAGE_COVERAGE_REQUIRED')
    terms = original['draft']['economic_inventory']['terms']
    assertions = {a['term_index']: a for a in original['term_assertions']}
    recorded = {i for i, a in assertions.items() if a['status'] == 'RECORDED'}
    covered = set()
    for group in parsed.economic_source_coverage:
        if not group.reason.strip(): raise ValueError('SOURCE_COVERAGE_REASON_REQUIRED')
        indices = group.term_indices
        if len(indices) != len(set(indices)) or any(i < 0 or i >= len(terms) for i in indices):
            raise ValueError('INVALID_SOURCE_COVERAGE_TERM_REFERENCE')
        if group.role in ('CORE', 'QUALIFICATION'):
            if not indices: raise ValueError('SOURCE_COVERAGE_TERM_REQUIRED')
        elif indices: raise ValueError('NON_ECONOMIC_GROUP_HAS_TERM_REFERENCE')
        if group.role == 'CORE':
            if not set(indices) <= recorded: raise ValueError('CORE_REQUIRES_RECORDED_ASSERTION')
            covered.update(indices)
        if group.role == 'UNRESOLVED' and original['draft']['research']['materiality_coverage']['status'] == 'SUFFICIENT_FOR_RESEARCH':
            raise ValueError('UNRESOLVED_SOURCE_COVERAGE_NOT_SUFFICIENT')
    if covered != recorded: raise ValueError('RECORDED_CORE_SOURCE_COVERAGE_REQUIRED')
    return projected


def core_source_links(packet, original):
    catalog = numbered_passages(packet)
    # Preserve complete occurrence-specific rows, not model paraphrases or keywords.
    return [dict(coverage_index=i, term_indices=deepcopy(group['term_indices']),
        source_passages=[dict(number=n, **deepcopy(catalog[n])) for n in group['passages']],
        attribution='SOURCE_CLAIM_NOT_VERIFIED_OUTCOME')
        for i, group in enumerate(original['economic_source_coverage']) if group['role'] == 'CORE']


def completeness_checklist(original, request_id):
    items = binding_checklist({k: v for k, v in original.items() if k != 'economic_source_coverage'}, request_id)
    for i, value in enumerate(original['economic_source_coverage']):
        path = ['economic_source_coverage', i]
        row = dict(kind='ECONOMIC_SOURCE_COVERAGE', path=path, original_value=deepcopy(value), value_digest=digest(value),
            question='Does this classification preserve every selected qualitative economic effect and its scope, magnitude, timing and uncertainty? Check full source continuations, term assertions and every exclusion; labels and caution-topic lists are not core assertions.',
            status='SOURCE_REVIEW_REQUIRED')
        row['item_id'] = digest(dict(request_id=request_id, kind=row['kind'], path=path, value_digest=row['value_digest']))
        items.append(row)
    return items


def completeness_report(packet, request, text):
    _, previous = validate_completeness_request(packet, request)
    original = json.loads(text)
    report = binding_report(packet, previous, canonical(coverage_projection(packet, original)))
    links = core_source_links(packet, original)
    for term in report['materiality_economic_links']:
        term['core_source_links'] = deepcopy([x for x in links if term['term_index'] in x['term_indices']])
    report.update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1], request_id=request['request_id'],
        original_draft=original, original_response_text=text, draft_digest=digest(original),
        field_items=completeness_checklist(original, request['request_id']), economic_core_source_links=links,
        source_coverage='EXACT_PASSAGE_ACCOUNTING_NOT_SEMANTIC_COMPLETENESS')
    report['limitations'].append('Exact passage accounting cannot detect false scope classifications or incomplete paraphrases. Verbatim core links preserve declared evidence but do not establish completeness, source truth or qualification.')
    del report['report_id']; report['report_id'] = digest(report)
    return report


def resolve_completeness_draft(packet, request, text):
    _, previous = validate_completeness_request(packet, request)
    report = completeness_report(packet, request, text)
    result = resolve_binding_draft(packet, previous, canonical(coverage_projection(packet, report['original_draft'])))
    binding = result[-1]
    binding['selection_transport']['catalog_scope'] = request['request_id']
    binding['extraction_instructions'].update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1],
        instruction_digest=digest(request['body']['input'][0]['content']), request_id=request['request_id'],
        field_meaning_contract='ECONOMIC_SOURCE_COVERAGE_V1')
    binding['economic_inventory'].update(implementation_version=VERSIONS[0], request_id=request['request_id'])
    binding['explicit_response_contract'] = report
    binding['materiality_economic_links'] = deepcopy(report['materiality_economic_links'])
    binding['economic_core_source_links'] = deepcopy(report['economic_core_source_links'])
    return result
