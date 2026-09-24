"""v11 clause-location checks and host-attributed abstentions, not entailment.

Historical v10 remains unchanged. Quotes prove location; their relevance,
completeness, causal interpretation and gap necessity still need semantic review.
"""
from typing import Literal
from pydantic import ConfigDict, Field, StrictInt

from evidence_review import Strict, CRITERIA, canonical, digest, reviewer_request
from research_context import ContextClaim, FixedResolver, context_evidence_message
from research_subjects import SubjectDraft, INSTRUCTIONS as SUBJECT_INSTRUCTIONS, resolve_subject_draft
from research_citations import selectable_catalog
from research_facts import SUBSTANTIVE

VERSIONS = ('1.10.0-automated-research', 'governed-research-v11')
RESEARCH_CRITERIA = ('catalyst_materiality_tier', 'same_event_verification')
HOST_REASONS = {
    'catalyst_freshness': 'This document-research adapter has no approved freshness-policy evaluator. Event and publication evidence do not establish current qualification.',
    'market_context': 'This document-research adapter does not establish current broad-market context.',
    'liquidity': 'This document-research adapter does not measure current liquidity. The preferred ADV value in the Strategy Rules is not converted into a mandatory cutoff.',
    'participation_relative_strength': 'This document-research adapter does not measure current participation or relative strength.',
    'setup_structure': 'This document-research adapter does not construct or validate a current setup.',
    'target_and_risk': 'This document-research adapter does not validate current targets, stops, sizing or risk approval.',
    'prospective_confirmation': 'Historical reporting and price movement do not establish prospective trigger confirmation. This adapter has no prospective confirmation input.',
    'current_data_and_approvals': 'This adapter does not refresh market data or obtain current qualification, setup and risk approvals. Corporate or regulatory approvals are a separate domain.',
    'macro_context': 'This document-research adapter does not establish the current economic-event calendar or macro context.',
}


class ResearchClaim(ContextClaim):
    criterion: Literal[RESEARCH_CRITERIA]


class ExactQuote(Strict):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    excerpt_id: str
    quote: str = Field(min_length=1)


class Clause(Strict):
    statement: str = Field(min_length=1)
    time_basis: Literal['NOT_TEMPORAL', 'EVENT_OCCURRENCE', 'PUBLICATION', 'MARKET_OBSERVATION', 'CAPTURE']
    quotes: list[ExactQuote] = Field(min_length=1)


class Support(Strict):
    path: str
    event_relation: Literal['SELECTED_EVENT', 'OTHER_EVENT', 'CONTEXT']
    clauses: list[Clause] = Field(min_length=1)


class GapReview(Strict):
    gap_index: StrictInt
    assessment_scope: str
    domain: Literal['NARROW_MATERIALITY_FACT']
    already_established: str = Field(min_length=1)
    why_needed_for_this_scope: str = Field(min_length=1)


class ContextNote(Strict):
    kind: Literal['CONDITIONALITY', 'EXPECTATIONS', 'COUNTEREVIDENCE', 'CAUSAL_LIMIT', 'PROVENANCE', 'OTHER_EVENT']
    finding: str = Field(min_length=1)
    quotes: list[ExactQuote] = Field(min_length=1)


class SupportDraft(SubjectDraft):
    claims: list[ResearchClaim]
    support: list[Support]
    gap_review: list[GapReview]
    context_notes: list[ContextNote]


INSTRUCTIONS = SUBJECT_INSTRUCTIONS.replace('RESEARCH CONTRACT v10.', 'RESEARCH CONTRACT v11.')
INSTRUCTIONS = INSTRUCTIONS.replace('Do NOT\nreturn supporting_text, quotes or offsets.',
    'Legacy evidence fields contain excerpt IDs only; exact quotes belong only in the v11 support/context_notes fields. Never supply offsets.')
