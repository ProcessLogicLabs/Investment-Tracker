"""Database models and initialization for Asset Tracker."""

import sqlite3
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

DATABASE_PATH = Path(__file__).parent.parent.parent / "assets.db"


@dataclass
class Asset:
    """Represents an asset in the portfolio."""
    id: Optional[int] = None
    name: str = ""
    asset_type: str = ""  # 'metal', 'stock', 'realestate', 'other'
    symbol: str = ""
    quantity: float = 0.0
    unit: str = ""  # 'oz', 'g', 'shares', 'sqft', etc.
    weight_per_unit: float = 1.0  # For metals: oz per coin/bar (e.g., 0.1 for 1/10 oz coins)
    purchase_price: float = 0.0
    purchase_date: Optional[str] = None
    current_price: float = 0.0
    last_updated: Optional[str] = None
    notes: str = ""
    created_at: Optional[str] = None

    @property
    def total_weight(self) -> float:
        """Calculate total weight for metals (quantity * weight_per_unit)."""
        return self.quantity * self.weight_per_unit

    @property
    def total_cost(self) -> float:
        """Calculate total purchase cost."""
        return self.quantity * self.purchase_price

    @property
    def current_value(self) -> float:
        """Calculate current market value.
        For metals: total_weight * current_price (price per oz)
        For others: quantity * current_price
        """
        if self.asset_type == 'metal':
            return self.total_weight * self.current_price
        return self.quantity * self.current_price

    @property
    def gain_loss(self) -> float:
        """Calculate gain/loss in dollars."""
        return self.current_value - self.total_cost

    @property
    def gain_loss_percent(self) -> float:
        """Calculate gain/loss percentage."""
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
