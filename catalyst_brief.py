"""Display attributed research, never qualify a catalyst or submit a decision."""
from copy import deepcopy
from html import escape
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field
from evidence_review import aware, digest

VERSION = "1.0.0-catalyst-brief"
QUESTIONS = [
    ("fresh_event", "Can I explain what actually changed for this company today?"),
    ("sources", "Do the linked sources support the same event and its important details?"),
    ("significance", "Is the proposed economic significance convincing, with forecasts separated from facts?"),
    ("limitations", "Do the limitations or contrary evidence change the conclusion?"),
    ("tier", "Does the proposed catalyst tier follow the existing rules?"),
    ("market", "Is the market/sector context known and suitable, including imminent macro events?"),
    ("data", "Is the data current and adequate for liquidity, spread and participation judgments?"),
    ("pattern", "Can I identify one approved entry pattern on the annotated chart?"),
    ("trigger", "Was the trigger predefined, and has full confirmation occurred without chasing?"),
    ("stop", "Does the stop represent where this particular setup becomes invalid?"),
    ("target", "Is the target justified, including any required clean-structure review?"),
    ("invalidation", "Do I understand what would cancel or invalidate this plan?"),
]
SECTIONS = ("What happened", "Economic significance", "Timeline", "Case against", "Tier reasoning")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class Citation(Strict):
    source_id: str
    field: str
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)
    excerpt: str = Field(min_length=1)


class Claim(Strict):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    kind: Literal["ATTRIBUTED_FACT", "MANAGEMENT_FORECAST", "ANALYSIS", "UNRESOLVED"]
    citations: list[Citation] = Field(min_length=1)
    source_check: str = Field(min_length=1)


class Brief(Strict):
    schema_version: Literal[1]
    packet_id: str
    symbol: str
    trace: dict
    source_experiment_class: Literal["STRATEGY_1", "INFRASTRUCTURE_TEST"]
    source_snapshot_digest: str
    title: str = Field(min_length=1)
    authored_by: str = Field(min_length=1)
    authored_at: str
    checked_by: str = Field(min_length=1)
    checked_at: str
    review_scope: Literal["AUTHOR_SOURCE_CHECK_NOT_INDEPENDENT"]
    event_timing: str = Field(min_length=1)
    knowledge_limit: str = Field(min_length=1)
    tier_proposal: Literal["A", "B", "C", "UNRESOLVED"]
    claims: list[Claim] = Field(min_length=1)
    sections: dict[str, list[str]]
    limitations: list[str] = Field(min_length=1)


def attach_briefs(report, briefs, now):
    """Bind exact source passages and lineage. Matching text is not semantic approval."""
    if not isinstance(briefs, list):
        raise ValueError("Brief input must be a JSON list.")
    result = deepcopy(report)
    candidates = {c["packet_id"]: c for c in result["candidates"]}
    seen = set()
    for raw in briefs:
        b = Brief.model_validate(raw).model_dump()
        if b["packet_id"] in seen or b["packet_id"] not in candidates:
            raise ValueError("Duplicate brief or unknown candidate packet.")
        seen.add(b["packet_id"])
        c = candidates[b["packet_id"]]
        if (b["symbol"] != c["symbol"] or b["trace"] != c["trace"] or
                b["source_snapshot_digest"] != result["source_snapshot_digest"] or
                b["source_experiment_class"] != result["experiment_class"]):
            raise ValueError("Brief does not match source snapshot, classification or trace.")
        if not aware(result["source_captured_at"]) <= aware(b["authored_at"]) <= aware(b["checked_at"]) <= aware(now):
            raise ValueError("Invalid source/authorship/review chronology.")
        if any(not b[k].strip() for k in ("title", "authored_by", "checked_by", "event_timing", "knowledge_limit")):
            raise ValueError("Blank research attribution.")
        if any(not item.strip() for item in b["limitations"]):
            raise ValueError("Blank limitation.")
        ids = [claim["id"] for claim in b["claims"]]
        if len(set(ids)) != len(ids) or any(not x.strip() for x in ids):
            raise ValueError("Unique nonblank claim identifiers required.")
        if set(b["sections"]) != set(SECTIONS) or any(not refs for refs in b["sections"].values()):
            raise ValueError("All research sections are required.")
        references = [ref for refs in b["sections"].values() for ref in refs]
        if set(references) != set(ids):
            raise ValueError("Every claim must be displayed; no unknown claim references.")
        sources = {s["source_id"]: s for s in c["sources"]}
        for claim in b["claims"]:
            if not claim["text"].strip() or not claim["source_check"].strip():
                raise ValueError("Claim and source-check notes required.")
            for cite in claim["citations"]:
                src = sources.get(cite["source_id"])
                if not src or src["kind"] not in ("news", "filing", "retrieved_document"):
                    raise ValueError("Citation is not a captured catalyst source.")
                text = src["raw"].get(cite["field"])
                if (not isinstance(text, str) or cite["end"] > len(text) or cite["start"] >= cite["end"] or
                        text[cite["start"]:cite["end"]] != cite["excerpt"]):
                    raise ValueError("Citation passage mismatch.")
        b.update(implementation_version=VERSION, classification="RESEARCH_BRIEF_ONLY",
                 eligible_for_handoff=False, current_approval="NOT_ESTABLISHED",
                 independent_acceptance="NOT_ESTABLISHED", source_context=result["source_context"])
        b["brief_id"] = digest(b)
        c["catalyst_brief"] = b
    result["review_questions"] = [{"id": key, "question": text} for key, text in QUESTIONS]
    result["review_question_version"] = VERSION
    result["preparation_id"] = digest({k: v for k, v in result.items() if k != "preparation_id"})
    return result


