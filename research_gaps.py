"""v9 research gaps and nonbinding follow-ups; historical v8 stays immutable.

This adapter cannot adjudicate a contradictory same-event outcome or establish
that a document is required by strategy. Model prose still needs semantic review.
"""
from typing import Literal
from pydantic import Field, StrictInt

from evidence_review import Strict, CRITERIA, canonical, digest, reviewer_request
from research_context import (ContextDraft, ExcerptRef, FixedResolver,
    context_evidence_message, resolve_context_draft, INSTRUCTIONS as CONTEXT_INSTRUCTIONS)
from research_citations import selectable_catalog
from research_facts import SUBSTANTIVE

VERSIONS = ('1.8.0-automated-research', 'governed-research-v9')
FAILURE_CAPABILITY = 'UNAVAILABLE_NO_APPROVED_CONTRADICTION_ADAPTER'
DOCUMENT_AUTHORITY = 'PROPOSAL_ONLY_NOT_AN_APPROVED_REQUIREMENT'


class SubstantiveRef(ExcerptRef):
    pass


class EvidenceGap(Strict):
    missing_fact: str = Field(min_length=1)
    why_material: str = Field(min_length=1)
    captured_evidence_limit: str = Field(min_length=1)
    evidence: list[SubstantiveRef]


class DocumentFollowup(Strict):
    document: str = Field(min_length=1)
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    gap_index: StrictInt | None
    evidence: list[SubstantiveRef]


class GapCoverage(Strict):
    subject_symbol: str
    status: Literal['SUFFICIENT_FOR_RESEARCH', 'INCOMPLETE', 'UNRESOLVED']
    assessment_scope: str
    evidence_gaps: list[EvidenceGap]
    document_followups: list[DocumentFollowup]
    rationale: str
    evidence: list[SubstantiveRef]


class GapDraft(ContextDraft):
    materiality_coverage: GapCoverage
    verification_basis: Literal['UNRESOLVED', 'MISSING_CORROBORATION', 'SHARED_ORIGIN',
        'DIFFERENT_EVENT', 'CONFLICT_REVIEW_REQUIRED', 'CORROBORATION_PROPOSED']


INSTRUCTIONS = CONTEXT_INSTRUCTIONS.replace('RESEARCH CONTRACT v8.', 'RESEARCH CONTRACT v9.')
_start = INSTRUCTIONS.index('Materiality coverage concerns')
_end = INSTRUCTIONS.index('\nCITATIONS:', _start)
INSTRUCTIONS = INSTRUCTIONS[:_start] + '''
VERIFICATION: OBSERVED_FAILURE for same_event_verification is unavailable in this
adapter. Missing corroboration, shared-origin captures and different events are
INSUFFICIENT_EVIDENCE, not observed contradictory evidence. Record the matching
verification_basis. Even a proposed conflict stays INSUFFICIENT_EVIDENCE with
CONFLICT_REVIEW_REQUIRED and an explanation/citations for later adjudication.
No approved contradiction adjudicator is implemented here. Do not convert a
source-provenance observation into a failed strategy criterion. OBSERVED_SUPPORT
is only a research proposal with CORROBORATION_PROPOSED and the existing two
substantive source gate. Two source IDs do not prove independence or same event.
This implementation restriction does not create a new strategy source-count rule.

Materiality coverage concerns the TARGET and SELECTED EVENT only. Identify missing
FACTS in evidence_gaps: missing_fact, why_material to this precise assessment, and
captured_evidence_limit explaining why the available text cannot establish it.
An absent exhibit, primary source or original note is not itself a material fact
gap. Do not import verification, freshness, setup, participation or execution
requirements into limited materiality research. Preserve genuine economic gaps.
SUFFICIENT_FOR_RESEARCH requires substantive coverage evidence and no evidence
gaps. INCOMPLETE requires an explicit fact gap. UNRESOLVED is valid when sufficiency
cannot be assessed. Positive/negative materiality still requires sufficient
coverage and the existing fact prerequisites. Never hide gaps to gain admission.

Document suggestions belong ONLY in document_followups. Give the document, the
specific question it may answer, the reason, and a zero-based gap_index or null
for optional context. They are unapproved research proposals, never mandatory
strategy prerequisites. A follow-up alone cannot make coverage incomplete or
block a supported narrow research finding. Do not state a document is required
unless a governing rule explicitly establishes it; this adapter cannot approve
that necessity. Referenced exhibits can be noted without requiring their retrieval.
Reputable financial news can support limited analyst-action or management-commentary
research. No universal original-note, SEC, primary-document, legal-opinion or
transaction-completion rule exists here. Apply the masters' source rules.
''' + INSTRUCTIONS[_end:]


def gap_schema(packet):
    from research_reviewer import ReviewBlocked
    schema = GapDraft.model_json_schema()
    catalog = selectable_catalog(packet)
    if not catalog:
        raise ReviewBlocked('NO_SELECTABLE_EVIDENCE')
    substantive = sorted(k for k, v in catalog.items() if v['category'] in SUBSTANTIVE)
    if not substantive:
        raise ReviewBlocked('NO_SUBSTANTIVE_EVIDENCE')
    schema['$defs']['ExcerptRef']['properties']['excerpt_id']['enum'] = sorted(catalog)
    schema['$defs']['SubstantiveRef']['properties']['excerpt_id']['enum'] = substantive
    schema['$defs']['Target']['properties']['symbol']['enum'] = [packet['symbol']]
    for name in ('ContextClaim', 'GapCoverage'):
        schema['$defs'][name]['properties']['subject_symbol']['enum'] = [packet['symbol']]
    # Prevent metadata selection for binding at generation time as well as locally.
    for name, fields in (('Target', ('evidence',)), ('Event', ('evidence', 'link_evidence'))):
        for field in fields:
            schema['$defs'][name]['properties'][field]['items'] = {'$ref': '#/$defs/SubstantiveRef'}
    def enums(value):
        if isinstance(value, dict):
            if 'enum' in value: yield value['enum']
            for v in value.values(): yield from enums(v)
        elif isinstance(value, list):
            for v in value: yield from enums(v)
    choices = list(enums(schema))
    if sum(map(len, choices)) > 1000 or any(len(e) > 250 and
            sum(len(v) for v in e if isinstance(v, str)) > 15000 for e in choices):
        raise ReviewBlocked('CITATION_SCHEMA_LIMIT_EXCEEDED_NO_TRUNCATION')
    return schema


