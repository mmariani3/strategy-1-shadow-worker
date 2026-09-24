"""v13 occurrence-specific passages and unapproved, rule-bound tier proposals.

Passage boundaries are mechanical presentation aids, not assertions of atomicity
or completeness. Historical v1-v12 contracts and outcomes remain unchanged.
"""
import json
import re
from hashlib import sha256
from typing import Literal

from pydantic import Field
from evidence_review import AUTHORITIES, CRITERIA, Strict, canonical, digest, reviewer_request
from research_citations import selectable_catalog
from research_context import context_evidence_message
from research_facts import SUBSTANTIVE
from research_subjects import resolve_subject_draft
from research_support import (SupportDraft, Support,
    RESEARCH_CRITERIA, HOST_REASONS, INSTRUCTIONS as SUPPORT_INSTRUCTIONS, support_items)

VERSIONS = ('1.12.0-automated-research', 'governed-research-v13')


class PassageRef(Strict):
    passage_id: str = Field(pattern=r'^P[0-9a-f]{20}$')


class SelectedClause(Strict):
    statement: str = Field(min_length=1)
    time_basis: Literal['NOT_TEMPORAL', 'EVENT_OCCURRENCE', 'PUBLICATION', 'MARKET_OBSERVATION', 'CAPTURE']
    passages: list[PassageRef] = Field(min_length=1)


class SelectedSupport(Support):
    clauses: list[SelectedClause] = Field(min_length=1)


class SelectedContext(Strict):
    kind: Literal['CONDITIONALITY', 'EXPECTATIONS', 'COUNTEREVIDENCE', 'CAUSAL_LIMIT', 'PROVENANCE', 'OTHER_EVENT']
    finding: str = Field(min_length=1)
    passages: list[PassageRef] = Field(min_length=1)


class RuleRef(Strict):
    rule_id: str = Field(pattern=r'^R[0-9a-f]{20}$')


class TierProposal(Strict):
    proposed_tier: Literal['A', 'B', 'C', 'UNRESOLVED']
    mapping_status: Literal['PROPOSED', 'UNRESOLVED']
    rules: list[RuleRef]
    supporting_paths: list[str]
    explanation: str = Field(min_length=1)


class PassageDraft(SupportDraft):
    support: list[SelectedSupport]
    context_notes: list[SelectedContext]
    tier_proposal: TierProposal


def passage_catalog(packet):
    """Index each occurrence inside an already anchored original excerpt.

    No text search chooses among repeated passages. Encoding the readable prefix
    supplies the exact offset in canonical source.text. All text remains visible.
    """
    from research_reviewer import ReviewBlocked
    result = {}
    sources = {s['source_id']: s['text'] for s in packet['sources']}
    for eid, row in selectable_catalog(packet).items():
        text = row['text']
        if canonical(text)[1:-1] != row['quote']:
            # Non-string metadata has a key:value representation, not a string.
            bounds = [(0, len(text), row['start'], row['end'], row['quote'])]
        else:
            # Newlines, semicolons and sentence punctuation are presentation
            # boundaries only. Abbreviations/chunk edges can split a sentence.
            ends = [m.end() for m in re.finditer(r'\r\n|[\r\n]|[;.!?][ \t]+', text)] + [len(text)]
            bounds = []; start = 0
            for end in sorted(set(ends)):
                quote = canonical(text[start:end])[1:-1]
                absolute = row['start'] + len(canonical(text[:start])[1:-1])
                if text[start:end].strip():
                    bounds.append((start, end, absolute, absolute + len(quote), quote))
                start = end
        for a, b, start, end, quote in bounds:
            if sources[row['source_id']][start:end] != quote:
                raise ReviewBlocked('PASSAGE_SOURCE_OFFSET_MISMATCH')
            pid = 'P' + digest(dict(source_id=row['source_id'], start=start, end=end))[:20]
            value = dict(passage_id=pid, excerpt_id=eid, source_id=row['source_id'], path=row['path'],
                category=row['category'], text=text[a:b], quote=quote, start=start, end=end)
            if pid in result and result[pid] != value:
                raise ReviewBlocked('PASSAGE_ID_COLLISION')
            result[pid] = value
    return result


