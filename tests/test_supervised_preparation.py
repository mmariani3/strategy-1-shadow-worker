from copy import deepcopy
from pathlib import Path
import json
import subprocess
import sys

import pytest

from evidence_review import digest
from supervised_preparation import prepare, render, save, STRATEGY_REVISION
from test_evidence_review import authorities, snapshot, NOW


@pytest.fixture
def inputs(snapshot, authorities):
    authorities["strategy"]["revision_id"] = STRATEGY_REVISION
    checks = deepcopy(authorities)
    checks["strategy"]["read_at"] = NOW
    return snapshot, authorities, checks


def test_full_funnel_classification_and_source_times(inputs):
    before = deepcopy(inputs)
    result = prepare(*inputs, "2026-09-24T14:00:00Z")
    assert len(result["candidates"]) == 2
    assert result["source_context"] == "HISTORICAL_REPLAY"
    assert result["source_captured_at"] == NOW
    assert result["journal_draft"]["rows"] == []
    assert result["journal_draft"]["executed_trade_rows"] == []
    assert result["experiment_class"] == "INFRASTRUCTURE_TEST"
    assert not result["execution_enabled"] and not result["eligible_for_handoff"]
    assert result["model_calls"] == result["external_writes"] == 0
    assert inputs == before


def test_same_day_capture_never_claims_live_approval(inputs):
    result = prepare(*inputs, NOW)
    assert result["source_context"] == "CAPTURED_SNAPSHOT_NOT_LIVE"
    assert all(c["current_approval"] == "NOT_ESTABLISHED" for c in result["candidates"])


def test_preserves_rejection_and_does_not_invent_signal(inputs):
    inputs[0]["items"][0].update(operational_state="REJECTED", rejection_reason="Missed trigger")
    result = prepare(*inputs, NOW)
    c = result["candidates"][0]
    assert c["rejection_reason"] == "Missed trigger"
    assert c["trace"] == dict(run_id="run", source_discovery_item_id="one",
                              candidate_id=None, signal_id=None, journal_trade_id=None)


@pytest.mark.parametrize("mutation", ["revision", "reviewed_rule", "future_read", "future_capture", "count", "duplicate", "blank_id", "class"])
def test_invalid_or_changed_sources_block(inputs, mutation):
    snapshot, authorities, checks = inputs
    if mutation == "revision": checks["experiment"]["revision_id"] = "changed"
    if mutation == "reviewed_rule":
        authorities["strategy"]["revision_id"] = checks["strategy"]["revision_id"] = "unreviewed"
    if mutation == "future_read": checks["strategy"]["read_at"] = "2026-10-01T12:00:00Z"
    if mutation == "future_capture": snapshot["captured_at"] = "2026-10-01T12:00:00Z"
    if mutation == "count": snapshot["run"]["candidates_discovered"] = 3
    if mutation == "duplicate": snapshot["items"][1] = snapshot["items"][0]
    if mutation == "blank_id": snapshot["items"][0]["id"] = ""
    if mutation == "class": snapshot["run"]["experiment_class"] = "UNCLASSIFIED"
    with pytest.raises(ValueError): prepare(*inputs, NOW)


def test_empty_partial_scan_is_not_complete_or_an_opportunity(inputs):
    inputs[0]["items"] = []
    inputs[0]["run"]["candidates_discovered"] = 0
    result = prepare(*inputs, NOW)
    assert not result["candidates"] and result["opportunity_count"] is None
    assert result["coverage"]["status"] == "PARTIAL"


def test_trace_links_retained(inputs):
    s = inputs[0]
    s["candidates"] = [{"id": "c", "source_discovery_item_id": "one", "run_id": "run", "symbol": "LOCAL",
                        "experiment_class": "INFRASTRUCTURE_TEST", "last_signal_id": "s", "journal_trade_id": "j"}]
    s["signals"] = [{"id": "s", "journal_trade_id": "j", "experiment_class": "INFRASTRUCTURE_TEST",
                     "decision_inputs": {"candidate_id": "c", "run_id": "run"}}]
    assert prepare(*inputs, NOW)["candidates"][0]["trace"] == dict(run_id="run", source_discovery_item_id="one",
                                                                      candidate_id="c", signal_id="s", journal_trade_id="j")
    s["signals"][0]["decision_inputs"]["run_id"] = "other"
    with pytest.raises(ValueError): prepare(*inputs, NOW)


def test_strategy_projection_is_draft_only_and_not_written(inputs, monkeypatch):
    # Isolated adapter test, never delivered to the live Journal or execution path.
    inputs[0]["run"]["experiment_class"] = "STRATEGY_1"
    calls = []
    def projection(*args):
        calls.append(args)
        return [{"sheet_name": "Scan Coverage", "key": "isolated-fixture"}]
    monkeypatch.setattr("supervised_preparation.project_run", projection)
    result = prepare(*inputs, NOW)
    assert len(calls) == 1 and len(result["journal_draft"]["rows"]) == 1
    assert not result["journal_draft"]["live_sheet_read"]
    assert result["journal_draft"]["status"] == "DRAFT_REQUIRES_LIVE_RECONCILIATION"


def test_untrusted_html_is_text_and_no_network_is_allowed(inputs):
    inputs[0]["items"][0]["news_evidence"][0]["summary"] = '</script><img src=x onerror="alert(1)">'
    result = prepare(*inputs, NOW)
    html = render(result)
    assert '<img src=x' not in html
    assert '&lt;/script&gt;&lt;img' in html
    assert "connect-src 'none'" in html and "form-action 'none'" in html
    assert "\\u003c/script\\u003e" in html
    assert "No opportunity ranking" in html


def test_content_addressed_retry_and_history(inputs, tmp_path):
    result = prepare(*inputs, NOW)
    page = save(result, tmp_path)
    before = page.stat().st_mtime_ns
    assert save(result, tmp_path) == page
    assert page.stat().st_mtime_ns == before
    assert json.loads(page.with_name("preparation.json").read_text())["preparation_id"] == result["preparation_id"]
    page.write_text("operator edit", encoding="utf-8")
    with pytest.raises(ValueError): save(result, tmp_path)
    assert page.read_text() == "operator edit"


def test_changed_report_cannot_render_as_original(inputs):
    result = prepare(*inputs, NOW)
    result["execution_enabled"] = True
    with pytest.raises(ValueError): render(result)


def test_cli_offline_runs_without_credentials(inputs, tmp_path):
    for name, data in zip(("snapshot", "authorities", "checks"), inputs):
        (tmp_path / (name + ".json")).write_text(json.dumps(data), encoding="utf-8")
    cli = Path(__file__).resolve().parents[1] / "supervised_preparation.py"
    command = [sys.executable, str(cli), "--snapshot", str(tmp_path / "snapshot.json"),
               "--authorities", str(tmp_path / "authorities.json"), "--authority-checks", str(tmp_path / "checks.json"),
               "--prepared-at", NOW, "--output", str(tmp_path / "output")]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["external_writes"] == 0
    failed = subprocess.run(command + ["--apply"], capture_output=True, text=True)
    assert failed.returncode != 0
