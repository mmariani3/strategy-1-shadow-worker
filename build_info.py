"""Persist the code revision, not a stale WORKER_VERSION environment override."""
import hashlib
import os
from pathlib import Path


def implementation_version(component, version):
    root = Path(__file__).parent
    digest = hashlib.sha256()
    names = [component + ".py", "review_contract.py", "build_info.py"]
    if component == "discovery_coordinator":
        names.append("discovery_collection.py")
        names.append("premarket_collection.py")
        names.extend(["coordinator_acceptance_controls.py", "coordinator_acceptance_app.py",
                      "coordinator_runtime_preflight.py", "coordinator_rehearsal_binding.py",
                      "coordinator_launch_guard.py", "coordinator_service_adapters.py",
                      "coordinator_driver.py", "coordinator_watchdog_process.py",
                      "catalyst_source_evidence.py",
                      "premarket_evidence_collection.py", "prior_session_evidence.py",
                      "shadow_evidence_workflow.py", "setup_evidence.py"])
    for name in sorted(names):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    revision = os.getenv("RENDER_GIT_COMMIT", "unavailable")
    return f"{version};git={revision};sha256={digest.hexdigest()}"
