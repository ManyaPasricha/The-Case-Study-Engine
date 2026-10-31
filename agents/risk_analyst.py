
import json
import re
from pathlib import Path

from core.llm_client import ask_llm


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

EVIDENCE_FILE = BASE_DIR / "outputs" / "evidence_chunks.json"

OUTPUT_DIR = BASE_DIR / "outputs" / "exposure_report"
OUTPUT_FILE = OUTPUT_DIR / "risk_analyst_output.json"

MAX_LLM_FINDINGS = 6
BATCH_SIZE = 1
MAX_CONTENT_LENGTH = 200


# ==========================================
# RISK CATEGORIES AND KEYWORDS
# ==========================================

RISK_RULES = {

    "CONFIDENTIALITY": [
        "confidential",
        "confidentiality",
        "non-disclosure",
        "nda",
        "internal use only",
        "proprietary"
    ],

    "PRIVACY_AND_PERSONAL_DATA": [
        "face recognition",
        "facial recognition",
        "personal data",
        "biometric",
        "consent",
        "privacy",
        "identity"
    ],

    "SAFETY_AND_INCIDENTS": [
        "incident",
        "accident",
        "injury",
        "safety violation",
        "near miss",
        "hazard",
        "fatality"
    ],

    "PUBLICITY_AND_PERMISSION": [
        "publicity",
        "publication",
        "permission",
        "approval",
        "case study",
        "press release",
        "logo",
        "trademark"
    ],

    "COMMERCIAL_SENSITIVITY": [
        "invoice",
        "payment",
        "purchase order",
        "commercial",
        "pricing",
        "contract",
        "financial"
    ],

    "SECURITY_AND_ACCESS": [
        "security",
        "access control",
        "surveillance",
        "camera",
        "credential",
        "password",
        "network"
    ]
}


# ==========================================
# SAFE REVIEW RECOMMENDATIONS
# ==========================================

SAFE_REPLACEMENTS = {

    "CONFIDENTIALITY":
        "Remove confidential details or use approved descriptions.",

    "PRIVACY_AND_PERSONAL_DATA":
        "Remove identifiable personal information. Consider anonymised or aggregated descriptions after review.",

    "SAFETY_AND_INCIDENTS":
        "Avoid identifiable incident details. Use an approved high-level description.",

    "PUBLICITY_AND_PERMISSION":
        "Obtain documented permission before using names, logos, quotes or photographs.",

    "COMMERCIAL_SENSITIVITY":
        "Remove invoice values, payment details, pricing and commercial terms unless approved.",

    "SECURITY_AND_ACCESS":
        "Remove credentials, camera identifiers, access details and sensitive infrastructure information."
}


# ==========================================
# LOAD EVIDENCE
# ==========================================

