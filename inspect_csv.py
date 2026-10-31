from pathlib import Path
import csv

file_path = Path(
    r"C:\Case Study Engine\Project_Drishti_Library\Project_Drishti_Library\04_delivery\project_tracker.csv"
)

with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)

    header = next(reader)
    expected_columns = len(header)

    print("Expected columns:", expected_columns)

    for line_number, row in enumerate(reader, start=2):
        if len(row) != expected_columns:
            print(
                f"Line {line_number}: MALFORMED "
                f"({len(row)} columns; expected {expected_columns})"
            )