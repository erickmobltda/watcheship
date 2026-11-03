# Changelog

## 2026-11-03 — One watch per model

**Why:** the first real catalog listed the same watch several times (seller notes in the reference, colour and strap variants).

- Colour and strap variants are merged into one watch per base reference: about 19,700 watches instead of about 23,300. The variant references are listed as "Other references" and found by search.
- How the catalog was built: `data/BACKFILL.md`.

## 2026-11-03 — Real catalog

**Why:** replace the 20 samples with a real catalog built from public datasets.

- Catalog: about 23,000 real references from public market-listing datasets, with gender, dial, strap and bezel as new filters and specs. Materials, colours and complications are now shown in your language. The 20 sample items keep their ids.
- Model-family photos from Wikimedia Commons, credited on the item page.

## 2026-10-30 — First version

**Why:** the first watch app built from the [collector-app-blueprint](https://github.com/erickmobltda/collector-app-blueprint), to try the blueprint end to end.

- Discover, item page, watch box (box & papers), wishlist, ratings with likes, profiles, follows, Following/Everyone feeds, find people, settings, demo account.
- EN and PT-BR, chosen by the user.
- Catalog: 20 sample watches (real brands, illustrative specs) in `data/sample.json`.
