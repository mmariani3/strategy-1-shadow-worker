const {test} = require('node:test');
const assert = require('node:assert/strict');
const {calculate, planningDraft} = require('../supervised_preparation.js');
const {reviewDraft} = require('../supervised_preparation.js');
const vm = require('node:vm');
const fs = require('node:fs');
const limits = {max_risk:'50', max_notional:'10000', max_daily_loss:'100', max_trades:'3', minimum_rr:'1.5', preferred_rr:'2'};
const input = {direction:'LONG', entry:'100', stop:'99', target:'102', budget:'50', loss:'0', trades:'0'};

const reviewReport = {experiment_class:'INFRASTRUCTURE_TEST', source_context:'HISTORICAL_REPLAY',
  preparation_id:'prep', source_snapshot_digest:'hash', review_question_version:'test',
  review_questions:[{id:'sources',question:'Sources verified?'}],
  candidates:[{symbol:'LOCAL',packet_id:'p1',trace:{run_id:'run',candidate_id:null,signal_id:null,journal_trade_id:null},
    catalyst_brief:{brief_id:'brief'}},{symbol:'OTHER',packet_id:'p2',trace:{run_id:'run'}}]};
test('review draft preserves unanswered questions and exact brief lineage without approving', () => {
  for (const answer of ['UNANSWERED','SUPPORTED','UNCLEAR','FAILS']) {
    const d = reviewDraft(reviewReport,0,{sources:{answer,reason:answer==='UNANSWERED'?'':'Evidence passage 1'}},'Mitch','2026-09-25T05:30:00Z');
    assert.equal(d.answers[0].answer,answer); assert.equal(d.catalyst_brief_id,'brief');
    assert.equal(d.trigger_confirmation,'NOT_ESTABLISHED'); assert.equal(d.eligible_for_handoff,false);
    assert.equal(d.journaled,false); assert.equal(d.source_experiment_class,'INFRASTRUCTURE_TEST');
    assert.deepEqual(d.trace,reviewReport.candidates[0].trace);
  }
});
test('review answer shape and attribution fail closed', () => {
  const args=[reviewReport,0,{sources:{answer:'SUPPORTED',reason:'Source 1'}},'Mitch','2026-09-25T05:30:00Z'];
  for (const a of [{}, {sources:{answer:'APPROVED',reason:'yes'}},{sources:{answer:'SUPPORTED',reason:''}},
    {sources:{answer:'UNANSWERED',reason:0}}, {sources:{answer:'UNCLEAR',reason:'Missing'},unknown:{}}])
    assert.throws(()=>reviewDraft(args[0],args[1],a,args[3],args[4]));
  assert.throws(()=>reviewDraft(args[0],0,args[2],'',args[4]));
  assert.throws(()=>reviewDraft(args[0],0,args[2],'Mitch','invalid'));
  assert.throws(()=>reviewDraft(args[0],-1,args[2],'Mitch',args[4]));
});
test('DOM event wiring downloads bound draft and clears answers when candidate changes', async () => {
  // Simulated DOM, not a claim of browser rendering or filesystem-download acceptance.
  const nodes = new Map(); const blobs = [];
  const node = id => {
    if (!nodes.has(id)) nodes.set(id,{value:'',textContent:'',listeners:{},
      addEventListener(event,handler){this.listeners[event]=handler;},appendChild(){},click(){}});
    return nodes.get(id);
  };
  node('preparation-data').textContent = JSON.stringify(reviewReport);
  const document = {getElementById:node,createElement:()=>({click(){}}),querySelectorAll:()=>[]};
  vm.runInNewContext(fs.readFileSync(require.resolve('../supervised_preparation.js'),'utf8'),{
    document,Blob,URL:{createObjectURL:b=>{blobs.push(b);return 'blob:test';},revokeObjectURL(){}},setTimeout:()=>{},Date});
  node('candidate').value='0'; node('candidate').listeners.change();
  node('review-name').value='Mitch'; node('review-sources').value='SUPPORTED'; node('reason-sources').value='Passage one';
  node('save-review').listeners.click();
  const first=JSON.parse(await blobs[0].text());
  assert.equal(first.catalyst_brief_id,'brief'); assert.equal(first.symbol,'LOCAL');
  assert.equal(first.answers[0].answer,'SUPPORTED'); assert.equal(first.eligible_for_handoff,false);
  node('candidate').value='1'; node('candidate').listeners.change();
  assert.equal(node('review-sources').value,'UNANSWERED'); assert.equal(node('reason-sources').value,'');
  node('save-review').listeners.click();
  const second=JSON.parse(await blobs[1].text());
  assert.equal(second.symbol,'OTHER'); assert.equal(second.catalyst_brief_id,null);
  assert.equal(second.answers[0].answer,'UNANSWERED');
  node('review-sources').value='SUPPORTED'; node('save-review').listeners.click();
  assert.equal(blobs.length,2); assert.match(node('review-status').textContent,/reason and evidence/);
});

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
