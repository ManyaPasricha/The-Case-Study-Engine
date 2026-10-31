import json
import re
import requests
from pathlib import Path
from datetime import datetime
from collections import Counter

# ============================================================
# PROJECT DRISHTI - WRITER + QUALITY CONTROL AGENT
# Local Ollama only. Creates three audience-specific drafts,
# applies conservative privacy filters, and reports QC issues.
# It NEVER grants publication approval.
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs" / "case_study"

HISTORIAN_FILE = BASE_DIR / "outputs" / "story_spine" / "historian_output.json"
KPI_FILE = BASE_DIR / "outputs" / "results_sheet" / "kpi_analyst_output.json"
VERIFIER_FILE = BASE_DIR / "outputs" / "verification_report.json"
EVIDENCE_FILE = BASE_DIR / "outputs" / "evidence_chunks.json"

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:3b"
TIMEOUT = 300

MAX_EVENTS = 24
MAX_METRICS = 30
MAX_EVIDENCE = 22
MAX_EVIDENCE_CHARS = 650
MAX_OUTPUT_TOKENS = 2200

AUDIENCES = {
    "GATEKEEPER": (
        "Write for a senior approver. Prioritise governance, privacy, "
        "security, contractual publicity restrictions, risk ownership, "
        "evidence quality and approval conditions. Do not turn this into "
        "a technical sales pitch."
    ),
    "USER": (
        "Write for an operational user or team lead. Prioritise the "
        "operational problem, proposed workflow, how alerts or processes "
        "would fit into daily work, responsibilities, usability questions "
        "and what users still need to validate. Do not claim adoption."
    ),
    "BUYER": (
        "Write for a prospective business buyer. Prioritise the business "
        "problem, solution fit, delivery model, implementation dependencies, "
        "commercial decision considerations and evidence needed to assess value. "
        "Do not invent ROI, savings or performance gains."
    )
}

SECTION_NAMES = [
    "TITLE", "EXECUTIVE_SUMMARY", "PROBLEM", "OBJECTIVES",
    "APPROACH", "IMPLEMENTATION", "CHALLENGES",
    "RESULTS_AND_IMPACT", "LIMITATIONS", "CONCLUSION"
]

REQUIRED_SECTIONS = [
    "title", "executive_summary", "problem", "objectives",
    "approach", "implementation", "challenges", "results_and_impact"
]


# ------------------------- FILE HELPERS -------------------------

def load_json(path, default=None):
    if not path.exists():
        print(f"WARNING: Missing input file: {path}")
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"WARNING: Could not read {path.name}: {exc}")
        return default if default is not None else {}


