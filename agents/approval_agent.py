
import json
from pathlib import Path
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_DIR = BASE_DIR / "outputs" / "approval_request"

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

VERIFIER_FILE = (
    BASE_DIR / "outputs" / "verification_report.json"
)

WRITER_FILE = (
    BASE_DIR / "outputs" / "case_study"
    / "writer_output.json"
)

MEDIA_FILE = (
    BASE_DIR / "outputs" / "media_pack"
    / "media_inventory.json"
)

REQUEST_FILE = OUTPUT_DIR / "approval_request.json"
SHEET_FILE = OUTPUT_DIR / "approval_sheet.json"


# --------------------------------------------------
# FILE HANDLING
# --------------------------------------------------

def load_json(file_path):
    if not file_path.exists():
        raise FileNotFoundError(
            f"Required output not found: {file_path}"
        )

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_optional_json(file_path):
    if not file_path.exists():
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, file_path):
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )


# --------------------------------------------------
# VERIFICATION CHECK
# --------------------------------------------------

def check_verification(verifier):

    summary = verifier.get("verification_summary", {})

    total_claims = summary.get(
        "TOTAL_CLAIMS",
        verifier.get("total_candidate_claims", 0)
    )

    supported = summary.get("SUPPORTED", 0)
    needs_review = summary.get("NEEDS_REVIEW", 0)
    conflicting = summary.get("CONFLICTING", 0)
    unsupported = summary.get("UNSUPPORTED", 0)

    invalid_references = summary.get(
        "INVALID_EVIDENCE_REFERENCES", 0
    )

    no_evidence_id = summary.get(
        "NO_EVIDENCE_ID", 0
    )

    # The current rule-based verifier checks references,
    # not semantic support. Therefore it cannot pass this gate.

    return {
        "total_claims": total_claims,
        "supported": supported,
        "needs_review": needs_review,
        "conflicting": conflicting,
        "unsupported": unsupported,
        "invalid_evidence_references": invalid_references,
        "claims_without_evidence_id": no_evidence_id,
        "verification_method": verifier.get(
            "verification_method",
            "NOT_SPECIFIED"
        ),
        "passed": (
            total_claims > 0
            and supported == total_claims
            and needs_review == 0
            and conflicting == 0
            and unsupported == 0
            and invalid_references == 0
        )
    }


# --------------------------------------------------
# RISK CHECK
# --------------------------------------------------

def check_risks(risk):

    findings = risk.get("risk_findings", [])

    pending = []
    approved = []

    for item in findings:

        finding_id = item.get(
            "finding_id",
            "UNKNOWN_FINDING"
        )

        if item.get("approval_status") == "APPROVED":
            approved.append(finding_id)
        else:
            pending.append(finding_id)

    return {
        "total_findings": len(findings),
        "approved_findings": len(approved),
        "pending_findings": pending,
        "passed": len(pending) == 0
    }


# --------------------------------------------------
# MEDIA CHECK
# --------------------------------------------------

def check_media(media):

    if media is None:
        return {
            "available": False,
            "total_assets": 0,
            "pending_assets": [],
            "passed": False,
            "reason": "Media inventory file is missing."
        }

    assets = media.get("assets", [])

    pending = []

    for asset in assets:

        asset_id = asset.get(
            "asset_id",
            "UNKNOWN_ASSET"
        )

        if (
            asset.get("visual_review_status") != "APPROVED"
            or asset.get("permission_status") != "APPROVED"
            or asset.get("publication_status") != "APPROVED"
        ):
            pending.append(asset_id)

    return {
        "available": True,
        "total_assets": len(assets),
        "pending_assets": pending,
        "passed": (
            len(assets) >= 3
            and len(pending) == 0
        )
    }


# --------------------------------------------------
# WRITER CHECK
# --------------------------------------------------

