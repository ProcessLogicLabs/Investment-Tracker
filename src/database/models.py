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
class AssetSale:
    """Represents a completed asset sale."""
    id: Optional[int] = None
    asset_id: Optional[int] = None  # None if the asset has been deleted
    asset_name: str = ""  # Denormalized so history survives asset deletion
    asset_type: str = ""
    symbol: str = ""
    sale_date: Optional[str] = None
    quantity_sold: float = 0.0
    sale_price_per_unit: float = 0.0
    total_proceeds: float = 0.0
    cost_basis_sold: float = 0.0
    buyer_name: str = ""
    notes: str = ""
    created_at: Optional[str] = None

    @property
    def profit_loss(self) -> float:
        """Profit or loss on the sale."""
        return self.total_proceeds - self.cost_basis_sold

    @property
    def profit_loss_percent(self) -> float:
        """Profit or loss as a percentage of cost basis."""
        if self.cost_basis_sold == 0:
            return 0.0
        return (self.profit_loss / self.cost_basis_sold) * 100


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


@dataclass
class PaymentHistory:
    """Represents a recorded loan payment."""
    id: Optional[int] = None
    liability_id: int = 0
    payment_date: Optional[str] = None  # ISO date of the payment
    payment_amount: float = 0.0  # Total payment applied
    interest_portion: float = 0.0  # Interest part of the payment
    principal_portion: float = 0.0  # Principal part of the payment
    balance_before: float = 0.0  # Balance before payment
    balance_after: float = 0.0  # Balance after payment
    is_auto: bool = True  # True if auto-applied, False if manual
    created_at: Optional[str] = None


@dataclass
class Transaction:
    """Represents an imported bank/credit card transaction."""
    id: Optional[int] = None
    transaction_date: Optional[str] = None  # YYYY-MM-DD
    description: str = ""  # Merchant/payee name
    amount: float = 0.0  # Negative=debit, positive=credit
    category: str = ""  # food, transportation, utilities, etc.
    transaction_type: str = ""  # debit_card, direct_pay, zelle, bill_pay, atm, deposit, etc.
    account_name: str = ""  # "SoFi Checking", "Chase Visa", etc.
    original_description: str = ""  # Raw description from CSV
    is_income: bool = False  # True if deposit/income
    notes: str = ""
    created_at: Optional[str] = None


@dataclass
class Goal:
    """Represents a financial goal."""
    id: Optional[int] = None
    name: str = ""
    goal_type: str = ""  # 'savings', 'debt_payoff', 'net_worth', 'asset_acquisition'
    target_amount: float = 0.0
    current_amount: float = 0.0
    start_amount: float = 0.0  # Amount when goal was created, for progress calculation
    target_date: Optional[str] = None
    start_date: Optional[str] = None
    is_active: bool = True
    is_completed: bool = False
    completed_date: Optional[str] = None
    linked_liability_id: Optional[int] = None  # For debt_payoff goals
    linked_asset_type: Optional[str] = None  # For savings/asset_acquisition goals
    milestones: str = "[]"  # JSON string
    notes: str = ""
    created_at: Optional[str] = None
    last_updated: Optional[str] = None

    @property
    def progress_percent(self) -> float:
        """Calculate progress toward goal as percentage."""
        if self.goal_type == 'debt_payoff':
            if self.start_amount <= 0:
                return 100.0
            paid_off = self.start_amount - self.current_amount
            return min(100.0, max(0.0, (paid_off / self.start_amount) * 100))
        else:
            if self.target_amount <= 0:
                return 0.0
            return min(100.0, max(0.0, (self.current_amount / self.target_amount) * 100))

    @property
    def amount_remaining(self) -> float:
        """Calculate amount remaining to reach goal."""
        if self.goal_type == 'debt_payoff':
            return max(0, self.current_amount)
        return max(0, self.target_amount - self.current_amount)

    @property
    def is_on_track(self) -> Optional[bool]:
        """Check if goal is on track based on target date and linear progress."""
        if not self.target_date or not self.start_date:
            return None
        try:
            start = datetime.fromisoformat(self.start_date)
            target = datetime.fromisoformat(self.target_date)
            now = datetime.now()
            total_days = (target - start).days
            elapsed_days = (now - start).days
            if total_days <= 0:
                return None
            expected_progress = (elapsed_days / total_days) * 100
            return self.progress_percent >= expected_progress
        except (ValueError, TypeError):
            return None


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

    # Create goals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            goal_type TEXT NOT NULL,
            target_amount REAL NOT NULL DEFAULT 0,
            current_amount REAL NOT NULL DEFAULT 0,
            start_amount REAL NOT NULL DEFAULT 0,
            target_date DATE,
            start_date DATE,
            is_active INTEGER DEFAULT 1,
            is_completed INTEGER DEFAULT 0,
            completed_date DATE,
            linked_liability_id INTEGER,
            linked_asset_type TEXT,
            milestones TEXT DEFAULT '[]',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_updated DATETIME,
            FOREIGN KEY (linked_liability_id) REFERENCES liabilities(id) ON DELETE SET NULL
        )
    """)

    # Create transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_date DATE NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            category TEXT DEFAULT '',
            transaction_type TEXT DEFAULT '',
            account_name TEXT DEFAULT '',
            original_description TEXT DEFAULT '',
            is_income INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_date
        ON transactions(transaction_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_account
        ON transactions(account_name)
    """)

    # Create payment_history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            liability_id INTEGER NOT NULL,
            payment_date DATE NOT NULL,
            payment_amount REAL NOT NULL DEFAULT 0,
            interest_portion REAL NOT NULL DEFAULT 0,
            principal_portion REAL NOT NULL DEFAULT 0,
            balance_before REAL NOT NULL DEFAULT 0,
            balance_after REAL NOT NULL DEFAULT 0,
            is_auto INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (liability_id) REFERENCES liabilities(id) ON DELETE CASCADE
        )
    """)

    # Create index for faster payment history lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_payment_history_liability_id
        ON payment_history(liability_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_payment_history_date
        ON payment_history(payment_date)
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

    # Create asset_sales table (records of asset sales)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asset_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER,
            asset_name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            symbol TEXT DEFAULT '',
            sale_date DATE NOT NULL,
            quantity_sold REAL NOT NULL DEFAULT 0,
            sale_price_per_unit REAL NOT NULL DEFAULT 0,
            total_proceeds REAL NOT NULL DEFAULT 0,
            cost_basis_sold REAL NOT NULL DEFAULT 0,
            buyer_name TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_asset_sales_date
        ON asset_sales(sale_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_asset_sales_asset_id
        ON asset_sales(asset_id)
    """)

    conn.commit()
    conn.close()
