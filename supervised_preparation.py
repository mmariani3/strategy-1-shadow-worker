"""Build a local human preparation page. No qualification, orders or Journal writes."""
import argparse
import base64
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
from uuid import UUID

from code_review import inspect_packet
from evidence_pipeline import load_snapshot, write_once
from evidence_review import AUTHORITIES, aware, build_packets, canonical, check_authorities, digest
from journal_projection import project_run
from review_contract import MARKET_TZ

VERSION = "1.0.0-supervised-preparation"
FILES = ("supervised_preparation.py", "supervised_preparation.js", "code_review.py",
         "evidence_review.py", "evidence_pipeline.py", "journal_projection.py", "review_contract.py")
# A changed governing revision requires deliberate review of this calculator contract.
STRATEGY_REVISION = "ANLCKQlpoauv4o_e_Ut3p4XGlBvaAjNqPrikkRGldDjpjirxqWxq8jeKFBdoJpuq2ul5Bvlh26vWGhdcyzzyfSE2tqOMCcqtEE1IX8nDOqs"
LIMITS = {"max_risk": "50", "max_notional": "10000", "max_daily_loss": "100",
          "max_trades": "3", "minimum_rr": "1.5", "preferred_rr": "2"}


def implementation():
    return VERSION + ";sha256=" + digest({name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                        for name in FILES})


def prepare(snapshot, authorities, authority_checks, now):
    """Keep source capture time separate from generation and master-recheck times."""
    check_authorities(authorities, snapshot["captured_at"])
    check_authorities(authority_checks, now)
    if not aware(snapshot["captured_at"]) <= aware(now):
        raise ValueError("Future source capture.")
    for role in AUTHORITIES:
        if authorities[role]["revision_id"] != authority_checks[role]["revision_id"]:
            raise ValueError("Master changed; source packet needs explicit review/rebinding.")
    if authority_checks["strategy"]["revision_id"] != STRATEGY_REVISION:
        raise ValueError("Risk calculator has not been reviewed against this Strategy revision.")
    run = snapshot["run"]
    packets = build_packets(snapshot, authorities, snapshot["captured_at"])
    # Even a zero-item run must be a complete, finalized, dated source snapshot.
    if type(run["candidates_discovered"]) is not int or run["candidates_discovered"] < 0:
        raise ValueError("Invalid discovery count.")
    for group in (snapshot["items"], snapshot.get("candidates", []), snapshot.get("signals", [])):
        if any(not isinstance(row.get("id"), str) or not row["id"].strip() for row in group):
            raise ValueError("Nonblank string IDs required.")
    candidates = []
    for packet in packets:
        source_item = next(s["raw"] for s in packet["sources"] if s["kind"] == "discovery_record")
        candidates.append({"symbol": packet["symbol"], "trace": packet["trace"],
            "packet_id": packet["packet_id"], "source_state": packet["source_state"],
            "rejection_reason": source_item.get("rejection_reason"),
            "sources": packet["sources"], "unresolved": packet["gaps"],
            "checks": inspect_packet(packet, now),
            "current_approval": "NOT_ESTABLISHED", "eligible_for_handoff": False})
    # Production rows remain drafts. Infrastructure fixtures never get production projections.
    rows = project_run(run, snapshot["items"], snapshot.get("candidates", []), snapshot.get("signals", [])) \
        if run["experiment_class"] == "STRATEGY_1" else []
    historical = run["session_date"] != aware(now).astimezone(MARKET_TZ).date().isoformat()
    report = {"implementation_version": implementation(), "prepared_at": now,
        "source_captured_at": snapshot["captured_at"], "source_snapshot_digest": digest(snapshot),
        "authority_refs_at_capture": deepcopy(authorities), "authority_checks": deepcopy(authority_checks),
        "session_date": run["session_date"], "run_id": run["id"], "phase": "SHADOW",
        "experiment_class": run["experiment_class"], "classification": "PREPARATION_ONLY",
        "source_context": "HISTORICAL_REPLAY" if historical else "CAPTURED_SNAPSHOT_NOT_LIVE",
        "execution_enabled": False, "eligible_for_handoff": False, "model_calls": 0,
        "external_writes": 0, "opportunity_count": None, "risk_limits": LIMITS,
        "coverage": deepcopy(run), "candidates": candidates,
        "journal_draft": {"status": "DRAFT_REQUIRES_LIVE_RECONCILIATION", "live_sheet_read": False,
                          "rows": rows, "executed_trade_rows": []}}
    report["preparation_id"] = digest(report)
    return report


def text_block(value):
    return "<pre>" + escape(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)) + "</pre>"


