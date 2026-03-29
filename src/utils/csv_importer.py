"""CSV importer for bank and credit card transaction statements."""

import csv
from typing import List, Tuple
from ..database.models import Transaction


# Merchant keywords → category mapping
CATEGORY_MAP = {
    # Food / Restaurants
    'food': [
        'TACO BELL', 'BURGER KING', 'POPEYES', 'RAISING CANE', 'SONIC DRIVE',
        'DAIRY QUEEN', 'WHATABURGER', 'LITTLE CAESARS', 'MCDONALDS', "MCDONALD'S",
        'WENDYS', "WENDY'S", 'CHICK-FIL-A', 'SUBWAY', 'DOMINOS', "DOMINO'S",
        'PIZZA HUT', 'KFC', 'PANDA EXPRESS', 'CHIPOTLE', 'FIVE GUYS',
        "JASON'S DELI", 'TEXAS ROADHOUSE', "PETE'S BURGER", 'IHOP',
        "DENNY'S", 'WAFFLE HOUSE', 'JACK IN THE BOX', 'ARBY',
        '365 MARKET', 'KROGER', 'WALMART', 'H-E-B', 'PUBLIX', 'ALDI',
        'WHOLE FOODS', 'TRADER JOE', 'FOOD LION',
        'SALTGRASS', 'CRACKER BARREL', 'OLIVE GARDEN', 'RED LOBSTER',
        'OUTBACK', 'APPLEBEE', 'CHILI', 'GOLDEN CORRAL', 'STARBUCKS',
        'DUNKIN', 'PANERA',
    ],
    # Automotive
    'automotive': [
        "O'REILLY", 'AUTOZONE', 'ADVANCE AUTO', 'JIFFY LUBE',
        'VALVOLINE', 'TIRE', 'CARWASH', 'CAR WASH',
    ],
    # Healthcare
    'healthcare': [
        'OPTICAL', 'VISION', 'DENTAL', 'DENTIST', 'PHARMACY',
        'CLINIC', 'HOSPITAL', 'MEDICAL', 'DOCTOR', 'DR.',
        'URGENT CARE', 'QUEST DIAG', 'LABCORP',
    ],
    # Housing
    'housing': [
        'HOME DEPOT', 'LOWES', "LOWE'S", 'MENARDS', 'ACE HARDWARE',
        'RENT', 'PROPERTY',
    ],
    # Transportation / Gas
    'transportation': [
        'SHELL', 'CHEVRON', 'EXXON', 'BP ', 'MOBIL', 'CITGO', 'VALERO',
        'STOP N GAS', 'RACETRAC', 'QT ', 'QUIKTRIP', 'CIRCLE K',
        'SPEEDWAY', 'MURPHY', 'WAWA', 'SHEETZ', 'BUCCEE', "BUCEE'S",
        'UBER', 'LYFT', 'PARKING',
    ],
    # Utilities
    'utilities': [
        'VERIZON', 'AT&T', 'T-MOBILE', 'SPRINT', 'COMCAST', 'SPECTRUM',
        'XFINITY', 'COX COMM', 'ELECTRIC', 'WATER BILL', 'GAS BILL',
        'ENTERGY', 'CENTERPOINT',
    ],
    # Personal / Pharmacy / Retail
    'personal': [
        'WALGREENS', 'CVS', 'RITE AID', 'TARGET', 'DOLLAR GENERAL',
        'DOLLAR TREE', 'FAMILY DOLLAR', 'AMAZON', 'STORE',
    ],
    # Subscriptions
    'subscriptions': [
        'NETFLIX', 'SPOTIFY', 'HULU', 'DISNEY+', 'APPLE.COM',
        'GOOGLE', 'MICROSOFT', 'ADOBE',
    ],
}

# Transaction type → category overrides
TYPE_CATEGORY_MAP = {
    'DIRECT_DEPOSIT': 'income',
    'INTEREST_EARNED': 'income',
    'DEPOSIT': 'income',
    'BILL_PAY': 'debt',
    'ZELLE': 'transfers',
    'ATM': 'cash',
}


