"""Opt-in v24 economic nature consistency; source truth remains unverified."""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field, StrictInt, StrictStr
from evidence_review import Strict, canonical, digest
from research_roles import (VERSIONS as PREVIOUS, RoleDraft, prepare_role_request,
    validate_role_request, role_schema, role_report, role_checklist, resolve_role_draft)

VERSIONS = ('1.23.0-automated-research', 'governed-research-v24')
INSTRUCTIONS = '''
Keep each economic term homogeneous in nature: a demonstrated/reported result,
anticipated future benefit, commitment and obligation are distinct assertions.
Split different natures into separate terms even when they share a percentage,
product, comparison basis or source sentence. Preserve both meanings, all source
qualifiers and all relevant passages. Never drop an expected benefit to make a
reported-result term consistent. An announcement of a forecast is not realization.

A historical demonstrated yield belongs to REPORTED_RESULT; an anticipated
production increase or future benefit belongs to FORECAST. Preserve the same-input
comparison basis wherever applicable without inventing an absolute baseline.
Each term's core assertion and every amounts entry must fit its single nature.
OTHER is for an actually different nature, not a way to hide mixed known natures.
If the source is ambiguous, preserve the ambiguity and unresolved information.

Qualifications apply locally to every term they qualify. Preserve applicable
forecast uncertainty, no-assurance cautions and source limitations in the forecast
term itself. Global cautions and another term's qualifications do not cure a local
scope omission. Do not turn a caution into a prerequisite or invent missing
qualifications. The qualification_scope explains what applies to this particular
term and what remains unknown, consistent with its complete qualifications facet.

The term_classifications schema binds a core nature and passages to each original
term_assertion, plus a nature and matching passages for every amounts entry.
Cover all terms and all amounts entries exactly once, using zero-based indices.
These declarations check consistency only: prose, classifications, complete terms
and local qualifications still need attributed source review. No new strategy
criterion, authority, numerical threshold, handoff or observation eligibility.
'''

Nature = Literal['OBLIGATION','COMMITMENT','REPORTED_RESULT','FORECAST','OTHER']

class AmountNature(Strict):
    entry_index: StrictInt = Field(ge=0)
    nature: Nature
    passages: list[StrictInt] = Field(min_length=1)
    reason: StrictStr = Field(min_length=1)

class TermClassification(Strict):
    term_index: StrictInt = Field(ge=0)
    core_nature: Nature
    core_passages: list[StrictInt]
    amount_natures: list[AmountNature]
    qualification_scope: StrictStr = Field(min_length=1)

class NatureDraft(RoleDraft):
    term_classifications: list[TermClassification]

def nature_schema(packet, masters):
    schema=NatureDraft.model_json_schema()
    schema['$defs'].update(deepcopy(role_schema(packet,masters)['$defs']))
    from research_linked import numbered_passages
    for name,field in [('AmountNature','passages'),('TermClassification','core_passages')]:
        schema['$defs'][name]['properties'][field]['items'].update(minimum=1,maximum=len(numbered_passages(packet)))
    return schema

def prepare_nature_request(packet,masters,model,max_output_tokens,max_input_bytes,now):
    from research_reviewer import authority_texts,ReviewBlocked
    r=prepare_role_request(packet,masters,model,max_output_tokens,max_input_bytes,now)
    r['implementation_version'],r['prompt_version']=VERSIONS
    r['body']['input'][0]['content']+='\n'+INSTRUCTIONS
    r['body']['text']['format']['schema']=nature_schema(packet,authority_texts(packet,masters,now))
    if len(canonical(r['body']).encode())>max_input_bytes:raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id']=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=r['body']))
    return r

def validate_nature_request(packet,request):
    from research_reviewer import ReviewBlocked
    try:
        if (request['implementation_version'],request['prompt_version'])!=VERSIONS:raise ValueError()
        if request['request_id']!=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=request['body'])):raise ValueError()
        content=request['body']['input'][0]['content']
        if not content.endswith('\n'+INSTRUCTIONS):raise ValueError()
        masters=json.loads(content.split('\nGOVERNING_MASTERS:\n',1)[1].split('\nCRITERION_REFERENCES:\n',1)[0])
        if request['body']['text']['format']['schema']!=nature_schema(packet,masters):raise ValueError()
        previous=deepcopy(request)
        previous['implementation_version'],previous['prompt_version']=PREVIOUS
        previous['body']['input'][0]['content']=content[:-len('\n'+INSTRUCTIONS)]
        previous['body']['text']['format']['schema']=role_schema(packet,masters)
        previous['request_id']=digest(dict(version=PREVIOUS[0],prompt_version=PREVIOUS[1],body=previous['body']))
        validate_role_request(packet,previous)
        return masters,previous
    except (KeyError,IndexError,TypeError,ValueError):raise ReviewBlocked('NATURE_REQUEST_BINDING_MISMATCH') from None