def prepare_gap_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import prepare_request, authority_texts, ReviewBlocked
    request = prepare_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    request['implementation_version'], request['prompt_version'] = VERSIONS
    body = request['body']
    body['input'][0]['content'] = (reviewer_request(packet)['instructions'] + '\n' + INSTRUCTIONS +
        '\nGOVERNING_MASTERS:\n' + canonical(authority_texts(packet, masters, now)) +
        '\nCRITERION_REFERENCES:\n' + canonical(CRITERIA))
    body['input'][-1] = context_evidence_message(packet)
    body['text']['format']['schema'] = gap_schema(packet)
    if len(canonical(body).encode('utf-8')) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    request['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=body))
    return request


def validate_gap_request(packet, request):
    from research_reviewer import ReviewBlocked
    if (request['packet_id'] != packet['packet_id'] or
            request['body']['input'][-1] != context_evidence_message(packet) or
            request['body']['text']['format'] != dict(type='json_schema', name='research_assessment',
                strict=True, schema=gap_schema(packet))):
        raise ReviewBlocked('GAP_REQUEST_BINDING_MISMATCH')


def resolve_gap_draft(packet, text):
    from research_reviewer import ReviewBlocked
    d = GapDraft.model_validate_json(text)
    coverage = d.materiality_coverage
    for c in d.claims:
        if c.criterion == 'same_event_verification':
            if c.evidence_state == 'OBSERVED_FAILURE':
                raise ReviewBlocked('VERIFICATION_FAILURE_ADAPTER_UNAVAILABLE')
            if c.evidence_state == 'OBSERVED_SUPPORT' and d.verification_basis != 'CORROBORATION_PROPOSED':
                raise ReviewBlocked('VERIFICATION_BASIS_CONFLICT')
    if coverage.status == 'INCOMPLETE' and not coverage.evidence_gaps:
        raise ReviewBlocked('FACT_GAP_REQUIRED_NOT_DOCUMENT_ABSENCE')
    if coverage.status == 'SUFFICIENT_FOR_RESEARCH' and coverage.evidence_gaps:
        raise ReviewBlocked('COVERAGE_SUFFICIENCY_CONFLICT')
    gap_values = [g.missing_fact for g in coverage.evidence_gaps]
    if len(set(gap_values)) != len(gap_values):
        raise ReviewBlocked('DUPLICATE_FACT_GAP')
    followup_values = [(f.document, f.question) for f in coverage.document_followups]
    if len(set(followup_values)) != len(followup_values):
        raise ReviewBlocked('DUPLICATE_DOCUMENT_FOLLOWUP')
    resolver = FixedResolver(packet)
    def evidence(item):
        rows = resolver.resolve(item.evidence)
        if any(r['category'] not in SUBSTANTIVE for r in rows):
            raise ReviewBlocked('GAP_SUBSTANTIVE_SOURCE_REQUIRED')
        return rows
    gap_rows = [evidence(g) for g in coverage.evidence_gaps]
    followup_rows = []
    for f in coverage.document_followups:
        if f.gap_index is not None and (type(f.gap_index) is not int or not 0 <= f.gap_index < len(gap_values)):
            raise ReviewBlocked('FOLLOWUP_GAP_REFERENCE_INVALID')
        followup_rows.append(evidence(f))
    converted = d.model_dump(exclude={'verification_basis'})
    cv = converted['materiality_coverage']
    cv.pop('evidence_gaps'); cv.pop('document_followups')
    # Internal legacy validation only: gap IDs stand for unresolved factual gaps,
    # never document mandates. Remove these compatibility fields from v9 output.
    cv['missing_documents'] = [dict(document='fact-gap:' + digest(g.model_dump()),
        reason=g.why_material) for g in coverage.evidence_gaps]
    resolved, facts, record, audit, binding = resolve_context_draft(packet, canonical(converted))
    for key in ('missing_documents', 'missing_document_reasons'):
        record.pop(key, None)
    event_id = binding['selected_event_id']
    gap_ids = [digest(dict(packet_id=packet['packet_id'], selected_event_id=event_id, gap=g.model_dump()))
        for g in coverage.evidence_gaps]
    record['evidence_gaps'] = [dict(g.model_dump(), gap_id=gid, citations=rows,
        semantic_verification='NOT_ESTABLISHED') for g, gid, rows in zip(coverage.evidence_gaps, gap_ids, gap_rows)]
    record['document_followups'] = [dict(f.model_dump(), gap_id=None if f.gap_index is None else gap_ids[f.gap_index],
        citations=rows, authority=DOCUMENT_AUTHORITY) for f, rows in zip(coverage.document_followups, followup_rows)]
    record['document_requirement_authority'] = DOCUMENT_AUTHORITY
    binding.update(verification_basis=d.verification_basis, verification_failure_capability=FAILURE_CAPABILITY)
    return resolved, facts, record, audit, binding