def source_digest(sources):
    """Extract captured headlines/summaries verbatim; never infer a catalyst or tier."""
    parts = []
    for source in sources:
        if source["kind"] not in ("news", "filing", "retrieved_document"):
            continue
        raw = source["raw"]
        headline = raw.get("headline_or_event") or raw.get("headline") or raw.get("title") or raw.get("form")
        summary = raw.get("summary")
        parts.append("<article><h4>" + escape(str(headline or "Source document; headline unavailable")) + "</h4>"
                     + "<p class=muted>" + escape(str(raw.get("source") or "Source name unavailable"))
                     + " · " + escape(str(raw.get("event_timestamp") or "Source timestamp unavailable")) + "</p>"
                     + ("<p>" + escape(summary) + "</p>" if isinstance(summary, str) else "")
                     + "<small>Captured source wording; event timing and meaning need review.</small></article>")
    return "".join(parts) or "<p>No captured catalyst document. Further source collection is required.</p>"


def render(report):
    """Escape evidence as text; no source HTML, external assets or credential storage."""
    if digest({k: v for k, v in report.items() if k != "preparation_id"}) != report["preparation_id"]:
        raise ValueError("Preparation artifact changed.")
    cards = []
    for i, candidate in enumerate(report["candidates"]):
        sources = []
        for source in candidate["sources"]:
            sources.append("<details><summary>" + escape(source["kind"]) + " — captured evidence</summary>"
                           + "<p>" + escape(source["timestamp_semantics"]) + "</p>"
                           + text_block(source["raw"]) + "<small>Source ID: " + escape(source["source_id"])
                           + "</small></details>")
        cards.append(f'<details class="candidate" data-index="{i}"><summary>'
                     + escape(candidate["symbol"]) + " · " + escape(candidate["source_state"])
                     + " (captured state)</summary><p><strong>Current approval: not established.</strong></p>"
                     + ("<p>Captured rejection: " + escape(str(candidate["rejection_reason"])) + "</p>"
                        if candidate["rejection_reason"] else "")
                     + "<h3>Research digest</h3>" + source_digest(candidate["sources"])
                     + "<details><summary>Unresolved checks</summary>" + text_block(candidate["unresolved"]) + "</details>"
                     + "<details><summary>Full captured evidence and source identifiers</summary>" + "".join(sources) + "</details>"
                     + "<details><summary>Arithmetic and input checks at capture</summary>"
                     + text_block(candidate["checks"]) + "</details>"
                     + "<details><summary>Record identifiers</summary>" + text_block(candidate["trace"])
                     + "</details></details>")
    js = Path(__file__).with_suffix(".js").read_text(encoding="utf-8")
    script_hash = base64.b64encode(sha256(js.encode()).digest()).decode()
    # Escape '<' so untrusted evidence cannot close the data script element.
    data = canonical(report).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    fields = "".join(f'<label>{label}<input id="{key}" inputmode="decimal" autocomplete="off"></label>'
                     for key, label in (("entry", "Planned entry ($)"), ("stop", "Structural stop ($)"),
                                        ("target", "Planned target ($)"), ("budget", "Chosen risk budget ($; at most 50)"),
                                        ("loss", "Realized daily loss ($)"), ("trades", "Executed trades today")))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; connect-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'">
