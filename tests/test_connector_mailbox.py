from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import json
import time

import pytest

from coordinator_connector_mailbox import ConnectorMailbox, host_request, host_response
from coordinator_connector_snapshot import ConnectorSnapshotCollector, connector_arguments
from coordinator_launch_guard import Blocked
from coordinator_service_adapters import AdapterError
from test_connector_snapshot import NOW, evidence, wrap
from test_coordinator_launch_guard import tmp_path
from test_coordinator_preflight_binding import rehearsal, probes


def test_actual_file_relay_routes_fixed_arguments_and_single_response(tmp_path):
    expiry=NOW+timedelta(minutes=10)
    mailbox=ConnectorMailbox(directory=tmp_path,day=NOW.date(),now=lambda:NOW,expires_at=expiry)
    collector=ConnectorSnapshotCollector(execute_sql=mailbox,day=NOW.date(),now=lambda:NOW)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(collector.collect)
        end=time.monotonic()+5
        while not list(tmp_path.glob("*.request.json")) and time.monotonic()<end: time.sleep(.01)
        file=next(tmp_path.glob("*.request.json")); nonce=file.name.split(".")[0]
        args=host_request(tmp_path,nonce,day=NOW.date(),now=NOW,expires_at=expiry)
        assert args==connector_arguments(NOW.date(),nonce)
        with pytest.raises(FileExistsError):
            host_request(tmp_path,nonce,day=NOW.date(),now=NOW,expires_at=expiry)
        host_response(tmp_path,nonce,query=args["query"],provider_result=wrap(evidence(args["query"])))
        result=future.result(timeout=5)
    assert len(result["table_fingerprints"])==8
    assert len(list(tmp_path.glob("*.host-claim.json")))==1
    assert "PRIVATE" not in file.read_text()
    assert "query" not in json.loads(file.read_text())  # Only a digest in request.


def test_mailbox_timeout_consumes_request_without_retry(tmp_path):
    elapsed=[0]
    def sleep(seconds): elapsed[0]+=seconds
    mailbox=ConnectorMailbox(directory=tmp_path,day=NOW.date(),now=lambda:NOW,
        expires_at=NOW+timedelta(minutes=10),monotonic=lambda:elapsed[0],sleep=sleep)
    args=connector_arguments(NOW.date(),"a"*32)
    with pytest.raises(AdapterError): mailbox(**args)
    assert len(list(tmp_path.glob("*.request.json")))==1
    with pytest.raises(AdapterError): mailbox(**args)
    assert len(list(tmp_path.glob("*.request.json")))==1


def test_wrong_project_query_or_nonce_never_leaves_mailbox(tmp_path):
    mailbox=ConnectorMailbox(directory=tmp_path,day=NOW.date(),now=lambda:NOW,expires_at=NOW+timedelta(minutes=10))
    args=connector_arguments(NOW.date(),"a"*32)
    with pytest.raises(AdapterError): mailbox(**{**args,"project_id":"production"})
    with pytest.raises(AdapterError): mailbox(**{**args,"query":args["query"]+" SELECT 1;"})
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("state",["async","stuck","error"])
def test_asynchronous_database_pause_is_bounded(rehearsal,state):
    r=rehearsal
    def pause(project):
        r.calls.append(("PAUSE_DB",project))
        r.status[0]="PAUSING"
    original=r.connections.project_status
    def status():
        if r.status[0]=="PAUSING":
            if state=="error": raise RuntimeError("PRIVATE")
            if state=="async" and r.clock[0]>=r.p.suspend_at+timedelta(minutes=2):
                r.status[0]="INACTIVE"
        return original()
    r.connections.pause_project=pause
    r.connections.project_status=status
    result=r.run()
    assert len([x for x in r.calls if x[0]=="PAUSE_DB"])==1
    if state=="async": assert result["status"]=="NO_SCAN_CHECKS_PASSED" and result["cleanup"]=="VERIFIED"
    else:
        assert result["status"]=="CLEANUP_OR_WATCHDOG_UNRESOLVED"
        assert r.clock[0]==r.p.verify_by and ("STOP_CHILD","LOCAL") not in r.calls
