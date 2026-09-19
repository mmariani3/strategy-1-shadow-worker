"""v5 anchored citation spans and explicit materiality evidence coverage.

All results remain research only. Historical v3/v4 contracts are unchanged.
"""
import json
from typing import Literal

from evidence_review import Strict, canonical, digest
from research_citations import Selection, SelectedDraft, selectable_catalog
from research_facts import INSTRUCTIONS, SUBSTANTIVE, resolve_draft

VERSIONS = ('1.4.0-automated-research', 'governed-research-v5')


class MaterialityCoverage(Strict):
    status: Literal['SUFFICIENT_FOR_RESEARCH', 'INCOMPLETE', 'UNRESOLVED']
    missing_documents: list[str]
    rationale: str
    evidence: list[Selection]


class CoverageDraft(SelectedDraft):
    materiality_coverage: MaterialityCoverage


def coverage_evidence_message(packet):
    from research_citations import selection_evidence_message
    view = json.loads(selection_evidence_message(packet)['content'].split('\n', 1)[1])
    view['citation_policy'] = 'ANCHORED_SAME_FIELD_SPAN_V1'
    return {'role': 'user', 'content': 'UNTRUSTED_CAPTURED_EVIDENCE_WITH_COVERAGE_V1:\n' + canonical(view)}


INSTRUCTIONS_V5 = '''
CONTRACT v5 overrides earlier output/citation syntax and the meaning of document
coverage prerequisites. Return the supplied schema: facts, claims, limitations,
materiality_coverage. Each citation is {excerpt_id, supporting_text}.

Copy a supporting clause exactly as readable source text, with normal JSON
escaping. An excerpt_id is an ANCHOR: the quote must overlap that excerpt but may
extend into neighboring text in the SAME original source field. Never combine
separate fields, documents, or disjoint passages. No punctuation normalization,
ellipsis substitution, or reconstructed quotations. Use separate selections for
separate clauses. Distinct quotes may reuse an anchor ID. Do not repeat the same
source location twice within a finding, claim, or coverage assessment.
Workflow fields and market snapshots remain context, not selectable evidence.
Publication metadata supports publication facts only, never catalyst conclusions.

document_coverage is a FACT FINDING: an EVIDENCED finding can correctly report that
an exhibit is missing. It does NOT establish enough evidence for materiality.
Separately assess materiality_coverage: SUFFICIENT_FOR_RESEARCH only if captured
substantive evidence is adequate for the proposed materiality assessment, with no
missing documents needed to support it. Identify missing required exhibits or
documents explicitly in missing_documents and mark INCOMPLETE. If sufficiency or
what is needed cannot be established, mark UNRESOLVED. Give a rationale and cite
the substantive text establishing the basis or the referenced missing document.
An exhibit's mere mention is not its contents. A patent or acquisition label alone
does not establish the economic significance required by the governing rules.
Do not silently omit a known gap to obtain a sufficient status. A fact that an
event happened is not a finding that required supporting evidence is complete.

Any OBSERVED_SUPPORT or OBSERVED_FAILURE for catalyst_materiality_tier requires
SUFFICIENT_FOR_RESEARCH coverage, no missing required documents, and the existing
instrument/event/document fact prerequisites. Otherwise use INSUFFICIENT_EVIDENCE.
These are research-adapter evidence gates, not new strategy thresholds or approvals.
Keep all other v3 capability, category, timing and source rules. Unknown freshness
policy must remain unresolved, not be replaced by an invented age cutoff. Exact
citations and a declared sufficient status do not independently verify meaning.
'''


