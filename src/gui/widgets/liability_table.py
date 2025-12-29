"""Liability table widget for displaying portfolio liabilities."""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu,
    QAbstractItemView, QWidget, QVBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QAction
from ...database.models import Liability


class LiabilityTableWidget(QWidget):
    """Widget displaying a table of liabilities."""

    # Signals
    liability_selected = pyqtSignal(int)  # liability_id
    liability_double_clicked = pyqtSignal(int)  # liability_id
    edit_requested = pyqtSignal(int)  # liability_id
    delete_requested = pyqtSignal(int)  # liability_id

    COLUMNS = [
        ('Name', 150),
        ('Type', 100),
        ('Creditor', 120),
        ('Original Amount', 120),
        ('Current Balance', 120),
        ('Paid Off', 100),
        ('Interest Rate', 90),
        ('Monthly Payment', 110),
        ('Last Updated', 140),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._liabilities: List[Liability] = []
        self._setup_ui()

    def _setup_ui(self):
        """Set up the table widget."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([col[0] for col in self.COLUMNS])

        # Set column widths
        for i, (_, width) in enumerate(self.COLUMNS):
            self.table.setColumnWidth(i, width)

        # Configure table behavior
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Stretch last column
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)

        # Connect signals
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

    def set_liabilities(self, liabilities: List[Liability]):
        """Populate the table with liabilities."""
        self._liabilities = liabilities
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(liabilities))

        for row, liability in enumerate(liabilities):
            self._set_row(row, liability)

        self.table.setSortingEnabled(True)

    def _set_row(self, row: int, liability: Liability):
        """Set the data for a single row."""
        # Store liability ID in first column
        name_item = QTableWidgetItem(liability.name)
        name_item.setData(Qt.ItemDataRole.UserRole, liability.id)
        self.table.setItem(row, 0, name_item)

        # Type
        type_display = {
            'mortgage': 'Mortgage',
            'auto': 'Auto Loan',
            'student': 'Student Loan',
            'credit': 'Credit Card',
            'personal': 'Personal Loan',
            'other': 'Other'
        }.get(liability.liability_type, liability.liability_type)
        self.table.setItem(row, 1, QTableWidgetItem(type_display))

        # Creditor
        self.table.setItem(row, 2, QTableWidgetItem(liability.creditor or ''))

        # Original Amount
        orig_item = QTableWidgetItem(f"${liability.original_amount:,.2f}")
        orig_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 3, orig_item)

        # Current Balance
        bal_item = QTableWidgetItem(f"${liability.current_balance:,.2f}")
        bal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bal_item.setForeground(QBrush(QColor('#c62828')))  # Red for debt
        self.table.setItem(row, 4, bal_item)

        # Paid Off (original - current)
        paid = liability.original_amount - liability.current_balance
        paid_percent = (paid / liability.original_amount * 100) if liability.original_amount > 0 else 0
        paid_item = QTableWidgetItem(f"${paid:,.2f} ({paid_percent:.1f}%)")
        paid_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        paid_item.setForeground(QBrush(QColor('#2e7d32')))  # Green for paid
        self.table.setItem(row, 5, paid_item)

        # Interest Rate
        rate_item = QTableWidgetItem(f"{liability.interest_rate:.3f}%")
        rate_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 6, rate_item)

        # Monthly Payment
        payment_item = QTableWidgetItem(f"${liability.monthly_payment:,.2f}")
        payment_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 7, payment_item)

        # Last Updated
        last_updated = liability.last_updated or 'Never'
        if liability.last_updated:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(liability.last_updated)
                last_updated = dt.strftime('%Y-%m-%d %H:%M')
            except Exception:
                pass
        self.table.setItem(row, 8, QTableWidgetItem(last_updated))

    def update_liability_balance(self, liability_id: int, new_balance: float):
        """Update the balance display for a specific liability."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == liability_id:
                for liability in self._liabilities:
                    if liability.id == liability_id:
                        liability.current_balance = new_balance
                        self._set_row(row, liability)
                        break
                break

    def get_selected_liability_id(self) -> Optional[int]:
        """Get the ID of the currently selected liability."""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            item = self.table.item(row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_selection_changed(self):
        """Handle selection change."""
        liability_id = self.get_selected_liability_id()
        if liability_id is not None:
            self.liability_selected.emit(liability_id)

    def _on_double_click(self, item: QTableWidgetItem):
        """Handle double-click on a row."""
        row = item.row()
        name_item = self.table.item(row, 0)
        if name_item:
            liability_id = name_item.data(Qt.ItemDataRole.UserRole)
            if liability_id is not None:
                self.liability_double_clicked.emit(liability_id)

    def _show_context_menu(self, position):
        """Show right-click context menu."""
        liability_id = self.get_selected_liability_id()
        if liability_id is None:
            return

        menu = QMenu(self)

        edit_action = QAction('Edit', self)
        edit_action.triggered.connect(lambda: self.edit_requested.emit(liability_id))
        menu.addAction(edit_action)

        delete_action = QAction('Delete', self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(liability_id))
        menu.addAction(delete_action)

        menu.exec(self.table.mapToGlobal(position))
