#!/usr/bin/env bash
# Download the raw catalog sources into data/raw/ (git-ignored) and check their checksums.
#   bash scripts/niche/fetch_sources.sh && python3 scripts/niche/build_items.py && npm run catalog
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p data/raw

fetch() { # kaggle-dataset file sha256
  local dir="data/raw/${1//\//_}"
  if [ ! -f "$dir/$2" ]; then
    mkdir -p "$dir"
    curl -fsSL -o "$dir/d.zip" "https://www.kaggle.com/api/v1/datasets/download/$1"
    unzip -oq "$dir/d.zip" -d "$dir" && rm "$dir/d.zip"
  fi
  echo "$3  $dir/$2" | shasum -a 256 -c -
}

# Timepiece Treasures (CC0): 163k listings with brand, model and reference.
fetch yoerireumkens/timepiece-treasures-a-luxury-watches-dataset watch_data.csv 3371c10f5f143834bd84ac5ed2f5567228d0d9e2eb31c28bcac37656a4c44fb3
# Luxury Watch Listings: 284k listings with case size, gender and year.
fetch philmorekoung11/luxury-watch-listings Watches.csv 9c362f80ba31827b5e15f4d9e45eaeaede6dedd76910530bfb2ab9a50887cb72
# Luxury Watches Price (CC BY 4.0, rkiattisak): typical specs per model family.
fetch rkiattisak/luxury-watches-price-dataset "Luxury watch.csv" 92be338dc3c99754ca4e2ce956c80008c905620eb46ff3ee9ae383a22b9bf297