def prepare_coverage_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import prepare_request, ReviewBlocked
    request = prepare_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    request['implementation_version'], request['prompt_version'] = VERSIONS
    body = request['body']
    body['input'][0]['content'] += '\n' + INSTRUCTIONS + '\n' + INSTRUCTIONS_V5
    body['input'][-1] = coverage_evidence_message(packet)
    body['text']['format']['schema'] = CoverageDraft.model_json_schema()
    if len(canonical(body).encode('utf-8')) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    request['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=body))
    return request


class SpanResolver:
    def __init__(self, packet):
        self.catalog = selectable_catalog(packet)
        self.sources = {s['source_id']: s for s in packet['sources']}

    def resolve(self, selections):
        """Unique exact source spans, anchored within the same raw JSON leaf.

        No fuzzy matching, whitespace cleanup, deduplication, or source rewriting.
        Span uniqueness is scoped to one finding/claim/coverage item.
        """
        from research_reviewer import ReviewBlocked
        spans = []; seen = set()
        for selection in selections:
            row = self.catalog.get(selection.excerpt_id)
            if row is None:
                raise ReviewBlocked('EXCERPT_NOT_SELECTABLE')
            source = self.sources[row['source_id']]
            support = selection.supporting_text
            if not support.strip():
                raise ReviewBlocked('SUPPORT_TEXT_REQUIRED')
            quote = canonical(support)[1:-1]
            if source['text'].count(quote) != 1:
                raise ReviewBlocked('SUPPORT_TEXT_MISSING_OR_AMBIGUOUS')
            start = source['text'].index(quote); end = start + len(quote)
            value = source['raw']
            for part in row['path']:
                value = value[part]
            if isinstance(value, str):
                # The original serialized leaf, not neighboring JSON fields.
                leaf = canonical(value)[1:-1]
                if support not in value or source['text'].count(leaf) != 1:
                    raise ReviewBlocked('SUPPORT_TEXT_OUTSIDE_SOURCE_FIELD')
                lower = source['text'].index(leaf); upper = lower + len(leaf)
            else:
                lower, upper = row['start'], row['end']
            if not (lower <= start < end <= upper):
                raise ReviewBlocked('SUPPORT_TEXT_OUTSIDE_SOURCE_FIELD')
            if not (start < row['end'] and end > row['start']):
                raise ReviewBlocked('SUPPORT_TEXT_DOES_NOT_OVERLAP_ANCHOR')
            identity = (row['source_id'], start, end)
            if identity in seen:
                raise ReviewBlocked('DUPLICATE_SOURCE_SPAN')
            seen.add(identity)
            spans.append(dict(source_id=row['source_id'], quote=quote, start=start,
                end=end, anchor_excerpt_id=selection.excerpt_id, category=row['category']))
        return spans


def resolve_coverage_draft(packet, text):
    from research_reviewer import ReviewBlocked
    draft = CoverageDraft.model_validate_json(text)
    resolver = SpanResolver(packet)
    converted = draft.model_dump(exclude={'materiality_coverage'})
    audit = {}
    for group in ('facts', 'claims'):
        audit[group] = []
        for original, item in zip(getattr(draft, group), converted[group]):
            rows = resolver.resolve(original.evidence)
            item.pop('evidence')
            # The legacy validator checks categories by unique anchors; distinct
            # validated spans are retained below, including reused anchor IDs.
            item['excerpt_ids'] = list(dict.fromkeys(s.excerpt_id for s in original.evidence))
            audit[group].append(dict(item=item.get('topic', item.get('criterion')), spans=rows))
    coverage = draft.materiality_coverage
    if not coverage.rationale.strip() or any(not x.strip() for x in coverage.missing_documents):
        raise ReviewBlocked('COVERAGE_EXPLANATION_REQUIRED')
    rows = resolver.resolve(coverage.evidence)
    if any(r['category'] not in SUBSTANTIVE for r in rows):
        raise ReviewBlocked('COVERAGE_SUBSTANTIVE_SOURCE_REQUIRED')
    if coverage.status == 'SUFFICIENT_FOR_RESEARCH':
        if coverage.missing_documents or not rows:
            raise ReviewBlocked('COVERAGE_SUFFICIENCY_CONFLICT')
    if coverage.status == 'INCOMPLETE' and not coverage.missing_documents:
        raise ReviewBlocked('MISSING_DOCUMENTS_REQUIRED')
    for claim in draft.claims:
        if (claim.criterion == 'catalyst_materiality_tier' and
                claim.evidence_state != 'INSUFFICIENT_EVIDENCE' and
                (coverage.status != 'SUFFICIENT_FOR_RESEARCH' or coverage.missing_documents)):
            raise ReviewBlocked('MATERIALITY_COVERAGE_NOT_SUFFICIENT')
    # Preserve category, capability, complete-topic and prerequisite checks.
    resolved, facts = resolve_draft(packet, canonical(converted))
    for fact, item in zip(facts, audit['facts']):
        fact['citations'] = [{k:r[k] for k in ('source_id','quote','start','end')} for r in item['spans']]
    for claim, item in zip(resolved['claims'], audit['claims']):
        claim['citations'] = [{k:r[k] for k in ('source_id','quote')} for r in item['spans']]
    coverage_record = dict(coverage.model_dump(), citations=rows,
                          semantic_verification='NOT_ESTABLISHED')
    return resolved, facts, coverage_record, audit
