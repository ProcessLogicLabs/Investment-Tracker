"""Database models and initialization for Asset Tracker."""

import sqlite3
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

DATABASE_PATH = Path(__file__).parent.parent.parent / "assets.db"


# Asset types that are balance-only (no gain/loss tracking)
BALANCE_ONLY_TYPES = ['retirement', 'cash']


@dataclass
class Asset:
    """Represents an asset in the portfolio."""
    id: Optional[int] = None
    name: str = ""
    asset_type: str = ""  # 'metal', 'stock', 'realestate', 'retirement', 'cash', 'other'
    symbol: str = ""
    quantity: float = 0.0
    unit: str = ""  # 'pcs', 'shares', 'sqft', etc.
    weight_per_unit: float = 1.0  # For metals: oz per coin/bar (e.g., 0.1 for 1/10 oz coins)
    purchase_price: float = 0.0
    purchase_date: Optional[str] = None
    current_price: float = 0.0
    last_updated: Optional[str] = None
    notes: str = ""
    created_at: Optional[str] = None
    monthly_contribution: float = 0.0  # For retirement accounts: monthly contribution amount
    baseline_price: float = 0.0  # For retirement: fund price when balance was entered (for tracking performance)

    @property
    def is_balance_only(self) -> bool:
        """Check if this asset type only tracks balance (no gain/loss)."""
        return self.asset_type in BALANCE_ONLY_TYPES

    @property
    def total_weight(self) -> float:
        """Calculate total weight for metals (quantity * weight_per_unit)."""
        return self.quantity * self.weight_per_unit

    @property
    def total_cost(self) -> float:
        """Calculate total purchase cost."""
        if self.is_balance_only:
            return 0.0  # No cost basis for balance-only assets
        return self.quantity * self.purchase_price

    @property
    def current_value(self) -> float:
        """Calculate current market value.
        For balance-only: current_price is the balance
        For metals: total_weight * current_price (price per oz)
        For others: quantity * current_price
        """
        if self.is_balance_only:
            return self.current_price  # current_price holds the balance
        if self.asset_type == 'metal':
            return self.total_weight * self.current_price
        return self.quantity * self.current_price

    @property
    def gain_loss(self) -> float:
        """Calculate gain/loss in dollars."""
        if self.asset_type == 'retirement' and self.baseline_price > 0 and self.purchase_price > 0:
            # For retirement accounts with tracking: gain/loss is current_balance - original_balance
            # purchase_price stores the original balance when tracking was set up
            return self.current_price - self.purchase_price
        if self.is_balance_only:
            return 0.0  # No gain/loss for balance-only assets without tracking
        return self.current_value - self.total_cost

    @property
    def gain_loss_percent(self) -> float:
        """Calculate gain/loss percentage."""
        if self.asset_type == 'retirement' and self.baseline_price > 0 and self.purchase_price > 0:
            # For retirement accounts: percentage change from original balance
            if self.purchase_price == 0:
                return 0.0
            return ((self.current_price - self.purchase_price) / self.purchase_price) * 100
        if self.is_balance_only:
            return 0.0  # No gain/loss for balance-only assets without tracking
        if self.total_cost == 0:
            return 0.0
        return (self.gain_loss / self.total_cost) * 100


@dataclass
class PriceHistory:
    """Represents a historical price record."""
    id: Optional[int] = None
    asset_id: int = 0
    price: float = 0.0
    timestamp: Optional[str] = None


