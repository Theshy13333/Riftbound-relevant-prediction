import json
import re
from pathlib import Path


# Change this to the name/location of your downloaded RiftDecks file
INPUT_FILE = "Last 15 days stat"

# Name of the JSON file that will be created
OUTPUT_FILE = "riftdecks_stats.json"


# Read the downloaded HTML file
html = Path(INPUT_FILE).read_text(
    encoding="utf-8",
    errors="replace"
)

# Find the JavaScript variable:
# var DATA = [...]
match = re.search(
    r'var\s+DATA\s*=\s*(\[[\s\S]*?\]);',
    html
)

if not match:
    print("ERROR: Could not find RiftDecks card data.")
    exit()


# Convert the extracted text into Python data
cards = json.loads(match.group(1))


# Optional: make the output easier to use later
formatted_data = {
    "source": "RiftDecks",
    "card_count": len(cards),
    "cards": cards
}


# Save formatted JSON
with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
    json.dump(
        formatted_data,
        file,
        indent=4,
        ensure_ascii=False
    )


print(f"Successfully extracted {len(cards)} cards.")
print(f"Saved to: {OUTPUT_FILE}")