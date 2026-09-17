// Isolated reproduction from read-only catalog metadata. No production rows or credentials.
import {PGlite} from '@electric-sql/pglite';
import {readFileSync,readdirSync} from 'node:fs';
import assert from 'node:assert/strict';
const db=new PGlite();
const schema=JSON.parse(readFileSync(new URL('live_schema_snapshot.json',import.meta.url),'utf8'));
const quote=s=>'"'+s.replaceAll('"','""')+'"';
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
for(const name of new Set(schema.columns.map(c=>c.table_name))){
    const columns=schema.columns.filter(c=>c.table_name===name).map(c=>`${quote(c.column_name)} ${c.udt_name.startsWith('_') ? c.udt_name.slice(1)+'[]' : c.udt_name}${c.column_default ? ' default '+c.column_default : ''}${c.is_nullable==='NO' ? ' not null' : ''}`);
    await db.exec(`create table public.${quote(name)} (${columns.join(',')});`);
}
for(const c of [...schema.constraints].sort((a,b)=>Number(a.definition.startsWith('FOREIGN'))-Number(b.definition.startsWith('FOREIGN')))){
    await db.exec(`alter table public.${quote(c.table)} add constraint ${quote(c.name)} ${c.definition};`);
}
const constraintNames=new Set(schema.constraints.map(c=>c.name));
for(const i of schema.indexes.filter(i=>!constraintNames.has(i.indexname)))await db.exec(i.indexdef);
for(const name of ['set_updated_at','set_strategy_signals_updated_at']){
    await db.exec(`create function public.${name}() returns trigger language plpgsql as $$ begin new.updated_at=now(); return new; end $$;`);
}
for(const trigger of schema.triggers)await db.exec(trigger);
await db.exec('grant select,insert,update on all tables in schema public to service_role;');
const run=(await db.query(`insert into strategy_discovery_runs(session_date,phase,status,run_key,ruleset_version) values ('2026-09-15','PREMARKET','PARTIAL','isolated-only','v0.3') returning id`)).rows[0].id;
const item=(await db.query(`insert into strategy_discovery_items(run_id,symbol,operational_state) values ($1,'LOCAL','WATCHLIST_CANDIDATE') returning id`,[run])).rows[0].id;
const before=(await db.query('select to_jsonb(i) row from strategy_discovery_items i')).rows[0].row;
// Prove the discovered production constraint really rejects the new state.
await assert.rejects(()=>db.query("update strategy_discovery_items set operational_state='HOLD_UNRESOLVED' where id=$1",[item]),/operational_state_check/);
for(const file of readdirSync(new URL('../supabase/migrations/',import.meta.url)).filter(n=>n.endsWith('.sql')).sort()){
    await db.exec(readFileSync(new URL('../supabase/migrations/'+file,import.meta.url),'utf8'));
}
const after=(await db.query('select to_jsonb(i) row from strategy_discovery_items i')).rows[0].row;
for(const [key,value] of Object.entries(before))assert.deepEqual(after[key],value);
await db.exec('set role service_role;');
for(const state of ['HOLD_UNRESOLVED','REJECTED','WAITING_FOR_TRIGGER','CONFIRMATION_REQUIRED','TRADE_READY']){
    await db.query('update strategy_discovery_items set operational_state=$1,transition_context=$2 where id=$3',
        [state,JSON.stringify({owner:'acceptance-test',implementation_version:'fixture-only',reason:state}),item]);
}
assert.equal((await db.query('select count(*)::int n from strategy_discovery_events')).rows[0].n,5);
await assert.rejects(()=>db.query("update strategy_discovery_items set operational_state='INVALID' where id=$1",[item]),/operational_state_check/);
await assert.rejects(()=>db.query("insert into strategy_discovery_runs(session_date,phase,status,run_key,ruleset_version) values ('2026-09-15','PREMARKET','PARTIAL','isolated-only','v0.3')"),/run_key_uidx/);
await db.close();
console.log('Live-schema acceptance passed: captured columns/defaults/constraints/indexes/triggers, migration chain, state transitions, immutable history, duplicate run guard.');
