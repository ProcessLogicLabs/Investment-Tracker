"""Add/Edit liability dialog."""

from datetime import date
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QDateEdit, QSpinBox,
    QTextEdit, QPushButton, QLabel, QMessageBox, QGroupBox, QCheckBox
)
from PyQt6.QtCore import Qt, QDate
from ...database.models import Liability
from ...database.operations import LiabilityOperations


class AddLiabilityDialog(QDialog):
    """Dialog for adding or editing a liability."""

    def __init__(self, parent=None, liability: Optional[Liability] = None):
        super().__init__(parent)
        self.liability = liability
        self.is_edit = liability is not None
        self._setup_ui()
        if self.is_edit:
            self._populate_fields()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Edit Liability" if self.is_edit else "Add Liability")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Basic info group
        basic_group = QGroupBox("Liability Information")
        basic_layout = QFormLayout(basic_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Home Mortgage, Car Loan")
        basic_layout.addRow("Name:", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Mortgage", "mortgage")
        self.type_combo.addItem("Auto Loan", "auto")
        self.type_combo.addItem("Student Loan", "student")
        self.type_combo.addItem("Credit Card", "credit")
        self.type_combo.addItem("Personal Loan", "personal")
        self.type_combo.addItem("Other", "other")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        basic_layout.addRow("Type:", self.type_combo)

        # Revolving credit checkbox (for credit cards)
        self.is_revolving_check = QCheckBox("Revolving Credit (Credit Card)")
        self.is_revolving_check.setToolTip("Check for credit cards and lines of credit")
        self.is_revolving_check.stateChanged.connect(self._on_revolving_changed)
        basic_layout.addRow("", self.is_revolving_check)

        self.creditor_edit = QLineEdit()
        self.creditor_edit.setPlaceholderText("e.g., Bank of America, Discover")
        basic_layout.addRow("Creditor:", self.creditor_edit)

        layout.addWidget(basic_group)

        # Financial info group
        financial_group = QGroupBox("Financial Details")
        financial_layout = QFormLayout(financial_group)

        self.original_amount_spin = QDoubleSpinBox()
        self.original_amount_spin.setRange(0, 999999999)
        self.original_amount_spin.setDecimals(2)
        self.original_amount_spin.setPrefix("$")
        financial_layout.addRow("Original Amount:", self.original_amount_spin)

        self.current_balance_spin = QDoubleSpinBox()
        self.current_balance_spin.setRange(0, 999999999)
        self.current_balance_spin.setDecimals(2)
        self.current_balance_spin.setPrefix("$")
        financial_layout.addRow("Current Balance:", self.current_balance_spin)

        self.interest_rate_spin = QDoubleSpinBox()
        self.interest_rate_spin.setRange(0, 100)
        self.interest_rate_spin.setDecimals(3)
        self.interest_rate_spin.setSuffix("%")
        financial_layout.addRow("Interest Rate:", self.interest_rate_spin)

        self.monthly_payment_spin = QDoubleSpinBox()
        self.monthly_payment_spin.setRange(0, 999999999)
        self.monthly_payment_spin.setDecimals(2)
        self.monthly_payment_spin.setPrefix("$")
        financial_layout.addRow("Monthly Payment:", self.monthly_payment_spin)

        self.minimum_payment_spin = QDoubleSpinBox()
        self.minimum_payment_spin.setRange(0, 999999999)
        self.minimum_payment_spin.setDecimals(2)
        self.minimum_payment_spin.setPrefix("$")
        self.minimum_payment_spin.setToolTip("Minimum required payment (for credit cards)")
        self.minimum_payment_label = QLabel("Minimum Payment:")
        financial_layout.addRow(self.minimum_payment_label, self.minimum_payment_spin)

        # Credit limit (for revolving credit)
        self.credit_limit_spin = QDoubleSpinBox()
        self.credit_limit_spin.setRange(0, 999999999)
        self.credit_limit_spin.setDecimals(2)
        self.credit_limit_spin.setPrefix("$")
        self.credit_limit_spin.setToolTip("Credit limit for revolving accounts")
        self.credit_limit_label = QLabel("Credit Limit:")
        financial_layout.addRow(self.credit_limit_label, self.credit_limit_spin)

        # Payment day of month
        self.payment_day_spin = QSpinBox()
        self.payment_day_spin.setRange(1, 28)
        self.payment_day_spin.setValue(1)
        self.payment_day_spin.setToolTip("Day of month payment is due")
        financial_layout.addRow("Payment Due Day:", self.payment_day_spin)

        # Hide revolving-specific fields initially
        self.minimum_payment_label.setVisible(False)
        self.minimum_payment_spin.setVisible(False)
        self.credit_limit_label.setVisible(False)
        self.credit_limit_spin.setVisible(False)

        layout.addWidget(financial_group)

        # Dates group
        dates_group = QGroupBox("Dates")
        dates_layout = QFormLayout(dates_group)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())
        dates_layout.addRow("Start Date:", self.start_date_edit)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate().addYears(30))
        dates_layout.addRow("Expected Payoff:", self.end_date_edit)

        layout.addWidget(dates_group)

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

    def _on_type_changed(self, index: int):
        """Handle liability type change."""
        liability_type = self.type_combo.currentData()
        is_credit = liability_type == 'credit'

        # Auto-check revolving for credit cards
        if is_credit:
            self.is_revolving_check.setChecked(True)
        else:
            self.is_revolving_check.setChecked(False)

    def _on_revolving_changed(self, state: int):
        """Show/hide revolving credit fields."""
        is_revolving = state == Qt.CheckState.Checked.value

        self.minimum_payment_label.setVisible(is_revolving)
        self.minimum_payment_spin.setVisible(is_revolving)
        self.credit_limit_label.setVisible(is_revolving)
        self.credit_limit_spin.setVisible(is_revolving)

    def _populate_fields(self):
        """Populate fields with existing liability data."""
        if not self.liability:
            return

        self.name_edit.setText(self.liability.name)

        # Find and set the correct type index
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == self.liability.liability_type:
                self.type_combo.setCurrentIndex(i)
                break

        self.is_revolving_check.setChecked(self.liability.is_revolving)
        self._on_revolving_changed(Qt.CheckState.Checked.value if self.liability.is_revolving else 0)

        self.creditor_edit.setText(self.liability.creditor or "")
        self.original_amount_spin.setValue(self.liability.original_amount)
        self.current_balance_spin.setValue(self.liability.current_balance)
        self.interest_rate_spin.setValue(self.liability.interest_rate)
        self.monthly_payment_spin.setValue(self.liability.monthly_payment)
        self.minimum_payment_spin.setValue(self.liability.minimum_payment)
        self.credit_limit_spin.setValue(self.liability.credit_limit)
        self.payment_day_spin.setValue(self.liability.payment_day)

        if self.liability.start_date:
            try:
                qdate = QDate.fromString(self.liability.start_date, Qt.DateFormat.ISODate)
                if qdate.isValid():
                    self.start_date_edit.setDate(qdate)
            except Exception:
                pass

        if self.liability.end_date:
            try:
                qdate = QDate.fromString(self.liability.end_date, Qt.DateFormat.ISODate)
                if qdate.isValid():
                    self.end_date_edit.setDate(qdate)
            except Exception:
                pass

        self.notes_edit.setPlainText(self.liability.notes or "")

    def _save(self):
        """Save the liability."""
        # Validate
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Please enter a name.")
            return

        if self.current_balance_spin.value() <= 0:
            QMessageBox.warning(self, "Validation", "Please enter a current balance.")
            return

        # Create or update liability
        if self.is_edit:
            liability = self.liability
        else:
            liability = Liability()

        liability.name = name
        liability.liability_type = self.type_combo.currentData()
        liability.creditor = self.creditor_edit.text().strip()
        liability.original_amount = self.original_amount_spin.value()
        liability.current_balance = self.current_balance_spin.value()
        liability.interest_rate = self.interest_rate_spin.value()
        liability.monthly_payment = self.monthly_payment_spin.value()
        liability.minimum_payment = self.minimum_payment_spin.value()
        liability.payment_day = self.payment_day_spin.value()
        liability.is_revolving = self.is_revolving_check.isChecked()
        liability.credit_limit = self.credit_limit_spin.value()
        liability.start_date = self.start_date_edit.date().toString(Qt.DateFormat.ISODate)
        liability.end_date = self.end_date_edit.date().toString(Qt.DateFormat.ISODate)
        liability.notes = self.notes_edit.toPlainText().strip()

        try:
            if self.is_edit:
                LiabilityOperations.update(liability)
            else:
                LiabilityOperations.create(liability)

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")

    def get_liability(self) -> Optional[Liability]:
        """Get the created/edited liability."""
        return self.liability
