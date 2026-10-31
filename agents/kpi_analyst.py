import csv
import json
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

LIBRARY_DIR = (
    BASE_DIR
    / "Project_Drishti_Library"
    / "Project_Drishti_Library"
)

OUTPUT_DIR = BASE_DIR / "outputs" / "results_sheet"
OUTPUT_FILE = OUTPUT_DIR / "kpi_analyst_output.json"


def load_csv_safely(file_path):
    """
    Read CSV without silently discarding malformed records.
    Valid rows are retained; malformed rows are flagged.
    """

    valid_rows = []
    flagged_rows = []

    with open(
        file_path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.reader(f)
        headers = next(reader, None)

        if not headers:
            return pd.DataFrame(), []

        for line_number, row in enumerate(reader, start=2):

            if len(row) == len(headers):
                valid_rows.append(row)

            else:
                flagged_rows.append({
                    "line_number": line_number,
                    "expected_columns": len(headers),
                    "actual_columns": len(row),
                    "status": "NEEDS_MANUAL_REVIEW"
                })

    df = pd.DataFrame(valid_rows, columns=headers)

    return df, flagged_rows


def detect_date_columns(df):
    """Identify columns that appear to contain dates."""

    date_columns = []

    for column in df.columns:

        name = column.lower()

        if any(word in name for word in [
            "date", "time", "month", "week", "period"
        ]):

            parsed = pd.to_datetime(
                df[column],
                errors="coerce",
                format="mixed"
            )

            valid_dates = parsed.dropna()

            if not valid_dates.empty:

                date_columns.append({
                    "column": column,
                    "minimum_date": str(
                        valid_dates.min().date()
                    ),
                    "maximum_date": str(
                        valid_dates.max().date()
                    ),
                    "valid_date_records": int(
                        valid_dates.count()
                    )
                })

    return date_columns


def detect_numeric_columns(df):
    """Identify columns containing measurable numeric values."""

    numeric_columns = []

    for column in df.columns:

        name = column.lower()

        # Avoid treating identifiers as measurable KPIs
        if any(word in name for word in [
            "id", "code", "phone", "pincode"
        ]):
            continue

        converted = pd.to_numeric(
            df[column],
            errors="coerce"
        )

        valid_count = int(converted.notna().sum())

        if valid_count == 0:
            continue

        numeric_ratio = valid_count / max(len(df), 1)

        if numeric_ratio < 0.80:
            continue

        numeric_columns.append({
            "column": column,
            "values": converted
        })

    return numeric_columns


def analyze_dataset(file_path):
    """Profile one dataset and identify candidate metrics."""

    df, flagged_rows = load_csv_safely(file_path)

    relative_path = str(
        file_path.relative_to(LIBRARY_DIR)
    )

    if df.empty:
        return {
            "source_file": relative_path,
            "status": "EMPTY_OR_UNREADABLE",
            "valid_records": 0,
            "flagged_records": flagged_rows,
            "candidate_metrics": [],
            "date_ranges": []
        }

    date_ranges = detect_date_columns(df)
    numeric_columns = detect_numeric_columns(df)

    candidate_metrics = []

    for item in numeric_columns:

        series = item["values"].dropna()

        # Skip columns without usable numeric observations
        if series.empty:
            continue

        candidate_metrics.append({

            "metric_name": item["column"],
            "source_column": item["column"],
            "source_file": relative_path,

            "definition": "NOT_YET_ESTABLISHED",
            "unit": "NOT_YET_ESTABLISHED",
            "baseline": "NOT_AVAILABLE",
            "comparison_period": "NOT_ESTABLISHED",

            "measurement_window": date_ranges,

            "record_count": int(len(series)),

            "missing_records": int(
                item["values"].isna().sum()
            ),

            "descriptive_statistics": {
                "minimum": float(series.min()),
                "maximum": float(series.max()),
                "mean": float(series.mean()),
                "median": float(series.median())
            },

            "calculation_method": (
                "Descriptive statistics calculated from "
                "valid numeric records."
            ),

            "status": "NEEDS_DEFINITION_AND_VALIDATION"
        })

    return {
        "source_file": relative_path,

        "status": (
            "NEEDS_MANUAL_REVIEW"
            if flagged_rows
            else "PROFILED"
        ),

        "total_valid_records": int(len(df)),
        "total_columns": int(len(df.columns)),

        "columns": df.columns.tolist(),

        "date_ranges": date_ranges,

        "flagged_records": flagged_rows,

        "candidate_metrics": candidate_metrics
    }


def run_kpi_analyst():
    """Run KPI Analyst over all project CSV files."""

    print("\nStarting KPI Analyst Agent...\n")

    if not LIBRARY_DIR.exists():
        raise FileNotFoundError(
            f"Library not found: {LIBRARY_DIR}"
        )

    csv_files = sorted(
        LIBRARY_DIR.rglob("*.csv")
    )

    datasets = []
    all_metrics = []

    for file_path in csv_files:

        try:
            result = analyze_dataset(file_path)

        except Exception as error:

            result = {
                "source_file": str(
                    file_path.relative_to(LIBRARY_DIR)
                ),
                "status": "EXTRACTION_ERROR",
                "error": str(error),
                "candidate_metrics": [],
                "flagged_records": []
            }

        datasets.append(result)

        all_metrics.extend(
            result.get("candidate_metrics", [])
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    flagged_count = sum(
        len(dataset.get("flagged_records", []))
        for dataset in datasets
    )

    error_count = sum(
        dataset["status"] == "EXTRACTION_ERROR"
        for dataset in datasets
    )

    output = {

        "agent": "KPI Analyst",
        "project": "Project Drishti",

        "status": "PRELIMINARY_DATA_ANALYSIS",

        "datasets_analyzed": len(datasets),

        "total_candidate_metrics": len(all_metrics),

        "total_malformed_records": flagged_count,

        "total_extraction_errors": error_count,

        "datasets": datasets,

        "candidate_metrics": all_metrics,

        "limitations": [
            "Numeric columns are candidate metrics, not approved KPIs.",
            "Metric definitions and units require validation.",
            "Baselines and comparison periods are not assumed.",
            "Descriptive statistics do not establish project impact.",
            "Malformed records are excluded from calculations and flagged.",
            "Conflicting results require source-level investigation.",
            "No causal improvement claims are generated.",
            "Date parsing results require source-level validation."
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

    print("KPI ANALYST COMPLETE")
    print("-" * 40)

    print("Datasets analyzed:", len(datasets))
    print("Candidate metrics:", len(all_metrics))
    print("Malformed records flagged:", flagged_count)
    print("Extraction errors:", error_count)

    print("\nOutput saved to:")
    print(OUTPUT_FILE)

    return output


if __name__ == "__main__":
    run_kpi_analyst()
