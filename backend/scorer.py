"""
scorer.py
---------
Behavioral credit scoring engine for FinSight.
Generates a CIBIL-range score (300-900) based on:
  - UPI transaction behavior (75% weight)
  - Personal details (25% weight)

Scoring philosophy:
  - Start at base score 600 (average, Fair band)
  - Good behavior adds points
  - Bad behavior subtracts points
  - Final score clamped between 300 and 900
"""

from collections import defaultdict
from datetime import datetime


# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────

BASE_SCORE = 600

ESSENTIAL_CATEGORIES = {"Groceries", "Bills & Utilities", "Transport", "Education", "Healthcare"}
LUXURY_CATEGORIES    = {"Entertainment", "Food & Dining", "Travel", "AI Subscriptions"}
NEUTRAL_CATEGORIES   = {"Shopping", "Personal Transfer", "Tech Subscriptions", "Other"}

EMPLOYMENT_SCORES = {
    "salaried":      +25,
    "banking":       +25,
    "corporate":     +25,
    "self-employed": +10,
    "business":      +10,
    "gig worker":    -5,
    "student":       -5,
    "unemployed":    -20,
}

LOAN_PURPOSE_SCORES = {
    "education": +10,
    "business":  +8,
    "home":      +6,
    "vehicle":   +2,
    "personal":  -5,
}

HOUSING_SCORES = {
    "owned":        +15,
    "family owned": +8,
    "rented":       -5,
}


# ─────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────

def clamp(value: float, min_val: int = 300, max_val: int = 900) -> int:
    return int(max(min_val, min(max_val, value)))


def get_band(score: int) -> str:
    if score >= 750: return "Excellent"
    if score >= 650: return "Good"
    if score >= 500: return "Fair"
    return "Poor"


# ─────────────────────────────────────────────────────────────
# BEHAVIOR SCORING
# ─────────────────────────────────────────────────────────────

def score_savings_ratio(debits, credits) -> tuple[float, str]:
    """
    Savings ratio — max +60, min -80
    How much of income is left after spending.
    """
    total_spent  = sum(abs(t['amount']) for t in debits)
    total_income = sum(t['amount'] for t in credits)

    if total_income == 0:
        return -50, "No income detected"

    ratio = (total_income - total_spent) / total_income

    if ratio >= 0.30:
        return +60, f"Saving {ratio*100:.0f}% of income — excellent"
    elif ratio >= 0.20:
        return +40, f"Saving {ratio*100:.0f}% of income — good"
    elif ratio >= 0.10:
        return +20, f"Saving {ratio*100:.0f}% of income — fair"
    elif ratio >= 0:
        return +5,  f"Saving {ratio*100:.0f}% of income — very low"
    elif ratio >= -0.20:
        return -40, f"Overspending by {abs(ratio)*100:.0f}% — concerning"
    else:
        return -80, f"Overspending by {abs(ratio)*100:.0f}% — serious risk"


def score_essential_vs_luxury(debits) -> tuple[float, str]:
    """
    Essential vs luxury spending — max +40, min -40
    Essentials = groceries, bills, transport, education, healthcare
    Luxury = entertainment, food delivery, travel
    """
    total_spent = sum(abs(t['amount']) for t in debits)
    if total_spent == 0:
        return 0, "No spending data"

    essential = sum(abs(t['amount']) for t in debits if t.get('category') in ESSENTIAL_CATEGORIES)
    luxury    = sum(abs(t['amount']) for t in debits if t.get('category') in LUXURY_CATEGORIES)

    essential_ratio = essential / total_spent
    luxury_ratio    = luxury / total_spent

    score   = 0
    reasons = []

    if essential_ratio >= 0.70:
        score += 40
        reasons.append(f"Essential spending {essential_ratio*100:.0f}% — excellent")
    elif essential_ratio >= 0.50:
        score += 20
        reasons.append(f"Essential spending {essential_ratio*100:.0f}% — good")
    elif essential_ratio >= 0.30:
        score += 0
        reasons.append(f"Essential spending {essential_ratio*100:.0f}% — average")

    if luxury_ratio > 0.60:
        score -= 40
        reasons.append(f"Luxury spending {luxury_ratio*100:.0f}% — too high")
    elif luxury_ratio > 0.40:
        score -= 20
        reasons.append(f"Luxury spending {luxury_ratio*100:.0f}% — high")

    return score, " | ".join(reasons) if reasons else "Neutral spending pattern"


