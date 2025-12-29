"""Database CRUD operations for Asset Tracker."""

import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from .models import Asset, PriceHistory, Liability, Income, Expense, get_connection


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