def pick(data, keys, default=""):
    if not isinstance(data, dict):
        return default
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def stringify(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def normalize_ids(value):
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [stringify(x) for x in value if stringify(x)]
    return []


# ------------------------- INPUT EXTRACTION -------------------------

def extract_events(data):
    raw = pick(data, ["timeline_events", "events", "timeline"], [])
    if not isinstance(raw, list):
        return []

    events = []
    for item in raw:
        if isinstance(item, str):
            event = {
                "date": "Date not established",
                "type": "Project event",
                "description": item.strip(),
                "status": "NEEDS_HUMAN_REVIEW",
                "evidence_ids": []
            }
        elif isinstance(item, dict):
            event = {
                "date": stringify(pick(item, ["date", "event_date"], "Date not established")),
                "type": stringify(pick(item, ["event_type", "type", "category"], "Project event")),
                "description": stringify(pick(
                    item, ["description", "event", "claim", "summary", "details", "text"]
                )),
                "status": stringify(pick(
                    item, ["status", "verification_status", "completion_status"],
                    "NEEDS_HUMAN_REVIEW"
                )),
                "evidence_ids": normalize_ids(pick(item, ["evidence_ids", "evidence_id"], []))
            }
        else:
            continue

        if event["description"]:
            events.append(event)

    return events[:MAX_EVENTS]


def extract_metrics(data):
    raw = pick(data, ["candidate_metrics", "metrics", "kpi_candidates"], [])
    if not isinstance(raw, list):
        return []

    metrics = []
    for item in raw[:MAX_METRICS]:
        if not isinstance(item, dict):
            continue
        metrics.append({
            "name": stringify(pick(item, ["metric_name", "name", "metric"], "Unnamed metric")),
            "value": stringify(pick(item, ["final_value", "value", "candidate_value"], "Not established")),
            "baseline": stringify(pick(item, ["baseline", "baseline_value"], "Not established")),
            "definition": stringify(pick(item, ["definition", "metric_definition"], "Not established")),
            "window": stringify(pick(item, ["measurement_window", "window", "period"], "Not established")),
            "method": stringify(pick(item, ["methodology", "method", "calculation"], "Not established")),
            "source": stringify(pick(item, ["source_file", "filename", "source"], "Source not specified")),
            "unit": stringify(pick(item, ["unit", "units"], "")),
            "evidence_ids": normalize_ids(pick(item, ["evidence_ids", "evidence_id"], []))
        })
    return metrics


def extract_evidence(data):
    if isinstance(data, list):
        chunks = data
    elif isinstance(data, dict):
        chunks = pick(data, ["evidence_chunks", "chunks", "records"], [])
    else:
        chunks = []

    result = {}
    if not isinstance(chunks, list):
        return result

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        eid = stringify(pick(chunk, ["evidence_id", "id", "chunk_id"]))
        if not eid:
            continue
        result[eid] = {
            "source": stringify(pick(
                chunk, ["source_file", "filename", "file_name", "source"], "Unknown source"
            )),
            "content": stringify(pick(
                chunk, ["content", "text", "chunk_text", "body"], ""
            ))
        }
    return result


# ------------------------- PRIVACY FILTERS -------------------------

def redact_sensitive_text(text):
    """Conservative pattern-based masking. Human privacy review is still required."""
    if not isinstance(text, str):
        return text

    # Email addresses and phone-like strings.
    text = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "[EMAIL REDACTED]", text, flags=re.I
    )
    text = re.sub(
        r"(?<!\w)(?:\+?\d[\d\s().-]{8,}\d)(?!\w)",
        "[CONTACT NUMBER REDACTED]", text
    )

    # Contract / RFQ / purchase / reference identifiers.
    text = re.sub(
        r"\b[A-Z]{2,}(?:[-/][A-Z0-9]{2,}){2,}\b",
        "[REFERENCE ID REDACTED]", text
    )

    # Amounts and explicit budget figures are not needed in public drafts.
    text = re.sub(
        r"(?i)(?:₹|INR\s*)\s*[\d,]+(?:\.\d+)?\s*(?:lakh|lakhs|crore|crores)?",
        "[COMMERCIAL AMOUNT REDACTED]", text
    )

    # Names immediately following common honorifics.
    text = re.sub(
        r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}",
        "[PERSON REDACTED]", text
    )
    return text


def privacy_safe_events(events):
    safe = []
    for event in events:
        safe.append({
            **event,
            "description": redact_sensitive_text(event["description"]),
            "date": redact_sensitive_text(event["date"])
        })
    return safe


# ------------------------- EVIDENCE CONTEXT -------------------------

def build_evidence_context(events, metrics, evidence):
    requested_ids = []
    for event in events:
        requested_ids.extend(event["evidence_ids"])
    for metric in metrics:
        requested_ids.extend(metric["evidence_ids"])

    selected = []
    seen = set()
    for eid in requested_ids:
        if eid in evidence and eid not in seen:
            selected.append((eid, evidence[eid], True))
            seen.add(eid)
        if len(selected) >= MAX_EVIDENCE:
            break

    if not selected:
        for eid, item in list(evidence.items())[:MAX_EVIDENCE]:
            selected.append((eid, item, False))

    blocks = []
    for eid, item, linked in selected:
        content = redact_sensitive_text(item["content"][:MAX_EVIDENCE_CHARS])
        source = redact_sensitive_text(Path(item["source"]).name)
        blocks.append(
            f"[{eid}] Source label: {source}\n"
            f"Association: {'ID attached to an extracted event/metric' if linked else 'UNLINKED SAMPLE'}\n"
            f"Extract: {content}"
        )
    return "\n\n".join(blocks), len(selected)


