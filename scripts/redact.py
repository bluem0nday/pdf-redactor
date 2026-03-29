#!/usr/bin/env python3
"""
PDF Redactor — true redaction using pikepdf + pdfplumber.

Strategy:
1. Use pdfplumber to find term locations (for counting/logging)
2. Parse each font's ToUnicode CMap to decode CID-encoded text
3. Buffer text operators between BT/ET blocks, concatenate decoded text
4. Replace matching Tj/TJ operands with space CIDs (removing text from the stream)
5. Normalize Unicode ligatures before matching

Result: redacted text is removed from the content stream.
Redacted areas appear as clean white gaps. Non-redacted text remains fully selectable.
"""

import re
import sys
from pathlib import Path

import pdfplumber
import pikepdf


# ── ToUnicode CMap parsing ──────────────────────────────────────────────────

def parse_tounicode(cmap_bytes):
    """Parse a ToUnicode CMap to build CID -> Unicode and Unicode -> CID mappings."""
    text = cmap_bytes.decode('latin-1')
    cid_to_unicode = {}

    # Parse bfchar entries: <CID> <Unicode>
    for match in re.finditer(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', text):
        cid = int(match.group(1), 16)
        unicode_val = int(match.group(2), 16)
        cid_to_unicode[cid] = chr(unicode_val)

    # Parse bfrange entries: <start> <end> <unicode_start>
    for match in re.finditer(r'beginbfrange\s*(.*?)\s*endbfrange', text, re.DOTALL):
        range_text = match.group(1)
        for rmatch in re.finditer(
            r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', range_text
        ):
            start_cid = int(rmatch.group(1), 16)
            end_cid = int(rmatch.group(2), 16)
            start_unicode = int(rmatch.group(3), 16)
            for i in range(end_cid - start_cid + 1):
                cid_to_unicode[start_cid + i] = chr(start_unicode + i)

    # Build reverse mapping
    unicode_to_cid = {v: k for k, v in cid_to_unicode.items()}

    return cid_to_unicode, unicode_to_cid


def get_font_maps(page):
    """Extract ToUnicode mappings for all fonts on a page."""
    font_cid_to_unicode = {}
    font_unicode_to_cid = {}

    resources = page.get('/Resources', {})
    fonts = resources.get('/Font', {})

    for font_name, font_ref in fonts.items():
        if '/ToUnicode' in font_ref:
            cmap_bytes = font_ref['/ToUnicode'].read_bytes()
            c2u, u2c = parse_tounicode(cmap_bytes)
            font_cid_to_unicode[str(font_name)] = c2u
            font_unicode_to_cid[str(font_name)] = u2c

    return font_cid_to_unicode, font_unicode_to_cid


def decode_cid_string(text_bytes, cid_to_unicode):
    """Decode a CID-encoded byte string to Unicode text."""
    decoded = ''
    for j in range(0, len(text_bytes), 2):
        if j + 1 < len(text_bytes):
            cid = (text_bytes[j] << 8) | text_bytes[j + 1]
            decoded += cid_to_unicode.get(cid, '\ufffd')
    return decoded


def encode_space_string(length, unicode_to_cid):
    """Create a CID-encoded byte string of spaces with the given character count."""
    space_cid = unicode_to_cid.get(' ', 0x0003)  # fallback to common space CID
    result = b''
    for _ in range(length):
        result += bytes([(space_cid >> 8) & 0xFF, space_cid & 0xFF])
    return result


# ── Find term locations using pdfplumber (for counting/logging) ──────────

def find_term_locations(pdf_path, terms):
    """Find each occurrence of each term using pdfplumber text extraction."""
    results = []
    pdf = pdfplumber.open(pdf_path)

    for page_idx, page in enumerate(pdf.pages):
        chars = page.chars
        if not chars:
            continue

        full_text = "".join(c["text"] for c in chars)
        full_text_lower = full_text.lower()

        for term in terms:
            term_lower = term.lower()
            start = 0
            while True:
                pos = full_text_lower.find(term_lower, start)
                if pos == -1:
                    break
                results.append({"term": term, "page": page_idx})
                start = pos + 1

    pdf.close()
    return results


# ── Content stream text removal ─────────────────────────────────────────────

def expand_terms_to_words(terms_lower):
    """Expand multi-word terms into individual words for matching against split Tj operators.
    Only expands words that are 3+ chars to avoid false positives (e.g., 'st', 'ny')."""
    # Full terms for substring matching
    full_terms = set(terms_lower)
    # Individual words for exact matching only (to handle split Tj operators)
    exact_words = set()
    for term in terms_lower:
        for word in term.split():
            word = word.strip('.,;:')
            if word and len(word) >= 3:  # skip short words like 'st', 'ny', '2a'
                exact_words.add(word)
    return full_terms, exact_words


def blank_tj_operands(operands, operator, font_unicode_to_cid, current_font):
    """Replace text in a Tj or TJ operator with spaces."""
    op = str(operator)
    unicode_to_cid = font_unicode_to_cid.get(current_font, {})

    if op == 'Tj':
        text_bytes = bytes(operands[0])
        char_count = len(text_bytes) // 2
        space_bytes = encode_space_string(char_count, unicode_to_cid)
        return ([pikepdf.String(space_bytes)], operator)
    elif op == 'TJ':
        arr = operands[0]
        new_arr = pikepdf.Array()
        for elem in arr:
            if isinstance(elem, pikepdf.String):
                text_bytes = bytes(elem)
                char_count = len(text_bytes) // 2
                space_bytes = encode_space_string(char_count, unicode_to_cid)
                new_arr.append(pikepdf.String(space_bytes))
            else:
                new_arr.append(elem)
        return ([new_arr], operator)
    return (operands, operator)


def decode_instruction_text(operands, operator, cid_to_unicode):
    """Decode the text content of a Tj or TJ operator."""
    op = str(operator)
    if op == 'Tj':
        return decode_cid_string(bytes(operands[0]), cid_to_unicode)
    elif op == 'TJ':
        decoded = ''
        for elem in operands[0]:
            if isinstance(elem, pikepdf.String):
                decoded += decode_cid_string(bytes(elem), cid_to_unicode)
        return decoded
    return ''


LIGATURE_MAP = {
    '\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl',
    '\ufb03': 'ffi', '\ufb04': 'ffl', '\ufb06': 'st',
}

def normalize_ligatures(text):
    """Replace common Unicode ligatures with their ASCII equivalents."""
    for lig, repl in LIGATURE_MAP.items():
        text = text.replace(lig, repl)
    return text


def remove_text_from_stream(pdf, page_idx, terms_lower, font_cid_to_unicode, font_unicode_to_cid):
    """
    Walk the content stream, buffer text operators between BT/ET blocks,
    concatenate their decoded text, and blank all Tj/TJ ops in the block
    if the concatenated text contains a redaction term.

    This handles PDFs that split words across multiple Tj operators with
    Td kerning adjustments in between (e.g., 'Courser' + Td + 'a' = 'Coursera').
    Also normalizes Unicode ligatures (e.g., ﬂ → fl) before matching.
    """
    page = pdf.pages[page_idx]
    page.contents_coalesce()

    full_terms, exact_words = expand_terms_to_words(terms_lower)

    instructions = list(pikepdf.parse_content_stream(page))
    current_font = None
    modified = False

    new_instructions = []
    in_text_block = False
    text_block_buffer = []  # list of (operands, operator, decoded_text_or_None)

    for operands, operator in instructions:
        op = str(operator)

        if op == 'BT':
            in_text_block = True
            text_block_buffer = [(operands, operator, None)]
            continue

        if op == 'ET':
            text_block_buffer.append((operands, operator, None))

            # Concatenate all decoded text in this BT..ET block
            block_text = ''
            for buf_ops, buf_op, buf_decoded in text_block_buffer:
                if buf_decoded is not None:
                    block_text += buf_decoded

            block_text_lower = normalize_ligatures(block_text.lower())

            # Check if concatenated block text contains any redaction term
            block_has_match = False
            for term in full_terms:
                if term in block_text_lower:
                    block_has_match = True
                    break

            if not block_has_match:
                for word in exact_words:
                    if word in block_text_lower:
                        block_has_match = True
                        break

            if block_has_match:
                # Blank all Tj/TJ operators in this block
                for buf_ops, buf_op, buf_decoded in text_block_buffer:
                    bop = str(buf_op)
                    if bop in ('Tj', 'TJ') and current_font in font_cid_to_unicode:
                        blanked = blank_tj_operands(buf_ops, buf_op, font_unicode_to_cid, current_font)
                        new_instructions.append(blanked)
                        modified = True
                    else:
                        new_instructions.append((buf_ops, buf_op))
            else:
                # No match — pass through unchanged
                for buf_ops, buf_op, buf_decoded in text_block_buffer:
                    new_instructions.append((buf_ops, buf_op))

            in_text_block = False
            text_block_buffer = []
            continue

        if in_text_block:
            if op == 'Tf':
                current_font = str(operands[0])
                text_block_buffer.append((operands, operator, None))
                continue

            if op in ('Tj', 'TJ') and current_font in font_cid_to_unicode:
                cid_to_unicode = font_cid_to_unicode[current_font]
                decoded = decode_instruction_text(operands, operator, cid_to_unicode)
                text_block_buffer.append((operands, operator, decoded))
            else:
                text_block_buffer.append((operands, operator, None))
            continue

        # Outside text block
        if op == 'Tf':
            current_font = str(operands[0])

        new_instructions.append((operands, operator))

    if modified:
        new_stream = pikepdf.unparse_content_stream(new_instructions)
        page.Contents = pdf.make_stream(new_stream)

    return modified


# ── Main redaction pipeline ─────────────────────────────────────────────────

def redact_pdf(input_path, output_path, terms):
    """Full redaction pipeline: find locations, remove text."""

    terms_lower = [t.lower() for t in terms]

    # Step 1: Find locations
    print("Finding term locations...")
    locations = find_term_locations(input_path, terms)

    print(f"Found {len(locations)} instances")
    by_term = {}
    for loc in locations:
        by_term.setdefault(loc["term"], []).append(loc)
    for term in sorted(by_term):
        print(f"  '{term}': {len(by_term[term])}")

    if not locations:
        print("Nothing to redact.")
        return 0

    # Get unique pages that need processing
    pages_to_process = sorted(set(loc["page"] for loc in locations))

    # Step 2: Open PDF with pikepdf and process each page
    print("\nRemoving text from content streams...")
    pdf = pikepdf.open(input_path)

    for page_idx in pages_to_process:
        page = pdf.pages[page_idx]

        # Get font mappings for this page
        font_c2u, font_u2c = get_font_maps(page)

        # Remove text from content stream
        was_modified = remove_text_from_stream(pdf, page_idx, terms_lower, font_c2u, font_u2c)
        if was_modified:
            print(f"  Page {page_idx + 1}: text removed from stream")
        else:
            print(f"  Page {page_idx + 1}: WARNING - could not modify stream")

    # Save
    pdf.save(output_path, linearize=True)
    pdf.close()

    return len(locations)


def build_log(locations, input_name):
    """Build a redaction log."""
    lines = [f"REDACTION LOG — {input_name}", "=" * 50, ""]
    by_term = {}
    for loc in locations:
        by_term.setdefault(loc["term"], []).append(loc)
    for term in sorted(by_term):
        insts = by_term[term]
        pages = sorted(set(i["page"] + 1 for i in insts))
        lines.append(
            f"  '{term}': {len(insts)} instance(s) — page(s) {', '.join(str(p) for p in pages)}"
        )
    lines += ["", f"TOTAL REDACTIONS: {len(locations)}"]
    return "\n".join(lines)


def main():
    input_path = sys.argv[1]
    output_dir = sys.argv[2]
    terms_str = sys.argv[3]

    terms = [t.strip() for t in terms_str.split("|") if t.strip()]

    print(f"Input: {input_path}")
    print(f"Terms: {terms}")

    stem = Path(input_path).stem
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = out_dir / f"{stem}_REDACTED.pdf"
    out_log = out_dir / f"{stem}_redaction_log.txt"

    count = redact_pdf(input_path, str(out_pdf), terms)

    if count > 0:
        # Rebuild locations for log
        locations = find_term_locations(input_path, terms)
        log_text = build_log(locations, Path(input_path).name)
        with open(out_log, "w") as f:
            f.write(log_text)

        print(f"\nRedacted PDF: {out_pdf}")
        print(f"Log: {out_log}")
        print(f"Total: {count}")
    else:
        print("No redactions applied.")


if __name__ == "__main__":
    main()
