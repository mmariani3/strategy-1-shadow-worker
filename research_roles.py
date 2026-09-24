"""Opt-in v23 declared-role consistency. Source meaning still needs review."""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field, StrictInt, StrictStr
from evidence_review import Strict, canonical, digest
from research_fields import (VERSIONS as PREVIOUS, prepare_field_request,
    validate_field_request, field_report, field_checklist, resolve_field_draft)
from research_explicit_contract import ExplicitDraft, explicit_schema

VERSIONS = ('1.22.0-automated-research', 'governed-research-v23')
INSTRUCTIONS = '''
v23 retains every v22 field and adds required meaning_contract with conditions,
contexts and followups arrays. Each array covers its referenced entries exactly
once with zero-based indices. No new trading criteria or authority are created.

For each economic term conditions.entries entry, declare term_index, entry_index,
role, prerequisite, dependent_outcome, temporal_scope, passages and reason.
DEPENDENCY means the source explicitly states what must hold for what outcome.
Name both sides and cite the same complete source passages as the condition.
An already-granted approval that is credited with future benefits is causal
attribution, not a realization prerequisite. Classifying a forecast or warning
that results may differ is also not a condition. CAUSAL_ATTRIBUTION,
FORECAST_CLASSIFICATION, GENERIC_CAUTION and UNRESOLVED roles cannot remain in a
recorded condition. Move that information to core assertions, qualifications or
appropriate context; keep an undisclosed condition UNRESOLVED with empty entries.
Do not invent a prerequisite to pass the schema. Preserve genuine disclosed
conditions, including contingencies, exceptions and already-completed conditions.
For genuine conditions, temporal_scope OCCURRED requires EVENT_OCCURRENCE,
PROSPECTIVE requires FORECAST_PERIOD, ATEMPORAL requires NOT_TEMPORAL. A statement
about future realization is not occurred merely because its announcement occurred.

For each research.context_notes entry, declare context_index, role, passages and
reason. Roles map to kinds: CONDITION -> CONDITIONALITY, FORECAST -> EXPECTATIONS,
CAUTION or CAUSAL_LIMIT -> CAUSAL_LIMIT, OBSERVED_COUNTEREVIDENCE -> COUNTEREVIDENCE,
PROVENANCE -> PROVENANCE, OTHER_EVENT -> OTHER_EVENT. REPORTED_RESULT belongs in
the existing evidenced facts and/or economic inventory with REPORTED_RESULT;
do not duplicate it as an EXPECTATIONS note. Preserve its full source content
there. UNRESOLVED cannot justify a context classification. Generic no-assurance
language is CAUTION, not observed counter-results. An expectation can incorporate
reported evidence only when the entire note clearly expresses the expectation;
do not use it to disguise a standalone reported result.

For each materiality_coverage.document_followups entry, declare followup_index,
verification_policy GOVERNING_MASTERS_UNCHANGED and scope_note. Explain that the
particular extra document may be optional for this narrow extraction, while all
governing catalyst/watchlist verification requirements remain applicable. Never
waive verification or imply that an optional followup grants trading eligibility.

These declarations enable consistency checks, not semantic self-certification.
Every declaration, referenced field and temporal clause still requires source
review. Never discard an economic fact to satisfy a role check. No handoff.
'''


class ConditionRole(Strict):
    term_index: StrictInt = Field(ge=0)
    entry_index: StrictInt = Field(ge=0)
    role: Literal['DEPENDENCY','CAUSAL_ATTRIBUTION','FORECAST_CLASSIFICATION','GENERIC_CAUTION','UNRESOLVED']
    prerequisite: StrictStr
    dependent_outcome: StrictStr
    temporal_scope: Literal['OCCURRED','PROSPECTIVE','ATEMPORAL']
    passages: list[StrictInt] = Field(min_length=1)
    reason: StrictStr = Field(min_length=1)


class ContextRole(Strict):
    context_index: StrictInt = Field(ge=0)
    role: Literal['CONDITION','FORECAST','CAUTION','CAUSAL_LIMIT','OBSERVED_COUNTEREVIDENCE','PROVENANCE','OTHER_EVENT','REPORTED_RESULT','UNRESOLVED']
    passages: list[StrictInt] = Field(min_length=1)
    reason: StrictStr = Field(min_length=1)


