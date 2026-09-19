"""Versioned, source-bound factual research. No qualification or order authority."""
import json
from typing import Literal

from evidence_review import CRITERIA, Strict, canonical, digest

VERSIONS = ('1.2.0-automated-research', 'governed-research-v3')
TOPICS = ('instrument_identity', 'catalyst_event', 'event_timing',
          'publication_timing', 'document_coverage')
CATALYST_CRITERIA = {'catalyst_freshness', 'catalyst_materiality_tier', 'same_event_verification'}
SUBSTANTIVE = {'DOCUMENT_TEXT', 'NEWS_TEXT'}
STATES = {'INSUFFICIENT_EVIDENCE': 'UNRESOLVED', 'OBSERVED_SUPPORT': 'SUPPORTED',
          'OBSERVED_FAILURE': 'CONTRADICTED'}


class Fact(Strict):
    topic: Literal[TOPICS]
    status: Literal['EVIDENCED', 'UNRESOLVED']
    finding: str
    excerpt_ids: list[str]


class Claim(Strict):
    criterion: Literal[tuple(CRITERIA)]
    evidence_state: Literal[tuple(STATES)]
    rationale: str
    excerpt_ids: list[str]


class FactDraft(Strict):
    facts: list[Fact]
    claims: list[Claim]
    limitations: list[str]


def category(kind, path):
    # This classifies source locations, never the truth or meaning of their content.
    if kind == 'retrieved_document' and path == ('text',):
        return 'DOCUMENT_TEXT'
    if kind == 'news' and path in [('summary',), ('headline_or_event',)]:
        return 'NEWS_TEXT'
    if (kind == 'news' and path == ('event_timestamp',)) or kind == 'filing':
        return 'PUBLICATION_METADATA'
    if kind == 'mover':
        return 'MARKET_SNAPSHOT'
    return 'WORKFLOW_METADATA'


