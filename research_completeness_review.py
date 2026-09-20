"""Attributed, offline checklist review; never automated semantic acceptance."""
from typing import Literal
from pydantic import Field, StrictInt, StrictStr
from evidence_review import Strict, canonical, digest, aware
from research_reference_coverage import audit_reference_coverage

VERSION = '1.0.0-scoped-completeness-review'
ASPECTS = ('FEES_AND_ECONOMIC_TERMS', 'CONDITIONS', 'TIMING', 'COUNTEREVIDENCE')


class DraftEvidence(Strict):
    path: list[StrictStr | StrictInt] = Field(min_length=1)
    value_digest: str = Field(pattern=r'^[0-9a-f]{64}$')


class AnchorDecision(Strict):
    anchor_id: str = Field(min_length=1)
    relevance: Literal['REQUIRED_FOR_SCOPE', 'OPTIONAL_CONTEXT', 'UNRESOLVED']
    finding: Literal['PRESERVED', 'MATERIAL_OMISSION', 'MEANING_ERROR', 'CITATION_GAP', 'UNRESOLVED']
    rationale: str = Field(min_length=1)
    draft_evidence: list[DraftEvidence] = Field(min_length=1)


class AspectDecision(Strict):
    aspect: Literal[ASPECTS]
    status: Literal['REVIEWED', 'NOT_APPLICABLE', 'UNRESOLVED']
    anchor_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class Assessment(Strict):
    audit_id: str
    scope: str = Field(min_length=1)
    assessor_id: str = Field(min_length=1)
    assessor_kind: Literal['HUMAN', 'AI_IMPLEMENTATION_AUTHOR', 'AI_OTHER']
    reviewed_at: str
    limitations: list[str] = Field(min_length=1)
    anchors: list[AnchorDecision]
    aspects: list[AspectDecision]


def draft_value(draft, path):
    value = draft
    for key in path:
        if isinstance(value, dict) and isinstance(key, str) and key in value: value = value[key]
        elif isinstance(value, list) and type(key) is int and 0 <= key < len(value): value = value[key]
        else: raise ValueError('DRAFT_EVIDENCE_PATH_INVALID')
    return value


def prepare_checklist(packet, request, draft, reference):
    audit = audit_reference_coverage(packet, request, draft, reference)
    ids = [r['anchor']['id'] for r in audit['rows']]
    return dict(audit_id=audit['audit_id'],scope=draft['materiality_coverage']['assessment_scope'],
        assessor_id='UNASSIGNED',assessor_kind='AI_OTHER',reviewed_at='',
        limitations=['Template only; judgments and assessor attribution must be supplied after source/prose review.'],
        anchors=[dict(anchor_id=i,relevance='UNRESOLVED',finding='UNRESOLVED',rationale='Source and prose review pending.',
            draft_evidence=[dict(path=['materiality_coverage'],value_digest=digest(draft['materiality_coverage']))]) for i in ids],
        aspects=[dict(aspect=a,status='UNRESOLVED',anchor_ids=ids,rationale='Scope-specific review pending.') for a in ASPECTS])


def record_completeness_review(packet, request, draft, reference, assessment, now):
    audit = audit_reference_coverage(packet, request, draft, reference)
    review = Assessment.model_validate(assessment)
    if review.audit_id != audit['audit_id']: raise ValueError('COMPLETENESS_AUDIT_MISMATCH')
    if review.scope != draft['materiality_coverage']['assessment_scope']:
        raise ValueError('COMPLETENESS_SCOPE_MISMATCH')
    if review.assessor_id == 'UNASSIGNED': raise ValueError('ASSESSOR_REQUIRED')
    when = aware(review.reviewed_at)
    if when < aware(reference['at']) or when > aware(now): raise ValueError('REVIEW_TIME_INVALID')
    rows = {r['anchor']['id']:r for r in audit['rows']}
    if sorted(x.anchor_id for x in review.anchors) != sorted(rows):
        raise ValueError('COMPLETE_ANCHOR_REVIEW_REQUIRED')
    if sorted(x.aspect for x in review.aspects) != sorted(ASPECTS):
        raise ValueError('COMPLETE_ASPECT_REVIEW_REQUIRED')
    evidence = []
    for item in review.anchors:
        if item.finding == 'MATERIAL_OMISSION' and item.relevance != 'REQUIRED_FOR_SCOPE':
            raise ValueError('MATERIAL_OMISSION_REQUIRES_SCOPE_RELEVANCE')
        seen = set()
        for ref in item.draft_evidence:
            key = canonical(ref.path)
            if key in seen: raise ValueError('DUPLICATE_DRAFT_EVIDENCE')
            seen.add(key); value = draft_value(draft, ref.path)
            if digest(value) != ref.value_digest: raise ValueError('DRAFT_EVIDENCE_CHANGED')
            evidence.append(dict(anchor_id=item.anchor_id,path=ref.path,value=value,value_digest=ref.value_digest))
    for aspect in review.aspects:
        if len(set(aspect.anchor_ids)) != len(aspect.anchor_ids) or not set(aspect.anchor_ids) <= set(rows):
            raise ValueError('ASPECT_REFERENCE_INVALID')
    changes = [a.anchor_id for a in review.anchors if a.finding in ('MATERIAL_OMISSION','MEANING_ERROR','CITATION_GAP')]
    unresolved = [a.anchor_id for a in review.anchors if a.relevance == 'UNRESOLVED' or a.finding == 'UNRESOLVED']
    pending = [a.aspect for a in review.aspects if a.status == 'UNRESOLVED']
    status = 'REVISIONS_REQUIRED' if changes else 'REVIEW_REQUIRED' if unresolved or pending or audit['invalid_selections'] else 'SCOPED_REVIEW_RECORDED'
    result = dict(implementation_version=VERSION,audit_id=audit['audit_id'],packet_id=packet['packet_id'],trace=packet['trace'],
        request_id=request['request_id'],draft_digest=digest(draft),reference_digest=digest(reference),assessment_digest=digest(assessment),
        assessment=assessment,verified_draft_evidence=evidence,source_rows=audit['rows'],
        status=status,revision_anchor_ids=changes,unresolved_anchor_ids=unresolved,unresolved_aspects=pending,
        invalid_selections=audit['invalid_selections'],original_coverage_status=draft['materiality_coverage']['status'],
        summary_completeness='NOT_ESTABLISHED',semantic_acceptance='NOT_ESTABLISHED',eligible_for_handoff=False,
        classification='INFRASTRUCTURE_EVALUATION',assessor_independence='NOT_ESTABLISHED_BY_SOFTWARE',
        original_admission='NOT_EVALUATED_OR_CHANGED',
        limitation='Software verifies attribution, source/draft binding and checklist coverage only. Judgments remain assessor-supplied; even a fully reviewed supplied checklist cannot certify complete source understanding or strategy qualification.')
    result['review_id'] = digest(result)
    return result


def main():
    import argparse, json
    from pathlib import Path
    from evidence_pipeline import write_once
    from review_attempts import utc_now
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('packet','request','draft','reference','output'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--assessment',type=Path)
    args=parser.parse_args();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    inputs=[read(getattr(args,k)) for k in ('packet','request','draft','reference')]
    if args.assessment:
        result=record_completeness_review(*inputs,read(args.assessment),utc_now());kind='review'
    else: result=prepare_checklist(*inputs);kind='template'
    path=write_once(args.output,'completeness-'+kind+'-'+digest(result)+'.json',canonical(result)+'\n')
    print(canonical(dict(path=str(path),kind=kind,status=result.get('status','REVIEW_REQUIRED'),eligible_for_handoff=False)))


if __name__ == '__main__': main()