class FollowupRole(Strict):
    followup_index: StrictInt = Field(ge=0)
    verification_policy: Literal['GOVERNING_MASTERS_UNCHANGED']
    scope_note: StrictStr = Field(min_length=1)


class MeaningContract(Strict):
    conditions: list[ConditionRole]
    contexts: list[ContextRole]
    followups: list[FollowupRole]


class RoleDraft(ExplicitDraft):
    meaning_contract: MeaningContract


def role_schema(packet, masters):
    base = explicit_schema(packet, masters)
    schema = RoleDraft.model_json_schema()
    schema['$defs'].update(deepcopy(base['$defs']))
    from research_linked import numbered_passages
    for name in ('ConditionRole','ContextRole'):
        schema['$defs'][name]['properties']['passages']['items'].update(
            minimum=1, maximum=len(numbered_passages(packet)))
    return schema


def prepare_role_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import authority_texts, ReviewBlocked
    r = prepare_field_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0]['content'] += '\n'+INSTRUCTIONS
    r['body']['text']['format']['schema'] = role_schema(packet, authority_texts(packet, masters, now))
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=r['body']))
    return r


def validate_role_request(packet, request):
    from research_reviewer import ReviewBlocked
    try:
        if (request['implementation_version'],request['prompt_version']) != VERSIONS:
            raise ValueError()
        if request['request_id'] != digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=request['body'])):
            raise ValueError()
        if type(request['body']['max_output_tokens']) is not int or request['body']['max_output_tokens'] <= 0:
            raise ValueError()
        content = request['body']['input'][0]['content']
        if not content.endswith('\n'+INSTRUCTIONS): raise ValueError()
        masters = json.loads(content.split('\nGOVERNING_MASTERS:\n',1)[1].split('\nCRITERION_REFERENCES:\n',1)[0])
        if request['body']['text']['format']['schema'] != role_schema(packet,masters): raise ValueError()
        previous = deepcopy(request)
        previous['implementation_version'],previous['prompt_version'] = PREVIOUS
        previous['body']['input'][0]['content'] = content[:-len('\n'+INSTRUCTIONS)]
        previous['body']['text']['format']['schema'] = explicit_schema(packet,masters)
        previous['request_id'] = digest(dict(version=PREVIOUS[0],prompt_version=PREVIOUS[1],body=previous['body']))
        validate_field_request(packet,previous)
        return masters,previous
    except (KeyError,IndexError,TypeError,ValueError):
        raise ReviewBlocked('ROLE_REQUEST_BINDING_MISMATCH') from None


def validate_roles(original):
    """Check declared relationships only; never infer prose truth from keywords."""
    parsed = RoleDraft.model_validate(original)
    c = parsed.meaning_contract
    terms = original['draft']['economic_inventory']['terms']
    expected = [(i,j) for i,t in enumerate(terms) for j,_ in enumerate(t['conditions']['entries'])]
    if sorted((x.term_index,x.entry_index) for x in c.conditions) != expected:
        raise ValueError('EXACT_CONDITION_ROLE_SET_REQUIRED')
    def sources(role, entry):
        if len(set(role.passages)) != len(role.passages) or sorted(role.passages) != sorted(entry['passages']):
            raise ValueError('ROLE_SOURCE_BINDING_MISMATCH')
        if not role.reason.strip(): raise ValueError('ROLE_REASON_REQUIRED')
    for role in c.conditions:
        entry = terms[role.term_index]['conditions']['entries'][role.entry_index]
        sources(role,entry)
        if role.role != 'DEPENDENCY': raise ValueError('NONDEPENDENCY_RECORDED_AS_CONDITION')
        if not role.prerequisite.strip() or not role.dependent_outcome.strip():
            raise ValueError('EXPLICIT_DEPENDENCY_REQUIRED')
        basis = dict(OCCURRED='EVENT_OCCURRENCE',PROSPECTIVE='FORECAST_PERIOD',ATEMPORAL='NOT_TEMPORAL')
        if entry['time_basis'] != basis[role.temporal_scope]: raise ValueError('CONDITION_TEMPORAL_ROLE_MISMATCH')
    notes = original['draft']['research']['context_notes']
    if sorted(x.context_index for x in c.contexts) != list(range(len(notes))):
        raise ValueError('EXACT_CONTEXT_ROLE_SET_REQUIRED')
    kinds = dict(CONDITION='CONDITIONALITY',FORECAST='EXPECTATIONS',CAUTION='CAUSAL_LIMIT',
        CAUSAL_LIMIT='CAUSAL_LIMIT',OBSERVED_COUNTEREVIDENCE='COUNTEREVIDENCE',PROVENANCE='PROVENANCE',OTHER_EVENT='OTHER_EVENT')
    for role in c.contexts:
        note = notes[role.context_index]; sources(role,note)
        if role.role == 'REPORTED_RESULT': raise ValueError('REPORTED_RESULT_REQUIRES_FACT_OR_ECONOMIC_TERM')
        if kinds.get(role.role) != note['kind']: raise ValueError('CONTEXT_ROLE_MISMATCH')
    followups = original['draft']['research']['materiality_coverage']['document_followups']
    if sorted(x.followup_index for x in c.followups) != list(range(len(followups))):
        raise ValueError('EXACT_FOLLOWUP_ROLE_SET_REQUIRED')
    if any(not x.scope_note.strip() for x in c.followups): raise ValueError('FOLLOWUP_SCOPE_REQUIRED')


