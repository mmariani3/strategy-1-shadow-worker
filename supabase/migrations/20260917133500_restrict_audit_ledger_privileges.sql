-- Supabase may grant ALL to service_role through the creator's default ACL.
-- GRANT is additive: reset effective direct grants before granting the contract.
-- Preserve every row, existing migration, role default and strategy rule.
begin;

revoke all on public.strategy_candidate_events, public.strategy_discovery_events
    from public, anon, authenticated, service_role;
grant select, insert on public.strategy_candidate_events, public.strategy_discovery_events
    to service_role;

revoke all on public.journal_deliveries from public, anon, authenticated, service_role;
grant select, insert on public.journal_deliveries to service_role;
-- Keep source snapshots and exact patches immutable after insertion. The writer
-- and an authorized reconciliation operator only update the delivery outcome.
grant update (status, verified_at, resolution_evidence) on public.journal_deliveries
    to service_role;

revoke all on function public.audit_shadow_candidate(), public.audit_shadow_discovery()
    from public, anon, authenticated, service_role;
-- These are existing trigger functions. PostgreSQL checks EXECUTE when a trigger
-- is created, not when it fires; service_role trigger writes retain INSERT access.

commit;
