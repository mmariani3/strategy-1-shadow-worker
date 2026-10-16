"""Bounded local RPC relay for an authenticated Codex Supabase host connector.

The launcher supplies an exclusive private directory after ACL review. This is
not credential storage, a scheduler, a launcher, or proof of host authentication.
The host reconstructs fixed SQL instead of executing SQL from a request file.
"""
from datetime import date
from pathlib import Path
import hashlib
import json
import time

from coordinator_acceptance_controller import consume
from coordinator_connector_snapshot import connector_arguments, decode_result, MAX_BYTES
from coordinator_launch_guard import DATABASE, need, timestamp
from coordinator_service_adapters import fail


class ConnectorMailbox:
    def __init__(self, *, directory, day, now, expires_at, monotonic=time.monotonic, sleep=time.sleep):
        self.root=Path(directory).resolve()
        need(self.root.is_dir() and type(day) is date,"CONNECTOR_MAILBOX_DIRECTORY")
        self.day,self.now,self.expires_at=day,now,expires_at
        self.monotonic,self.sleep=monotonic,sleep

    def __call__(self, *, project_id, query):
        import re
        try:
            need(project_id==DATABASE and self.now()<self.expires_at,"CONNECTOR_MAILBOX_SCOPE")
            found=re.search("'nonce','([a-f0-9]{32})'",query)
            need(found is not None,"CONNECTOR_MAILBOX_QUERY")
            nonce=found[1]
            expected=connector_arguments(self.day,nonce)
            need(query==expected["query"],"CONNECTOR_MAILBOX_QUERY")
            request={"kind":"STAGING_NO_SCAN_SNAPSHOT_REQUEST_V1","nonce":nonce,"day":self.day.isoformat(),
                "project_id":DATABASE,"query_sha256":hashlib.sha256(query.encode()).hexdigest(),
                "requested_at":self.now().isoformat(),"expires_at":self.expires_at.isoformat()}
            consume(self.root/(nonce+".request.json"),request)
            response=self.root/(nonce+".response.json")
            start=self.monotonic()
            while self.monotonic()-start<45 and self.now()<self.expires_at:
                if response.exists():
                    need(not response.is_symlink() and response.stat().st_size<=MAX_BYTES,"CONNECTOR_MAILBOX_SIZE")
                    try:
                        data=json.loads(response.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        # An exclusive response file may still be being written.
                        self.sleep(.1)
                        continue
                    need(set(data)=={"nonce","query_sha256","evidence"} and data["nonce"]==nonce
                         and data["query_sha256"]==request["query_sha256"],"CONNECTOR_MAILBOX_RESPONSE")
                    return [{"evidence":data["evidence"]}]
                self.sleep(.1)
            fail("CONNECTOR_MAILBOX_TIMEOUT")
        except Exception:
            fail("CONNECTOR_MAILBOX_UNAVAILABLE")


def host_request(directory, nonce, *, day, now, expires_at):
    """Return ONLY fixed MCP arguments. Host separately verifies the code manifest.

    The caller's pinned day/window must match the permit; no value from the
    request is treated as approval. No arbitrary path or SQL is accepted.
    """
    import re
    need(re.fullmatch("[a-f0-9]{32}",nonce) is not None,"CONNECTOR_HOST_NONCE")
    root=Path(directory).resolve()
    request=root/(nonce+".request.json")
    need(not request.is_symlink() and request.stat().st_size<=4096,"CONNECTOR_HOST_REQUEST")
    r=json.loads(request.read_text(encoding="utf-8"))
    need(set(r)=={"kind","nonce","day","project_id","query_sha256","requested_at","expires_at"}
         and r["kind"]=="STAGING_NO_SCAN_SNAPSHOT_REQUEST_V1" and r["nonce"]==nonce
         and r["day"]==day.isoformat() and r["project_id"]==DATABASE
         and timestamp(r["expires_at"])==expires_at and now<expires_at
         and 0<=(now-timestamp(r["requested_at"])).total_seconds()<45,"CONNECTOR_HOST_BINDING")
    args=connector_arguments(day,nonce)
    need(hashlib.sha256(args["query"].encode()).hexdigest()==r["query_sha256"],"CONNECTOR_HOST_QUERY")
    # A durable claim prevents host retries/replay after an ambiguous tool call.
    consume(root/(nonce+".host-claim.json"),{"nonce":nonce,"at":now.isoformat()})
    return args


def host_response(directory, nonce, *, query, provider_result):
    """Store the fixed query's evidence only, never raw provider diagnostics."""
    import re
    need(re.fullmatch("[a-f0-9]{32}",nonce) is not None,"CONNECTOR_HOST_NONCE")
    root=Path(directory).resolve()
    need((root/(nonce+".host-claim.json")).is_file(),"CONNECTOR_HOST_CLAIM")
    e=decode_result(provider_result)
    need(e["nonce"]==nonce,"CONNECTOR_HOST_RESPONSE")
    consume(root/(nonce+".response.json"),{"nonce":nonce,
        "query_sha256":hashlib.sha256(query.encode()).hexdigest(),"evidence":e})
