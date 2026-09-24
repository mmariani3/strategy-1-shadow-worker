"""v15 scope-specific economic extraction instructions; frozen v14 parsing gates.

Only new requests use this prompt. Original provider text is never repaired.
Prompt compliance and semantic completeness still require external assessment.
"""
from copy import deepcopy
import json
from evidence_review import canonical, digest
from research_linked import (VERSIONS as PARSER_VERSIONS, linked_developer,
    linked_evidence_message, linked_schema, prepare_linked_request,
    validate_linked_request, resolve_linked_draft)

VERSIONS = ('1.14.0-automated-research', 'governed-research-v15')

ECONOMIC_INSTRUCTIONS = '''
RESEARCH EXTRACTION v15. Apply the following review procedure to the existing
inline-support output contract. It changes research instructions, not strategy
rules, eligibility, tier authority or trading approvals. Return concise findings
and their support in the existing fields, not private reasoning or extra fields.

SCOPE FIRST: State the narrow economic question for the selected event. Do not
combine it with watchlist admission, corroboration, freshness, setup readiness or
execution. Do not narrow the question merely to avoid contradictory evidence or
obligations integral to the event. Read the complete captured source before deciding
what matters; headlines and selected passages alone are not a completeness check.

ECONOMIC TERMS: For transactions/financing, preserve scope-relevant principal,
purchase price, proceeds, discounts, interest, fees and obligations as distinct
facts. For fees identify amount/basis, when earned/due, payment form and whether
contingent, to the extent actually disclosed. An earned/noncontingent obligation
may matter even when the associated facility is undrawn or later funding uncertain.
Do not net amounts, infer receipts, calculate missing denominators or invent terms.
For operating results preserve the reported metric, period and attribution; a
qualitative reported beat is not a measured surprise or proof of a different metric.
These are scope-specific reading checks, not a mandatory list of facts for every
event. Source silence is not proof of no fee or no condition.

CONDITIONS: Preserve each condition that changes a claim's meaning, including
joint AND conditions, alternatives, elections, approvals, default provisions,
conversion restrictions and contingencies. Keep commitments/ceilings, optional
draws, actual receipts and existing obligations distinct. A generic statement
that financing is conditional cannot replace a disclosed specific condition.

TIMING: Distinguish event occurrence, announcement/filing/publication, payment or
effective dates, future eligibility dates and market-observation times. Keep
different issuers/events separate. Preserve a disclosed relative timing condition
as stated; do not invent an absolute date. Missing clock time does not erase a
supported date, and a historical price never establishes current confirmation.

COUNTEREVIDENCE: Preserve source-supported costs, dilution, warnings, uncertainty,
downside qualifications and causal limits relevant to the same scope. Retain the
source's degree and attribution: an explicit expectation of substantial dilution
is not faithfully summarized as generic possible dilution. A technical warning
is market context, not a new fundamental issuer event. Put supported qualifications
in facts, coverage support or context_notes as appropriate; do not turn them into
unsupported rejection rules or omit them because the headline is favorable.

FACT BEFORE GAP: Separate (a) what the source establishes, (b) what is absent from
captured evidence, (c) uncertainty in interpreting the governing category, and
(d) a genuinely necessary economic fact missing for this narrow question. Only
(d) belongs in materiality evidence_gaps. If an interpretation remains uncertain,
explain it and leave the relevant mapping/coverage unresolved; do not manufacture
a source omission. Issuers need not label the private strategy's categories.
A missing filing, full contract or analyst note is a document followup, not itself
a missing economic fact. A numerical benchmark can answer a magnitude question
without being a universal prerequisite for reporting qualitative source evidence.
Do not replace the masters' most-direct-credible-source rule with a primary-only
rule. Do not map sales/revenue to earnings/guidance merely because that category
is closest; establish the substantive fit under the actual master or leave it
UNRESOLVED. All tier proposals remain NOT_APPROVED.

FINAL SOURCE/PROSE CHECK: Inspect fees/economic terms, conditions, timing and
counterevidence for the chosen scope. Preserve relevant disclosed details in the
answer, not merely in an uncited source or selected passage. Cite the adjacent
passages needed to support the entire assertion, including qualifiers and names.
An uncited reference may be a citation gap despite correct prose; a cited reference
may accompany a material omission or meaning error. Do not infer one from the other.
Do not claim SUFFICIENT_FOR_RESEARCH solely because citations are valid. Explain
unresolved scope-relevant interpretation in existing rationale/limitations fields.
Source-supported findings must remain source-supported; limitations are not a
place to hide economic assertions from citation checks. This self-check provides
no independent semantic acceptance, qualification or prospective approval.
'''


def economic_developer(packet, masters):
    result = linked_developer(packet, masters)
    result['content'] += '\n' + ECONOMIC_INSTRUCTIONS
    return result


def prepare_economic_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import authority_texts, ReviewBlocked
    r = prepare_linked_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0] = economic_developer(packet, authority_texts(packet, masters, now))
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def parser_request(packet, request, masters):
    """Internal parser context only; never persists or changes an original request."""
    r = deepcopy(request)
    r['implementation_version'], r['prompt_version'] = PARSER_VERSIONS
    r['body']['input'][0] = linked_developer(packet, masters)
    r['request_id'] = digest(dict(version=PARSER_VERSIONS[0], prompt_version=PARSER_VERSIONS[1], body=r['body']))
    return r


def validate_economic_request(packet, request):
    from research_reviewer import ReviewBlocked
    try:
        if (request['implementation_version'], request['prompt_version']) != VERSIONS:
            raise ValueError()
        if request['packet_id'] != packet['packet_id'] or request['request_id'] != digest(
                dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=request['body'])):
            raise ValueError()
        masters = json.loads(request['body']['input'][0]['content'].split('\nGOVERNING_MASTERS:\n', 1)[1].split('\nCRITERION_REFERENCES:\n', 1)[0])
        validate_linked_request(packet, parser_request(packet, request, masters))
        if (request['body']['input'] != [economic_developer(packet, masters), linked_evidence_message(packet)]
                or request['body']['text']['format'] != dict(type='json_schema', name='research_assessment', strict=True, schema=linked_schema(packet, masters))):
            raise ValueError()
    except (KeyError, IndexError, ValueError, TypeError):
        raise ReviewBlocked('ECONOMIC_REQUEST_BINDING_MISMATCH') from None
    return masters


def resolve_economic_draft(packet, request, text):
    masters = validate_economic_request(packet, request)
    internal = parser_request(packet, request, masters)
    resolved, facts, coverage, audit, binding = resolve_linked_draft(packet, internal, text)
    # The v14 support parser really ran; retain its implementation attribution.
    binding['selection_transport']['catalog_scope'] = request['request_id']
    binding['extraction_instructions'] = dict(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1],
        instruction_digest=digest(ECONOMIC_INSTRUCTIONS), parser_implementation_version=PARSER_VERSIONS[0],
        parser_prompt_contract=PARSER_VERSIONS[1], request_id=request['request_id'],
        compliance='NOT_ESTABLISHED', semantic_completeness='NOT_ESTABLISHED',
        original_response='UNMODIFIED')
    return resolved, facts, coverage, audit, binding