def rule_catalog(masters):
    """Exact Strategy master lines; tier lists additionally split at semicolons.

    Labels identify the master's literal Tier A/B/C headings, not event meaning.
    All other lines remain selectable context but cannot stand in for a tier rule.
    """
    m = masters['strategy']; result = {}; offset = 0
    for line in m['text'].splitlines(keepends=True):
        match = re.match(r'Tier ([ABC]) - [^:]+:', line)
        tier = match[1] if match else None
        start = match.end() if match else 0
        ends = [x.end() for x in re.finditer(';', line)] + [len(line)] if match else [len(line)]
        for end in ends:
            if line[start:end].strip():
                row = dict(document_id=m['document_id'], version=m['version'], revision_id=m['revision_id'],
                    text_sha256=m['text_sha256'], start=offset+start, end=offset+end,
                    text=line[start:end], tier=tier, heading=line[:match.end()] if match else None)
                rid = 'R' + digest(row)[:20]
                if rid in result and result[rid] != row: raise ValueError('RULE_ID_COLLISION')
                result[rid] = row
            start = end
        offset += len(line)
    return result


INSTRUCTIONS = SUPPORT_INSTRUCTIONS.replace('v11', 'v13').replace('V11', 'V13')
INSTRUCTIONS = INSTRUCTIONS.replace(
    'Legacy evidence fields contain excerpt IDs only; exact quotes belong only in the v13 support/context_notes fields. Never supply offsets.',
    'Evidence fields contain excerpt IDs only; support/context_notes select passage IDs. Never supply quotations or offsets.')
INSTRUCTIONS = INSTRUCTIONS.replace(
    "its statement, time_basis and exact contiguous quote(s) copied from the selected\nexcerpt's quote string, with excerpt_id.",
    'its statement, time_basis and passages: [{passage_id}] from selectable_passages.')
INSTRUCTIONS = INSTRUCTIONS.replace('with exact quotes.', 'with passage IDs.')
INSTRUCTIONS += '''
V13 PASSAGE CONTRACT: The only citation output in support and context_notes is
passages: [{passage_id}]. Do not retype quotations. The host copies each selected
passage verbatim, including punctuation and whitespace, from its exact occurrence.
Duplicate text has distinct IDs at distinct locations. Select all adjacent IDs
needed to support a clause and preserve qualifiers. Boundaries are mechanical;
they may split an abbreviation or sentence, and do not establish atomic meaning.
Full original text and complete non-source context remain supplied separately.
Each cited excerpt in an item's evidence must have a selected supporting passage
and vice versa. Include selected_event.subject among support paths when cited.
Valid locations do not prove entailment, correct event identity or completeness.

TIER PROPOSAL: Return tier_proposal with proposed_tier A/B/C/UNRESOLVED,
mapping_status PROPOSED/UNRESOLVED, rules [{rule_id}], supporting_paths, explanation.
For PROPOSED select the exact category passage from selectable_rules with the same
tier and explain how source-supported facts fit that category, including limits.
supporting_paths must include facts.catalyst_event and refer to recorded support.
Discovery channel descriptions are not tier definitions. A corporate action or
filing is not by itself a catch-all Tier B category. If a mapping is uncertain,
use UNRESOLVED with proposed_tier UNRESOLVED and explain the uncertainty. Rules
are governing text, not event evidence; never cite rule IDs as source passages.
Every tier mapping remains NOT_APPROVED. catalyst_materiality_tier must always
use INSUFFICIENT_EVIDENCE in this adapter: it cannot approve or reject a strategy
tier automatically. Keep useful event facts and scoped coverage; this capability
boundary does not change Strategy Rules or claim that the event lacks significance.
Even a PROPOSED category with exact rule/source references needs semantic review.
Same-event-verification retains its existing limited research assessment contract.
'''


def passage_evidence_message(packet):
    view = json.loads(context_evidence_message(packet)['content'].split('\n', 1)[1])
    view['selectable_passages'] = {k: {name: v for name, v in r.items()
        if name not in ('quote', 'start', 'end', 'passage_id', 'source_id', 'path', 'category')}
        for k, r in passage_catalog(packet).items()}
    view['citation_policy'] = 'FIXED_OCCURRENCE_PASSAGE_V1'
    return dict(role='user', content='UNTRUSTED_PASSAGE_RESEARCH_V1:\n' + canonical(view))


