"""Build data/items.json (the catalog source) from the downloaded datasets.

Then `npm run catalog` (the shared scripts/build_catalog.py) turns it into
public/catalog.json.

Sources (bash scripts/niche/fetch_sources.sh downloads them to data/raw/):
  Timepiece Treasures      163k market listings (CC0). One item per brand + reference;
                           each spec takes its most common value across the listings.
  Luxury Watch Listings    284k listings: case size, gender and year, matched by brand + reference.
  Luxury Watches Price     typical specs per model family (CC BY 4.0, rkiattisak): water
                           resistance and case size, only where the listings have none.
  data/sample.json         the first 20 items (t1..t20): kept, so no rating or collection loses its item.

Usage: bash scripts/niche/fetch_sources.sh && python3 scripts/niche/build_items.py && npm run catalog
"""

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data/raw"
TREASURES = RAW / "yoerireumkens_timepiece-treasures-a-luxury-watches-dataset/watch_data.csv"
LISTINGS = RAW / "philmorekoung11_luxury-watch-listings/Watches.csv"
FAMILIES = RAW / "rkiattisak_luxury-watches-price-dataset/Luxury watch.csv"

MOVEMENTS = {"Automatic": "automatic", "Quartz": "quartz", "Hand-wound": "manual", "Manual winding": "manual"}
GENDERS = {"Men's watch/Unisex": "men", "Women's watch": "women"}
FIXES = {"champaign": "champagne", "ostritch_leather": "ostrich_leather", "resin": "plastic"}
# Word in the model name → complication, in display order.
COMPLICATIONS = [
    (r"day[- ]date", "day_date"),
    (r"\bdate\b|datejust|datograph", "date"),
    (r"chrono(graph)?\b|daytona|speedmaster|navitimer|el primero", "chronograph"),
    (r"\bgmt\b|dual time|\bdual[- ]?zone\b", "gmt"),
    (r"world ?time|worldtimer|world time", "world_time"),
    (r"moon ?phase|\bmoon\b", "moonphase"),
    (r"annual calendar", "annual_calendar"),
    (r"perpetual", "perpetual_calendar"),
    (r"tourbillon", "tourbillon"),
    (r"repeater", "minute_repeater"),
    (r"power reserve", "power_reserve"),
    (r"alarm|memovox|cricket", "alarm"),
]
JUNK_REF = re.compile(r"^(unknown|n/?a|none|-+|\?+)$", re.I)


def fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(text))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-")


def value_key(text: str) -> str:
    """'Rose gold', 'Crocodile-Leather' → 'rose_gold', 'crocodile_leather'."""
    key = re.sub(r"[^a-z0-9]+", "_", fold(text)).strip("_")
    return FIXES.get(key, key)


def most_common(values):
    values = [v for v in values if v not in (None, "")]
    return Counter(values).most_common(1)[0][0] if values else None


def clean_ref(ref: str) -> str:
    ref = re.sub(r"\s+", " ", (ref or "").strip()).upper()
    # Long or wordy "references" are listing titles typed into the wrong field.
    junk = len(compact(ref)) < 3 or len(ref) > 40 or len(re.findall(r"[A-Z]{4,}", ref)) > 1 or JUNK_REF.match(ref)
    return "" if junk else ref


def ref_prefixes(ref: str) -> list[str]:
    """'15300ST.OO.1220ST.02' → its compact form, then shorter by whole parts: '15300stoo1220st', … '15300st'."""
    parts = [p for p in re.split(r"[.\-/ ]", ref) if p]
    return [compact("".join(parts[:n])) for n in range(len(parts), 0, -1)]


