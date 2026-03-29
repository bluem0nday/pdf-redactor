---
name: pdf-redactor
description: >
  Redacts words and names from PDF files by permanently removing the underlying
  text data from the content stream. Recipients cannot select, copy, or recover
  redacted content. Non-redacted text remains fully selectable. Use this skill
  whenever the user wants to redact, remove, or hide specific names, words, or
  phrases from a PDF — even if they phrase it as "censor", "hide", "remove names
  from", "make safe to send", "anonymize", or "block out". Also trigger when the
  user uploads a PDF and mentions any words or names they don't want visible.
---

# PDF Redactor

Permanently redact words and names from PDFs. Removes the underlying text from the
PDF content stream — recipients cannot select, copy, search for, or recover redacted
content. Redacted areas appear as clean white gaps. Non-redacted text remains fully
selectable.

## What you produce

1. **Redacted PDF** — text permanently removed; redacted areas left as white space
2. **Redaction log** — plain text summary: each term, how many times it was redacted, and which pages

## Inputs

- A PDF file (from the user's upload or filesystem)
- A list of words/names to redact (gathered from the user — see Step 1)

## Workflow

### Step 1 — Ask the user what to redact

**Do not skip this step.** When the user uploads a PDF, use AskUserQuestion with this
exact structure:

```
Question: "What do you want to redact from this PDF?"
Header: "Redact"
multiSelect: true
Options:
  - label: "People's names"
    description: "I'll ask you for the specific names next"
  - label: "Company or org names"
    description: "I'll ask you for the specific companies next"
  - label: "Addresses"
    description: "Street addresses, cities, zip codes, etc."
  - label: "Other words or phrases"
    description: "Any specific text you want removed"
```

After the user selects categories, ask a **single follow-up message** (not another
AskUserQuestion) requesting the specific terms for each category they selected. Example:

> "Please list the specific [names / companies / addresses / words] you want redacted,
> separated by commas."

Collect all terms into a single list. Before running the script, confirm the final list
with the user in a short summary.

**Common-word warning:** If any term the user provides is also a common English word
(e.g., "Will", "May", "Grace", "Mark", "Hope", "Joy", "Art", "Chase", "Rich"), flag it:
"Heads up — '[term]' is also a common word. This will redact every occurrence, including
normal usage like 'will you...' — want me to include it?"

### Step 2 — Run the redaction script

Use the bundled script at `scripts/redact.py`. It uses **pikepdf** and **pdfplumber**
— both pre-installed in the Cowork VM. No additional installs needed.

Run it:
```bash
python scripts/redact.py <input-pdf> <output-dir> "term1|term2|term3"
```

Terms are pipe-separated (`|`), not comma-separated (since terms can contain commas,
like addresses).

The script produces:
- `<original-filename>_REDACTED.pdf` — the safe-to-send file
- `<original-filename>_redaction_log.txt` — the audit log

### Step 3 — Verify the redaction

**Do not skip this step.** After the script runs, extract text from the redacted PDF
and confirm that every redacted term is gone. Use pdfplumber:

```python
import pdfplumber
pdf = pdfplumber.open("<redacted-pdf-path>")
full_text = ""
for page in pdf.pages:
    full_text += (page.extract_text() or "")
pdf.close()

# Check each term
for term in terms:
    count = full_text.lower().count(term.lower())
    if count > 0:
        print(f"WARNING: '{term}' still found {count} time(s)")
    else:
        print(f"OK: '{term}' fully removed")
```

If any terms are still found, tell the user which ones and that the text could not be
fully removed from the content stream. Be transparent about this limitation.

### Step 4 — Deliver to user

Save both files to the session's outputs folder and present them with computer:// links.

Tell the user:
- How many total redactions were applied
- Whether all terms were fully removed from the content stream (from Step 3)
- That non-redacted text remains fully selectable

---

## Technical notes

The script uses **pikepdf** + **pdfplumber**:

1. **pdfplumber** finds each term via character-level text search (for counting/logging)
2. **pikepdf** buffers all operators between BT/ET text blocks, concatenates their
   decoded text (with ligature normalization), and replaces matching Tj/TJ operators
   with space characters

This approach handles PDFs that split words across multiple Tj operators with Td kerning
adjustments in between (e.g., 'Courser' + Td + 'a' = 'Coursera'), and normalizes
Unicode ligatures (fl, fi, ff, ffi, ffl, st) before matching.

---

## Error handling

- **Password-protected PDF**: Tell the user you can't process it and ask them to unlock it first
- **Scanned PDF (image-only, no selectable text)**: The script will find zero matches. Inform the user — scanned PDFs require OCR first; offer to run OCR via the pdf skill if available
- **Term not found**: Note it in the log as "0 instances found" rather than silently skipping it
- **Font without ToUnicode CMap**: The script cannot decode text for that font. Text may remain in the stream. Warn the user.

---

## Changelog Protocol

Any edit to this skill requires a changelog entry before the session ends — no exceptions.

1. Run `date +"%B %-d, %Y"` in the shell. Use that exact output as the date. Never estimate or hardcode it.
2. Increment the version: patch (x.x+1) for fixes and small edits, minor (x+1.0) for structural changes.
3. Add the new entry at the **top** of `CHANGELOG.md`, above all existing entries, in this format:

```
## v[X.Y] — [date from shell]
[One-line summary of what changed]

Changed:
- **[Label]:** [What changed, and why the old version was wrong or incomplete. The why is mandatory — "updated X" is a useless entry six months later.]
```
