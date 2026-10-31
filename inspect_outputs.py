import json
from pathlib import Path

files = [
    "outputs/verification_report.json",
    "outputs/story_spine/historian_output.json",
    "outputs/results_sheet/kpi_analyst_output.json",
    "outputs/exposure_report/risk_analyst_output.json",
    "outputs/case_study/writer_output.json",
    "outputs/media_pack/media_inventory.json",
    "outputs/approval_request/approval_request.json"
]

for file in files:
    path = Path(file)

    print(f"\n{'=' * 50}")
    print(file)

    if not path.exists():
        print("FILE NOT FOUND")
        continue

    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            print("Top-level keys:", list(data.keys()))
        else:
            print("Data type:", type(data).__name__)

    except Exception as e:
        print("Error:", e)