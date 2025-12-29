"""Add/Edit income dialog."""

from datetime import date
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QDateEdit,
    QTextEdit, QPushButton, QLabel, QMessageBox, QGroupBox, QCheckBox
)
from PyQt6.QtCore import Qt, QDate
from ...database.models import Income
from ...database.operations import IncomeOperations


class AddIncomeDialog(QDialog):
    """Dialog for adding or editing an income source."""

    def __init__(self, parent=None, income: Optional[Income] = None):
        super().__init__(parent)
        self.income = income
        self.is_edit = income is not None
        self._setup_ui()
        if self.is_edit:
            self._populate_fields()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Edit Income" if self.is_edit else "Add Income")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Basic info group
        basic_group = QGroupBox("Income Information")
        basic_layout = QFormLayout(basic_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Primary Job, Freelance Work")
        basic_layout.addRow("Name:", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Salary/Wages", "salary")
        self.type_combo.addItem("Bonus", "bonus")
        self.type_combo.addItem("Investment Income", "investment")
        self.type_combo.addItem("Rental Income", "rental")
        self.type_combo.addItem("Side Gig/Freelance", "side_gig")
        self.type_combo.addItem("Other", "other")
        basic_layout.addRow("Type:", self.type_combo)

        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("e.g., Employer name, Client name")
        basic_layout.addRow("Source:", self.source_edit)

        self.is_active_check = QCheckBox("Active")
        self.is_active_check.setChecked(True)
        self.is_active_check.setToolTip("Uncheck for past or inactive income sources")
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

        # Dates group
        dates_group = QGroupBox("Dates")
        dates_layout = QFormLayout(dates_group)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())
        dates_layout.addRow("Start Date:", self.start_date_edit)

        self.has_end_date_check = QCheckBox("Has End Date")
        self.has_end_date_check.setChecked(False)
        self.has_end_date_check.stateChanged.connect(self._on_end_date_toggle)
        dates_layout.addRow("", self.has_end_date_check)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate().addYears(1))
        self.end_date_edit.setEnabled(False)
        self.end_date_label = QLabel("End Date:")
        dates_layout.addRow(self.end_date_label, self.end_date_edit)

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

        # Initial calculation
        self._update_calculated_amounts()

    def _on_end_date_toggle(self, state: int):
        """Toggle end date field."""
        has_end = state == Qt.CheckState.Checked.value
        self.end_date_edit.setEnabled(has_end)

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
        elif frequency == 'annual':
            monthly = amount / 12
            annual = amount
        else:
            monthly = amount
            annual = amount * 12

        self.monthly_label.setText(f"${monthly:,.2f}")
        self.annual_label.setText(f"${annual:,.2f}")

    def _populate_fields(self):
        """Populate fields with existing income data."""
        if not self.income:
            return

        self.name_edit.setText(self.income.name)

        # Find and set the correct type index
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == self.income.income_type:
                self.type_combo.setCurrentIndex(i)
                break

        self.source_edit.setText(self.income.source or "")
        self.is_active_check.setChecked(self.income.is_active)
        self.amount_spin.setValue(self.income.amount)

        # Find and set the correct frequency index
        for i in range(self.frequency_combo.count()):
            if self.frequency_combo.itemData(i) == self.income.frequency:
                self.frequency_combo.setCurrentIndex(i)
                break

        if self.income.start_date:
            try:
                qdate = QDate.fromString(self.income.start_date, Qt.DateFormat.ISODate)
                if qdate.isValid():
                    self.start_date_edit.setDate(qdate)
            except Exception:
                pass

        if self.income.end_date:
            self.has_end_date_check.setChecked(True)
            self._on_end_date_toggle(Qt.CheckState.Checked.value)
            try:
                qdate = QDate.fromString(self.income.end_date, Qt.DateFormat.ISODate)
                if qdate.isValid():
                    self.end_date_edit.setDate(qdate)
            except Exception:
                pass

        self.notes_edit.setPlainText(self.income.notes or "")
        self._update_calculated_amounts()

    def _save(self):
        """Save the income."""
        # Validate
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Please enter a name.")
            return

        if self.amount_spin.value() <= 0:
            QMessageBox.warning(self, "Validation", "Please enter an amount.")
            return

        # Create or update income
        if self.is_edit:
            income = self.income
        else:
            income = Income()

        income.name = name
        income.income_type = self.type_combo.currentData()
        income.source = self.source_edit.text().strip()
        income.is_active = self.is_active_check.isChecked()
        income.amount = self.amount_spin.value()
        income.frequency = self.frequency_combo.currentData()
        income.start_date = self.start_date_edit.date().toString(Qt.DateFormat.ISODate)

        if self.has_end_date_check.isChecked():
            income.end_date = self.end_date_edit.date().toString(Qt.DateFormat.ISODate)
        else:
            income.end_date = None

        income.notes = self.notes_edit.toPlainText().strip()

        try:
            if self.is_edit:
                IncomeOperations.update(income)
            else:
                IncomeOperations.create(income)

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")

    def get_income(self) -> Optional[Income]:
        """Get the created/edited income."""
        return self.income
