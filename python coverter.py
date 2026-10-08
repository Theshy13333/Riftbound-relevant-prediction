import json
import re
import unicodedata
from pathlib import Path

import requests


# =========================================================
# SETTINGS
# =========================================================

RIFTCODEX_URL = "https://api.riftcodex.com/cards"

# Every time you download new RiftDecks stats,
# rename/replace the file with this name.
STATS_FILE = "latest_stats"

OUTPUT_FILE = "riftbound_dataset.json"

# Helpful debugging file showing anything that failed to match.
REPORT_FILE = "dataset_report.json"

PAGE_SIZE = 100

# Any sets in this list will NEVER be included.
EXCLUDED_SETS = {
    "RAD"
}


# =========================================================
# NORMALIZE CARD NAMES
# =========================================================

def normalize_name(name):
    """
    Makes matching between RiftCodex and RiftDecks
    more reliable.

    Example:

    Kai'Sa, Survivor
    kai’sa survivor

    both become something similar to:
    kaisasurvivor
    """

    if not name:
        return ""

    name = unicodedata.normalize(
        "NFKD",
        str(name)
    )

    name = "".join(
        character
        for character in name
        if not unicodedata.combining(character)
    )

    name = name.lower()

    # Normalize apostrophes
    name = name.replace("’", "'")

    # Remove punctuation and spaces
    name = re.sub(
        r"[^a-z0-9]+",
        "",
        name
    )

    return name


def normalize_type(card_type):

    if not card_type:
        return ""

    return str(card_type).strip().lower()


# =========================================================
# LOAD RIFTDECKS LAST-15-DAYS STATS
# =========================================================

def load_riftdecks_stats(filename):

    print()
    print("Reading RiftDecks stats...")

    html = Path(filename).read_text(
        encoding="utf-8",
        errors="replace"
    )

    match = re.search(
        r'var\s+DATA\s*=\s*(\[[\s\S]*?\]);',
        html
    )

    if not match:
        raise ValueError(
            "Could not find RiftDecks DATA inside "
            f"'{filename}'."
        )

    stats_cards = json.loads(
        match.group(1)
    )

    lookup = {}

    excluded = 0

    for card in stats_cards:

        set_code = str(
            card.get("set") or ""
        ).upper()

        # -----------------------------------------
        # REMOVE RADIANCE
        # -----------------------------------------

        if set_code in EXCLUDED_SETS:
            excluded += 1
            continue

        name = card.get("name")
        card_type = card.get("type")

        key = (
            set_code,
            normalize_name(name),
            normalize_type(card_type)
        )

        lookup[key] = {
            "name": name,
            "set": set_code,
            "card_type": card_type,

            "play_rate": card.get("play"),
            "win_rate": card.get("win")
        }

    print(
        f"RiftDecks records loaded: {len(lookup)}"
    )

    return lookup, excluded


# =========================================================
# DOWNLOAD ALL CARDS FROM RIFTCODEX
# =========================================================

def download_all_riftcodex_cards():

    all_cards = []

    page = 1

    print()
    print("Contacting RiftCodex API...")

    while True:

        params = {
            "page": page,
            "size": PAGE_SIZE,
            "sort": "set_id",
            "dir": 1
        }

        print(
            f"Downloading API page {page}..."
        )

        try:

            response = requests.get(
                RIFTCODEX_URL,
                params=params,
                timeout=30
            )

            response.raise_for_status()

        except requests.RequestException as error:

            print()
            print("ERROR contacting RiftCodex:")
            print(error)

            raise SystemExit


        data = response.json()

        items = data.get(
            "items",
            []
        )

        if not items:
            break

        all_cards.extend(items)

        total = data.get("total")

        print(
            f"  Received {len(all_cards)}"
            + (
                f" / {total}"
                if total is not None
                else ""
            )
        )

        # Stop when API says we have everything
        if (
            total is not None
            and len(all_cards) >= total
        ):
            break

        # A partial page also means we're finished
        if len(items) < PAGE_SIZE:
            break

        page += 1


    print()
    print(
        f"Total RiftCodex records downloaded: "
        f"{len(all_cards)}"
    )

    return all_cards


