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
  data/extra.json          watches added by hand because no dataset has them.

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
    # Seller notes after the reference: "116500LN BLACK", "116500LN -- 05-2017", "116503 FULL SET".
    ref = re.split(r"\s*--|\s+(?=(?:[A-Z]{3,}|LC|EU|NG)\b)|\s*\(", ref)[0].strip(" -")
    ref = re.sub(r"\s*([.\-/])\s*", r"\1", ref)  # "5167R- 001" → "5167R-001"
    return "" if junk or len(compact(ref)) < 3 else ref


def base_ref(brand: str, ref: str) -> str:
    """The model's reference without its dial/strap variant code, so colour variants become one item."""
    b = compact(brand)
    if b in ("rolex", "tudor"):
        m = re.match(r"M?\d{4,6}[A-Z]*", ref)  # 116500LN-0001, 116500LN 0523, M79030N-0001
        return m.group(0) if m else ref
    if b == "patekphilippe":
        return re.sub(r"-\d{3}$", "", ref)  # 5196G-001
    if b in ("audemarspiguet", "tagheuer"):
        return re.split(r"[.\-]", ref)[0]  # 25721ST.OO.1000ST.01, CBS2210.FC6534, WAZ111A-BA0875
    if b == "zenith":
        return ref.split("/")[0]  # 03.3100.3600/69.M3100
    if b == "omega" and ref.count(".") >= 4:
        return ".".join(ref.split(".")[:4])  # 210.30.42.20.01.001
    if b in ("tissot", "longines") and ref.count(".") >= 3:
        return ".".join(ref.split(".")[:3])  # T137.407.11.041.00, L3.810.4.53.0
    if b == "hublot" and ref.count(".") >= 3:
        return ".".join(ref.split(".")[:2])  # 511.NO.1181.RX
    if b == "breitling":
        m = re.match(r"[A-Z]{2}\d{4}|[A-Z]\d{5}", ref)  # AB0138211B1P1, A13356
        return m.group(0) if m else ref
    if b == "iwc":
        m = re.match(r"IW\d{4}", ref)  # IW371605
        return m.group(0) if m else ref
    return ref


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
        groups[(compact(row["Brand"]), compact(base_ref(row["Brand"], ref)))].append({**row, "Reference": ref})
    # A Rolex/Tudor reference written without its letters ("116500") joins its most listed lettered one ("116500LN").
    for (brand, ref) in [k for k in groups if k[0] in ("rolex", "tudor") and k[1].isdigit()]:
        lettered = [k for k in groups if k[0] == brand and k[1] != ref and re.fullmatch(rf"m?{ref}[a-z]+", k[1])]
        if lettered:
            groups[max(lettered, key=lambda k: len(groups[k]))] += groups.pop((brand, ref))

    items = {}
    for key, rows in groups.items():
        col = lambda c: [r[c].strip() for r in rows]  # noqa: E731
        model = most_common(col("Model")) or ""
        brand = most_common(col("Brand"))
        variants = Counter(col("Reference"))
        # The key stays that of the most listed variant, so its id (from the first catalog) is kept.
        top = variants.most_common(1)[0][0]
        reference = base_ref(brand, top)
        items[key] = {
            "key": slug(f"{brand}-{top}"),
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
            # Other official references of this model (dial, strap); free text from listings is left out.
            "variants": sorted(v for v in variants if v != reference and re.fullmatch(r"[A-Z0-9][A-Z0-9.\-/]*", v)),
            "listings": len(rows),
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
        options = [compact(base_ref(row["brand"], ref)), *ref_prefixes(ref)]
        key = next(((brand, p) for p in options if (brand, p) in items), None)
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
    # The 20 first samples, plus watches added by hand because no dataset has them (data/extra.json).
    hand_made = json.loads((ROOT / "data/sample.json").read_text()) + json.loads((ROOT / "data/extra.json").read_text())
    samples = {(compact(s["brand"]), compact(s["reference"])): from_sample(s) for s in hand_made}
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
    return collapse_lines(out, {s["key"] for s in samples.values()})


def line_name(model: str) -> str:
    """The model line without its size: "Datejust 36" and "Navitimer 01 (46 MM)" → "Datejust", "Navitimer 01"."""
    model = re.sub(r"\s*\([^)]*\)", "", model or "")
    model = re.sub(r"\s+[2-5]\d(?:\s*mm)?$", "", model, flags=re.I)
    return re.sub(r"\s+", " ", model).strip()


def size_of_ref(ref: dict) -> int | None:
    """The case size, or the one in the model name ("Datejust 41", "Navitimer 01 (46 MM)")."""
    m = re.search(r"\b([2-5]\d)(?:\s*mm)?\)?$", ref.get("model") or "", re.I)
    if m:
        return int(m.group(1))
    return round(ref["caseSize"]) if ref.get("caseSize") else None


def ref_line(brand: str, ref: str) -> str | None:
    """For brands whose listings only name the collection ("G-Shock", "Prospex"), the line comes from the
    reference: Casio "GA-2100-1A1ER" → "GA-2100", Seiko "SRPF67K1" → "SRPF67", Citizen "NB6021-68L" → "NB6021"."""
    b = compact(brand)
    if b == "casio":
        m = re.match(r"[A-Z]+-?[A-Z]*\d+", ref)
        return m.group(0) if m else ref
    if b == "seiko":
        return re.sub(r"[JKP]\d?$", "", ref)
    if b == "citizen":
        return ref.split("-")[0]
    if b == "grandseiko":
        return ref
    return None


def collapse_lines(refs: list[dict], sample_keys: set[str]) -> list[dict]:
    """One item per brand + model line + main case size. Its references become "Other references".

    Sizes come from listings and are noisy, so a line is split only by its main sizes (at least 3 references
    and 10% of the line); other sizes, and references with no size, join the nearest main size."""
    lines: dict[tuple[str, str], list[dict]] = defaultdict(list)
    out = []
    for ref in refs:
        by_ref = ref_line(ref["brand"], ref["reference"])
        if by_ref:
            ref["line"] = by_ref
            lines[(compact(ref["brand"]), "ref:" + compact(by_ref))].append(ref)
        else:
            lines[(compact(ref["brand"]), compact(line_name(ref["model"])))].append(ref)
    for (_, line), members in lines.items():
        if line.startswith("ref:"):  # the reference already fixes the size
            out.append(merge_line(members, None, sample_keys))
            continue
        sizes = Counter(s for s in map(size_of_ref, members) if s)
        known = sum(sizes.values())
        main = [s for s, n in sizes.items() if n >= 3 and n >= 0.1 * known] or [s for s, _ in sizes.most_common(1)]
        default = sizes.most_common(1)[0][0] if sizes else None
        nearest = lambda s: min(main, key=lambda m: (abs(m - s), -sizes[m]))  # noqa: E731
        groups: dict[int | None, list[dict]] = defaultdict(list)
        for r in members:
            size = size_of_ref(r) or default
            groups[nearest(size) if size is not None else None].append(r)
        for size, group in groups.items():
            # Two hand-made samples in one group: each stays its own item, so its id is kept.
            for sample in [r for r in group if r["key"] in sample_keys][1:]:
                group.remove(sample)
                out.append(merge_line([sample], size if len(groups) > 1 else None, sample_keys))
            out.append(merge_line(group, size if len(groups) > 1 else None, sample_keys))
    return out


def merge_line(group: list[dict], size: int | None, sample_keys: set[str]) -> dict:
    top = max(group, key=lambda r: (r["key"] in sample_keys, r.get("listings", 0)))
    col = lambda f: [r.get(f) for r in group]  # noqa: E731
    model = most_common([line_name(m) for m in col("model")]) or top["model"]
    sizes = Counter(r["caseSize"] for r in group if r.get("caseSize"))
    references = [top["reference"]] + sorted(
        {v for r in group for v in [r["reference"], *r.get("variants", [])]} - {top["reference"]})
    name = " ".join(p for p in (top["brand"], model, top.get("line")) if p) + (f" {size} mm" if size else "")
    return {
        "key": top["key"] if top["key"] in sample_keys else slug(name),
        "name": name,
        "brand": top["brand"],
        "model": model,
        "reference": top["reference"],
        "variants": references[1:],
        "movement": most_common(col("movement")) or "",
        "caseSize": size or (sizes.most_common(1)[0][0] if sizes else None),
        "caseMaterial": most_common(col("caseMaterial")) or "",
        "waterResistance": most_common(col("waterResistance")),
        "complications": top.get("complications", []),
        "dialColor": most_common(col("dialColor")) or "",
        "bracelet": most_common(col("bracelet")) or "",
        "bezel": most_common(col("bezel")) or "",
        "gender": most_common(col("gender")) or "",
        "year": min((y for y in col("year") if y), default=None),
    }


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
