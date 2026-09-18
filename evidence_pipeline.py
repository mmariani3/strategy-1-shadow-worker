"""Read-only discovery-to-research pipeline. Writes only content-addressed local artifacts."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from evidence_review import build_packets,canonical,digest,unresolved_draft,validate_draft,reviewer_request
from review_report import session_summary,render_summary


def json_value(value):
    return json.loads(json.dumps(value,default=str))


def load_snapshot(conn, run_id):
    # A separate snapshot transaction is read-only and repeatable; no session state/locks are advanced.
    with conn.transaction():
        conn.execute('set transaction isolation level repeatable read, read only')
        run=conn.execute('select * from public.strategy_discovery_runs where id=%s',(run_id,)).fetchone()
        if not run:raise ValueError('Discovery run not found.')
        items=conn.execute('select * from public.strategy_discovery_items where run_id=%s order by id',(run_id,)).fetchall()
        candidates=conn.execute('select c.* from public.strategy_candidates c join public.strategy_discovery_items i '
            'on i.id=c.source_discovery_item_id where i.run_id=%s order by c.id',(run_id,)).fetchall()
        signals=conn.execute('select s.* from public.strategy_signals s join public.strategy_candidates c '
            'on c.last_signal_id=s.id join public.strategy_discovery_items i on i.id=c.source_discovery_item_id '
            'where i.run_id=%s order by s.id',(run_id,)).fetchall()
        captured_at=datetime.now(timezone.utc).isoformat()
    return json_value({'run':run,'items':items,'candidates':candidates,'signals':signals,'captured_at':captured_at})


def produce(snapshot,authorities,responses=None,now=None):
    now=now or datetime.now(timezone.utc).isoformat()
    packets=build_packets(snapshot,authorities,snapshot['captured_at'])
    responses=responses or {}
    if not set(responses).issubset({p['packet_id'] for p in packets}):
        raise ValueError('Review response outside captured funnel.')
    reviews=[validate_draft(p,responses[p['packet_id']] if p['packet_id'] in responses
                           else unresolved_draft(p,now),now) for p in packets]
    bundle={'run':snapshot['run'],'packets':packets,'reviews':reviews,
            'source_snapshot_digest':digest(snapshot),'authority_digest':digest(authorities),
            'classification':'RESEARCH_ONLY','snapshot_captured_at':snapshot['captured_at']}
    report=session_summary([bundle],snapshot['run']['session_date'],now)
    return bundle,report


def write_once(directory,name,content):
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/name
    try:
        with target.open('x',encoding='utf-8',newline='\n') as output:output.write(content)
    except FileExistsError:
        if target.read_text(encoding='utf-8')!=content:
            raise ValueError('Existing artifact differs; refusing to overwrite review history.')
    return target


def save(bundle,report,directory):
    # Request and response snapshots are separate. Neither is an executable handoff.
    for packet in bundle['packets']:
        write_once(directory,'packet-'+packet['packet_id']+'.json',canonical(packet)+'\n')
        write_once(directory,'request-'+packet['packet_id']+'.json',canonical(reviewer_request(packet))+'\n')
    for review in bundle['reviews']:
        write_once(directory,'review-'+review['review_artifact_id']+'.json',canonical(review)+'\n')
    bundle_path=write_once(directory,'bundle-'+digest(bundle)+'.json',canonical(bundle)+'\n')
    report_path=write_once(directory,'summary-'+report['report_id']+'.md',render_summary(report))
    write_once(directory,'summary-'+report['report_id']+'.json',canonical(report)+'\n')
    return {'bundle':str(bundle_path),'summary':str(report_path),'packet_count':len(bundle['packets']),
            'status':'RESEARCH_ONLY','external_writes':0,'model_calls':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--run-id',type=UUID)
    source.add_argument('--snapshot',type=Path,help='Captured JSON snapshot; does not connect to a database')
    parser.add_argument('--authorities',type=Path,required=True,help='Freshly read living-master identities/revisions')
    parser.add_argument('--responses',type=Path,help='Optional JSON map of packet ID to reviewer draft')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    authorities=json.loads(args.authorities.read_text(encoding='utf-8'))
    if args.snapshot:
        snapshot=json.loads(args.snapshot.read_text(encoding='utf-8'))
    else:
        with psycopg.connect(os.environ['REVIEW_DATABASE_URL'],autocommit=True,row_factory=dict_row) as conn:
            snapshot=load_snapshot(conn,args.run_id)
    responses=json.loads(args.responses.read_text(encoding='utf-8')) if args.responses else None
    bundle,report=produce(snapshot,authorities,responses)
    print(json.dumps(save(bundle,report,args.output)))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Do not echo source text, database URLs, connection strings or provider error bodies.
        print(json.dumps({'status':'BLOCKED','error_type':type(exc).__name__}))
        raise SystemExit(2)