def check_writer(writer):

    case_studies = writer.get("case_studies", {})

    required = {
        "GATEKEEPER",
        "USER",
        "BUYER"
    }

    available = set(case_studies.keys())

    missing = sorted(required - available)

    incomplete = []

    required_sections = [
        "title",
        "executive_summary",
        "project_background",
        "solution_and_implementation",
        "results_and_impact",
        "conclusion"
    ]

    for audience in required.intersection(available):

        draft = case_studies[audience]

        missing_sections = [
            section
            for section in required_sections
            if not draft.get(section)
        ]

        if missing_sections:
            incomplete.append({
                "audience": audience,
                "missing_sections": missing_sections
            })

    return {
        "required_versions": sorted(required),
        "available_versions": sorted(available),
        "missing_versions": missing,
        "incomplete_versions": incomplete,
        "passed": (
            len(missing) == 0
            and len(incomplete) == 0
        )
    }


# --------------------------------------------------
# APPROVAL RECORDS
# --------------------------------------------------

def build_approval_items():

    audiences = [
        "GATEKEEPER",
        "USER",
        "BUYER"
    ]

    items = []

    for audience in audiences:

        items.append({
            "audience": audience,
            "reviewer_name": None,
            "reviewer_role": None,
            "decision": "PENDING",
            "comments": "",
            "requested_changes": [],
            "reviewed_at": None
        })

    return items


def build_client_approval_choices():

    return {
        "publication_options": [
            {
                "option": "NAMED",
                "description": (
                    "Client name and approved identifying details "
                    "may appear in the case study."
                )
            },
            {
                "option": "ANONYMISED",
                "description": (
                    "Client identity and identifying details "
                    "must be removed or replaced."
                )
            },
            {
                "option": "INTERNAL_ONLY",
                "description": (
                    "The material may be used internally only "
                    "and must not be publicly published."
                )
            }
        ],
        "selected_option": None,
        "additional_conditions": [],
        "client_decision": "PENDING"
    }


# --------------------------------------------------
# CLIENT APPROVAL REQUEST
# --------------------------------------------------

def build_client_message():

    return {
        "subject": (
            "Request for Review and Approval - "
            "Project Drishti Case Study"
        ),

        "recipient": "[Client Approver / Authorized Representative]",

        "message": (
            "Dear [Client Representative],\n\n"
            "We have prepared preliminary case study materials "
            "documenting Project Drishti and would appreciate "
            "your review before any external use.\n\n"
            "Please review the proposed case study versions and "
            "associated media assets. Kindly indicate whether "
            "the material may be used under a named, anonymised "
            "or internal-only arrangement.\n\n"
            "Please identify any factual inaccuracies, "
            "confidential information, requested changes or "
            "publication restrictions.\n\n"
            "No material will be published or distributed "
            "externally without the required documented approvals.\n\n"
            "Requested response date: [Insert Date]\n\n"
            "Regards,\n"
            "[Project Team]"
        ),

        "status": "DRAFT_NOT_SENT"
    }


# --------------------------------------------------
# MAIN APPROVAL AGENT
# --------------------------------------------------

