-- DRAFT READ-ONLY QUERY. NOT EXECUTED. Requires separate hosted authorization.
-- Run in a READ ONLY, REPEATABLE READ transaction and export COMPLETE results.
-- $1 is the approved future run key; do not reuse October 13's key.
-- Preserve this output, full paginated rows and prior-row digests independently.
with r as (
  select * from public.strategy_discovery_runs where run_key=$1
), i as (
  select x.* from public.strategy_discovery_items x join r on r.id=x.run_id
), e as (
  select x.* from public.strategy_discovery_events x join r on r.id=x.run_id
)
select jsonb_build_object(
  'checked_at', now(),
  'runs', (select coalesce(jsonb_agg(to_jsonb(r)), '[]'::jsonb) from r),
  'item_count', (select count(*) from i),
  'distinct_symbols', (select count(distinct symbol) from i),
  'event_count', (select count(*) from e),
  'invalid_items', (select count(*) from i where
      promotion_status is distinct from 'REVIEW_REQUIRED'
      or verification_status is distinct from 'REVIEW_REQUIRED'
      or provisional_tier is not null or orchestrator_candidate_id is not null
      or qualification_review is not null or setup_review is not null
      or transition_context->'strategy_evidence_eligible' is distinct from 'false'::jsonb),
  'items_without_exact_audit', (select count(*) from i where not exists (
      select 1 from e where e.discovery_item_id=i.id and e.payload->'after'=to_jsonb(i)
      and e.payload->'before'='null'::jsonb)),
  'unfinished_runs', (select count(*) from public.strategy_discovery_runs where status='IN_PROGRESS'),
  'prior_run_count', (select count(*) from public.strategy_discovery_runs x where not exists(select 1 from r where r.id=x.id)),
  'prior_item_count', (select count(*) from public.strategy_discovery_items x where not exists(select 1 from r where r.id=x.run_id)),
  'prior_runs_digest', (select md5(coalesce(string_agg(to_jsonb(x)::text,'|' order by x.id),''))
      from public.strategy_discovery_runs x where not exists(select 1 from r where r.id=x.id)),
  'prior_items_digest', (select md5(coalesce(string_agg(to_jsonb(x)::text,'|' order by x.id),''))
      from public.strategy_discovery_items x where not exists(select 1 from r where r.id=x.run_id)),
  'prior_events_digest', (select md5(coalesce(string_agg(to_jsonb(x)::text,'|' order by x.id),''))
      from public.strategy_discovery_events x where not exists(select 1 from r where r.id=x.run_id)),
  'protected_tables', jsonb_build_object(
      'strategy_candidates', (select md5(coalesce(string_agg(to_jsonb(x)::text,'|' order by x.id),'')) from public.strategy_candidates x),
      'strategy_signals', (select md5(coalesce(string_agg(to_jsonb(x)::text,'|' order by x.id),'')) from public.strategy_signals x),
      'strategy_candidate_events', (select md5(coalesce(string_agg(to_jsonb(x)::text,'|' order by x.id),'')) from public.strategy_candidate_events x),
      'execution_shadow_audit', (select md5(coalesce(string_agg(to_jsonb(x)::text,'|' order by x.id),'')) from public.execution_shadow_audit x),
      'journal_deliveries', (select md5(coalesce(string_agg(to_jsonb(x)::text,'|' order by x.id),'')) from public.journal_deliveries x)
  )
) as evidence;
-- Additionally export ALL run/item/event rows and complete protected-table
-- digests for coordinator_acceptance_verify.verify(before, after, ...).
-- Compare the complete preflight schema/trigger/index inventory independently.
-- No INSERT, UPDATE, DELETE, ALTER, repair or forced completion is authorized.
