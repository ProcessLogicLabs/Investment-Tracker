"""Budget wizard: create expense budget lines from imported transaction data."""

from datetime import datetime
from typing import Dict, Any, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit, QGroupBox,
    QFormLayout, QMessageBox, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ...database.models import Expense
from ...database.operations import TransactionOperations, ExpenseOperations


# Map transaction category -> (expense_type, is_essential_default, default_budget_multiplier)
# The multiplier rounds budget slightly above/below actual for realistic targets.
CATEGORY_TO_EXPENSE_TYPE = {
    'housing':        ('housing',        True,  1.00),
    'utilities':      ('utilities',      True,  1.05),
    'transportation': ('transportation', True,  1.10),
    'food':           ('food',           True,  1.00),
    'automotive':     ('transportation', True,  1.00),
    'healthcare':     ('healthcare',     True,  1.00),
    'insurance':      ('insurance',      True,  1.00),
    'personal':       ('personal',       False, 1.00),
    'subscriptions':  ('subscriptions',  False, 1.00),
    'entertainment':  ('entertainment',  False, 1.00),
    'bills & utilities': ('utilities',   True,  1.05),
    'cash':           ('other',          False, 1.00),
    'uncategorized':  ('other',          False, 1.00),
    'other':          ('other',          False, 1.00),
}

# Columns: 0=include, 1=category, 2=expense_type, 3=actual/mo, 4=budget/mo, 5=essential
COL_INCLUDE = 0
COL_CATEGORY = 1
COL_EXPENSE_TYPE = 2
COL_ACTUAL = 3
COL_BUDGET = 4
COL_ESSENTIAL = 5

EXPENSE_TYPE_OPTIONS = [
    ('housing', 'Housing'),
    ('utilities', 'Utilities'),
    ('transportation', 'Transportation'),
    ('food', 'Food/Groceries'),
    ('insurance', 'Insurance'),
    ('healthcare', 'Healthcare'),
    ('entertainment', 'Entertainment'),
    ('subscriptions', 'Subscriptions'),
    ('debt', 'Debt Payments'),
    ('childcare', 'Childcare/Education'),
    ('personal', 'Personal Care'),
    ('other', 'Other'),
]


