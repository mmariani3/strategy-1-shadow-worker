-- Accept every state now emitted by the discovery/setup handoff.
-- Existing WATCHLIST_CANDIDATE/WORKER_READY rows are preserved unchanged.
begin;
alter table public.strategy_discovery_items
    drop constraint if exists strategy_discovery_items_operational_state_check;
alter table public.strategy_discovery_items
    add constraint strategy_discovery_items_operational_state_check check (
        operational_state in ('REVIEW_REQUIRED','WATCHLIST_CANDIDATE','WORKER_READY',
            'HOLD_UNRESOLVED','WAITING_FOR_TRIGGER','CONFIRMATION_REQUIRED','TRADE_READY','REJECTED')
    );
commit;
