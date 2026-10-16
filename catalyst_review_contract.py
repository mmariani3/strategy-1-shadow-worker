"""Validate traceable review inputs; never approve a catalyst or trade.

This is an offline review-record contract, not a qualitative-rule evaluator.
The author asserts the interpretation; code checks binding and citations only.
"""
from datetime import datetime

from coordinator_acceptance_verify import verify_packet
from setup_evidence import digest

FIELDS = frozenset({"event_identity", "issuer_relationship", "event_time", "source_relationship",
                    "contradictions", "analyst_attribution", "sector_relationship"})


def review_record(packet, submission, *, now):
    try:
        if not verify_packet(packet, run_key=submission["run_key"], symbol=submission["symbol"]):
            raise ValueError()
        if submission["packet_sha256"] != packet["packet_sha256"] or not submission["reviewer_id"]:
            raise ValueError()
        reviewed_at = datetime.fromisoformat(submission["reviewed_at"])
        if reviewed_at.tzinfo is None or now.tzinfo is None or reviewed_at > now:
            raise ValueError()
        if set(submission["findings"]) != FIELDS:
            raise ValueError()
        if submission["disposition"] not in {"REVIEW_REQUIRED", "REJECT_EVIDENCE"}:
            raise ValueError()
        sources = {source["source_id"]:source for source in packet["sources"]}
        findings = {}
        for name, finding in submission["findings"].items():
            if set(finding) != {"assessment", "rationale", "citations"}:
                raise ValueError()
            if finding["assessment"] not in {"SUPPORTED", "DISPUTED", "UNKNOWN", "NOT_APPLICABLE"}:
                raise ValueError()
            if not isinstance(finding["rationale"], str) or not 1 <= len(finding["rationale"]) <= 2000:
                raise ValueError()
            refs = finding["citations"]
            if not isinstance(refs,list) or len(refs) > 20:
                raise ValueError()
            if finding["assessment"] in {"SUPPORTED", "DISPUTED"} and not refs:
                raise ValueError()
            for ref in refs:
                if set(ref) != {"source_id", "start", "end", "text_sha256"}:
                    raise ValueError()
                source = sources[ref["source_id"]]
                if source["status"] != "CONTENT_RETRIEVED_REVIEW_REQUIRED":
                    raise ValueError()
                text = "".join(p["text"] for p in source["passages"])
                if type(ref["start"]) is not int or type(ref["end"]) is not int:
                    raise ValueError()
                if not 0 <= ref["start"] < ref["end"] <= len(text):
                    raise ValueError()
                import hashlib
                if hashlib.sha256(text[ref["start"]:ref["end"]].encode()).hexdigest() != ref["text_sha256"]:
                    raise ValueError()
            findings[name] = {"assessment":finding["assessment"], "rationale":finding["rationale"],
                              "citations":[dict(ref) for ref in refs]}
        record = {"schema":"catalyst-structured-review/v1", "packet_sha256":packet["packet_sha256"],
            "run_key":submission["run_key"], "symbol":submission["symbol"],
            "reviewer_id":submission["reviewer_id"], "reviewed_at":submission["reviewed_at"],
            "findings":findings, "disposition":submission["disposition"],
            "mode":"SHADOW", "experiment_class":"INFRASTRUCTURE_TEST",
            "candidate_state":"REVIEW_REQUIRED", "qualification_created":False,
            "automatic_promotion":False, "strategy_evidence_eligible":False,
            "semantic_accuracy_verified":False, "reviewer_identity_authenticated":False,
            "limitations":["A matching passage hash validates citation integrity, not the interpretation.",
                "Reviewer identity requires authentication outside this offline contract.",
                "Identical text is not independent confirmation; distinct text does not establish independence."]}
        record["review_sha256"] = digest(record)
        return {"accepted_structure":True, "record":record}
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return {"accepted_structure":False, "reason":"REVIEW_BINDING_OR_CITATION_INVALID"}
