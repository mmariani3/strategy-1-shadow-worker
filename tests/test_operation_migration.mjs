import { PGlite } from '@electric-sql/pglite';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const db = new PGlite();
await db.exec(`create role anon; create role authenticated; create role service_role bypassrls;
  alter default privileges in schema public grant all on tables to anon,authenticated,service_role;
  alter default privileges in schema public grant all on sequences to anon,authenticated,service_role;`);
await db.exec(readFileSync(new URL('../supabase/migrations/20260918173946_shadow_operation_events.sql',import.meta.url),'utf8'));
const q = (sql,args=[]) => db.query(sql,args);
assert.equal((await q("select relrowsecurity from pg_class where oid='shadow_operation_events'::regclass")).rows[0].relrowsecurity,true);
await db.exec('set role service_role');
const insert = type => q("insert into shadow_operation_events(job_key,event_type,implementation_version,payload) values('test-only',$1,'test','{}')",[type]);
await insert('PLANNED');
await assert.rejects(()=>insert('PLANNED'),/duplicate/i);
await insert('DISPATCHED');
await assert.rejects(()=>insert('DISPATCHED'),/duplicate/i);
await insert('AMBIGUOUS');await insert('PARTIAL');
assert.equal((await q('select count(*)::int n from shadow_operation_events')).rows[0].n,4);
await assert.rejects(()=>db.exec("update shadow_operation_events set event_type='COMPLETE'"),/permission denied/i);
await assert.rejects(()=>db.exec('delete from shadow_operation_events'),/permission denied/i);
await assert.rejects(()=>db.exec('truncate shadow_operation_events'),/permission denied/i);
await assert.rejects(()=>insert('TRADE'),/check constraint/i);
for (const role of ['anon','authenticated']) {
  await db.exec(`reset role;set role ${role}`);
  await assert.rejects(()=>q('select * from shadow_operation_events'),/permission denied/i);
  await assert.rejects(()=>insert('MISSED'),/permission denied/i);
}
await db.close();
console.log('Operations migration passed: immutable history, unique dispatch intent, RLS, default-grant regression.');
