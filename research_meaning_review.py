"""Attributed offline meaning review of original drafts; no provider or trade path."""
from copy import deepcopy
from html import escape
import json
from typing import Literal

from pydantic import Field, StrictInt
from evidence_review import Strict, aware, canonical, digest
from research_completeness_review import DraftEvidence, draft_value
from research_linked import numbered_passages, numbered_rules
from research_facts import SUBSTANTIVE
from research_omissions import omission_report
from research_review_view import review_view, render_view

VERSION = '1.0.1-source-meaning-review'
QUESTIONS = {
    'RULE_APPLICATION': 'Does the selected event establish this individual rule? Identify the exact event/fact and source support. A matching tier label, future approval requirement or general strategic context is insufficient.',
    'TIMING': 'Separate announcement/publication, event occurrence, commitment, payment/effective date and future calls. Does each cited clause establish the asserted date or time? Leave unavailable timing unresolved.',
    'ECONOMIC_TERM': 'Review all facets and their reasons together. Preserve who owes what, present commitment versus future funding, conditions versus assumptions, forecasts and downside. Source silence cannot establish a condition or its absence.',
    'SOURCE_ANCHOR': 'Compare the entire source anchor, including continuations, with the full answer and stated scope. Record required versus optional relevance. Generic caution or a document followup does not preserve a disclosed risk.',
}


def passage_numbers(value):
    """Read exact selections, without guessing support from text or tier labels."""
    if isinstance(value, list):
        return [n for v in value for n in passage_numbers(v)]
    if isinstance(value, dict):
        return list(value.get('passages', [])) + [n for k, v in value.items()
            if k != 'passages' for n in passage_numbers(v)]
    return []


def meaning_dossier(packet, request, draft, reference):
    if request.get('prompt_version') not in ('governed-research-v17', 'governed-research-v18', 'governed-research-v19','governed-research-v20'):
        raise ValueError('MEANING_REVIEW_REQUIRES_SINGLE_SCOPE_DRAFT')
    report = omission_report(packet, request, draft, reference)
    # The preceding audit verifies the exact request and authority text. Read the
    # frozen governing catalog used for THIS answer, never today's renumbered copy.
    masters = json.loads(request['body']['input'][0]['content'].split(
        '\nGOVERNING_MASTERS:\n', 1)[1].split('\nCRITERION_REFERENCES:\n', 1)[0])
    rules = numbered_rules(masters)
    prefix = ['research'] if 'research' in draft else []
    research = draft_value(draft, prefix)
    rows = []

    def add(kind, path, **extra):
        value = draft_value(draft, path)
        row = dict(kind=kind, path=path, original_value=deepcopy(value),
            value_digest=digest(value), question=QUESTIONS[kind], **extra)
        row['item_id'] = digest(dict(kind=kind, path=path, extra=extra))
        rows.append(row)

    for i, number in enumerate(research['tier_proposal']['rules']):
        add('RULE_APPLICATION', prefix + ['tier_proposal', 'rules', i],
            rule_number=number, governing_rule=deepcopy(rules.get(number)),
            original_proposal=deepcopy(research['tier_proposal']),
            candidate_facts=[dict(path=prefix+['facts', j], original_value=deepcopy(f))
                for j, f in enumerate(research['facts'])
                if f['topic'] in research['tier_proposal']['fact_topics']])
    # No selected rules is still an explicit review item, not a vacuous pass.
    if not research['tier_proposal']['rules']:
        add('RULE_APPLICATION', prefix + ['tier_proposal'], rule_number=None,
            governing_rule=None, original_proposal=deepcopy(research['tier_proposal']))
    for i, fact in enumerate(research['facts']):
        if fact['topic'] in ('event_timing', 'publication_timing'):
            add('TIMING', prefix + ['facts', i])
    for i in range(len(draft.get('economic_inventory', {}).get('terms', []))):
        add('ECONOMIC_TERM', ['economic_inventory', 'terms', i])
    for row in report['reference_rows']:
        add('SOURCE_ANCHOR', [], anchor=deepcopy(row['anchor']),
            location_status=row['location_status'])
        # Full answer remains accessible once, rather than copied per anchor.
        rows[-1]['original_value'] = dict(assessment_scope=report['assessment_scope'],
            answer_digest=digest(draft))
    result = dict(implementation_version=VERSION, packet_id=packet['packet_id'],
        request_id=request['request_id'], draft_digest=digest(draft),
        reference_digest=digest(reference), omission_report_id=report['report_id'],
        trace=deepcopy(packet['trace']), assessment_scope=report['assessment_scope'],
        original_versions=dict(implementation=request['implementation_version'], prompt=request['prompt_version']),
        items=rows, original_draft=deepcopy(draft),
        source_catalog=[dict(number=n, **deepcopy(p)) for n, p in numbered_passages(packet).items()],
        full_sources=deepcopy(report['source_texts']), invalid_selections=report['invalid_selections'],
        classification='INFRASTRUCTURE_EVALUATION', eligible_for_handoff=False,
        original_admission='NOT_EVALUATED_OR_CHANGED', semantic_acceptance='NOT_ESTABLISHED',
        limitation='A review checklist, not a semantic classifier. It covers selected rules, timing facts, recorded terms and supplied anchors, not every possible assertion or omitted fact. Full sources and original prose remain available. No automatic strategy prerequisites or importance thresholds.')
    result['dossier_id'] = digest(result)
    return result


