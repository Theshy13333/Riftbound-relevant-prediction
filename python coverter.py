import json
import re
from pathlib import Path

INPUT_FILE = "Last 15 days stat"
OUTPUT_FILE = "riftdecks_stats.json"

html = Path(INPUT_FILE).read_text(
    encoding="utf-8",
    errors="replace"
)

match = re.search(
    r'var\s+DATA\s*=\s*(\[[\s\S]*?\]);',
    html
)

if not match:
    print("ERROR: Could not find RiftDecks card data.")
    exit()

cards = json.loads(match.group(1))

# Remove image fields
for card in cards:
    card.pop("img", None)
    card.pop("full_img", None)

formatted_data = {
    "source": "RiftDecks",
    "date_range": "Last 15 Days",
    "card_count": len(cards),
    "cards": cards
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
    json.dump(
        formatted_data,
        file,
        indent=4,
        ensure_ascii=False
    )

print(f"Successfully extracted {len(cards)} cards.")
print(f"Saved to: {OUTPUT_FILE}")