"""Deterministic operator guidance; no notifications, retries or state changes."""

ALERT_POLICY_VERSION = "1.1.0-discovery-alerts"

# Each entry describes only the scheduler invocation, never all trading services.
OUTCOMES = {
    "CONFIGURATION_ERROR": ("MAINTENANCE", "Scheduler configuration is missing or invalid.",
        "Stopped before contacting dependencies."),
    "DEPENDENCY_UNAVAILABLE_OR_UNSAFE": ("MAINTENANCE", "Required service health or SHADOW safety settings could not be verified.",
        "Blocked scan submission by this invocation."),
    "MISSED_LAUNCH_WINDOW": ("MISSED_SCAN", "The permitted scan launch minute was missed.",
        "Skipped submission; did not launch a late replacement."),
    "MISSED_RUN": ("MISSED_SCAN", "No run was found for the expected session, phase and class.",
        "Reported the missing run without submitting a replacement."),
    "RUN_UNFINISHED": ("RECONCILE", "The saved run is still in progress.",
        "Bounded read-only reconciliation ended with the run still unfinished; no resubmission."),
    "DISPATCH_OUTCOME_UNRESOLVED": ("RECONCILE", "Submission was attempted but readback found no saved run.",
        "Bounded read-only reconciliation followed one submission attempt; did not replay the POST."),
    "READBACK_UNAVAILABLE_OR_INVALID": ("RECONCILE", "The session or saved result could not be reliably verified.",
        "Stopped without certifying completion. A submission may already have occurred."),
    "RUN_IDENTITY_MISMATCH": ("MAINTENANCE", "The saved run does not match the expected identity.",
        "Rejected the run as proof of the expected scan."),
    "RESPONSE_ID_MISMATCH": ("MAINTENANCE", "The submission response and saved run have different IDs.",
        "Rejected the result as verified completion; did not resubmit."),
    "INVALID_RUN_TIMESTAMPS": ("MAINTENANCE", "Saved run timestamps are inconsistent.",
        "Rejected the result as verified completion."),
    "PERSISTENCE_MISMATCH": ("MAINTENANCE", "The reported candidate count and saved items do not agree.",
        "Rejected the result as verified completion."),
    "COVERAGE_STATUS_INCONSISTENT": ("MAINTENANCE", "A COMPLETE label conflicts with unresolved discovery coverage.",
        "Rejected the completion claim without changing stored records."),
    "COLLECTION_FAILED": ("MAINTENANCE", "The saved collection has a failed, unavailable or unrecognized status.",
        "Reported failure without resubmitting or promoting the run."),
    "RUN_OUTSIDE_SCHEDULED_MINUTE": ("TIMING_REVIEW", "The saved run started outside its configured launch minute.",
        "Flagged the timing mismatch without rewriting the record."),
    "PREMARKET_NOT_FINISHED_BEFORE_OPEN": ("TIMING_REVIEW", "Premarket collection did not finish before the market opened.",
        "Flagged the late completion without relabeling it as timely coverage."),
    "WRONG_MARKET_PHASE": ("TIMING_REVIEW", "The requested or saved run does not fit its market phase.",
        "Stopped this invocation without accepting the phase mismatch."),
    "COLLECTED_REVIEW_REQUIRED": ("RESEARCH_REVIEW", "Raw discovery was saved as PARTIAL; review remains outstanding.",
        "Kept collection partial and reported coverage gaps; did not qualify a catalyst or approve a trade."),
    "AUDIT_NOT_DUE": ("MAINTENANCE", "The audit was invoked before its configured reporting time.",
        "Stopped without auditing or launching a scan."),
    "COMPLETED": ("INFO", "The expected discovery run passed completion, timing, count and coverage checks.",
        "Verified discovery completion only; did not approve a setup or trade."),
    "WEEKEND": ("INFO", "This is a weekend invocation.", "Skipped submission."),
    "MARKET_CLOSED": ("INFO", "The market calendar identifies a non-trading day.", "Skipped submission."),
    "OTHER_DST_INVOCATION": ("INFO", "This is the extra invocation from the paired daylight-saving schedule.",
        "Skipped this invocation; this does not establish that the intended scan ran."),
    "WARMED_WAITING_FOR_LAUNCH": ("PROGRESS", "Health passed and the scheduler is waiting for the launch minute.",
        "Waiting inside the current process; no scan submitted yet."),
    "DISPATCH_INTENT": ("PROGRESS", "The scheduler is about to attempt a scan submission.",
        "Recorded intent only; completion is not yet verified."),
    "READBACK_RETRY": ("PROGRESS", "The scheduler is automatically checking a temporary read failure or pending result again.",
        "Waiting for the next bounded GET check; no scan resubmission or repair."),
}

GUIDANCE = {
    "MAINTENANCE": ("BEFORE_RELIANCE", "Ask for configuration and saved-run investigation before relying on this pipeline. Do not force a retry or change safety settings to bypass the failure."),
    "MISSED_SCAN": ("WHEN_CONVENIENT", "Keep this scan marked missed. Send the alert for investigation when convenient; do not chase it with a late scan or use a post-open scan as its replacement."),
    "RECONCILE": ("BEFORE_RELIANCE", "Automatic checks could not establish a usable result. Request investigation of the exact saved run before relying on it. Do not resubmit the scan; an in-flight request may still finish."),
    "TIMING_REVIEW": ("BEFORE_USE", "Review the timing and applicable coverage rules before using the research. Preserve the timestamps; do not backdate or relabel the run."),
    "RESEARCH_REVIEW": ("BEFORE_USE", "Research remains available for review in the saved run; no failure notification is requested. Review sources and coverage before use. If unavailable, leave it unreviewed."),
    "INFO": ("NONE", "No response needed to this scheduler event. Discovery completion is not trade approval."),
    "PROGRESS": ("NONE", "Wait for a final result; this progress event does not establish completion."),
}


def response_for(outcome):
    """Return fresh JSON-safe advice, without executing any remediation."""
    category, summary, action = OUTCOMES.get(outcome, (
        "MAINTENANCE", "An unrecognized scheduler outcome requires investigation.",
        "No completion or safety action can be inferred from this unknown outcome."))
    timing, user_action = GUIDANCE[category]
    return dict(policy_version=ALERT_POLICY_VERSION, category=category,
                event_stage="INTERMEDIATE" if category == "PROGRESS" else "FINAL",
                summary=summary, scheduler_action=action,
                user_action_timing=timing, user_action=user_action,
                scope="DISCOVERY_ONLY", advisory_only=True,
                scope_note="This guidance does not pause future jobs, monitor positions, or verify other services. The scheduler performs bounded GET reconciliation; no automatic repair or trade approval is performed.")
