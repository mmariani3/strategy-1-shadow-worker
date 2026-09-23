"""v20 source-meaning instructions; v19 schema and historical answers stay frozen."""
from copy import deepcopy
import json
from evidence_review import canonical, digest
from research_tiers import (tier_developer, tier_schema, prepare_tier_request,
    validate_tier_request, resolve_tier_draft, VERSIONS as PARSER_VERSIONS)

VERSIONS = ('1.19.0-automated-research', 'governed-research-v20')
INSTRUCTIONS = '''
RESEARCH CONTRACT v20 retains the v19 schema and all governing boundaries.
Provide source-grounded findings, not a record of private reasoning.

INDIVIDUAL RULE SUPPORT: In tier_proposal.explanation identify each selected rule
number and the specific selected-event fact that supports that rule. Keep the
source citations with that fact's support. Select only individually supported
categories; selecting every row with the desired tier label is not evidence.
A pending regulatory approval is not an issued regulatory decision; a future
business projection alone does not establish an earnings/guidance surprise.
An agreement does not establish every contract, acquisition, strategic or industry
category simultaneously. Apply the master's literal categories to the disclosed
event; do not add thresholds. Unsupported categories must not be proposed. Use
UNRESOLVED when the mapping cannot be established, without forcing a tier.

TIMING AND CONDITIONS: Preserve the tense and object of each source assertion.
An already-made commitment to fund in a future year is a present commitment with
future funding timing, not a commitment first made in that year. Record occurrence,
publication, payment/effectiveness, deadlines and forecast periods in their own
fields/bases. Publication-timing findings must state the supported publication
date/time or its unavailability; links, a future filing or a scheduled call do not
establish publication timing. Do not invent a clock time when only a date exists.
Keep each obligation's own conditions separate from general transaction closing
conditions. Reasons for unresolved facets describe what is unknown; do not insert
likely conditions, assumed absence of conditions or uncited facts into reasons.

COMPLETE QUALIFICATIONS: Read the entire captured source, including continuations
after any cited passage. Retain each disclosed qualification needed for the chosen
scope in qualifications/context and its exact supporting passages. Preserve who
pays, when, all relevant AND/alternative dependencies, exceptions and consequences.
A risk that approval conditions could harm benefits or cause abandonment is more
specific than 'approvals are required'. Preserve disclosed tax, litigation or
contract-consent risks when relevant to the stated scope. Do not narrow scope to
hide contrary context. Optional operational details remain optional; no universal
checklist of economic facts or new strategy prerequisite is created.
Generic caution, a future document followup or a citation to an incomplete sentence
does not replace a risk already disclosed. Include every adjacent passage needed
for each assertion's subject, condition and consequence, even if another facet
cites part of it. A valid source location does not establish truthful prose.
Review your final fields for these errors before returning the unchanged schema.
No assertion or completed checklist grants approval or trading eligibility.
'''


def semantic_developer(packet, masters):
    out = tier_developer(packet, masters)
    out['content'] += '\n' + INSTRUCTIONS
    return out


def prepare_semantic_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import authority_texts, ReviewBlocked
    r = prepare_tier_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0] = semantic_developer(packet, authority_texts(packet, masters, now))
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def parser_request(packet, request, masters):
    r = deepcopy(request)
    r['implementation_version'], r['prompt_version'] = PARSER_VERSIONS
    r['body']['input'][0] = tier_developer(packet, masters)
    r['request_id'] = digest(dict(version=PARSER_VERSIONS[0], prompt_version=PARSER_VERSIONS[1], body=r['body']))
    return r


def validate_semantic_request(packet, request):
    from research_reviewer import ReviewBlocked
    try:
        if ((request['implementation_version'], request['prompt_version']) != VERSIONS
                or request['packet_id'] != packet['packet_id']
                or request['request_id'] != digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=request['body']))):
            raise ValueError()
        m = json.loads(request['body']['input'][0]['content'].split('\nGOVERNING_MASTERS:\n', 1)[1].split('\nCRITERION_REFERENCES:\n', 1)[0])
        internal = parser_request(packet, request, m)
        validate_tier_request(packet, internal)
        if request['body']['input'] != [semantic_developer(packet, m), internal['body']['input'][1]]:
            raise ValueError()
    except (KeyError, IndexError, TypeError, ValueError):
        raise ReviewBlocked('SEMANTIC_REQUEST_BINDING_MISMATCH') from None
    return m


def resolve_semantic_draft(packet, request, text):
    m = validate_semantic_request(packet, request)
    result = resolve_tier_draft(packet, parser_request(packet, request, m), text)
    binding = result[-1]
    binding['selection_transport']['catalog_scope'] = request['request_id']
    binding['extraction_instructions'].update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1],
        instruction_digest=digest(INSTRUCTIONS), request_id=request['request_id'],
        source_meaning_contract='INDIVIDUAL_RULES_TIMING_AND_QUALIFICATIONS_V1')
    binding['economic_inventory'].update(implementation_version=VERSIONS[0], request_id=request['request_id'])
    return result