def source_link(raw):
    url = raw.get("url") or raw.get("requested_url")
    if not isinstance(url, str):
        return "Source URL unavailable"
    try:
        parsed = urlsplit(url)
    except ValueError:
        return "Source link withheld: malformed URL"
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return "Source link withheld: unsupported URL"
    return '<a target="_blank" rel="noopener noreferrer" href="' + escape(url, quote=True) + '">Open original source</a>'


def render_brief(candidate):
    b = candidate.get("catalyst_brief")
    if not b:
        return "<h3>Catalyst brief</h3><p>No checked research brief attached. Captured headlines below are source material, not completed research.</p>"
    sources = {s["source_id"]: s for s in candidate["sources"]}
    claims = {c["id"]: c for c in b["claims"]}
    body = []
    for title in SECTIONS:
        body.append("<h4>" + title + "</h4>")
        for key in b["sections"][title]:
            claim = claims[key]
            body.append("<p><strong>" + escape(claim["kind"].replace("_", " ")) + ":</strong> " + escape(claim["text"]) + "</p>")
            body.append("<details><summary>Evidence and source check — " + escape(key) + "</summary>")
            for cite in claim["citations"]:
                raw = sources[cite["source_id"]]["raw"]
                body.append("<blockquote>" + escape(cite["excerpt"]) + "</blockquote><p>" + source_link(raw) + "</p>"
                            + "<small>Captured field " + escape(cite["field"]) + "; characters " + str(cite["start"]) + "–" + str(cite["end"])
                            + "; source " + escape(cite["source_id"]) + "</small>")
            body.append("<p>Author's source check: " + escape(claim["source_check"]) + "</p></details>")
    return ("<article class=brief><h3>" + escape(b["title"]) + "</h3>"
            + "<p class=notice><strong>Research only · " + escape(b["source_context"]) + "</strong><br>"
            + "Author source check; independent acceptance and current approval are not established.</p>"
            + "<p>Event timing: " + escape(b["event_timing"]) + "<br>Knowledge limit: " + escape(b["knowledge_limit"]) + "</p>"
            + "<p>Written by " + escape(b["authored_by"]) + " at " + escape(b["authored_at"])
            + "; checked by " + escape(b["checked_by"]) + " at " + escape(b["checked_at"]) + "</p>"
            + "".join(body) + "<h4>Unresolved and contrary evidence</h4><ul>"
            + "".join("<li>" + escape(x) + "</li>" for x in b["limitations"]) + "</ul>"
            + "<p>Tier proposal: " + escape(b["tier_proposal"]) + " — pending explicit review; not qualification.</p>"
            + "<small>Brief ID: " + escape(b["brief_id"]) + "</small></article>")
