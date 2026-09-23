"""Prepare/check an opt-in structured research contract offline. No dispatch path."""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field, StrictInt, StrictStr

from evidence_review import Strict, canonical, digest
from research_semantics import prepare_semantic_request, semantic_developer, validate_semantic_request
from research_tiers import tier_schema, validate_tier_selection
from research_typed import TypedDraft
from research_linked import numbered_passages, numbered_rules
from research_facts import SUBSTANTIVE

VERSIONS = ('1.0.0-explicit-research-contract', 'governed-research-v21-preview')
INSTRUCTIONS = '''
EXPERIMENTAL v21 OUTPUT CONTRACT: Return a root object with draft,
rule_applications, and term_assertions. draft is the complete unchanged v20 shape.
This preview has no dispatch or trading integration.

For every selected draft.research.tier_proposal.rules number, supply exactly one
rule_applications entry: rule_number, explanation, fact_index (zero based within
draft.research.facts), and passages. Explain why that individual category fits
the selected event. The referenced fact must be an EVIDENCED catalyst_event with
SELECTED_EVENT support; choose substantive passages already cited by that fact.
Do not use category labels alone or select every rule in a tier. If the mapping
cannot be supported, keep the original mapping UNRESOLVED without selected rules
and supply no rule applications. Never force a tier to fill this structure.

For every economic_inventory term, supply exactly one term_assertions entry:
term_index (zero based), status, statement, passages, reason. RECORDED requires
the term's substantive core assertion and full supporting passage numbers, plus
an explanation of the evidence limits. A label or generic forward-looking caution
alone is not the core assertion. Preserve parties, qualifications and timing.
Unknown amounts do not prevent recording an evidenced plan or qualitative forecast.
If the core assertion itself is unavailable, use UNRESOLVED, an empty statement
and empty passages, with a substantive reason. Never invent a value or condition.
Do not claim completeness from required fields. The host verifies structure and
links only, not entailment, materiality or truth. No approval or handoff is granted.
'''


class RuleApplication(Strict):
    rule_number: StrictInt = Field(ge=1)
    explanation: StrictStr = Field(min_length=1)
    fact_index: StrictInt = Field(ge=0, le=4)
    passages: list[StrictInt] = Field(min_length=1)


class TermAssertion(Strict):
    term_index: StrictInt = Field(ge=0)
    status: Literal['RECORDED', 'UNRESOLVED']
    statement: StrictStr
    passages: list[StrictInt]
    reason: StrictStr = Field(min_length=1)


class ExplicitDraft(Strict):
    draft: TypedDraft
    rule_applications: list[RuleApplication]
    term_assertions: list[TermAssertion]


def explicit_schema(packet, masters):
    # Reuse every v20 field constraint; only add the enclosing explicit contract.
    base = tier_schema(packet, masters)
    schema = ExplicitDraft.model_json_schema()
    schema['$defs'].update(deepcopy(base['$defs']))
    schema['$defs']['TypedDraft'] = {k:deepcopy(v) for k,v in base.items() if k != '$defs'}
    for name in ('RuleApplication','TermAssertion'):
        schema['$defs'][name]['properties']['passages']['items'].update(
            minimum=1, maximum=len(numbered_passages(packet)))
    return schema


def prepare_explicit_request(packet, masters, model, max_output_tokens, max_input_bytes, now):
    from research_reviewer import ReviewBlocked, authority_texts
    base = prepare_semantic_request(packet, masters, model, max_output_tokens, max_input_bytes, now)
    m = authority_texts(packet, masters, now)
    r = deepcopy(base)
    r['implementation_version'], r['prompt_version'] = VERSIONS
    r['body']['input'][0]['content'] += '\n'+INSTRUCTIONS
    r['body']['text']['format']['schema'] = explicit_schema(packet, m)
    if len(canonical(r['body']).encode()) > max_input_bytes:
        raise ReviewBlocked('INPUT_LIMIT_EXCEEDED_NO_TRUNCATION')
    r['request_id'] = digest(dict(version=VERSIONS[0], prompt_version=VERSIONS[1], body=r['body']))
    return r


def validate_explicit_request(packet, request):
    from research_semantics import VERSIONS as PREVIOUS
    from research_reviewer import ReviewBlocked
    try:
        if (request['implementation_version'],request['prompt_version']) != VERSIONS:
            raise ValueError()
        if request['packet_id'] != packet['packet_id'] or request['request_id'] != digest(
                dict(version=VERSIONS[0],prompt_version=VERSIONS[1],body=request['body'])):
            raise ValueError()
        m = json.loads(request['body']['input'][0]['content'].split('\nGOVERNING_MASTERS:\n',1)[1].split('\nCRITERION_REFERENCES:\n',1)[0])
        base = deepcopy(request)
        base['implementation_version'],base['prompt_version'] = PREVIOUS
        base['body']['input'][0] = semantic_developer(packet,m)
        base['body']['text']['format']['schema'] = tier_schema(packet,m)
        base['request_id'] = digest(dict(version=PREVIOUS[0],prompt_version=PREVIOUS[1],body=base['body']))
        validate_semantic_request(packet,base)
        expected = deepcopy(base['body'])
        expected['input'][0]['content'] += '\n'+INSTRUCTIONS
        expected['text']['format']['schema'] = explicit_schema(packet,m)
        if expected != request['body']:raise ValueError()
        return m,base
    except (KeyError,IndexError,TypeError,ValueError):
        raise ReviewBlocked('EXPLICIT_REQUEST_BINDING_MISMATCH') from None


