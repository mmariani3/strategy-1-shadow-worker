"""Opt-in v22 field-meaning guidance; historical v21 remains frozen."""
from copy import deepcopy
from evidence_review import canonical, digest
from research_explicit import (VERSIONS as PREVIOUS, prepare_integrated_request,
    validate_integrated_request, integrated_report, resolve_integrated_draft)

VERSIONS = ('1.21.0-automated-research', 'governed-research-v22')
INSTRUCTIONS = '''
RESEARCH CONTRACT v22 retains the complete v21 response shape and all authority
boundaries. Apply these field meanings throughout the answer, including summary
support clauses. Do not change the strategy or add trading prerequisites.

CONDITIONS ARE SOURCE-DISCLOSED DEPENDENCIES: A conditions entry describes an
actual source-stated prerequisite, contingency, exception or dependency applying
to that particular term. Identify what depends on what, with complete citations.
The fact that a statement is forward-looking, an effect is attributed to an
event, or actual results may differ is not itself an operational condition.
Keep forecast classification and generic caution in qualifications; keep the
forecast's core economic assertion in its assertion/appropriate amounts field.
When the source does not disclose conditions, use UNRESOLVED with empty entries
and a bounded reason describing missing source detail. Do not interpret silence
as no conditions; NOT_APPLICABLE requires a defensible scope-based explanation.
Do not list hypothetical prerequisite classes such as reimbursement, demand or
financing unless the source actually establishes their relevance to this term.

ONE TEMPORAL BASIS PER CLAUSE: Each statement with a time_basis must express only
content compatible with that basis. Separate an already-occurred announcement
from forecasted future benefits, keeping complete citations with both assertions.
The existing general support.clauses schema does NOT allow FORECAST_PERIOD.
Keep the occurred-event assertion there under EVENT_OCCURRENCE. Preserve future
economic benefits in the appropriate economic_inventory term with nature FORECAST
and forecast timing entries marked FORECAST_PERIOD, plus its core term_assertion
and qualifications. Use EXPECTATIONS context notes where needed. Do not put
FORECAST_PERIOD into general support, publication-time or event-time clauses.
This is field placement, not permission to drop future benefits from the answer.
Apply the separation to materiality summaries, claims, event links and facts too.
Correct dedicated forecast fields do not cure a mixed-basis summary elsewhere.
A historical observation of a forecast is not evidence its outcome occurred.
Do not relabel a mixed sentence NOT_TEMPORAL to avoid separating its time bases.

PRECISE UNKNOWNS: Distinguish a disclosed comparison basis from missing absolute
baseline quantities or measurement periods. For example, same-input percentage
improvement gives a comparison basis even if absolute input/output is absent.
Reasons must not deny a basis already recorded, invent assumptions or add facts
without support. Unknowns remain unknown; no numerical threshold is introduced.

All condition facets, facet reasons and temporal clauses require source review.
The host binds that checklist to the original answer; it cannot prove semantic
truth from keywords, declarations, valid citations or a completed schema.
No field review grants qualification, trade, execution or observation eligibility.
'''


def prepare_field_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import ReviewBlocked
    r = prepare_integrated_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0]['content'] += '\n' + INSTRUCTIONS
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def validate_field_request(packet, request):
    from research_reviewer import ReviewBlocked
    try:
        if (request['implementation_version'], request['prompt_version']) != VERSIONS:
            raise ValueError()
        if request['request_id'] != digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=request['body'])):
            raise ValueError()
        content = request['body']['input'][0]['content']
        if not content.endswith('\n' + INSTRUCTIONS): raise ValueError()
        previous = deepcopy(request)
        previous['implementation_version'], previous['prompt_version'] = PREVIOUS
        previous['body']['input'][0]['content'] = content[:-len('\n' + INSTRUCTIONS)]
        previous['request_id'] = digest(dict(version=PREVIOUS[0], prompt_version=PREVIOUS[1], body=previous['body']))
        masters, _, _ = validate_integrated_request(packet, previous)
        return masters, previous
    except (KeyError, IndexError, TypeError, ValueError):
        raise ReviewBlocked('FIELD_REQUEST_BINDING_MISMATCH') from None


def field_checklist(original, request_id):
    """Exhaustive structural inventory, never an automatic semantic verdict."""
    items = []
    def add(kind, path, value, question):
        row = dict(kind=kind, path=path, original_value=deepcopy(value), value_digest=digest(value),
            question=question, status='SOURCE_REVIEW_REQUIRED')
        row['item_id'] = digest(dict(request_id=request_id, kind=kind, path=path, value_digest=row['value_digest']))
        items.append(row)
    for i, term in enumerate(original['draft']['economic_inventory']['terms']):
        path = ['draft', 'economic_inventory', 'terms', i]
        add('CONDITION_FACET', path+['conditions'], term['conditions'],
            'Does each recorded entry disclose a real dependency of this term? Forecast classification, causal attribution and generic caution are not conditions. If none are disclosed, preserve uncertainty.')
        for name in ('amounts', 'conditions', 'timing', 'qualifications'):
            # Bind the entire facet: a reason must be read alongside its entries.
            add('FACET_REASON', path+[name], term[name],
                'Is the reason consistent with the entries and full source, without hypothetical prerequisites or denial of a disclosed comparison basis?')
    def walk(value, path):
        if isinstance(value, dict):
            if 'statement' in value and 'time_basis' in value and 'passages' in value:
                add('TEMPORAL_CLAUSE', path, value,
                    'Does the entire statement fit its temporal basis? Split occurred events from forecast benefits; review all cited continuations and do not infer truth from tense keywords.')
            for k,v in value.items(): walk(v, path+[k])
        elif isinstance(value, list):
            for i,v in enumerate(value): walk(v, path+[i])
    walk(original, [])
    return items


def field_report(packet, request, text):
    _, previous = validate_field_request(packet, request)
    report = integrated_report(packet, previous, text)
    report.update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1], request_id=request['request_id'])
    report['field_items'] = field_checklist(report['original_draft'], request['request_id'])
    report['field_review_status'] = 'SOURCE_REVIEW_REQUIRED'
    report['limitations'].append('Field inventory is exhaustive structurally, not a semantic validator. Reviewer judgments are still required.')
    del report['report_id']; report['report_id'] = digest(report)
    return report


def resolve_field_draft(packet, request, text):
    _, previous = validate_field_request(packet, request)
    report = field_report(packet, request, text)
    result = resolve_integrated_draft(packet, previous, text)
    binding = result[-1]
    binding['selection_transport']['catalog_scope'] = request['request_id']
    binding['extraction_instructions'].update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1],
        instruction_digest=digest(request['body']['input'][0]['content']), request_id=request['request_id'],
        field_meaning_contract='CONDITIONS_AND_SINGLE_TEMPORAL_BASIS_V1')
    binding['economic_inventory'].update(implementation_version=VERSIONS[0], request_id=request['request_id'])
    binding['explicit_response_contract'] = report
    binding['field_review_status'] = 'SOURCE_REVIEW_REQUIRED'
    return result
