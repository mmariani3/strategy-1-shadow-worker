"""Source-bound condition/timing assessment; no paid calls or automatic approval."""
from copy import deepcopy
from contextlib import closing
from pathlib import Path
from typing import Literal
import json
import sqlite3
from pydantic import Field, StrictInt
from evidence_review import Strict, aware, canonical, digest
from research_fields import VERSIONS, validate_field_request, field_checklist
from research_explicit import VERSIONS as PREVIOUS
from research_explicit_review import explicit_review, render_explicit_review
from research_reviewer import parse_response, ReviewBlocked

VERSION = '1.0.0-condition-timing-review'


def field_review(packet, request, response, received_at, reference):
    from research_roles import VERSIONS as ROLE_VERSIONS, validate_role_request, role_checklist
    from research_nature import VERSIONS as NATURE_VERSIONS, validate_nature_request, nature_checklist
    from research_binding import VERSIONS as BINDING_VERSIONS, validate_binding_request, binding_checklist
    from research_completeness import VERSIONS as COMPLETENESS_VERSIONS, validate_completeness_request, completeness_checklist
    versions = (request.get('implementation_version'), request.get('prompt_version'))
    projected_response = response
    if versions in (ROLE_VERSIONS, NATURE_VERSIONS, BINDING_VERSIONS, COMPLETENESS_VERSIONS):
        binding_request = validate_completeness_request(packet, request)[1] if versions == COMPLETENESS_VERSIONS else request
        nature_request = validate_binding_request(packet, binding_request)[1] if versions in (BINDING_VERSIONS, COMPLETENESS_VERSIONS) else request
        role_request = validate_nature_request(packet, nature_request)[1] if versions in (NATURE_VERSIONS, BINDING_VERSIONS, COMPLETENESS_VERSIONS) else request
        _, field_request = validate_role_request(packet, role_request)
        _, previous = validate_field_request(packet, field_request)
        # Projection is for the frozen v21 exporter only. The report below
        # restores the exact original text, wrapper and provider envelope.
        projected_response = deepcopy(response)
        for message in projected_response.get('output', []):
            if message.get('type') == 'message':
                for part in message.get('content', []):
                    if part.get('type') == 'output_text':
                        raw = json.loads(part['text'])
                        part['text'] = canonical({k:v for k,v in raw.items() if k not in ('meaning_contract','term_classifications','materiality_term_indices','materiality_clause_roles','economic_source_coverage')})
    elif versions == VERSIONS:
        _, previous = validate_field_request(packet, request)
    elif versions == PREVIOUS:
        previous = request
    else: raise ReviewBlocked('FIELD_REVIEW_REQUIRES_V21_V22_OR_V23')
    result = parse_response(packet, request, response, received_at)
    # The v21 projection is only an internal export adapter. Replace every
    # request-specific identity and contract before exposing the final report.
    report = explicit_review(packet, previous, projected_response, received_at, reference)
    report.update(implementation_version=VERSION, request_id=request['request_id'],
        original_versions=dict(implementation=versions[0], prompt=versions[1]),
        contract_report=deepcopy(result['research_binding']['explicit_response_contract']))
    for item in report['items']:
        item['item_id'] = digest(dict(request_id=request['request_id'], path=item['path'], kind=item['kind'], anchor=item.get('anchor')))
    if versions in (ROLE_VERSIONS, NATURE_VERSIONS, BINDING_VERSIONS, COMPLETENESS_VERSIONS):
        contract = result['research_binding']['explicit_response_contract']
        report.update(implementation_version='1.1.0-condition-context-review',
            original_provider_response=deepcopy(response),original_draft=deepcopy(contract['original_draft']),
            original_response_text=contract['original_response_text'],draft_digest=digest(contract['original_draft']))
        report['field_items'] = role_checklist(report['original_draft'],request['request_id'])
        if versions == NATURE_VERSIONS:
            report['implementation_version'] = '1.2.0-economic-nature-review'
            report['field_items'] = nature_checklist(report['original_draft'],request['request_id'])
        elif versions == BINDING_VERSIONS:
            report['implementation_version'] = '1.3.0-summary-binding-review'
            report['field_items'] = binding_checklist(report['original_draft'],request['request_id'])
        elif versions == COMPLETENESS_VERSIONS:
            report['implementation_version'] = '1.4.0-source-coverage-review'
            report['field_items'] = completeness_checklist(report['original_draft'],request['request_id'])
    else:
        report['field_items'] = field_checklist(report['original_draft'], request['request_id'])
    report['items'].extend(deepcopy(report['field_items']))
    report['field_review_status'] = 'SOURCE_REVIEW_REQUIRED'
    report['limitations'] = [s.replace('the full v21 wrapper', 'the full original wrapper') for s in report['limitations']]
    report['limitations'].append('Field judgments require a named assessor and exact source/draft binding. No semantic truth or independent review is inferred from checklist completion.')
    del report['report_id']; report['report_id'] = digest(report)
    return report


class FieldDecision(Strict):
    item_id: str = Field(min_length=1)
    value_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    finding: Literal['SUPPORTED', 'REVISION_REQUIRED', 'UNRESOLVED']
    rationale: str = Field(min_length=1)
    source_numbers: list[StrictInt] = Field(min_length=1)


class FieldAssessment(Strict):
    report_id: str
    assessor_id: str = Field(min_length=1)
    assessor_kind: Literal['HUMAN', 'AI_IMPLEMENTATION_AUTHOR', 'AI_OTHER']
    reviewed_at: str
    limitations: list[str] = Field(min_length=1)
    decisions: list[FieldDecision]


