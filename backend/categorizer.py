from rapidfuzz import fuzz, process


MERCHANT_CATEGORIES = {
    # Food & Dining
    "swiggy":               "Food & Dining",
    "zomato":               "Food & Dining",
    "dominos":              "Food & Dining",
    "pizza hut":            "Food & Dining",
    "mcdonalds":            "Food & Dining",
    "kfc":                  "Food & Dining",
    "starbucks":            "Food & Dining",
    "subway":               "Food & Dining",
    "dunkin":               "Food & Dining",

    # Groceries
    "zepto":                "Groceries",
    "blinkit":              "Groceries",
    "bigbasket":            "Groceries",
    "dunzo":                "Groceries",
    "jiomart":              "Groceries",
    "dmart":                "Groceries",
    "reliance fresh":       "Groceries",
    "more supermarket":     "Groceries",

    # Transport
    "uber":                 "Transport",
    "ola":                  "Transport",
    "rapido":               "Transport",
    "metropolitan transport": "Transport",
    "redbus":               "Transport",
    "irctc":                "Transport",
    "indian railway":       "Transport",
    "ola electric":         "Transport",

    # Entertainment
    "netflix":              "Entertainment",
    "spotify":              "Entertainment",
    "fancode":              "Entertainment",
    "hotstar":              "Entertainment",
    "disney":               "Entertainment",
    "amazon prime":         "Entertainment",
    "youtube premium":      "Entertainment",
    "google play":          "Entertainment",
    "apple":                "Entertainment",
    "bookmyshow":           "Entertainment",
    "pvr":                  "Entertainment",
    "inox":                 "Entertainment",
    "sony liv":             "Entertainment",
    "zee5":                 "Entertainment",
    "jio cinema":           "Entertainment",

    # Shopping
    "amazon":               "Shopping",
    "flipkart":             "Shopping",
    "myntra":               "Shopping",
    "meesho":               "Shopping",
    "nykaa":                "Shopping",
    "ajio":                 "Shopping",
    "snapdeal":             "Shopping",
    "tata cliq":            "Shopping",
    "reliance digital":     "Shopping",
    "croma":                "Shopping",

    # Bills & Utilities
    "airtel":               "Bills & Utilities",
    "jio":                  "Bills & Utilities",
    "bsnl":                 "Bills & Utilities",
    "vi ":                  "Bills & Utilities",
    "vodafone":             "Bills & Utilities",
    "bescom":               "Bills & Utilities",
    "tneb":                 "Bills & Utilities",
    "msedcl":               "Bills & Utilities",
    "tata power":           "Bills & Utilities",
    "adani electricity":    "Bills & Utilities",
    "gas authority":        "Bills & Utilities",
    "indane":               "Bills & Utilities",
    "bharat gas":           "Bills & Utilities",
    "hp gas":               "Bills & Utilities",
    "piped gas":            "Bills & Utilities",

    # Education
    "college":              "Education",
    "university":           "Education",
    "school":               "Education",
    "coaching":             "Education",
    "byju":                 "Education",
    "unacademy":            "Education",
    "vedantu":              "Education",
    "coursera":             "Education",
    "udemy":                "Education",
    "simplilearn":          "Education",

    # AI & Tech Subscriptions
    # These are the actual billing names that appear in UPI
    "openai":               "AI Subscriptions",
    "anthropic":            "AI Subscriptions",
    "perplexity":           "AI Subscriptions",
    "midjourney":           "AI Subscriptions",
    "github":               "Tech Subscriptions",
    "microsoft":            "Tech Subscriptions",
    "google":               "Tech Subscriptions",
    "adobe":                "Tech Subscriptions",
    "notion":               "Tech Subscriptions",
    "figma":                "Tech Subscriptions",
    "aws":                  "Tech Subscriptions",
    "digitalocean":         "Tech Subscriptions",

    # Health
    "apollo":               "Healthcare",
    "medplus":              "Healthcare",
    "netmeds":              "Healthcare",
    "pharmeasy":            "Healthcare",
    "practo":               "Healthcare",
    "tata 1mg":             "Healthcare",
    "cult fit":             "Healthcare",
    "healthkart":           "Healthcare",

    # Finance
    "zerodha":              "Finance & Investments",
    "groww":                "Finance & Investments",
    "upstox":               "Finance & Investments",
    "coin":                 "Finance & Investments",
    "paytm money":          "Finance & Investments",
    "navi":                 "Finance & Investments",
    "policybazaar":         "Finance & Investments",
    "lic":                  "Finance & Investments",
    "hdfc life":            "Finance & Investments",
    "sbi life":             "Finance & Investments",

    # Travel
    "makemytrip":           "Travel",
    "goibibo":              "Travel",
    "cleartrip":            "Travel",
    "yatra":                "Travel",
    "airasia":              "Travel",
    "indigo":               "Travel",
    "air india":            "Travel",
    "oyo":                  "Travel",
    "treebo":               "Travel",
}

def detect_merchant(description : str) -> tuple[str, str] :
    desc_lower = description.lower()
    merchants = list(MERCHANT_CATEGORIES.keys())

    if len(desc_lower) < 6:
        return "Unknown", "Personal Transfer"
   
    result = process.extractOne(
            desc_lower,
            merchants,
            scorer = fuzz.partial_ratio,
            score_cutoff = 72
    )
    if result :
        merchant = result[0]
        return merchant.title(), MERCHANT_CATEGORIES[merchant]

    return "Unknown", "Personal Transfer"

def categorize_transaction(transactions : list[dict]) -> list[dict] :
    
    for txn in transactions :
        merchant, category = detect_merchant(txn["raw_description"])
        txn["merchant"] = merchant
        txn["category"] = category
        
    return transactions

if __name__ == "__main__":
    from phonepe_parser import parse_phonepe_pdf

    transactions = parse_phonepe_pdf("phonepe_statement.pdf")
    transactions = categorize_transaction(transactions)

    print(f"\n{'Date':<14} {'Description':<35} {'Category':<25} {'Amount':>10}")
    print("-" * 88)
    for t in transactions:
        sign = "+" if t['type'] == 'CREDIT' else "-"
        print(
            f"{t['datetime']:<14} "
            f"{t['raw_description'][:33]:<35} "
            f"{t['category']:<25} "
            f"{sign}₹{abs(t['amount']):>8,.0f}"
        )