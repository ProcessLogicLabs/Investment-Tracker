"""Add/Edit goal dialog."""

import json
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QDateEdit,
    QTextEdit, QPushButton, QLabel, QMessageBox, QGroupBox, QCheckBox
)
from PyQt6.QtCore import Qt, QDate
from ...database.models import Goal
from ...database.operations import GoalOperations, LiabilityOperations


class AddGoalDialog(QDialog):
    """Dialog for adding or editing a financial goal."""

    def __init__(self, parent=None, goal: Optional[Goal] = None):
        super().__init__(parent)
        self.goal = goal
        self.is_edit = goal is not None
        self._setup_ui()
        if self.is_edit:
            self._populate_fields()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Edit Goal" if self.is_edit else "Add Goal")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # Goal info group
        info_group = QGroupBox("Goal Information")
        info_layout = QFormLayout(info_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Emergency Fund, Pay off Car Loan")
        info_layout.addRow("Name:", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Savings Target", "savings")
        self.type_combo.addItem("Debt Payoff", "debt_payoff")
        self.type_combo.addItem("Net Worth Target", "net_worth")
        self.type_combo.addItem("Asset Acquisition", "asset_acquisition")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        info_layout.addRow("Type:", self.type_combo)

        layout.addWidget(info_group)

        # Linked item group
        self.link_group = QGroupBox("Link to Existing Data")
        link_layout = QFormLayout(self.link_group)

        # For debt_payoff: pick a liability
        self.liability_label = QLabel("Liability:")
        self.liability_combo = QComboBox()
        link_layout.addRow(self.liability_label, self.liability_combo)

        # For savings/acquisition: pick asset type
        self.asset_type_label = QLabel("Asset Type:")
        self.asset_type_combo = QComboBox()
        self.asset_type_combo.addItem("Cash/Savings", "cash")
        self.asset_type_combo.addItem("Investments (Stocks)", "stock")
        self.asset_type_combo.addItem("Precious Metals", "metal")
        self.asset_type_combo.addItem("Retirement", "retirement")
        self.asset_type_combo.addItem("Real Estate", "realestate")
        link_layout.addRow(self.asset_type_label, self.asset_type_combo)

        layout.addWidget(self.link_group)

        # Target group
        target_group = QGroupBox("Target")
        target_layout = QFormLayout(target_group)

        self.target_amount_spin = QDoubleSpinBox()
        self.target_amount_spin.setRange(0, 999999999)
        self.target_amount_spin.setDecimals(2)
        self.target_amount_spin.setPrefix("$")
        target_layout.addRow("Target Amount:", self.target_amount_spin)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())
        target_layout.addRow("Start Date:", self.start_date_edit)

        self.has_target_date = QCheckBox("Set Target Date")
        self.has_target_date.stateChanged.connect(self._on_target_date_toggle)
        target_layout.addRow("", self.has_target_date)

        self.target_date_edit = QDateEdit()
        self.target_date_edit.setCalendarPopup(True)
        self.target_date_edit.setDate(QDate.currentDate().addYears(1))
        self.target_date_edit.setEnabled(False)
        target_layout.addRow("Target Date:", self.target_date_edit)

        layout.addWidget(target_group)

        # Milestones group
        milestones_group = QGroupBox("Milestones (Optional)")
        milestones_layout = QVBoxLayout(milestones_group)
        self.auto_milestones = QCheckBox("Auto-generate milestones at 25%, 50%, 75%")
        self.auto_milestones.setChecked(True)
        milestones_layout.addWidget(self.auto_milestones)
        layout.addWidget(milestones_group)

        # Notes group
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
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

        # Populate liability combo
        self._populate_liabilities()
        self._on_type_changed()

    def _on_type_changed(self):
        """Show/hide fields based on goal type."""
        goal_type = self.type_combo.currentData()

        self.liability_combo.setVisible(goal_type == 'debt_payoff')
        self.liability_label.setVisible(goal_type == 'debt_payoff')
        self.asset_type_combo.setVisible(goal_type in ('savings', 'asset_acquisition'))
        self.asset_type_label.setVisible(goal_type in ('savings', 'asset_acquisition'))
        self.link_group.setVisible(goal_type != 'net_worth')

    def _on_target_date_toggle(self, state: int):
        """Enable/disable target date based on checkbox."""
        self.target_date_edit.setEnabled(state == Qt.CheckState.Checked.value)

    def _populate_liabilities(self):
        """Fill liability combo from database."""
        liabilities = LiabilityOperations.get_all()
        for liability in liabilities:
            self.liability_combo.addItem(
                f"{liability.name} (${liability.current_balance:,.2f})", liability.id
            )

    def _populate_fields(self):
        """Populate fields with existing goal data."""
        if not self.goal:
            return

        self.name_edit.setText(self.goal.name)

        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == self.goal.goal_type:
                self.type_combo.setCurrentIndex(i)
                break

        self.target_amount_spin.setValue(self.goal.target_amount)

        if self.goal.start_date:
            try:
                qdate = QDate.fromString(self.goal.start_date, Qt.DateFormat.ISODate)
                if qdate.isValid():
                    self.start_date_edit.setDate(qdate)
            except Exception:
                pass

        if self.goal.target_date:
            self.has_target_date.setChecked(True)
            try:
                qdate = QDate.fromString(self.goal.target_date, Qt.DateFormat.ISODate)
                if qdate.isValid():
                    self.target_date_edit.setDate(qdate)
            except Exception:
                pass

        if self.goal.linked_liability_id:
            for i in range(self.liability_combo.count()):
                if self.liability_combo.itemData(i) == self.goal.linked_liability_id:
                    self.liability_combo.setCurrentIndex(i)
                    break

        if self.goal.linked_asset_type:
            for i in range(self.asset_type_combo.count()):
                if self.asset_type_combo.itemData(i) == self.goal.linked_asset_type:
                    self.asset_type_combo.setCurrentIndex(i)
                    break

        self.notes_edit.setPlainText(self.goal.notes or "")
        self.auto_milestones.setChecked(False)

    def _save(self):
        """Save the goal."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Please enter a name.")
            return

        goal_type = self.type_combo.currentData()
        target_amount = self.target_amount_spin.value()

        if target_amount <= 0 and goal_type != 'debt_payoff':
            QMessageBox.warning(self, "Validation", "Please enter a target amount.")
            return

        if self.is_edit:
            goal = self.goal
        else:
            goal = Goal()

        goal.name = name
        goal.goal_type = goal_type
        goal.target_amount = target_amount
        goal.start_date = self.start_date_edit.date().toString(Qt.DateFormat.ISODate)

        if self.has_target_date.isChecked():
            goal.target_date = self.target_date_edit.date().toString(Qt.DateFormat.ISODate)
        else:
            goal.target_date = None

        # Set linked IDs and auto-populate amounts
        goal.linked_liability_id = None
        goal.linked_asset_type = None

        if goal_type == 'debt_payoff' and self.liability_combo.currentData():
            goal.linked_liability_id = self.liability_combo.currentData()
            liability = LiabilityOperations.get_by_id(goal.linked_liability_id)
            if liability and not self.is_edit:
                goal.start_amount = liability.current_balance
                goal.current_amount = liability.current_balance
                if target_amount <= 0:
                    goal.target_amount = liability.current_balance
        elif goal_type in ('savings', 'asset_acquisition'):
            goal.linked_asset_type = self.asset_type_combo.currentData()

        # Auto milestones
        if self.auto_milestones.isChecked() and goal.target_amount > 0:
            target = goal.target_amount
            milestones = [
                {"amount": target * 0.25, "label": "25%", "reached": False, "date": None},
                {"amount": target * 0.50, "label": "50%", "reached": False, "date": None},
                {"amount": target * 0.75, "label": "75%", "reached": False, "date": None},
            ]
            goal.milestones = json.dumps(milestones)

        goal.notes = self.notes_edit.toPlainText().strip()

        try:
            if self.is_edit:
                GoalOperations.update(goal)
            else:
                GoalOperations.create(goal)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")
