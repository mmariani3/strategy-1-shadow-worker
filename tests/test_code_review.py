from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import json
import sys

import pytest

from code_review import check_structured, inspect_packet, number, plan_bundle
from evidence_pipeline import produce
from evidence_review import digest
from test_evidence_review import authorities, snapshot, packet, NOW


def index(raw):
    return {c['check']: c for c in check_structured(raw, 'fixture-source', NOW)}


@pytest.mark.parametrize('value', [True, False, 'NaN', 'Infinity', '-Infinity', '', [], None])
def test_bad_numbers_never_pass(value):
    with pytest.raises(ValueError): number(value)


@pytest.mark.parametrize('direction,stop,target', [('LONG', '99', '102'), ('SHORT', '101', '98')])
def test_geometry_and_size_are_calculated_without_approval(direction, stop, target):
    checks = index(dict(direction=direction, entry_price='100', stop_price=stop, target_price=target))
    assert checks['price_geometry']['status'] == 'PASS'
    assert checks['reward_risk_floor']['values'] == '2'
    assert checks['position_ceiling']['values'] == dict(risk_per_share='1', reward_per_share='2', planned_rr='2',
        maximum_qty_at_ruleset_ceilings=50, dollar_risk='50', notional='5000')
    assert checks['required_inputs']['status'] == 'UNRESOLVED'


@pytest.mark.parametrize('target,status,clean', [('101.49','FAIL','NOT_APPLICABLE'),
    ('101.5','PASS','UNRESOLVED'), ('101.99','PASS','UNRESOLVED'), ('102','PASS','NOT_APPLICABLE')])
def test_reward_risk_boundaries_do_not_infer_clean_structure(target, status, clean):
    checks = index(dict(direction='LONG', entry_price='100', stop_price='99', target_price=target, clean_structure=True))
    assert checks['reward_risk_floor']['status'] == status
    assert checks['clean_structure_requirement']['status'] == clean
    assert checks['assertion.clean_structure']['status'] == 'RECORDED_ASSERTION'


@pytest.mark.parametrize('entry,stop,target,qty', [('1000','999','1002',10), ('10001','10000','10003',0)])
def test_notional_cap_and_zero_quantity(entry,stop,target,qty):
    c = index(dict(direction='LONG', entry_price=entry, stop_price=stop, target_price=target))['position_ceiling']
    assert c['values']['maximum_qty_at_ruleset_ceilings'] == qty
    assert c['status'] == ('PASS' if qty else 'FAIL')


@pytest.mark.parametrize('raw,status', [
    ({'direction':'LONG','entry_price':'100','stop_price':'101','target_price':'102'},'FAIL'),
    ({'direction':'LONG','entry_price':'100','stop_price':'100','target_price':'102'},'FAIL'),
    ({'direction':'LONG','entry_price':'100','stop_price':'99','target_price':'98'},'FAIL'),
    ({'direction':'LONG','entry_price':True,'stop_price':'99','target_price':'102'},'INVALID'),
    ({'direction':'LONG','entry_price':'NaN','stop_price':'99','target_price':'102'},'INVALID'),
    ({'direction':'LONG','entry_price':'100','stop_price':'-1','target_price':'102'},'INVALID'),
    ({'direction':'LONG','entry_price':'100','stop_price':'99'},'UNRESOLVED')])
def test_invalid_or_missing_geometry(raw,status):
    checks = index(raw)
    assert checks['price_geometry']['status'] == status
    assert 'position_ceiling' not in checks


@pytest.mark.parametrize('loss,trades,loss_status,trade_status', [
    ('99.99',2,'PASS','PASS'),('100',3,'FAIL','FAIL'),('-1',2.5,'INVALID','INVALID'),
    (None,None,'UNRESOLVED','UNRESOLVED'),(False,True,'INVALID','INVALID')])
def test_daily_limits_and_missing_state(loss,trades,loss_status,trade_status):
    c = index(dict(realized_daily_loss_dollars=loss,executed_trades_today=trades))
    assert c['realized_daily_loss_dollars']['status'] == loss_status
    assert c['executed_trades_today']['status'] == trade_status