def build_shared_context(events, metrics, evidence, verifier):
    safe_events = privacy_safe_events(events)

    event_lines = []
    for i, event in enumerate(safe_events, 1):
        ids = ", ".join(event["evidence_ids"]) or "none attached"
        event_lines.append(
            f"{i}. Date: {event['date']}; Type: {event['type']}; "
            f"Recorded status: {event['status']}; Evidence IDs: {ids}\n"
            f"Record: {event['description']}"
        )

    metric_lines = []
    for i, metric in enumerate(metrics, 1):
        # Do not send raw candidate values to narrative generation.
        metric_lines.append(
            f"{i}. Metric name: {metric['name']}; "
            f"definition: {metric['definition']}; "
            f"baseline field: {metric['baseline']}; "
            f"measurement window: {metric['window']}; "
            f"method: {metric['method']}; "
            f"source label: {redact_sensitive_text(Path(metric['source']).name)}. "
            f"STATUS: CANDIDATE - NOT VERIFIED."
        )

    evidence_text, evidence_count = build_evidence_context(
        safe_events, metrics, evidence
    )

    summary = {}
    if isinstance(verifier, dict):
        summary = pick(verifier, ["summary", "verification_summary"], {})

    context = f"""
PROJECT LABEL: Project Drishti
The project label is a pseudonym. Do not reveal or guess the real client,
company, site, employee, vendor, contract or location identity.

EXTRACTED EVENTS:
{chr(10).join(event_lines) if event_lines else "No events extracted."}

CANDIDATE METRIC DEFINITIONS:
{chr(10).join(metric_lines) if metric_lines else "No metrics extracted."}

SOURCE EXTRACTS:
{evidence_text if evidence_text else "No source extracts available."}

VERIFICATION SUMMARY:
{json.dumps(summary, ensure_ascii=False)}

NON-NEGOTIABLE EVIDENCE RULES:
- The source library is incomplete and machine-extracted.
- A discussion, RFQ, proposal, plan or signed agreement does not prove deployment.
- Never describe a pilot, rollout, installation or operation as completed unless
  an extracted record explicitly establishes completion.
- When status is unclear, say "the records describe a proposal/plan/discussion"
  or "completion is not established in the available records."
- Do not invent or infer project outcomes, adoption, user satisfaction or impact.
- Candidate metrics are not verified results. Do not quote candidate values.
- Do not invent dates, percentages, financial figures, quotations or ROI.
- Do not expose personal names, company names, plant/site names, vendor names,
  exact locations, contract/RFQ numbers, phone numbers, emails or budget amounts.
- Refer to parties only as "the client", "the solution provider", "site team",
  "legal team", "IT/OT team" or similarly generic roles.
- Do not say that privacy, security or legal approval has been completed unless
  the evidence clearly confirms it.
- No client approval for publication is implied.
- Use concise, non-repetitive business prose.
"""
    return context, evidence_count, safe_events


# ------------------------- LOCAL LLM -------------------------

def ask_ollama(system_prompt, user_prompt):
    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "options": {
            "temperature": 0.1,
            "num_ctx": 8192,
            "num_predict": MAX_OUTPUT_TOKENS
        }
    }
    response = requests.post(
        OLLAMA_URL, json=payload, timeout=TIMEOUT
    )
    response.raise_for_status()
    answer = response.json().get("message", {}).get("content", "")
    if not answer.strip():
        raise ValueError("Ollama returned an empty response.")
    return answer.strip()


def parse_sections(response):
    result = {}
    upper = response.upper()
    positions = []

    for name in SECTION_NAMES:
        marker = f"[[{name}]]"
        pos = upper.find(marker)
        if pos >= 0:
            positions.append((pos, name, len(marker)))

    positions.sort()
    for i, (start, name, marker_len) in enumerate(positions):
        content_start = start + marker_len
        content_end = positions[i + 1][0] if i + 1 < len(positions) else len(response)
        content = response[content_start:content_end].strip()
        content = re.sub(
            rf"\[\[/{re.escape(name)}\]\]", "", content, flags=re.I
        ).strip()
        result[name.lower()] = content

    return result