@dataclass
class Income:
    """Represents an income source."""
    id: Optional[int] = None
    name: str = ""
    income_type: str = ""  # 'salary', 'bonus', 'investment', 'rental', 'side_gig', 'other'
    amount: float = 0.0
    frequency: str = "monthly"  # 'weekly', 'biweekly', 'monthly', 'annual'
    source: str = ""  # Employer or source name
    start_date: Optional[str] = None
    end_date: Optional[str] = None  # None means ongoing
    is_active: bool = True
    notes: str = ""
    created_at: Optional[str] = None
    last_updated: Optional[str] = None

    @property
    def monthly_amount(self) -> float:
        """Calculate monthly income amount."""
        if self.frequency == 'weekly':
            return self.amount * 52 / 12
        elif self.frequency == 'biweekly':
            return self.amount * 26 / 12
        elif self.frequency == 'monthly':
            return self.amount
        elif self.frequency == 'annual':
            return self.amount / 12
        return self.amount

    @property
    def annual_amount(self) -> float:
        """Calculate annual income amount."""
        if self.frequency == 'weekly':
            return self.amount * 52
        elif self.frequency == 'biweekly':
            return self.amount * 26
        elif self.frequency == 'monthly':
            return self.amount * 12
        elif self.frequency == 'annual':
            return self.amount
        return self.amount * 12


@dataclass
class Expense:
    """Represents a recurring expense."""
    id: Optional[int] = None
    name: str = ""
    expense_type: str = ""  # 'housing', 'utilities', 'transportation', 'food', 'insurance', 'healthcare', 'entertainment', 'subscriptions', 'other'
    amount: float = 0.0
    frequency: str = "monthly"  # 'weekly', 'biweekly', 'monthly', 'quarterly', 'annual'
    category: str = ""  # 'essential', 'discretionary'
    is_active: bool = True
    notes: str = ""
    created_at: Optional[str] = None
    last_updated: Optional[str] = None

    @property
    def monthly_amount(self) -> float:
        """Calculate monthly expense amount."""
        if self.frequency == 'weekly':
            return self.amount * 52 / 12
        elif self.frequency == 'biweekly':
            return self.amount * 26 / 12
        elif self.frequency == 'monthly':
            return self.amount
        elif self.frequency == 'quarterly':
            return self.amount / 3
        elif self.frequency == 'annual':
            return self.amount / 12
        return self.amount

    @property
    def annual_amount(self) -> float:
        """Calculate annual expense amount."""
        if self.frequency == 'weekly':
            return self.amount * 52
        elif self.frequency == 'biweekly':
            return self.amount * 26
        elif self.frequency == 'monthly':
            return self.amount * 12
        elif self.frequency == 'quarterly':
            return self.amount * 4
        elif self.frequency == 'annual':
            return self.amount
        return self.amount * 12

    @property
    def is_essential(self) -> bool:
        """Check if expense is essential."""
        return self.category == 'essential'


@dataclass
class Liability:
    """Represents a liability (debt) in the portfolio."""
    id: Optional[int] = None
    name: str = ""
    liability_type: str = ""  # 'mortgage', 'auto', 'student', 'credit', 'personal', 'other'
    creditor: str = ""  # Lender/creditor name
    original_amount: float = 0.0  # Original loan amount
    current_balance: float = 0.0  # Current outstanding balance
    interest_rate: float = 0.0  # Annual interest rate (percentage)
    monthly_payment: float = 0.0  # Monthly payment amount
    minimum_payment: float = 0.0  # Minimum required payment
    payment_day: int = 1  # Day of month payment is due (1-28)
    is_revolving: bool = False  # True for credit cards, False for installment loans
    credit_limit: float = 0.0  # For revolving credit: credit limit
    start_date: Optional[str] = None  # Loan start date
    end_date: Optional[str] = None  # Expected payoff date
    notes: str = ""
    created_at: Optional[str] = None
    last_updated: Optional[str] = None

    @property
    def monthly_interest_rate(self) -> float:
        """Get monthly interest rate as decimal."""
        return (self.interest_rate / 100) / 12

    @property
    def monthly_interest_charge(self) -> float:
        """Calculate monthly interest charge on current balance."""
        return self.current_balance * self.monthly_interest_rate

    @property
    def principal_payment(self) -> float:
        """Calculate principal portion of monthly payment."""
        return max(0, self.monthly_payment - self.monthly_interest_charge)

    @property
    def months_to_payoff(self) -> int:
        """Estimate months to pay off at current payment rate."""
        if self.monthly_payment <= self.monthly_interest_charge:
            return -1  # Will never pay off
        if self.current_balance <= 0:
            return 0

        balance = self.current_balance
        months = 0
        monthly_rate = self.monthly_interest_rate

        while balance > 0 and months < 600:  # Cap at 50 years
            interest = balance * monthly_rate
            principal = self.monthly_payment - interest
            balance -= principal
            months += 1

        return months

    @property
    def total_interest_remaining(self) -> float:
        """Calculate total interest that will be paid if paying minimum."""
        if self.monthly_payment <= self.monthly_interest_charge:
            return float('inf')
        if self.current_balance <= 0:
            return 0

        balance = self.current_balance
        total_interest = 0
        monthly_rate = self.monthly_interest_rate

        while balance > 0.01:
            interest = balance * monthly_rate
            total_interest += interest
            principal = self.monthly_payment - interest
            balance -= principal
            if balance < 0:
                break

        return total_interest

    @property
    def available_credit(self) -> float:
        """For revolving credit: available credit remaining."""
        if self.is_revolving and self.credit_limit > 0:
            return max(0, self.credit_limit - self.current_balance)
        return 0.0

    @property
    def utilization_rate(self) -> float:
        """For revolving credit: credit utilization percentage."""
        if self.is_revolving and self.credit_limit > 0:
            return (self.current_balance / self.credit_limit) * 100
        return 0.0


