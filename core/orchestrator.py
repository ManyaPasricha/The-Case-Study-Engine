
import json
import traceback
from pathlib import Path
from datetime import datetime

from core.evidence_store import build_evidence_chunks

from agents.historian import run_historian
from agents.kpi_analyst import run_kpi_analyst
from agents.risk_analyst import run_risk_analyst
from agents.verifier import run_verifier
from agents.writer import run_writer
from agents.media_agent import build_media_inventory
from agents.approval_agent import run_approval_agent


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

CURRENT_DIR = Path(__file__).resolve().parent

# Supports execution from the project root or a subfolder.
if (
    (CURRENT_DIR / "agents").exists()
    and (CURRENT_DIR / "core").exists()
):
    BASE_DIR = CURRENT_DIR
elif (
    (CURRENT_DIR.parent / "agents").exists()
    and (CURRENT_DIR.parent / "core").exists()
):
    BASE_DIR = CURRENT_DIR.parent
else:
    raise RuntimeError(
        "Could not identify Case Study Engine project root."
    )

OUTPUT_DIR = BASE_DIR / "outputs"
LOG_DIR = BASE_DIR / "logs"

PIPELINE_REPORT = OUTPUT_DIR / "pipeline_report.json"
APPROVAL_REQUEST = (
    OUTPUT_DIR / "approval_request" / "approval_request.json"
)


# --------------------------------------------------
# PIPELINE EXECUTION
# --------------------------------------------------

def run_pipeline():

    print("\n" + "=" * 60)
    print("       PROJECT DRISHTI - CASE STUDY ENGINE")
    print("=" * 60)

    start_time = datetime.now()

    pipeline_steps = [

        ("Evidence Extraction", build_evidence_chunks),

        ("Historian Agent", run_historian),

        ("KPI Analyst", run_kpi_analyst),

        ("Risk Analyst", run_risk_analyst),

        ("Verifier Agent", run_verifier),

        ("Writer Agent", run_writer),

        ("Media Agent", build_media_inventory),

        ("Approval Agent", run_approval_agent)

    ]

    step_results = []

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------
    # RUN EACH AGENT
    # --------------------------------------------------

    for step_number, (step_name, function) in enumerate(
        pipeline_steps, start=1
    ):

        print("\n" + "-" * 60)
        print(f"STEP {step_number}: {step_name}")
        print("-" * 60)

        step_start = datetime.now()

        try:

            result = function()

            duration = (
                datetime.now() - step_start
            ).total_seconds()

            step_results.append({

                "step_number": step_number,

                "step": step_name,

                "status": "SUCCESS",

                "duration_seconds": round(duration, 2)

            })

            print(f"\n{step_name}: SUCCESS")

        except Exception as error:

            duration = (
                datetime.now() - step_start
            ).total_seconds()

            step_results.append({

                "step_number": step_number,

                "step": step_name,

                "status": "FAILED",

                "duration_seconds": round(duration, 2),

                "error": str(error),

                "traceback": traceback.format_exc()

            })

            print(f"\n{step_name}: FAILED")
            print("Error:", error)

            traceback.print_exc()

            print("\nStopping pipeline.")
            break

    # --------------------------------------------------
    # CHECK FINAL APPROVAL STATUS
    # --------------------------------------------------

    approval_status = {
        "approval_request_generated": False,
        "release_ready_for_human_review": False,
        "publication_authorized": False,
        "status": "NOT_GENERATED"
    }

    if APPROVAL_REQUEST.exists():

        try:

            with open(
                APPROVAL_REQUEST,
                "r",
                encoding="utf-8"
            ) as f:

                approval_data = json.load(f)

            approval_status = {

                "approval_request_generated": True,

                "release_ready_for_human_review": (
                    approval_data.get(
                        "release_ready_for_human_review",
                        False
                    )
                ),

                "publication_authorized": (
                    approval_data.get(
                        "publication_authorized",
                        False
                    )
                ),

                "status": approval_data.get(
                    "status",
                    "UNKNOWN"
                ),

                "blocking_reasons": approval_data.get(
                    "blocking_reasons",
                    []
                )

            }

        except Exception as error:

            approval_status["status"] = "ERROR_READING_APPROVAL"
            approval_status["error"] = str(error)

    # --------------------------------------------------
    # GENERATE PIPELINE REPORT
    # --------------------------------------------------

    end_time = datetime.now()

    failed_steps = [
        item
        for item in step_results
        if item["status"] == "FAILED"
    ]

    successful_steps = [
        item
        for item in step_results
        if item["status"] == "SUCCESS"
    ]

    execution_completed = (
        len(failed_steps) == 0
        and len(successful_steps) == len(pipeline_steps)
    )

    report = {

        "project": "Project Drishti",

        "engine": "Case Study Engine",

        "started_at": start_time.isoformat(),

        "completed_at": end_time.isoformat(),

        "total_duration_seconds": round(
            (end_time - start_time).total_seconds(),
            2
        ),

        "execution_status": (
            "COMPLETED" if execution_completed else "FAILED"
        ),

        "publication_status": (
            "AUTHORIZED"
            if approval_status["publication_authorized"]
            else "NOT_AUTHORIZED"
        ),

        "steps_completed": len(successful_steps),

        "total_steps": len(pipeline_steps),

        "step_results": step_results,

        "approval_summary": approval_status

    }

    with open(
        PIPELINE_REPORT,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            indent=4,
            ensure_ascii=False
        )

    # --------------------------------------------------
    # TERMINAL SUMMARY
    # --------------------------------------------------

    print("\n" + "=" * 60)
    print("             PIPELINE EXECUTION SUMMARY")
    print("=" * 60)

    print(
        "Execution status:",
        report["execution_status"]
    )

    print(
        "Steps completed:",
        report["steps_completed"],
        "/",
        report["total_steps"]
    )

    print(
        "Total duration:",
        report["total_duration_seconds"],
        "seconds"
    )

    print("\nSTEP RESULTS:")

    for item in step_results:

        print(
            item["step"],
            "->",
            item["status"]
        )

    print("\nPUBLICATION STATUS:")

    print(
        approval_status["status"]
    )

    print(
        "Publication authorized:",
        approval_status["publication_authorized"]
    )

    if approval_status.get("blocking_reasons"):

        print("\nOutstanding requirements:")

        for reason in approval_status["blocking_reasons"]:
            print("-", reason)

    print("\nPipeline report saved to:")
    print(PIPELINE_REPORT)

    if execution_completed:

        print("\nALL PIPELINE STAGES EXECUTED SUCCESSFULLY!")

    else:

        print("\nPIPELINE STOPPED DUE TO AN ERROR.")

    return report


if __name__ == "__main__":
    run_pipeline()
