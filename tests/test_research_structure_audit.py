"""Synthetic offline fixtures; no provider, production or strategy observations."""
from copy import deepcopy
import json
import pytest
from evidence_review import canonical, digest
from research_structure_audit import structure_audit
from research_semantics import prepare_semantic_request
from research_reviewer import parse_response
from research_tiers import tier_choices
from test_evidence_review import authorities, snapshot, NOW
from test_research_reviewer import masters, ledger_path
from test_research_facts import fact_case, reply
from test_research_passages import passage_case
from test_research_linked import linked_case
from test_research_tiers import case


def fixture(linked_case):
    p,_,d,ref,m=case(linked_case)
    r=prepare_semantic_request(p,m,'offline-fixture',12000,250000,NOW)
    return p,r,d,ref,m


def test_each_selected_rule_is_checked_without_rewriting_admission(linked_case):
    p,r,d,ref,m=fixture(linked_case);t=d['research']['tier_proposal']
    t.update(proposed_tier='A',mapping_status='PROPOSED',rules=tier_choices(m)['A'],fact_topics=['catalyst_event'],explanation='This is an acquisition, so Tier A applies.')
    original=deepcopy((p,r,d,ref));before=parse_response(p,r,reply(d),NOW)
    out=structure_audit(p,r,d,ref)
    rules=[x for x in out['items'] if x['kind']=='RULE_APPLICATION']
    assert len(rules)==len(t['rules']) and all(x['flags']==['RULE_DECLARATION_NOT_FOUND'] for x in rules)
    assert (p,r,d,ref)==original and parse_response(p,r,reply(d),NOW)==before
    assert out['trace']==p['trace'] and out['original_versions']['prompt']==r['prompt_version']
    assert not out['eligible_for_handoff'] and out['semantic_acceptance']=='NOT_ESTABLISHED'


@pytest.mark.parametrize('text,found',[
    ('Rule {n}: acquisition.',True),('rule #{n}: acquisition.',True),
    ('RULE {n} only: event supports acquisition.',True),
    ('Payment of {n} dollars.',False),('rule {n}0: another reference.',False),
    ('rule {n}.5: not an integer reference.',False),('rule {n}x',False),
    ('rules {n}: shorthand list.',False),
    ('Rule {n} is NOT supported.',True),('Source quotation says rule {n}.',True)])
def test_declarations_are_literal_not_semantic_approval(linked_case,text,found):
    p,r,d,ref,m=fixture(linked_case);n=tier_choices(m)['A'][0]
    d['research']['tier_proposal'].update(rules=[n],fact_topics=['catalyst_event'],mapping_status='PROPOSED',proposed_tier='A')
    d['research']['tier_proposal']['explanation']=text.format(n=n)
    out=structure_audit(p,r,d,ref);row=next(x for x in out['items'] if x['kind']=='RULE_APPLICATION')
    assert bool(row['declaration_matches'])==found
    assert not out['eligible_for_handoff'] and out['semantic_acceptance']=='NOT_ESTABLISHED'


def test_sparse_terms_detected_even_when_prose_elsewhere_preserves_expectation(linked_case):
    p,r,d,ref,m=fixture(linked_case);term=d['economic_inventory']['terms'][0]
    for name in ('amounts','conditions','timing'):
        term[name].update(entries=[],status='UNRESOLVED',reason='Not quantified here; see narrative.')
    # The qualifications and complete original narrative remain available.
    out=structure_audit(p,r,d,ref);row=next(x for x in out['items'] if x['kind']=='ECONOMIC_TERM')
    assert row['flags']==['NO_CORE_TERM_ENTRIES'] and row['original_value']==term
    assert row['core_entry_counts']==dict(amounts=0,conditions=0,timing=0)


def test_unquantified_but_recorded_funding_plan_not_flagged_as_empty(linked_case):
    p,r,d,ref,m=fixture(linked_case);term=d['economic_inventory']['terms'][0]
    entry=deepcopy(term['amounts']['entries'][0])
    term['amounts'].update(entries=[],status='UNRESOLVED',reason='Funding split unavailable.')
    term['timing'].update(entries=[entry],status='RECORDED',reason='The source describes a future funding plan.')
    out=structure_audit(p,r,d,ref);row=next(x for x in out['items'] if x['kind']=='ECONOMIC_TERM')
    assert row['flags']==[] and not out['eligible_for_handoff']


def test_unresolved_rule_mapping_remains_visible(linked_case):
    p,r,d,ref,_=fixture(linked_case)
    d['research']['tier_proposal'].update(rules=[],fact_topics=[],proposed_tier='UNRESOLVED',mapping_status='UNRESOLVED')
    out=structure_audit(p,r,d,ref)
    assert out['items'][0]['flags']==['UNRESOLVED_RULE_MAPPING']


@pytest.mark.parametrize('what',['source','request','reference','draft','version'])
def test_invalid_bindings_fail_before_report(linked_case,what):
    p,r,d,ref,_=fixture(linked_case)
    if what=='source':p['packet_id']='0'*64
    if what=='request':r['body']['input'][0]['content']+='tampered'
    if what=='reference':ref['cases'][0]['expectations'][0]['quote']='tampered'
    if what=='draft':d['economic_inventory']['terms'][0]['amounts']['entries'][0]['passages']=['bad']
    if what=='version':r['prompt_version']='governed-research-v19'
    with pytest.raises((ValueError,KeyError)):structure_audit(p,r,d,ref)


def test_cli_writes_immutable_reproducible_sidecar_only(linked_case,monkeypatch,capsys):
    import research_structure_audit as cli
    p,r,d,ref,_=fixture(linked_case);root=ledger_path().parent
    before=deepcopy((p,r,d,ref));expected=structure_audit(p,r,d,ref)
    paths={}
    for n,v in zip(('packet','request','draft','reference'),before):
        paths[n]=root/(n+'.json');paths[n].write_text(json.dumps(v),encoding='utf-8')
    hashes={n:x.read_bytes() for n,x in paths.items()}
    monkeypatch.setattr('sys.argv',['audit',*[v for n,p in paths.items() for v in ('--'+n,str(p))],'--output',str(root)])
    cli.main();first=json.loads(capsys.readouterr().out)
    cli.main();assert json.loads(capsys.readouterr().out)==first
    assert {n:x.read_bytes() for n,x in paths.items()}==hashes
    saved=json.loads((root/('structure-audit-'+expected['report_id']+'.json')).read_text())
    assert saved==expected and first['api_calls']==0 and not first['eligible_for_handoff']