def fallback_draft(audience, events, metrics, evidence_count):
    descriptions = [e["description"] for e in events[:7]]
    event_text = "\n".join(f"- {x}" for x in descriptions)
    metric_names = [m["name"] for m in metrics[:12]]

    if audience == "GATEKEEPER":
        problem = (
            "The available records describe a safety-compliance initiative, "
            "but do not establish a complete account of delivery or operational "
            "outcomes. The central governance task is to distinguish documented "
            "decisions from proposals and unverified claims."
        )
        objectives = (
            "Establish a traceable account of scope and decisions; identify "
            "privacy, security and publicity obligations; and determine which "
            "claims can be considered for approval."
        )
        approach = (
            "The available material describes the proposed use of video analytics "
            "alongside discussions about operational integration and governance. "
            "The records must be checked by the relevant owners before any "
            "implementation or compliance status is asserted."
        )
    elif audience == "USER":
        problem = (
            "The records describe an operational need to monitor safety practices "
            "more consistently. They do not yet provide a verified account of "
            "how a finished system changed day-to-day work."
        )
        objectives = (
            "Explain the intended operational workflow, identify the roles that "
            "would interact with it, and make clear what needs testing before "
            "users can rely on the process."
        )
        approach = (
            "The proposed approach uses existing camera infrastructure and "
            "video analytics to support safety monitoring. The available records "
            "do not establish that the proposed workflow is fully operational."
        )
    else:
        problem = (
            "The records describe a business need for stronger safety monitoring "
            "and more consistent use of existing camera infrastructure. They "
            "do not yet establish a measured commercial outcome."
        )
        objectives = (
            "Describe the business problem, explain the proposed delivery model "
            "and identify the operational, technical and governance conditions "
            "a buyer should validate."
        )
        approach = (
            "The documented proposal centres on video analytics using existing "
            "camera streams and infrastructure. Deployment status and measurable "
            "value must be confirmed before the approach is presented as proven."
        )

    return {
        "title": f"Project Drishti: {audience.title()} Perspective",
        "executive_summary": (
            "This working draft summarises the project records available to the "
            "Writer Agent. It distinguishes the proposed initiative and recorded "
            "project activity from completed delivery and verified outcomes. "
            f"The current extraction includes {len(events)} events, "
            f"{len(metrics)} candidate metrics and {evidence_count} evidence extracts."
        ),
        "problem": problem,
        "objectives": objectives,
        "approach": approach,
        "implementation": (
            "The extracted records identify the following activity. They are "
            "provided as a review trail and do not independently prove completion:\n\n"
            + (event_text or "- No events were extracted.")
        ),
        "challenges": (
            "The main review challenges are incomplete extraction, uncertain "
            "completion status, missing or unverified metric baselines, and "
            "privacy, security and publicity questions that require owner review."
        ),
        "results_and_impact": (
            "No verified impact is asserted in this draft. Candidate measures "
            "identified for validation include: "
            + (", ".join(metric_names) if metric_names else "no candidate measures")
            + ". Each requires a confirmed definition, baseline, measurement "
            "window, calculation method and source before it can be reported as a result."
        ),
        "limitations": (
            "This draft is based on partial machine-extracted records. It is not "
            "a complete source review. Dates, scope, delivery status, metrics, "
            "privacy controls and publicity permissions require human confirmation."
        ),
        "conclusion": (
            "The records provide a starting point for a case study, not a "
            "publication-ready success story. Confirm the chronology and delivery "
            "status, validate metrics, complete privacy and contractual review, "
            "and obtain written client approval before external use."
        )
    }