def role_checklist(original, request_id):
    items = field_checklist(original,request_id)
    def add(kind,path,value):
        row = dict(kind=kind,path=path,original_value=deepcopy(value),value_digest=digest(value),
            question='Do the source and the full referenced field support this role, timing and authority scope? Matching declarations do not prove meaning.',status='SOURCE_REVIEW_REQUIRED')
        row['item_id'] = digest(dict(request_id=request_id,kind=kind,path=path,value_digest=row['value_digest']))
        items.append(row)
    for key,values in original['meaning_contract'].items():
        for i,v in enumerate(values): add('ROLE_DECLARATION',['meaning_contract',key,i],v)
    research=original['draft']['research']
    for i,v in enumerate(research['context_notes']):add('CONTEXT_MEANING',['draft','research','context_notes',i],v)
    for i,v in enumerate(research['materiality_coverage']['document_followups']):
        add('FOLLOWUP_AUTHORITY',['draft','research','materiality_coverage','document_followups',i],v)
    return items


def role_report(packet,request,text):
    _,previous=validate_role_request(packet,request)
    original=json.loads(text);validate_roles(original)
    projection={k:deepcopy(v) for k,v in original.items() if k!='meaning_contract'}
    report=field_report(packet,previous,canonical(projection))
    report.update(implementation_version=VERSIONS[0],prompt_version=VERSIONS[1],request_id=request['request_id'],
        original_draft=original,original_response_text=text,draft_digest=digest(original),
        field_items=role_checklist(original,request['request_id']),meaning_contract=deepcopy(original['meaning_contract']),
        declared_role_consistency='CHECKED_NOT_SOURCE_TRUTH')
    report['limitations'].append('Declared roles can agree while still misrepresenting the source. All role and field items require attributed source review.')
    del report['report_id'];report['report_id']=digest(report)
    return report


def resolve_role_draft(packet,request,text):
    _,previous=validate_role_request(packet,request);report=role_report(packet,request,text)
    original=report['original_draft'];projection={k:v for k,v in original.items() if k!='meaning_contract'}
    result=resolve_field_draft(packet,previous,canonical(projection));binding=result[-1]
    binding['selection_transport']['catalog_scope']=request['request_id']
    binding['extraction_instructions'].update(implementation_version=VERSIONS[0],prompt_version=VERSIONS[1],
        instruction_digest=digest(request['body']['input'][0]['content']),request_id=request['request_id'],
        field_meaning_contract='DECLARED_CONDITION_CONTEXT_AND_FOLLOWUP_ROLES_V1')
    binding['economic_inventory'].update(implementation_version=VERSIONS[0],request_id=request['request_id'])
    binding['explicit_response_contract']=report
    return result
