"""v16 economic inventory with lossless host presentation, not semantic approval."""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field
from evidence_review import Strict, canonical, digest
from research_linked import LinkedDraft, NumberedClause, numbered_passages, linked_schema
from research_economic import (VERSIONS as PARSER_VERSIONS, economic_developer,
    prepare_economic_request, validate_economic_request, resolve_economic_draft)
from research_facts import SUBSTANTIVE

VERSIONS = ('1.15.0-automated-research', 'governed-research-v16')
FACETS = ('amounts', 'conditions', 'timing', 'qualifications')


class EconomicClause(NumberedClause):
    time_basis: Literal['NOT_TEMPORAL', 'EVENT_OCCURRENCE', 'PUBLICATION',
        'MARKET_OBSERVATION', 'CAPTURE', 'PAYMENT_OR_EFFECTIVE',
        'RELATIVE_DEADLINE', 'FORECAST_PERIOD', 'REPORTED_PERIOD']


class TermFacet(Strict):
    status: Literal['RECORDED', 'UNRESOLVED', 'NOT_APPLICABLE']
    reason: str = Field(min_length=1)
    entries: list[EconomicClause]


class EconomicTerm(Strict):
    label: str = Field(min_length=1)
    event_relation: Literal['SELECTED_EVENT', 'OTHER_EVENT', 'CONTEXT']
    nature: Literal['OBLIGATION', 'COMMITMENT', 'REPORTED_RESULT', 'FORECAST', 'OTHER']
    amounts: TermFacet
    conditions: TermFacet
    timing: TermFacet
    qualifications: TermFacet


class TermInventory(Strict):
    assessment_scope: str = Field(min_length=1)
    status: Literal['RECORDED_UNVERIFIED', 'UNRESOLVED']
    unresolved: list[str]
    terms: list[EconomicTerm]


class TermsDraft(Strict):
    economic_inventory: TermInventory
    research: LinkedDraft


INSTRUCTIONS = '''
RESEARCH CONTRACT v16 overrides the v14/v15 root output shape only. Return
economic_inventory FIRST, then research containing the existing inline-support
research object. This is a record of source findings, not private reasoning.
Read the full source and select the economic scope before populating the inventory.
Use exactly the same assessment_scope in the inventory and research coverage.

For each relevant economic term, record a specific label, event_relation and nature
(OBLIGATION, COMMITMENT, REPORTED_RESULT, FORECAST or OTHER). Keep distinct
obligations/results separate. For EACH term supply amounts, conditions, timing and
qualifications facets with status, reason and entries. An entry is a concise atomic
statement with time_basis and numbered source passages, using the existing catalog.
Inventory time_basis additionally distinguishes PAYMENT_OR_EFFECTIVE,
RELATIVE_DEADLINE, FORECAST_PERIOD and REPORTED_PERIOD; do not label a relative
payment deadline as event occurrence or publication. The nested research contract
retains its original, narrower time_basis enum.
Preserve disclosed units, amounts/rates, basis/period, payment form, limits and
attribution. Conditions include AND/alternative dependencies, elections, approval
exceptions and restrictions. Timing includes relative deadlines as stated, without
inventing dates. Qualifications include counterevidence, uncertainty, source
ambiguities and limits. Forecasts/commitments are not realized results/receipts.

RECORDED facets require entries; UNRESOLVED or NOT_APPLICABLE facets have no entries
and must explain the limitation. Source silence cannot establish absence. Use
UNRESOLVED for unavailable or ambiguous details, not an invented zero or unconditional
term. Reasons describe assessment limitations only; source assertions belong in
cited entries. Do not hide a disclosed obligation in an unresolved reason. A
recorded inventory is always UNVERIFIED, never complete, approved or trade-eligible.
If no terms can be recorded, mark the inventory UNRESOLVED with an explanation.
Keep overall unresolved issues visible even if some terms can be recorded.

Write research only after recording the inventory. It may give a concise overview,
but must not contradict the inventory. The host will publish a separate lossless
economic summary containing EVERY recorded facet, entry and unresolved reason;
the narrative research alone is not the complete economic presentation. A citation
to a generic term category does not replace its stated amounts and conditions.
Do not choose a narrower scope to suppress related obligations or downside context.
All strategy, source, tier, timing and no-handoff boundaries still apply. No primary-
only source prerequisite, new tier category or numerical strategy rule is permitted.
'''


def terms_developer(packet, masters):
    out = economic_developer(packet, masters)
    out['content'] += '\n' + INSTRUCTIONS
    return out


def terms_schema(packet, masters):
    schema = TermsDraft.model_json_schema()
    # Reuse exact nested constraints without changing the frozen historical schema.
    schema['$defs'].update(deepcopy(linked_schema(packet, masters)['$defs']))
    schema['$defs']['EconomicClause']['properties']['passages']['items'].update(
        minimum=1, maximum=len(numbered_passages(packet)))
    return schema


def prepare_terms_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import authority_texts, ReviewBlocked
    r = prepare_economic_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    m = authority_texts(packet, masters, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0] = terms_developer(packet, m)
    r['body']['text']['format']['schema'] = terms_schema(packet, m)
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def parser_request(packet, request, masters):
    r = deepcopy(request)
    r['implementation_version'], r['prompt_version'] = PARSER_VERSIONS
    r['body']['input'][0] = economic_developer(packet, masters)
    r['body']['text']['format']['schema'] = linked_schema(packet, masters)
    r['request_id'] = digest(dict(version=PARSER_VERSIONS[0], prompt_version=PARSER_VERSIONS[1], body=r['body']))
    return r