def test_booleans_are_not_coerced_and_negative_updates_are_preserved():
    c = index(dict(target_validated='true', liquidity_ok=False, missed_trigger=True,
                   consolidated_data_required=True, consolidated_data=False, market_context_ok=False))
    assert c['assertion.target_validated']['status'] == 'INVALID'
    assert c['assertion.liquidity_ok']['values'] is False
    assert c['assertion.missed_trigger']['values'] is True
    assert c['assertion.market_context_ok']['values'] is False
    assert c['consolidated_requirement']['status'] == 'FAIL'


@pytest.mark.parametrize('stamp,status',[('2026-09-18T14:00:01Z','FAIL'),
    ('2026-09-18T13:59:00','INVALID'),('2020-01-01T00:00:00Z','PASS'),(None,'UNRESOLVED')])
def test_timestamps_check_order_but_never_invent_freshness(stamp,status):
    c = index(dict(data_timestamp=stamp))
    assert c['timestamp.data_timestamp']['status'] == status
    assert c['review_contract_at_capture']['status'] == 'UNRESOLVED'


def test_valid_then_expired_review_and_observation_are_not_confirmation(candidate_data):
    from datetime import datetime, timezone
    data = deepcopy(candidate_data)
    now = datetime.now(timezone.utc).isoformat()
    checks = {c['check']:c for c in check_structured(data,'source',now)}
    assert checks['review_contract_at_capture']['status'] == 'PASS'
    data['current_review']['valid_until'] = data['data_timestamp']
    checks = {c['check']:c for c in check_structured(data,'source',now)}
    assert checks['review_contract_at_capture']['status'] == 'UNRESOLVED'
    assert checks['assertion.trigger_confirmed']['values'] is False


def test_empty_inputs_do_not_pass_as_worker_ready():
    c = index({})
    assert c['required_inputs']['fields'] and c['price_geometry']['status'] == 'UNRESOLVED'
    assert all(c[k]['status']=='UNRESOLVED' for k in ['approved_entry_model','review_contract_at_capture'])


def test_review_routing_preserves_full_funnel_and_budget(snapshot,authorities):
    snapshot['run']['experiment_class']='STRATEGY_1'
    original=deepcopy(snapshot)
    bundle,_=produce(snapshot,authorities,now=NOW)
    plan=plan_bundle(bundle,NOW,0)
    assert plan['counts']=={'DEFERRED_BUDGET_UNREVIEWED':1,'NEEDS_SOURCE_EVIDENCE':1}
    assert plan['total_records']==2 and plan['opportunity_count']=='UNKNOWN'
    assert all(not r['eligible_for_handoff'] and not r['execution_enabled'] for r in plan['reports'])
    assert all(len(r['unresolved_criteria'])==11 for r in plan['reports'])
    assert plan['model_calls']==0 and snapshot==original
    assert plan_bundle(bundle,NOW,1)['counts']=={'RESEARCH_REVIEW_SLOT':1,'NEEDS_SOURCE_EVIDENCE':1}
    assert plan_bundle(bundle,NOW,0)==plan


def test_filing_metadata_is_retrieval_task_not_catalyst_rejection(snapshot,authorities):
    snapshot['run']['experiment_class']='STRATEGY_1'
    snapshot['items'][0]['news_evidence']=[]
    p=packet(snapshot,authorities)
    r=inspect_packet(p,NOW)
    assert r['route']=='NEEDS_SOURCE_EVIDENCE'
    assert r['evidence_inventory'][0]['actual_event_freshness']=='UNRESOLVED'
    assert not r['evidence_inventory'][0]['has_captured_text']


def test_infrastructure_keeps_classification_and_gets_no_proposed_paid_slot(snapshot,authorities):
    bundle,_=produce(snapshot,authorities,now=NOW)
    result=plan_bundle(bundle,NOW,100)
    assert result['counts']=={'EXCLUDED_INFRASTRUCTURE':2}
    assert all(r['experiment_class']=='INFRASTRUCTURE_TEST' for r in result['reports'])


def test_injection_and_source_cooccurrence_do_not_establish_strategy_claims(snapshot,authorities):
    r=inspect_packet(packet(snapshot,authorities),NOW)
    assert r['unresolved_criteria'] and not r['eligible_for_handoff']
    assert all(s['source_independence']=='UNRESOLVED' for s in r['evidence_inventory'])
    assert r['journal_verification']=='NOT_CHECKED'


