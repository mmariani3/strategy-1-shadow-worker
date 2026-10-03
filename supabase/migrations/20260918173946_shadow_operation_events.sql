-- Append-only operational history, separate from strategy decisions and observations.
begin;
create table public.shadow_operation_events (
    id bigint generated always as identity primary key,
    job_key text not null,
    event_type text not null check (event_type in ('PLANNED','DISPATCHED','COMPLETE','PARTIAL',
        'DATA_UNAVAILABLE','AMBIGUOUS','CLOSED','MISSED','CALENDAR_UNAVAILABLE',
        'WINDOW_INVALID','DEPENDENCY_UNAVAILABLE')),
    recorded_at timestamptz not null default now(),
    implementation_version text not null,
    payload jsonb not null check (jsonb_typeof(payload)='object')
);
create unique index shadow_operation_once on public.shadow_operation_events(job_key,event_type)
    where event_type in ('PLANNED','DISPATCHED');
create index shadow_operation_history on public.shadow_operation_events(job_key,id);
alter table public.shadow_operation_events enable row level security;
-- Reset broad Supabase default grants before granting only the backend contract.
revoke all on public.shadow_operation_events from public,anon,authenticated,service_role;
grant select,insert on public.shadow_operation_events to service_role;
revoke all on sequence public.shadow_operation_events_id_seq from public,anon,authenticated,service_role;
grant usage on sequence public.shadow_operation_events_id_seq to service_role;
commit;
