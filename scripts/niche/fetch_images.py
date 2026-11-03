"""Find licensed model-family photos on Wikidata/Wikimedia Commons and prepare them for the image CDN.

No open source has a photo per reference, so a family photo (e.g. "Rolex Submariner")
is shown on every reference of that family. Commons photos are CC BY / CC BY-SA:
each one is credited on the item page (data/image_credits.json → catalog column imageCredit).

Writes:
  data/raw/images/<n>.webp     the photos to upload (git-ignored)
  data/images.json             item key → image number (read by build_items.py)
  data/image_credits.json      image number → {author, license, url}
  data/image_backgrounds.json  image number → edge colour, or null
Image numbers never change once given: the CDN caches them forever.

Needs Pillow:
  python3 -m venv /tmp/img && /tmp/img/bin/pip install pillow
  /tmp/img/bin/python scripts/niche/fetch_images.py
  python3 scripts/niche/build_items.py && npm run catalog
Then upload data/raw/images/ to the R2 bucket erickmob-cdn under <app>/ (see README).
"""

import html
import io
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent.parent
FAMILIES = ROOT / "data/raw/wikidata_watches.json"
OUT = ROOT / "data/raw/images"
IMAGES = ROOT / "data/images.json"
CREDITS = ROOT / "data/image_credits.json"
BACKGROUNDS = ROOT / "data/image_backgrounds.json"
AGENT = "Watcheship-catalog/1.0 (https://watcheship.erickmob.dev)"
WIDTH = 500  # one of Commons' standard thumbnail widths
QUERY = """SELECT DISTINCT ?w ?wLabel ?mLabel ?img WHERE {
  { ?w wdt:P31/wdt:P279* wd:Q178794 } UNION { ?w wdt:P279+ wd:Q178794 }
  ?w wdt:P18 ?img .
  OPTIONAL { ?w wdt:P176 ?m }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""


def get(url: str) -> bytes:
    for attempt in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENT}), timeout=60).read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3)


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def families(brands: list[str]) -> dict[tuple[str, str], str]:
    """(brand, family) → Commons file name, for Wikidata watch models whose label or maker is one of our brands."""
    if not FAMILIES.exists():
        url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(QUERY)
        FAMILIES.write_text(get(url).decode())
    by_length = sorted(brands, key=lambda b: -len(compact(b)))
    found = {}
    for row in json.loads(FAMILIES.read_text())["results"]["bindings"]:
        label, maker = row["wLabel"]["value"], row.get("mLabel", {}).get("value", "")
        # The brand starts the label ("Rolex Submariner"), or is the maker ("Reverso", made by Jaeger-LeCoultre).
        brand = next((b for b in by_length if compact(label).startswith(compact(b))), None) or next(
            (b for b in by_length if maker and compact(maker).startswith(compact(b))), None)
        if not brand or (maker and not compact(maker).startswith(compact(brand))):
            continue
        family = re.sub(rf"^{re.escape(brand)}\s*", "", label, flags=re.I).strip()
        if family:  # a bare brand would put one photo on every watch it makes
            found.setdefault((brand, family), urllib.parse.unquote(row["img"]["value"].rsplit("/", 1)[1]))
    return found


def commons(file: str) -> tuple[str, dict]:
    """(thumbnail url, credit) from the Commons API."""
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo"
           f"&iiprop=url|extmetadata&iiurlwidth={WIDTH}&titles=" + urllib.parse.quote(f"File:{file}"))
    page = next(iter(json.loads(get(api))["query"]["pages"].values()))
    info = page["imageinfo"][0]
    meta = info.get("extmetadata", {})
    author = html.unescape(re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", ""))).strip().split("\n")[0].strip()
    licence = meta.get("LicenseShortName", {}).get("value", "")
    return info["thumburl"], {"author": author or "Wikimedia Commons", "license": licence, "url": info["descriptionurl"]}


def bucket(p):
    return (p[0] // 16, p[1] // 16, p[2] // 16)


def background(img: Image.Image) -> str | None:
    """Same rule as the Smokership script: the edge colour that covers at least half of the edge."""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    edge = [px[0, y] for y in range(h)] + [px[w - 1, y] for y in range(h)] + [px[x, 0] for x in range(w)] + [px[x, h - 1] for x in range(w)]
    if any(p[3] < 250 for p in edge):
        return None
    top, n = Counter(bucket(p) for p in edge).most_common(1)[0]
    if n / len(edge) < 0.5:
        return None
    r, g, b, _ = Counter(p for p in edge if bucket(p) == top).most_common(1)[0][0]
    return f"#{r:02x}{g:02x}{b:02x}"


def main():
    items = json.loads((ROOT / "data/items.json").read_text())
    photos = families(sorted({i["brand"] for i in items}))
    credits = json.loads(CREDITS.read_text()) if CREDITS.exists() else {}
    backgrounds = json.loads(BACKGROUNDS.read_text()) if BACKGROUNDS.exists() else {}
    number_of = {c["url"]: int(n) for n, c in credits.items()}
    next_n = max(map(int, credits), default=0) + 1
    by_file: dict[str, int] = {}
    images = {}
    OUT.mkdir(parents=True, exist_ok=True)
    for item in items:
        model = compact(item["model"])
        # The longest family name that starts the model wins: "Speedmaster Professional" over "Speedmaster".
        fits = [(len(compact(f)), file) for (b, f), file in photos.items() if b == item["brand"] and model.startswith(compact(f))]
        if not fits:
            continue
        file = max(fits)[1]
        if file not in by_file:
            thumb, credit = commons(file)
            if credit["url"] not in number_of:
                number_of[credit["url"]], next_n = next_n, next_n + 1
            n = by_file[file] = number_of[credit["url"]]
            out = OUT / f"{n}.webp"
            if not out.exists():
                img = Image.open(io.BytesIO(get(thumb))).convert("RGB")
                img.save(out, "WEBP", quality=80, method=6)
                backgrounds[str(n)] = background(img)
            credits[str(n)] = credit
        images[item["key"]] = by_file[file]
    IMAGES.write_text(json.dumps(dict(sorted(images.items())), indent=2) + "\n")
    CREDITS.write_text(json.dumps(dict(sorted(credits.items(), key=lambda kv: int(kv[0]))), indent=2, ensure_ascii=False) + "\n")
    BACKGROUNDS.write_text(json.dumps(dict(sorted(backgrounds.items(), key=lambda kv: int(kv[0]))), indent=0) + "\n")
    print(f"families with a photo {len(photos)} · items with a photo {len(images)} · images {len(by_file)}")


if __name__ == "__main__":
    main()
