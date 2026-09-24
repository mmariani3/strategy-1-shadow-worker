"""v10 typed research subjects; no new instrument or qualification authority."""
from typing import Literal

from evidence_review import Strict, CRITERIA, canonical, digest, reviewer_request
from research_context import ExcerptRef, FixedResolver, context_evidence_message
from research_gaps import (GapDraft, SubstantiveRef, INSTRUCTIONS as GAP_INSTRUCTIONS,
    resolve_gap_draft)
from research_citations import selectable_catalog
from research_facts import TOPICS, SUBSTANTIVE

VERSIONS = ('1.9.0-automated-research', 'governed-research-v10')


class EventSubject(Strict):
    kind: Literal['ISSUER', 'ORGANIZATION', 'ECONOMIC_EVENT', 'UNKNOWN']
    name: str | None
    symbol: str | None
    evidence: list[SubstantiveRef]


class SubjectEvent(Strict):
    subject: EventSubject
    description: str
    relationship: Literal['DIRECT', 'READ_THROUGH', 'UNRELATED', 'UNRESOLVED']
    target_link: Literal['EVIDENCED', 'UNRESOLVED']
    link_rationale: str
    evidence: list[SubstantiveRef]
    link_evidence: list[SubstantiveRef]


class SubjectFact(Strict):
    topic: Literal[TOPICS]
    subject_role: Literal['TARGET', 'EVENT', 'PUBLICATION', 'UNRESOLVED']
    status: Literal['EVIDENCED', 'UNRESOLVED']
    finding: str
    evidence: list[ExcerptRef]


class SubjectDraft(GapDraft):
    selected_event: SubjectEvent
    facts: list[SubjectFact]


INSTRUCTIONS = GAP_INSTRUCTIONS.replace('RESEARCH CONTRACT v9.', 'RESEARCH CONTRACT v10.')
INSTRUCTIONS = INSTRUCTIONS.replace('If no event is established use null subject and UNRESOLVED link.',
    'If no event is established use UNKNOWN subject and UNRESOLVED link.')
INSTRUCTIONS += '''
TYPED EVENT SUBJECT: selected_event.subject contains kind, name, symbol and
substantive evidence. ISSUER has a captured company name and symbol. ORGANIZATION
(for example a central bank) and ECONOMIC_EVENT have a captured name and null
symbol: NEVER invent a ticker for a non-company subject. UNKNOWN has null name,
null symbol and no subject evidence. Known subjects require substantive evidence.
DIRECT requires an ISSUER with the target symbol. READ_THROUGH requires a known
separate subject and evidenced economic linkage when target_link is EVIDENCED.
UNKNOWN cannot establish an evidenced link or evidenced event/timing facts.
Target instrument eligibility remains separate and unchanged: an organization
subject does not turn an ETF/currency trust into an eligible stock.

FACT ROLES replace fact subject_symbol. instrument_identity and document_coverage
use TARGET, catalyst_event and event_timing use EVENT, publication_timing uses
PUBLICATION. UNRESOLVED role is allowed only for an unresolved fact. No publication
clock time can establish the occurrence time of an event. Keep the full supplied
event context, including conditional relief, bounded stays and future intentions.

GAP REVIEW: Before asserting a gap, assess relevant facts already in the captured
text and state their limits. A reported investment plan may have economic
significance without being binding, funded, completed or formally approved.
Those details can change the assessment, but their absence is not a universal
materiality prerequisite. Keep event freshness and corroboration separate from
narrow materiality research. Do not claim prior risk context is absent when the
captured text already explains it. Additional impact can still be unresolved.
These clarifications confer no semantic-review or document-requirement authority.
'''


def subject_schema(packet):
    from research_reviewer import ReviewBlocked
    schema = SubjectDraft.model_json_schema()
    catalog = selectable_catalog(packet)
    substantive = sorted(k for k,v in catalog.items() if v['category'] in SUBSTANTIVE)
    if not substantive: raise ReviewBlocked('NO_SUBSTANTIVE_EVIDENCE')
    schema['$defs']['ExcerptRef']['properties']['excerpt_id']['enum'] = sorted(catalog)
    schema['$defs']['SubstantiveRef']['properties']['excerpt_id']['enum'] = substantive
    schema['$defs']['Target']['properties']['symbol']['enum'] = [packet['symbol']]
    schema['$defs']['Target']['properties']['evidence']['items'] = {'$ref':'#/$defs/SubstantiveRef'}
    for name in ('ContextClaim', 'GapCoverage'):
        schema['$defs'][name]['properties']['subject_symbol']['enum'] = [packet['symbol']]
    def enums(x):
        if isinstance(x,dict):
            if 'enum' in x: yield x['enum']
            for v in x.values(): yield from enums(v)
        elif isinstance(x,list):
            for v in x: yield from enums(v)
    choices=list(enums(schema))
    if sum(map(len,choices))>1000 or any(len(e)>250 and sum(len(v) for v in e if isinstance(v,str))>15000 for e in choices):
        raise ReviewBlocked('CITATION_SCHEMA_LIMIT_EXCEEDED_NO_TRUNCATION')
    return schema


