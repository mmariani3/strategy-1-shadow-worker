const {test} = require('node:test');
const assert = require('node:assert/strict');
const {calculate, planningDraft} = require('../supervised_preparation.js');
const limits = {max_risk:'50', max_notional:'10000', max_daily_loss:'100', max_trades:'3', minimum_rr:'1.5', preferred_rr:'2'};
const input = {direction:'LONG', entry:'100', stop:'99', target:'102', budget:'50', loss:'0', trades:'0'};

test('long and short arithmetic never establishes approval', () => {
  for (const v of [input, {...input, direction:'SHORT', stop:'101', target:'98'}]) {
    const r = calculate(v, limits);
    assert.equal(r.planning_quantity, '50'); assert.equal(r.planned_dollar_risk, '50');
    assert.equal(r.planned_notional, '5000'); assert.equal(r.planned_rr_truncated_8dp, '2');
    assert.equal(r.eligible_for_handoff, false); assert.equal(r.current_approval, 'NOT_ESTABLISHED');
  }
});
test('exact decimal sizing respects chosen risk and notional', () => {
  let r = calculate({...input, entry:'0.3', stop:'0.2', target:'0.5', budget:'0.3'}, limits);
  assert.equal(r.planning_quantity, '3'); assert.equal(r.planned_dollar_risk, '0.3');
  r = calculate({...input, entry:'1000', stop:'999', target:'1002'}, limits);
  assert.equal(r.planning_quantity, '10'); assert.equal(r.planned_notional, '10000');
  r = calculate({...input, budget:'25'}, limits); assert.equal(r.planning_quantity, '25');
});
test('daily ceilings, poor RR and zero shares suppress planning quantity', () => {
  for (const extra of [{loss:'100'}, {trades:'3'}, {target:'101.49'}, {entry:'10001',stop:'10000',target:'10003'}]) {
    const r = calculate({...input,...extra}, limits);
    assert.ok(r.blockers.length); assert.equal(r.planning_quantity, null); assert.equal(r.planned_dollar_risk, null);
  }
});
test('1.5 to below 2R flags human clean-structure review without approving', () => {
  for (const target of ['101.5', '101.99999999']) assert.equal(calculate({...input,target},limits).clean_structure_review_required,true);
  assert.equal(calculate(input,limits).clean_structure_review_required,false);
});
test('malformed numbers, missing counters and invalid geometry fail', () => {
  for (const budget of [true, null, '', 'NaN', 'Infinity', '-1', '0', '51', '1e2', '0.123456789'])
    assert.throws(() => calculate({...input,budget},limits));
  for (const extra of [{trades:'1.5'}, {loss:''}, {direction:''}, {stop:'100'}, {stop:'101'}, {target:'99'}, {entry:'0'}])
    assert.throws(() => calculate({...input,...extra},limits));
});
test('draft keeps IDs, classification, input evidence and blocked result', () => {
  const report = {experiment_class:'INFRASTRUCTURE_TEST', preparation_id:'prep', implementation_version:'test',
    source_snapshot_digest:'digest', source_captured_at:'2026-09-18T14:00:00Z', source_context:'HISTORICAL_REPLAY',
    session_date:'2026-09-18', risk_limits:limits, candidates:[{symbol:'LOCAL',packet_id:'packet',
      trace:{run_id:'run',candidate_id:null,source_discovery_item_id:'item',signal_id:null,journal_trade_id:null}}]};
  const d = planningDraft(report,0,{...input,loss:'100'},'Reviewer','Isolated fixture; no market data.','2026-09-24T14:00:00Z');
  assert.deepEqual(d.trace,report.candidates[0].trace); assert.equal(d.arithmetic.planning_quantity,null);
  assert.equal(d.source_experiment_class,'INFRASTRUCTURE_TEST'); assert.equal(d.journaled,false);
  assert.equal(d.execution_enabled,false); assert.equal(d.trigger_confirmation,'NOT_ESTABLISHED');
  assert.throws(() => planningDraft(report,0,input,'','notes','2026-09-24T14:00:00Z'));
  assert.throws(() => planningDraft(report,1,input,'Reviewer','notes','2026-09-24T14:00:00Z'));
  assert.throws(() => planningDraft(report,-1,input,'Reviewer','notes','2026-09-24T14:00:00Z'));
});