# =========================================================
# CLEAN RIFTCODEX CARD
# =========================================================

def clean_riftcodex_card(card):

    attributes = (
        card.get("attributes")
        or {}
    )

    classification = (
        card.get("classification")
        or {}
    )

    text_data = (
        card.get("text")
        or {}
    )

    set_data = (
        card.get("set")
        or {}
    )

    metadata = (
        card.get("metadata")
        or {}
    )


    set_code = str(
        set_data.get("set_id") or ""
    ).upper()


    return {

        # -----------------------------------------
        # Useful card information
        # -----------------------------------------

        "name": card.get("name"),

        "set": set_code,

        "card_type": classification.get(
            "type"
        ),

        "supertype": classification.get(
            "supertype"
        ),

        "domain": classification.get(
            "domain"
        ),

        "energy_cost": attributes.get(
            "energy"
        ),

        "power_cost": attributes.get(
            "power"
        ),

        "might": attributes.get(
            "might"
        ),

        # Includes Unit / Spell / Gear /
        # Battlefield rules text.
        "text": text_data.get(
            "plain"
        ),


        # -----------------------------------------
        # Internal information used only while
        # deciding which printing to keep.
        # These are removed from final JSON.
        # -----------------------------------------

        "_alternate_art": metadata.get(
            "alternate_art",
            False
        ),

        "_signature": metadata.get(
            "signature",
            False
        ),

        "_overnumbered": metadata.get(
            "overnumbered",
            False
        )
    }


# =========================================================
# DETERMINE WHETHER PRINTING IS SPECIAL
# =========================================================

