import copy
import re
from datetime import datetime
from types import SimpleNamespace

import pytest
from journal_writer import JournalConflict,deliver,plan,writer_lock
from journal_projection import project_run,candidate_projection,run_projection
from fastapi import HTTPException


class Sheets:
    def __init__(self,rows):
        self.snapshot={}
        for row in rows:
            self.snapshot[row["sheet_name"]]={"values":[list(row["values"])],"row_count":1000}
        self.writes=0
        self.fail_after_write=False
    def read(self): return copy.deepcopy(self.snapshot)
    def write(self,patches):
        self.writes+=1
        for patch in patches:
            name,letters,row=re.fullmatch(r"'([^']+)'!([A-Z]+)([0-9]+)",patch["range"]).groups()
            column=0
            for letter in letters: column=column*26+ord(letter)-64
            grid=self.snapshot[name]["values"]
            while len(grid)<int(row):grid.append([])
            while len(grid[int(row)-1])<column:grid[int(row)-1].append("")
            grid[int(row)-1][column-1]=patch["values"][0][0]
        if self.fail_after_write:raise TimeoutError("ambiguous remote success")


class Ledger:
    def __init__(self):self.state=None;self.completed=0
    def pending(self):return self.state
    def begin(self,patches,rows):self.state="delivery";return self.state
    def complete(self,_):self.state=None;self.completed+=1


@pytest.fixture
def rows():
    return [{"sheet_name":"Premarket Candidates","key_column":"Candidate ID","key":"one",
             "values":{"Candidate ID":"one","Date":"2026-09-15","Ticker":"LOCAL","Notes":"original","Operational State":"REVIEW_REQUIRED"}},
            {"sheet_name":"Scan Coverage","key_column":"Run ID","key":"run",
             "values":{"Run ID":"run","Date":"2026-09-15","Notes":"run"}}]


def test_write_readback_and_idempotent_retry(rows):
    sheets,ledger=Sheets(rows),Ledger()
    assert deliver(rows,sheets,ledger)["status"]=="VERIFIED"
    assert deliver(rows,sheets,ledger)["status"]=="NOOP"
    assert sheets.writes==1 and ledger.completed==1


def test_ambiguous_write_blocks_retry(rows):
    sheets,ledger=Sheets(rows),Ledger();sheets.fail_after_write=True
    with pytest.raises(TimeoutError):deliver(rows,sheets,ledger)
    with pytest.raises(JournalConflict):deliver(rows,sheets,ledger)
    assert sheets.writes==1 and ledger.pending()


def test_multiple_insertions_reserve_different_rows(rows):
    rows.append(copy.deepcopy(rows[0]));rows[-1]["key"]="two";rows[-1]["values"]["Candidate ID"]="two"
    sheets,ledger=Sheets(rows),Ledger()
    deliver(rows,sheets,ledger)
    assert len(sheets.snapshot["Premarket Candidates"]["values"])==3


def test_duplicate_ids_rejected(rows):
    sheets,ledger=Sheets(rows),Ledger();deliver(rows,sheets,ledger)
    grid=sheets.snapshot["Premarket Candidates"]["values"];grid.append(grid[1].copy())
    with pytest.raises(JournalConflict):deliver(rows,sheets,ledger)
    assert sheets.writes==1


def test_historical_unkeyed_match_requires_reconciliation(rows):
    sheets=Sheets(rows)
    sheets.snapshot["Premarket Candidates"]["values"].append(["","2026-09-15","LOCAL"])
    with pytest.raises(JournalConflict):plan(rows,sheets.read())


def test_notes_and_other_columns_preserved(rows):
    sheets,ledger=Sheets(rows),Ledger();deliver(rows,sheets,ledger)
    grid=sheets.snapshot["Premarket Candidates"]["values"]
    grid[1][3]="User note"
    rows[0]["values"]["Operational State"]="WATCHLIST_CANDIDATE"
    deliver(rows,sheets,ledger)
    assert grid[1][3]=="User note"


def test_changed_sheet_rejected_before_post(rows):
    sheets,ledger=Sheets(rows),Ledger();original=sheets.read;reads=0
    def read():
        nonlocal reads
        reads+=1
        if reads==2:sheets.snapshot["Premarket Candidates"]["values"].append(["human"])
        return original()
    sheets.read=read
    with pytest.raises(JournalConflict):deliver(rows,sheets,ledger)
    assert sheets.writes==0 and not ledger.pending()


def test_readback_mismatch_keeps_delivery_pending(rows):
    sheets,ledger=Sheets(rows),Ledger()
    sheets.write=lambda patches:None
    with pytest.raises(JournalConflict):deliver(rows,sheets,ledger)
    assert ledger.pending()


def test_lock_contention_prevents_delivery():
    class Connection:
        def execute(self,*args):return SimpleNamespace(fetchone=lambda:{"acquired":False})
    with pytest.raises(JournalConflict):
        with writer_lock(Connection(),"sheet"):pytest.fail("must not enter")