def score_income_consistency(credits) -> tuple[float, str]:
    """
    Income consistency — max +30, min -20
    Multiple income sources = stable = good signal
    """
    if not credits:
        return -20, "No income detected"

    if len(credits) == 1:
        return -10, "Only one income transaction — inconsistent"

    sources = set(t.get('raw_description', '') for t in credits)

    if len(sources) == 1:
        return -10, "All income from one source — dependent income"
    elif len(sources) >= 3:
        return +30, f"Income from {len(sources)} sources — consistent"
    elif len(sources) == 2:
        return +15, "Income from 2 sources — fairly consistent"

    return +5, "Some income consistency"


def score_recurring_payments(transactions) -> tuple[float, str]:
    """
    Recurring payments — max +30, min 0
    Same merchant appearing multiple times = planned, responsible spending
    """
    merchant_count = defaultdict(int)
    for t in transactions:
        if t['type'] == 'DEBIT' and t.get('merchant') and t['merchant'] != 'Unknown':
            merchant_count[t['merchant']] += 1

    recurring = [m for m, count in merchant_count.items() if count >= 2]

    if len(recurring) >= 3:
        return +30, f"{len(recurring)} recurring merchants — excellent payment habits"
    elif len(recurring) >= 1:
        return +15, f"{len(recurring)} recurring merchant(s) — good habit"
    else:
        return 0, "No recurring payments detected"


def score_p2p_ratio(transactions) -> tuple[float, str]:
    """
    P2P transfer ratio — max 0, min -30
    High personal transfers = informal economy dependence = risk
    """
    debits = [t for t in transactions if t['type'] == 'DEBIT']
    if not debits:
        return 0, "No debit transactions"

    p2p   = [t for t in debits if t.get('category') == 'Personal Transfer']
    ratio = len(p2p) / len(debits)

    if ratio > 0.60:
        return -30, f"{ratio*100:.0f}% P2P transfers — high informal spending"
    elif ratio > 0.40:
        return -15, f"{ratio*100:.0f}% P2P transfers — moderate"
    elif ratio > 0.20:
        return -5,  f"{ratio*100:.0f}% P2P transfers — acceptable"
    else:
        return 0,   f"{ratio*100:.0f}% P2P transfers — good"


def score_large_transactions(debits, total_income) -> tuple[float, str]:
    """
    Large transaction flag — max 0, min -30
    Single transaction > 50% of monthly income = risk flag
    """
    if total_income == 0 or not debits:
        return 0, "Cannot evaluate"

    large = [t for t in debits if abs(t['amount']) > total_income * 0.50]

    if len(large) >= 3:
        return -30, f"{len(large)} transactions over 50% of income — high risk"
    elif len(large) == 2:
        return -20, f"{len(large)} large transactions detected"
    elif len(large) == 1:
        return -10, f"1 large transaction detected — minor flag"
    else:
        return 0, "No unusually large transactions"


def score_transaction_frequency(transactions) -> tuple[float, str]:
    """
    Transaction frequency — max +15, min -10
    Active financial life = more data = better scoring visibility
    """
    count = len(transactions)

    if count >= 20:
        return +15, f"{count} transactions — very active"
    elif count >= 10:
        return +8,  f"{count} transactions — active"
    elif count >= 5:
        return +3,  f"{count} transactions — moderate activity"
    else:
        return -10, f"Only {count} transactions — insufficient data"


def score_spending_diversity(debits) -> tuple[float, str]:
    """
    Spending diversity — max +20, min 0
    Spending across many categories = stable, diverse lifestyle
    """
    categories = set(t.get('category') for t in debits if t.get('category'))
    count = len(categories)

    if count >= 6:
        return +20, f"Spending across {count} categories — diverse"
    elif count >= 4:
        return +12, f"Spending across {count} categories — good"
    elif count >= 2:
        return +5,  f"Spending across {count} categories — limited"
    else:
        return 0, "Very limited spending diversity"


# ─────────────────────────────────────────────────────────────
# PERSONAL DETAILS SCORING
# ─────────────────────────────────────────────────────────────

def score_employment(personal: dict) -> tuple[float, str]:
    """Employment type — max +25, min -20"""
    emp_type = personal.get('employment_type', '').lower().strip()
    for key, score in EMPLOYMENT_SCORES.items():
        if key in emp_type:
            return score, f"Employment: {emp_type}"
    return 0, "Employment type unknown"