INSTRUCTIONS += '''
V11 OUTPUT CONTRACT (takes precedence over legacy field examples):
Return exactly TWO claims: catalyst_materiality_tier and same_event_verification.
The host appends the nine unavailable freshness/operational criteria as explicit
host-authored abstentions. Do not supply those claims, infer current trading
approvals from corporate approvals, or invent chronology in limitations.

CLAUSE SUPPORT: For every item with nonempty evidence, supply one support record.
Paths: target.rationale, selected_event.description, selected_event.link_rationale,
facts.<topic>, claims.<criterion>, materiality_coverage.rationale,
materiality_coverage.evidence_gaps.<zero-based-index>, and
materiality_coverage.document_followups.<zero-based-index>.
Each record breaks its factual assertions into atomic clauses. Each clause gives
its statement, time_basis and exact contiguous quote(s) copied from the selected
excerpt's quote string, with excerpt_id. Every cited excerpt must be covered and
must support this precise clause, not just the same ticker. Include separate
support for a raised price target, upgraded rating and their respective dates;
do not infer 'raised' from a displayed target. A quote may resolve but not entail
the statement: never claim semantic verification from location matching.

event_relation distinguishes SELECTED_EVENT from OTHER_EVENT and CONTEXT.
Selected event description, event facts and materiality gaps use SELECTED_EVENT;
another analyst's action cannot support the selected regulatory event. Event time
uses EVENT_OCCURRENCE from substantive event text, never publication metadata.
Publication time uses PUBLICATION. Market observation and capture times remain
separate. Do not infer that a reported price move happened after publication.

CONTEXT NOTES: Preserve material conditionality, temporary relief, intentions vs
completed decisions, expectations/pricing, contrary causal context and disclosed
source provenance in context_notes with exact quotes. An expected/fully priced
hike plus dovish guidance/rate-gap explanation cannot become an unqualified
'hike caused currency gains' narrative. Distinguish analyst maintenance from an
upgrade and forecasts from realized outcomes. Empty notes are valid only when no
such relevant context is captured; completeness is a semantic-review question.

GAP REVIEW: For each evidence_gap give its gap_index, the identical coverage
assessment_scope, domain NARROW_MATERIALITY_FACT, already_established and
why_needed_for_this_scope. State why available facts cannot answer that precise
question. Verification, freshness, instrument eligibility and operational review
are separate domains, not narrow materiality fact gaps. Missing document types,
publisher counts, full NAV mechanics, corporate approvals, binding contracts or
near-term receipts are not universal prerequisites. Put optional research routes
in document_followups. A source-backed descriptive finding or economic linkage
may remain useful while formal strategy eligibility stays unresolved. Never hide
a real gap; all necessity and scope judgments remain unapproved model proposals.
'''


def support_schema(packet):
    from research_reviewer import ReviewBlocked
    schema = SupportDraft.model_json_schema()
    catalog = selectable_catalog(packet)
    if not any(r['category'] in SUBSTANTIVE for r in catalog.values()):
        raise ReviewBlocked('NO_SUBSTANTIVE_EVIDENCE')
    for name in ('ExcerptRef', 'ExactQuote', 'SubstantiveRef'):
        schema['$defs'][name]['properties']['excerpt_id']['enum'] = sorted(k for k, v in catalog.items()
            if name != 'SubstantiveRef' or v['category'] in SUBSTANTIVE)
    schema['$defs']['Target']['properties']['symbol']['enum'] = [packet['symbol']]
    schema['$defs']['Target']['properties']['evidence']['items'] = {'$ref': '#/$defs/SubstantiveRef'}
    for name in ('ResearchClaim', 'GapCoverage'):
        schema['$defs'][name]['properties']['subject_symbol']['enum'] = [packet['symbol']]
    def enums(x):
        if isinstance(x, dict):
            if 'enum' in x: yield x['enum']
            for v in x.values(): yield from enums(v)
        elif isinstance(x, list):
            for v in x: yield from enums(v)
    choices = list(enums(schema))
    if sum(map(len, choices)) > 1000 or any(len(e) > 250 and sum(len(v) for v in e if isinstance(v, str)) > 15000 for e in choices):
        raise ReviewBlocked('CITATION_SCHEMA_LIMIT_EXCEEDED_NO_TRUNCATION')
    return schema


def prepare_support_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import prepare_request, authority_texts, ReviewBlocked
    r = prepare_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    b = r['body']
    b['input'][0]['content'] = (reviewer_request(packet)['instructions'] + '\n' + INSTRUCTIONS +
        '\nGOVERNING_MASTERS:\n' + canonical(authority_texts(packet, masters, now)) +
        '\nCRITERION_REFERENCES:\n' + canonical(CRITERIA))
    b['input'][-1] = context_evidence_message(packet)
    b['text']['format']['schema'] = support_schema(packet)
    if len(canonical(b).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=b))
    return r


def validate_support_request(packet, r):
    from research_reviewer import ReviewBlocked
    if (r['packet_id'] != packet['packet_id'] or r['body']['input'][-1] != context_evidence_message(packet)
        or r['body']['text']['format'] != dict(type='json_schema', name='research_assessment', strict=True, schema=support_schema(packet))):
        raise ReviewBlocked('SUPPORT_REQUEST_BINDING_MISMATCH')


def support_items(d):
    items = {'target.rationale': d.target, 'selected_event.description': d.selected_event,
        'selected_event.link_rationale': d.selected_event, 'materiality_coverage.rationale': d.materiality_coverage}
    items.update({'facts.' + f.topic: f for f in d.facts})
    items.update({'claims.' + c.criterion: c for c in d.claims})
    for field in ('evidence_gaps', 'document_followups'):
        items.update({f'materiality_coverage.{field}.{i}': item for i, item in enumerate(getattr(d.materiality_coverage, field))})
    return {path: (item.link_evidence if path == 'selected_event.link_rationale' else item.evidence)
        for path, item in items.items() if (item.link_evidence if path == 'selected_event.link_rationale' else item.evidence)}