def passage_schema(packet):
    from research_reviewer import ReviewBlocked
    schema = PassageDraft.model_json_schema(); catalog = selectable_catalog(packet)
    if not any(r['category'] in SUBSTANTIVE for r in catalog.values()):
        raise ReviewBlocked('NO_SUBSTANTIVE_EVIDENCE')
    # Runtime lookups reject unknown IDs. Patterns avoid growing provider enums
    # or silently dropping passages when a long document exceeds enum limits.
    for name in ('ExcerptRef', 'SubstantiveRef'):
        schema['$defs'][name]['properties']['excerpt_id']['pattern'] = '^E[0-9a-f]{20}$'
    schema['$defs']['Target']['properties']['symbol']['enum'] = [packet['symbol']]
    for name in ('ResearchClaim', 'GapCoverage'):
        schema['$defs'][name]['properties']['subject_symbol']['enum'] = [packet['symbol']]
    return schema


def developer_message(packet, masters):
    # Master identity/offsets are host-derived. Avoid repeating them for every
    # rule in the transport view; the full master remains above the index.
    visible_rules = {k: {name: row[name] for name in ('text', 'tier', 'heading')}
        for k, row in rule_catalog(masters).items()}
    return dict(role='developer', content=reviewer_request(packet)['instructions'] + '\n' + INSTRUCTIONS +
        '\nGOVERNING_MASTERS:\n' + canonical(masters) + '\nCRITERION_REFERENCES:\n' + canonical(CRITERIA) +
        '\nSELECTABLE_RULES:\n' + canonical(visible_rules))


def prepare_passage_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import prepare_request, authority_texts, ReviewBlocked
    r = prepare_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'] = [developer_message(packet, authority_texts(packet, masters, now)), passage_evidence_message(packet)]
    r['body']['text']['format']['schema'] = passage_schema(packet)
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def validate_passage_request(packet, request):
    from research_reviewer import ReviewBlocked
    try:
        masters = json.loads(request['body']['input'][0]['content'].split('\nGOVERNING_MASTERS:\n', 1)[1].split('\nCRITERION_REFERENCES:\n', 1)[0])
        if set(masters) != set(AUTHORITIES) or digest(masters) != request['masters_digest']:
            raise ValueError()
        for role, (doc, version) in AUTHORITIES.items():
            m = masters[role]; ref = packet['authority_refs'][role]
            if (m['document_id'] != doc or m['version'] != version or not m['text'].strip()
                or sha256(m['text'].encode()).hexdigest() != m['text_sha256']
                or any(m[k] != ref[k] for k in ('document_id', 'version', 'revision_id'))):
                raise ValueError()
        b = request['body']
        if (request['packet_id'] != packet['packet_id'] or b['tools'] != [] or b['store'] is not False
            or b['input'] != [developer_message(packet, masters), passage_evidence_message(packet)]
            or b['text']['format'] != dict(type='json_schema', name='research_assessment', strict=True, schema=passage_schema(packet))):
            raise ValueError()
    except (KeyError, ValueError, IndexError, TypeError):
        raise ReviewBlocked('PASSAGE_REQUEST_BINDING_MISMATCH') from None
    return masters


