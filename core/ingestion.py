from pathlib import Path
import pandas as pd
import yaml
import csv

# Locate project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Actual project library location (nested folder)
LIBRARY_DIR = (
    BASE_DIR
    / "Project_Drishti_Library"
    / "Project_Drishti_Library"
)


def scan_library():
    """Discover all files in the project library."""

    if not LIBRARY_DIR.exists():
        raise FileNotFoundError(
            f"Library not found: {LIBRARY_DIR}"
        )

    documents = []

    for file_path in LIBRARY_DIR.rglob("*"):
        if file_path.is_file():
            documents.append({
                "filename": file_path.name,
                "relative_path": str(
                    file_path.relative_to(LIBRARY_DIR)
                ),
                "extension": file_path.suffix.lower(),
                "file_path": file_path
            })

    return documents


def extract_content(file_path):
    """Extract content while preserving problematic records."""

    extension = file_path.suffix.lower()

    try:

        # Markdown and text files
        if extension in [".md", ".txt"]:
            return file_path.read_text(
                encoding="utf-8",
                errors="replace"
            )

        # CSV files
        elif extension == ".csv":

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

                if headers is None:
                    return {
                        "columns": [],
                        "rows": 0,
                        "data": [],
                        "flagged_rows": [],
                        "total_records_read": 0
                    }

                expected_columns = len(headers)

                for line_number, row in enumerate(
                    reader, start=2
                ):

                    if len(row) == expected_columns:

                        valid_rows.append(
                            dict(zip(headers, row))
                        )

                    else:

                        flagged_rows.append({
                            "line_number": line_number,
                            "expected_columns": expected_columns,
                            "actual_columns": len(row),
                            "status": "NEEDS_MANUAL_REVIEW"
                        })

            return {
                "columns": headers,
                "rows": len(valid_rows),
                "data": valid_rows,
                "flagged_rows": flagged_rows,
                "total_records_read": (
                    len(valid_rows) + len(flagged_rows)
                )
            }

        # YAML files
        elif extension in [".yaml", ".yml"]:

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as f:

                return yaml.safe_load(f)

        # Image files
        elif extension in [".jpg", ".png"]:
            return "IMAGE_FILE_REQUIRES_VISUAL_INSPECTION"

        else:
            return "UNSUPPORTED_FILE_TYPE"

    except Exception as error:

        return f"EXTRACTION_ERROR: {str(error)}"


def process_library():
    """Scan and process the complete project library."""

    documents = scan_library()
    extracted_documents = []

    for document in documents:

        content = extract_content(document["file_path"])

        extracted_documents.append({
            "filename": document["filename"],
            "relative_path": document["relative_path"],
            "extension": document["extension"],
            "content": content
        })

    return extracted_documents


def get_document_status(content):
    """Determine processing status of a document."""

    if isinstance(content, str):

        if content.startswith("EXTRACTION_ERROR"):
            return "EXTRACTION_ERROR"

        if content == "UNSUPPORTED_FILE_TYPE":
            return "UNSUPPORTED"

        return "PROCESSED"

    if isinstance(content, dict):

        if content.get("flagged_rows"):
            return "NEEDS_MANUAL_REVIEW"

    return "PROCESSED"


if __name__ == "__main__":

    print("\nStarting document ingestion...\n")

    processed = process_library()

    # Display extraction errors
    print("\nFILES WITH EXTRACTION ERRORS:\n")

    for doc in processed:

        if get_document_status(doc["content"]) == "EXTRACTION_ERROR":
            print("File:", doc["relative_path"])
            print("Error:", doc["content"])
            print("-" * 40)

    # Display CSV records needing review
    print("\nCSV RECORDS NEEDING MANUAL REVIEW:\n")

    for doc in processed:

        content = doc["content"]

        if isinstance(content, dict):

            for flagged in content.get("flagged_rows", []):

                print(
                    doc["relative_path"],
                    "| Line:", flagged["line_number"],
                    "| Expected:", flagged["expected_columns"],
                    "| Actual:", flagged["actual_columns"]
                )

    # Generate document inventory
    inventory = pd.DataFrame([
        {
            "filename": doc["filename"],
            "path": doc["relative_path"],
            "type": doc["extension"],
            "status": get_document_status(doc["content"])
        }
        for doc in processed
    ])

    print("\nTOTAL FILES:", len(inventory))

    print("\nFILE TYPE DISTRIBUTION:")
    print(inventory["type"].value_counts())

    print("\nPROCESSING SUMMARY:")
    print(inventory["status"].value_counts())

    # Save inventory
    output_dir = BASE_DIR / "outputs"
    output_dir.mkdir(exist_ok=True)

    inventory.to_csv(
        output_dir / "document_inventory.csv",
        index=False
    )

    print("\nInventory saved successfully!")