def test_discovery_funnel_before_any_signal():
    run={"id":"run","experiment_class":"STRATEGY_1","session_date":"2026-09-15","phase":"PREMARKET","created_at":"2026-09-15T13:00:00Z","ruleset_version":"v0.3","status":"PARTIAL","candidates_discovered":3}
    items=[{"id":str(i),"run_id":"run","symbol":"LOCAL","operational_state":state} for i,state in enumerate(["REVIEW_REQUIRED","WATCHLIST_CANDIDATE","REJECTED"])]
    projected=project_run(run,items,[],[])
    assert len(projected)==4
    assert {r["sheet_name"] for r in projected}=={"Scan Coverage","Premarket Candidates"}
    assert all(r["values"]["Worker Decision"]=="" for r in projected[1:])
    assert projected[-1]["values"]["Final Decision"]=="NO TRADE"


@pytest.mark.parametrize("classification",[None,"INFRASTRUCTURE_TEST"])
def test_infrastructure_and_unclassified_runs_excluded(classification):
    with pytest.raises(HTTPException): project_run({"experiment_class":classification},[],[],[])


def test_coverage_matches_live_dropdown_without_inferring_completion():
    run={"id":"run","session_date":"2026-09-15","phase":"PREMARKET","created_at":"2026-09-15T13:00:00Z","ruleset_version":"v0.3","status":"PARTIAL",
         "channel_status":{"earnings_guidance":"CHECKED_ALPACA_NEWS","cross_source_verification":"REVIEW_REQUIRED"}}
    row=run_projection(run)
    assert row["values"]["Earnings / Guidance"]=="Checked"
    assert row["values"]["Cross-Source Verification"]=="Unavailable"
    assert row["values"]["Scan Status"]=="Partial"
    assert row["trace"]["channel_status"]==run["channel_status"]


@pytest.mark.parametrize("phase,label", [("PREMARKET","Premarket"),("POST_OPEN","Post-Open Refresh")])
@pytest.mark.parametrize("timestamp", ["2026-09-18T06:34:25.927838-07:00", "2026-09-18T13:34:25.927838Z",
    datetime.fromisoformat("2026-09-18T09:34:25.927838-04:00")])
def test_scan_metadata_survives_delivery_and_retry(phase,label,timestamp):
    run={"id":"run","session_date":"2026-09-18","phase":phase,"created_at":timestamp,
         "updated_at":"2026-09-19T20:00:00Z","ruleset_version":"v0.3","status":"PARTIAL","notes":"Original evidence"}
    original=copy.deepcopy(run)
    row=run_projection(run)
    assert row["values"]["Scan Time"]=="2026-09-18T13:34:25.927838Z"
    assert f"{phase} ({label})" in row["values"]["Notes"]
    assert row["values"]["Notes"].endswith("Original evidence")
    assert row["trace"]["phase"]==phase
    assert row["trace"]["scan_started_at"]==row["values"]["Scan Time"]
    sheets,ledger=Sheets([row]),Ledger()
    assert deliver([row],sheets,ledger)["status"]=="VERIFIED"
    assert deliver([run_projection(run)],sheets,ledger)["status"]=="NOOP"
    assert sheets.writes==1 and run==original


@pytest.mark.parametrize("bad", [None,"", "not-a-time","2026-09-18", "2026-09-18T13:34:25",
                                 datetime(2026,9,18,13,34),123])
def test_missing_or_ambiguous_scan_time_blocks_projection(bad):
    with pytest.raises(HTTPException) as error:
        run_projection({"phase":"POST_OPEN","created_at":bad})
    assert error.value.status_code==409


@pytest.mark.parametrize("phase", [None,"", "POSTMARKET"])
def test_unknown_scan_phase_cannot_be_labeled_postopen(phase):
    with pytest.raises(HTTPException) as error:
        run_projection({"phase":phase,"created_at":"2026-09-18T13:34:25Z"})
    assert error.value.status_code==409


@pytest.mark.parametrize("mismatch",[None,"candidate_id","run_id","data_kind"])
def test_signal_projection_requires_matching_trace(candidate_data,mismatch):
    c={**candidate_data,"id":candidate_data["candidate_id"],"run_id":"run","ruleset_version":"v0.3",
       "discovery_phase":"POST_OPEN","last_signal_id":"signal","last_worker_decision":"WAIT",
       "operational_state":"WAITING_FOR_TRIGGER","reason_code":"TRIGGER_NOT_CONFIRMED"}
    signal={"id":"signal","symbol":c["symbol"],"ruleset_version":"v0.3","journal_trade_id":c["journal_trade_id"],
            "worker_version":"actual-build","experiment_class":"STRATEGY_1","decision":"WAIT",
            "decision_inputs":{"candidate_id":c["id"],"run_id":"run","data_kind":"MARKET"}}
    if mismatch:
        signal["decision_inputs"][mismatch]="wrong"
        with pytest.raises(HTTPException):candidate_projection(c,signal)
    else:
        result=candidate_projection(c,signal)
        assert result["trace"]=={"candidate_id":c["id"],"run_id":"run","signal_id":"signal","journal_trade_id":c["journal_trade_id"]}
        assert result["values"]["Final Decision"]=="WAIT"
