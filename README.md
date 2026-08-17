# BISMIRPG

BIS report generation tools for MapleStory Idle RPG.

## Current baseline

The current generator is based on the v191 OCR/report workflow and uses a conservative keep-first policy.

Key rules:

- OCR `Equipped` screenshots are authoritative for the actual Basic Preset.
- If the optimiser export has stale Basic IDs, the report flags the mismatch rather than silently trusting it.
- Any item physically shown as Equipped is always protected from UNLOCK.
- Optimiser-selected equipment is never silently substituted.
- Spare keep pools are recalculated fresh from the current export on every run; no old item IDs or pool selections are carried forward.
- Pool allocation is unique and left-to-right: Boss -> Normal -> Evasion -> Accuracy.
- Ring, Ring 2, Face Accessory, Eye Accessory and Necklace keep up to Top 5 per category; other slots keep up to Top 3.
- Boss and Normal pools score the whole item rather than requiring a literal Boss/Normal Damage line. Useful Crit Rate, Crit Damage, target damage, skill levels, Min/Max Damage, Damage, Attack and related lines can all contribute.
- Crit Rate is valued strongly only while the current build is below effective 100% Crit Rate.
- A conservative safety net protects strong recognised multi-line damage combinations and near-best HP/MP/Evasion/Accuracy/Defense rolls. The report intentionally prefers keeping too much gear over recommending deletion of a potentially valuable item.
- Ring, Ring 2, Face Accessory and Necklace receive no artificial scarcity protection just because they are Party Quest items; quality rolls are protected by the ranking/safety rules instead.
- Any 4-substat item is always kept.
- Page 2 groups actions by equipment type, then sorts by true OCR screenshot capture order within that type.
- T/Lv and first visible substat are taken from the matching OCR screenshot record.

## Inputs

The report workflow expects matching files from the same OCR/import state:

- `mapleexport.txt`
- `lock_status.txt`
- `maplelocked.txt`
- `import_review_easyocr_vXXX.csv`

The MapleOCR workflow is intended to package these together as `BIS_stats.zip`.

## Status

The repository now contains the conservative v191 report generator with fresh current-run spare-pool calculation and keep-first safety rules. The current v191 validation run kept 144 of 148 items and produced no UNLOCK recommendations, deliberately favouring false-positive keeps over accidental loss of good gear while the ranking logic is being field-tested.
