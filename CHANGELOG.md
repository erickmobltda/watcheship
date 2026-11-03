# Changelog

## 2026-11-03 — G-Shock, Seiko and Citizen models are back

**Why:** these brands' listings only name the collection, so the previous change made one "Casio G-Shock" out of 408 references.

- Casio, Seiko, Grand Seiko and Citizen get one watch per model reference again ("Casio G-Shock GA-2100"): about 3,800 watches in all.
- New `data/extra.json` for watches no dataset has; first one: Casio G-Shock Gravitymaster GR-B300-1A.

## 2026-11-03 — One watch per model line

**Why:** the catalog still listed the same watch many times, once per reference.

- One watch per model line and main case size (e.g. "Rolex Datejust 41 mm"): about 2,100 watches instead of about 19,700. Every reference of the line is listed under "Other references" and found by search.

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
