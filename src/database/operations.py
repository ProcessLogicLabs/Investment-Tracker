"""Database CRUD operations for Asset Tracker."""

import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from .models import Asset, PriceHistory, get_connection


class AssetOperations:
    """CRUD operations for assets."""

    @staticmethod
    def create(asset: Asset) -> int:
        """Create a new asset and return its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO assets (name, asset_type, symbol, quantity, unit, weight_per_unit,
                              purchase_price, purchase_date, current_price, last_updated, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            asset.name,
            asset.asset_type,
            asset.symbol,
            asset.quantity,
            asset.unit,
            asset.weight_per_unit,
            asset.purchase_price,
            asset.purchase_date,
            asset.current_price,
            asset.last_updated,
            asset.notes
        ))

        asset_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return asset_id

    @staticmethod
    def get_by_id(asset_id: int) -> Optional[Asset]:
        """Get an asset by its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return Asset(
                id=row['id'],
                name=row['name'],
                asset_type=row['asset_type'],
                symbol=row['symbol'],
                quantity=row['quantity'],
                unit=row['unit'] if 'unit' in row.keys() else '',
                weight_per_unit=row['weight_per_unit'] if 'weight_per_unit' in row.keys() else 1.0,
                purchase_price=row['purchase_price'],
                purchase_date=row['purchase_date'],
                current_price=row['current_price'],
                last_updated=row['last_updated'],
                notes=row['notes'],
                created_at=row['created_at']
            )
        return None

    @staticmethod
    def get_all() -> List[Asset]:
        """Get all assets."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM assets ORDER BY asset_type, name")
        rows = cursor.fetchall()
        conn.close()

        return [
            Asset(
                id=row['id'],
                name=row['name'],
                asset_type=row['asset_type'],
                symbol=row['symbol'],
                quantity=row['quantity'],
                unit=row['unit'] if 'unit' in row.keys() else '',
                weight_per_unit=row['weight_per_unit'] if 'weight_per_unit' in row.keys() else 1.0,
                purchase_price=row['purchase_price'],
                purchase_date=row['purchase_date'],
                current_price=row['current_price'],
                last_updated=row['last_updated'],
                notes=row['notes'],
                created_at=row['created_at']
            )
            for row in rows
        ]

    @staticmethod
    def get_by_type(asset_type: str) -> List[Asset]:
        """Get all assets of a specific type."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM assets WHERE asset_type = ? ORDER BY name",
            (asset_type,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            Asset(
                id=row['id'],
                name=row['name'],
                asset_type=row['asset_type'],
                symbol=row['symbol'],
                quantity=row['quantity'],
                unit=row['unit'] if 'unit' in row.keys() else '',
                weight_per_unit=row['weight_per_unit'] if 'weight_per_unit' in row.keys() else 1.0,
                purchase_price=row['purchase_price'],
                purchase_date=row['purchase_date'],
                current_price=row['current_price'],
                last_updated=row['last_updated'],
                notes=row['notes'],
                created_at=row['created_at']
            )
            for row in rows
        ]

    @staticmethod
    def update(asset: Asset) -> bool:
        """Update an existing asset."""
        if asset.id is None:
            return False

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE assets SET
                name = ?,
                asset_type = ?,
                symbol = ?,
                quantity = ?,
                unit = ?,
                weight_per_unit = ?,
                purchase_price = ?,
                purchase_date = ?,
                current_price = ?,
                last_updated = ?,
                notes = ?
            WHERE id = ?
        """, (
            asset.name,
            asset.asset_type,
            asset.symbol,
            asset.quantity,
            asset.unit,
            asset.weight_per_unit,
            asset.purchase_price,
            asset.purchase_date,
            asset.current_price,
            asset.last_updated,
            asset.notes,
            asset.id
        ))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def update_price(asset_id: int, price: float) -> bool:
        """Update the current price of an asset."""
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            UPDATE assets SET current_price = ?, last_updated = ?
            WHERE id = ?
        """, (price, now, asset_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def delete(asset_id: int) -> bool:
        """Delete an asset."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM assets WHERE id = ?", (asset_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def get_portfolio_summary() -> Dict[str, Any]:
        """Get portfolio summary statistics."""
        assets = AssetOperations.get_all()

        total_cost = sum(a.total_cost for a in assets)
        total_value = sum(a.current_value for a in assets)
        total_gain_loss = total_value - total_cost

        by_type = {}
        for asset in assets:
            if asset.asset_type not in by_type:
                by_type[asset.asset_type] = {
                    'count': 0,
                    'total_cost': 0.0,
                    'current_value': 0.0
                }
            by_type[asset.asset_type]['count'] += 1
            by_type[asset.asset_type]['total_cost'] += asset.total_cost
            by_type[asset.asset_type]['current_value'] += asset.current_value

        return {
            'total_assets': len(assets),
            'total_cost': total_cost,
            'total_value': total_value,
            'total_gain_loss': total_gain_loss,
            'gain_loss_percent': (total_gain_loss / total_cost * 100) if total_cost > 0 else 0,
            'by_type': by_type
        }


class PriceHistoryOperations:
    """CRUD operations for price history."""

    @staticmethod
    def add(asset_id: int, price: float) -> int:
        """Add a price history record."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO price_history (asset_id, price)
            VALUES (?, ?)
        """, (asset_id, price))

        history_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return history_id

    @staticmethod
    def get_by_asset(asset_id: int, limit: int = 100) -> List[PriceHistory]:
        """Get price history for an asset."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM price_history
            WHERE asset_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (asset_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [
            PriceHistory(
                id=row['id'],
                asset_id=row['asset_id'],
                price=row['price'],
                timestamp=row['timestamp']
            )
            for row in rows
        ]

    @staticmethod
    def get_portfolio_history(days: int = 30) -> List[Dict[str, Any]]:
        """Get portfolio value history for the last N days."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DATE(timestamp) as date, SUM(price) as total_value
            FROM price_history
            WHERE timestamp >= DATE('now', ?)
            GROUP BY DATE(timestamp)
            ORDER BY date
        """, (f'-{days} days',))

        rows = cursor.fetchall()
        conn.close()

        return [{'date': row['date'], 'value': row['total_value']} for row in rows]


class SettingsOperations:
    """CRUD operations for settings."""

    @staticmethod
    def get(key: str, default: str = "") -> str:
        """Get a setting value."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()

        return row['value'] if row else default

    @staticmethod
    def set(key: str, value: str) -> bool:
        """Set a setting value."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        """, (key, value))

        conn.commit()
        conn.close()
        return True

    @staticmethod
    def get_all() -> Dict[str, str]:
        """Get all settings."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        conn.close()

        return {row['key']: row['value'] for row in rows}