def auto_categorize(description: str, txn_type: str) -> str:
    """Determine category from merchant description and transaction type."""
    # Check type-based overrides first
    type_upper = txn_type.upper()
    if type_upper in TYPE_CATEGORY_MAP:
        return TYPE_CATEGORY_MAP[type_upper]

    desc_upper = description.upper()

    # Income patterns (check before spending patterns)
    if any(kw in desc_upper for kw in [
        'DIRECT DEPOSIT', 'PAYROLL', 'SALARY', 'WAGE',
        'TAX REFUND', 'IRS TREAS', 'BONUS:', 'PROMO BONUS',
        'INTEREST',
    ]):
        return 'income'

    # Debt / loan payment patterns
    if any(kw in desc_upper for kw in [
        'BILL PAY:', 'BILL PAYMENT', 'LOAN', 'PERSONAL LOAN',
        'SOFI BANK', 'SOFI LOAN', 'SOFI CREDIT',
        'MORTGAGE', 'AUTO PAY', 'AUTOPAY',
        'STUDENT LOAN', 'NAVIENT', 'NELNET', 'FEDLOAN',
        'PAYMENT THANK YOU',
    ]):
        return 'debt'

    # Housing - specific payees before general transfer matching
    if 'SUMMER SPRING' in desc_upper:
        return 'housing'

    # Transfer patterns
    if any(kw in desc_upper for kw in [
        'TRANSFER TO', 'TRANSFER FROM', 'XFER', 'CASH APP',
        'VENMO', 'SAVINGS TRANSFER', 'INTERNAL TRANSFER',
        'ZELLE', 'WELLS FARGO', 'VANGUARD',
    ]):
        return 'transfers'

    # SoFi self-payments (loan payments to SoFi from SoFi)
    if desc_upper.strip() == 'SOFI' or desc_upper.startswith('SOFI '):
        # Bare "SoFi" or "SoFi <something>" that isn't a known merchant
        if not any(kw in desc_upper for kw in ['SOFI TRAVEL', 'SOFI INVEST']):
            return 'debt'

    # ATM withdrawals
    if 'ATM:' in desc_upper or 'ATM ' in desc_upper:
        return 'cash'

    # Check merchant keywords
    for category, keywords in CATEGORY_MAP.items():
        for keyword in keywords:
            if keyword in desc_upper:
                return category

    # PAYPAL with DIRECT_PAY is usually subscriptions
    if 'PAYPAL' in desc_upper and type_upper == 'DIRECT_PAY':
        return 'subscriptions'

    return 'uncategorized'


def detect_format(file_path: str) -> str:
    """Detect the CSV format by reading headers.

    Returns format identifier string or 'unknown'.
    """
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return 'unknown'

    headers_lower = [h.strip().lower() for h in headers]

    # SoFi: Date,Description,Type,Amount,Current balance,Status
    if headers_lower[:4] == ['date', 'description', 'type', 'amount']:
        return 'sofi'

    # Chase: Transaction Date,Post Date,Description,Category,Type,Amount,Memo
    if 'transaction date' in headers_lower and 'post date' in headers_lower:
        return 'chase'

    # Fidelity 401K: has metadata rows, then Date,Investment,Transaction Type,Amount,Shares/Unit
    # Scan up to 10 lines for the actual header row
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        for _ in range(10):
            line = f.readline()
            if not line:
                break
            parts = [h.strip().lower() for h in line.split(',')]
            if 'investment' in parts and 'transaction type' in parts:
                return 'fidelity'

    return 'unknown'


def parse_sofi(file_path: str, account_name: str = "SoFi Checking") -> List[Transaction]:
    """Parse a SoFi bank statement CSV into Transaction objects."""
    transactions = []

    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get('Date', '').strip()
            description = row.get('Description', '').strip()
            txn_type = row.get('Type', '').strip()
            amount_str = row.get('Amount', '0').strip()

            try:
                amount = float(amount_str)
            except ValueError:
                continue

            is_income = amount > 0
            category = auto_categorize(description, txn_type)

            txn = Transaction(
                transaction_date=date,
                description=description,
                amount=amount,
                category=category,
                transaction_type=txn_type.lower(),
                account_name=account_name,
                original_description=description,
                is_income=is_income,
            )
            transactions.append(txn)

    return transactions


CHASE_CATEGORY_MAP = {
    'food & drink': 'food',
    'groceries': 'food',
    'gas': 'transportation',
    'travel': 'transportation',
    'shopping': 'personal',
    'entertainment': 'entertainment',
    'health & wellness': 'healthcare',
    'professional services': 'other',
    'personal': 'personal',
    'home': 'housing',
    'education': 'other',
    'gifts & donations': 'personal',
    'fees & adjustments': 'other',
}