<title>Supervised paper preparation</title><style>
body{{font:16px/1.5 system-ui,sans-serif;background:#f3f6f8;color:#172d3b;margin:0}}main{{max-width:1050px;margin:auto;padding:24px}}
h1{{font-size:30px;line-height:1.2}}h2{{font-size:23px}}section,details.candidate{{background:white;border:1px solid #d6e1e7;border-radius:12px;padding:20px;margin:18px 0}}
.notice{{border-left:5px solid #ba7616;background:#fff2db;padding:16px}}.muted,small{{color:#49606f}}summary{{cursor:pointer;font-weight:650;padding:8px 0}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f7;padding:12px;border-radius:6px;font-size:13px}}details details{{border-top:1px solid #ddd;padding:10px}}
label{{display:block}}input,select,textarea,button{{font:inherit;padding:10px;border:1px solid #9aacb7;border-radius:6px;box-sizing:border-box;width:100%}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}button{{background:#155b6a;color:white;cursor:pointer;margin-top:12px;width:auto}}button:disabled{{opacity:.45;cursor:default}}textarea{{min-height:100px}}a{{color:#155b6a}}#candidates{{max-height:38rem;overflow:auto}}article{{border-left:3px solid #ccdce4;padding-left:14px;margin:20px 0}}@media print{{button{{display:none}}#candidates{{max-height:none;overflow:visible}}}}
</style></head><body><main>
<p class="muted">STRATEGY #1 · SUPERVISED PREPARATION · SHADOW</p><h1>Your session preparation</h1>
<div class="notice"><strong>{escape(report['source_context'])} · {escape(report['experiment_class'])}</strong><br>
Source session: {escape(report['session_date'])}. This page does not refresh market data, approve setups, submit orders or write to the Journal.
Historical source states and arithmetic are not current trading permissions.</div>
<p>Snapshot captured: {escape(report['source_captured_at'])}<br>Page prepared: {escape(report['prepared_at'])}</p>
<p><a href="#risk">Go to risk planning</a> · <a href="#journal">Go to Journal drafts</a></p>
<section><h2>1. Review the discovery</h2><p>{len(cards)} candidates retained, including rejections. No opportunity ranking or trade count is inferred. Discovered names are not necessarily eligible instruments.</p>
<details><summary>Scan coverage and macro context</summary>{text_block(report['coverage'])}</details>
<label>Find a symbol <input id="filter" type="search" placeholder="All candidates are retained"></label><p id="shown"></p></section>
<div id="candidates">{''.join(cards)}</div>
<section id="risk"><h2>2. Plan risk after reviewing the setup</h2><p>Enter your proposed levels. The calculator checks arithmetic against v0.3 ceilings only. It does not choose the setup, validate the target or confirm a trigger. Nothing is preapproved.</p>
<div class="grid"><label>Candidate<select id="candidate"><option value="">Select a candidate</option></select></label>
<label>Direction<select id="direction"><option value="">Select direction</option><option>LONG</option><option>SHORT</option></select></label>{fields}</div>
<button id="calculate" type="button">Calculate planning figures</button><pre id="calculation" role="status">No calculation yet.</pre>
<p>Inputs accept up to eight decimal places; this is an arithmetic input limit, not a trading threshold. Required live data, current approvals, daily counters and confirmation must be rechecked before any action.</p>
<label>Reviewer name<input id="reviewer" autocomplete="off"></label>
<label>Market-data source and timestamp; setup reasoning; unresolved questions<textarea id="notes"></textarea></label>
<button id="save-plan" type="button" disabled>Save planning draft</button>
<p id="save-status">Drafts are not saved automatically. Saving downloads a local JSON file; it does not journal or approve a trade.</p></section>
<section id="journal"><h2>3. Review the draft Journal records</h2><p>Status: draft only. The live Sheet has not been read or changed. Reconcile stable IDs against the live Journal before any delivery through the approved writer.</p>
<p>{len(report['journal_draft']['rows'])} proposed process records; zero executed-trade records.</p>
<details><summary>Inspect draft rows</summary>{text_block(report['journal_draft'])}</details>
<button id="save-journal" type="button">Save Journal draft package</button></section>
<section><h2>Your live review still covers</h2><ul><li>Material, fresh catalyst and same-event source verification.</li><li>Market context, liquidity, participation and reliable data.</li><li>Approved setup, structural stop, target and prospective trigger confirmation.</li><li>Current account risk, permitted execution route and supervision until predefined exit.</li></ul>
<p>Missing or stale inputs remain unresolved. A price crossing alone is not confirmation. NO TRADE is valid.</p>
<details><summary>Authority checks and implementation attribution</summary>{text_block(report['authority_checks'])}<p>{escape(report['implementation_version'])}</p><p>Preparation ID: {report['preparation_id']}</p></details></section>
<script type="application/json" id="preparation-data">{data}</script><script>{js}</script></main></body></html>'''


def save(report, output):
    root = Path(output) / ("preparation-" + report["preparation_id"])
    payload = canonical(report) + "\n"
    page = render(report)
    # Reject differing artifacts before touching either file; exclusive creation protects retries.
    for name, content in (("preparation.json", payload), ("index.html", page)):
        if (root / name).exists() and (root / name).read_text(encoding="utf-8") != content:
            raise ValueError("Existing preparation differs; history cannot be overwritten.")
    write_once(root, "preparation.json", payload)
    return write_once(root, "index.html", page)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--snapshot", type=Path)
    source.add_argument("--run-id", type=UUID, help="Read-only existing discovery snapshot; never starts a scan")
    parser.add_argument("--authorities", type=Path, required=True, help="Authority references at source capture")
    parser.add_argument("--authority-checks", type=Path, required=True, help="Explicit living-master revision rechecks")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared-at", help="Fixed timestamp for reproducible replay; not a freshness approval")
    args = parser.parse_args()
    if args.snapshot:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    else:
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(os.environ["REVIEW_DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
            snapshot = load_snapshot(conn, args.run_id)
    report = prepare(snapshot, json.loads(args.authorities.read_text(encoding="utf-8")),
                     json.loads(args.authority_checks.read_text(encoding="utf-8")),
                     args.prepared_at or datetime.now(timezone.utc).isoformat())
    print(json.dumps({"status": "PREPARATION_ONLY", "page": str(save(report, args.output)),
                      "candidates": len(report["candidates"]), "model_calls": 0, "external_writes": 0}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED", "error_type": type(exc).__name__}))
        raise SystemExit(2)
