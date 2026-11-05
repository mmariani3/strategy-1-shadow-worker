-- Infrastructure only. Apply to the existing Phase 1 schema, never by the app.
-- No historical classifications, decisions, or input snapshots are rewritten.
begin;

alter table public.strategy_discovery_runs
    add column if not exists experiment_class text,
    add column if not exists transition_context jsonb;
alter table public.strategy_discovery_items
    add column if not exists qualification_review jsonb,
    add column if not exists setup_review jsonb,
    add column if not exists rejection_review jsonb,
    add column if not exists operational_state text,
    add column if not exists transition_context jsonb;
alter table public.strategy_candidates
    add column if not exists run_id uuid references public.strategy_discovery_runs(id),
    add column if not exists current_review jsonb,
    add column if not exists data_kind text,
    add column if not exists confirmation_review_id text,
    add column if not exists transition_context jsonb,
    add column if not exists operational_state text,
    add column if not exists reason_code text,
    add column if not exists data_timestamp timestamptz,
    add column if not exists data_quality_ok boolean,
    add column if not exists lifecycle_revision integer not null default 0;

create table public.strategy_discovery_events (
    id uuid primary key default gen_random_uuid(),
    event_at timestamptz not null default now(),
    run_id uuid not null references public.strategy_discovery_runs(id),
    discovery_item_id uuid references public.strategy_discovery_items(id),
    payload jsonb not null
);
alter table public.strategy_discovery_events enable row level security;
revoke all on public.strategy_discovery_events from public, anon, authenticated;
grant select, insert on public.strategy_discovery_events to service_role;

-- Trigger writes share the candidate transaction: failed audit insert rolls back state.
create function public.audit_shadow_candidate() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
    insert into public.strategy_candidate_events(candidate_id,event_type,event_at,payload)
    values(new.id,'UPDATED',now(),jsonb_build_object(
        'owner',coalesce(new.transition_context->>'owner',current_user),
        'implementation_version',new.transition_context->>'implementation_version',
        'reviewer',new.transition_context->>'reviewer',
        'reason',coalesce(new.reason_code,'CANDIDATE_INGESTED'),
        'previous_state',case when tg_op='UPDATE' then old.operational_state else null end,
        'new_state',new.operational_state,
        'run_id',new.run_id,'candidate_id',new.id,'signal_id',new.last_signal_id,
        'journal_trade_id',new.journal_trade_id,'ruleset_version',new.ruleset_version,
        'before',case when tg_op='UPDATE' then to_jsonb(old) else null end,
        'after',to_jsonb(new)));
    return new;
end $$;
revoke all on function public.audit_shadow_candidate() from public, anon, authenticated;
create trigger audit_shadow_candidate after insert or update on public.strategy_candidates
for each row execute function public.audit_shadow_candidate();

create function public.audit_shadow_discovery() returns trigger
language plpgsql security invoker set search_path = '' as $$
declare after_row jsonb := to_jsonb(new); before_row jsonb;
begin
    if tg_op='UPDATE' then before_row := to_jsonb(old); end if;
    insert into public.strategy_discovery_events(run_id,discovery_item_id,payload)
    values(case when tg_table_name='strategy_discovery_runs' then new.id else (after_row->>'run_id')::uuid end,
        case when tg_table_name='strategy_discovery_items' then new.id else null end,
        jsonb_build_object('owner',coalesce(after_row->'transition_context'->>'owner',current_user),
            'implementation_version',after_row->'transition_context'->>'implementation_version',
            'reviewer',after_row->'transition_context'->>'reviewer',
            'reason',after_row->'transition_context'->>'reason',
            'previous_state',coalesce(before_row->>'operational_state',before_row->>'status',before_row->>'promotion_status'),
            'new_state',coalesce(after_row->>'operational_state',after_row->>'status',after_row->>'promotion_status'),
            'before',before_row,'after',after_row));
    return new;
end $$;
revoke all on function public.audit_shadow_discovery() from public, anon, authenticated;
create trigger audit_shadow_discovery_run after insert or update on public.strategy_discovery_runs
for each row execute function public.audit_shadow_discovery();
create trigger audit_shadow_discovery_item after insert or update on public.strategy_discovery_items
for each row execute function public.audit_shadow_discovery();

create table public.journal_deliveries (
    id uuid primary key,
    spreadsheet_id text not null,
    created_at timestamptz not null default now(),
    verified_at timestamptz,
    status text not null check(status in ('PENDING','VERIFIED','RESOLVED_MANUALLY')),
    patches jsonb not null,
    source_rows jsonb not null,
    resolution_evidence jsonb,
    check(status <> 'RESOLVED_MANUALLY' or resolution_evidence is not null)
);
create unique index journal_one_unresolved_delivery on public.journal_deliveries(spreadsheet_id)
where status='PENDING';
alter table public.journal_deliveries enable row level security;
revoke all on public.journal_deliveries from public, anon, authenticated;
grant select, insert, update on public.journal_deliveries to service_role;

-- Existing candidate/signal constraints remain the authority for replay protection.
commit;
