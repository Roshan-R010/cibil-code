import re
import pdfplumber
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# REGEX PATTERNS
# ─────────────────────────────────────────────────────────────

DATE_PATTERN    = re.compile(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}')
TYPE_PATTERN    = re.compile(r'\b(DEBIT|CREDIT)\b')
AMOUNT_PATTERN  = re.compile(r'₹([0-9,]+)')
TXN_ID_PATTERN  = re.compile(r'Transaction ID\s+(T\w+)')
UTR_PATTERN     = re.compile(r'UTR No\.\s+(\w+)')
TIME_PREFIX     = re.compile(r'^\d{2}:\d{2}\s+(AM|PM)\s*')

# KEY FIX: stop capturing at DEBIT/CREDIT using negative lookahead
PAID_TO_PATTERN = re.compile(r'Paid to\s*((?:(?!DEBIT|CREDIT).)*)', re.IGNORECASE)
RECV_PATTERN    = re.compile(r'Received from\s*((?:(?!DEBIT|CREDIT).)*)', re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# VERIFY
# ─────────────────────────────────────────────────────────────

def verify_phonepe_statement(text: str) -> bool:
    text_lower = text.lower()
    return 'phonepe' in text_lower and 'transaction statement' in text_lower


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def parse_amount(text: str) -> float:
    match = AMOUNT_PATTERN.search(text)
    if match:
        return float(match.group(1).replace(',', ''))
    return 0.0


def parse_date(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str.strip(), "%b %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return date_str.strip()


def is_metadata(line: str) -> bool:
    return (
        not line or
        'Transaction ID' in line or
        'UTR No' in line or
        'paid by' in line.lower() or
        'credited to' in line.lower() or
        bool(TYPE_PATTERN.search(line)) or
        bool(AMOUNT_PATTERN.search(line)) or
        bool(DATE_PATTERN.match(line))
    )


# ─────────────────────────────────────────────────────────────
# MAIN PARSER
# ─────────────────────────────────────────────────────────────

def parse_phonepe_pdf(pdf_path: str) -> list[dict]:
    transactions = []
    full_text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    if not verify_phonepe_statement(full_text):
        raise ValueError("Not a valid PhonePe statement.")

    lines = full_text.split('\n')

    for i, line in enumerate(lines):

        # Must start with a date
        if not DATE_PATTERN.match(line):
            continue

        # Must have DEBIT or CREDIT
        type_match = TYPE_PATTERN.search(line)
        if not type_match:
            continue

        txn_type = type_match.group(1)
        date_str = parse_date(line[:12])
        amount   = parse_amount(line)
        if txn_type == "DEBIT":
            amount = -amount

        # Extract merchant — regex stops at DEBIT/CREDIT
        paid_match = PAID_TO_PATTERN.search(line)
        recv_match = RECV_PATTERN.search(line)

        if paid_match:
            raw = paid_match.group(1).strip()
        elif recv_match:
            raw = recv_match.group(1).strip()
        else:
            continue

        # If raw is empty, merchant name is on the next line(s)
        # e.g. "Mar 06, 2026 Paid to DEBIT ₹63"
        #      "04:17 PM METROPOLITAN TRANSPORT CORPORATION"
        #      "CHENNAI"
        if not raw:
            name_parts = []
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j].strip()
                # Strip time prefix: "04:17 PM METROPOLITAN..." → "METROPOLITAN..."
                next_line = TIME_PREFIX.sub('', next_line).strip()
                if is_metadata(next_line):
                    break
                if next_line:
                    name_parts.append(next_line)
            raw = ' '.join(name_parts).strip()

        if not raw:
            raw = "Unknown"

        transactions.append({
            "datetime":        date_str,
            "raw_description": raw,
            "type":            txn_type,
            "amount":          amount,
            "merchant":        None,
            "category":        None,
            "source":          "phonepe",
        })
        # Remove duplicates — same date + amount + type = duplicate
        seen = set()
        unique = []
        for t in transactions:
            key = (t['datetime'], t['amount'], t['type'])
            if key not in seen:
                seen.add(key)
                unique.append(t)
        transactions = unique

    return transactions

    return transactions


# ─────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "phonepe_statement.pdf"

    try:
        txns = parse_phonepe_pdf(pdf_path)
        print(f"Found {len(txns)} transactions\n")
        print(f"{'Date':<14} {'Description':<42} {'Type':<8} {'Amount':>10}")
        print("-" * 78)
        for t in txns:
            sign = "+" if t['type'] == 'CREDIT' else "-"
            print(
                f"{t['datetime']:<14} "
                f"{t['raw_description'][:40]:<42} "
                f"{t['type']:<8} "
                f"{sign}₹{abs(t['amount']):>8,.0f}"
            )
    except ValueError as e:
        print(f"Error: {e}")