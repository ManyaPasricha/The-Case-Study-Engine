
import json
import re
from pathlib import Path

import streamlit as st
import pandas as pd

# ==========================================================
# THE CASE STUDY ENGINE
# Local Streamlit Dashboard
# Run: streamlit run app.py
# ==========================================================

st.set_page_config(
    page_title="The Case Study Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"

# -------------------- CUSTOM STYLING --------------------

st.markdown("""
<style>
.block-container {
    padding-top: 1.5rem;
}
.main-title {
    font-size: 2.2rem;
    font-weight: 800;
    letter-spacing: -1px;
}
.subtitle {
    color: #9299a8;
    font-size: 0.85rem;
    letter-spacing: 2px;
}
div[data-testid="stMetric"] {
    background: rgba(128,128,128,0.08);
    border: 1px solid rgba(128,128,128,0.2);
    padding: 16px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)


# -------------------- FILE LOADING --------------------

def find_file(patterns):
    for pattern in patterns:
        matches = list(OUTPUTS.rglob(pattern)) if OUTPUTS.exists() else []
        if matches:
            return max(matches, key=lambda p: p.stat().st_mtime)
    return None


def load_json(patterns, default=None):
    path = find_file(patterns)

    if not path:
        return default if default is not None else {}, None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), path
    except Exception as e:
        return {"error": str(e)}, path


def first_value(data, keys, default="Not available"):
    if not isinstance(data, dict):
        return default

    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return value

    return default


def get_list(data, keys):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in keys:
            if isinstance(data.get(key), list):
                return data[key]

    return []


def safe_text(value):
    if value is None:
        return "Not available"

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    return str(value)


# Basic display-only masking. This is not a complete privacy review.
def mask_sensitive(value):
    value = safe_text(value)

    value = re.sub(
        r'\b[A-Z]{2,}[A-Z0-9/-]*\d{3,}[A-Z0-9/-]*\b',
        "[REDACTED ID]",
        value
    )

    names = [
        "Arvind Rao",
        "Rajiv Bhandari",
        "Aarav Malhotra",
        "Ardent Cement Works Limited",
        "Ardent Bhadrapur",
        "PredCo",
        "ViewOS"
    ]

    for name in names:
        value = re.sub(
            re.escape(name),
            "[REDACTED]",
            value,
            flags=re.IGNORECASE
        )

    return value


# -------------------- LOAD AGENT OUTPUTS --------------------

historian, historian_path = load_json(["historian_output.json"])
kpi, kpi_path = load_json(["kpi_analyst_output.json"])
risk, risk_path = load_json(["risk_analyst_output.json", "*risk*.json"])
verification, verification_path = load_json(["verification_report.json"])
writer, writer_path = load_json(["writer_output.json"])
approval, approval_path = load_json(["approval_output.json", "*approval*.json"])
media, media_path = load_json(["media_output.json", "*media*.json"])

events = get_list(historian, ["timeline_events", "events"])
metrics = get_list(kpi, ["candidate_metrics", "metrics"])

case_studies = (
    writer.get("case_studies", {})
    if isinstance(writer, dict) else {}
)

risk_findings = get_list(
    risk,
    ["findings", "risk_findings", "potential_findings", "results"]
)

if not risk_findings and isinstance(risk, dict):
    for value in risk.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            risk_findings = value
            break

media_assets = get_list(
    media,
    ["assets", "media_assets", "generated_assets"]
)


# -------------------- SIDEBAR NAVIGATION --------------------

st.sidebar.title("THE CASE STUDY ENGINE")
st.sidebar.caption("Evidence Intelligence Platform")
st.sidebar.divider()

page = st.sidebar.radio(
    "NAVIGATION",
    [
        "Overview",
        "Project Timeline",
        "KPI Explorer",
        "Risk & Exposure",
        "Evidence Verification",
        "Case Studies",
        "Approval & Media",
        "System Files"
    ]
)

st.sidebar.divider()
st.sidebar.caption("PROJECT DRISHTI")
st.sidebar.caption("Local dashboard build")
st.sidebar.caption("No external API calls")


# -------------------- MAIN HEADER --------------------

st.markdown(
    '<div class="main-title">THE CASE STUDY ENGINE</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">PROJECT DRISHTI / EVIDENCE-TO-CASE-STUDY WORKSPACE</div>',
    unsafe_allow_html=True
)

st.write("")


# ==========================================================
# 1. OVERVIEW
# ==========================================================

if page == "Overview":

    st.subheader("Project Intelligence Overview")

    st.error(
        "PUBLICATION STATUS: HOLD — HUMAN VERIFICATION AND CLIENT APPROVAL REQUIRED"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Evidence Chunks", 194)
    c2.metric("Timeline Events", len(events))
    c3.metric("Candidate Metrics", len(metrics))
    c4.metric("Case Study Drafts", len(case_studies))

    st.divider()

    left, right = st.columns([1.2, 1])

    with left:

        st.markdown("### Agent Pipeline Status")

        pipeline = [
            ["Evidence Extraction", "Completed"],
            ["Historian Agent", "Completed" if historian_path else "Missing"],
            ["KPI Analyst", "Completed" if kpi_path else "Missing"],
            ["Risk Analyst", "Loaded" if risk_path else "Missing"],
            ["Verifier Agent", "Completed" if verification_path else "Missing"],
            ["Writer Agent", "3 drafts generated" if case_studies else "Missing"],
            ["Media Agent", "Loaded" if media_path else "Missing"],
            ["Approval Agent", "Loaded" if approval_path else "Missing"]
        ]

        st.dataframe(
            pd.DataFrame(pipeline, columns=["Agent", "Status"]),
            use_container_width=True,
            hide_index=True
        )

    with right:

        st.markdown("### Attention Required")

        st.warning("Candidate metrics require validation.")
        st.warning("Timeline claims require source verification.")
        st.warning("Confidentiality and publicity permissions require review.")
        st.info("External publication is currently blocked.")

    st.divider()

    st.markdown("### Project Summary")

    st.write("""
    The Case Study Engine converts unstructured project records into
    structured evidence, project timelines, candidate KPIs, risk findings,
    verification reports and audience-specific case-study drafts.

    It supports three audiences:

    - Gatekeepers: Governance, safety and compliance.
    - Users: Operational workflows and usability.
    - Buyers: Business value and solution fit.
    """)


# ==========================================================
# 2. PROJECT TIMELINE
# ==========================================================

elif page == "Project Timeline":

    st.subheader("Project Timeline")

    st.caption(
        "Extracted historical events. Dates and descriptions require human review."
    )

    rows = []

    for i, event in enumerate(events, 1):

        if isinstance(event, dict):

            rows.append({
                "No.": i,
                "Date": safe_text(
                    first_value(event, ["date", "event_date"])
                ),
                "Event": mask_sensitive(first_value(
                    event,
                    ["description", "event", "claim", "summary", "details", "text"]
                )),
                "Type": safe_text(
                    first_value(event, ["event_type", "type"])
                ),
                "Evidence IDs": safe_text(
                    event.get("evidence_ids", [])
                ),
                "Review Status": "Needs Human Review"
            })

        else:

            rows.append({
                "No.": i,
                "Date": "Not established",
                "Event": mask_sensitive(event),
                "Type": "Project Event",
                "Evidence IDs": "Not available",
                "Review Status": "Needs Human Review"
            })

    if rows:

        df = pd.DataFrame(rows)

        search = st.text_input(
            "Search Timeline",
            placeholder="Search events, dates or evidence IDs"
        )

        if search:
            df = df[
                df.astype(str).apply(
                    lambda col: col.str.contains(
                        search,
                        case=False,
                        na=False
                    )
                ).any(axis=1)
            ]

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "Download Timeline CSV",
            df.to_csv(index=False).encode("utf-8"),
            "project_timeline.csv",
            "text/csv"
        )

    else:
        st.info("No timeline events found.")


# ==========================================================
# 3. KPI EXPLORER
# ==========================================================

elif page == "KPI Explorer":

    st.subheader("KPI & Metrics Explorer")

    st.warning(
        "These are candidate metrics, NOT verified business outcomes."
    )

    rows = []

    for metric in metrics:

        if not isinstance(metric, dict):
            continue

        rows.append({

            "Metric": safe_text(first_value(
                metric,
                ["metric_name", "name", "metric"]
            )),

            "Candidate Value": safe_text(first_value(
                metric,
                ["final_value", "value"]
            )),

            "Baseline": safe_text(metric.get("baseline")),

            "Unit": safe_text(metric.get("unit")),

            "Measurement Window": safe_text(
                metric.get("measurement_window")
            ),

            "Methodology": safe_text(
                metric.get("methodology")
            ),

            "Source": safe_text(first_value(
                metric,
                ["source_file", "filename"]
            )),

            "Status": "Needs Validation"

        })

    if rows:

        df = pd.DataFrame(rows)

        st.metric("Candidate Metrics Identified", len(df))

        search = st.text_input(
            "Search Metrics",
            placeholder="Search KPI name or source"
        )

        if search:
            df = df[
                df.astype(str).apply(
                    lambda col: col.str.contains(
                        search,
                        case=False,
                        na=False
                    )
                ).any(axis=1)
            ]

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "Download KPI Inventory",
            df.to_csv(index=False).encode("utf-8"),
            "candidate_kpi_inventory.csv",
            "text/csv"
        )

    else:
        st.info("KPI output not found.")

    st.info(
        "The current extracted KPI information does not establish "
        "verified baselines, final values or calculation methods. "
        "Charts are intentionally withheld until values are validated."
    )


# ==========================================================
# 4. RISK & EXPOSURE
# ==========================================================

elif page == "Risk & Exposure":

    st.subheader("Risk & Exposure Analysis")

    st.caption(
        "Potential findings are screening flags, not final legal determinations."
    )

    if risk_findings:

        rows = []
        categories = {}

        for item in risk_findings:

            if not isinstance(item, dict):
                continue

            category = safe_text(first_value(
                item,
                ["category", "risk_category", "type"],
                "Uncategorised"
            ))

            categories[category] = categories.get(category, 0) + 1

            rows.append({

                "Category": category,

                "Finding": mask_sensitive(first_value(
                    item,
                    ["finding", "description", "text", "matched_text", "risk"]
                )),

                "Source": safe_text(first_value(
                    item,
                    ["source_file", "filename"]
                )),

                "Severity": safe_text(first_value(
                    item,
                    ["severity", "level"]
                )),

                "Status": "Human Review Required"

            })

        cols = st.columns(min(4, max(1, len(categories))))

        for col, (category, count) in zip(
            cols,
            list(categories.items())[:4]
        ):
            col.metric(category.replace("_", " ").title(), count)

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("Risk findings could not be loaded.")
        st.caption(f"Detected file: {risk_path}")

    st.error(
        "Do not publish externally until confidentiality, privacy "
        "and client publicity risks have been reviewed."
    )


# ==========================================================
# 5. EVIDENCE VERIFICATION
# ==========================================================

elif page == "Evidence Verification":

    st.subheader("Evidence Verification")

    st.caption(
        "Rule-based checks verify reference integrity, not semantic truth."
    )

    summary = {}

    if isinstance(verification, dict):

        summary = verification.get(
            "summary",
            verification.get("verification_summary", {})
        )

        if not isinstance(summary, dict):
            summary = {}

    if summary:

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Total Claims",
            safe_text(first_value(
                summary,
                ["total_claims", "claims_checked", "total"]
            ))
        )

        c2.metric(
            "Valid References",
            safe_text(first_value(
                summary,
                ["valid_evidence_references", "valid_references"]
            ))
        )

        c3.metric(
            "Invalid References",
            safe_text(first_value(
                summary,
                ["invalid_evidence_references", "invalid_references"]
            ))
        )

        c4.metric(
            "Needs Review",
            safe_text(first_value(
                summary,
                ["claims_needing_review", "needs_review"]
            ))
        )

    if verification:

        with st.expander("View Complete Verification Report"):
            st.json(verification)

    else:

        st.info("Verification report not found.")

    st.warning(
        "A valid evidence ID does not automatically prove that "
        "a claim is accurate. Human review is still necessary."
    )


# ==========================================================
# 6. CASE STUDIES
# ==========================================================

elif page == "Case Studies":

    st.subheader("Audience-Specific Case Studies")

    st.caption(
        "Three preliminary drafts generated from extracted project records."
    )

    if case_studies:

        audience = st.selectbox(
            "Select Target Audience",
            list(case_studies.keys())
        )

        draft = case_studies[audience]

        st.markdown(
            f"## {mask_sensitive(draft.get('title', 'Case Study'))}"
        )

        st.error(
            f"Draft Status: {draft.get('generation_status', 'Draft')} "
            "| Publication: HOLD"
        )

        sections = [

            ("Executive Summary", "executive_summary"),

            ("Problem", "problem"),

            ("Objectives", "objectives"),

            ("Approach", "approach"),

            ("Implementation", "implementation"),

            ("Challenges", "challenges"),

            ("Results and Impact", "results_and_impact"),

            ("Limitations", "limitations"),

            ("Conclusion", "conclusion"),

            ("Missing Information", "missing_information")

        ]

        for heading, key in sections:

            with st.expander(heading, expanded=key == "executive_summary"):

                value = draft.get(key, "Not available")

                if isinstance(value, list):

                    for item in value:
                        st.write("• " + mask_sensitive(item))

                else:

                    st.write(mask_sensitive(value))

        with st.expander("Claims Requiring Verification"):

            claims = draft.get("key_claims", [])

            if claims:

                for claim in claims:

                    if isinstance(claim, dict):

                        st.write(
                            "• " + mask_sensitive(
                                claim.get("claim", "")
                            )
                        )

                        st.caption(
                            "Evidence IDs: " +
                            safe_text(claim.get("evidence_ids", []))
                        )

            else:

                st.info("No structured claims available.")

        st.download_button(
            "Download Case Study JSON",
            json.dumps(draft, indent=2, ensure_ascii=False),
            f"{audience.lower()}_case_study.json",
            "application/json"
        )

    else:

        st.info("Writer output not found. Run the Writer Agent first.")

    st.warning(
        "Review and anonymise the case study before sharing it externally."
    )


# ==========================================================
# 7. APPROVAL & MEDIA
# ==========================================================

elif page == "Approval & Media":

    st.subheader("Approval & Media Management")

    c1, c2 = st.columns(2)

    c1.metric(
        "Approval Agent",
        "Loaded" if approval_path else "Not Found"
    )

    c2.metric(
        "Media Agent",
        "Loaded" if media_path else "Not Found"
    )

    st.divider()

    st.error("PUBLICATION GATE: HOLD — DO NOT PUBLISH")

    st.write("""
    Publication requires:

    - Verification of all factual claims.
    - Confidentiality and exposure review.
    - Review of generated media assets.
    - Approval from authorised client approvers.
    """)

    if approval:

        with st.expander("Approval Agent Report"):
            st.json(approval)

    if media_assets:

        st.markdown("### Media Assets")

        for i, asset in enumerate(media_assets, 1):

            if isinstance(asset, dict):

                st.markdown(
                    f"**Asset {i}:** " +
                    safe_text(first_value(
                        asset,
                        ["title", "name", "asset_type"]
                    ))
                )

                st.write(mask_sensitive(first_value(
                    asset,
                    ["description", "purpose", "status"]
                )))

                st.caption(
                    "Review: " + safe_text(first_value(
                        asset,
                        ["status", "review_status"]
                    ))
                )

            else:

                st.write(f"Asset {i}: {safe_text(asset)}")

    else:

        st.info(
            "Media asset output not found. Check the Media Agent output."
        )


# ==========================================================
# 8. SYSTEM FILES
# ==========================================================

elif page == "System Files":

    st.subheader("Agent Output Files")

    files = [

        ["Historian", historian_path],

        ["KPI Analyst", kpi_path],

        ["Risk Analyst", risk_path],

        ["Verifier", verification_path],

        ["Writer", writer_path],

        ["Approval", approval_path],

        ["Media", media_path]

    ]

    rows = []

    for agent, path in files:

        rows.append({

            "Agent": agent,

            "File": (
                str(path.relative_to(ROOT))
                if path else "Not found"
            ),

            "Status": "Loaded" if path else "Missing"

        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True
    )

    st.info(
        "The dashboard searches the outputs folder for JSON files. "
        "Keep this dashboard local and do not expose confidential source records."
    )


# -------------------- FOOTER --------------------

st.sidebar.divider()
st.sidebar.caption("THE CASE STUDY ENGINE")
st.sidebar.caption("Local Review Build")