class BudgetWizardDialog(QDialog):
    """Wizard that turns imported transaction spending into an Expense budget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Budget from Transactions")
        self.setMinimumSize(900, 600)
        self.created_count = 0
        self.replaced_count = 0
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header info
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # Strategy selection
        strategy_group = QGroupBox("Budget Strategy")
        strategy_layout = QVBoxLayout(strategy_group)

        self.strategy_group = QButtonGroup(self)
        self.match_actual_radio = QRadioButton(
            "Match actual spending (use your real averages as the budget)"
        )
        self.match_actual_radio.setChecked(True)
        self.match_actual_radio.toggled.connect(self._on_strategy_changed)
        self.strategy_group.addButton(self.match_actual_radio)
        strategy_layout.addWidget(self.match_actual_radio)

        self.reduce_10_radio = QRadioButton(
            "Trim 10% from actual (aspirational — aims to spend less)"
        )
        self.reduce_10_radio.toggled.connect(self._on_strategy_changed)
        self.strategy_group.addButton(self.reduce_10_radio)
        strategy_layout.addWidget(self.reduce_10_radio)

        self.reduce_20_radio = QRadioButton(
            "Trim 20% from actual (aggressive savings)"
        )
        self.reduce_20_radio.toggled.connect(self._on_strategy_changed)
        self.strategy_group.addButton(self.reduce_20_radio)
        strategy_layout.addWidget(self.reduce_20_radio)

        layout.addWidget(strategy_group)

        # Existing expense handling
        existing_group = QGroupBox("If a budget item already exists for a category:")
        existing_layout = QVBoxLayout(existing_group)

        self.existing_group = QButtonGroup(self)
        self.skip_existing_radio = QRadioButton("Skip — don't touch existing budget items")
        self.skip_existing_radio.setChecked(True)
        self.existing_group.addButton(self.skip_existing_radio)
        existing_layout.addWidget(self.skip_existing_radio)

        self.add_alongside_radio = QRadioButton("Add alongside — create a new budget item with '(from transactions)' suffix")
        self.existing_group.addButton(self.add_alongside_radio)
        existing_layout.addWidget(self.add_alongside_radio)

        self.replace_existing_radio = QRadioButton("Replace — update the existing budget item's amount")
        self.existing_group.addButton(self.replace_existing_radio)
        existing_layout.addWidget(self.replace_existing_radio)

        layout.addWidget(existing_group)

        # Budget proposal table
        table_group = QGroupBox("Proposed Budget Lines")
        table_layout = QVBoxLayout(table_group)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Include", "Transaction Category", "Budget Type",
            "Actual / mo", "Budget / mo", "Essential"
        ])
        self.table.setColumnWidth(COL_INCLUDE, 70)
        self.table.setColumnWidth(COL_CATEGORY, 170)
        self.table.setColumnWidth(COL_EXPENSE_TYPE, 170)
        self.table.setColumnWidth(COL_ACTUAL, 120)
        self.table.setColumnWidth(COL_BUDGET, 140)
        self.table.setColumnWidth(COL_ESSENTIAL, 80)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setAlternatingRowColors(True)
        table_layout.addWidget(self.table)

        # Totals row
        totals_row = QHBoxLayout()
        self.total_actual_label = QLabel("Actual total: $0.00/mo")
        self.total_budget_label = QLabel("Budget total: $0.00/mo")
        bold = QFont()
        bold.setBold(True)
        self.total_actual_label.setFont(bold)
        self.total_budget_label.setFont(bold)
        totals_row.addWidget(self.total_actual_label)
        totals_row.addStretch()
        totals_row.addWidget(self.total_budget_label)
        table_layout.addLayout(totals_row)

        layout.addWidget(table_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.create_btn = QPushButton("Create Budget")
        self.create_btn.setDefault(True)
        self.create_btn.clicked.connect(self._accept)
        btn_row.addWidget(self.create_btn)

        layout.addLayout(btn_row)

    def _load_data(self):
        """Pull spending data and build the proposal table."""
        spending = TransactionOperations.get_spending_summary()

        # Determine the transaction date range for monthly averaging
        all_txns = TransactionOperations.get_all(limit=10000)
        dates = [t.transaction_date for t in all_txns if t.transaction_date]
        months_span = 1.0
        period_str = "unknown"
        if dates:
            try:
                d1 = datetime.strptime(min(dates), '%Y-%m-%d')
                d2 = datetime.strptime(max(dates), '%Y-%m-%d')
                days_span = max((d2 - d1).days, 1)
                months_span = max(days_span / 30.44, 0.5)
                period_str = f"{min(dates)} to {max(dates)} ({months_span:.1f} months)"
            except ValueError:
                pass

        self.months_span = months_span

        if not spending:
            self.info_label.setText(
                "<b>No spending data found.</b><br>"
                "Import bank or credit card transactions first, then come back "
                "to create a budget from your actual spending."
            )
            self.create_btn.setEnabled(False)
            return

        total_actual = sum(abs(d['total']) for d in spending.values())
        monthly_actual = total_actual / months_span

        self.info_label.setText(
            f"<b>Transaction period:</b> {period_str}<br>"
            f"<b>Total spending:</b> ${total_actual:,.2f} "
            f"(~${monthly_actual:,.2f}/mo avg)<br>"
            f"Review and adjust each line below, then click Create Budget."
        )

        # Build existing expense map by expense_type for duplicate detection
        existing_expenses = ExpenseOperations.get_active()
        existing_by_type: Dict[str, Any] = {}
        for exp in existing_expenses:
            existing_by_type.setdefault(exp.expense_type, []).append(exp)
        self.existing_by_type = existing_by_type

        # Populate table
        sorted_cats = sorted(
            spending.items(),
            key=lambda x: x[1]['total']  # most negative first (largest spending)
        )
        self.table.setRowCount(len(sorted_cats))

        for row, (category, data) in enumerate(sorted_cats):
            actual_monthly = abs(data['total']) / months_span

            mapping = CATEGORY_TO_EXPENSE_TYPE.get(
                category.lower(),
                ('other', False, 1.00)
            )
            default_type, default_essential, _ = mapping

            # Col 0: Include checkbox
            include_cb = QCheckBox()
            include_cb.setChecked(True)
            include_cb.stateChanged.connect(self._recalc_totals)
            self._set_cell_widget(row, COL_INCLUDE, include_cb)

            # Col 1: Transaction category (read-only)
            cat_item = QTableWidgetItem(category.title())
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, COL_CATEGORY, cat_item)

            # Col 2: Expense type combo
            type_combo = QComboBox()
            for etype, elabel in EXPENSE_TYPE_OPTIONS:
                type_combo.addItem(elabel, etype)
            # Select default
            idx = type_combo.findData(default_type)
            if idx >= 0:
                type_combo.setCurrentIndex(idx)
            self.table.setCellWidget(row, COL_EXPENSE_TYPE, type_combo)

            # Col 3: Actual monthly (read-only)
            actual_item = QTableWidgetItem(f"${actual_monthly:,.2f}")
            actual_item.setFlags(actual_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            actual_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            actual_item.setData(Qt.ItemDataRole.UserRole, actual_monthly)
            self.table.setItem(row, COL_ACTUAL, actual_item)

            # Col 4: Budget amount (editable spinbox)
            budget_spin = QDoubleSpinBox()
            budget_spin.setRange(0, 999_999_999)
            budget_spin.setDecimals(2)
            budget_spin.setPrefix("$")
            budget_spin.setValue(actual_monthly)
            budget_spin.valueChanged.connect(self._recalc_totals)
            self.table.setCellWidget(row, COL_BUDGET, budget_spin)

            # Col 5: Essential checkbox
            essential_cb = QCheckBox()
            essential_cb.setChecked(default_essential)
            self._set_cell_widget(row, COL_ESSENTIAL, essential_cb)

        self._on_strategy_changed()

    def _set_cell_widget(self, row, col, widget):
        """Center a widget in a table cell."""
        from PyQt6.QtWidgets import QWidget, QHBoxLayout as HB
        container = QWidget()
        lay = HB(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(widget)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setCellWidget(row, col, container)
        widget.setProperty("_table_widget", True)

    def _get_cell_widget(self, row, col):
        """Retrieve the inner widget from a centered container cell."""
        container = self.table.cellWidget(row, col)
        if container is None:
            return None
        # Direct widget (no container wrapper)
        if container.property("_table_widget"):
            return container
        # Container wrapping our widget
        lay = container.layout()
        if lay and lay.count() > 0:
            return lay.itemAt(0).widget()
        return container

    def _on_strategy_changed(self):
        """Apply the selected multiplier to all budget spinboxes."""
        if self.reduce_10_radio.isChecked():
            multiplier = 0.90
        elif self.reduce_20_radio.isChecked():
            multiplier = 0.80
        else:
            multiplier = 1.00

        for row in range(self.table.rowCount()):
            actual_item = self.table.item(row, COL_ACTUAL)
            if not actual_item:
                continue
            actual = actual_item.data(Qt.ItemDataRole.UserRole) or 0.0
            spin = self.table.cellWidget(row, COL_BUDGET)
            if spin:
                spin.setValue(actual * multiplier)

        self._recalc_totals()

    def _recalc_totals(self):
        total_actual = 0.0
        total_budget = 0.0
        for row in range(self.table.rowCount()):
            include_cb = self._get_cell_widget(row, COL_INCLUDE)
            if include_cb is None or not include_cb.isChecked():
                continue
            actual_item = self.table.item(row, COL_ACTUAL)
            budget_spin = self.table.cellWidget(row, COL_BUDGET)
            if actual_item:
                total_actual += actual_item.data(Qt.ItemDataRole.UserRole) or 0.0
            if budget_spin:
                total_budget += budget_spin.value()

        self.total_actual_label.setText(f"Actual total: ${total_actual:,.2f}/mo")
        self.total_budget_label.setText(f"Budget total: ${total_budget:,.2f}/mo")

    def _accept(self):
        """Create Expense records from the checked rows."""
        to_create: List[Dict[str, Any]] = []

        for row in range(self.table.rowCount()):
            include_cb = self._get_cell_widget(row, COL_INCLUDE)
            if include_cb is None or not include_cb.isChecked():
                continue

            category = self.table.item(row, COL_CATEGORY).text()
            type_combo = self.table.cellWidget(row, COL_EXPENSE_TYPE)
            budget_spin = self.table.cellWidget(row, COL_BUDGET)
            essential_cb = self._get_cell_widget(row, COL_ESSENTIAL)

            expense_type = type_combo.currentData()
            amount = budget_spin.value()
            is_essential = essential_cb.isChecked() if essential_cb else False

            if amount <= 0:
                continue

            to_create.append({
                'category': category,
                'expense_type': expense_type,
                'amount': amount,
                'is_essential': is_essential,
            })

        if not to_create:
            QMessageBox.information(
                self, "No Items Selected",
                "No budget items were selected. Check at least one row to create."
            )
            return

        confirm = QMessageBox.question(
            self, "Create Budget",
            f"Create {len(to_create)} budget item(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        how_existing = 'skip'
        if self.add_alongside_radio.isChecked():
            how_existing = 'add'
        elif self.replace_existing_radio.isChecked():
            how_existing = 'replace'

        created = 0
        replaced = 0
        skipped = 0

        for item in to_create:
            existing = self.existing_by_type.get(item['expense_type'], [])

            if existing and how_existing == 'skip':
                skipped += 1
                continue

            if existing and how_existing == 'replace':
                # Replace the first matching active expense's amount
                exp = existing[0]
                exp.amount = item['amount']
                exp.frequency = 'monthly'
                exp.category = 'essential' if item['is_essential'] else 'discretionary'
                ExpenseOperations.update(exp)
                replaced += 1
                continue

            # Create new (either no existing, or "add alongside")
            name = f"{item['category']}"
            if existing and how_existing == 'add':
                name = f"{item['category']} (from transactions)"

            expense = Expense(
                name=name,
                expense_type=item['expense_type'],
                amount=item['amount'],
                frequency='monthly',
                category='essential' if item['is_essential'] else 'discretionary',
                is_active=True,
                notes=f"Auto-created from transaction history ({self.months_span:.1f} months of data)"
            )
            ExpenseOperations.create(expense)
            created += 1

        self.created_count = created
        self.replaced_count = replaced

        msg_parts = []
        if created:
            msg_parts.append(f"{created} created")
        if replaced:
            msg_parts.append(f"{replaced} replaced")
        if skipped:
            msg_parts.append(f"{skipped} skipped (already existed)")

        QMessageBox.information(
            self, "Budget Created",
            f"Budget update complete: {', '.join(msg_parts) if msg_parts else 'nothing changed'}."
        )
        self.accept()
