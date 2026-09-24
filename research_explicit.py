"""Opt-in v21 research integration. Historical preview and CLI default stay frozen."""
from copy import deepcopy
import json
from evidence_review import canonical, digest
from research_explicit_contract import (VERSIONS as PREVIEW, INSTRUCTIONS as PREVIEW_INSTRUCTIONS,
    prepare_explicit_request, validate_explicit_request, validate_explicit_draft)

VERSIONS = ('1.20.0-automated-research', 'governed-research-v21')
INSTRUCTIONS = PREVIEW_INSTRUCTIONS.replace(
    'This preview has no dispatch or trading integration.',
    'This opt-in research contract retains the complete answer in the attempt ledger. No trading handoff is permitted.')


def prepare_integrated_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import ReviewBlocked
    # Preparation uses the same full inputs and schema as the frozen preview.
    r = prepare_explicit_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0]['content'] = r['body']['input'][0]['content'][:-len(PREVIEW_INSTRUCTIONS)] + INSTRUCTIONS
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def validate_integrated_request(packet, request):
    """Construct a validation projection only after checking the complete request."""
    from research_reviewer import ReviewBlocked
    try:
        if (request['implementation_version'], request['prompt_version']) != VERSIONS:
            raise ValueError()
        if request['request_id'] != digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=request['body'])):
            raise ValueError()
        content = request['body']['input'][0]['content']
        if not content.endswith('\n' + INSTRUCTIONS):
            raise ValueError()
        preview = deepcopy(request)
        preview['implementation_version'], preview['prompt_version'] = PREVIEW
        preview['body']['input'][0]['content'] = content[:-len(INSTRUCTIONS)] + PREVIEW_INSTRUCTIONS
        preview['request_id'] = digest(dict(version=PREVIEW[0], prompt_version=PREVIEW[1], body=preview['body']))
        masters, base = validate_explicit_request(packet, preview)
        return masters, base, preview
    except (KeyError, IndexError, TypeError, ValueError):
        raise ReviewBlocked('INTEGRATED_REQUEST_BINDING_MISMATCH') from None


def integrated_report(packet, request, text):
    _, _, preview = validate_integrated_request(packet, request)
    report = validate_explicit_draft(packet, preview, text)
    report.update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1], request_id=request['request_id'])
    report['limitations'][-1] = 'Opt-in research integration only. Structural validity is not source review, strategy evidence or trading approval.'
    del report['report_id']
    report['report_id'] = digest(report)
    return report


def resolve_integrated_draft(packet, request, text):
    from research_semantics import resolve_semantic_draft
    report = integrated_report(packet, request, text)
    _, base, _ = validate_integrated_request(packet, request)
    # Inherited checks operate on an explicitly internal projection. The entire
    # original provider text and wrapper remain mandatory in the returned result.
    result = resolve_semantic_draft(packet, base, canonical(report['original_draft']['draft']))
    binding = result[-1]
    binding['selection_transport']['catalog_scope'] = request['request_id']
    binding['extraction_instructions'].update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1],
        instruction_digest=digest(INSTRUCTIONS), request_id=request['request_id'],
        explicit_contract='INDIVIDUAL_RULE_APPLICATIONS_AND_TERM_ASSERTIONS_V1')
    binding['economic_inventory'].update(implementation_version=VERSIONS[0], request_id=request['request_id'])
    binding['explicit_response_contract'] = report
    return result