def score_experience(personal: dict) -> tuple[float, str]:
    """
    Work experience — max +20, min -10
    More years = more stable income history
    """
    try:
        years = float(personal.get('experience', 0))
    except (ValueError, TypeError):
        years = 0

    if years >= 10:
        return +20, f"{years} years experience — very stable"
    elif years >= 5:
        return +15, f"{years} years experience — stable"
    elif years >= 2:
        return +8,  f"{years} years experience — growing"
    elif years >= 1:
        return +3,  f"{years} years experience — early career"
    else:
        return -10, "Less than 1 year experience — high risk"


def score_housing(personal: dict) -> tuple[float, str]:
    """
    Housing stability — max +25, min -10
    Owned house + many years = highest stability signal
    """
    status = personal.get('housing_status', '').lower().strip()
    years  = float(personal.get('years_at_residence', 0) or 0)

    base = HOUSING_SCORES.get(status, 0)

    if years >= 10:
        base += 10
    elif years >= 5:
        base += 5
    elif years >= 2:
        base += 2
    elif years < 1:
        base -= 5

    return base, f"Housing: {status}, {years} years"


def score_age_factor(personal: dict) -> tuple[float, str]:
    """
    Age factor — max +10, min -5
    Young people get leniency — expected to have lower savings
    """
    try:
        age = int(personal.get('age', 25))
    except (ValueError, TypeError):
        age = 25

    if age < 22:
        return +10, f"Age {age} — student leniency applied"
    elif age < 25:
        return +7,  f"Age {age} — early career leniency"
    elif age < 30:
        return +3,  f"Age {age} — young professional"
    elif age < 40:
        return 0,   f"Age {age} — standard scoring"
    else:
        return -5,  f"Age {age} — expected higher stability"


def score_family_support(personal: dict) -> tuple[float, str]:
    """
    Family earning members — max +10, min 0
    More earners = shared burden = lower personal risk
    """
    try:
        members = int(personal.get('earning_members', 1))
    except (ValueError, TypeError):
        members = 1

    if members >= 4:
        return +10, f"{members} earning members — strong family support"
    elif members >= 3:
        return +7,  f"{members} earning members — good support"
    elif members >= 2:
        return +4,  f"{members} earning members — some support"
    else:
        return 0,   "Single earning member"


def score_loan_purpose(personal: dict) -> tuple[float, str]:
    """Loan purpose — max +10, min -5"""
    purpose = personal.get('loan_purpose', '').lower().strip()
    for key, score in LOAN_PURPOSE_SCORES.items():
        if key in purpose:
            return score, f"Loan purpose: {purpose}"
    return 0, "Loan purpose unknown"


# ─────────────────────────────────────────────────────────────
# REPAYMENT CAPACITY — replaces max loan amount
# Tells the bank what the person can safely repay per month
# Bank decides the loan amount based on their own policies
# ─────────────────────────────────────────────────────────────

def calculate_repayment_capacity(transactions: list[dict], score: int) -> dict:
    """
    FOIR — Fixed Obligation to Income Ratio
    Banks approve loans only when EMI keeps FOIR below 50%

    We tell the bank:
    - How much this person earns
    - How much they spend
    - How much they can safely repay per month
    - What interest rate they qualify for based on score

    The bank decides the loan amount based on their policies.
    """
    credits      = [t for t in transactions if t['type'] == 'CREDIT']
    debits       = [t for t in transactions if t['type'] == 'DEBIT']
    total_income = sum(t['amount'] for t in credits)
    total_spent  = sum(abs(t['amount']) for t in debits)
    disposable   = max(total_income - total_spent, 0)
    max_safe_emi = disposable * 0.50

    # Interest rate based on score band
    if score >= 750:
        interest_rate = 10.5
        risk_level    = "Low Risk"
    elif score >= 650:
        interest_rate = 13.0
        risk_level    = "Moderate Risk"
    elif score >= 500:
        interest_rate = 16.0
        risk_level    = "High Risk"
    else:
        interest_rate = 20.0
        risk_level    = "Very High Risk"

    return {
        "monthly_income":    round(total_income),
        "monthly_spending":  round(total_spent),
        "disposable_income": round(disposable),
        "max_safe_emi":      round(max_safe_emi),
        "interest_rate":     interest_rate,
        "risk_level":        risk_level,
        "band":              get_band(score),
    }


# ─────────────────────────────────────────────────────────────
# MAIN SCORING FUNCTION
# ─────────────────────────────────────────────────────────────

