# Catalog backfill: where the watches come from

The first catalog had 20 hand-made sample watches. On 2026-11-03 it was replaced by about 23,300 references built from public datasets. The same day, references were merged twice to remove near-duplicates:

1. Colour and strap variants were merged into one base reference (19,712 watches).
2. References were merged into **one watch per model line and main case size**: "Rolex Datejust 36 mm" and "Rolex Datejust 41 mm", not 144 Datejust references. That leaves **2,131 watches**.

This file explains where each fact comes from, how the data was merged, and how to rebuild it.

## Sources

| Source | What we take | Licence |
|---|---|---|
| [Timepiece Treasures](https://www.kaggle.com/datasets/yoerireumkens/timepiece-treasures-a-luxury-watches-dataset) (Kaggle, 163k market listings) | The list of watches: brand, model, reference, movement, case, dial, bezel and strap | CC0 |
| [Luxury Watch Listings](https://www.kaggle.com/datasets/philmorekoung11/luxury-watch-listings) (Kaggle, 284k listings) | Case size, gender, year | "Free to use"; scraped from Chrono24 |
| [Luxury Watches Price](https://www.kaggle.com/datasets/rkiattisak/luxury-watches-price-dataset) (Kaggle, 507 rows) | Typical water resistance and case size per model family | CC BY 4.0, credited in Settings |
| [Wikidata](https://www.wikidata.org) / [Wikimedia Commons](https://commons.wikimedia.org) | One photo per model family (e.g. Submariner) | Each photo's own CC licence; author and licence are shown on the item page |
| `data/sample.json` | The first 20 items (`t1`…`t20`) | Our own |

The listings were scraped from marketplaces (mostly Chrono24). Only facts are used (brand, reference, materials, sizes). The owner accepted the risk.

## How the data was merged

`scripts/niche/build_items.py` does it, with no extra Python packages.

1. **Clean the reference.** It drops seller notes typed into the field ("116500LN -- 05-2017", "116503 FULL SET", "(NEW"), spaces around separators ("5167R- 001"), and rows whose "reference" is a listing title.
2. **One item per base model.** Colour and strap variants share a base reference, cut per brand:

   | Brand | Variant | Base |
   |---|---|---|
   | Rolex, Tudor | `116500LN-0001`, `116500LN 0523` | `116500LN` |
   | Omega | `210.30.42.20.01.001` | `210.30.42.20` |
   | Audemars Piguet, TAG Heuer | `25721ST.OO.1000ST.01`, `WAZ111A-BA0875` | `25721ST`, `WAZ111A` |
   | Patek Philippe | `5196G-001` | `5196G` |
   | Tissot, Longines | `T137.407.11.041.00` | `T137.407.11` |
   | Hublot | `511.NO.1181.RX` | `511.NO` |
   | Breitling, IWC | `AB0138211B1P1`, `IW371605` | `AB0138`, `IW3716` |
   | Zenith | `03.3100.3600/69.M3100` | `03.3100.3600` |

   A Rolex or Tudor reference written without its letters ("116500") joins its most listed lettered one ("116500LN"). Other brands keep the reference as listed.
3. **Each spec takes its most common value** across the model's listings: movement, case material, dial colour, bezel, strap.
4. **Other references:** the official variant references (e.g. `116500LN-0001`) are kept on the item as "Other references", so searching for any of them finds the watch.
5. **One watch per model line and main size.** References of the same brand and model line merge into one watch. The line is the model name without its size: "Datejust 41" and "Datejust 36" are the line "Datejust"; "Navitimer 01 (46 MM)" is "Navitimer 01".
   - A line is split by case size only for its **main sizes**: those with at least 3 references and 10% of the line. Sizes come from the model name when it has one, else from the listings, which are noisy. Rare sizes, and references with no size, join the nearest main size.
   - The name shows the size only when the line has more than one ("Rolex Datejust 41 mm", but "Rolex Explorer").
   - The watch shows its most listed reference as Reference, and every other reference of the line under "Other references".
   - Each spec takes its most common value across the merged references; the year is the earliest.
6. **Complications** come from the model name (Chronograph, GMT, Day-Date, Perpetual Calendar…).
7. **Case size, gender and year** come from the second listing set, matched by brand + base reference. The year is the earliest one seen at least twice.
8. **Family defaults:** water resistance, and case size when missing, come from the third dataset, matched by brand and the start of the model name. They are typical values, not the reference's own.
9. **The 20 samples keep their ids.** The sample's hand-entered facts win where they exist. Two samples never merge into one watch.
10. **Photos:** `scripts/niche/fetch_images.py` finds Wikidata watch models with a photo (37 families, 21 photos) and shows a family's photo on every reference whose model starts with that family name.

## Result

| | |
|---|---|
| Watches | 2,131, from 159 brands |
| References behind them | about 19,700 base references (23,842 references listed under "Other references") |
| With case size | 1,178 |
| With water resistance | 516 |
| With gender / year | 1,021 / 1,055 |
| With complications | 402 |
| With a family photo | 171 |

## Known limits

- Specs come from listings, not from the makers. Half of the watches have no case size, and two thirds have no water resistance.
- The model line comes from the listings' model names, so a few lines still have more than one name for the same watch (e.g. "Navitimer 01" and "Navitimer 1 B01 Chronograph").
- Specs are the most common value across many references, so a merged watch shows its typical dial and strap, not every option.
- No calibre, and no photo per reference: that would need a paid source (e.g. the WatchBase data feed) or user photos.

## Rebuild

```bash
bash scripts/niche/fetch_sources.sh                 # downloads to data/raw/ (git-ignored), checks sha256
python3 scripts/niche/build_items.py                # → data/items.json
/tmp/img/bin/python scripts/niche/fetch_images.py   # optional, needs Pillow: photos → data/raw/images/
python3 scripts/niche/build_items.py && npm run catalog
bash scripts/niche/upload_images.sh                 # owner only: photos → R2 bucket erickmob-cdn
python3 -m unittest discover -s scripts/niche       # tests of these scripts
```

Ids in `data/ids.json` never change once users have them. Image numbers never point to another photo (the CDN caches them for a year), so never delete `data/image_credits.json` before running `fetch_images.py` again.
