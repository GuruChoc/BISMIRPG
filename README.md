# BISMIRPG

BIS report generation tools for MapleStory Idle RPG.

## Current baseline

The current generator is based on the v191 OCR/report workflow.

Key rules:

- OCR `Equipped` screenshots are authoritative for the actual Basic Preset.
- If the optimiser export has stale Basic IDs, the report flags the mismatch rather than silently trusting it.
- Any item physically shown as Equipped is always protected from UNLOCK.
- Ring, Ring 2, Face Accessory and Necklace receive no special scarcity protection. Party Quest items follow the same keep rules as every other slot.
- Keep items are those used by presets, selected by spare keep pools, or protected by the 4-substat always-keep rule.
- Page 2 groups actions by equipment type, then sorts by true OCR screenshot capture order within that type.
- T/Lv and first visible substat are taken from the matching OCR screenshot record.
- Optimiser-selected equipment is never silently substituted.

## Inputs

The report workflow expects matching files from the same OCR/import state:

- `mapleexport.txt`
- `lock_status.txt`
- `maplelocked.txt`
- `import_review_easyocr_vXXX.csv`

The MapleOCR workflow is intended to package these together as `BIS_stats.zip`.

## Status

This repository currently contains the v191 report-generator baseline. Spare keep-pool selection is still encoded in the generator and is the next area to generalise into a fully current-run ranking calculation.