def validate_natures(original):
    parsed=NatureDraft.model_validate(original)
    terms=original['draft']['economic_inventory']['terms']
    rows=parsed.term_classifications
    if sorted(x.term_index for x in rows)!=list(range(len(terms))):raise ValueError('EXACT_TERM_NATURE_SET_REQUIRED')
    if sorted(x['term_index'] for x in original['term_assertions'])!=list(range(len(terms))):
        raise ValueError('EXACT_CORE_ASSERTION_SET_REQUIRED')
    assertions={x['term_index']:x for x in original['term_assertions']}
    def same_sources(numbers,expected):
        if len(set(numbers))!=len(numbers) or sorted(numbers)!=sorted(expected):raise ValueError('NATURE_SOURCE_BINDING_MISMATCH')
    for row in rows:
        term=terms[row.term_index]
        if row.core_nature!=term['nature']:raise ValueError('CORE_TERM_NATURE_MISMATCH')
        same_sources(row.core_passages,assertions[row.term_index]['passages'])
        entries=term['amounts']['entries']
        if sorted(x.entry_index for x in row.amount_natures)!=list(range(len(entries))):raise ValueError('EXACT_AMOUNT_NATURE_SET_REQUIRED')
        if not row.qualification_scope.strip():raise ValueError('LOCAL_QUALIFICATION_SCOPE_REQUIRED')
        for entry in row.amount_natures:
            if entry.nature!=term['nature']:raise ValueError('MIXED_ECONOMIC_NATURES_REQUIRE_SEPARATE_TERMS')
            same_sources(entry.passages,entries[entry.entry_index]['passages'])
            if not entry.reason.strip():raise ValueError('NATURE_REASON_REQUIRED')

def nature_checklist(original,request_id):
    projection={k:v for k,v in original.items() if k!='term_classifications'}
    items=role_checklist(projection,request_id)
    def add(kind,path,value):
        row=dict(kind=kind,path=path,original_value=deepcopy(value),value_digest=digest(value),
            question='Does the full source support one economic nature across the complete term/core/amounts, with every applicable local qualification and no lost assertion? Declarations do not prove truth.',status='SOURCE_REVIEW_REQUIRED')
        row['item_id']=digest(dict(request_id=request_id,kind=kind,path=path,value_digest=row['value_digest']))
        items.append(row)
    for i,term in enumerate(original['draft']['economic_inventory']['terms']):
        add('COMPLETE_ECONOMIC_TERM',['draft','economic_inventory','terms',i],term)
    for i,row in enumerate(original['term_classifications']):add('ECONOMIC_NATURE_DECLARATION',['term_classifications',i],row)
    return items

def nature_report(packet,request,text):
    _,previous=validate_nature_request(packet,request)
    original=json.loads(text);validate_natures(original)
    projection={k:v for k,v in original.items() if k!='term_classifications'}
    report=role_report(packet,previous,canonical(projection))
    report.update(implementation_version=VERSIONS[0],prompt_version=VERSIONS[1],request_id=request['request_id'],
        original_draft=original,original_response_text=text,draft_digest=digest(original),
        field_items=nature_checklist(original,request['request_id']),term_classifications=deepcopy(original['term_classifications']),
        declared_nature_consistency='CHECKED_NOT_SOURCE_TRUTH')
    report['limitations'].append('Matching economic nature declarations cannot prove truthful classification or complete local qualifications. Complete terms require source review.')
    del report['report_id'];report['report_id']=digest(report)
    return report

def resolve_nature_draft(packet,request,text):
    _,previous=validate_nature_request(packet,request);report=nature_report(packet,request,text)
    projection={k:v for k,v in report['original_draft'].items() if k!='term_classifications'}
    result=resolve_role_draft(packet,previous,canonical(projection));binding=result[-1]
    binding['selection_transport']['catalog_scope']=request['request_id']
    binding['extraction_instructions'].update(implementation_version=VERSIONS[0],prompt_version=VERSIONS[1],
        instruction_digest=digest(request['body']['input'][0]['content']),request_id=request['request_id'],
        field_meaning_contract='HOMOGENEOUS_ECONOMIC_NATURE_AND_LOCAL_QUALIFICATIONS_V1')
    binding['economic_inventory'].update(implementation_version=VERSIONS[0],request_id=request['request_id'])
    binding['explicit_response_contract']=report
    return result
