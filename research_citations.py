"""v4 selection contract: bind readable support words to their actual excerpt.

This verifies location, not entailment. v3 remains immutable for history replay.
"""
import json
from typing import Literal

from pydantic import ConfigDict

from evidence_review import CRITERIA, Strict, canonical, digest
from research_facts import (TOPICS, STATES, SUBSTANTIVE, INSTRUCTIONS,
    excerpt_catalog, resolve_draft)

VERSIONS = ('1.3.0-automated-research', 'governed-research-v4')


class Selection(Strict):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    excerpt_id: str
    supporting_text: str


class SelectedFact(Strict):
    topic: Literal[TOPICS]
    status: Literal['EVIDENCED', 'UNRESOLVED']
    finding: str
    evidence: list[Selection]


class SelectedClaim(Strict):
    criterion: Literal[tuple(CRITERIA)]
    evidence_state: Literal[tuple(STATES)]
    rationale: str
    evidence: list[Selection]


class SelectedDraft(Strict):
    facts: list[SelectedFact]
    claims: list[SelectedClaim]
    limitations: list[str]


def selectable_catalog(packet):
    return {k: v for k, v in excerpt_catalog(packet).items()
            if v['category'] in SUBSTANTIVE | {'PUBLICATION_METADATA'}}


def selection_evidence_message(packet):
    from research_reviewer import evidence_message
    view = json.loads(evidence_message(packet)['content'].split('\n', 1)[1])
    visible = {k: {name: value for name, value in row.items()
                   if name not in ('quote', 'start', 'end')}
               for k, row in selectable_catalog(packet).items()}
    return {'role': 'user', 'content': 'UNTRUSTED_CAPTURED_EVIDENCE_WITH_SELECTIONS_V1:\n' +
            canonical({'packet': view, 'selectable_excerpts': visible})}


SELECTION_INSTRUCTIONS = '''
SELECTION CONTRACT v4 overrides v3 output syntax only; all its substantive
restrictions still apply. Return facts, claims, limitations using the supplied
schema. Replace excerpt_ids with evidence: [{excerpt_id, supporting_text}].
For each selection copy a short, complete supporting clause verbatim from that
exact selectable_excerpts[excerpt_id].text. Copy decoded readable words, using
ordinary JSON string escaping, not the double-escaped source.text encoding.
Re-read the selected text before assigning its ID. Do not quote a nearby excerpt
or another source. The words must support this particular finding or rationale.
Do not use a common label, ticker, or date alone to stand in for the event claim.
If you cannot locate adequate support, keep the item UNRESOLVED or
INSUFFICIENT_EVIDENCE and explain the gap; an empty evidence list is allowed there.
Workflow and market-snapshot fields remain in the full packet for context but
have no selectable handles. Never borrow a document handle to cite them.
PUBLICATION_METADATA may support only publication_timing facts, never underlying
event timing or catalyst conclusions. A new announcement date requires words
stating that announcement, not a filing date alone. Different dates can refer
to approval, agreement, announcement and expected effective dates; separate them.
Do not assign a catalyst tier from the event label alone or invent an age cutoff.
Passed quote checks establish location only, not truth or strategy eligibility.
'''


def prepare_selection_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import prepare_request, ReviewBlocked
    request = prepare_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    request['implementation_version'], request['prompt_version'] = VERSIONS
    body = request['body']
    body['input'][0]['content'] += '\n' + INSTRUCTIONS + '\n' + SELECTION_INSTRUCTIONS
    body['input'][-1] = selection_evidence_message(packet)
    body['text']['format']['schema'] = SelectedDraft.model_json_schema()
    if len(canonical(body).encode('utf-8')) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    request['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=body))
    return request


def resolve_selected_draft(packet, text):
    from research_reviewer import ReviewBlocked
    draft = SelectedDraft.model_validate_json(text)
    catalog = selectable_catalog(packet)
    sources = {s['source_id']: s['text'] for s in packet['sources']}
    converted = draft.model_dump()
    spans = {'facts': [], 'claims': []}
    for group in spans:
        for item in converted[group]:
            selections = item.pop('evidence')
            item['excerpt_ids'] = [s['excerpt_id'] for s in selections]
            rows = []
            for selection in selections:
                row = catalog.get(selection['excerpt_id'])
                if row is None:
                    raise ReviewBlocked('EXCERPT_NOT_SELECTABLE')
                support = selection['supporting_text']
                if not support.strip() or support not in row['text']:
                    raise ReviewBlocked('SUPPORT_TEXT_EXCERPT_MISMATCH')
                quote = canonical(support)[1:-1]
                source_text = sources[row['source_id']]
                start = source_text.find(quote)
                if source_text.count(quote) != 1 or not (row['start'] <= start and
                        start + len(quote) <= row['end']):
                    raise ReviewBlocked('SUPPORT_TEXT_NOT_UNIQUE_IN_SOURCE')
                rows.append(dict(source_id=row['source_id'], quote=quote,
                                 start=start, end=start+len(quote)))
            spans[group].append(rows)
    # Retain every v3 category/capability/prerequisite gate. No repair or relabeling.
    resolved, facts = resolve_draft(packet, canonical(converted))
    for fact, rows in zip(facts, spans['facts']):
        fact['citations'] = rows
    for claim, rows in zip(resolved['claims'], spans['claims']):
        claim['citations'] = [{k: r[k] for k in ('source_id', 'quote')} for r in rows]
    return resolved, facts