def load_evidence():

    if not EVIDENCE_FILE.exists():
        raise FileNotFoundError(
            "Evidence store not found. Run evidence_store.py first."
        )

    with open(EVIDENCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ==========================================
# PYTHON KEYWORD SCREENING
# ==========================================

def find_risk_categories(text):

    text_lower = text.lower()

    matched_categories = []

    for category, keywords in RISK_RULES.items():

        matched_keywords = [
            keyword
            for keyword in keywords
            if re.search(
                r"(?<!\w)" + re.escape(keyword) + r"(?!\w)",
                text_lower
            )
        ]

        if matched_keywords:

            matched_categories.append({
                "category": category,
                "matched_keywords": matched_keywords
            })

    return matched_categories


def assess_evidence(evidence):

    risk_findings = []

    for item in evidence:

        content = item.get("content", "")

        if not isinstance(content, str):
            continue

        matches = find_risk_categories(content)

        for match in matches:

            category = match["category"]

            risk_findings.append({

                "finding_id": f"RISK-{len(risk_findings) + 1:04d}",

                "category": category,

                "source_file": item.get(
                    "source_file", "NOT PROVIDED"
                ),

                "source_path": item.get(
                    "source_path", "NOT PROVIDED"
                ),

                "evidence_id": item.get("evidence_id"),

                "matched_keywords": match["matched_keywords"],

                "review_recommendation": SAFE_REPLACEMENTS[category],

                "severity": "NOT_ASSESSED",

                "approval_status": "NOT_VERIFIED",

                "publication_status": "HOLD_PENDING_REVIEW",

                "llm_assessment": "NOT_ANALYSED",

                "llm_risk_explanation": "NOT PROVIDED",

                "llm_risk_level": "UNDETERMINED",

                "llm_safer_wording": "NOT PROVIDED",

                "llm_review_required": True
            })

    return risk_findings


# ==========================================
# SELECT REPRESENTATIVE FINDINGS
# ==========================================

def select_findings(findings):

    selected = []
    selected_categories = set()

    # First select one finding from each category.
    for finding in findings:

        category = finding["category"]

        if category not in selected_categories:

            selected.append(finding)
            selected_categories.add(category)

        if len(selected) >= MAX_LLM_FINDINGS:
            break

    return selected


# ==========================================
# LLM RISK ANALYSIS
# ==========================================

def analyse_risks_with_llm(findings, evidence):

    print(
        "\nStarting local LLM risk interpretation...",
        flush=True
    )

    if not findings:
        return findings

    evidence_lookup = {
        item.get("evidence_id"): item
        for item in evidence
    }

    selected = select_findings(findings)

    completed_ids = set()

    for start in range(0, len(selected), BATCH_SIZE):

        batch = selected[start:start + BATCH_SIZE]

        batch_number = (start // BATCH_SIZE) + 1

        print(
            f"\nAnalysing risk batch {batch_number}...",
            flush=True
        )

        llm_input = []

        for slot, finding in enumerate(batch, start=1):

            source = evidence_lookup.get(
                finding["evidence_id"], {}
            )

            llm_input.append({

                "slot": slot,

                "finding_id": finding["finding_id"],

                "category": finding["category"],

                "matched_keywords": finding["matched_keywords"],

                "evidence_id": finding["evidence_id"],

                "context": source.get(
                    "content", ""
                )[:MAX_CONTENT_LENGTH]
            })

        system_prompt = """
You are a cautious Risk Analyst Agent.

Analyse the supplied potential exposure findings.

STRICT RULES:

1. Use only supplied evidence.
2. Never invent contractual restrictions or permissions.
3. Explain why a finding may create exposure.
4. Distinguish potential risks from confirmed violations.
5. Suggest safer wording or removal.
6. Never approve publication.
7. Return exactly one assessment for each supplied finding.
8. Copy each slot number and finding ID exactly.
9. Keep answers concise.
10. Return valid JSON only.

Return this structure:

{
    "assessments": [
        {
            "slot": 1,
            "finding_id": "RISK-0001",
            "risk_explanation": "",
            "risk_level": "UNDETERMINED",
            "safer_wording": ""
        }
    ]
}
"""

        user_prompt = (
            "Analyse these potential exposure findings:\n\n"
            + json.dumps(llm_input, ensure_ascii=False)
        )

        try:

            response = ask_llm(
                system_prompt,
                user_prompt
            )

            assessments = response.get(
                "assessments", []
            )

            if not isinstance(assessments, list):
                raise ValueError(
                    "Invalid assessments structure."
                )

            print(
                "Assessments returned:",
                len(assessments),
                flush=True
            )

            for assessment in assessments:

                if not isinstance(assessment, dict):
                    continue

                slot = assessment.get("slot")

                if not isinstance(slot, int):
                    continue

                if slot < 1 or slot > len(batch):
                    continue

                finding = batch[slot - 1]

                # Require exact ID matching.
                if assessment.get("finding_id") != finding["finding_id"]:
                    continue

                finding["llm_assessment"] = "COMPLETED"

                finding["llm_risk_explanation"] = str(
                    assessment.get(
                        "risk_explanation",
                        "NOT PROVIDED"
                    )
                )

                finding["llm_risk_level"] = str(
                    assessment.get(
                        "risk_level",
                        "UNDETERMINED"
                    )
                )

                finding["llm_safer_wording"] = str(
                    assessment.get(
                        "safer_wording",
                        "NOT PROVIDED"
                    )
                )

                completed_ids.add(
                    finding["finding_id"]
                )

            print(
                f"Batch {batch_number} completed. "
                f"Total interpreted: {len(completed_ids)}",
                flush=True
            )

        except Exception as error:

            print(
                f"Batch {batch_number} failed: {error}",
                flush=True
            )

    # Preserve the review status of all other findings.
    for finding in findings:

        if finding["finding_id"] not in completed_ids:

            finding["llm_assessment"] = (
                "NOT_ANALYSED_REQUIRES_REVIEW"
            )

            finding["llm_review_required"] = True

    return findings


# ==========================================
# RISK SUMMARY
# ==========================================

def summarize_risks(findings):

    summary = {}

    for finding in findings:

        category = finding["category"]

        summary[category] = (
            summary.get(category, 0) + 1
        )

    return summary


# ==========================================
# RUN RISK ANALYST
# ==========================================

def run_risk_analyst():

    print(
        "\nStarting LLM-assisted Risk Analyst Agent...\n",
        flush=True
    )

    evidence = load_evidence()

    # Stage 1: Python keyword screening.
    findings = assess_evidence(evidence)

    print(
        "Evidence chunks reviewed:",
        len(evidence),
        flush=True
    )

    print(
        "Potential findings identified:",
        len(findings),
        flush=True
    )

    # Stage 2: Local Qwen analysis.
    findings = analyse_risks_with_llm(
        findings,
        evidence
    )

    summary = summarize_risks(findings)

    llm_completed = sum(
        1
        for item in findings
        if item["llm_assessment"] == "COMPLETED"
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output = {

        "agent": "LLM-Assisted Risk Analyst",

        "project": "Project Drishti",

        "status": "PRELIMINARY_RISK_SCREENING_REQUIRES_HUMAN_REVIEW",

        "model": "qwen2.5:3b",

        "total_evidence_chunks_reviewed": len(evidence),

        "total_potential_risk_findings": len(findings),

        "llm_findings_analysed": llm_completed,

        "llm_findings_not_analysed": (
            len(findings) - llm_completed
        ),

        "risk_summary": summary,

        "risk_findings": findings,

        "limitations": [

            "Keyword matches indicate potential risks, not confirmed violations.",

            "LLM interpretations are preliminary and require human review.",

            "Only six representative findings receive LLM analysis.",

            "Absence of a keyword does not establish that content is safe.",

            "Contractual restrictions require review of the actual contract.",

            "Publication permissions require documentary verification.",

            "Severity and legal determinations are not automatically approved.",

            "No content is approved for external publication.",

            "Human review is mandatory before release."
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

    print("\nRISK ANALYST COMPLETE")
    print("-" * 40)

    print("Evidence chunks reviewed:", len(evidence))
    print("Potential findings:", len(findings))
    print("LLM findings analysed:", llm_completed)
    print(
        "LLM findings not analysed:",
        len(findings) - llm_completed
    )

    print("\nRISK CATEGORY SUMMARY:")

    for category, count in summary.items():
        print(f"{category}: {count}")

    print("\nOutput saved to:")
    print(OUTPUT_FILE)

    return output


if __name__ == "__main__":
    run_risk_analyst()


