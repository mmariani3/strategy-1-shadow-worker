-- Minimal existing Phase 1 contract for the isolated migration test; not a deployment baseline.
create role anon;
create role authenticated;
create role service_role bypassrls; -- Matches the Supabase backend role.
create table public.strategy_discovery_runs(id uuid primary key, session_date date, status text);
create table public.strategy_discovery_items(id uuid primary key,run_id uuid references public.strategy_discovery_runs(id),promotion_status text);
create table public.strategy_candidates(id uuid primary key,source_discovery_item_id uuid,session_date date,
    last_signal_id uuid,journal_trade_id text,ruleset_version text,experiment_class text);
create table public.strategy_candidate_events(id uuid primary key default gen_random_uuid(),candidate_id uuid,
    event_type text,event_at timestamptz,payload jsonb);
insert into public.strategy_discovery_runs values ('00000000-0000-4000-8000-000000000001','2026-09-15','PARTIAL');
insert into public.strategy_candidates(id,experiment_class) values ('00000000-0000-4000-8000-000000000002','STRATEGY_1');
grant select,insert,update on public.strategy_candidates,public.strategy_discovery_items,public.strategy_discovery_runs to service_role;
grant select,insert on public.strategy_candidate_events to service_role;
