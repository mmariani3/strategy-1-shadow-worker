"""v18 schema-constrained fact roles and event support; v17 stays frozen."""
from copy import deepcopy
import json
from typing import Literal, Union
from pydantic import Field, create_model
from evidence_review import Strict, canonical, digest
from research_linked import (LinkedFact, LinkedSubject, LinkedEvent, LinkedGap,
    InlineSupport, NumberedClause, numbered_passages)
from research_scope import (ScopeDraft, ScopeResearch, ScopeCoverage, scope_schema,
    scope_developer, prepare_scope_request, validate_scope_request, resolve_scope_draft,
    VERSIONS as PARSER_VERSIONS)

VERSIONS = ('1.17.0-automated-research', 'governed-research-v18')
ROLES = {'instrument_identity': 'TARGET', 'document_coverage': 'TARGET',
    'catalyst_event': 'EVENT', 'event_timing': 'EVENT', 'publication_timing': 'PUBLICATION'}


def replace_fields(name, base, replacements):
    fields = {k: (f.annotation, deepcopy(f)) for k, f in base.model_fields.items()}
    fields.update(replacements)
    return create_model(name, __base__=Strict, **fields)


SelectedSupport = replace_fields('TypedSelectedSupport', InlineSupport,
    {'event_relation': (Literal['SELECTED_EVENT'], ...)})
EventClause = replace_fields('TypedEventClause', NumberedClause,
    {'time_basis': (Literal['EVENT_OCCURRENCE'], ...)})
PublicationClause = replace_fields('TypedPublicationClause', NumberedClause,
    {'time_basis': (Literal['PUBLICATION'], ...)})
EventTimeSupport = replace_fields('TypedEventTimeSupport', SelectedSupport,
    {'clauses': (list[EventClause], ...)})
PublicationSupport = replace_fields('TypedPublicationSupport', InlineSupport,
    {'clauses': (list[PublicationClause], ...)})
FACTS = tuple(replace_fields('TypedFact_' + topic, LinkedFact, {
    'topic': (Literal[topic], ...), 'subject_role': (Literal[role], ...),
    'support': ((EventTimeSupport if topic == 'event_timing' else
                 PublicationSupport if topic == 'publication_timing' else
                 SelectedSupport if topic == 'catalyst_event' else InlineSupport), ...)
}) for topic, role in ROLES.items())
TypedSubject = replace_fields('TypedSubject', LinkedSubject, {'support': (SelectedSupport, ...)})
TypedEvent = replace_fields('TypedEvent', LinkedEvent, {
    'subject': (TypedSubject, ...), 'support': (SelectedSupport, ...),
    'link_support': (SelectedSupport, ...)})
TypedGap = replace_fields('TypedGap', LinkedGap, {'support': (SelectedSupport, ...)})
TypedCoverage = replace_fields('TypedCoverage', ScopeCoverage, {'evidence_gaps': (list[TypedGap], ...)})
TypedResearch = replace_fields('TypedResearch', ScopeResearch, {
    'facts': (list[Union[FACTS]], Field(min_length=5, max_length=5)),
    'selected_event': (TypedEvent, ...), 'materiality_coverage': (TypedCoverage, ...)})
TypedDraft = replace_fields('TypedDraft', ScopeDraft, {'research': (TypedResearch, ...)})

INSTRUCTIONS = '''
RESEARCH CONTRACT v18 retains the v17 envelope and single root scope.
Fact subject_role is a fixed topic label, not an evidence-confidence judgment:
instrument_identity/document_coverage TARGET; catalyst_event/event_timing EVENT;
publication_timing PUBLICATION. Keep the same role even when status is UNRESOLVED.
Return each of the five topics once. Use status UNRESOLVED and explain unavailable
evidence; a fixed role never makes a fact evidenced. Event-time clauses use
EVENT_OCCURRENCE only; publication-time clauses use PUBLICATION only.
The selected event, its subject and link, catalyst/event-time facts, and evidence
gaps use SELECTED_EVENT support, including empty clauses for unavailable evidence.
Other-event and contextual material still belong in their separate context fields.
These schema restrictions express existing infrastructure relationships only.
They do not verify meaning, impose a new strategy prerequisite or grant approval.
Read every source, including dates, qualifications and cost/risk continuations.
An offline location report can expose unselected passages and narrative-only
selections; it cannot decide their materiality or certify a complete summary.
'''