class MeaningDecision(Strict):
    item_id: str
    relevance: Literal['REQUIRED_FOR_SCOPE', 'OPTIONAL_CONTEXT', 'UNRESOLVED']
    finding: Literal['SUPPORTED', 'UNSUPPORTED', 'MEANING_ERROR', 'MATERIAL_OMISSION', 'CITATION_GAP', 'UNRESOLVED', 'NOT_APPLICABLE']
    rationale: str = Field(min_length=1)
    draft_evidence: list[DraftEvidence] = Field(min_length=1)
    source_passages: list[StrictInt]


class MeaningAssessment(Strict):
    dossier_id: str
    assessor_id: str = Field(min_length=1)
    assessor_kind: Literal['HUMAN', 'AI_IMPLEMENTATION_AUTHOR', 'AI_OTHER']
    reviewed_at: str
    limitations: list[str] = Field(min_length=1)
    decisions: list[MeaningDecision]


def meaning_template(dossier):
    return dict(dossier_id=dossier['dossier_id'], assessor_id='UNASSIGNED',
        assessor_kind='AI_OTHER', reviewed_at='',
        limitations=['Template only. Source review and assessor attribution are required.'],
        decisions=[dict(item_id=r['item_id'], relevance='UNRESOLVED', finding='UNRESOLVED',
            rationale='Review pending.', draft_evidence=[dict(path=r['path'] or ['assessment_scope'],
                value_digest=digest(draft_value(dossier['original_draft'], r['path'] or ['assessment_scope'])))],
            source_passages=[]) for r in dossier['items']])


