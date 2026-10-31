
import json
from pathlib import Path
from collections import Counter

base = Path(__file__).resolve().parent

with open(
    base / "outputs/story_spine/historian_output.json",
    encoding="utf-8"
) as f:
    historian = json.load(f)

with open(
    base / "outputs/verification_report.json",
    encoding="utf-8"
) as f:
    verifier = json.load(f)

items = historian.get("timeline_evidence", [])

print("HISTORIAN TOP-LEVEL KEYS:")
print(list(historian.keys()))

print("\nTIMELINE EVIDENCE COUNT:")
print(len(items))

print("\nFIRST ITEM FIELD NAMES:")
if items:
    print(list(items[0].keys()))

print("\nFIRST ITEM FIELD TYPES:")
if items:
    for key, value in items[0].items():
        print(key, type(value).__name__)

print("\nVERIFIER CLAIM TYPE COUNTS:")
print(Counter(
    x.get("claim_type") for x in verifier["claims"]
))

print("\nSOURCE REFERENCE STATUS COUNTS:")
print(Counter(
    x.get("source_reference_status") for x in verifier["claims"]
))

print("\nHISTORIAN CLAIM TEXT COUNTS:")
print("Non-empty:", sum(
    bool(x.get("claim_text") or x.get("event_description")
         or x.get("event") or x.get("description")
         or x.get("summary") or x.get("statement")
         or x.get("text"))
    for x in items
))

print("\nHISTORIAN EVIDENCE ID COUNTS:")
print("Present:", sum(bool(x.get("evidence_id")) for x in items))
