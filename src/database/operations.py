"""Database CRUD operations for Asset Tracker."""

import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from .models import Asset, PriceHistory, Liability, Income, Expense, Goal, PaymentHistory, Transaction, get_connection


class AssetOperations:
    """CRUD operations for assets."""

    @staticmethod
    def create(asset: Asset) -> int:
        """Create a new asset and return its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO assets (name, asset_type, symbol, quantity, unit, weight_per_unit,
                              purchase_price, purchase_date, current_price, last_updated, notes,
                              monthly_contribution, baseline_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            asset.monthly_contribution,
            asset.baseline_price
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
                created_at=row['created_at'],
                monthly_contribution=row['monthly_contribution'] if 'monthly_contribution' in row.keys() else 0.0,
                baseline_price=row['baseline_price'] if 'baseline_price' in row.keys() else 0.0
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
                created_at=row['created_at'],
                monthly_contribution=row['monthly_contribution'] if 'monthly_contribution' in row.keys() else 0.0,
                baseline_price=row['baseline_price'] if 'baseline_price' in row.keys() else 0.0
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
                created_at=row['created_at'],
                monthly_contribution=row['monthly_contribution'] if 'monthly_contribution' in row.keys() else 0.0,
                baseline_price=row['baseline_price'] if 'baseline_price' in row.keys() else 0.0
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
                notes = ?,
                monthly_contribution = ?,
                baseline_price = ?
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
            asset.monthly_contribution,
            asset.baseline_price,
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
        metal_ounces = {}  # Track total ounces by metal type (gold, silver, etc.)

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

            # Track metal ounces by symbol (GOLD, SILVER, etc.)
            if asset.asset_type == 'metal' and asset.symbol:
                metal_key = asset.symbol.upper()
                if metal_key not in metal_ounces:
                    metal_ounces[metal_key] = 0.0
                metal_ounces[metal_key] += asset.total_weight

        return {
            'total_assets': len(assets),
            'total_cost': total_cost,
            'total_value': total_value,
            'total_gain_loss': total_gain_loss,
            'gain_loss_percent': (total_gain_loss / total_cost * 100) if total_cost > 0 else 0,
            'by_type': by_type,
            'metal_ounces': metal_ounces
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


class LiabilityOperations:
    """CRUD operations for liabilities."""

    @staticmethod
    def create(liability: Liability) -> int:
        """Create a new liability and return its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO liabilities (name, liability_type, creditor, original_amount,
                                    current_balance, interest_rate, monthly_payment,
                                    minimum_payment, payment_day, is_revolving, credit_limit,
                                    start_date, end_date, notes, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            liability.name,
            liability.liability_type,
            liability.creditor,
            liability.original_amount,
            liability.current_balance,
            liability.interest_rate,
            liability.monthly_payment,
            liability.minimum_payment,
            liability.payment_day,
            1 if liability.is_revolving else 0,
            liability.credit_limit,
            liability.start_date,
            liability.end_date,
            liability.notes,
            now
        ))

        liability_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return liability_id

    @staticmethod
    def _row_to_liability(row) -> Liability:
        """Convert a database row to a Liability object."""
        return Liability(
            id=row['id'],
            name=row['name'],
            liability_type=row['liability_type'],
            creditor=row['creditor'],
            original_amount=row['original_amount'],
            current_balance=row['current_balance'],
            interest_rate=row['interest_rate'],
            monthly_payment=row['monthly_payment'],
            minimum_payment=row['minimum_payment'] if 'minimum_payment' in row.keys() else 0.0,
            payment_day=row['payment_day'] if 'payment_day' in row.keys() else 1,
            is_revolving=bool(row['is_revolving']) if 'is_revolving' in row.keys() else False,
            credit_limit=row['credit_limit'] if 'credit_limit' in row.keys() else 0.0,
            start_date=row['start_date'],
            end_date=row['end_date'],
            notes=row['notes'],
            created_at=row['created_at'],
            last_updated=row['last_updated']
        )

    @staticmethod
    def get_by_id(liability_id: int) -> Optional[Liability]:
        """Get a liability by its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM liabilities WHERE id = ?", (liability_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return LiabilityOperations._row_to_liability(row)
        return None

    @staticmethod
    def get_all() -> List[Liability]:
        """Get all liabilities."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM liabilities ORDER BY liability_type, name")
        rows = cursor.fetchall()
        conn.close()

        return [LiabilityOperations._row_to_liability(row) for row in rows]

    @staticmethod
    def get_by_type(liability_type: str) -> List[Liability]:
        """Get all liabilities of a specific type."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM liabilities WHERE liability_type = ? ORDER BY name",
            (liability_type,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [LiabilityOperations._row_to_liability(row) for row in rows]

    @staticmethod
    def update(liability: Liability) -> bool:
        """Update an existing liability."""
        if liability.id is None:
            return False

        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            UPDATE liabilities SET
                name = ?,
                liability_type = ?,
                creditor = ?,
                original_amount = ?,
                current_balance = ?,
                interest_rate = ?,
                monthly_payment = ?,
                minimum_payment = ?,
                payment_day = ?,
                is_revolving = ?,
                credit_limit = ?,
                start_date = ?,
                end_date = ?,
                notes = ?,
                last_updated = ?
            WHERE id = ?
        """, (
            liability.name,
            liability.liability_type,
            liability.creditor,
            liability.original_amount,
            liability.current_balance,
            liability.interest_rate,
            liability.monthly_payment,
            liability.minimum_payment,
            liability.payment_day,
            1 if liability.is_revolving else 0,
            liability.credit_limit,
            liability.start_date,
            liability.end_date,
            liability.notes,
            now,
            liability.id
        ))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def update_balance(liability_id: int, balance: float) -> bool:
        """Update the current balance of a liability."""
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            UPDATE liabilities SET current_balance = ?, last_updated = ?
            WHERE id = ?
        """, (balance, now, liability_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def delete(liability_id: int) -> bool:
        """Delete a liability."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM liabilities WHERE id = ?", (liability_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def get_total_liabilities() -> float:
        """Get total of all liability balances."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT SUM(current_balance) as total FROM liabilities")
        row = cursor.fetchone()
        conn.close()

        return row['total'] if row['total'] else 0.0

    @staticmethod
    def get_liabilities_summary() -> Dict[str, Any]:
        """Get liabilities summary statistics."""
        liabilities = LiabilityOperations.get_all()

        total_original = sum(l.original_amount for l in liabilities)
        total_balance = sum(l.current_balance for l in liabilities)
        total_monthly_payments = sum(l.monthly_payment for l in liabilities)

        by_type = {}
        for liability in liabilities:
            if liability.liability_type not in by_type:
                by_type[liability.liability_type] = {
                    'count': 0,
                    'original_amount': 0.0,
                    'current_balance': 0.0,
                    'monthly_payment': 0.0
                }
            by_type[liability.liability_type]['count'] += 1
            by_type[liability.liability_type]['original_amount'] += liability.original_amount
            by_type[liability.liability_type]['current_balance'] += liability.current_balance
            by_type[liability.liability_type]['monthly_payment'] += liability.monthly_payment

        return {
            'total_liabilities': len(liabilities),
            'total_original': total_original,
            'total_balance': total_balance,
            'total_paid': total_original - total_balance,
            'total_monthly_payments': total_monthly_payments,
            'by_type': by_type
        }


class IncomeOperations:
    """CRUD operations for income."""

    @staticmethod
    def create(income: Income) -> int:
        """Create a new income source and return its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO income (name, income_type, amount, frequency, source,
                              start_date, end_date, is_active, notes, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            income.name,
            income.income_type,
            income.amount,
            income.frequency,
            income.source,
            income.start_date,
            income.end_date,
            1 if income.is_active else 0,
            income.notes,
            now
        ))

        income_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return income_id

    @staticmethod
    def _row_to_income(row) -> Income:
        """Convert a database row to an Income object."""
        return Income(
            id=row['id'],
            name=row['name'],
            income_type=row['income_type'],
            amount=row['amount'],
            frequency=row['frequency'],
            source=row['source'],
            start_date=row['start_date'],
            end_date=row['end_date'],
            is_active=bool(row['is_active']),
            notes=row['notes'],
            created_at=row['created_at'],
            last_updated=row['last_updated']
        )

    @staticmethod
    def get_by_id(income_id: int) -> Optional[Income]:
        """Get an income source by its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM income WHERE id = ?", (income_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return IncomeOperations._row_to_income(row)
        return None

    @staticmethod
    def get_all() -> List[Income]:
        """Get all income sources."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM income ORDER BY income_type, name")
        rows = cursor.fetchall()
        conn.close()

        return [IncomeOperations._row_to_income(row) for row in rows]

    @staticmethod
    def get_active() -> List[Income]:
        """Get all active income sources."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM income WHERE is_active = 1 ORDER BY income_type, name")
        rows = cursor.fetchall()
        conn.close()

        return [IncomeOperations._row_to_income(row) for row in rows]

    @staticmethod
    def get_by_type(income_type: str) -> List[Income]:
        """Get all income sources of a specific type."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM income WHERE income_type = ? ORDER BY name",
            (income_type,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [IncomeOperations._row_to_income(row) for row in rows]

    @staticmethod
    def update(income: Income) -> bool:
        """Update an existing income source."""
        if income.id is None:
            return False

        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            UPDATE income SET
                name = ?,
                income_type = ?,
                amount = ?,
                frequency = ?,
                source = ?,
                start_date = ?,
                end_date = ?,
                is_active = ?,
                notes = ?,
                last_updated = ?
            WHERE id = ?
        """, (
            income.name,
            income.income_type,
            income.amount,
            income.frequency,
            income.source,
            income.start_date,
            income.end_date,
            1 if income.is_active else 0,
            income.notes,
            now,
            income.id
        ))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def delete(income_id: int) -> bool:
        """Delete an income source."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM income WHERE id = ?", (income_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def get_total_monthly_income() -> float:
        """Get total monthly income from all active sources."""
        incomes = IncomeOperations.get_active()
        return sum(i.monthly_amount for i in incomes)

    @staticmethod
    def get_total_annual_income() -> float:
        """Get total annual income from all active sources."""
        incomes = IncomeOperations.get_active()
        return sum(i.annual_amount for i in incomes)

    @staticmethod
    def get_income_summary() -> Dict[str, Any]:
        """Get income summary statistics."""
        incomes = IncomeOperations.get_all()
        active_incomes = [i for i in incomes if i.is_active]

        total_monthly = sum(i.monthly_amount for i in active_incomes)
        total_annual = sum(i.annual_amount for i in active_incomes)

        by_type = {}
        for income in active_incomes:
            if income.income_type not in by_type:
                by_type[income.income_type] = {
                    'count': 0,
                    'monthly_amount': 0.0,
                    'annual_amount': 0.0
                }
            by_type[income.income_type]['count'] += 1
            by_type[income.income_type]['monthly_amount'] += income.monthly_amount
            by_type[income.income_type]['annual_amount'] += income.annual_amount

        return {
            'total_sources': len(incomes),
            'active_sources': len(active_incomes),
            'total_monthly': total_monthly,
            'total_annual': total_annual,
            'by_type': by_type
        }


class ExpenseOperations:
    """CRUD operations for expenses."""

    @staticmethod
    def create(expense: Expense) -> int:
        """Create a new expense and return its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO expenses (name, expense_type, amount, frequency, category,
                                is_active, notes, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            expense.name,
            expense.expense_type,
            expense.amount,
            expense.frequency,
            expense.category,
            1 if expense.is_active else 0,
            expense.notes,
            now
        ))

        expense_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return expense_id

    @staticmethod
    def _row_to_expense(row) -> Expense:
        """Convert a database row to an Expense object."""
        return Expense(
            id=row['id'],
            name=row['name'],
            expense_type=row['expense_type'],
            amount=row['amount'],
            frequency=row['frequency'],
            category=row['category'],
            is_active=bool(row['is_active']),
            notes=row['notes'],
            created_at=row['created_at'],
            last_updated=row['last_updated']
        )

    @staticmethod
    def get_by_id(expense_id: int) -> Optional[Expense]:
        """Get an expense by its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return ExpenseOperations._row_to_expense(row)
        return None

    @staticmethod
    def get_all() -> List[Expense]:
        """Get all expenses."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM expenses ORDER BY category, expense_type, name")
        rows = cursor.fetchall()
        conn.close()

        return [ExpenseOperations._row_to_expense(row) for row in rows]

    @staticmethod
    def get_active() -> List[Expense]:
        """Get all active expenses."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM expenses WHERE is_active = 1 ORDER BY category, expense_type, name")
        rows = cursor.fetchall()
        conn.close()

        return [ExpenseOperations._row_to_expense(row) for row in rows]

    @staticmethod
    def get_by_type(expense_type: str) -> List[Expense]:
        """Get all expenses of a specific type."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM expenses WHERE expense_type = ? ORDER BY name",
            (expense_type,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [ExpenseOperations._row_to_expense(row) for row in rows]

    @staticmethod
    def get_by_category(category: str) -> List[Expense]:
        """Get all expenses of a specific category (essential/discretionary)."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM expenses WHERE category = ? ORDER BY expense_type, name",
            (category,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [ExpenseOperations._row_to_expense(row) for row in rows]

    @staticmethod
    def update(expense: Expense) -> bool:
        """Update an existing expense."""
        if expense.id is None:
            return False

        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            UPDATE expenses SET
                name = ?,
                expense_type = ?,
                amount = ?,
                frequency = ?,
                category = ?,
                is_active = ?,
                notes = ?,
                last_updated = ?
            WHERE id = ?
        """, (
            expense.name,
            expense.expense_type,
            expense.amount,
            expense.frequency,
            expense.category,
            1 if expense.is_active else 0,
            expense.notes,
            now,
            expense.id
        ))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def delete(expense_id: int) -> bool:
        """Delete an expense."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def get_total_monthly_expenses() -> float:
        """Get total monthly expenses from all active expenses."""
        expenses = ExpenseOperations.get_active()
        return sum(e.monthly_amount for e in expenses)

    @staticmethod
    def get_total_annual_expenses() -> float:
        """Get total annual expenses from all active expenses."""
        expenses = ExpenseOperations.get_active()
        return sum(e.annual_amount for e in expenses)

    @staticmethod
    def get_expense_summary() -> Dict[str, Any]:
        """Get expense summary statistics."""
        expenses = ExpenseOperations.get_all()
        active_expenses = [e for e in expenses if e.is_active]

        total_monthly = sum(e.monthly_amount for e in active_expenses)
        total_annual = sum(e.annual_amount for e in active_expenses)

        essential_monthly = sum(e.monthly_amount for e in active_expenses if e.is_essential)
        discretionary_monthly = sum(e.monthly_amount for e in active_expenses if not e.is_essential)

        by_type = {}
        for expense in active_expenses:
            if expense.expense_type not in by_type:
                by_type[expense.expense_type] = {
                    'count': 0,
                    'monthly_amount': 0.0,
                    'annual_amount': 0.0
                }
            by_type[expense.expense_type]['count'] += 1
            by_type[expense.expense_type]['monthly_amount'] += expense.monthly_amount
            by_type[expense.expense_type]['annual_amount'] += expense.annual_amount

        return {
            'total_expenses': len(expenses),
            'active_expenses': len(active_expenses),
            'total_monthly': total_monthly,
            'total_annual': total_annual,
            'essential_monthly': essential_monthly,
            'discretionary_monthly': discretionary_monthly,
            'by_type': by_type
        }


class GoalOperations:
    """CRUD operations for financial goals."""

    @staticmethod
    def _row_to_goal(row) -> Goal:
        """Convert a database row to a Goal object."""
        return Goal(
            id=row['id'],
            name=row['name'],
            goal_type=row['goal_type'],
            target_amount=row['target_amount'],
            current_amount=row['current_amount'],
            start_amount=row['start_amount'],
            target_date=row['target_date'],
            start_date=row['start_date'],
            is_active=bool(row['is_active']),
            is_completed=bool(row['is_completed']),
            completed_date=row['completed_date'],
            linked_liability_id=row['linked_liability_id'],
            linked_asset_type=row['linked_asset_type'],
            milestones=row['milestones'] or '[]',
            notes=row['notes'],
            created_at=row['created_at'],
            last_updated=row['last_updated']
        )

    @staticmethod
    def create(goal: Goal) -> int:
        """Create a new goal and return its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO goals (name, goal_type, target_amount, current_amount, start_amount,
                              target_date, start_date, is_active, is_completed, completed_date,
                              linked_liability_id, linked_asset_type, milestones, notes, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            goal.name,
            goal.goal_type,
            goal.target_amount,
            goal.current_amount,
            goal.start_amount,
            goal.target_date,
            goal.start_date,
            1 if goal.is_active else 0,
            1 if goal.is_completed else 0,
            goal.completed_date,
            goal.linked_liability_id,
            goal.linked_asset_type,
            goal.milestones,
            goal.notes,
            now
        ))

        goal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return goal_id

    @staticmethod
    def get_by_id(goal_id: int) -> Optional[Goal]:
        """Get a goal by its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return GoalOperations._row_to_goal(row)
        return None

    @staticmethod
    def get_all() -> List[Goal]:
        """Get all goals."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM goals ORDER BY is_completed, goal_type, name")
        rows = cursor.fetchall()
        conn.close()

        return [GoalOperations._row_to_goal(row) for row in rows]

    @staticmethod
    def get_active() -> List[Goal]:
        """Get all active (non-completed) goals."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM goals WHERE is_active = 1 AND is_completed = 0 ORDER BY goal_type, name")
        rows = cursor.fetchall()
        conn.close()

        return [GoalOperations._row_to_goal(row) for row in rows]

    @staticmethod
    def update(goal: Goal) -> bool:
        """Update an existing goal."""
        if goal.id is None:
            return False

        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute("""
            UPDATE goals SET
                name = ?,
                goal_type = ?,
                target_amount = ?,
                current_amount = ?,
                start_amount = ?,
                target_date = ?,
                start_date = ?,
                is_active = ?,
                is_completed = ?,
                completed_date = ?,
                linked_liability_id = ?,
                linked_asset_type = ?,
                milestones = ?,
                notes = ?,
                last_updated = ?
            WHERE id = ?
        """, (
            goal.name,
            goal.goal_type,
            goal.target_amount,
            goal.current_amount,
            goal.start_amount,
            goal.target_date,
            goal.start_date,
            1 if goal.is_active else 0,
            1 if goal.is_completed else 0,
            goal.completed_date,
            goal.linked_liability_id,
            goal.linked_asset_type,
            goal.milestones,
            goal.notes,
            now,
            goal.id
        ))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def delete(goal_id: int) -> bool:
        """Delete a goal."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def refresh_all_goal_progress():
        """Recalculate progress for all active goals from live data."""
        import json

        goals = GoalOperations.get_active()
        if not goals:
            return

        for goal in goals:
            new_amount = goal.current_amount
            now = datetime.now().isoformat()

            if goal.goal_type == 'debt_payoff' and goal.linked_liability_id:
                liability = LiabilityOperations.get_by_id(goal.linked_liability_id)
                if liability:
                    new_amount = liability.current_balance

            elif goal.goal_type == 'net_worth':
                total_assets = sum(a.current_value for a in AssetOperations.get_all())
                total_liabilities = LiabilityOperations.get_total_liabilities()
                new_amount = total_assets - total_liabilities

            elif goal.goal_type in ('savings', 'asset_acquisition') and goal.linked_asset_type:
                assets = AssetOperations.get_by_type(goal.linked_asset_type)
                new_amount = sum(a.current_value for a in assets)

            if new_amount != goal.current_amount:
                # Update milestones
                milestones = json.loads(goal.milestones or '[]')
                for ms in milestones:
                    if not ms.get('reached'):
                        ms_amount = ms.get('amount', float('inf'))
                        if goal.goal_type == 'debt_payoff':
                            paid = goal.start_amount - new_amount
                            target_paid = goal.start_amount * (ms_amount / goal.start_amount) if goal.start_amount > 0 else 0
                            if paid >= target_paid:
                                ms['reached'] = True
                                ms['date'] = now
                        else:
                            if new_amount >= ms_amount:
                                ms['reached'] = True
                                ms['date'] = now

                # Check completion
                is_completed = False
                if goal.goal_type == 'debt_payoff':
                    is_completed = new_amount <= 0
                else:
                    is_completed = new_amount >= goal.target_amount

                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE goals SET current_amount = ?, milestones = ?,
                        is_completed = ?, completed_date = ?, last_updated = ?
                    WHERE id = ?
                """, (
                    new_amount, json.dumps(milestones),
                    1 if is_completed else 0,
                    now if is_completed and not goal.is_completed else goal.completed_date,
                    now, goal.id
                ))
                conn.commit()
                conn.close()


