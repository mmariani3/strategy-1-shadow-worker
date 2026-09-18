"""Offline planner/readback probe; connector transports patches ONLY to a named test copy.

Never invokes the production writer or contacts a network endpoint.
Usage: python tests/sheet_acceptance_probe.py before.json [after.json]
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from journal_projection import project_run
from journal_writer import plan,verify

run={"id":"00000000-0000-4000-8000-000000000091","session_date":"2026-09-15",
     "phase":"PREMARKET","created_at":"2026-09-15T13:00:00Z","ruleset_version":"v0.3","status":"PARTIAL","candidates_discovered":3,
     "experiment_class":"STRATEGY_1", # Local branch fixture only; never inserted in any live DB.
     "notes":"INFRASTRUCTURE_TEST: isolated fixture; excluded from all strategy evidence",
     "channel_status":{"earnings_guidance":"CHECKED_ALPACA_NEWS","cross_source_verification":"REVIEW_REQUIRED"}}
items=[{"id":f"00000000-0000-4000-8000-{i:012d}","run_id":run["id"],"symbol":symbol,
        "operational_state":state,"notes":run["notes"],"rejection_reason":"Fixture rejection" if state=="REJECTED" else None}
       for i,symbol,state in [(92,"TSTREVIEW","REVIEW_REQUIRED"),(93,"TSTWATCH","WATCHLIST_CANDIDATE"),(94,"TSTREJECT","REJECTED")]]
rows=project_run(run,items,[],[])
before=json.loads(Path(sys.argv[1]).read_text())
patches=plan(rows,before)
if len(sys.argv)>2:
    after=json.loads(Path(sys.argv[2]).read_text())
    verify(patches,after)
    assert not plan(rows,after),"Retry must be NOOP"
    for row in rows:
        grid=after[row['sheet_name']]['values']; index=grid[0].index(row['key_column'])
        assert sum(len(r)>index and r[index]==row['key'] for r in grid[1:])==1
    print(json.dumps({"status":"VERIFIED","unique_rows":len(rows),"retry":"NOOP","patches":len(patches),
        "transport":"Google Drive connector; ADC transport and PostgreSQL ledger not exercised by this probe"}))
else:
    print(json.dumps({"rows":rows,"patches":patches}))
