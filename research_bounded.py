"""v7 research format: packet-bound citation choices and one document/reason list."""
from typing import Literal

from evidence_review import Strict, canonical, digest
from research_citations import SelectedDraft, Selection, selectable_catalog
from research_scoped import (MissingDocumentReason, prepare_scoped_request,
                             resolve_scoped_draft)

VERSIONS = ('1.6.0-automated-research', 'governed-research-v7')


class UnifiedCoverage(Strict):
    status: Literal['SUFFICIENT_FOR_RESEARCH', 'INCOMPLETE', 'UNRESOLVED']
    assessment_scope: str
    missing_documents: list[MissingDocumentReason]
    rationale: str
    evidence: list[Selection]


class BoundedDraft(SelectedDraft):
    materiality_coverage: UnifiedCoverage


INSTRUCTIONS_V7 = '''
CONTRACT v7 replaces the earlier missing-document output syntax only.
materiality_coverage.missing_documents is ONE list of {document, reason} objects.
Do not return a separate missing_document_reasons field or duplicate document names
in another list. Use [] when no required document is missing. Each reason must
explain the necessary fact and why the captured evidence cannot establish it.
All v6 claim-specific sufficiency and independent-criterion requirements remain.

Each excerpt_id must be one of the packet-specific choices in the strict schema.
Choose the actual supporting excerpt; a valid ID alone does not make a quotation
correct. Copy the exact clause and retain the anchored uniqueness rules. No quote
repair, invented offset, source substitution or eligibility change is permitted.
'''


def bounded_schema(packet):
    from research_reviewer import ReviewBlocked
    schema = BoundedDraft.model_json_schema()
    handles = sorted(selectable_catalog(packet))
    if not handles:
        raise ReviewBlocked('NO_SELECTABLE_EVIDENCE')
    schema['$defs']['Selection']['properties']['excerpt_id']['enum'] = handles

    def enum_lists(value):
        if isinstance(value, dict):
            if 'enum' in value:
                yield value['enum']
            for child in value.values():
                yield from enum_lists(child)
        elif isinstance(value, list):
            for child in value:
                yield from enum_lists(child)

    enums = list(enum_lists(schema))
    # Published provider schema limits; never truncate the evidence catalogue.
    if (sum(map(len, enums)) > 1000 or any(len(e) > 250 and
            sum(len(v) for v in e if isinstance(v, str)) > 15000 for e in enums)):
        raise ReviewBlocked('CITATION_SCHEMA_LIMIT_EXCEEDED_NO_TRUNCATION')
    return schema


def prepare_bounded_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import ReviewBlocked
    request = prepare_scoped_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    request['implementation_version'], request['prompt_version'] = VERSIONS
    body = request['body']
    body['input'][0]['content'] += '\n' + INSTRUCTIONS_V7
    body['text']['format']['schema'] = bounded_schema(packet)
    if len(canonical(body).encode('utf-8')) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    request['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=body))
    return request


def validate_bounded_request(packet, request):
    from research_reviewer import ReviewBlocked
    if request['body']['text']['format'] != dict(type='json_schema', name='research_assessment',
                                                strict=True, schema=bounded_schema(packet)):
        raise ReviewBlocked('PACKET_BOUND_SCHEMA_MISMATCH')


def resolve_bounded_draft(packet, text):
    draft = BoundedDraft.model_validate_json(text)
    converted = draft.model_dump()
    entries = converted['materiality_coverage']['missing_documents']
    # Derive compatibility fields locally from a single provider-generated list;
    # do not reconcile, normalize or repair two independently generated names.
    converted['materiality_coverage']['missing_document_reasons'] = entries
    converted['materiality_coverage']['missing_documents'] = [e['document'] for e in entries]
    return resolve_scoped_draft(packet, canonical(converted))
