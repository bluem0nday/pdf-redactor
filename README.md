<div align="center">

# PDF Redactor

### A Claude Code skill for true PDF redaction

**The text is removed — not just covered up.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-3.2-brightgreen.svg)](../../releases/latest)
[![Python](https://img.shields.io/badge/python-3-blue.svg)](https://www.python.org)
[![Claude Code](https://img.shields.io/badge/Claude_Code-skill-blueviolet.svg)](https://claude.ai/code)

</div>

Permanently redact words and names from PDFs. Removes text directly from the PDF content stream — recipients cannot select, copy, search for, or recover redacted content.

Built as a skill for [Claude Code](https://claude.ai/code).

## What it does

- Finds every occurrence of your redaction terms across all pages
- Removes the actual text data from the PDF content stream (not just a visual overlay)
- Handles PDFs that split words across operators with kerning adjustments
- Normalizes Unicode ligatures (fl, fi, ff, ffi, ffl, st) before matching
- Produces a redaction log showing what was removed and where
- Non-redacted text stays fully selectable

## Install

### Option 1: Download the skill file

Download `pdf-redactor.skill` from the [latest release](../../releases/latest) and install it in Claude Code.

### Option 2: Install from source

Clone this repo and copy the `SKILL.md` and `scripts/` directory into your Claude Code skills folder:

```bash
git clone https://github.com/bluem0nday/pdf-redactor.git
```

## Dependencies

The redaction script uses two Python libraries:

- [pikepdf](https://pikepdf.readthedocs.io/) — PDF content stream manipulation
- [pdfplumber](https://github.com/jsvine/pdfplumber) — text extraction and location finding

```bash
pip install pikepdf pdfplumber
```

These are pre-installed in the Claude Code Cowork VM.

## How it works

1. **pdfplumber** scans each page for your redaction terms at the character level
2. **pikepdf** parses the PDF content stream, buffers all operators between BT/ET text blocks, concatenates decoded text (with ligature normalization), and replaces matching text operators with space characters
3. The result is a PDF where redacted text is genuinely gone from the file — not hidden under a box, but removed from the data

## Limitations

- Password-protected PDFs must be unlocked first
- Scanned PDFs (image-only, no selectable text) require OCR before redaction
- Fonts without a ToUnicode CMap cannot be decoded; text may remain in the stream

## Example usage

Just describe what you want removed — Claude asks for the specifics, confirms the list, runs the redaction, and delivers a clean PDF plus a log of everything removed.

**Redact names from a contract before sharing with someone:**
> "Remove the names Dale Cooper and Audrey Horne everywhere they appear in this document before I send it to the vendor."

**Anonymize a report with employee addresses:**
> "Strip all the addresses from this HR report — I need a version I can share with the whole team."

**Remove a company name from my competitive analysis:**
> "Redact every mention of Tyrell Corporation from this document."

**Scrub multiple things at once:**
> "This NDA has client names, their company, and their address. Remove all of it before I file it."

**The skill also triggers on plain language — you don't need to use the word "redact":**
> "Make this safe to send." &nbsp; · &nbsp; "Anonymize this." &nbsp; · &nbsp; "Hide the names." &nbsp; · &nbsp; "Block out the addresses."

## License

MIT License — see [LICENSE](LICENSE) for details.

## Author

**Matt MacQueen** — Product Design Leader, NYC
[GitHub](https://github.com/bluem0nday) · [LinkedIn](https://www.linkedin.com/in/mattmacqueen/)