def validate_terms_request(packet, request):
    from research_reviewer import ReviewBlocked
    try:
        if ((request['implementation_version'], request['prompt_version']) != VERSIONS
                or request['packet_id'] != packet['packet_id']
                or request['request_id'] != digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=request['body']))):
            raise ValueError()
        m = json.loads(request['body']['input'][0]['content'].split('\nGOVERNING_MASTERS:\n', 1)[1].split('\nCRITERION_REFERENCES:\n', 1)[0])
        internal = parser_request(packet, request, m)
        validate_economic_request(packet, internal)
        if (request['body']['input'] != [terms_developer(packet, m), internal['body']['input'][1]]
                or request['body']['text']['format'] != dict(type='json_schema', name='research_assessment', strict=True, schema=terms_schema(packet, m))):
            raise ValueError()
    except (KeyError, IndexError, ValueError, TypeError):
        raise ReviewBlocked('TERMS_REQUEST_BINDING_MISMATCH') from None
    return m


def inventory_summary(inventory):
    """Deterministic complete projection. No shortening, field inference or rewriting."""
    # Validate structure without persisting Pydantic's whitespace-normalized strings.
    TermInventory.model_validate(inventory)
    out = dict(format_version='1.0.0-lossless-economic-summary',
        inventory_digest=digest(inventory), assessment_scope=inventory['assessment_scope'],
        status=inventory['status'], unresolved=deepcopy(inventory['unresolved']),
        rows=[dict(term_index=i, **deepcopy(term)) for i, term in enumerate(inventory['terms'])],
        preservation='ALL_RECORDED_FIELDS_EXACT', semantic_completeness='NOT_ESTABLISHED',
        eligible_for_handoff=False)
    return out


def verify_inventory_summary(inventory, summary):
    # JSON type identity matters: Python considers True == 1 == 1.0.
    if canonical(summary) != canonical(inventory_summary(inventory)):
        raise ValueError('ECONOMIC_SUMMARY_RETENTION_MISMATCH')


def inspect_inventory(packet, request, draft):
    """Check source locations and explicit facet states, never judge economic meaning."""
    from research_reviewer import ReviewBlocked
    validate_terms_request(packet, request)
    TermsDraft.model_validate(draft)
    inv = draft['economic_inventory']; research = draft['research']
    if inv['assessment_scope'] != research['materiality_coverage']['assessment_scope']:
        raise ReviewBlocked('INVENTORY_SCOPE_MISMATCH')
    if (not inv['terms'] and inv['status'] != 'UNRESOLVED') or (inv['status'] == 'UNRESOLVED' and not inv['unresolved']):
        raise ReviewBlocked('INVENTORY_UNRESOLVED_REASON_REQUIRED')
    if any(not s.strip() for s in inv['unresolved']): raise ReviewBlocked('EMPTY_INVENTORY_REASON')
    pc = numbered_passages(packet); bound = []; seen = set()
    for i, term in enumerate(inv['terms']):
        key = digest(term)
        if key in seen: raise ReviewBlocked('DUPLICATE_ECONOMIC_TERM')
        seen.add(key); count = 0
        for facet in FACETS:
            group = term[facet]
            if (group['status'] == 'RECORDED') != bool(group['entries']):
                raise ReviewBlocked('TERM_FACET_STATE_MISMATCH')
            for j, entry in enumerate(group['entries']):
                numbers = entry['passages']; count += 1
                if len(numbers) != len(set(numbers)) or any(n not in pc for n in numbers):
                    raise ReviewBlocked('TERM_PASSAGE_SELECTION_INVALID')
                citations = [deepcopy(pc[n]) for n in numbers]
                allowed = SUBSTANTIVE | ({'PUBLICATION_METADATA'} if facet == 'timing' and entry['time_basis'] == 'PUBLICATION' else set())
                if any(c['category'] not in allowed for c in citations):
                    raise ReviewBlocked('TERM_SUBSTANTIVE_SOURCE_REQUIRED')
                bound.append(dict(path=['economic_inventory','terms',i,facet,'entries',j],
                    entry_digest=digest(entry), citations=citations, semantic_support='NOT_ESTABLISHED'))
        if not count: raise ReviewBlocked('EMPTY_ECONOMIC_TERM')
    summary = inventory_summary(inv); verify_inventory_summary(inv, summary)
    return dict(implementation_version=VERSIONS[0], request_id=request['request_id'],
        packet_id=packet['packet_id'], trace=deepcopy(packet['trace']),
        original_draft_digest=digest(draft), inventory=deepcopy(inv), citations=bound,
        summary=summary, semantic_completeness='NOT_ESTABLISHED',
        classification='INFRASTRUCTURE_EVALUATION', eligible_for_handoff=False,
        limitation='Retention covers supplied fields only; omissions, false prose, missing qualifiers, scope choices and narrative contradictions still require source review.')


def resolve_terms_draft(packet, request, text):
    masters = validate_terms_request(packet, request)
    draft = json.loads(text)  # Preserve exact original strings for retention checks.
    inventory = inspect_inventory(packet, request, draft)
    # Explicit nested research projection for this new contract only. Original
    # provider envelope remains unchanged in the durable ledger and draft digest.
    resolved, facts, coverage, audit, binding = resolve_economic_draft(
        packet, parser_request(packet, request, masters), canonical(draft['research']))
    binding['selection_transport']['catalog_scope'] = request['request_id']
    binding['extraction_instructions'].update(implementation_version=VERSIONS[0], prompt_version=VERSIONS[1],
        instruction_digest=digest(INSTRUCTIONS), request_id=request['request_id'],
        inventory_contract='ECONOMIC_TERMS_V1', original_response='UNMODIFIED_ENVELOPE_WITH_DECLARED_RESEARCH_PROJECTION')
    binding['economic_inventory'] = inventory
    return resolved, facts, coverage, audit, binding
