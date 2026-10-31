
import json
import re
from pathlib import Path
from collections import defaultdict


# =====================================================
# CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent

EVIDENCE_FILE = BASE_DIR / "outputs" / "evidence_chunks.json"

HISTORIAN_FILE = (
    BASE_DIR / "outputs" / "story_spine"
    / "historian_output.json"
)

KPI_FILE = (
    BASE_DIR / "outputs" / "results_sheet"
    / "kpi_analyst_output.json"
)

RISK_FILE = (
    BASE_DIR / "outputs" / "exposure_report"
    / "risk_analyst_output.json"
)

OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "verification_report.json"


# =====================================================
# LOAD JSON
# =====================================================

def load_json(path):

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =====================================================
# BASIC UTILITIES
# =====================================================

def normalize_text(text):

    text = str(text).lower()
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_source_name(item):

    if not isinstance(item, dict):
        return "NOT PROVIDED"

    return (
        item.get("source_file")
        or item.get("source_path")
        or item.get("file_name")
        or item.get("file")
        or "NOT PROVIDED"
    )


def get_claim_text(item):

    if isinstance(item, str):
        return item.strip()

    if not isinstance(item, dict):
        return ""

    fields = [
        "claim_text",
        "event_description",
        "event_text",
        "event",
        "description",
        "summary",
        "statement",
        "text",
        "event_name",
        "milestone",
        "details",
        "action",
        "decision",
        "change",
        "outcome"
    ]

    for field in fields:

        value = item.get(field)

        if isinstance(value, str) and value.strip():
            return value.strip()

    # Fallback: retain event information without metadata.
    excluded = {
        "evidence_id",
        "evidence_ids",
        "source_file",
        "source_path",
        "document_type",
        "verification_status",
        "status",
        "confidence"
    }

    meaningful = {
        key: value
        for key, value in item.items()
        if key.lower() not in excluded
        and value not in (None, "", [], {})
    }

    if meaningful:
        return json.dumps(meaningful, ensure_ascii=False)

    return ""


def collect_evidence_ids(item):

    ids = []

    if not isinstance(item, dict):
        return ids

    for key, value in item.items():

        if "evidence_id" in key.lower():

            if isinstance(value, str):
                ids.append(value)

            elif isinstance(value, list):
                ids.extend(
                    x for x in value
                    if isinstance(x, str)
                )

        elif isinstance(value, dict):
            ids.extend(collect_evidence_ids(value))

        elif isinstance(value, list):

            for child in value:
                if isinstance(child, dict):
                    ids.extend(collect_evidence_ids(child))

    return list(dict.fromkeys(ids))


# =====================================================
# BUILD EVIDENCE LOOKUP
# =====================================================

def build_evidence_lookup(evidence):

    evidence_by_id = {}
    evidence_by_source = defaultdict(list)

    for item in evidence:

        if not isinstance(item, dict):
            continue

        evidence_id = item.get("evidence_id")

        if evidence_id:
            evidence_by_id[evidence_id] = item

        source = get_source_name(item)

        if source != "NOT PROVIDED":
            filename = Path(source).name.lower()
            evidence_by_source[filename].append(item)

    return evidence_by_id, evidence_by_source


# =====================================================
# EXTRACT CLAIMS
# =====================================================

