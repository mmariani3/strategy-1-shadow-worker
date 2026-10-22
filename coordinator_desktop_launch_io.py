"""Unarmed desktop I/O helpers for a future separately pinned launcher.

No CLI, credential loader, provider API, authorization creation or attempt ledger.
Existing October 19 launchers are intentionally untouched. A future launcher must
still validate its permit, caller evidence, source bindings and durable guard.
"""
from datetime import timedelta
from pathlib import Path
import time

from coordinator_launch_guard import need


def wait_for_launch_window(*, not_before, latest_start, expires_at, now,
                          monotonic=time.monotonic, sleep=time.sleep):
    """Wait at most 60 seconds; never shift the authorized start/end timestamps."""
    current=now(); now_start=current; started=monotonic()
    need(all(x.tzinfo is not None for x in (current,not_before,latest_start,expires_at)),
         'LAUNCH_TIMEZONE')
    need(not_before<latest_start<=expires_at
         and latest_start-not_before<=timedelta(seconds=60),'LAUNCH_WINDOW')
    need(current<latest_start and (not_before-current).total_seconds()<=60,'LAUNCH_TIME')
    while current<not_before:
        need(monotonic()-started<=60
             and abs((current-now_start).total_seconds()-(monotonic()-started))<=5,'LAUNCH_CLOCK')
        sleep(min(0.25,(not_before-current).total_seconds()))
        current=now()
    need(not_before<=current<latest_start and current<expires_at
         and monotonic()-started<=60
         and abs((current-now_start).total_seconds()-(monotonic()-started))<=5,'LAUNCH_DEADLINE')
    # This establishes time only, never readiness or permission.
    return {'launch_window_open':True}


def relay_response_file(path, *, private_directory, responder):
    """Pass a local file stream to the reviewed responder, never shell JSON.

    The responder retains all existing nonce/kind/freshness/claim validation.
    No path, file contents, exception text or responder output is returned.
    """
    try:
        root=Path(private_directory).resolve(strict=True)
        source=Path(path)
        need(source.is_absolute() and source.suffix=='.json','RESPONSE_FILE')
        resolved=source.resolve(strict=True)
        need(resolved.is_relative_to(root) and resolved.is_file()
             and resolved.stat().st_size<=32*1024*1024,'RESPONSE_FILE_SCOPE')
        with resolved.open('r',encoding='utf-8') as stream:
            responder(stream)
        return {'response_submitted':True}
    except Exception:
        raise RuntimeError('RESPONSE_RELAY_FAILED_CLOSED') from None


if __name__=='__main__':
    raise SystemExit('UNARMED_HELPERS_NO_EXECUTABLE_LAUNCHER')