def is_special_printing(card):

    return (
        card.get("_alternate_art", False)
        or card.get("_signature", False)
        or card.get("_overnumbered", False)
    )


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # 1. Load newest RiftDecks stats
    # -----------------------------------------------------

    stats_lookup, rad_stats_removed = (
        load_riftdecks_stats(
            STATS_FILE
        )
    )


    # -----------------------------------------------------
    # 2. Automatically download current RiftCodex database
    # -----------------------------------------------------

    raw_api_cards = (
        download_all_riftcodex_cards()
    )


    # -----------------------------------------------------
    # 3. Clean API data and remove RAD
    # -----------------------------------------------------

    unique_cards = {}

    rad_api_removed = 0

    discovered_sets = set()


    for raw_card in raw_api_cards:

        card = clean_riftcodex_card(
            raw_card
        )

        set_code = card.get(
            "set",
            ""
        )

        if set_code:
            discovered_sets.add(
                set_code
            )


        # =========================================
        # REMOVE ALL RAD CARDS
        # =========================================

        if set_code in EXCLUDED_SETS:

            rad_api_removed += 1

            continue


        # =========================================
        # MATCHING KEY
        # =========================================

        key = (
            set_code,
            normalize_name(
                card.get("name")
            ),
            normalize_type(
                card.get("card_type")
            )
        )


        # =========================================
        # FIRST PRINTING
        # =========================================

        if key not in unique_cards:

            unique_cards[key] = card

            continue


        # =========================================
        # DUPLICATE / ALT ART HANDLING
        # =========================================

        existing = unique_cards[key]

        existing_special = (
            is_special_printing(
                existing
            )
        )

        new_special = (
            is_special_printing(
                card
            )
        )


        # Prefer normal base card over
        # signature / alternate / overnumbered.
        if (
            existing_special
            and not new_special
        ):

            unique_cards[key] = card


    # -----------------------------------------------------
    # 4. Merge stats
    # -----------------------------------------------------

    final_cards = []

    matched_stats = 0

    cards_without_stats = []

    used_stat_keys = set()


    for key, card in unique_cards.items():

        stat = stats_lookup.get(
            key
        )


        if stat is not None:

            matched_stats += 1

            used_stat_keys.add(
                key
            )

            card["play_rate"] = (
                stat.get("play_rate")
            )

            card["win_rate"] = (
                stat.get("win_rate")
            )


        else:

            # This is NOT the same as 0%.
            # It means RiftDecks had no matching
            # stat record for this card.
            card["play_rate"] = None

            card["win_rate"] = None


            cards_without_stats.append(
                {
                    "name": card.get(
                        "name"
                    ),

                    "set": card.get(
                        "set"
                    ),

                    "card_type": card.get(
                        "card_type"
                    )
                }
            )


        # =========================================
        # REMOVE TEMPORARY INTERNAL FIELDS
        # =========================================

        card.pop(
            "_alternate_art",
            None
        )

        card.pop(
            "_signature",
            None
        )

        card.pop(
            "_overnumbered",
            None
        )


        final_cards.append(
            card
        )


    # -----------------------------------------------------
    # 5. Find RiftDecks records that failed to match
    # -----------------------------------------------------

    unmatched_stats = []


    for key, stat in stats_lookup.items():

        if key not in used_stat_keys:

            unmatched_stats.append(
                {
                    "name": stat.get(
                        "name"
                    ),

                    "set": stat.get(
                        "set"
                    ),

                    "card_type": stat.get(
                        "card_type"
                    ),

                    "play_rate": stat.get(
                        "play_rate"
                    ),

                    "win_rate": stat.get(
                        "win_rate"
                    )
                }
            )


    # -----------------------------------------------------
    # 6. Sort output
    # -----------------------------------------------------

    final_cards.sort(
        key=lambda card: (
            card.get("set") or "",
            card.get("name") or "",
            card.get("card_type") or ""
        )
    )


    # -----------------------------------------------------
    # 7. Create final dataset
    # -----------------------------------------------------

    output = {

        "source": {
            "card_data": "RiftCodex",
            "competitive_stats": "RiftDecks"
        },

        "stats_period": (
            "Last 15 Days"
        ),

        "excluded_sets": sorted(
            EXCLUDED_SETS
        ),

        "sets_found": sorted(
            discovered_sets
            - EXCLUDED_SETS
        ),

        "card_count": len(
            final_cards
        ),

        "cards": final_cards
    }


    # -----------------------------------------------------
    # 8. Save main JSON
    # -----------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=4,
            ensure_ascii=False
        )


    # -----------------------------------------------------
    # 9. Create diagnostic report
    # -----------------------------------------------------

    report = {

        "riftcodex_records_downloaded":
            len(raw_api_cards),

        "sets_discovered":
            sorted(discovered_sets),

        "excluded_sets":
            sorted(EXCLUDED_SETS),

        "api_cards_removed_from_excluded_sets":
            rad_api_removed,

        "riftdecks_records":
            len(stats_lookup),

        "riftdecks_excluded_records":
            rad_stats_removed,

        "unique_cards_saved":
            len(final_cards),

        "cards_with_stats":
            matched_stats,

        "cards_without_stats":
            len(cards_without_stats),

        "riftdecks_records_failed_to_match":
            len(unmatched_stats),

        "cards_missing_stats":
            cards_without_stats,

        "unmatched_riftdecks_stats":
            unmatched_stats
    }


    with open(
        REPORT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4,
            ensure_ascii=False
        )


    # -----------------------------------------------------
    # 10. Print report
    # -----------------------------------------------------

    print()
    print("================================")
    print("       DATASET BUILD REPORT")
    print("================================")

    print(
        f"RiftCodex records downloaded: "
        f"{len(raw_api_cards)}"
    )

    print(
        "Sets automatically discovered: "
        + ", ".join(
            sorted(discovered_sets)
        )
    )

    print(
        f"RAD/API cards removed: "
        f"{rad_api_removed}"
    )

    print(
        f"RiftDecks stat records: "
        f"{len(stats_lookup)}"
    )

    print(
        f"RAD stat records removed: "
        f"{rad_stats_removed}"
    )

    print(
        f"Unique cards saved: "
        f"{len(final_cards)}"
    )

    print(
        f"Cards matched with stats: "
        f"{matched_stats}"
    )

    print(
        f"Cards without recent stats: "
        f"{len(cards_without_stats)}"
    )

    print(
        f"RiftDecks stats that failed "
        f"to match: {len(unmatched_stats)}"
    )

    print()
    print(
        f"Dataset saved to: "
        f"{OUTPUT_FILE}"
    )

    print(
        f"Detailed report saved to: "
        f"{REPORT_FILE}"
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()