def get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize the database with required tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create assets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            symbol TEXT,
            quantity REAL NOT NULL DEFAULT 0,
            unit TEXT DEFAULT '',
            purchase_price REAL NOT NULL DEFAULT 0,
            purchase_date DATE,
            current_price REAL DEFAULT 0,
            last_updated DATETIME,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add unit column if it doesn't exist (migration for existing databases)
    try:
        cursor.execute("ALTER TABLE assets ADD COLUMN unit TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add weight_per_unit column if it doesn't exist (migration for existing databases)
    try:
        cursor.execute("ALTER TABLE assets ADD COLUMN weight_per_unit REAL DEFAULT 1.0")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add monthly_contribution column if it doesn't exist (migration for existing databases)
    try:
        cursor.execute("ALTER TABLE assets ADD COLUMN monthly_contribution REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add baseline_price column if it doesn't exist (for retirement fund tracking)
    try:
        cursor.execute("ALTER TABLE assets ADD COLUMN baseline_price REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Create liabilities table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS liabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            liability_type TEXT NOT NULL,
            creditor TEXT DEFAULT '',
            original_amount REAL NOT NULL DEFAULT 0,
            current_balance REAL NOT NULL DEFAULT 0,
            interest_rate REAL DEFAULT 0,
            monthly_payment REAL DEFAULT 0,
            minimum_payment REAL DEFAULT 0,
            payment_day INTEGER DEFAULT 1,
            is_revolving INTEGER DEFAULT 0,
            credit_limit REAL DEFAULT 0,
            start_date DATE,
            end_date DATE,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_updated DATETIME
        )
    """)

    # Add new liability columns if they don't exist (migration)
    try:
        cursor.execute("ALTER TABLE liabilities ADD COLUMN minimum_payment REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE liabilities ADD COLUMN payment_day INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE liabilities ADD COLUMN is_revolving INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE liabilities ADD COLUMN credit_limit REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Create income table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            income_type TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            frequency TEXT DEFAULT 'monthly',
            source TEXT DEFAULT '',
            start_date DATE,
            end_date DATE,
            is_active INTEGER DEFAULT 1,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_updated DATETIME
        )
    """)

    # Create expenses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            expense_type TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            frequency TEXT DEFAULT 'monthly',
            category TEXT DEFAULT 'essential',
            is_active INTEGER DEFAULT 1,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_updated DATETIME
        )
    """)

    # Create price_history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            price REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
        )
    """)

    # Create settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Create index for faster price history lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_history_asset_id
        ON price_history(asset_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_history_timestamp
        ON price_history(timestamp)
    """)

    conn.commit()
    conn.close()