def generate_draft(audience, focus, context, events, metrics, evidence_count):
    system = (
        "You are an experienced B2B case-study editor and evidence auditor. "
        "Write restrained, specific, polished prose. Accuracy is more important "
        "than persuasive language. Never fill evidence gaps with plausible guesses."
    )

    prompt = f"""
Write one complete case-study draft for the audience below.

AUDIENCE: {audience}
AUDIENCE PRIORITIES: {focus}

Make this version genuinely useful to this audience. Do not simply change the
tone of a generic case study. Avoid repeating the same fact in multiple sections.

STRICT WRITING RULES:
- Use only facts supported by the supplied records.
- Do not include personal, company, vendor or site names. Use generic roles.
- Do not include contract/RFQ references, exact locations or budget amounts.
- Never state that deployment, pilot, installation or rollout happened unless
  the records explicitly establish completion.
- If the record describes a proposal, say "proposed".
- If the record describes a discussion, say "discussed".
- If the status is unclear, say it is not established.
- Do not include candidate metric values or make up a target.
- Do not claim improved safety, reduced incidents, savings, ROI or adoption.
- In Results and Impact, explain what is measurable and what evidence is missing.
- Do not repeat paragraphs or pad the conclusion.
- Use about 2-4 sentences per section. Implementation can use 2-3 paragraphs.
- Write in professional, natural business English.

Return exactly these opening markers in this order:

[[TITLE]]
A short title without client or vendor names.
[[EXECUTIVE_SUMMARY]]
A concise summary of the project and evidence status.
[[PROBLEM]]
The documented operational/business problem.
[[OBJECTIVES]]
The documented objectives, clearly labelled as intended objectives.
[[APPROACH]]
The proposed approach, not assumed deployment.
[[IMPLEMENTATION]]
What the records establish about the sequence of work. Separate proposal,
agreement and completed delivery.
[[CHALLENGES]]
Documented or explicitly unresolved challenges.
[[RESULTS_AND_IMPACT]]
No unsupported success claims. Explain which results remain unverified.
[[LIMITATIONS]]
The limits of the current source records.
[[CONCLUSION]]
A concise, actionable conclusion.

SOURCE CONTEXT:
{context}
"""
    response = ask_ollama(system, prompt)
    sections = parse_sections(response)

    missing = [
        name for name in REQUIRED_SECTIONS
        if not sections.get(name, "").strip()
    ]
    fallback = fallback_draft(audience, events, metrics, evidence_count)

    if missing:
        print(f"  Missing sections {missing}; using safe fallback for this audience.")
        return fallback, "EVIDENCE_GROUNDED_FALLBACK_DRAFT"

    result = {}
    for section in SECTION_NAMES:
        key = section.lower()
        value = sections.get(key, "").strip()
        if not value:
            value = fallback[key]
        result[key] = value

    result["title"] = result["title"].splitlines()[0].strip()
    return result, "LOCAL_LLM_NARRATIVE_DRAFT"


# ------------------------- DETERMINISTIC RESULTS SECTION -------------------------

def make_results_section(metrics):
    if not metrics:
        return (
            "The current extraction did not provide candidate metrics in a form "
            "that can be reported. No quantified impact is asserted."
        )

    names = []
    for metric in metrics[:15]:
        names.append(metric["name"])

    return (
        "The KPI extraction identified candidate measures for further validation: "
        + "; ".join(names)
        + ". These are not verified results. Before reporting any value, the project "
          "owner must confirm the metric definition, baseline, final value, measurement "
          "window, calculation method and source record. No improvement, reduction, "
          "ROI or operational benefit is asserted in this draft."
    )


# ------------------------- QUALITY CONTROL -------------------------

def word_count(text):
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def repetition_score(text):
    paragraphs = [
        re.sub(r"\W+", " ", p).strip().lower()
        for p in re.split(r"\n\s*\n", text or "")
        if len(p.strip()) > 40
    ]
    counts = Counter(paragraphs)
    return [p[:120] for p, count in counts.items() if count > 1]


def detect_status_language(text):
    low = (text or "").lower()
    positive = bool(re.search(
        r"\b(deployed|installed|operational|went live|rolled out|"
        r"fully implemented|pilot was completed|rollout was completed)\b",
        low
    ))
    negative = bool(re.search(
        r"\b(not deployed|not yet deployed|not operational|"
        r"deployment is not established|completion is not established|"
        r"no evidence of deployment)\b",
        low
    ))
    return positive, negative


def detect_sensitive_patterns(text):
    checks = {
        "email": r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "phone": r"(?<!\w)(?:\+?\d[\d\s().-]{8,}\d)(?!\w)",
        "reference_id": r"\b[A-Z]{2,}(?:[-/][A-Z0-9]{2,}){2,}\b",
        "currency_amount": r"(?i)(?:₹|INR\s*)\s*[\d,]+(?:\.\d+)?"
    }
    found = []
    for label, pattern in checks.items():
        if re.search(pattern, text or ""):
            found.append(label)
    return found