def extract_candidate_claims(historian, kpi, risk):

    claims = []

    # 1. HISTORICAL EVENTS

    events = historian.get("timeline_events", [])

    print("Historian timeline events:", len(events))

    for item in events:

        claim_text = get_claim_text(item)

        if not claim_text:
            continue

        evidence_ids = collect_evidence_ids(item)

        claims.append({

            "claim_id": f"CLM-{len(claims) + 1:04d}",

            "claim_type": "HISTORICAL_EVENT",

            "description": claim_text[:300],

            "claim_text": claim_text,

            "source_file": get_source_name(item),

            "evidence_id": (
                evidence_ids[0] if evidence_ids else None
            ),

            "evidence_ids": evidence_ids,

            "status": "NEEDS_REVIEW"

        })

    # 2. KPI METRICS

    for item in kpi.get("candidate_metrics", []):

        if not isinstance(item, dict):
            continue

        claims.append({

            "claim_id": f"CLM-{len(claims) + 1:04d}",

            "claim_type": "NUMERIC_METRIC",

            "description": item.get(
                "metric_name",
                "Unnamed metric"
            ),

            "claim_text": json.dumps(
                item,
                ensure_ascii=False
            ),

            "source_file": get_source_name(item),

            "evidence_id": None,

            "evidence_ids": [],

            "metric_details": item,

            "status": "NEEDS_REVIEW"

        })

    # 3. RISK FINDINGS

    for item in risk.get("risk_findings", []):

        if not isinstance(item, dict):
            continue

        evidence_id = item.get("evidence_id")

        claims.append({

            "claim_id": f"CLM-{len(claims) + 1:04d}",

            "claim_type": "RISK_SCREENING_FINDING",

            "description": item.get(
                "category",
                "Risk finding"
            ),

            "claim_text": "",

            "source_file": get_source_name(item),

            "evidence_id": evidence_id,

            "evidence_ids": (
                [evidence_id] if evidence_id else []
            ),

            "status": "NEEDS_REVIEW"

        })

    return claims


# =====================================================
# RULE-BASED VERIFICATION
# =====================================================

def verify_claims(claims, evidence_by_id, evidence_by_source):

    for claim in claims:

        evidence_ids = claim.get("evidence_ids", [])

        if not evidence_ids and claim.get("evidence_id"):
            evidence_ids = [claim["evidence_id"]]

        # Check evidence IDs.
        valid_ids = [
            eid for eid in evidence_ids
            if eid in evidence_by_id
        ]

        claim["valid_evidence_ids"] = valid_ids

        if valid_ids:
            claim["source_reference_status"] = "VALID_EVIDENCE_REFERENCE"

        elif evidence_ids:
            claim["source_reference_status"] = "INVALID_EVIDENCE_REFERENCE"

        else:
            claim["source_reference_status"] = "NO_EVIDENCE_ID"

        # Check source file.
        source = claim.get("source_file", "")

        if source and source != "NOT PROVIDED":

            filename = Path(source).name.lower()

            source_exists = filename in evidence_by_source

        else:
            source_exists = False

        claim["source_file_found_in_evidence_store"] = source_exists

        # Retrieve evidence.
        supporting_evidence = []

        for eid in valid_ids:
            supporting_evidence.append(evidence_by_id[eid])

        if not supporting_evidence and source_exists:

            supporting_evidence = evidence_by_source.get(
                filename, []
            )

        claim["matching_evidence_count"] = len(supporting_evidence)

        # Basic claim checks.
        if not claim.get("claim_text") and claim["claim_type"] != "RISK_SCREENING_FINDING":

            claim["rule_check_status"] = "MISSING_CLAIM_TEXT"

        elif supporting_evidence:

            claim["rule_check_status"] = "REFERENCE_VALID_REQUIRES_CONTENT_REVIEW"

        else:

            claim["rule_check_status"] = "MISSING_OR_UNMATCHED_EVIDENCE"

        # Numeric metrics need separate calculation validation.
        if claim["claim_type"] == "NUMERIC_METRIC":

            claim["calculation_review_status"] = (
                "PENDING_MANUAL_DATA_VALIDATION"
            )

        # Risk findings are potential flags, not verified violations.
        if claim["claim_type"] == "RISK_SCREENING_FINDING":

            claim["risk_review_status"] = (
                "PENDING_HUMAN_REVIEW"
            )

        # Never automatically approve a factual claim.
        claim["status"] = "NEEDS_REVIEW"
        claim["human_review_required"] = True

    return claims


# =====================================================
# EXACT DUPLICATE DETECTION
# =====================================================