def record_meaning_review(packet, request, draft, reference, assessment, now):
    dossier = meaning_dossier(packet, request, draft, reference)
    review = MeaningAssessment.model_validate(assessment)
    if review.dossier_id != dossier['dossier_id']: raise ValueError('MEANING_DOSSIER_MISMATCH')
    if review.assessor_id == 'UNASSIGNED': raise ValueError('ASSESSOR_REQUIRED')
    when = aware(review.reviewed_at)
    if when < aware(reference['at']) or when > aware(now):
        raise ValueError('REVIEW_TIME_INVALID')
    items = {r['item_id']:r for r in dossier['items']}
    if sorted(d.item_id for d in review.decisions) != sorted(items):
        raise ValueError('COMPLETE_MEANING_REVIEW_REQUIRED')
    catalog = numbered_passages(packet); verified = []; revisions = []; pending = []
    prefix = ['research'] if 'research' in draft else []
    for d in review.decisions:
        item = items[d.item_id]; paths = set(); evidence = []; direct_fact = False
        if len(set(d.source_passages)) != len(d.source_passages) or any(n not in catalog for n in d.source_passages):
            raise ValueError('MEANING_SOURCE_SELECTION_INVALID')
        for ref in d.draft_evidence:
            key = canonical(ref.path)
            if key in paths: raise ValueError('DUPLICATE_DRAFT_EVIDENCE')
            paths.add(key); value = draft_value(draft, ref.path)
            if digest(value) != ref.value_digest: raise ValueError('DRAFT_EVIDENCE_CHANGED')
            evidence.append(dict(path=ref.path, value=deepcopy(value), value_digest=ref.value_digest))
            is_fact = (ref.path[:len(prefix)+1] == prefix+['facts'] and len(ref.path) == len(prefix)+2
                and isinstance(value, dict) and value.get('topic') == 'catalyst_event')
            is_event = ref.path == prefix+['selected_event']
            substantive = {n for n in d.source_passages if catalog[n]['category'] in SUBSTANTIVE}
            if (is_fact or is_event) and set(passage_numbers(value)) & substantive: direct_fact = True
        if item['kind'] in ('TIMING', 'ECONOMIC_TERM') and not any(
                ref.path[:len(item['path'])] == item['path'] for ref in d.draft_evidence):
            raise ValueError('MEANING_ITEM_DRAFT_EVIDENCE_REQUIRED')
        if item['kind'] != 'SOURCE_ANCHOR' and d.relevance == 'OPTIONAL_CONTEXT':
            raise ValueError('ASSERTED_MEANING_CANNOT_BE_OPTIONAL')
        if d.finding != 'UNRESOLVED' and not d.source_passages:
            raise ValueError('MEANING_SOURCE_EVIDENCE_REQUIRED')
        if item['kind'] == 'RULE_APPLICATION' and d.finding == 'SUPPORTED':
            if (item['governing_rule'] is None or not direct_fact
                    or item['original_proposal']['mapping_status'] != 'PROPOSED'
                    or item['governing_rule']['tier'] != item['original_proposal']['proposed_tier']):
                raise ValueError('INDIVIDUAL_RULE_FACT_SUPPORT_REQUIRED')
        if d.finding == 'MATERIAL_OMISSION' and d.relevance != 'REQUIRED_FOR_SCOPE':
            raise ValueError('MATERIAL_OMISSION_REQUIRES_SCOPE_RELEVANCE')
        if d.finding == 'NOT_APPLICABLE' and (item['kind'] != 'SOURCE_ANCHOR' or d.relevance != 'OPTIONAL_CONTEXT'):
            raise ValueError('NOT_APPLICABLE_REQUIRES_OPTIONAL_SOURCE_CONTEXT')
        if d.finding in ('UNSUPPORTED', 'MEANING_ERROR', 'MATERIAL_OMISSION', 'CITATION_GAP'):
            revisions.append(d.item_id)
        if d.finding == 'UNRESOLVED' or d.relevance == 'UNRESOLVED': pending.append(d.item_id)
        verified.append(dict(item_id=d.item_id, draft_evidence=evidence,
            source_evidence=[dict(number=n, **deepcopy(catalog[n])) for n in d.source_passages]))
    result = dict(implementation_version=VERSION, dossier_id=dossier['dossier_id'],
        packet_id=packet['packet_id'], request_id=request['request_id'], trace=deepcopy(packet['trace']),
        draft_digest=digest(draft), reference_digest=digest(reference), assessment_digest=digest(assessment),
        assessment=deepcopy(assessment), verified_evidence=verified,
        status='REVISIONS_REQUIRED' if revisions else 'REVIEW_REQUIRED' if pending or dossier['invalid_selections'] else 'ATTRIBUTED_REVIEW_RECORDED',
        revision_item_ids=revisions, unresolved_item_ids=pending,
        classification='INFRASTRUCTURE_EVALUATION', eligible_for_handoff=False,
        semantic_acceptance='NOT_ESTABLISHED', assessor_independence='NOT_ESTABLISHED_BY_SOFTWARE',
        original_admission='NOT_EVALUATED_OR_CHANGED',
        limitation='Software validates attribution and exact evidence bindings, not the truth of reviewer judgments. Recording a checklist never admits a draft, approves a tier or permits a trading handoff.')
    result['review_id'] = digest(result)
    return result


