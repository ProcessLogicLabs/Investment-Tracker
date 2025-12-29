"""Expense table widget for displaying expenses."""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu,
    QAbstractItemView, QWidget, QVBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QAction
from ...database.models import Expense


class ExpenseTableWidget(QWidget):
    """Widget displaying a table of expenses."""

    # Signals
    expense_selected = pyqtSignal(int)  # expense_id
    expense_double_clicked = pyqtSignal(int)  # expense_id
    edit_requested = pyqtSignal(int)  # expense_id
    delete_requested = pyqtSignal(int)  # expense_id

    COLUMNS = [
        ('Name', 150),
        ('Type', 120),
        ('Category', 100),
        ('Amount', 100),
        ('Frequency', 90),
        ('Monthly', 110),
        ('Annual', 110),
        ('Status', 70),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expenses: List[Expense] = []
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

    def set_expenses(self, expenses: List[Expense]):
        """Populate the table with expenses."""
        self._expenses = expenses
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(expenses))

        for row, expense in enumerate(expenses):
            self._set_row(row, expense)

        self.table.setSortingEnabled(True)

    def _set_row(self, row: int, expense: Expense):
        """Set the data for a single row."""
        # Store expense ID in first column
        name_item = QTableWidgetItem(expense.name)
        name_item.setData(Qt.ItemDataRole.UserRole, expense.id)
        self.table.setItem(row, 0, name_item)

        # Type
        type_display = {
            'housing': 'Housing',
            'utilities': 'Utilities',
            'transportation': 'Transportation',
            'food': 'Food/Groceries',
            'insurance': 'Insurance',
            'healthcare': 'Healthcare',
            'entertainment': 'Entertainment',
            'subscriptions': 'Subscriptions',
            'debt': 'Debt Payments',
            'childcare': 'Childcare/Education',
            'personal': 'Personal Care',
            'other': 'Other'
        }.get(expense.expense_type, expense.expense_type)
        self.table.setItem(row, 1, QTableWidgetItem(type_display))

        # Category
        category_display = {
            'essential': 'Essential',
            'discretionary': 'Discretionary'
        }.get(expense.category, expense.category)
        category_item = QTableWidgetItem(category_display)
        if expense.is_essential:
            category_item.setForeground(QBrush(QColor('#1565c0')))  # Blue for essential
        else:
            category_item.setForeground(QBrush(QColor('#757575')))  # Gray for discretionary
        self.table.setItem(row, 2, category_item)

        # Amount
        amount_item = QTableWidgetItem(f"${expense.amount:,.2f}")
        amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 3, amount_item)

        # Frequency
        freq_display = {
            'weekly': 'Weekly',
            'biweekly': 'Bi-weekly',
            'monthly': 'Monthly',
            'quarterly': 'Quarterly',
            'annual': 'Annual'
        }.get(expense.frequency, expense.frequency)
        self.table.setItem(row, 4, QTableWidgetItem(freq_display))

        # Monthly Amount
        monthly_item = QTableWidgetItem(f"${expense.monthly_amount:,.2f}")
        monthly_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        monthly_item.setForeground(QBrush(QColor('#c62828')))  # Red for expenses
        self.table.setItem(row, 5, monthly_item)

        # Annual Amount
        annual_item = QTableWidgetItem(f"${expense.annual_amount:,.2f}")
        annual_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        annual_item.setForeground(QBrush(QColor('#c62828')))  # Red for expenses
        self.table.setItem(row, 6, annual_item)

        # Status
        status_item = QTableWidgetItem('Active' if expense.is_active else 'Inactive')
        if expense.is_active:
            status_item.setForeground(QBrush(QColor('#2e7d32')))  # Green
        else:
            status_item.setForeground(QBrush(QColor('#757575')))  # Gray
        self.table.setItem(row, 7, status_item)

    def get_selected_expense_id(self) -> Optional[int]:
        """Get the ID of the currently selected expense."""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            item = self.table.item(row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_selection_changed(self):
        """Handle selection change."""
        expense_id = self.get_selected_expense_id()
        if expense_id is not None:
            self.expense_selected.emit(expense_id)

    def _on_double_click(self, item: QTableWidgetItem):
        """Handle double-click on a row."""
        row = item.row()
        name_item = self.table.item(row, 0)
        if name_item:
            expense_id = name_item.data(Qt.ItemDataRole.UserRole)
            if expense_id is not None:
                self.expense_double_clicked.emit(expense_id)

    def _show_context_menu(self, position):
        """Show right-click context menu."""
        expense_id = self.get_selected_expense_id()
        if expense_id is None:
            return

        menu = QMenu(self)

        edit_action = QAction('Edit', self)
        edit_action.triggered.connect(lambda: self.edit_requested.emit(expense_id))
        menu.addAction(edit_action)

        delete_action = QAction('Delete', self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(expense_id))
        menu.addAction(delete_action)

        menu.exec(self.table.mapToGlobal(position))