@pytest.mark.parametrize('tamper',['raw','text','recorded_at'])
def test_rehashed_outer_packet_cannot_hide_inner_source_corruption(snapshot,authorities,tamper):
    p=packet(snapshot,authorities)
    if tamper=='raw': p['sources'][0]['raw']['symbol']='CHANGED'
    if tamper=='text': p['sources'][0]['text']='changed'
    if tamper=='recorded_at': p['sources'][0]['recorded_at']='2026-09-19T00:00:00Z'
    p['packet_id']=digest({k:v for k,v in p.items() if k!='packet_id'})
    with pytest.raises(ValueError): inspect_packet(p,NOW)


@pytest.mark.parametrize('tamper',['omit','duplicate','lineage','authority','snapshot'])
def test_bundle_completeness_and_lineage_fail_closed(snapshot,authorities,tamper):
    b,_=produce(snapshot,authorities,now=NOW)
    if tamper=='omit': b['packets'].pop()
    if tamper=='duplicate': b['packets'].append(b['packets'][0])
    if tamper=='lineage':
        p=b['packets'][0];p['trace']['candidate_id']='invented'
        p['packet_id']=digest({k:v for k,v in p.items() if k!='packet_id'})
    if tamper=='authority': b['authority_digest']='changed'
    if tamper=='snapshot': b['source_snapshot_digest']='changed'
    with pytest.raises(ValueError): plan_bundle(b,NOW)


def test_existing_dispatch_cli_blocks_empty_evidence_before_credentials_or_network(snapshot,authorities,monkeypatch,capsys):
    import run_research_reviewer as cli
    tmp_path=Path(__file__).resolve().parents[1]/'.tmp'/('code-review-'+uuid4().hex)
    tmp_path.mkdir(parents=True)
    snapshot['run']['experiment_class']='STRATEGY_1'
    p=produce(snapshot,authorities,now=NOW)[0]['packets'][1]
    path=tmp_path/'packet.json';path.write_text(json.dumps(p))
    monkeypatch.setattr(cli,'utc_now',lambda:NOW)
    def forbidden(*args,**kwargs): raise AssertionError('Must not reach request preparation or provider')
    monkeypatch.setattr(cli,'prepare_request',forbidden)
    monkeypatch.setattr(cli,'OpenAIReviewer',forbidden)
    monkeypatch.setattr(sys,'argv',['review','--packet',str(path),'--masters',str(tmp_path/'absent.json'),
        '--model','unused','--max-output-tokens','6000','--max-input-bytes','250000',
        '--output',str(tmp_path),'--dispatch','--ledger',str(tmp_path/'ledger.sqlite'),'--max-calls','1'])
    cli.main()
    result=json.loads(capsys.readouterr().out)
    assert result['status']=='NEEDS_SOURCE_EVIDENCE' and result['model_calls']==0
    assert not (tmp_path/'ledger.sqlite').exists()


def test_iex_cannot_supply_consolidated_and_two_publishers_do_not_prove_independence():
    c=index(dict(market_data_source='IEX',consolidated_data=True,catalyst_sources=[{'source':'A'},{'source':'B'}]))
    assert c['iex_consolidated_contradiction']['status']=='FAIL'
    assert c['distinct_named_sources']['status']=='PASS'
    c=index(dict(catalyst_sources=[{'source':' A '},{'source':'a'}]))
    assert c['distinct_named_sources']['status']=='UNRESOLVED'


def test_plan_reports_structured_sources_separately_without_silent_merge(snapshot,authorities):
    snapshot['items'][0]['qualification_review']={'direction':'LONG','catalyst_material':True}
    snapshot['items'][0]['setup_review']={'target_validated':False,'liquidity_ok':False,'missed_trigger':True}
    p=packet(snapshot,authorities);r=inspect_packet(p,NOW)
    assert r['structured_sources_checked']==2
    assert any(c['check']=='assertion.missed_trigger' and c['values'] is True for c in r['checks'])
    assert any(c['check']=='assertion.target_validated' and c['values'] is False for c in r['checks'])
    assert 'direction' not in next(s for s in p['sources'] if s['kind']=='setup_review')['raw']
    assert not r['eligible_for_handoff']


def test_empty_run_remains_unknown_and_unfinished_run_blocks(snapshot,authorities):
    snapshot['items']=[];snapshot['run']['candidates_discovered']=0
    b,_=produce(snapshot,authorities,now=NOW)
    assert plan_bundle(b,NOW)['opportunity_count']=='UNKNOWN'
    b['run']['status']='IN_PROGRESS'
    with pytest.raises(ValueError): plan_bundle(b,NOW)
