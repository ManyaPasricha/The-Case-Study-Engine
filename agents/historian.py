import json
from pathlib import Path
from collections import defaultdict

from core.llm_client import ask_llm, evidence_grounded_prompt


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

EVIDENCE_FILE = BASE_DIR / "outputs" / "evidence_chunks.json"
OUTPUT_DIR = BASE_DIR / "outputs" / "story_spine"
OUTPUT_FILE = OUTPUT_DIR / "historian_output.json"

BATCH_SIZE = 1
MAX_CONTENT_LENGTH = 1000

# DEMO SETTINGS
# True  = process only the first 12 batches
# False = process all available batches

DEMO_MODE = True
DEMO_BATCH_LIMIT = 12


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
# SELECT RELEVANT EVIDENCE
# ==========================================

def identify_timeline_evidence(evidence):

    relevant_categories = {
        "PROJECT_SCOPE",
        "MEETING",
        "EMAIL",
        "DELIVERY",
        "COMMERCIAL_OR_CONTRACT",
        "TECHNICAL"
    }

    timeline_evidence = []

    for item in evidence:

        if item.get("document_type") in relevant_categories:

            timeline_evidence.append({
                "evidence_id": item.get("evidence_id"),
                "source_file": item.get("source_file"),
                "source_path": item.get("source_path"),
                "document_type": item.get("document_type"),
                "content": item.get("content", ""),
                "verification_status": "UNVERIFIED"
            })

    return timeline_evidence


# ==========================================
# GROUP EVIDENCE BY SOURCE
# ==========================================

def group_by_source(evidence):

    grouped = defaultdict(list)

    for item in evidence:
        grouped[item["source_path"]].append(item)

    return dict(grouped)


# ==========================================
# PREPARE BATCHES
# ==========================================

def create_batches(evidence):

    return [
        evidence[i:i + BATCH_SIZE]
        for i in range(0, len(evidence), BATCH_SIZE)
    ]


# ==========================================
# LLM HISTORIAN
# ==========================================

def analyse_evidence_batch(batch, batch_number):

    evidence_text = []

    valid_ids = {
        item["evidence_id"]
        for item in batch
        if item.get("evidence_id")
    }

    for item in batch:

        evidence_text.append({
            "evidence_id": item["evidence_id"],
            "source_file": item["source_file"],
            "document_type": item["document_type"],
            "content": item.get("content", "")[:MAX_CONTENT_LENGTH]
        })

    system_prompt = evidence_grounded_prompt() + """

    You are the Historian Agent of a project case study engine.

    Your responsibility is to reconstruct the documented history
    of a project from emails, meetings, contracts, technical
    records and delivery documents.

    STRICT RULES:

    1. Extract only events explicitly supported by the supplied evidence.
    2. Never invent dates, people, decisions or milestones.
    3. Do not assume that a proposed activity was completed.
    4. Distinguish planned, proposed, approved and completed events.
    5. If a date is unclear, use NOT PROVIDED.
    6. Preserve disagreements between sources.
    7. Every event must include one or more supplied evidence IDs.
    8. Never create or modify evidence IDs.
    9. Do not turn expected benefits into actual results.
    10. Return valid JSON only.
    11. If no event can be extracted, return an empty events array.

    Return exactly this structure:

    {
        "events": [
            {
                "event": "",
                "date": "",
                "event_type": "",
                "description": "",
                "people_or_roles": [],
                "decision": "",
                "status": "",
                "evidence_ids": [],
                "uncertainty": ""
            }
        ],
        "uncertainties": []
    }
    """

    user_prompt = f"""
    Analyse evidence batch {batch_number}.

    Extract important project events supported by the evidence.

    Evidence:

    {json.dumps(evidence_text, ensure_ascii=False)}

    Return only the requested JSON structure.
    """

    response = ask_llm(
        system_prompt,
        user_prompt
    )

    events = response.get("events", [])

    if not isinstance(events, list):
        raise ValueError("Historian response has an invalid events field.")

    uncertainties = response.get("uncertainties", [])

    if not isinstance(uncertainties, list):
        uncertainties = [
            "The model returned uncertainties in an unexpected format."
        ]

    validated_events = []

    for event in events:

        if not isinstance(event, dict):
            continue

        returned_ids = event.get("evidence_ids", [])

        if not isinstance(returned_ids, list):
            continue

        valid_event_ids = [
            evidence_id
            for evidence_id in returned_ids
            if isinstance(evidence_id, str)
            and evidence_id in valid_ids
        ]

        # Reject unsupported or unreferenced events.
        if not valid_event_ids:
            continue

        event["evidence_ids"] = valid_event_ids
        event["verification_status"] = "NEEDS_REVIEW"
        event["historian_batch"] = batch_number

        validated_events.append(event)

    return {
        "events": validated_events,
        "uncertainties": uncertainties
    }


# ==========================================
# RUN HISTORIAN AGENT
# ==========================================