def prepare_subject_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import prepare_request, authority_texts, ReviewBlocked
    r=prepare_request(packet,masters,model,max_output_tokens,max_input_bytes,now)
    r['implementation_version'],r['prompt_version']=VERSIONS
    b=r['body']
    b['input'][0]['content']=(reviewer_request(packet)['instructions']+'\n'+INSTRUCTIONS+
        '\nGOVERNING_MASTERS:\n'+canonical(authority_texts(packet,masters,now))+
        '\nCRITERION_REFERENCES:\n'+canonical(CRITERIA))
    b['input'][-1]=context_evidence_message(packet)
    b['text']['format']['schema']=subject_schema(packet)
    if len(canonical(b).encode())>max_input_bytes: raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id']=digest(dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=b))
    return r


def validate_subject_request(packet,r):
    from research_reviewer import ReviewBlocked
    if (r['packet_id']!=packet['packet_id'] or r['body']['input'][-1]!=context_evidence_message(packet)
        or r['body']['text']['format']!=dict(type='json_schema',name='research_assessment',strict=True,schema=subject_schema(packet))):
        raise ReviewBlocked('SUBJECT_REQUEST_BINDING_MISMATCH')


def resolve_subject_draft(packet,text):
    from research_reviewer import ReviewBlocked
    d=SubjectDraft.model_validate_json(text);e=d.selected_event;s=e.subject
    known=s.kind!='UNKNOWN';resolver=FixedResolver(packet)
    rows=resolver.resolve(s.evidence)
    if any(r['category'] not in SUBSTANTIVE for r in rows): raise ReviewBlocked('SUBJECT_SUBSTANTIVE_EVIDENCE_REQUIRED')
    if known and (not s.name or not rows): raise ReviewBlocked('NAMED_SUBJECT_EVIDENCE_REQUIRED')
    if s.kind=='ISSUER' and (not s.symbol or s.symbol.startswith('internal-subject:')):
        raise ReviewBlocked('ISSUER_SYMBOL_REQUIRED')
    if s.kind!='ISSUER' and s.symbol is not None: raise ReviewBlocked('NONISSUER_SYMBOL_FORBIDDEN')
    if not known and (s.name is not None or rows): raise ReviewBlocked('UNKNOWN_SUBJECT_CONFLICT')
    if e.relationship=='DIRECT' and (s.kind!='ISSUER' or s.symbol!=d.target.symbol):
        raise ReviewBlocked('DIRECT_EVENT_TARGET_MISMATCH')
    if e.relationship=='READ_THROUGH' and (not known or s.symbol==d.target.symbol):
        raise ReviewBlocked('READ_THROUGH_SUBJECT_REQUIRED')
    if e.target_link=='EVIDENCED' and not known: raise ReviewBlocked('EVENT_SUBJECT_REQUIRED')
    roles={'instrument_identity':'TARGET','catalyst_event':'EVENT','event_timing':'EVENT',
        'publication_timing':'PUBLICATION','document_coverage':'TARGET'}
    for f in d.facts:
        if f.subject_role!=roles[f.topic] and not (f.status=='UNRESOLVED' and f.subject_role=='UNRESOLVED'):
            raise ReviewBlocked('FACT_ROLE_MISMATCH')
        if f.status=='EVIDENCED' and f.subject_role=='EVENT' and not known:
            raise ReviewBlocked('FACT_SUBJECT_UNRESOLVED')

    # Host-only compatibility key for unchanged v9 validation. It is never a
    # security identifier and is removed from every persisted subject field.
    subject_id=digest(dict(packet_id=packet['packet_id'],subject=s.model_dump())) if known else None
    internal=s.symbol if s.kind=='ISSUER' else 'internal-subject:'+subject_id if known else None
    converted=d.model_dump();converted['selected_event'].pop('subject')
    converted['selected_event']['subject_symbol']=internal
    for f in converted['facts']:
        role=f.pop('subject_role');f['subject_symbol']=d.target.symbol if role=='TARGET' else internal if role=='EVENT' else None
    resolved,facts,record,audit,binding=resolve_gap_draft(packet,canonical(converted))
    event_id=digest(dict(packet_id=packet['packet_id'],selected_event=e.model_dump()))
    for f,original in zip(facts,d.facts):
        f.pop('subject_symbol',None)
        f.update(subject_role=original.subject_role,event_subject_id=subject_id if original.subject_role=='EVENT' else None,
            target_symbol=d.target.symbol if original.subject_role=='TARGET' else None,selected_event_id=event_id)
    record['selected_event_id']=event_id
    gap_ids=[digest(dict(packet_id=packet['packet_id'],selected_event_id=event_id,gap=g.model_dump())) for g in d.materiality_coverage.evidence_gaps]
    for g,gid in zip(record['evidence_gaps'],gap_ids):g['gap_id']=gid
    for f in record['document_followups']:f['gap_id']=None if f['gap_index'] is None else gap_ids[f['gap_index']]
    binding.update(selected_event=e.model_dump(),selected_event_id=event_id,event_subject_id=subject_id,subject_citations=rows)
    for c in binding['claims']:c['selected_event_id']=event_id
    return resolved,facts,record,audit,binding
