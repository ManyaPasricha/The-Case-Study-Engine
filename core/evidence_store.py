
from pathlib import Path
import json
import re

from core.ingestion import process_library, BASE_DIR


# Where extracted evidence will be stored
OUTPUT_DIR = BASE_DIR / "outputs"
EVIDENCE_FILE = OUTPUT_DIR / "evidence_chunks.json"


def clean_text(text):
    """Normalize whitespace without changing the meaning."""

    text = str(text)
    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def split_into_chunks(text, chunk_size=1200, overlap=150):
    """
    Split text into manageable chunks.

    Each chunk retains some overlap with the previous chunk
    so that context is not abruptly lost.
    """

    text = clean_text(text)

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):

        end = min(start + chunk_size, len(text))

        # Prefer ending at a paragraph or sentence boundary
        if end < len(text):
            boundary = text.rfind("\n", start, end)

            if boundary == -1 or boundary <= start + chunk_size // 2:
                boundary = text.rfind(". ", start, end)

            if boundary > start + chunk_size // 2:
                end = boundary + 1

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        next_start = max(start + 1, end - overlap)
        start = next_start

    return chunks


def classify_document(relative_path):
    """Identify the broad document category from its folder."""

    path = relative_path.lower()

    if "contract" in path or "commercial" in path:
        return "COMMERCIAL_OR_CONTRACT"

    elif "email" in path:
        return "EMAIL"

    elif "meeting" in path:
        return "MEETING"

    elif "data" in path:
        return "DATA"

    elif "delivery" in path:
        return "DELIVERY"

    elif "github" in path:
        return "TECHNICAL"

    elif "feedback" in path:
        return "FEEDBACK"

    elif "media" in path:
        return "MEDIA"

    elif "scoping" in path:
        return "PROJECT_SCOPE"

    elif "vendor" in path:
        return "VENDOR"

    elif "public" in path:
        return "PUBLIC_REFERENCE"

    else:
        return "GENERAL"


def extract_text_content(content):
    """Convert supported extracted content into text."""

    if isinstance(content, str):
        return content

    # Structured CSV content
    if isinstance(content, dict):

        # Do not use malformed CSV rows as evidence
        if "data" in content and "columns" in content:

            lines = []

            for row_number, row in enumerate(
                content["data"], start=1
            ):
                lines.append(
                    f"Record {row_number}: {json.dumps(row, ensure_ascii=False)}"
                )

            return "\n".join(lines)

        # Do not turn YAML or other dictionaries into claims
        return json.dumps(content, ensure_ascii=False, default=str)

    return str(content)


def build_evidence_chunks():
    """Process documents and generate traceable evidence chunks."""

    print("\nBuilding evidence chunks...\n")

    documents = process_library()

    all_chunks = []
    skipped_files = []

    for document in documents:

        filename = document["filename"]
        relative_path = document["relative_path"]
        extension = document["extension"]
        content = document["content"]

        # Skip failed or unsupported files
        if isinstance(content, str) and (
            content.startswith("EXTRACTION_ERROR")
            or content == "UNSUPPORTED_FILE_TYPE"
            or content == "IMAGE_FILE_REQUIRES_VISUAL_INSPECTION"
        ):
            skipped_files.append(relative_path)
            continue

        # Skip CSV files containing records needing review.
        # Their valid records can still be used, but malformed
        # records are explicitly excluded.
        text = extract_text_content(content)

        if not text.strip():
            continue

        chunks = split_into_chunks(text)

        for index, chunk in enumerate(chunks, start=1):

            evidence_item = {
                "evidence_id": (
                    f"EV-{len(all_chunks) + 1:04d}"
                ),
                "source_file": filename,
                "source_path": relative_path,
                "document_type": classify_document(
                    relative_path
                ),
                "file_type": extension,
                "chunk_number": index,
                "content": chunk,
                "verification_status": "UNVERIFIED",
                "review_required": (
                    isinstance(content, dict)
                    and bool(content.get("flagged_rows"))
                )
            }

            all_chunks.append(evidence_item)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(
        EVIDENCE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            all_chunks,
            f,
            indent=4,
            ensure_ascii=False
        )

    print("EVIDENCE EXTRACTION COMPLETE")
    print("-" * 40)

    print("Total evidence chunks:", len(all_chunks))
    print("Files skipped:", len(skipped_files))

    print("\nDocument categories:")

    categories = {}

    for item in all_chunks:
        category = item["document_type"]
        categories[category] = categories.get(category, 0) + 1

    for category, count in categories.items():
        print(f"{category}: {count}")

    print("\nEvidence saved to:")
    print(EVIDENCE_FILE)

    return all_chunks


if __name__ == "__main__":
    build_evidence_chunks()