def calculate_score(transactions: list[dict], personal: dict) -> dict:
    """
    Main entry point. Call this from main.py.

    Takes:
    - transactions: list of dicts from parser + categorizer
    - personal: dict from personal details form

    Returns:
    - cibil_score: 300-900
    - band: Poor / Fair / Good / Excellent
    - breakdown: list of signals with delta and reason
    - repayment_capacity: what the person can safely repay
    - summary: income, spending, transaction count
    """
    debits       = [t for t in transactions if t['type'] == 'DEBIT']
    credits      = [t for t in transactions if t['type'] == 'CREDIT']
    total_income = sum(t['amount'] for t in credits)

    score     = BASE_SCORE
    breakdown = []

    # ── BEHAVIOR SIGNALS ──

    delta, reason = score_savings_ratio(debits, credits)
    score += delta
    breakdown.append({"signal": "Savings Ratio",         "delta": delta, "reason": reason})

    delta, reason = score_essential_vs_luxury(debits)
    score += delta
    breakdown.append({"signal": "Essential vs Luxury",   "delta": delta, "reason": reason})

    delta, reason = score_income_consistency(credits)
    score += delta
    breakdown.append({"signal": "Income Consistency",    "delta": delta, "reason": reason})

    delta, reason = score_recurring_payments(transactions)
    score += delta
    breakdown.append({"signal": "Recurring Payments",    "delta": delta, "reason": reason})

    delta, reason = score_p2p_ratio(transactions)
    score += delta
    breakdown.append({"signal": "P2P Transfer Ratio",    "delta": delta, "reason": reason})

    delta, reason = score_large_transactions(debits, total_income)
    score += delta
    breakdown.append({"signal": "Large Transactions",    "delta": delta, "reason": reason})

    delta, reason = score_transaction_frequency(transactions)
    score += delta
    breakdown.append({"signal": "Transaction Frequency", "delta": delta, "reason": reason})

    delta, reason = score_spending_diversity(debits)
    score += delta
    breakdown.append({"signal": "Spending Diversity",    "delta": delta, "reason": reason})

    # ── PERSONAL DETAIL SIGNALS ──

    delta, reason = score_employment(personal)
    score += delta
    breakdown.append({"signal": "Employment Type",       "delta": delta, "reason": reason})

    delta, reason = score_experience(personal)
    score += delta
    breakdown.append({"signal": "Work Experience",       "delta": delta, "reason": reason})

    delta, reason = score_housing(personal)
    score += delta
    breakdown.append({"signal": "Housing Stability",     "delta": delta, "reason": reason})

    delta, reason = score_age_factor(personal)
    score += delta
    breakdown.append({"signal": "Age Factor",            "delta": delta, "reason": reason})

    delta, reason = score_family_support(personal)
    score += delta
    breakdown.append({"signal": "Family Support",        "delta": delta, "reason": reason})

    delta, reason = score_loan_purpose(personal)
    score += delta
    breakdown.append({"signal": "Loan Purpose",          "delta": delta, "reason": reason})

    #FINAL SCORE CALCULATION
    total_spent  = sum(abs(t['amount']) for t in debits)
    total_income = sum(t['amount'] for t in credits)

    if total_income > 0 and total_spent >= total_income:
        final_score = min(clamp(score), 649)  # cap at Fair
    else:
        final_score = clamp(score)

    return {
        "cibil_score":         final_score,
        "band":                get_band(final_score),
        "base_score":          BASE_SCORE,
        "final_raw":           round(score),
        "breakdown":           breakdown,
        "repayment_capacity":  calculate_repayment_capacity(transactions, final_score),
        "summary": {
            "total_income": round(total_income),
            "total_spent":  round(sum(abs(t['amount']) for t in debits)),
            "total_txns":   len(transactions),
        }
    }


# ─────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from phonepe_parser import parse_phonepe_pdf
    from categorizer import categorize_transaction

    transactions = parse_phonepe_pdf("phonepe_statement.pdf")
    transactions = categorize_transaction(transactions)

    personal = {
        "employment_type":    "Student",
        "age":                21,
        "experience":         0,
        "housing_status":     "Family Owned",
        "years_at_residence": 5,
        "earning_members":    2,
        "loan_purpose":       "Education",
    }

    result = calculate_score(transactions, personal)

    print(f"Score: {result['cibil_score']} ({result['band']})")
    for item in result['breakdown']:
        sign = "+" if item['delta'] >= 0 else ""
        print(f"  {item['signal']:<25} {sign}{item['delta']:>4}   {item['reason']}")