def typed_developer(packet, masters):
    out = scope_developer(packet, masters)
    out['content'] = out['content'].replace('UNRESOLVED role is only for unresolved facts.',
        'In v18 role is fixed by topic; unavailable facts use status UNRESOLVED.')
    out['content'] += '\n' + INSTRUCTIONS
    return out


def typed_schema(packet, masters):
    schema = TypedDraft.model_json_schema()
    for name, definition in scope_schema(packet, masters)['$defs'].items():
        if name in schema['$defs']: schema['$defs'][name] = deepcopy(definition)
    schema['$defs']['TypedCoverage']['properties']['subject_symbol']['enum'] = [packet['symbol']]
    for name in ('TypedEventClause', 'TypedPublicationClause'):
        schema['$defs'][name]['properties']['passages']['items'].update(
            minimum=1, maximum=len(numbered_passages(packet)))
    return schema


def prepare_typed_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import authority_texts, ReviewBlocked
    r = prepare_scope_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    m = authority_texts(packet, masters, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0] = typed_developer(packet, m)
    r['body']['text']['format']['schema'] = typed_schema(packet, m)
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def parser_request(packet, request, masters):
    r = deepcopy(request)
    r['implementation_version'], r['prompt_version'] = PARSER_VERSIONS
    r['body']['input'][0] = scope_developer(packet, masters)
    r['body']['text']['format']['schema'] = scope_schema(packet, masters)
    r['request_id'] = digest(dict(version=PARSER_VERSIONS[0], prompt_version=PARSER_VERSIONS[1], body=r['body']))
    return r


def validate_typed_request(packet, request):
    from research_reviewer import ReviewBlocked
    try:
        if ((request['implementation_version'], request['prompt_version']) != VERSIONS
                or request['packet_id'] != packet['packet_id']
                or request['request_id'] != digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=request['body']))):
            raise ValueError()
        m = json.loads(request['body']['input'][0]['content'].split('\nGOVERNING_MASTERS:\n', 1)[1].split('\nCRITERION_REFERENCES:\n', 1)[0])
        internal = parser_request(packet, request, m)
        validate_scope_request(packet, internal)
        if (request['body']['input'] != [typed_developer(packet, m), internal['body']['input'][1]]
                or request['body']['text']['format'] != dict(type='json_schema', name='research_assessment', strict=True, schema=typed_schema(packet, m))):
            raise ValueError()
    except (KeyError, IndexError, TypeError, ValueError):
        raise ReviewBlocked('TYPED_REQUEST_BINDING_MISMATCH') from None
    return m


def resolve_typed_draft(packet, request, text):
    m = validate_typed_request(packet, request)
    draft = json.loads(text)
    TypedDraft.model_validate(draft)  # Validate original; never rewrite provider choices.
    if sorted(f['topic'] for f in draft['research']['facts']) != sorted(ROLES):
        raise ValueError('TYPED_FACT_SET_MISMATCH')
    result = resolve_scope_draft(packet, parser_request(packet, request, m), text)
    binding = result[-1]
    binding['selection_transport']['catalog_scope'] = request['request_id']
    binding['extraction_instructions'].update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1],
        instruction_digest=digest(INSTRUCTIONS), request_id=request['request_id'],
        field_contract='TOPIC_ROLES_AND_SELECTED_EVENT_SUPPORT_V1')
    binding['economic_inventory'].update(implementation_version=VERSIONS[0], request_id=request['request_id'])
    return result