def run_approval_agent():

    print("\nStarting Approval Agent...\n")

    historian = load_json(HISTORIAN_FILE)
    kpi = load_json(KPI_FILE)
    risk = load_json(RISK_FILE)
    verifier = load_json(VERIFIER_FILE)
    writer = load_json(WRITER_FILE)

    # Media is optional for generating the approval package,
    # but mandatory for clearing the publication gate.
    media = load_optional_json(MEDIA_FILE)

    verification_check = check_verification(verifier)
    risk_check = check_risks(risk)
    media_check = check_media(media)
    writer_check = check_writer(writer)

    checks = {

        "historian_output_available": bool(
            historian.get("timeline_evidence")
        ),

        "kpi_output_available": (
            kpi.get("datasets_analyzed", 0) > 0
        ),

        "verification_complete": (
            verification_check["passed"]
        ),

        "risk_review_complete": (
            risk_check["passed"]
        ),

        "media_review_complete": (
            media_check["passed"]
        ),

        "three_case_study_versions_available": (
            writer_check["passed"]
        )

    }

    blocking_reasons = [
        name
        for name, passed in checks.items()
        if not passed
    ]

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    case_studies = writer.get("case_studies", {})

    media_assets = (
        media.get("assets", [])
        if media else []
    )

    approval_items = build_approval_items()

    client_choices = build_client_approval_choices()

    # --------------------------------------------------
    # APPROVAL REQUEST
    # --------------------------------------------------

    approval_request = {

        "agent": "Approval Agent",

        "project": "Project Drishti",

        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "status": (
            "AWAITING_HUMAN_APPROVAL"
            if not blocking_reasons
            else "BLOCKED_PENDING_REQUIREMENTS"
        ),

        "release_ready_for_human_review": (
            len(blocking_reasons) == 0
        ),

        "automatically_approved": False,

        "publication_authorized": False,

        "pre_release_checks": checks,

        "verification_check": verification_check,

        "risk_check": risk_check,

        "media_check": media_check,

        "writer_check": writer_check,

        "blocking_reasons": blocking_reasons,

        # Include the exact draft text for client review.
        "case_study_versions_for_review": case_studies,

        # Include media inventory for review.
        "media_assets_for_review": media_assets,

        "client_approval_choices": client_choices,

        "client_approval_message": build_client_message(),

        "approval_items": approval_items,

        "instructions": [
            "Review the supporting project evidence.",
            "Resolve all claim verification issues.",
            "Review confidentiality, privacy and contractual restrictions.",
            "Inspect every proposed media asset.",
            "Obtain documented permission for each asset.",
            "Select named, anonymised or internal-only publication.",
            "Record reviewer names, decisions and requested changes.",
            "Do not publish until all required approvals are recorded."
        ]

    }

    # --------------------------------------------------
    # APPROVAL SHEET
    # --------------------------------------------------

    approval_sheet = {

        "project": "Project Drishti",

        "document_type": "Client Case Study Approval Sheet",

        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "approval_status": "PENDING",

        "publication_authorized": False,

        "client_approval_choices": client_choices,

        "case_study_versions": [
            "GATEKEEPER",
            "USER",
            "BUYER"
        ],

        "media_assets": [
            {
                "asset_id": asset.get("asset_id"),
                "asset_name": asset.get("asset_name"),
                "description": asset.get("description"),
                "permission_status": asset.get(
                    "permission_status",
                    "PENDING"
                )
            }
            for asset in media_assets
        ],

        "approval_items": approval_items,

        "requested_changes": [],

        "final_release_decision": {
            "decision": "NOT_AUTHORIZED",
            "reviewer": None,
            "date": None,
            "comments": None
        },

        "client_sign_off": {
            "authorized_representative": None,
            "designation": None,
            "approval_date": None,
            "documented_permission_reference": None
        }

    }

    save_json(approval_request, REQUEST_FILE)
    save_json(approval_sheet, SHEET_FILE)

    # --------------------------------------------------
    # TERMINAL SUMMARY
    # --------------------------------------------------

    print("APPROVAL AGENT COMPLETE")
    print("-" * 45)

    print("\nPRE-RELEASE CHECKS:")

    for name, passed in checks.items():

        print(
            name,
            ":",
            "PASSED" if passed else "BLOCKED"
        )

    print("\nVerification claims:",
          verification_check["total_claims"])

    print("Claims needing review:",
          verification_check["needs_review"])

    print("Pending risk findings:",
          len(risk_check["pending_findings"]))

    print("Pending media assets:",
          len(media_check["pending_assets"]))

    print("\nBlocking requirements:",
          len(blocking_reasons))

    print("Automatically approved: NO")
    print("Publication authorized: NO")

    print("\nApproval request saved to:")
    print(REQUEST_FILE)

    print("\nApproval sheet saved to:")
    print(SHEET_FILE)

    return approval_request


if __name__ == "__main__":
    run_approval_agent()
