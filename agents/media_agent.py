
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

LIBRARY_DIR = (
    BASE_DIR
    / "Project_Drishti_Library"
    / "Project_Drishti_Library"
)

OUTPUT_DIR = BASE_DIR / "outputs" / "media_pack"
OUTPUT_FILE = OUTPUT_DIR / "media_inventory.json"


# Media categories based on filename and folder context.
# These are preliminary classifications, not visual verification.

MEDIA_RULES = {
    "CAMERA_SNAPSHOT": [
        "camera",
        "cam",
        "snapshot",
        "alert"
    ],

    "DASHBOARD": [
        "dashboard",
        "export",
        "metrics",
        "chart"
    ],

    "ARCHITECTURE_DIAGRAM": [
        "architecture",
        "system",
        "diagram",
        "design"
    ]
}


def classify_asset(file_path):
    """Classify an image using its filename."""

    filename = file_path.name.lower()

    for category, keywords in MEDIA_RULES.items():

        if any(keyword in filename for keyword in keywords):
            return category

    return "UNCLASSIFIED"


def assess_asset(category):
    """Suggest a conservative review requirement."""

    assessments = {

        "CAMERA_SNAPSHOT": {
            "potential_risk": [
                "Personal information",
                "Faces or identifiable individuals",
                "Camera identifiers",
                "Sensitive operational details"
            ],
            "recommended_action": (
                "Inspect locally. Redact identifiable people, "
                "camera identifiers and sensitive operational "
                "details where necessary."
            ),
            "publication_status": "HOLD_PENDING_VISUAL_REVIEW"
        },

        "DASHBOARD": {
            "potential_risk": [
                "Employee or supervisor information",
                "Sensitive operational metrics",
                "Site-specific information",
                "Unapproved performance claims"
            ],
            "recommended_action": (
                "Check labels, names, values and reporting "
                "periods. Confirm that displayed metrics are "
                "approved for publication."
            ),
            "publication_status": "HOLD_PENDING_VISUAL_REVIEW"
        },

        "ARCHITECTURE_DIAGRAM": {
            "potential_risk": [
                "Network topology",
                "Security architecture",
                "Camera locations",
                "System access details"
            ],
            "recommended_action": (
                "Review locally. Create a simplified public "
                "diagram that excludes sensitive infrastructure "
                "and security information, if permitted."
            ),
            "publication_status": "HOLD_PENDING_VISUAL_REVIEW"
        },

        "UNCLASSIFIED": {
            "potential_risk": [
                "Unknown image content"
            ],
            "recommended_action": (
                "Manually inspect and classify the image "
                "before considering publication."
            ),
            "publication_status": "HOLD_PENDING_VISUAL_REVIEW"
        }
    }

    return assessments[category]


def discover_media():
    """Find all supported image files in the project library."""

    if not LIBRARY_DIR.exists():
        raise FileNotFoundError(
            f"Library not found: {LIBRARY_DIR}"
        )

    supported_extensions = {
        ".jpg",
        ".jpeg",
        ".png"
    }

    media_files = []

    for file_path in LIBRARY_DIR.rglob("*"):

        if (
            file_path.is_file()
            and file_path.suffix.lower() in supported_extensions
        ):
            media_files.append(file_path)

    return sorted(media_files)


def build_media_inventory():
    """Create a traceable inventory of media assets."""

    print("\nStarting Media Agent...\n")

    media_files = discover_media()

    assets = []

    for index, file_path in enumerate(media_files, start=1):

        category = classify_asset(file_path)

        assessment = assess_asset(category)

        relative_path = str(
            file_path.relative_to(LIBRARY_DIR)
        )

        asset = {

            "asset_id": f"MEDIA-{index:03d}",

            "filename": file_path.name,

            "source_path": relative_path,

            "file_extension": file_path.suffix.lower(),

            "category": category,

            "file_exists": file_path.exists(),

            "intended_use": {
                "CAMERA_SNAPSHOT": (
                    "Potential operational illustration"
                ),
                "DASHBOARD": (
                    "Potential results or performance illustration"
                ),
                "ARCHITECTURE_DIAGRAM": (
                    "Potential technical solution illustration"
                ),
                "UNCLASSIFIED": (
                    "Undetermined until manual inspection"
                )
            }[category],

            "potential_risk": assessment["potential_risk"],

            "recommended_action": assessment["recommended_action"],

            "visual_review_status": "NOT_YET_INSPECTED",

            "permission_status": "NOT_VERIFIED",

            "publication_status": assessment["publication_status"]

        }

        assets.append(asset)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output = {

        "agent": "Media Agent",

        "project": "Project Drishti",

        "status": "PRELIMINARY_MEDIA_INVENTORY",

        "total_assets_discovered": len(assets),

        "assets": assets,

        "limitations": [

            "Classification is based on filenames, not image content.",

            "No image has been visually inspected by this agent.",

            "Privacy and security risks require manual inspection.",

            "Publication permissions have not been established.",

            "No asset is approved for external publication.",

            "All original files remain unchanged."

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

    print("MEDIA AGENT COMPLETE")
    print("-" * 40)

    print("Total media assets:", len(assets))

    print("\nASSET SUMMARY:")

    for asset in assets:

        print(
            asset["asset_id"],
            "|",
            asset["category"],
            "|",
            asset["publication_status"]
        )

    print("\nOutput saved to:")
    print(OUTPUT_FILE)

    return output


if __name__ == "__main__":
    build_media_inventory()
