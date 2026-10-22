"""Local controller core, exercised ONLY with offline adapters.

There is deliberately no live adapter, credentials helper, deployment manifest,
CLI --run, service-resumption implementation or app factory binding. Adapter
methods below are a future integration contract, not hosted admission proof.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import uuid

from coordinator_launch_guard import (Blocked, need, preflight, isolation, watchdog, runtime,
    fresh, SERVICE, DATABASE, URL)
from coordinator_acceptance_verify import verify
from setup_evidence import digest


def snapshot_baseline(snapshot):
    result = {}
    for key in ("runs", "items", "events"):
        rows = sorted(snapshot[key], key=lambda row: row["id"])
        result[key] = {"count":len(rows), "sha256":digest(rows)}
    result["protected_tables"] = {"count":len(snapshot["protected_tables"]),
                                   "sha256":digest(snapshot["protected_tables"])}
    return result


def consume(path, value):
    # Exclusive create is a cross-process durable claim. A partial file after a
    # crash also consumes the attempt; never delete it or retry an ambiguous POST.
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())


class Controller:
    def __init__(self, policy, *, ports, clock, evidence_directory, controller_pid):
        self.policy, self.ports, self.clock = policy, ports, clock
        self.root = Path(evidence_directory).resolve()
        need(self.root.is_dir(), "EVIDENCE_DIRECTORY_MISSING")
        self.prefix = digest(policy.run_key)
        self.pid = controller_pid
        self.nonce = uuid.uuid4().hex
        self.phase = "NEW"
        self.baseline = None
        self.activation_attempted = False
        self.owns_attempt = False
        self.watchdog_started = False
        self.post_attempted = False
        self.post_at = None
        self.report = {"status":"NOT_STARTED", "storage_readback":"NOT_VERIFIED",
            "cleanup":"NOT_VERIFIED", "watchdog_shutdown":"NOT_VERIFIED",
            "full_discovery_accepted":False, "strategy_evidence_eligible":False,
            "hosted_adapter_installed":False}

    def save_event(self, kind):
        consume(self.root/(self.prefix+"."+kind+".json"), {
            "run_key":self.policy.run_key, "policy_hash":self.policy.fingerprint,
            "at":self.clock().isoformat(), "event":kind})

    def notice(self, code):
        try:
            self.ports.notify(code)
            self.report["notification"] = "SEND_RETURNED_DELIVERY_UNVERIFIED"
        except Exception:
            self.report["notification"] = "SEND_FAILED_DELIVERY_UNVERIFIED"
        try:
            consume(self.root/(self.prefix+".notification.json"), {
                "status_code":code, "notification":self.report["notification"],
                "run_key":self.policy.run_key, "at":self.clock().isoformat()})
        except Exception:
            self.report["notification_evidence_persistence"] = "FAILED"

    def stop(self, code):
        self.report["status"] = code
        self.cleanup()
        self.notice(code)
        return deepcopy(self.report)

    def start(self):
        if self.phase != "NEW":
            return deepcopy(self.report)
        if (self.root/(self.prefix+".attempt.json")).exists():
            self.phase = "TERMINAL"
            self.report["status"] = "ATTEMPT_ALREADY_CONSUMED"
            return deepcopy(self.report)
        try:
            need(self.phase == "NEW", "CONTROLLER_ALREADY_STARTED")
            now = self.clock()
            self.policy.validate(now)
            need(self.policy.at(5,45) <= now < self.policy.at(5,50), "START_WINDOW_CLOSED")
            self.save_event("attempt")
            self.owns_attempt = True
            self.phase = "PREPARING"
            observed = self.ports.observations()
            self.baseline = deepcopy(preflight(self.policy, observed, self.clock()))
            need(self.clock() < self.policy.at(5,50), "START_WINDOW_CLOSED")
            # A future adapter must create a real independent process and prove
            # its fixed program identity and bounded suspension authority.
            self.watchdog_started = True
            receipt = self.ports.start_watchdog(SERVICE, self.nonce, self.policy)
            watchdog(self.policy, receipt, self.clock(), controller_pid=self.pid, nonce=self.nonce)
            need(self.clock() < self.policy.at(5,50), "START_WINDOW_CLOSED")
            self.activation_attempted = True  # Resume timeout is ambiguous too.
            self.ports.resume(SERVICE)
            self.phase = "WARMING"
            self.report["status"] = "AWAITING_AUTHENTICATED_READINESS"
        except FileExistsError:
            # Never manipulate another running controller's watchdog or DB on
            # duplicate start. The original owner retains cleanup responsibility.
            self.phase = "TERMINAL"
            self.report["status"] = "ATTEMPT_ALREADY_CONSUMED"
        except Exception:
            if self.owns_attempt:
                self.stop("PREPARATION_FAILED_CLOSED")
            else:
                self.phase = "TERMINAL"
                self.report["status"] = "PREPARATION_FAILED_CLOSED"
        return deepcopy(self.report)

    def check_live(self):
        evidence = self.ports.observations()
        preflight(self.policy, evidence, self.clock(), active=True, baseline=self.baseline)
        watchdog(self.policy, self.ports.watchdog_receipt(self.nonce), self.clock(),
                 controller_pid=self.pid, nonce=self.nonce)
        runtime(self.policy, self.ports.runtime_probe(), self.clock())
        # Earlier observations must still be fresh after potentially slow probes.
        fresh(evidence["checked_at"], self.clock(), 120)

    def tick(self):
        """One bounded transition. Future driver must call regularly; no sleeps."""
        if self.phase == "TERMINAL":
            return deepcopy(self.report)
        try:
            need(self.phase not in ("NEW", "PREPARING"), "START_REQUIRED")
            now = self.clock()
            self.policy.validate(now)
            if now >= self.policy.at(6,20):
                return self.stop("FINISHED" if self.report["storage_readback"] == "PASS" else "READBACK_NOT_ACCEPTED")
            if self.phase == "WARMING":
                need(now < self.policy.at(5,55), "AUTHENTICATED_READINESS_DEADLINE")
                self.check_live()
                need(self.clock() < self.policy.at(5,55), "AUTHENTICATED_READINESS_DEADLINE")
                self.phase = "READY"
                self.report["status"] = "READY_WAITING_SINGLE_DISPATCH_WINDOW"
            elif self.phase == "READY" and now >= self.policy.at(6,0):
                need(now < self.policy.at(6,1), "DISPATCH_WINDOW_MISSED")
                self.check_live()
                need(self.policy.at(6,0) <= self.clock() < self.policy.at(6,1), "DISPATCH_WINDOW_MISSED")
                self.save_event("post-intent")
                self.post_attempted = True
                self.post_at = self.clock()
                self.phase = "READBACK"
                # Acknowledged HTTP success is not independent storage acceptance.
                self.ports.post(URL+"/scan/run-once", {"session_date":self.policy.day.isoformat(),
                    "phase":"PREMARKET", "run_class":"INFRASTRUCTURE_TEST", "include_dated_prior_evidence":True})
                self.report["status"] = "POST_RETURNED_READBACK_REQUIRED"
            elif self.phase == "READBACK":
                data = self.ports.readback()
                fresh(data["checked_at"], self.clock(), 120)
                from coordinator_launch_guard import timestamp
                need(timestamp(data["checked_at"]) >= self.post_at, "READBACK_PREDATES_ATTEMPT")
                need(snapshot_baseline(data["before"]) == self.baseline, "READBACK_BASELINE_MISMATCH")
                result = verify(data["before"], data["after"], run_key=self.policy.run_key,
                                implementation=self.ports.implementation_version)
                need(result.get("passed") is True, "INDEPENDENT_READBACK_FAILED")
                self.report["storage_readback"] = "PASS"
                self.phase = "WAITING_CLEANUP"
                self.report["status"] = "STORAGE_VERIFIED_DISCOVERY_STILL_PARTIAL"
        except Exception:
            self.stop("RUN_FAILED_OR_AMBIGUOUS_NO_REPLAY")
        return deepcopy(self.report)

    def cleanup(self):
        """Best-effort independent checks; never resume, repair, or erase evidence."""
        if not self.owns_attempt:
            self.report["cleanup"] = "NOT_ATTEMPT_OWNER"
            self.phase = "TERMINAL"
            return deepcopy(self.report)
        all_off = db_off = False
        try:
            self.ports.suspend(SERVICE)
        except Exception:
            pass  # A timeout is ambiguous: still attempt independent readback.
        try:
            observed = self.ports.cleanup_observations()
            fresh(observed["checked_at"], self.clock(), 30)
            isolation(observed["services"])
            all_off = True
        except Exception:
            pass
        # Do not pause DB under an unverified active writer.
        if all_off:
            try:
                self.ports.pause_database(DATABASE)
            except Exception:
                pass
            try:
                observed = self.ports.database_status()
                fresh(observed["checked_at"], self.clock(), 30)
                db_off = observed["id"] == DATABASE and observed["status"] == "INACTIVE"
            except Exception:
                pass
        self.report["services_suspended_verified"] = all_off
        self.report["database_inactive_verified"] = db_off
        self.report["cleanup"] = "VERIFIED" if all_off and db_off else "UNRESOLVED"
        self.report["cleanup_by_deadline"] = all_off and db_off and self.clock() <= self.policy.at(6,25)
        if all_off and db_off and self.watchdog_started:
            try:
                stopped = self.ports.stop_watchdog(self.nonce)
                need(stopped == {"nonce":self.nonce, "process_exited":True}, "WATCHDOG_STOP_UNVERIFIED")
                self.report["watchdog_shutdown"] = "VERIFIED"
            except Exception:
                self.report["watchdog_shutdown"] = "UNRESOLVED"
        if not all_off or not db_off:
            self.report["status"] = "CLEANUP_UNRESOLVED"
        self.phase = "TERMINAL"
        try:
            consume(self.root/(self.prefix+".result.json"), self.report)
        except Exception:
            self.report["result_persistence"] = "FAILED_EXISTING_EVIDENCE_PRESERVED"
        return deepcopy(self.report)


if __name__ == "__main__":
    raise SystemExit("HOSTED_RUN_DISABLED_NO_AUTHENTICATED_ADAPTER_OR_APPROVED_DATE")