def run_historian():

    print("\nStarting LLM-powered Historian Agent...\n", flush=True)

    evidence = load_evidence()

    timeline_evidence = identify_timeline_evidence(evidence)

    grouped_evidence = group_by_source(timeline_evidence)

    # Create all batches first.
    all_batches = create_batches(timeline_evidence)

    total_batches_available = len(all_batches)

    # Select batches based on demo setting.
    if DEMO_MODE:
        batches = all_batches[:DEMO_BATCH_LIMIT]
    else:
        batches = all_batches

    all_events = []
    all_uncertainties = []

    processed_evidence_ids = set()
    failed_batches = []

    batches_attempted = 0

    print("Total evidence chunks:", len(evidence), flush=True)
    print("Relevant evidence chunks:", len(timeline_evidence), flush=True)
    print("Source documents:", len(grouped_evidence), flush=True)
    print("Total batches available:", total_batches_available, flush=True)
    print("Batches selected for this run:", len(batches), flush=True)
    print("Demo mode:", DEMO_MODE, flush=True)

    # ======================================
    # PROCESS SELECTED BATCHES
    # ======================================

    for index, batch in enumerate(batches, start=1):

        print(
            f"\nAnalysing batch {index}/{len(batches)}...",
            flush=True
        )

        try:

            batches_attempted += 1

            result = analyse_evidence_batch(batch, index)

            all_events.extend(result["events"])
            all_uncertainties.extend(result["uncertainties"])

            for item in batch:
                processed_evidence_ids.add(item["evidence_id"])

            print(
                "Events extracted:",
                len(result["events"]),
                flush=True
            )

        except KeyboardInterrupt:
            print("\nHistorian interrupted by user.", flush=True)
            raise

        except Exception as error:

            print(
                f"Batch {index} failed: {error}",
                flush=True
            )

            failed_batches.append(index)

            all_uncertainties.append({
                "batch": index,
                "reason": str(error),
                "status": "BATCH_REQUIRES_REVIEW"
            })

    # ======================================
    # IDENTIFY UNPROCESSED EVIDENCE
    # ======================================

    unprocessed_evidence = [
        item["evidence_id"]
        for item in timeline_evidence
        if item["evidence_id"] not in processed_evidence_ids
    ]

    # ======================================
    # SORT EVENTS
    # ======================================

    all_events.sort(
        key=lambda event: (
            event.get("date") in ("", "NOT PROVIDED", None),
            str(event.get("date", ""))
        )
    )

    # ======================================
    # SAVE OUTPUT
    # ======================================

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    result = {

        "agent": "LLM-Powered Historian Agent",

        "project": "Project Drishti",

        "status": (
            "LLM_ANALYSIS_REQUIRES_VERIFICATION"
            if not unprocessed_evidence
            else "PARTIAL_ANALYSIS_REQUIRES_VERIFICATION"
        ),

        "model": "qwen2.5:3b",

        "demo_mode": DEMO_MODE,

        "total_evidence_chunks": len(evidence),

        "relevant_evidence_chunks": len(timeline_evidence),

        "source_documents": len(grouped_evidence),

        "total_batches": total_batches_available,

        "batches_selected": len(batches),

        "batches_attempted": batches_attempted,

        "successful_batches": batches_attempted - len(failed_batches),

        "failed_batches": failed_batches,

        "total_events_extracted": len(all_events),

        "timeline_events": all_events,

        # Retained for compatibility with existing agents.
        "timeline_evidence": timeline_evidence,

        "evidence_by_source": grouped_evidence,

        "processed_evidence_ids": sorted(processed_evidence_ids),

        "unprocessed_evidence_ids": unprocessed_evidence,

        "uncertainties": all_uncertainties,

        "limitations": [
            "Events are extracted using a local LLM and require verification.",
            "Evidence IDs are checked against the original evidence store.",
            "A valid evidence ID does not independently prove an event.",
            "Conflicting sources require human review.",
            "Dates are sorted as text and require chronological validation.",
            "Evidence content is limited to the first 1000 characters per chunk.",
            "Demo mode processes only the first 12 batches; skipped evidence remains unprocessed.",
            "No event is automatically approved for publication."
        ]
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

        json.dump(
            result,
            f,
            indent=4,
            ensure_ascii=False
        )

    # ======================================
    # SUMMARY
    # ======================================

    print("\nHISTORIAN AGENT COMPLETE", flush=True)
    print("-" * 45)

    print("Evidence chunks:", len(evidence))
    print("Relevant chunks:", len(timeline_evidence))
    print("Source documents:", len(grouped_evidence))
    print("Total batches available:", total_batches_available)
    print("Batches selected:", len(batches))
    print("Batches attempted:", batches_attempted)
    print("Successful batches:", batches_attempted - len(failed_batches))
    print("Failed batches:", len(failed_batches))
    print("Timeline events extracted:", len(all_events))
    print("Unprocessed evidence:", len(unprocessed_evidence))
    print("Uncertainties:", len(all_uncertainties))

    print("\nOutput saved to:", flush=True)
    print(OUTPUT_FILE, flush=True)

    return result


if __name__ == "__main__":
    run_historian()