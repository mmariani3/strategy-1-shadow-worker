"""Offline-tested admission policy. NOT an authenticated evidence collector.

No credentials, networking, mutable configuration or hosted entry point. Future
adapters must independently obtain these observations from authoritative systems;
passing a fabricated dict through this module is not launch authorization.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import re

from setup_evidence import digest

SERVICE = "srv-dal8abbl550s73cj3jm0"
WORKSPACE = "tea-daholiqfngtc73ddk480"
DATABASE = "cihwmameyylixouggwxk"
URL = "https://strategy1-pr1-staging-discovery.onrender.com"
SERVICES = frozenset({SERVICE, "crn-dainijm7bikc739cvcog", "crn-dainim6q1p3s73cr9hs0",
    "srv-daic8fvqj5pc739gkldg", "srv-dai9mttg1s2s738la0c0", "srv-daidcc1594qs7389mr9g",
    "srv-dahp98h42hec739tn4g0", "srv-daie017qj5pc739nck1g", "srv-dal8a68ae00c73ftd8u0",
    "srv-dal8a2m7bikc73enjn5g", "crn-daudag893c1s73dq0i6g"})
MASTERS = frozenset({"1DBtZYKLV0MdIg_f8NspwVLIoeTxCi9amlRFHO9Ji0tM",
    "1sfL2FAn-p6peY8LLbEwka_2gYIGiGka_BGe6prsygCc", "1uDGbnHQHX6tDD9a5efJD-O9FuMW6xvn_xlhCrltlfjw"})
PACIFIC = ZoneInfo("America/Los_Angeles")
NOTICE_CASES = {"missing_run", "stalled_run", "consecutive_failure_1", "consecutive_failure_2", "cleanup_failure"}
REQUIRED_FILES = frozenset({"coordinator_launch_guard.py", "coordinator_acceptance_controller.py",
    "coordinator_acceptance_app.py", "coordinator_acceptance_controls.py", "coordinator_acceptance_verify.py",
    "discovery_coordinator.py", "discovery_collection.py", "catalyst_source_evidence.py",
    "catalyst_review_contract.py", "build_info.py", "setup_evidence.py", "review_contract.py",
    "premarket_collection.py", "premarket_evidence_collection.py", "prior_session_evidence.py",
    "shadow_evidence_workflow.py", "coordinator-acceptance-readback.sql",
    "coordinator_service_adapters.py", "coordinator_driver.py", "coordinator_watchdog_process.py",
    "coordinator_runtime_preflight.py", "coordinator_rehearsal_binding.py",
    "coordinator_connector_snapshot.py", "coordinator_connector_snapshot.sql",
    "coordinator_connector_mailbox.py"})


class Blocked(ValueError):
    """Only fixed local codes may leave a controller boundary."""


def need(ok, code):
    if not ok:
        raise Blocked(code)


def timestamp(value):
    dt = datetime.fromisoformat(value)
    need(dt.tzinfo is not None and dt.utcoffset() is not None, "NAIVE_TIMESTAMP")
    return dt


def fresh(value, now, seconds):
    need(now.tzinfo is not None, "NAIVE_CLOCK")
    need(timedelta(0) <= now-timestamp(value) <= timedelta(seconds=seconds), "STALE_OR_FUTURE_EVIDENCE")


@dataclass(frozen=True)
class Policy:
    day: date
    commit: str
    source_hash: str
    deployment: str
    # Immutable (name, hash/revision) tuples from a separately reviewed package.
    files: tuple
    masters: tuple
    schema_hash: str
    rehearsal_hash: str
    authorization_id: str
    authorized_until: datetime

    @property
    def run_key(self):
        return f"STRATEGY_1|{self.day.isoformat()}|PREMARKET|v0.3|INFRASTRUCTURE_TEST"

    def at(self, hour, minute):
        return datetime.combine(self.day, time(hour, minute), tzinfo=PACIFIC)

    @property
    def fingerprint(self):
        return digest({"day":self.day.isoformat(), "commit":self.commit, "source_hash":self.source_hash,
            "deployment":self.deployment, "files":self.files, "masters":self.masters,
            "schema_hash":self.schema_hash, "rehearsal_hash":self.rehearsal_hash,
            "authorization_id":self.authorization_id, "authorized_until":self.authorized_until.isoformat()})

    def validate(self, now):
        need(now.tzinfo is not None and now.astimezone(PACIFIC).date() == self.day, "WRONG_DATE")
        need(bool(re.fullmatch("[0-9a-f]{40}", self.commit)) and
             bool(re.fullmatch("dep-[a-z0-9]+", self.deployment)), "UNPINNED_CODE")
        need(set(dict(self.files)) == REQUIRED_FILES and len(dict(self.files)) == len(self.files), "UNPINNED_FILES")
        for value in (self.source_hash, self.schema_hash, self.rehearsal_hash, *dict(self.files).values()):
            need(isinstance(value, str) and bool(re.fullmatch("[0-9a-f]{64}", value)), "INVALID_HASH")
        need(set(dict(self.masters)) == MASTERS and len(self.masters) == 3
             and all(isinstance(v,str) and v for v in dict(self.masters).values()), "MASTER_INVENTORY")
        need(bool(self.authorization_id) and self.authorized_until.tzinfo is not None
             and now < self.authorized_until and self.at(6,25) <= self.authorized_until <= self.at(8,0),
             "AUTHORIZATION_UNAVAILABLE_OR_EXPIRED")


def isolation(rows, *, active=False):
    need(isinstance(rows,list) and len(rows) == 11, "SERVICE_INVENTORY")
    need({r["id"] for r in rows} == SERVICES, "SERVICE_INVENTORY")
    for row in rows:
        need(row["ownerId"] == WORKSPACE and row["autoDeploy"] == "no"
             and row["autoDeployTrigger"] == "off", "OWNER_OR_AUTO_DEPLOY")
        expected = "not_suspended" if active and row["id"] == SERVICE else "suspended"
        need(row["suspended"] == expected, "SERVICE_ISOLATION")


def notification_evidence(receipts, policy):
    need(isinstance(receipts,list) and len(receipts) == len(NOTICE_CASES), "NOTIFICATION_CASES")
    need({r["case"] for r in receipts} == NOTICE_CASES, "NOTIFICATION_CASES")
    need(len({r["message_id"] for r in receipts}) == len(receipts), "NOTIFICATION_DUPLICATE_RECEIPT")
    for row in receipts:
        # A provider's send/accept status is insufficient. IDs must resolve to
        # independent receipt evidence in the pinned rehearsal package.
        need(row["message_id"] and row["receipt_evidence_id"] and
             row["outcome"] == "RECIPIENT_CONFIRMED", "NOTIFICATION_RECEIPT_UNVERIFIED")
        need(timestamp(row["sent_at"]) <= timestamp(row["received_at"]) < policy.at(5,40), "NOTIFICATION_TIME")
        need(timestamp(row["sent_at"]) >= policy.at(5,40)-timedelta(hours=24), "NOTIFICATION_REHEARSAL_EXPIRED")


def preflight(policy, evidence, now, *, active=False, baseline=None):
    policy.validate(now)
    fresh(evidence["checked_at"], now, 120)
    need(timestamp(evidence["checked_at"]) >= policy.at(5,40), "PREFLIGHT_TOO_EARLY")
    need(evidence["policy_hash"] == policy.fingerprint, "POLICY_CHANGED")
    need(evidence["file_sha256"] == dict(policy.files), "LOCAL_FILES_CHANGED")
    need(evidence["masters"] == dict(policy.masters), "MASTERS_CHANGED")
    isolation(evidence["services"], active=active)
    deployment = evidence["deployment"]
    need(deployment == {"id":policy.deployment, "commit":policy.commit, "source_hash":policy.source_hash,
        "service":SERVICE, "url":URL, "status":"live"}, "DEPLOYMENT_CHANGED")
    db = evidence["database"]
    need(db["id"] == DATABASE and db["status"] == "ACTIVE_HEALTHY", "DATABASE_NOT_READY")
    need(db["schema_sha256"] == policy.schema_hash, "SCHEMA_INDEX_AUDIT_CHANGED")
    need(db["matching_run_keys"] == [] and db["unfinished_run_ids"] == [], "RUN_EXISTS_OR_UNFINISHED")
    # These inventories must come from complete independent read-only queries.
    need(evidence["callers"] == {"active_schedules":[], "conflicting_process_ids":[], "active_pg_cron":[]},
         "CONFLICTING_CALLERS")
    need(set(db["baseline"]) == {"runs", "items", "events", "protected_tables"}, "BASELINE_INCOMPLETE")
    for value in db["baseline"].values():
        need(type(value["count"]) is int and value["count"] >= 0
             and bool(re.fullmatch("[0-9a-f]{64}", value["sha256"])), "BASELINE_INVALID")
    if baseline is not None:
        need(db["baseline"] == baseline, "BASELINE_CHANGED")
    rehearsal = evidence["rehearsal"]
    need(digest(rehearsal) == policy.rehearsal_hash, "REHEARSAL_CHANGED")
    need(rehearsal["scope"] == "NORMAL_COORDINATOR_NO_SCAN" and rehearsal["acceptance_posts"] == 0,
         "REHEARSAL_SCOPE")
    need(rehearsal["session_date"] == policy.day.isoformat(), "REHEARSAL_DATE")
    need(rehearsal["commit"] == policy.commit and rehearsal["source_hash"] == policy.source_hash
         and rehearsal["deployment"] == policy.deployment, "REHEARSAL_CODE")
    isolation(rehearsal["cleanup_services"])
    need(rehearsal["database_status"] == "INACTIVE", "REHEARSAL_CLEANUP")
    w = rehearsal["watchdog"]
    need(type(w["pid"]) is int and w["pid"] > 0 and w["pid"] != w["controller_pid"]
         and w["service"] == SERVICE and w["suspension_readback"] == "suspended"
         and timestamp(w["ready_at"]) < timestamp(w["resumed_at"]) < timestamp(w["suspended_at"])
         <= timestamp(w["deadline"]) < policy.at(5,40), "REHEARSAL_WATCHDOG")
    notification_evidence(rehearsal["notification_receipts"], policy)
    armed = evidence["armed"]
    need(armed["policy_hash"] == policy.fingerprint and armed["rehearsal_hash"] == policy.rehearsal_hash
         and armed["session_date"] == policy.day.isoformat(), "ARMED_BINDING")
    need(armed["verifier_id"] != evidence["collector_id"] and bool(armed["verifier_id"]), "ARMING_NOT_INDEPENDENT")
    need(timestamp(armed["created_at"]) < policy.at(5,40), "ARMING_TOO_LATE")
    return db["baseline"]


def watchdog(policy, receipt, now, *, controller_pid, nonce):
    fresh(receipt["heartbeat_at"], now, 15)
    need(type(receipt["pid"]) is int and receipt["pid"] > 0 and receipt["pid"] != controller_pid,
         "WATCHDOG_NOT_INDEPENDENT")
    need(receipt["nonce"] == nonce and receipt["policy_hash"] == policy.fingerprint
         and receipt["service"] == SERVICE, "WATCHDOG_BINDING")
    need(timestamp(receipt["suspend_at"]) == policy.at(6,20)
         and timestamp(receipt["verify_by"]) == policy.at(6,25), "WATCHDOG_DEADLINE")


def runtime(policy, data, now):
    fresh(data["checked_at"], now, 30)
    need(data["commit"] == policy.commit and data["source_hash"] == policy.source_hash
         and data["session_date"] == policy.day.isoformat() and data["database_id"] == DATABASE,
         "RUNTIME_IDENTITY")
    need(data["mode"] == "SHADOW" and data["broker_execution_enabled"] is False
         and data["qualification_enabled"] is False and data["journal_enabled"] is False
         and data["strategy_evidence_eligible"] is False, "RUNTIME_SAFETY")
    need(set(data["authenticated_probes"]) == {"paper_calendar", "sip", "historical_sip", "staging_database"}
         and all(v == "AUTHENTICATED_READ_ONLY" for v in data["authenticated_probes"].values()), "AUTH_UNVERIFIED")
