"""Opt-in Phase 1 process-journal writer. Never reads Signal Queue or submits orders."""
import argparse
import json
import os
from contextlib import contextmanager
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from google.auth import default as google_credentials
from google.auth.transport.requests import AuthorizedSession

from journal_projection import JOURNAL_SPREADSHEET_ID, project_run, candidate_projection
from journal_native import CELL_FIELDS, address, prepare_patch, requests_for

ALLOWED_SHEETS = {"Premarket Candidates", "Scan Coverage"}


class JournalConflict(RuntimeError):
    pass


def column_name(number):
    result = ""
    while number:
        number, digit = divmod(number - 1, 26)
        result = chr(65 + digit) + result
    return result


class GoogleSheets:
    def __init__(self, spreadsheet_id):
        credentials, _ = google_credentials(scopes=["https://www.googleapis.com/auth/spreadsheets"])
        self.http = AuthorizedSession(credentials)
        self.base = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"

    def read(self):
        response = self.http.get(self.base, params={"fields": "sheets.properties"}, timeout=30)
        response.raise_for_status()
        snapshot = {}
        for sheet in response.json()["sheets"]:
            prop = sheet["properties"]
            name = prop["title"]
            if name not in ALLOWED_SHEETS:
                continue
            grid = prop["gridProperties"]
            if grid["rowCount"] * grid["columnCount"] > 200000:
                raise JournalConflict("Sheet exceeds complete-read bound; no partial snapshot is accepted.")
            region = f"'{name}'!A1:{column_name(grid['columnCount'])}{grid['rowCount']}"
            response = self.http.get(self.base + "/values/" + region,
                                     params={"valueRenderOption": "FORMATTED_VALUE"}, timeout=30)
            response.raise_for_status()
            snapshot[name] = {"values": response.json().get("values", []), "row_count": grid["rowCount"]}
        if set(snapshot) != ALLOWED_SHEETS:
            raise JournalConflict("Required live Journal tabs missing.")
        return snapshot

    def native_cells(self, patches):
        bounds = {}
        for patch in patches:
            title, row, col = address(patch['range'])
            if title not in ALLOWED_SHEETS:
                raise JournalConflict('Unexpected native tab.')
            r0, r1, c1 = bounds.get(title, (row, row, col))
            bounds[title] = (min(r0, row), max(r1, row), max(c1, col))
        ranges = [f"'{name}'!A{r0+1}:{column_name(c1+1)}{r1+1}" for name, (r0, r1, c1) in bounds.items()]
        if sum((r1-r0+1)*(c1+1) for r0,r1,c1 in bounds.values()) > 200000:
            raise JournalConflict('Native read exceeds bounded limit.')
        response = self.http.get(self.base, params={'ranges': ranges, 'fields':
            f'sheets(properties,merges,protectedRanges,tables,data(startRow,startColumn,rowData(values({CELL_FIELDS}))))'}, timeout=30)
        response.raise_for_status()
        cells, ids = {}, {}
        for sheet in response.json()['sheets']:
            prop = sheet['properties']; title = prop['title']
            if title not in bounds:
                continue
            if any(sheet.get(k) for k in ('merges','protectedRanges','tables')):
                raise JournalConflict('Structured or protected sheet requires explicit native review.')
            ids[title] = prop['sheetId']
            r0,r1,c1 = bounds[title]
            grid = prop['gridProperties']
            if r1 >= grid['rowCount'] or c1 >= grid['columnCount']:
                raise JournalConflict('Native target outside grid.')
            for row in range(r0,r1+1):
                for col in range(c1+1):
                    cells[f"'{title}'!{column_name(col+1)}{row+1}"] = {}
            for data in sheet.get('data', []):
                for row, entry in enumerate(data.get('rowData', []), data.get('startRow', 0)):
                    for col, cell in enumerate(entry.get('values', []), data.get('startColumn', 0)):
                        cells[f"'{title}'!{column_name(col+1)}{row+1}"] = cell
        if set(ids) != set(bounds):
            raise JournalConflict('Native tab missing.')
        return cells, ids

    def prepare(self, patches):
        cells, ids = self.native_cells(patches)
        return [prepare_patch(p, cells[p['range']], ids[address(p['range'])[0]]) for p in patches]

    def verify_native(self, patches, stage):
        cells, ids = self.native_cells(patches)
        for patch in patches:
            native = patch.get('native') or {}
            if (native.get('version') != 1 or native.get('sheet_id') != ids[address(patch['range'])[0]]
                    or cells.get(patch['range']) != native.get(stage)):
                raise JournalConflict('Native cell mismatch; no delivery completion.')

    def write(self, patches):
        # No blind POST retry: the persistent pending delivery gates all later writers.
        response = self.http.post(self.base + ':batchUpdate',
                                  json={'requests': requests_for(patches)}, timeout=30)
        response.raise_for_status()


def normalized(value):
    return "" if value is None else str(value)


