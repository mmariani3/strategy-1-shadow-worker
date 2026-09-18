"""Clone a loopback acceptance DB; prove snapshot isolation and read-only enforcement.

No production connection, external HTTP, model call, Sheet write or strategy evidence.
Requires the schema template produced by credentialed_writer_acceptance.py.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import requests

from evidence_pipeline import load_snapshot, produce, save
from evidence_review import AUTHORITIES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection-file',required=True)
    parser.add_argument('--template-db',required=True)
    args=parser.parse_args()
    config=json.loads(Path(args.connection_file).read_text(encoding='utf-8'))
    assert config['host']=='127.0.0.1' and not config.get('hostaddr')
    assert args.template_db.startswith('writer_acceptance_')
    def blocked(*args,**kwargs):raise AssertionError('External HTTP forbidden')
    requests.sessions.Session.request=blocked
    database='evidence_acceptance_'+uuid4().hex
    with psycopg.connect(**config,autocommit=True) as admin:
        admin.execute(sql.SQL('create database {} template {}').format(
            sql.Identifier(database),sql.Identifier(args.template_db)))
    config['dbname']=database
    run_id,item_one,item_two=uuid4(),uuid4(),uuid4()
    with psycopg.connect(**config,autocommit=True) as fixture:
        fixture.execute("insert into strategy_discovery_runs(id,session_date,phase,status,run_key,ruleset_version,"
            "experiment_class,candidates_discovered,notes) values(%s,'2026-09-18','POST_OPEN','PARTIAL',%s,'v0.3',"
            "'INFRASTRUCTURE_TEST',2,'Isolated evidence pipeline fixture')",(run_id,str(run_id)))
        for item,symbol in ((item_one,'LOCAL'),(item_two,'OTHER')):
            fixture.execute("insert into strategy_discovery_items(id,run_id,symbol,operational_state) "
                            "values(%s,%s,%s,'REVIEW_REQUIRED')",(item,run_id,symbol))
    read_at=datetime.now(timezone.utc).isoformat()
    authorities={role:dict(document_id=doc,version=version,revision_id='isolated-fixture',read_at=read_at)
                 for role,(doc,version) in AUTHORITIES.items()}
    probes=[]
    with psycopg.connect(**config,autocommit=True,row_factory=dict_row) as reader:
        class CheckedConnection:
            def transaction(self):return reader.transaction()
            def execute(self,query,params=None):
                result=reader.execute(query,params)
                if query.startswith('select * from public.strategy_discovery_runs'):
                    assert reader.execute('show transaction_read_only').fetchone()['transaction_read_only']=='on'
                    # A savepoint allows the test to prove writes are rejected without aborting the snapshot.
                    try:
                        with reader.transaction():
                            reader.execute('delete from strategy_discovery_items where id=%s',(item_one,))
                    except psycopg.errors.ReadOnlySqlTransaction:probes.append('WRITE_REJECTED')
                    else:raise AssertionError('Read path admitted a database write')
                    with psycopg.connect(**config,autocommit=True) as concurrent_fixture:
                        concurrent_fixture.execute("update strategy_discovery_items set symbol='CHANGED' where id=%s",(item_one,))
                return result
        snapshot=load_snapshot(CheckedConnection(),run_id)
        assert {item['symbol'] for item in snapshot['items']}=={'LOCAL','OTHER'}
        assert reader.execute('select symbol from strategy_discovery_items where id=%s',(item_one,)).fetchone()['symbol']=='CHANGED'
    bundle,report=produce(snapshot,authorities)
    assert len(bundle['packets'])==2 and report['infrastructure_records_excluded']==2
    assert report['strategy_discovery_records']==0 and report['opportunity_outcome']=='UNKNOWN'
    assert probes==['WRITE_REJECTED']
    directory=Path(__file__).resolve().parents[1]/'.tmp'/database
    output=save(bundle,report,directory)
    assert save(bundle,report,directory)==output
    print(json.dumps(dict(status='PASSED',database=database,packets=2,read_only_enforced=True,
        repeatable_snapshot=True,immutable_retry=True,external_http=False,production_writes=0)))


if __name__=='__main__':main()