class PaymentOperations:
    """Operations for recording and applying loan payments."""

    @staticmethod
    def _row_to_payment(row) -> PaymentHistory:
        """Convert a database row to a PaymentHistory object."""
        return PaymentHistory(
            id=row['id'],
            liability_id=row['liability_id'],
            payment_date=row['payment_date'],
            payment_amount=row['payment_amount'],
            interest_portion=row['interest_portion'],
            principal_portion=row['principal_portion'],
            balance_before=row['balance_before'],
            balance_after=row['balance_after'],
            is_auto=bool(row['is_auto']),
            created_at=row['created_at']
        )

    @staticmethod
    def record_payment(payment: PaymentHistory) -> int:
        """Record a payment and return its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO payment_history (liability_id, payment_date, payment_amount,
                                        interest_portion, principal_portion,
                                        balance_before, balance_after, is_auto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payment.liability_id,
            payment.payment_date,
            payment.payment_amount,
            payment.interest_portion,
            payment.principal_portion,
            payment.balance_before,
            payment.balance_after,
            1 if payment.is_auto else 0
        ))

        payment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return payment_id

    @staticmethod
    def get_by_liability(liability_id: int, limit: int = 100) -> List[PaymentHistory]:
        """Get payment history for a liability, most recent first."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM payment_history
            WHERE liability_id = ?
            ORDER BY payment_date DESC
            LIMIT ?
        """, (liability_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [PaymentOperations._row_to_payment(row) for row in rows]

    @staticmethod
    def has_payment_for_month(liability_id: int, year: int, month: int) -> bool:
        """Check if a payment has already been recorded for a given month."""
        conn = get_connection()
        cursor = conn.cursor()

        date_prefix = f"{year:04d}-{month:02d}"
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM payment_history
            WHERE liability_id = ? AND payment_date LIKE ?
        """, (liability_id, f"{date_prefix}%"))

        row = cursor.fetchone()
        conn.close()
        return row['cnt'] > 0

    @staticmethod
    def apply_monthly_payments() -> List[Dict[str, Any]]:
        """Apply monthly payments to all active liabilities for any due months.

        Checks each liability and applies payments for months between the last
        recorded payment and the current month. Returns a list of applied payments.
        """
        results = []
        liabilities = LiabilityOperations.get_all()
        now = datetime.now()
        current_year = now.year
        current_month = now.month

        for liability in liabilities:
            if liability.current_balance <= 0 or liability.monthly_payment <= 0:
                continue

            # Find the last payment date for this liability
            last_payments = PaymentOperations.get_by_liability(liability.id, limit=1)
            if last_payments:
                try:
                    last_date = datetime.fromisoformat(last_payments[0].payment_date)
                    start_year = last_date.year
                    start_month = last_date.month
                    # Start from the month AFTER the last payment
                    start_month += 1
                    if start_month > 12:
                        start_month = 1
                        start_year += 1
                except (ValueError, TypeError):
                    # If we can't parse, start from current month
                    start_year = current_year
                    start_month = current_month
            else:
                # No previous payments - only apply for current month
                start_year = current_year
                start_month = current_month

            # Apply payments for each due month up to and including current
            year, month = start_year, start_month
            balance = liability.current_balance

            while (year < current_year or (year == current_year and month <= current_month)):
                if balance <= 0:
                    break

                # Calculate interest on current balance
                interest = balance * liability.monthly_interest_rate
                payment = min(liability.monthly_payment, balance + interest)
                principal = payment - interest
                if principal < 0:
                    principal = 0
                new_balance = max(0, balance - principal)

                payment_date = f"{year:04d}-{month:02d}-{liability.payment_day:02d}"

                record = PaymentHistory(
                    liability_id=liability.id,
                    payment_date=payment_date,
                    payment_amount=round(payment, 2),
                    interest_portion=round(interest, 2),
                    principal_portion=round(principal, 2),
                    balance_before=round(balance, 2),
                    balance_after=round(new_balance, 2),
                    is_auto=True
                )
                PaymentOperations.record_payment(record)

                results.append({
                    'liability': liability.name,
                    'date': payment_date,
                    'payment': round(payment, 2),
                    'interest': round(interest, 2),
                    'principal': round(principal, 2),
                    'balance_after': round(new_balance, 2)
                })

                balance = new_balance

                # Advance to next month
                month += 1
                if month > 12:
                    month = 1
                    year += 1

            # Update the liability balance if payments were applied
            if balance != liability.current_balance:
                LiabilityOperations.update_balance(liability.id, round(balance, 2))

        return results

    @staticmethod
    def get_all_history(limit: int = 200) -> List[PaymentHistory]:
        """Get all payment history across all liabilities."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM payment_history
            ORDER BY payment_date DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [PaymentOperations._row_to_payment(row) for row in rows]


class TransactionOperations:
    """CRUD operations for imported transactions."""

    @staticmethod
    def _row_to_transaction(row) -> Transaction:
        """Convert a database row to a Transaction object."""
        return Transaction(
            id=row['id'],
            transaction_date=row['transaction_date'],
            description=row['description'],
            amount=row['amount'],
            category=row['category'],
            transaction_type=row['transaction_type'],
            account_name=row['account_name'],
            original_description=row['original_description'],
            is_income=bool(row['is_income']),
            notes=row['notes'],
            created_at=row['created_at']
        )

    @staticmethod
    def create(transaction: Transaction) -> int:
        """Create a new transaction and return its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO transactions (transaction_date, description, amount, category,
                                     transaction_type, account_name, original_description,
                                     is_income, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            transaction.transaction_date,
            transaction.description,
            transaction.amount,
            transaction.category,
            transaction.transaction_type,
            transaction.account_name,
            transaction.original_description,
            1 if transaction.is_income else 0,
            transaction.notes
        ))

        txn_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return txn_id

    @staticmethod
    def create_bulk(transactions: List[Transaction]) -> int:
        """Bulk insert transactions. Returns count of inserted rows."""
        if not transactions:
            return 0

        conn = get_connection()
        cursor = conn.cursor()

        rows = [
            (t.transaction_date, t.description, t.amount, t.category,
             t.transaction_type, t.account_name, t.original_description,
             1 if t.is_income else 0, t.notes)
            for t in transactions
        ]

        cursor.executemany("""
            INSERT INTO transactions (transaction_date, description, amount, category,
                                     transaction_type, account_name, original_description,
                                     is_income, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count

    @staticmethod
    def get_by_id(transaction_id: int) -> Optional[Transaction]:
        """Get a transaction by its ID."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return TransactionOperations._row_to_transaction(row)
        return None

    @staticmethod
    def get_all(limit: int = 500) -> List[Transaction]:
        """Get all transactions, most recent first."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM transactions
            ORDER BY transaction_date DESC, id DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [TransactionOperations._row_to_transaction(row) for row in rows]

    @staticmethod
    def get_by_date_range(start_date: str, end_date: str) -> List[Transaction]:
        """Get transactions within a date range."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM transactions
            WHERE transaction_date BETWEEN ? AND ?
            ORDER BY transaction_date DESC, id DESC
        """, (start_date, end_date))

        rows = cursor.fetchall()
        conn.close()

        return [TransactionOperations._row_to_transaction(row) for row in rows]

    @staticmethod
    def get_by_category(category: str) -> List[Transaction]:
        """Get all transactions of a specific category."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM transactions
            WHERE category = ?
            ORDER BY transaction_date DESC
        """, (category,))

        rows = cursor.fetchall()
        conn.close()

        return [TransactionOperations._row_to_transaction(row) for row in rows]

    @staticmethod
    def get_by_account(account_name: str) -> List[Transaction]:
        """Get all transactions for an account."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM transactions
            WHERE account_name = ?
            ORDER BY transaction_date DESC
        """, (account_name,))

        rows = cursor.fetchall()
        conn.close()

        return [TransactionOperations._row_to_transaction(row) for row in rows]

    @staticmethod
    def get_accounts() -> List[str]:
        """Get distinct account names."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT account_name FROM transactions ORDER BY account_name")
        rows = cursor.fetchall()
        conn.close()

        return [row['account_name'] for row in rows]

    @staticmethod
    def get_categories() -> List[str]:
        """Get distinct categories."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT category FROM transactions WHERE category != '' ORDER BY category")
        rows = cursor.fetchall()
        conn.close()

        return [row['category'] for row in rows]

    @staticmethod
    def update(transaction: Transaction) -> bool:
        """Update an existing transaction."""
        if transaction.id is None:
            return False

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE transactions SET
                transaction_date = ?,
                description = ?,
                amount = ?,
                category = ?,
                transaction_type = ?,
                account_name = ?,
                original_description = ?,
                is_income = ?,
                notes = ?
            WHERE id = ?
        """, (
            transaction.transaction_date,
            transaction.description,
            transaction.amount,
            transaction.category,
            transaction.transaction_type,
            transaction.account_name,
            transaction.original_description,
            1 if transaction.is_income else 0,
            transaction.notes,
            transaction.id
        ))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def delete(transaction_id: int) -> bool:
        """Delete a transaction."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    @staticmethod
    def exists(date: str, amount: float, description: str) -> bool:
        """Check if a transaction already exists (for duplicate detection)."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as cnt FROM transactions
            WHERE transaction_date = ? AND amount = ? AND original_description = ?
        """, (date, amount, description))

        row = cursor.fetchone()
        conn.close()
        return row['cnt'] > 0

    # Categories that are not discretionary spending
    NON_SPENDING_CATEGORIES = {'debt', 'transfers', 'income', 'retirement'}

    @staticmethod
    def get_spending_summary(include_non_spending: bool = False) -> Dict[str, Any]:
        """Get spending summary by category.

        By default excludes debt payments, transfers, income, and retirement
        contributions since those aren't discretionary spending.
        """
        conn = get_connection()
        cursor = conn.cursor()

        if include_non_spending:
            cursor.execute("""
                SELECT category,
                       COUNT(*) as count,
                       SUM(amount) as total,
                       AVG(amount) as avg_amount
                FROM transactions
                WHERE amount < 0
                GROUP BY category
                ORDER BY total ASC
            """)
        else:
            placeholders = ','.join('?' for _ in TransactionOperations.NON_SPENDING_CATEGORIES)
            cursor.execute(f"""
                SELECT category,
                       COUNT(*) as count,
                       SUM(amount) as total,
                       AVG(amount) as avg_amount
                FROM transactions
                WHERE amount < 0
                  AND category NOT IN ({placeholders})
                GROUP BY category
                ORDER BY total ASC
            """, tuple(TransactionOperations.NON_SPENDING_CATEGORIES))

        rows = cursor.fetchall()
        conn.close()

        by_category = {}
        for row in rows:
            cat = row['category'] or 'uncategorized'
            by_category[cat] = {
                'count': row['count'],
                'total': row['total'],
                'avg': row['avg_amount']
            }

        return by_category

    @staticmethod
    def get_non_spending_summary() -> Dict[str, Any]:
        """Get summary of debt payments, transfers, etc. (non-spending outflows)."""
        conn = get_connection()
        cursor = conn.cursor()

        placeholders = ','.join('?' for _ in TransactionOperations.NON_SPENDING_CATEGORIES)
        cursor.execute(f"""
            SELECT category,
                   COUNT(*) as count,
                   SUM(amount) as total,
                   AVG(amount) as avg_amount
            FROM transactions
            WHERE amount < 0
              AND category IN ({placeholders})
            GROUP BY category
            ORDER BY total ASC
        """, tuple(TransactionOperations.NON_SPENDING_CATEGORIES))

        rows = cursor.fetchall()
        conn.close()

        by_category = {}
        for row in rows:
            cat = row['category'] or 'uncategorized'
            by_category[cat] = {
                'count': row['count'],
                'total': row['total'],
                'avg': row['avg_amount']
            }

        return by_category

    @staticmethod
    def recategorize_all():
        """Re-run auto-categorization on all transactions."""
        from ..utils.csv_importer import auto_categorize
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, description, original_description, transaction_type, amount FROM transactions")
        rows = cursor.fetchall()

        for row in rows:
            desc = row['original_description'] or row['description']
            txn_type = row['transaction_type'] or ''
            new_category = auto_categorize(desc, txn_type)
            is_income = row['amount'] > 0
            cursor.execute(
                "UPDATE transactions SET category = ?, is_income = ? WHERE id = ?",
                (new_category, is_income, row['id'])
            )

        conn.commit()
        conn.close()
        return len(rows)

    @staticmethod
    def get_deposit_totals() -> Dict[str, Any]:
        """Get total income deposits (excludes debt repayments and transfers in)."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as count,
                   COALESCE(SUM(amount), 0) as total
            FROM transactions
            WHERE amount > 0
              AND category = 'income'
        """)

        row = cursor.fetchone()
        conn.close()

        if row and row['count'] > 0:
            return {'count': row['count'], 'total': row['total']}
        return {}