def record_field_assessment(packet, request, response, received_at, reference, assessment, now):
    """Rebuild from the original inputs; never trust a caller-edited checklist."""
    report = field_review(packet, request, response, received_at, reference)
    a = FieldAssessment.model_validate(assessment)
    if a.report_id != report['report_id']: raise ValueError('FIELD_REPORT_MISMATCH')
    if not a.assessor_id.strip() or a.assessor_id == 'UNASSIGNED': raise ValueError('ASSESSOR_REQUIRED')
    if not all(x.strip() for x in a.limitations): raise ValueError('REVIEW_LIMITATIONS_REQUIRED')
    if not max(aware(received_at), aware(reference['at'])) <= aware(a.reviewed_at) <= aware(now):
        raise ValueError('REVIEW_TIME_INVALID')
    items = {x['item_id']:x for x in report['field_items']}
    if sorted(x.item_id for x in a.decisions) != sorted(items):
        raise ValueError('EXACT_FIELD_REVIEW_SET_REQUIRED')
    sources = {x['number']:x for x in report['source_catalog']}; bound=[]
    for decision in a.decisions:
        item = items[decision.item_id]
        if decision.value_digest != item['value_digest']: raise ValueError('FIELD_VALUE_CHANGED')
        if not decision.rationale.strip(): raise ValueError('FIELD_RATIONALE_REQUIRED')
        numbers = decision.source_numbers
        if len(set(numbers)) != len(numbers) or any(n not in sources for n in numbers):
            raise ValueError('FIELD_SOURCE_SELECTION_INVALID')
        # A metadata-only review cannot support source meaning. Unknown claims
        # still need inspection of substantive source text, including omissions.
        from research_facts import SUBSTANTIVE
        if not any(sources[n]['category'] in SUBSTANTIVE for n in numbers):
            raise ValueError('FIELD_SUBSTANTIVE_SOURCE_REQUIRED')
        bound.append(dict(item=deepcopy(item), decision=deepcopy(assessment['decisions'][len(bound)]),
            sources=[deepcopy(sources[n]) for n in numbers]))
    revisions=[x.item_id for x in a.decisions if x.finding=='REVISION_REQUIRED']
    unresolved=[x.item_id for x in a.decisions if x.finding=='UNRESOLVED']
    status='REVISIONS_REQUIRED' if revisions else 'SOURCE_REVIEW_REQUIRED' if unresolved or not items else 'FIELD_REVIEW_RECORDED'
    out=dict(implementation_version=report['implementation_version'], report_id=report['report_id'], request_id=request['request_id'],
        trace=deepcopy(packet['trace']), original_versions=report['original_versions'],
        original_report=report, assessment=deepcopy(assessment), assessment_digest=digest(assessment),
        verified_decisions=bound, revision_item_ids=revisions, unresolved_item_ids=unresolved,
        status=status, original_admission='NOT_CHANGED', classification='INFRASTRUCTURE_EVALUATION',
        eligible_for_handoff=False, semantic_acceptance='NOT_ESTABLISHED', api_calls=0,
        limitations=['This records assessor-supplied judgments, not machine-verified truth or independent acceptance.',
            'This focused field review does not replace review of categories, core assertions, completeness or other source meaning.'])
    out['review_id']=digest(out)
    return out


def ledger_inputs(ledger_path, request_id, packet):
    with closing(sqlite3.connect(Path(ledger_path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        row=db.execute('select request from requests where id=?',(request_id,)).fetchone()
        if row is None: raise ReviewBlocked('REQUEST_NOT_FOUND')
        request=json.loads(row[0])
        ev={k:dict(at=at,payload=json.loads(v)) for k,at,v in db.execute(
            'select event_type,at,payload from events where request_id=?',(request_id,))}
    if 'FAILED' in ev or not {'RECEIVED','COMPLETED'} <= set(ev):
        raise ReviewBlocked('COMPLETED_ORIGINAL_RESPONSE_REQUIRED')
    received=ev['RECEIVED']
    if parse_response(packet,request,received['payload'],received['at']) != ev['COMPLETED']['payload']:
        raise ReviewBlocked('COMPLETION_HISTORY_MISMATCH')
    return request,received['payload'],received['at']


def main():
    import argparse
    from evidence_pipeline import write_once
    from review_attempts import utc_now
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ledger','packet','reference','output'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--request-id',required=True)
    parser.add_argument('--assessment',type=Path)
    args=parser.parse_args();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    packet=read(args.packet);request,response,at=ledger_inputs(args.ledger,args.request_id,packet)
    reference=read(args.reference)
    report=field_review(packet,request,response,at,reference)
    files=dict(report=str(write_once(args.output,'field-report-'+report['report_id']+'.json',canonical(report)+'\n')),
        html=str(write_once(args.output,'field-report-'+report['report_id']+'.html',render_explicit_review(report))))
    status=report['field_review_status']
    if args.assessment:
        result=record_field_assessment(packet,request,response,at,reference,read(args.assessment),utc_now())
        files['assessment']=str(write_once(args.output,'field-assessment-'+result['review_id']+'.json',canonical(result)+'\n'))
        status=result['status']
    print(canonical(dict(files=files,status=status,api_calls=0,eligible_for_handoff=False)))


if __name__=='__main__':main()