def render_meaning_review(packet, request, draft, reference, assessment=None, now=None):
    dossier = meaning_dossier(packet, request, draft, reference)
    recorded = record_meaning_review(packet, request, draft, reference, assessment, now) if assessment is not None else None
    report = omission_report(packet, request, draft, reference)
    html = render_view(review_view(packet, request, draft, reference, report))
    e = lambda v: escape(str(v), quote=True)
    pre = lambda v: '<pre>'+e(json.dumps(v, ensure_ascii=False, indent=2, sort_keys=True))+'</pre>'
    blocks = ['<h2 id="meaning-review">Source meaning checklist</h2>',
        '<p class="notice">Every judgment is assessor-supplied. Matching labels and valid citations do not prove meaning. No automatic acceptance or trading approval.</p>',
        '<p class="meta">'+e(VERSION)+' · Dossier '+dossier['dossier_id']+'</p>']
    decisions = {d['item_id']:d for d in recorded['assessment']['decisions']} if recorded else {}
    if recorded: blocks.append('<h3>'+recorded['status']+'</h3>'+pre(recorded['assessment']))
    catalog = dossier['source_catalog']
    for item in dossier['items']:
        blocks.append('<section id="meaning-'+item['item_id']+'"><h3>'+e(item['kind'])+'</h3><p>'+e(item['question'])+'</p>'+pre(item))
        decision = decisions.get(item['item_id'])
        if decision: blocks.append('<strong>Attributed decision</strong>'+pre(decision))
        selected = set(passage_numbers(item['original_value']))
        if decision: selected.update(decision['source_passages'])
        # Neighbors are explicitly contextual. Do not add them to the model's
        # selections or assume one neighbor completes a sentence or source.
        for row in catalog:
            if row['number'] not in selected: continue
            same = [p for p in catalog if (p['source_id'],p['path']) == (row['source_id'],row['path'])]
            i = next(i for i,p in enumerate(same) if p['number'] == row['number'])
            blocks.append('<details><summary>Passage '+str(row['number'])+' and adjacent context</summary>')
            for p in same[max(0,i-1):i+2]:
                blocks.append('<p class="meta">'+('Selected for this review item' if p['number'] in selected else 'Adjacent context only')+' · '+str(p['number'])+'</p>'+pre(p))
            blocks.append('</details>')
        blocks.append('<a href="#sources">Read full captured source and all continuations</a> · <a href="#answer">Read full original answer</a></section>')
    blocks.append('<h3>Meaning review identity</h3>'+pre(dict(dossier_id=dossier['dossier_id'],
        review_id=recorded['review_id'] if recorded else None, trace=dossier['trace'],
        original_versions=dossier['original_versions'], limitation=dossier['limitation'])))
    html = html.replace('<nav>', '<nav><a href="#meaning-review">Meaning checks</a>', 1)
    return html.replace('<h2 id="queue">', ''.join(blocks)+'<h2 id="queue">', 1)


def verify_meaning_html(packet, request, draft, reference, html, assessment=None, now=None):
    if render_meaning_review(packet, request, draft, reference, assessment, now) != html:
        raise ValueError('MEANING_HTML_MISMATCH')


def main():
    import argparse
    from pathlib import Path
    from evidence_pipeline import write_once
    from review_attempts import utc_now
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('packet', 'request', 'draft', 'reference', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--assessment', type=Path)
    args = parser.parse_args(); read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    inputs = [read(getattr(args, name)) for name in ('packet', 'request', 'draft', 'reference')]
    dossier = meaning_dossier(*inputs); assessment = read(args.assessment) if args.assessment else None
    now = utc_now(); result = record_meaning_review(*inputs, assessment, now) if assessment is not None else meaning_template(dossier)
    html = render_meaning_review(*inputs, assessment, now)
    verify_meaning_html(*inputs, html, assessment, now)
    files = {}
    for kind, obj in (('dossier', dossier), ('review' if assessment is not None else 'template', result)):
        files[kind] = str(write_once(args.output, 'meaning-'+kind+'-'+digest(obj)+'.json', canonical(obj)+'\n'))
    files['html'] = str(write_once(args.output, 'meaning-review-'+digest(html)+'.html', html))
    print(canonical(dict(files=files, status=result.get('status', 'REVIEW_REQUIRED'), api_calls=0, eligible_for_handoff=False)))


if __name__ == '__main__': main()