def plan(rows, snapshot):
    """Plan against all existing rows, reserving each insertion row once per batch."""
    grids = {name: [list(row) for row in tab["values"]] for name, tab in snapshot.items()}
    patches = []
    seen = set()
    for desired in rows:
        name, key_column, key = desired["sheet_name"], desired["key_column"], desired["key"]
        if name not in ALLOWED_SHEETS or (name, key) in seen:
            raise JournalConflict("Unexpected tab or duplicate source key.")
        seen.add((name, key))
        grid = grids[name]
        if not grid:
            raise JournalConflict("Missing Journal header row.")
        headers = grid[0]
        if len(headers) != len(set(headers)) or not set(desired["values"]).issubset(headers):
            raise JournalConflict("Journal headers missing or duplicated.")
        key_index = headers.index(key_column)
        def cell(row, index):
            return normalized(row[index]) if index < len(row) else ""
        matches = [i for i, row in enumerate(grid[1:], 1) if cell(row, key_index) == key]
        if len(matches) > 1:
            raise JournalConflict("Duplicate stable IDs in live Journal.")
        if matches:
            target = matches[0]
            for identity in ("Date", "Ticker", "Ruleset Version"):
                if identity in desired["values"]:
                    old = cell(grid[target], headers.index(identity))
                    if old and old != normalized(desired["values"][identity]):
                        raise JournalConflict("Existing row identity conflicts with source.")
        else:
            # Unkeyed historical rows cannot safely be merged or duplicated by inference.
            identities = ("Date", "Ticker") if name == "Premarket Candidates" else ("Date",)
            for row in grid[1:]:
                if not cell(row, key_index) and all(cell(row, headers.index(k)) == normalized(desired["values"][k]) for k in identities):
                    raise JournalConflict("Matching historical row has no stable ID; explicit reconciliation required.")
            target = next((i for i, row in enumerate(grid[1:], 1) if not any(normalized(v) for v in row)), len(grid))
            if target >= snapshot[name]["row_count"]:
                raise JournalConflict("No empty row within live sheet bounds.")
            if target == len(grid):
                grid.append([])
        old_row = grid[target]
        old_row.extend([""] * (len(headers) - len(old_row)))
        for header, value in desired["values"].items():
            if matches and header == "Notes":
                continue
            index = headers.index(header)
            value = "" if value is None else value
            if normalized(old_row[index]) != normalized(value):
                patches.append({"range": f"'{name}'!{column_name(index + 1)}{target + 1}", "values": [[value]]})
                old_row[index] = value
    return patches


def verify(patches, snapshot):
    import re
    for patch in patches:
        match = re.fullmatch(r"'([^']+)'!([A-Z]+)([0-9]+)", patch["range"])
        name, letters, row = match.groups()
        column = 0
        for letter in letters:
            column = column * 26 + ord(letter) - 64
        grid = snapshot[name]["values"]
        actual = grid[int(row) - 1][column - 1] if len(grid) >= int(row) and len(grid[int(row) - 1]) >= column else ""
        if normalized(actual) != normalized(patch["values"][0][0]):
            raise JournalConflict("Journal readback mismatch; delivery remains blocked.")


def deliver(rows, sheets, ledger):
    if ledger.pending():
        raise JournalConflict("An earlier delivery is unresolved. Do not retry or clear it automatically.")
    before = sheets.read()
    patches = plan(rows, before)
    if not patches:
        return {"status": "NOOP", "rows": len(rows)}
    patches = sheets.prepare(patches)
    if sheets.read() != before:
        raise JournalConflict("Journal changed before write; retry from a new live read.")
    sheets.verify_native(patches, 'before')
    delivery_id = ledger.begin(patches, rows)
    # Persist pending BEFORE crossing systems. Any failure leaves a durable barrier.
    sheets.write(patches)
    after = sheets.read()
    verify(patches, after)
    sheets.verify_native(patches, 'after')
    if plan(rows, after):
        raise JournalConflict("Source rows do not reconcile after write.")
    ledger.complete(delivery_id)
    return {"status": "VERIFIED", "rows": len(rows), "delivery_id": str(delivery_id)}


def reconcile_pending(sheets, ledger):
    """Read-only external reconciliation: finish an exact successful write, never resend it."""
    pending = ledger.pending()
    if not pending:
        return {'status': 'NO_PENDING'}
    patches, rows = pending.get('patches'), pending.get('source_rows')
    if not patches or not rows or any(p.get('native', {}).get('version') != 1 for p in patches):
        raise JournalConflict('Legacy or incomplete delivery requires explicit reconciliation.')
    before = sheets.read()
    verify(patches, before)
    sheets.verify_native(patches, 'after')
    if plan(rows, before) or sheets.read() != before:
        raise JournalConflict('Pending source does not reconcile against stable live state.')
    ledger.complete(pending['id'])
    return {'status': 'VERIFIED', 'delivery_id': str(pending['id']), 'sheet_writes': 0}


