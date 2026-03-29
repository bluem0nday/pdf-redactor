# PDF Redactor — Changelog

---

## v3.2 — March 22, 2026
Fixed date format in Changelog Protocol.

Changed:
- **Date format:** Changed `%d` to `%-d` in the shell command. Why: `%d` pads single-digit days with a leading zero (e.g., "March 09, 2026") — `%-d` removes the padding and matches the natural written format ("March 9, 2026").

---

## v3.1 — March 22, 2026
Added Changelog Protocol section and created this CHANGELOG.md file.

Changed:
- **Changelog Protocol:** Added dedicated `## Changelog Protocol` section to SKILL.md with numbered checklist, shell date command, and explicit format template. Why: the skill had no changelog process at all — edits could be made with no record of what changed or why.
- **CHANGELOG.md created:** Migrated existing v1/v2/v3 history from embedded section at the bottom of SKILL.md into this standalone file. Why: changelog history belongs in its own file, not buried at the end of the skill instructions.

---

## v3 — March 8, 2026
WinAnsi font support.

Changed:
- **Single-byte font handling:** Added support for WinAnsiEncoding and TrueType fonts without ToUnicode. Why: prior versions silently skipped most text in PDFs exported from Word or Google Docs, leaving redaction targets undetected.

---

## v2 — March 8, 2026
Content stream rewrite.

Changed:
- **BT/ET block buffering:** Buffer full text blocks and concatenate before matching instead of per-operator matching. Why: fixes split-Tj kerning patterns (e.g., "Courser" + Td + "a" = "Coursera") that caused missed matches.
- **Unicode ligature normalization:** Normalize ﬂ→fl, ﬁ→fi, ff, ffi, ffl, st before matching. Why: fixes names like "Netflix" which encode as "Net" + ﬂ + "ix" in many PDFs.
- **Removed grey box overlay:** Replaced reportlab overlay approach with clean white gaps. Why: overlay approach left recoverable text underneath; content stream removal is permanent.

---

## v1 — original
Initial version.

- Per-Tj matching with grey box overlays. Failed on split operators, ligatures, and WinAnsi fonts.
