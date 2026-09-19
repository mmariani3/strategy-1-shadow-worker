"""Private local attempt ledger: reserve before billing; never retry an ambiguous request."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from evidence_review import canonical, digest, unresolved_draft, validate_draft
from research_reviewer import ReviewBlocked, parse_response, compact_request, request_evidence_message


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class AttemptLedger:
    def __init__(self, path, max_calls):
        if type(max_calls) is not int or max_calls <= 0:
            raise ReviewBlocked('CALL_BUDGET_REQUIRED')
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('pragma synchronous=FULL')
        self.db.executescript('''
            create table if not exists budget(singleton integer primary key check(singleton=1), max_calls integer not null);
            create table if not exists requests(id text primary key, request text not null, created_at text not null);
            create table if not exists events(
                request_id text not null, event_type text not null, at text not null, payload text not null,
                unique(request_id,event_type));
            create trigger if not exists immutable_requests_update before update on requests begin select raise(abort,'immutable'); end;
            create trigger if not exists immutable_requests_delete before delete on requests begin select raise(abort,'immutable'); end;
            create trigger if not exists immutable_events_update before update on events begin select raise(abort,'immutable'); end;
            create trigger if not exists immutable_events_delete before delete on events begin select raise(abort,'immutable'); end;
            create trigger if not exists immutable_budget_update before update on budget begin select raise(abort,'immutable'); end;
            create trigger if not exists immutable_budget_delete before delete on budget begin select raise(abort,'immutable'); end;
        ''')
        self.db.execute('insert or ignore into budget values(1,?)', (max_calls,))
        if self.db.execute('select max_calls from budget').fetchone()['max_calls'] != max_calls:
            self.close()
            raise ReviewBlocked('EXISTING_BUDGET_DIFFERS')

    def close(self):
        self.db.close()

    def events(self, request_id):
        return {row['event_type']: dict(at=row['at'], payload=json.loads(row['payload']))
                for row in self.db.execute('select * from events where request_id=?', (request_id,))}

    def claim(self, request, now):
        compact_request(request)
        expected = digest(dict(version=request['implementation_version'],
                               prompt_version=request['prompt_version'], body=request['body']))
        if request['request_id'] != expected:
            raise ReviewBlocked('REQUEST_DIGEST_MISMATCH')
        self.db.execute('begin immediate')
        try:
            existing = self.db.execute('select request from requests where id=?', (expected,)).fetchone()
            if existing:
                if existing['request'] != canonical(request):
                    raise ReviewBlocked('REQUEST_HISTORY_CONFLICT')
                self.db.execute('commit')
                return False
            count = self.db.execute('select count(*) n from requests').fetchone()['n']
            maximum = self.db.execute('select max_calls from budget').fetchone()['max_calls']
            if count >= maximum:
                raise ReviewBlocked('CALL_BUDGET_EXHAUSTED')
            self.db.execute('insert into requests values(?,?,?)', (expected, canonical(request), now))
            self.db.execute('insert into events values(?,?,?,?)', (expected, 'DISPATCH_RESERVED', now, '{}'))
            self.db.execute('commit')  # Survives process loss before the remote request/acknowledgement.
            return True
        except Exception:
            if self.db.in_transaction:
                self.db.execute('rollback')
            raise

    def record(self, request_id, event_type, payload, now):
        self.db.execute('insert or ignore into events values(?,?,?,?)',
                        (request_id, event_type, now, canonical(payload)))
        stored = self.events(request_id)[event_type]
        if stored['payload'] != payload:
            raise ReviewBlocked('EVENT_HISTORY_CONFLICT')
        return stored


def execute_once(ledger, packet, request, provider, clock=utc_now):
    validate_draft(packet, unresolved_draft(packet, clock()), clock())
    if packet['packet_id'] != request['packet_id']:
        raise ReviewBlocked('REQUEST_PACKET_MISMATCH')
    if request['body']['input'][-1] != request_evidence_message(packet, request):
        raise ReviewBlocked('REQUEST_EVIDENCE_MISMATCH')
    from research_bounded import VERSIONS as BOUNDED_VERSIONS, validate_bounded_request
    if (request['implementation_version'], request['prompt_version']) == BOUNDED_VERSIONS:
        validate_bounded_request(packet, request)
    claimed = ledger.claim(request, clock())
    history = ledger.events(request['request_id'])
    if 'COMPLETED' in history:
        received = history['RECEIVED']
        if parse_response(packet, request, received['payload'], received['at']) != history['COMPLETED']['payload']:
            raise ReviewBlocked('COMPLETION_HISTORY_MISMATCH')
        return history['COMPLETED']['payload']
    if 'FAILED' in history:
        raise ReviewBlocked('PREVIOUS_ATTEMPT_FAILED_NO_RETRY')
    if not claimed and 'RECEIVED' not in history:
        raise ReviewBlocked('AMBIGUOUS_ATTEMPT_NO_RETRY')
    if claimed:
        try:
            metadata = getattr(provider, 'transport_metadata', None)
            if callable(metadata):
                ledger.record(request['request_id'], 'TRANSPORT_CONFIGURED', metadata(), clock())
            response = provider.respond(request['body'])
            ledger.record(request['request_id'], 'RECEIVED', response, clock())
        except Exception:
            ledger.record(request['request_id'], 'FAILED', {'code': 'PROVIDER_RESULT_UNKNOWN'}, clock())
            raise ReviewBlocked('PROVIDER_RESULT_UNKNOWN_NO_RETRY') from None
    received = ledger.events(request['request_id'])['RECEIVED']
    try:
        result = parse_response(packet, request, received['payload'], received['at'])
    except Exception:
        ledger.record(request['request_id'], 'FAILED', {'code': 'RESPONSE_VALIDATION_FAILED'}, clock())
        raise ReviewBlocked('RESPONSE_VALIDATION_FAILED') from None
    ledger.record(request['request_id'], 'COMPLETED', result, received['at'])
    return result