def resolve_support_draft(packet, text):
    from research_reviewer import ReviewBlocked
    d = SupportDraft.model_validate_json(text)
    if sorted(c.criterion for c in d.claims) != sorted(RESEARCH_CRITERIA):
        raise ReviewBlocked('RESEARCH_CLAIM_SET_MISMATCH')
    expected = support_items(d)
    if len(d.support) != len(expected) or {s.path for s in d.support} != set(expected):
        raise ReviewBlocked('CLAUSE_SUPPORT_COVERAGE_MISMATCH')
    resolver = FixedResolver(packet)
    def quotes(refs):
        rows = []; seen = set()
        for q in refs:
            row = resolver.resolve([q])[0]; start = row['quote'].find(q.quote)
            if not q.quote.strip() or start < 0 or row['quote'].find(q.quote, start + 1) >= 0:
                raise ReviewBlocked('CLAUSE_QUOTE_MISSING_OR_AMBIGUOUS')
            absolute = row['start'] + start
            key = (row['source_id'], absolute, q.quote)
            if key in seen: raise ReviewBlocked('DUPLICATE_CLAUSE_QUOTE')
            seen.add(key)
            rows.append(dict(row, quote=q.quote, start=absolute, end=absolute + len(q.quote)))
        return rows
    audit = []
    for s in d.support:
        if {q.excerpt_id for c in s.clauses for q in c.quotes} != {r.excerpt_id for r in expected[s.path]}:
            raise ReviewBlocked('CLAUSE_EVIDENCE_BINDING_MISMATCH')
        event_scoped = s.path in ('selected_event.description', 'facts.catalyst_event', 'facts.event_timing') or s.path.startswith('materiality_coverage.evidence_gaps.')
        if event_scoped and s.event_relation != 'SELECTED_EVENT':
            raise ReviewBlocked('CLAUSE_EVENT_SCOPE_MISMATCH')
        clauses = []
        for c in s.clauses:
            rows = quotes(c.quotes)
            if s.path == 'facts.event_timing' and c.time_basis != 'EVENT_OCCURRENCE':
                raise ReviewBlocked('EVENT_TIME_BASIS_MISMATCH')
            if s.path == 'facts.publication_timing' and c.time_basis != 'PUBLICATION':
                raise ReviewBlocked('PUBLICATION_TIME_BASIS_MISMATCH')
            if c.time_basis in ('EVENT_OCCURRENCE', 'MARKET_OBSERVATION') and any(r['category'] not in SUBSTANTIVE for r in rows):
                raise ReviewBlocked('TEMPORAL_SUBSTANTIVE_EVIDENCE_REQUIRED')
            clauses.append(dict(c.model_dump(), citations=rows))
        audit.append(dict(path=s.path, event_relation=s.event_relation, clauses=clauses))
    gaps = d.materiality_coverage.evidence_gaps
    if sorted(g.gap_index for g in d.gap_review) != list(range(len(gaps))):
        raise ReviewBlocked('GAP_REVIEW_COVERAGE_MISMATCH')
    if any(g.assessment_scope != d.materiality_coverage.assessment_scope for g in d.gap_review):
        raise ReviewBlocked('GAP_REVIEW_SCOPE_MISMATCH')
    notes = [dict(n.model_dump(), citations=quotes(n.quotes)) for n in d.context_notes]
    converted = d.model_dump(exclude={'support', 'gap_review', 'context_notes'})
    claims = {c['criterion']: c for c in converted['claims']}
    claims.update({k: dict(criterion=k, subject_symbol=packet['symbol'], evidence_state='INSUFFICIENT_EVIDENCE',
        rationale=v, evidence=[]) for k, v in HOST_REASONS.items()})
    converted['claims'] = [claims[k] for k in CRITERIA]
    resolved, facts, coverage, selection_audit, binding = resolve_subject_draft(packet, canonical(converted))
    for row in binding['claims']:
        row['authored_by'] = 'HOST_CAPABILITY_BOUNDARY' if row['criterion'] in HOST_REASONS else 'MODEL_RESEARCH'
    binding['support_review'] = dict(clauses=audit, gap_review=[g.model_dump() for g in d.gap_review], context_notes=notes,
        implementation_version=VERSIONS[0], semantic_verification='NOT_ESTABLISHED',
        limitation='Exact location and declared scope checked; entailment, omitted qualifiers and gap necessity are not established.')
    return resolved, facts, coverage, selection_audit, binding
