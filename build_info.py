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
    for name in sorted(names):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    revision = os.getenv("RENDER_GIT_COMMIT", "unavailable")
    return f"{version};git={revision};sha256={digest.hexdigest()}"