def leaves(value, path=()):
    if isinstance(value, dict):
        for key in sorted(value):
            yield from leaves(value[key], path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from leaves(item, path + (index,))
    else:
        yield path, value


def excerpt_catalog(packet):
    """Add stable handles without changing source text, source IDs, or offsets.

    Every source remains in the full lossless view. The auxiliary catalogue indexes
    uniquely citable spans; it is not a summary or a completeness assertion.
    """
    from research_reviewer import evidence_message
    evidence_message(packet)  # Verify raw/text/digest agreement before deriving spans.
    catalog = {}
    for source in packet['sources']:
        for path, value in leaves(source['raw']):
            if not path:
                continue
            # Split long strings at line boundaries when possible, otherwise by
            # characters. JSON escaping is performed locally, not by the model.
            pieces = []
            if isinstance(value, str):
                start = 0
                while start < len(value):
                    end = min(start + 1200, len(value))
                    boundary = value.rfind('\n', start + 600, end)
                    if boundary >= 0:
                        end = boundary + 1
                    pieces.append((value[start:end], canonical(value[start:end])[1:-1]))
                    start = end
            else:
                pieces = [(canonical(value), canonical(path[-1]) + ':' + canonical(value))]
            for display, quote in pieces:
                if not quote or source['text'].count(quote) != 1:
                    continue  # Repeated spans stay visible in the complete evidence.
                start = source['text'].index(quote)
                entry = dict(source_id=source['source_id'], path=list(path),
                    category=category(source['kind'], path), text=display,
                    quote=quote, start=start, end=start+len(quote))
                handle = 'E' + digest({k: entry[k] for k in ('source_id', 'start', 'end')})[:20]
                if handle in catalog and catalog[handle] != entry:
                    raise ValueError('EXCERPT_ID_COLLISION')
                catalog[handle] = entry
    return catalog


def fact_evidence_message(packet):
    from research_reviewer import evidence_message
    view = json.loads(evidence_message(packet)['content'].split('\n', 1)[1])
    catalog = excerpt_catalog(packet)
    # Exact encoded quotes and offsets are reconstructed locally on receipt.
    visible = {key: {k: v for k, v in row.items() if k not in ('quote', 'start', 'end')}
               for key, row in catalog.items()}
    return {'role': 'user', 'content': 'UNTRUSTED_CAPTURED_EVIDENCE_WITH_EXCERPTS_V1:\n' +
            canonical({'packet': view, 'excerpt_catalog': visible})}


INSTRUCTIONS = '''
FACT-FIRST RESEARCH CONTRACT v3 (replaces the old output/quote instructions):
First read the substantive source documents. Return five separate fact findings:
instrument_identity (the exact security, e.g. stock versus subscription rights),
catalyst_event (what happened, to whom, and whether different sources match),
event_timing (when the underlying event or NEW announcement occurred),
publication_timing (article/filing dates separately), and document_coverage
(what the captured body establishes, and referenced exhibits that are absent).
Use UNRESOLVED for insufficient evidence, including missing material exhibits.
Do not simply repeat unresolved collector metadata when the document supplies facts.
Never infer an actual event time from a filing/publication timestamp alone.

Then assess the criteria. OBSERVED_FAILURE requires affirmative substantive
evidence of a failed criterion; absent reviews, null fields, a missing setup,
REVIEW_REQUIRED or unexplained-mover metadata are INSUFFICIENT_EVIDENCE instead.
Old workflow fields record process state, not substantive catalyst facts. Assess
newly captured documents even when the original workflow review is still pending.
Keep the instrument/universe question separate from spread, volume and liquidity;
the general price guideline is not an absolute new threshold or a liquidity test.
An earnings preview is not an earnings release. A filing cover referring to absent
financial exhibits does not establish a results surprise. Same ticker is not same
event. Two captured copies do not establish independent sources.

This document-research adapter can substantively assess only catalyst_freshness,
catalyst_materiality_tier, and same_event_verification. The other criteria MUST be
INSUFFICIENT_EVIDENCE: this adapter has no accepted measurement/current-review
adapter for market, liquidity, participation, setup, risk, prospective confirmation,
current approvals or macro clearance. Explain that scope rather than asserting a
failure. An empty macro calendar is not clearance. These are research capability
limits, not new Strategy Rules. No research output qualifies a trade.

For any OBSERVED_SUPPORT or OBSERVED_FAILURE, cite DOCUMENT_TEXT or NEWS_TEXT
excerpt IDs, not workflow/publication metadata. Freshness additionally needs an
EVIDENCED event_timing finding; materiality needs EVIDENCED instrument_identity,
catalyst_event and document_coverage findings. Same-event assessment needs at least
two distinct substantive source IDs; this still does not prove independence.
Keep insufficient criteria unresolved; never invent thresholds to fill policy gaps.
Use only supplied excerpt IDs in excerpt_ids. Do NOT copy quotes, invent IDs,
cite packet IDs, or use governing-document IDs as evidence IDs. Cite the excerpt
whose content supports the finding, not just a nearby passage. Repeated/unindexed
text remains visible in the full packet but cannot be cited with an invented handle.
All facts and rationales remain model judgments needing semantic review.
Return only the new strict schema: facts, claims, limitations.
'''


def prepare_fact_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import prepare_request, ReviewBlocked
    request = prepare_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    request['implementation_version'], request['prompt_version'] = VERSIONS
    body = request['body']
    body['input'][0]['content'] += '\n' + INSTRUCTIONS
    body['input'][-1] = fact_evidence_message(packet)
    body['text']['format']['schema'] = FactDraft.model_json_schema()
    if len(canonical(body).encode('utf-8')) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    request['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=body))
    return request


def resolve_draft(packet, text):
    from research_reviewer import ReviewBlocked
    draft = FactDraft.model_validate_json(text)
    if len(draft.facts) != len(TOPICS) or {f.topic for f in draft.facts} != set(TOPICS):
        raise ReviewBlocked('FACT_TOPICS_INCOMPLETE_OR_DUPLICATE')
    if len(draft.claims) != len(CRITERIA) or {c.criterion for c in draft.claims} != set(CRITERIA):
        raise ReviewBlocked('CRITERIA_INCOMPLETE_OR_DUPLICATE')
    catalog = excerpt_catalog(packet)

    def resolve(ids):
        if len(set(ids)) != len(ids) or any(i not in catalog for i in ids):
            raise ReviewBlocked('UNKNOWN_OR_DUPLICATE_EXCERPT')
        return [catalog[i] for i in ids]

    facts = {f.topic: f for f in draft.facts}
    factual_rows = []
    for fact in draft.facts:
        rows = resolve(fact.excerpt_ids)
        if not fact.finding.strip():
            raise ReviewBlocked('FACT_FINDING_REQUIRED')
        if fact.status == 'EVIDENCED':
            allowed = SUBSTANTIVE | ({'PUBLICATION_METADATA'} if fact.topic == 'publication_timing' else set())
            if not rows or any(r['category'] not in allowed for r in rows):
                raise ReviewBlocked('FACT_SUBSTANTIVE_SOURCE_REQUIRED')
        factual_rows.append(dict(fact.model_dump(), citations=[{k:r[k] for k in ('source_id','quote','start','end')} for r in rows]))
    claims = []
    for claim in draft.claims:
        rows = resolve(claim.excerpt_ids)
        if claim.evidence_state != 'INSUFFICIENT_EVIDENCE':
            if claim.criterion not in CATALYST_CRITERIA:
                raise ReviewBlocked('OUTSIDE_DOCUMENT_RESEARCH_CAPABILITY')
            if not rows or any(r['category'] not in SUBSTANTIVE for r in rows):
                raise ReviewBlocked('CLAIM_SUBSTANTIVE_SOURCE_REQUIRED')
            required = {'catalyst_freshness': ['event_timing'],
                        'catalyst_materiality_tier': ['instrument_identity','catalyst_event','document_coverage']}.get(claim.criterion, [])
            if any(facts[name].status != 'EVIDENCED' for name in required):
                raise ReviewBlocked('REQUIRED_FACT_UNRESOLVED')
            if claim.criterion == 'same_event_verification' and len({r['source_id'] for r in rows}) < 2:
                raise ReviewBlocked('SAME_EVENT_REQUIRES_DISTINCT_SOURCES')
        claims.append(dict(criterion=claim.criterion, assessment=STATES[claim.evidence_state],
            rationale=claim.rationale, citations=[dict(source_id=r['source_id'], quote=r['quote']) for r in rows]))
    return {'claims': claims, 'limitations': draft.limitations}, factual_rows