class PostgresLedger:
    def __init__(self, conn, spreadsheet_id):
        self.conn, self.spreadsheet_id = conn, spreadsheet_id

    def pending(self):
        return self.conn.execute("select id,patches,source_rows from public.journal_deliveries where spreadsheet_id=%s and status='PENDING'",
                                 (self.spreadsheet_id,)).fetchone()

    def begin(self, patches, rows):
        delivery_id = uuid4()
        self.conn.execute("insert into public.journal_deliveries(id,spreadsheet_id,patches,source_rows,status) values (%s,%s,%s,%s,'PENDING')",
                          (delivery_id, self.spreadsheet_id, Jsonb(patches), Jsonb(rows)))
        return delivery_id

    def complete(self, delivery_id):
        self.conn.execute("update public.journal_deliveries set status='VERIFIED',verified_at=now() where id=%s and status='PENDING'", (delivery_id,))


@contextmanager
def writer_lock(conn, spreadsheet_id):
    acquired = conn.execute("select pg_try_advisory_lock(hashtextextended(%s,0)) as acquired", (spreadsheet_id,)).fetchone()["acquired"]
    if not acquired:
        raise JournalConflict("Another journal writer is active.")
    try:
        yield
    finally:
        conn.execute("select pg_advisory_unlock(hashtextextended(%s,0))", (spreadsheet_id,))


def source_rows(conn, run_id=None, candidate_id=None):
    if run_id:
        run = conn.execute("select * from public.strategy_discovery_runs where id=%s for share", (run_id,)).fetchone()
        if not run or run["status"] == "IN_PROGRESS":
            raise JournalConflict("Run missing or not finalized.")
        items = conn.execute("select * from public.strategy_discovery_items where run_id=%s order by created_at,id for share", (run_id,)).fetchall()
        candidates = conn.execute("select c.* from public.strategy_candidates c join public.strategy_discovery_items i on i.id=c.source_discovery_item_id where i.run_id=%s order by c.id for share of c", (run_id,)).fetchall()
        signals = conn.execute("select s.* from public.strategy_signals s join public.strategy_candidates c on c.last_signal_id=s.id join public.strategy_discovery_items i on i.id=c.source_discovery_item_id where i.run_id=%s for share of s", (run_id,)).fetchall()
        if run.get("candidates_discovered") != len(items):
            raise JournalConflict("Finalized run count differs from complete discovery funnel.")
        return project_run(run, items, candidates, signals)
    c = conn.execute("select * from public.strategy_candidates where id=%s for share", (candidate_id,)).fetchone()
    if not c or c.get("source_discovery_item_id"):
        raise JournalConflict("Candidate missing or discovery-linked; use --run-id for complete funnel reconciliation.")
    signal = conn.execute("select * from public.strategy_signals where id=%s for share", (c.get("last_signal_id"),)).fetchone() if c.get("last_signal_id") else None
    if c.get("last_signal_id") and not signal:
        raise JournalConflict("Candidate signal missing.")
    return [candidate_projection(c, signal)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-id", type=UUID)
    group.add_argument("--candidate-id", type=UUID)
    group.add_argument('--reconcile-pending', action='store_true', help='Verify an ambiguous native delivery without resending it')
    parser.add_argument("--apply", action="store_true", help="Explicitly enable this invocation's Journal writes")
    args = parser.parse_args()
    spreadsheet_id = os.getenv("JOURNAL_SPREADSHEET_ID", JOURNAL_SPREADSHEET_ID)
    sheets = GoogleSheets(spreadsheet_id)
    # Direct/session-pooled connections only. Transaction pooling cannot hold a session lock.
    with psycopg.connect(os.environ["JOURNAL_DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
        with writer_lock(conn, spreadsheet_id), conn.transaction():
            if args.reconcile_pending:
                if not args.apply or os.getenv('JOURNAL_WRITES_ENABLED', 'false').lower() != 'true':
                    raise JournalConflict('Reconciliation changes ledger state; explicit apply and enable flag required.')
                with psycopg.connect(os.environ['JOURNAL_DATABASE_URL'], autocommit=True, row_factory=dict_row) as ledger_conn:
                    print(json.dumps(reconcile_pending(sheets, PostgresLedger(ledger_conn, spreadsheet_id))))
                return
            rows = source_rows(conn, args.run_id, args.candidate_id)
            if not args.apply:
                print(json.dumps({"status": "DRY_RUN", "patches": plan(rows, sheets.read())}))
                return
            if os.getenv("JOURNAL_WRITES_ENABLED", "false").lower() != "true":
                raise JournalConflict("Journal writes are disabled; configure only after isolated acceptance testing.")
            with psycopg.connect(os.environ["JOURNAL_DATABASE_URL"], autocommit=True, row_factory=dict_row) as ledger_conn:
                print(json.dumps(deliver(rows, sheets, PostgresLedger(ledger_conn, spreadsheet_id))))


if __name__ == "__main__":
    main()
