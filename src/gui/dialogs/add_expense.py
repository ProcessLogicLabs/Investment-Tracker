"""Add/Edit expense dialog."""

from datetime import date
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox,
    QTextEdit, QPushButton, QLabel, QMessageBox, QGroupBox, QCheckBox
)
from PyQt6.QtCore import Qt
from ...database.models import Expense
from ...database.operations import ExpenseOperations


class AddExpenseDialog(QDialog):
    """Dialog for adding or editing an expense."""

    def __init__(self, parent=None, expense: Optional[Expense] = None):
        super().__init__(parent)
        self.expense = expense
        self.is_edit = expense is not None
        self._setup_ui()
        if self.is_edit:
            self._populate_fields()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Edit Expense" if self.is_edit else "Add Expense")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Basic info group
        basic_group = QGroupBox("Expense Information")
        basic_layout = QFormLayout(basic_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Rent, Car Insurance, Netflix")
        basic_layout.addRow("Name:", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Housing", "housing")
        self.type_combo.addItem("Utilities", "utilities")
        self.type_combo.addItem("Transportation", "transportation")
        self.type_combo.addItem("Food/Groceries", "food")
        self.type_combo.addItem("Insurance", "insurance")
        self.type_combo.addItem("Healthcare", "healthcare")
        self.type_combo.addItem("Entertainment", "entertainment")
        self.type_combo.addItem("Subscriptions", "subscriptions")
        self.type_combo.addItem("Debt Payments", "debt")
        self.type_combo.addItem("Childcare/Education", "childcare")
        self.type_combo.addItem("Personal Care", "personal")
        self.type_combo.addItem("Other", "other")
        basic_layout.addRow("Type:", self.type_combo)

        self.category_combo = QComboBox()
        self.category_combo.addItem("Essential (Need)", "essential")
        self.category_combo.addItem("Discretionary (Want)", "discretionary")
        self.category_combo.setToolTip(
            "Essential: Required expenses like housing, utilities, food\n"
            "Discretionary: Optional expenses like entertainment, subscriptions"
        )
        basic_layout.addRow("Category:", self.category_combo)

        self.is_active_check = QCheckBox("Active")
        self.is_active_check.setChecked(True)
        self.is_active_check.setToolTip("Uncheck for past or inactive expenses")
        basic_layout.addRow("Status:", self.is_active_check)

        layout.addWidget(basic_group)

        # Financial info group
        financial_group = QGroupBox("Payment Details")
        financial_layout = QFormLayout(financial_group)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 999999999)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix("$")
        financial_layout.addRow("Amount:", self.amount_spin)

        self.frequency_combo = QComboBox()
        self.frequency_combo.addItem("Weekly", "weekly")
        self.frequency_combo.addItem("Bi-weekly", "biweekly")
        self.frequency_combo.addItem("Monthly", "monthly")
        self.frequency_combo.addItem("Quarterly", "quarterly")
        self.frequency_combo.addItem("Annual", "annual")
        self.frequency_combo.setCurrentIndex(2)  # Default to monthly
        self.frequency_combo.currentIndexChanged.connect(self._update_calculated_amounts)
        financial_layout.addRow("Frequency:", self.frequency_combo)

        # Calculated amounts display
        self.monthly_label = QLabel("$0.00")
        self.monthly_label.setStyleSheet("font-weight: bold;")
        financial_layout.addRow("Monthly Amount:", self.monthly_label)

        self.annual_label = QLabel("$0.00")
        self.annual_label.setStyleSheet("font-weight: bold;")
        financial_layout.addRow("Annual Amount:", self.annual_label)

        # Connect amount changes to update display
        self.amount_spin.valueChanged.connect(self._update_calculated_amounts)

        layout.addWidget(financial_group)

        # Notes group
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        notes_layout.addWidget(self.notes_edit)
        layout.addWidget(notes_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        # Initial calculation
        self._update_calculated_amounts()

    def _update_calculated_amounts(self):
        """Update the calculated monthly and annual amounts."""
        amount = self.amount_spin.value()
        frequency = self.frequency_combo.currentData()

        if frequency == 'weekly':
            monthly = amount * 52 / 12
            annual = amount * 52
        elif frequency == 'biweekly':
            monthly = amount * 26 / 12
            annual = amount * 26
        elif frequency == 'monthly':
            monthly = amount
            annual = amount * 12
        elif frequency == 'quarterly':
            monthly = amount / 3
            annual = amount * 4
        elif frequency == 'annual':
            monthly = amount / 12
            annual = amount
        else:
            monthly = amount
            annual = amount * 12

        self.monthly_label.setText(f"${monthly:,.2f}")
        self.annual_label.setText(f"${annual:,.2f}")

    def _populate_fields(self):
        """Populate fields with existing expense data."""
        if not self.expense:
            return

        self.name_edit.setText(self.expense.name)

        # Find and set the correct type index
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == self.expense.expense_type:
                self.type_combo.setCurrentIndex(i)
                break

        # Find and set the correct category index
        for i in range(self.category_combo.count()):
            if self.category_combo.itemData(i) == self.expense.category:
                self.category_combo.setCurrentIndex(i)
                break

        self.is_active_check.setChecked(self.expense.is_active)
        self.amount_spin.setValue(self.expense.amount)

        # Find and set the correct frequency index
        for i in range(self.frequency_combo.count()):
            if self.frequency_combo.itemData(i) == self.expense.frequency:
                self.frequency_combo.setCurrentIndex(i)
                break

        self.notes_edit.setPlainText(self.expense.notes or "")
        self._update_calculated_amounts()

    def _save(self):
        """Save the expense."""
        # Validate
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Please enter a name.")
            return

        if self.amount_spin.value() <= 0:
            QMessageBox.warning(self, "Validation", "Please enter an amount.")
            return

        # Create or update expense
        if self.is_edit:
            expense = self.expense
        else:
            expense = Expense()

        expense.name = name
        expense.expense_type = self.type_combo.currentData()
        expense.category = self.category_combo.currentData()
        expense.is_active = self.is_active_check.isChecked()
        expense.amount = self.amount_spin.value()
        expense.frequency = self.frequency_combo.currentData()
        expense.notes = self.notes_edit.toPlainText().strip()

        try:
            if self.is_edit:
                ExpenseOperations.update(expense)
            else:
                ExpenseOperations.create(expense)

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")

    def get_expense(self) -> Optional[Expense]:
        """Get the created/edited expense."""
        return self.expense
