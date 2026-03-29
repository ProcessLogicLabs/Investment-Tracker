"""Add/Edit transaction dialog."""

from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDoubleSpinBox,
    QComboBox, QDateEdit, QTextEdit, QPushButton, QHBoxLayout,
    QGroupBox, QMessageBox
)
from PyQt6.QtCore import QDate

from ...database.models import Transaction
from ...database.operations import TransactionOperations


CATEGORIES = [
    ('food', 'Food'),
    ('transportation', 'Transportation'),
    ('utilities', 'Utilities'),
    ('personal', 'Personal'),
    ('subscriptions', 'Subscriptions'),
    ('debt', 'Debt'),
    ('transfers', 'Transfers'),
    ('cash', 'Cash'),
    ('income', 'Income'),
    ('housing', 'Housing'),
    ('insurance', 'Insurance'),
    ('healthcare', 'Healthcare'),
    ('entertainment', 'Entertainment'),
    ('retirement', 'Retirement'),
    ('uncategorized', 'Uncategorized'),
    ('other', 'Other'),
]

TRANSACTION_TYPES = [
    ('debit_card', 'Debit Card'),
    ('direct_pay', 'Direct Pay'),
    ('direct_deposit', 'Direct Deposit'),
    ('zelle', 'Zelle'),
    ('bill_pay', 'Bill Pay'),
    ('atm', 'ATM'),
    ('deposit', 'Deposit'),
    ('interest_earned', 'Interest Earned'),
    ('contributions', 'Contributions'),
    ('loan_repayments', 'Loan Repayments'),
    ('check', 'Check'),
    ('transfer', 'Transfer'),
    ('other', 'Other'),
]


class AddTransactionDialog(QDialog):
    """Dialog for adding or editing a transaction."""

    def __init__(self, parent=None, transaction: Optional[Transaction] = None):
        super().__init__(parent)
        self.transaction = transaction
        self.is_edit = transaction is not None
        self.setWindowTitle("Edit Transaction" if self.is_edit else "Add Transaction")
        self.setMinimumWidth(400)
        self._setup_ui()
        if self.is_edit:
            self._populate_fields()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Details group
        details_group = QGroupBox("Transaction Details")
        form = QFormLayout(details_group)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Date:", self.date_edit)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Merchant or payee name")
        form.addRow("Description:", self.description_edit)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(-999999.99, 999999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix("$")
        form.addRow("Amount:", self.amount_spin)

        self.category_combo = QComboBox()
        for value, label in CATEGORIES:
            self.category_combo.addItem(label, value)
        form.addRow("Category:", self.category_combo)

        self.type_combo = QComboBox()
        for value, label in TRANSACTION_TYPES:
            self.type_combo.addItem(label, value)
        form.addRow("Type:", self.type_combo)

        self.account_edit = QLineEdit()
        self.account_edit.setPlaceholderText("e.g. SoFi Checking, Chase Visa")
        form.addRow("Account:", self.account_edit)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_edit)

        layout.addWidget(details_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _populate_fields(self):
        """Fill form fields from existing transaction."""
        t = self.transaction
        if t.transaction_date:
            self.date_edit.setDate(QDate.fromString(t.transaction_date, "yyyy-MM-dd"))
        self.description_edit.setText(t.description)
        self.amount_spin.setValue(t.amount)

        idx = self.category_combo.findData(t.category)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)

        idx = self.type_combo.findData(t.transaction_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        self.account_edit.setText(t.account_name)
        self.notes_edit.setPlainText(t.notes or '')

    def _save(self):
        """Validate and save the transaction."""
        description = self.description_edit.text().strip()
        if not description:
            QMessageBox.warning(self, "Validation Error", "Description is required.")
            return

        amount = self.amount_spin.value()
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        category = self.category_combo.currentData()
        txn_type = self.type_combo.currentData()
        account = self.account_edit.text().strip()
        notes = self.notes_edit.toPlainText().strip()

        txn = Transaction(
            id=self.transaction.id if self.is_edit else None,
            transaction_date=date_str,
            description=description,
            amount=amount,
            category=category,
            transaction_type=txn_type,
            account_name=account,
            original_description=self.transaction.original_description if self.is_edit else description,
            is_income=amount > 0,
            notes=notes,
        )

        if self.is_edit:
            TransactionOperations.update(txn)
        else:
            TransactionOperations.create(txn)

        self.accept()