def validate_explicit_draft(packet, request, text):
    """Return a supplemental evidence report, never a model/strategy admission."""
    from research_semantics import resolve_semantic_draft
    from research_meaning_review import passage_numbers
    masters,base = validate_explicit_request(packet,request)
    raw = json.loads(text)
    parsed = ExplicitDraft.model_validate(raw)
    d = raw['draft']
    validate_tier_selection(d,masters)
    # Validate the complete embedded draft with the original parser. The original
    # response text and full extended shape are retained separately, never repaired.
    resolve_semantic_draft(packet,base,canonical(d))
    proposal = d['research']['tier_proposal']
    if proposal['mapping_status']=='UNRESOLVED' and proposal['rules']:
        raise ValueError('UNRESOLVED_MAPPING_REQUIRES_NO_RULES')
    applications = parsed.rule_applications
    if sorted(x.rule_number for x in applications) != sorted(proposal['rules']):
        raise ValueError('EXACT_RULE_APPLICATION_SET_REQUIRED')
    catalog = numbered_passages(packet)
    def sources(numbers):
        if (len(set(numbers)) != len(numbers) or any(n not in catalog for n in numbers)
                or any(catalog[n]['category'] not in SUBSTANTIVE for n in numbers)):
            raise ValueError('SUBSTANTIVE_SOURCE_SELECTION_REQUIRED')
        return [dict(number=n,**deepcopy(catalog[n])) for n in numbers]
    rules = numbered_rules(masters); rule_rows=[]
    for app in applications:
        if not app.explanation.strip():raise ValueError('RULE_EXPLANATION_REQUIRED')
        fact = d['research']['facts'][app.fact_index]
        if (fact['topic']!='catalyst_event' or fact['status']!='EVIDENCED'
                or fact['support']['event_relation']!='SELECTED_EVENT'
                or not set(app.passages).issubset(passage_numbers(fact['support']))):
            raise ValueError('RULE_SELECTED_EVENT_FACT_LINK_REQUIRED')
        rule_rows.append(dict(application=deepcopy(raw['rule_applications'][len(rule_rows)]),
            governing_rule=deepcopy(rules[app.rule_number]), fact=deepcopy(fact),
            source_passages=sources(app.passages)))
    terms = d['economic_inventory']['terms']
    if sorted(x.term_index for x in parsed.term_assertions) != list(range(len(terms))):
        raise ValueError('EXACT_TERM_ASSERTION_SET_REQUIRED')
    term_rows=[]
    for assertion in parsed.term_assertions:
        if not assertion.reason.strip():raise ValueError('TERM_REASON_REQUIRED')
        if assertion.status=='RECORDED':
            if not assertion.statement.strip() or not assertion.passages:
                raise ValueError('RECORDED_TERM_CORE_REQUIRED')
        elif assertion.statement or assertion.passages:
            raise ValueError('UNRESOLVED_TERM_CONFLICT')
        term_rows.append(dict(assertion=deepcopy(raw['term_assertions'][len(term_rows)]),
            original_term=deepcopy(terms[assertion.term_index]),source_passages=sources(assertion.passages)))
    report = dict(implementation_version=VERSIONS[0],prompt_version=VERSIONS[1],
        packet_id=packet['packet_id'],request_id=request['request_id'],trace=deepcopy(packet['trace']),
        original_response_text=text,original_draft=deepcopy(raw),draft_digest=digest(raw),
        rule_applications=rule_rows,term_assertions=term_rows,
        status='STRUCTURE_VALIDATED_REVIEW_REQUIRED',classification='INFRASTRUCTURE_EVALUATION',
        eligible_for_handoff=False,semantic_acceptance='NOT_ESTABLISHED',api_calls=0,
        limitations=['Exact sets, nonblank fields and source links are structural checks, not evidence of entailment or explanation quality.',
            'Generic explanations, mismatched term meaning and omitted qualifications still require source review.',
            'Explicit UNRESOLVED is permitted; no evidence, trade or approval is manufactured.',
            'Preview contract only. Not integrated into the provider dispatcher, historical review tools or trading services.'])
    report['report_id']=digest(report)
    return report


def main():
    import argparse
    from pathlib import Path
    from evidence_pipeline import write_once
    from review_attempts import utc_now
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare');check=sub.add_parser('check')
    for command in (prep,check):
        command.add_argument('--packet',type=Path,required=True)
        command.add_argument('--output',type=Path,required=True)
    prep.add_argument('--masters',type=Path,required=True)
    prep.add_argument('--model',required=True)
    prep.add_argument('--max-output-tokens',type=int,required=True)
    prep.add_argument('--max-input-bytes',type=int,required=True)
    check.add_argument('--request',type=Path,required=True)
    check.add_argument('--response-text',type=Path,required=True)
    args=parser.parse_args();read=lambda p:json.loads(p.read_text(encoding='utf-8'));packet=read(args.packet)
    if args.action=='prepare':
        obj=prepare_explicit_request(packet,read(args.masters),args.model,args.max_output_tokens,args.max_input_bytes,utc_now())
        name='explicit-request-'+obj['request_id'];status='PREPARED_NOT_SENT'
    else:
        obj=validate_explicit_draft(packet,read(args.request),args.response_text.read_text(encoding='utf-8'))
        name='explicit-check-'+obj['report_id'];status=obj['status']
    path=write_once(args.output,name+'.json',canonical(obj)+'\n')
    print(canonical(dict(file=str(path),status=status,api_calls=0,eligible_for_handoff=False)))


if __name__=='__main__':main()