def _normalize_date(date_str: str) -> str:
    """Convert MM/DD/YYYY to YYYY-MM-DD. Pass through if already ISO."""
    if '/' in date_str:
        parts = date_str.split('/')
        if len(parts) == 3:
            month, day, year = parts
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return date_str


def parse_chase(file_path: str, account_name: str = "Chase") -> List[Transaction]:
    """Parse a Chase bank/credit card CSV into Transaction objects."""
    transactions = []

    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get('Transaction Date', row.get('Post Date', '')).strip()
            date = _normalize_date(date)
            description = row.get('Description', '').strip()
            txn_type = row.get('Type', '').strip()
            category_raw = row.get('Category', '').strip()
            amount_str = row.get('Amount', '0').strip()

            try:
                amount = float(amount_str)
            except ValueError:
                continue

            is_income = amount > 0
            category = auto_categorize(description, txn_type)
            if category == 'uncategorized' and category_raw:
                category = CHASE_CATEGORY_MAP.get(category_raw.lower(), category_raw.lower())

            txn = Transaction(
                transaction_date=date,
                description=description,
                amount=amount,
                category=category,
                transaction_type=txn_type.lower() if txn_type else 'card',
                account_name=account_name,
                original_description=description,
                is_income=is_income,
            )
            transactions.append(txn)

    return transactions


FIDELITY_CATEGORY_MAP = {
    'contributions': 'retirement',
    'loan repayments': 'debt',
    'dividends': 'income',
    'fee': 'other',
}


def parse_fidelity(file_path: str, account_name: str = "Fidelity 401K") -> List[Transaction]:
    """Parse a Fidelity 401K contribution history CSV into Transaction objects."""
    transactions = []

    with open(file_path, 'r', encoding='utf-8-sig') as f:
        # Skip metadata rows until we find the header row
        header_line = None
        for line in f:
            stripped = line.strip()
            if stripped.lower().startswith('date,investment'):
                header_line = stripped
                break

        if not header_line:
            return transactions

        # Use DictReader with the remaining lines
        reader = csv.DictReader(f, fieldnames=[h.strip() for h in header_line.split(',')])
        for row in reader:
            date = row.get('Date', '').strip()
            if not date:
                continue
            date = _normalize_date(date)

            investment = row.get('Investment', '').strip()
            txn_type = row.get('Transaction Type', '').strip()
            amount_str = row.get('Amount', '0').strip().replace(',', '').replace('"', '')
            shares_str = row.get('Shares/Unit', '0').strip().replace(',', '').replace('"', '')

            try:
                amount = float(amount_str)
            except ValueError:
                continue

            try:
                shares = float(shares_str)
            except ValueError:
                shares = 0.0

            category = FIDELITY_CATEGORY_MAP.get(txn_type.lower(), 'retirement')
            description = f"{investment} - {txn_type}"
            if shares:
                description += f" ({shares:.3f} shares)"

            txn = Transaction(
                transaction_date=date,
                description=description,
                amount=amount,
                category=category,
                transaction_type=txn_type.lower().replace(' ', '_'),
                account_name=account_name,
                original_description=f"{investment},{txn_type},{amount_str},{shares_str}",
                is_income=False,
                notes=f"Fund: {investment}",
            )
            transactions.append(txn)

    return transactions


def parse_csv(file_path: str, account_name: str = "") -> Tuple[List[Transaction], str]:
    """Auto-detect format and parse a CSV file.

    Returns (transactions, format_name).
    """
    fmt = detect_format(file_path)

    if fmt == 'sofi':
        name = account_name or "SoFi Checking"
        return parse_sofi(file_path, name), fmt
    elif fmt == 'chase':
        name = account_name or "Chase"
        return parse_chase(file_path, name), fmt
    elif fmt == 'fidelity':
        name = account_name or "Fidelity 401K"
        return parse_fidelity(file_path, name), fmt
    else:
        # Try SoFi format as fallback
        try:
            name = account_name or "Bank Account"
            txns = parse_sofi(file_path, name)
            if txns:
                return txns, 'sofi'
        except Exception:
            pass
        return [], 'unknown'
