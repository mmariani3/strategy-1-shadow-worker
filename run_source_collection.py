"""Plan or explicitly fetch public evidence into a private local append-only store."""
import argparse
import json
import os
from pathlib import Path

from code_review import inspect_packet
from evidence_pipeline import write_once
from evidence_review import canonical
from public_evidence_http import PublicFetcher
from source_collector import CaptureStore, collection_plan, collect, derived_packets, now


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--store',type=Path,required=True)
    parser.add_argument('--plan',type=Path,help='Reuse a saved plan to resume the same collection key')
    parser.add_argument('--fetch',action='store_true',help='Permit bounded public GETs; never calls an AI model')
    parser.add_argument('--allow-host',action='append',default=[])
    parser.add_argument('--collection-key')
    parser.add_argument('--max-documents',type=int,default=0)
    parser.add_argument('--refresh',action='store_true',help='Explicitly check remote versions, using conditional GETs')
    args=parser.parse_args()
    bundle=json.loads(args.bundle.read_text(encoding='utf-8'))
    if args.plan:
        plan=json.loads(args.plan.read_text(encoding='utf-8'))
        if plan!=collection_plan(bundle,plan['checked_at']): raise ValueError('PLAN_MISMATCH')
    else:
        plan=collection_plan(bundle,now())
    plan_path=write_once(args.output,'collection-plan-'+plan['plan_id']+'.json',canonical(plan)+'\n')
    fetcher=None
    if args.fetch:
        if not args.collection_key or args.max_documents<=0 or not args.allow_host:
            parser.error('--fetch requires --collection-key, --max-documents and exact --allow-host entries')
        fetcher=PublicFetcher(args.allow_host,os.environ.get('EVIDENCE_USER_AGENT'))
    store=CaptureStore(args.store)
    try:
        report=collect(plan,store,fetcher,args.collection_key,args.max_documents,args.refresh,args.allow_host)
        packets=derived_packets(bundle,plan,report,store)
        checks=[inspect_packet(p,now()) for p in packets]
        for p in packets:
            if p.get('collection_id')==report['collection_id']:
                write_once(args.output,'packet-'+p['packet_id']+'.json',canonical(p)+'\n')
        # Store the collection identity separately: it binds retrieval evidence, not these index paths.
        index=dict(collection=report,derived_packet_ids=[p['packet_id'] for p in packets],
                   code_checks=checks,source_plan_file=str(plan_path))
        path=write_once(args.output,'collection-report-'+report['collection_id']+'.json',canonical(index)+'\n')
        from collections import Counter
        print(json.dumps(dict(status='RESEARCH_COLLECTION_RECORDED',report=str(path),plan=str(plan_path),
            total_records=len(packets),unique_urls=plan['unique_urls'],records_without_urls=plan['records_without_urls'],
            retrieval_counts=report['counts'],review_routes=dict(Counter(c['route'] for c in checks)),
            http_requests=report['http_requests'],model_calls=0,external_writes=0,eligible_for_handoff=False)))
    finally:
        store.close()


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(json.dumps(dict(status='BLOCKED',error_type=type(exc).__name__)))
        raise SystemExit(2)