def run_quality_control(drafts, events, metrics):
    report = {
        "overall_status": "REVIEW_REQUIRED",
        "checks": [],
        "cross_version_flags": [],
        "drafts": {}
    }

    # Check each audience version.
    for audience, draft in drafts.items():
        narrative_fields = [
            "executive_summary", "problem", "objectives", "approach",
            "implementation", "challenges", "results_and_impact",
            "limitations", "conclusion"
        ]
        full_text = "\n\n".join(str(draft.get(k, "")) for k in narrative_fields)
        repeated = repetition_score(full_text)
        sensitive = detect_sensitive_patterns(full_text)
        missing = [
            key for key in REQUIRED_SECTIONS
            if not str(draft.get(key, "")).strip()
        ]
        too_short = {
            key: word_count(str(draft.get(key, "")))
            for key in narrative_fields
            if word_count(str(draft.get(key, ""))) < 12
        }

        issues = []
        if repeated:
            issues.append("Repeated paragraphs detected.")
        if sensitive:
            issues.append("Potential sensitive patterns: " + ", ".join(sensitive))
        if missing:
            issues.append("Missing required sections: " + ", ".join(missing))
        if too_short:
            issues.append("Some sections may be incomplete: " + ", ".join(too_short))

        report["drafts"][audience] = {
            "word_count": word_count(full_text),
            "repeated_paragraphs": repeated,
            "sensitive_patterns": sensitive,
            "missing_sections": missing,
            "short_sections_word_counts": too_short,
            "status_language": {
                "positive_deployment_language": detect_status_language(full_text)[0],
                "negative_or_uncertain_deployment_language": detect_status_language(full_text)[1]
            },
            "issues": issues,
            "status": "PASS_WITH_REVIEW" if not issues else "NEEDS_REVISION"
        }

    # Cross-version deployment contradictions.
    statuses = {
        audience: detect_status_language(
            "\n".join(str(v) for k, v in draft.items() if isinstance(v, str))
        )
        for audience, draft in drafts.items()
    }
    any_positive = any(v[0] for v in statuses.values())
    any_negative = any(v[1] for v in statuses.values())

    if any_positive and any_negative:
        report["cross_version_flags"].append(
            "Possible contradiction: one or more versions use completed/deployed "
            "language while another says deployment is not established. Check source "
            "records and correct all versions to one evidence-supported status."
        )

    # All generated case studies share the same evidence and KPI basis.
    if len(drafts) != 3:
        report["cross_version_flags"].append(
            "Expected three audience versions; one or more are missing."
        )

    # Metrics are candidate-only until manually validated.
    report["metric_rule"] = (
        f"{len(metrics)} candidate metrics were supplied. They are not treated "
        "as verified impact in the generated Results and Impact section."
    )

    if report["cross_version_flags"] or any(
        item["status"] != "PASS_WITH_REVIEW"
        for item in report["drafts"].values()
    ):
        report["overall_status"] = "REVISION_REQUIRED"
    else:
        report["overall_status"] = "PASS_WITH_HUMAN_REVIEW"

    return report


# ------------------------- TRACEABILITY -------------------------

def build_claim_register(events):
    register = []
    for event in events:
        register.append({
            "claim_or_event": event["description"],
            "date_as_extracted": event["date"],
            "recorded_status": event["status"],
            "evidence_ids": event["evidence_ids"],
            "verification_status": (
                "NEEDS_HUMAN_REVIEW" if event["evidence_ids"]
                else "NO_EVIDENCE_ID_ATTACHED"
            )
        })
    return register


def attach_metadata(draft, audience, events, metrics, status):
    draft.update({
        "audience": audience,
        "audience_priorities": AUDIENCES[audience],
        "generation_status": status,
        "review_status": "NEEDS_HUMAN_REVIEW",
        "publication_status": "HOLD",
        "human_review_required": True,
        "candidate_metrics": metrics,
        "claims_requiring_verification": build_claim_register(events),
        "privacy_note": (
            "Pattern-based redaction was applied. This is not a complete "
            "anonymisation guarantee; a human must inspect the draft and sources."
        )
    })
    return draft


# ------------------------- OUTPUT -------------------------

def markdown_output(drafts, qc):
    lines = [
        "# PROJECT DRISHTI - AUDIENCE-SPECIFIC CASE STUDIES",
        "",
        "**DRAFT - NOT APPROVED FOR PUBLICATION OR EXTERNAL SHARING**",
        "",
        "Generated locally. All claims require human review and client approval.",
        "",
        f"**Quality-control status: {qc['overall_status']}**",
        ""
    ]

    sections = [
        ("Executive Summary", "executive_summary"),
        ("Problem", "problem"),
        ("Objectives", "objectives"),
        ("Approach", "approach"),
        ("Implementation", "implementation"),
        ("Challenges", "challenges"),
        ("Results and Impact", "results_and_impact"),
        ("Limitations", "limitations"),
        ("Conclusion", "conclusion")
    ]

    for audience, draft in drafts.items():
        lines.extend([
            "---", "", f"# {audience} CASE STUDY", "",
            f"## {draft['title']}", ""
        ])

        for heading, key in sections:
            lines.extend([f"### {heading}", "", str(draft.get(key, "")), ""])

        lines.extend([
            "### Review Status", "",
            f"- Generation: {draft['generation_status']}",
            "- Human review: REQUIRED",
            "- Publication: HOLD",
            ""
        ])

    lines.extend(["---", "", "# QUALITY CONTROL REPORT", ""])
    lines.append(f"**Overall: {qc['overall_status']}**")
    lines.append("")
    for audience, checks in qc["drafts"].items():
        lines.append(f"## {audience}")
        lines.append(f"- Status: {checks['status']}")
        lines.append(f"- Word count: {checks['word_count']}")
        for issue in checks["issues"]:
            lines.append(f"- Issue: {issue}")
        if not checks["issues"]:
            lines.append("- No automatic issues detected; human review still required.")
        lines.append("")

    if qc["cross_version_flags"]:
        lines.append("## Cross-version flags")
        for flag in qc["cross_version_flags"]:
            lines.append(f"- {flag}")
        lines.append("")

    return "\n".join(lines)


