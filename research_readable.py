"""v12 readable exact quotes with deterministic source encoding.

v11 is frozen, including its incorrect encoded-quote contract. This adapter never
repairs prose, whitespace, punctuation or a historical response. New requests
explicitly ask for readable excerpt text; only JSON representation is encoded.
"""
from evidence_review import canonical, digest
from research_support import (SupportDraft, INSTRUCTIONS as SUPPORT_INSTRUCTIONS,
    prepare_support_request, validate_support_request, resolve_support_draft)
from research_citations import selectable_catalog

VERSIONS = ('1.11.0-automated-research', 'governed-research-v12')
INSTRUCTIONS = SUPPORT_INSTRUCTIONS.replace('v11', 'v12').replace('V11', 'V12').replace(
    "copied from the selected\nexcerpt's quote string", "copied from selectable_excerpts[excerpt_id].text")
INSTRUCTIONS += '''
READABLE QUOTE CONTRACT: quote contains the exact readable text from the selected
excerpt's text field, using ordinary JSON escaping in your response. Preserve
newlines, spaces, punctuation and Unicode exactly. Do not double-escape it to
match packet source.text. The host performs deterministic JSON encoding and
derives the original offsets; it never normalizes, fuzzy-matches or repairs text.
Every quote must be a unique contiguous substring within its selected excerpt.
'''


def prepare_readable_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import ReviewBlocked
    r = prepare_support_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0]['content'] = r['body']['input'][0]['content'].replace(SUPPORT_INSTRUCTIONS, INSTRUCTIONS, 1)
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def validate_readable_request(packet, r):
    validate_support_request(packet, r)


def resolve_readable_draft(packet, text):
    from research_reviewer import ReviewBlocked
    d = SupportDraft.model_validate_json(text)
    converted = d.model_dump(); catalog = selectable_catalog(packet)
    groups = [c for s in converted['support'] for c in s['clauses']] + converted['context_notes']
    original_groups = [c.model_dump() for s in d.support for c in s.clauses] + [n.model_dump() for n in d.context_notes]
    for group in groups:
        for q in group['quotes']:
            row = catalog.get(q['excerpt_id'])
            if row is None: raise ReviewBlocked('EXCERPT_NOT_SELECTABLE')
            if not q['quote'].strip() or row['text'].count(q['quote']) != 1:
                raise ReviewBlocked('READABLE_QUOTE_MISSING_OR_AMBIGUOUS')
            q['quote'] = canonical(q['quote'])[1:-1]
    resolved, facts, coverage, audit, binding = resolve_support_draft(packet, canonical(converted))
    support = binding['support_review']
    recorded = [c for s in support['clauses'] for c in s['clauses']] + support['context_notes']
    for group, original in zip(recorded, original_groups):
        group['quotes'] = original['quotes']
        for cite, quote in zip(group['citations'], original['quotes']):
            cite['readable_quote'] = quote['quote']
    support.update(implementation_version=VERSIONS[0], quote_contract='READABLE_EXACT_QUOTE_V1')
    return resolved, facts, coverage, audit, binding
