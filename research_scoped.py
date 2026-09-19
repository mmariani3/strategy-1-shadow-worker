"""v6 exact anchored occurrences and claim-specific research completeness.

No historical response is upgraded in place. No qualification or order authority.
"""
import json

from evidence_review import Strict, canonical, digest
from research_coverage import (CoverageDraft, MaterialityCoverage, SpanResolver,
    _resolve_coverage_draft, coverage_evidence_message, prepare_coverage_request)

VERSIONS = ('1.5.0-automated-research', 'governed-research-v6')


class MissingDocumentReason(Strict):
    document: str
    reason: str


class ScopedCoverage(MaterialityCoverage):
    assessment_scope: str
    missing_document_reasons: list[MissingDocumentReason]


class ScopedDraft(CoverageDraft):
    materiality_coverage: ScopedCoverage


INSTRUCTIONS_V6 = '''
CONTRACT v6 overrides earlier citation uniqueness and coverage syntax.
Use the supplied schema, including materiality_coverage.assessment_scope and
missing_document_reasons (one {document, reason} for each missing_documents entry).

A citation must match EXACTLY at one original source location that overlaps the
selected excerpt anchor and stays in its original source field. Repetition
elsewhere in the source is permitted only when the anchor distinguishes exactly
one occurrence. If two occurrences overlap the same anchor, choose a longer exact
clause that disambiguates them. Do not invent a handle or edit punctuation. The
server derives and validates source offsets; the model cannot supply offsets.

Evidence completeness is specific to the proposed materiality assessment. State
that narrow assessment in assessment_scope. For each missing document explain
which necessary fact it would establish and why captured evidence cannot establish
that fact. List only documents needed for this assessment, not all imaginable
follow-up documents. Keep optional corroboration and separate criterion gaps in
their own rationales or limitations, not mandatory materiality prerequisites.
Do not invent a universal primary-source, SEC-filing, original-analyst-note or
independent-news requirement. Apply the governing masters' source rules. A named
credible analyst action reported by reputable financial news can support a limited
analyst-action research classification without automatically needing the original
note or a company filing. This is not automatic acceptance of any news article.
Do not waive a required document or known contradiction. If an economic conclusion
depends on absent terms, exhibits or financial impact, explain that dependency and
keep coverage INCOMPLETE; if the needed basis is unknown, use UNRESOLVED.
A planned/conditional transaction is not completed financing or guaranteed revenue.
Mentioning a document is not supplying its contents. Missing-document reasons and
scope are model judgments, not independent semantic verification.

Sufficient materiality coverage does not clear freshness, cross-source verification,
watchlist eligibility, setup, risk or prospective confirmation. Preserve all prior
capability and fact prerequisites. Independent corroboration must still be assessed
separately; syndication is not independence. Do not infer exact event time from
publication time, invent a freshness threshold, or turn research into a trade.
'''


def scoped_evidence_message(packet):
    view = json.loads(coverage_evidence_message(packet)['content'].split('\n', 1)[1])
    view['citation_policy'] = 'UNIQUE_ANCHORED_SAME_FIELD_OCCURRENCE_V2'
    return {'role': 'user', 'content': 'UNTRUSTED_CAPTURED_EVIDENCE_SCOPED_V2:\n' + canonical(view)}


def prepare_scoped_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import ReviewBlocked
    request = prepare_coverage_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    request['implementation_version'], request['prompt_version'] = VERSIONS
    body = request['body']
    body['input'][0]['content'] += '\n' + INSTRUCTIONS_V6
    body['input'][-1] = scoped_evidence_message(packet)
    body['text']['format']['schema'] = ScopedDraft.model_json_schema()
    if len(canonical(body).encode('utf-8')) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    request['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=body))
    return request


class AnchoredResolver(SpanResolver):
    def resolve(self, selections):
        from research_reviewer import ReviewBlocked
        spans = []; seen = set()
        for selection in selections:
            row = self.catalog.get(selection.excerpt_id)
            if row is None:
                raise ReviewBlocked('EXCERPT_NOT_SELECTABLE')
            support = selection.supporting_text
            if not support.strip():
                raise ReviewBlocked('SUPPORT_TEXT_REQUIRED')
            source = self.sources[row['source_id']]
            value = source['raw']
            for part in row['path']:
                value = value[part]
            quote = canonical(support)[1:-1]
            if isinstance(value, str):
                leaf = canonical(value)[1:-1]
                # Preserve the existing unique-field catalogue boundary. Repeated
                # entire fields remain unresolved, not guessed from nearby keys.
                if support not in value or source['text'].count(leaf) != 1:
                    raise ReviewBlocked('SUPPORT_TEXT_OUTSIDE_SOURCE_FIELD')
                lower = source['text'].index(leaf); upper = lower + len(leaf)
            else:
                lower, upper = row['start'], row['end']
            matches = []
            cursor = lower
            while True:
                start = source['text'].find(quote, cursor, upper)
                if start < 0:
                    break
                end = start + len(quote)
                if start < row['end'] and end > row['start']:
                    matches.append((start, end))
                cursor = start + 1  # Include overlapping occurrences too.
            if len(matches) != 1:
                raise ReviewBlocked('SUPPORT_TEXT_ANCHOR_MISSING_OR_AMBIGUOUS')
            start, end = matches[0]
            identity = (row['source_id'], start, end)
            if identity in seen:
                raise ReviewBlocked('DUPLICATE_SOURCE_SPAN')
            seen.add(identity)
            spans.append(dict(source_id=row['source_id'], quote=quote, start=start,
                end=end, anchor_excerpt_id=selection.excerpt_id, category=row['category']))
        return spans


def resolve_scoped_draft(packet, text):
    from research_reviewer import ReviewBlocked
    draft = ScopedDraft.model_validate_json(text)
    coverage = draft.materiality_coverage
    names = coverage.missing_documents
    reasons = coverage.missing_document_reasons
    if not coverage.assessment_scope.strip():
        raise ReviewBlocked('MATERIALITY_ASSESSMENT_SCOPE_REQUIRED')
    if (len(names) != len(set(names)) or len(reasons) != len(names)
            or {r.document for r in reasons} != set(names)
            or any(not r.reason.strip() for r in reasons)):
        raise ReviewBlocked('MISSING_DOCUMENT_REASON_MISMATCH')
    converted = draft.model_dump()
    converted['materiality_coverage'].pop('assessment_scope')
    converted['materiality_coverage'].pop('missing_document_reasons')
    resolved, facts, record, audit = _resolve_coverage_draft(
        packet, canonical(converted), AnchoredResolver(packet))
    record.update(assessment_scope=coverage.assessment_scope,
                  missing_document_reasons=[r.model_dump() for r in reasons])
    return resolved, facts, record, audit