def run_writer():
    print("\nStarting Writer + Quality Control Agent...")
    print("=" * 64)

    historian = load_json(HISTORIAN_FILE)
    kpi_data = load_json(KPI_FILE)
    verifier = load_json(VERIFIER_FILE)
    evidence_data = load_json(EVIDENCE_FILE, [])

    events = extract_events(historian)
    metrics = extract_metrics(kpi_data)
    evidence = extract_evidence(evidence_data)

    print("Historical events:", len(events))
    print("Candidate metrics:", len(metrics))
    print("Evidence chunks loaded:", len(evidence))

    context, evidence_count, safe_events = build_shared_context(
        events, metrics, evidence, verifier
    )

    drafts = {}
    for audience, focus in AUDIENCES.items():
        print(f"\nGenerating {audience} case study...")
        try:
            draft, status = generate_draft(
                audience, focus, context, safe_events, metrics, evidence_count
            )
            print(f"{audience}: generated.")
        except Exception as exc:
            print(f"{audience}: Ollama generation failed: {exc}")
            draft = fallback_draft(audience, safe_events, metrics, evidence_count)
            status = "EVIDENCE_GROUNDED_FALLBACK_DRAFT"

        # Replace generated results text with deterministic candidate-only wording.
        draft["results_and_impact"] = make_results_section(metrics)

        # Apply final privacy pattern pass to all narrative fields.
        for key in SECTION_NAMES:
            field = key.lower()
            if field in draft and isinstance(draft[field], str):
                draft[field] = redact_sensitive_text(draft[field])

        drafts[audience] = attach_metadata(
            draft, audience, safe_events, metrics, status
        )

    qc = run_quality_control(drafts, safe_events, metrics)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "agent": "Writer and Quality Control Agent",
        "project": "Project Drishti",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL,
        "historical_events_loaded": len(events),
        "candidate_metrics_loaded": len(metrics),
        "evidence_chunks_loaded": len(evidence),
        "evidence_chunks_in_context": evidence_count,
        "case_studies": drafts,
        "quality_control": qc,
        "claim_register": build_claim_register(safe_events),
        "publication_gate": {
            "approved": False,
            "status": "HOLD_PENDING_HUMAN_AND_CLIENT_APPROVAL",
            "reason": (
                "Automated writing and quality checks do not constitute "
                "verification, legal approval, privacy approval or client consent."
            )
        }
    }

    json_path = OUTPUT_DIR / "writer_output.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    md_path = OUTPUT_DIR / "case_studies.md"
    md_path.write_text(markdown_output(drafts, qc), encoding="utf-8")

    qc_path = OUTPUT_DIR / "writer_quality_report.json"
    with open(qc_path, "w", encoding="utf-8") as f:
        json.dump(qc, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 64)
    print("WRITER + QUALITY CONTROL FINISHED")
    for audience in AUDIENCES:
        print(audience, ":", drafts[audience]["generation_status"])
    print("Quality control:", qc["overall_status"])
    if qc["cross_version_flags"]:
        for flag in qc["cross_version_flags"]:
            print("QC FLAG:", flag)

    print("\nJSON:", json_path)
    print("Markdown:", md_path)
    print("QC report:", qc_path)
    print("Publication approved: NO")
    print("All drafts remain on HOLD pending human and client approval.")


if __name__ == "__main__":
    run_writer()