def complications(model: str) -> list[str]:
    found = [label for pattern, label in COMPLICATIONS if re.search(pattern, model, re.I)]
    return [c for c in found if not (c == "date" and "day_date" in found)]


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def treasures() -> dict[tuple[str, str], dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    seen = set()
    for row in read_csv(TREASURES):
        ref = clean_ref(row["Reference"])
        line = tuple(row.values())
        if not ref or not row["Brand"].strip() or line in seen:
            continue
        seen.add(line)
        groups[(compact(row["Brand"]), compact(ref))].append({**row, "Reference": ref})

    items = {}
    for key, rows in groups.items():
        col = lambda c: [r[c].strip() for r in rows]  # noqa: E731
        model = most_common(col("Model")) or ""
        brand = most_common(col("Brand"))
        reference = most_common(col("Reference"))
        items[key] = {
            "key": slug(f"{brand}-{reference}"),
            "name": " ".join(p for p in (brand, model, reference) if p),
            "brand": brand,
            "model": model,
            "reference": reference,
            "movement": MOVEMENTS.get(most_common(col("Complication")) or "", ""),
            "caseSize": None,
            "caseMaterial": value_key(most_common(col("Case material")) or ""),
            "waterResistance": None,
            "complications": complications(model),
            "dialColor": value_key(most_common(col("Dial")) or ""),
            "bracelet": value_key(most_common(col("Bracelet material")) or ""),
            "bezel": value_key(most_common(col("Lunette Material")) or ""),
            "gender": "",
            "year": None,
        }
    return items


def year_of(value: str) -> int | None:
    m = re.fullmatch(r"(\d{4})", (value or "").strip())  # "(Approximation)" years are left out
    return int(m.group(1)) if m and 1900 <= int(m.group(1)) <= 2025 else None


def size_of(value: str) -> float | None:
    m = re.match(r"(\d{2}(?:\.\d+)?)\s*mm", (value or "").strip())
    return float(m.group(1)) if m and 20 <= float(m.group(1)) <= 60 else None


def add_listings(items: dict) -> int:
    """Case size, gender and year from the second listing set, matched by brand + reference (or its leading parts)."""
    found: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in read_csv(LISTINGS):
        ref, brand = clean_ref(row["ref"]), compact(row["brand"])
        if not ref:
            continue
        key = next(((brand, p) for p in ref_prefixes(ref) if (brand, p) in items), None)
        if key:
            found[key].append(row)
    for key, rows in found.items():
        item = items[key]
        item["caseSize"] = most_common([size_of(r["size"]) for r in rows])
        item["gender"] = GENDERS.get(most_common([r["sex"] for r in rows]) or "", "")
        if not item["movement"]:
            item["movement"] = MOVEMENTS.get(most_common([r["mvmt"] for r in rows]) or "", "")
        years = Counter(y for y in (year_of(r["yop"]) for r in rows) if y)
        # The earliest year seen twice (one-off years are often typos), else the earliest at all.
        item["year"] = min((y for y, n in years.items() if n > 1), default=min(years, default=None))
    return len(found)


def number_of(value: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", (value or "").replace(",", ""))
    return float(m.group(0)) if m else None


def add_families(items: dict) -> int:
    """Typical water resistance and case size of a model family, only where nothing better is known."""
    families: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for row in read_csv(FAMILIES):
        families[compact(row["Brand"])].append((compact(row["Model"]), row))
    filled = 0
    for (brand, _), item in items.items():
        model = compact(item["model"])
        match = [r for m, r in families.get(brand, []) if m and model.startswith(m)]
        if not match:
            continue
        filled += 1
        if item["waterResistance"] is None:
            item["waterResistance"] = most_common([number_of(r["Water Resistance"]) for r in match])
        if item["caseSize"] is None:
            item["caseSize"] = most_common([number_of(r["Case Diameter (mm)"]) for r in match])
    return filled


def from_sample(sample: dict) -> dict:
    """A hand-entered sample item, with its values in the catalog's keys."""
    return {
        **sample,
        "caseMaterial": value_key(sample.get("caseMaterial", "")),
        "complications": [c for c in (value_key(c) for c in sample.get("complications", [])) if c != "day"],
    }


def build() -> list[dict]:
    items = treasures()
    print(f"references {len(items)} · with listing specs {add_listings(items)} · with family specs {add_families(items)}")
    samples = {(compact(s["brand"]), compact(s["reference"])): from_sample(s)
               for s in json.loads((ROOT / "data/sample.json").read_text())}
    by_key = {item["key"]: item for item in items.values()}
    matched = set()
    for (brand, _), sample in samples.items():
        # Same brand + reference (or its leading parts), else the same generated key.
        item = next((items[(brand, p)] for p in ref_prefixes(sample["reference"]) if (brand, p) in items),
                    by_key.get(sample["key"]))
        if item is None:
            continue
        matched.add(sample["key"])
        item["sample"] = True
        item["key"] = sample["key"]  # keeps its t<n> id
        for field, value in sample.items():  # the sample's facts win where they exist
            if value not in (None, "", []) and field not in ("key", "name"):
                item[field] = value
        item["name"] = " ".join(p for p in (item["brand"], item["model"], item["reference"]) if p)
    out = list(items.values())
    out += [s for s in samples.values() if s["key"] not in matched]
    # A generated key can equal a sample's hand-made one: the sample keeps it, the other gets a suffix.
    for item in out:
        if not item.pop("sample", False) and item["key"] in matched:
            item["key"] += "-2"
    return out


def main():
    items = build()
    # Photos found by scripts/niche/fetch_images.py: item key → image number.
    images = json.loads((ROOT / "data/images.json").read_text()) if (ROOT / "data/images.json").exists() else {}
    for item in items:
        item["image"] = images.get(item["key"])
    (ROOT / "data/items.json").write_text(
        "[\n" + ",\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n]\n"
    )
    count = lambda f: sum(1 for i in items if i.get(f) not in (None, "", []))  # noqa: E731
    print(f"items {len(items)} · " + " · ".join(f"{f} {count(f)}" for f in
          ("movement", "caseSize", "caseMaterial", "waterResistance", "complications", "dialColor", "gender", "year")))


if __name__ == "__main__":
    main()