def find_exact_duplicates(evidence):

    grouped = defaultdict(list)

    for item in evidence:

        if not isinstance(item, dict):
            continue

        content = normalize_text(
            item.get("content", "")
        )

        if content:

            grouped[content].append({

                "evidence_id": item.get("evidence_id"),

                "source_file": get_source_name(item)

            })

    duplicates = []

    for content, sources in grouped.items():

        if len(sources) > 1:

            duplicates.append({

                "duplicate_count": len(sources),

                "sources": sources

            })

    return duplicates


# =====================================================
# SUMMARY
# =====================================================

def build_summary(claims):

    summary = {

        "TOTAL_CLAIMS": len(claims),

        "VALID_EVIDENCE_REFERENCES": 0,

        "INVALID_EVIDENCE_REFERENCES": 0,

        "NO_EVIDENCE_ID": 0,

        "SOURCE_FILE_FOUND": 0,

        "SOURCE_FILE_NOT_FOUND": 0,

        "NEEDS_REVIEW": 0

    }

    for claim in claims:

        reference_status = claim.get(
            "source_reference_status"
        )

        if reference_status == "VALID_EVIDENCE_REFERENCE":
            summary["VALID_EVIDENCE_REFERENCES"] += 1

        elif reference_status == "INVALID_EVIDENCE_REFERENCE":
            summary["INVALID_EVIDENCE_REFERENCES"] += 1

        else:
            summary["NO_EVIDENCE_ID"] += 1

        if claim.get("source_file_found_in_evidence_store"):
            summary["SOURCE_FILE_FOUND"] += 1
        else:
            summary["SOURCE_FILE_NOT_FOUND"] += 1

        if claim.get("status") == "NEEDS_REVIEW":
            summary["NEEDS_REVIEW"] += 1

    return summary


# =====================================================
# MAIN PIPELINE
# =====================================================

def run_verifier():

    print("\nStarting Rule-Based Verifier Agent...\n")

    evidence = load_json(EVIDENCE_FILE)

    historian = load_json(HISTORIAN_FILE)

    kpi = load_json(KPI_FILE)

    risk = load_json(RISK_FILE)

    # Build lookup tables.
    evidence_by_id, evidence_by_source = (
        build_evidence_lookup(evidence)
    )

    # Extract candidate claims.
    claims = extract_candidate_claims(
        historian,
        kpi,
        risk
    )

    print("Candidate claims extracted:", len(claims))

    # Perform deterministic checks.
    claims = verify_claims(
        claims,
        evidence_by_id,
        evidence_by_source
    )

    # Find exact duplicate evidence.
    duplicates = find_exact_duplicates(evidence)

    # Build summary.
    summary = build_summary(claims)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output = {

        "agent": "Rule-Based Verifier Agent",

        "project": "Project Drishti",

        "status": "REFERENCE_CHECK_COMPLETE_REQUIRES_HUMAN_REVIEW",

        "verification_method": "PYTHON_RULE_BASED",

        "total_evidence_chunks": len(evidence),

        "total_candidate_claims": len(claims),

        "verification_summary": summary,

        "claims": claims,

        "exact_duplicate_chunks": duplicates,

        "limitations": [

            "This agent checks evidence references and source-file matches only.",

            "A valid evidence reference does not prove that the content supports the claim.",

            "Semantic verification is not performed.",

            "Numeric metrics require calculation and source-data validation.",

            "Risk findings require separate human review.",

            "Exact duplicate detection does not detect paraphrases.",

            "No claim is automatically approved for publication."

        ]

    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            indent=4,
            ensure_ascii=False
        )

    print("\nRULE-BASED VERIFIER COMPLETE")
    print("-" * 40)

    print("Evidence chunks:", len(evidence))

    print("Candidate claims:", len(claims))

    print("Duplicate groups:", len(duplicates))

    print("\nVERIFICATION SUMMARY:")

    for key, value in summary.items():
        print(f"{key}: {value}")

    print("\nOutput saved to:")
    print(OUTPUT_FILE)

    return output


if __name__ == "__main__":
    run_verifier()