def resolve_passage_draft(packet, request, text):
    from research_reviewer import ReviewBlocked
    masters = validate_passage_request(packet, request)
    d = PassageDraft.model_validate_json(text)
    if sorted(c.criterion for c in d.claims) != sorted(RESEARCH_CRITERIA):
        raise ReviewBlocked('RESEARCH_CLAIM_SET_MISMATCH')
    expected = support_items(d)
    if d.selected_event.subject.evidence:
        expected['selected_event.subject'] = d.selected_event.subject.evidence
    if len(d.support) != len(expected) or {s.path for s in d.support} != set(expected):
        raise ReviewBlocked('CLAUSE_SUPPORT_COVERAGE_MISMATCH')
    catalog = passage_catalog(packet)

    def citations(refs):
        rows = []; seen = set()
        for ref in refs:
            row = catalog.get(ref.passage_id)
            if row is None: raise ReviewBlocked('PASSAGE_NOT_SELECTABLE')
            if ref.passage_id in seen: raise ReviewBlocked('DUPLICATE_CLAUSE_PASSAGE')
            seen.add(ref.passage_id); rows.append(dict(row))
        return rows

    audit = []
    for s in d.support:
        rows = [row for c in s.clauses for row in citations(c.passages)]
        if {r['excerpt_id'] for r in rows} != {r.excerpt_id for r in expected[s.path]}:
            raise ReviewBlocked('CLAUSE_EVIDENCE_BINDING_MISMATCH')
        event_scoped = s.path in ('selected_event.description', 'selected_event.subject', 'facts.catalyst_event', 'facts.event_timing') or s.path.startswith('materiality_coverage.evidence_gaps.')
        if event_scoped and s.event_relation != 'SELECTED_EVENT':
            raise ReviewBlocked('CLAUSE_EVENT_SCOPE_MISMATCH')
        clauses = []
        for c in s.clauses:
            rows = citations(c.passages)
            if s.path == 'facts.event_timing' and c.time_basis != 'EVENT_OCCURRENCE':
                raise ReviewBlocked('EVENT_TIME_BASIS_MISMATCH')
            if s.path == 'facts.publication_timing' and c.time_basis != 'PUBLICATION':
                raise ReviewBlocked('PUBLICATION_TIME_BASIS_MISMATCH')
            if c.time_basis in ('EVENT_OCCURRENCE', 'MARKET_OBSERVATION') and any(r['category'] not in SUBSTANTIVE for r in rows):
                raise ReviewBlocked('TEMPORAL_SUBSTANTIVE_EVIDENCE_REQUIRED')
            clauses.append(dict(c.model_dump(), citations=rows))
        audit.append(dict(path=s.path, event_relation=s.event_relation, clauses=clauses))
    if sorted(g.gap_index for g in d.gap_review) != list(range(len(d.materiality_coverage.evidence_gaps))):
        raise ReviewBlocked('GAP_REVIEW_COVERAGE_MISMATCH')
    if any(g.assessment_scope != d.materiality_coverage.assessment_scope for g in d.gap_review):
        raise ReviewBlocked('GAP_REVIEW_SCOPE_MISMATCH')
    notes = [dict(n.model_dump(), citations=citations(n.passages)) for n in d.context_notes]
    tier = d.tier_proposal; rules = rule_catalog(masters); rule_rows = []
    if len({r.rule_id for r in tier.rules}) != len(tier.rules) or len(set(tier.supporting_paths)) != len(tier.supporting_paths):
        raise ReviewBlocked('DUPLICATE_TIER_REFERENCE')
    for ref in tier.rules:
        if ref.rule_id not in rules: raise ReviewBlocked('RULE_NOT_SELECTABLE')
        rule_rows.append(dict(rule_id=ref.rule_id, **rules[ref.rule_id]))
    if any(path not in expected for path in tier.supporting_paths):
        raise ReviewBlocked('TIER_SUPPORT_PATH_MISMATCH')
    if tier.mapping_status == 'PROPOSED':
        if (tier.proposed_tier == 'UNRESOLVED' or not rule_rows
            or any(r['tier'] != tier.proposed_tier for r in rule_rows)
            or 'facts.catalyst_event' not in tier.supporting_paths):
            raise ReviewBlocked('TIER_RULE_MAPPING_REQUIRED')
    elif tier.proposed_tier != 'UNRESOLVED':
        raise ReviewBlocked('UNRESOLVED_TIER_CONFLICT')
    if any(c.criterion == 'catalyst_materiality_tier' and c.evidence_state != 'INSUFFICIENT_EVIDENCE' for c in d.claims):
        raise ReviewBlocked('TIER_SEMANTIC_APPROVAL_UNAVAILABLE')
    converted = d.model_dump(exclude={'support', 'gap_review', 'context_notes', 'tier_proposal'})
    claims = {c['criterion']: c for c in converted['claims']}
    claims.update({k: dict(criterion=k, subject_symbol=packet['symbol'], evidence_state='INSUFFICIENT_EVIDENCE',
        rationale=v, evidence=[]) for k, v in HOST_REASONS.items()})
    converted['claims'] = [claims[k] for k in CRITERIA]
    resolved, facts, coverage, selection_audit, binding = resolve_subject_draft(packet, canonical(converted))
    for row in binding['claims']:
        row['authored_by'] = 'HOST_CAPABILITY_BOUNDARY' if row['criterion'] in HOST_REASONS else 'MODEL_RESEARCH'
    binding['support_review'] = dict(clauses=audit, gap_review=[g.model_dump() for g in d.gap_review], context_notes=notes,
        implementation_version=VERSIONS[0], quote_contract='FIXED_OCCURRENCE_PASSAGE_V1', semantic_verification='NOT_ESTABLISHED',
        limitation='Occurrence and declared scope checked; entailment, omitted context and gap necessity remain unverified.')
    binding['tier_review'] = dict(tier.model_dump(), rule_citations=rule_rows,
        approval='NOT_APPROVED', semantic_verification='NOT_ESTABLISHED',
        capability='NO_APPROVED_AUTOMATIC_TIER_MAPPING', selected_event_id=binding['selected_event_id'])
    return resolved, facts, coverage, selection_audit, binding
