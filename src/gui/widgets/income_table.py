"""Income table widget for displaying income sources."""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu,
    QAbstractItemView, QWidget, QVBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QAction
from ...database.models import Income


class IncomeTableWidget(QWidget):
    """Widget displaying a table of income sources."""

    # Signals
    income_selected = pyqtSignal(int)  # income_id
    income_double_clicked = pyqtSignal(int)  # income_id
    edit_requested = pyqtSignal(int)  # income_id
    delete_requested = pyqtSignal(int)  # income_id

    COLUMNS = [
        ('Name', 150),
        ('Type', 120),
        ('Source', 150),
        ('Amount', 100),
        ('Frequency', 90),
        ('Monthly', 110),
        ('Annual', 110),
        ('Status', 70),
        ('Start Date', 100),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._incomes: List[Income] = []
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

    def set_incomes(self, incomes: List[Income]):
        """Populate the table with incomes."""
        self._incomes = incomes
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(incomes))

        for row, income in enumerate(incomes):
            self._set_row(row, income)

        self.table.setSortingEnabled(True)

    def _set_row(self, row: int, income: Income):
        """Set the data for a single row."""
        # Store income ID in first column
        name_item = QTableWidgetItem(income.name)
        name_item.setData(Qt.ItemDataRole.UserRole, income.id)
        self.table.setItem(row, 0, name_item)

        # Type
        type_display = {
            'salary': 'Salary/Wages',
            'bonus': 'Bonus',
            'investment': 'Investment',
            'rental': 'Rental',
            'side_gig': 'Side Gig',
            'other': 'Other'
        }.get(income.income_type, income.income_type)
        self.table.setItem(row, 1, QTableWidgetItem(type_display))

        # Source
        self.table.setItem(row, 2, QTableWidgetItem(income.source or ''))

        # Amount
        amount_item = QTableWidgetItem(f"${income.amount:,.2f}")
        amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 3, amount_item)

        # Frequency
        freq_display = {
            'weekly': 'Weekly',
            'biweekly': 'Bi-weekly',
            'monthly': 'Monthly',
            'annual': 'Annual'
        }.get(income.frequency, income.frequency)
        self.table.setItem(row, 4, QTableWidgetItem(freq_display))

        # Monthly Amount
        monthly_item = QTableWidgetItem(f"${income.monthly_amount:,.2f}")
        monthly_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        monthly_item.setForeground(QBrush(QColor('#2e7d32')))  # Green for income
        self.table.setItem(row, 5, monthly_item)

        # Annual Amount
        annual_item = QTableWidgetItem(f"${income.annual_amount:,.2f}")
        annual_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        annual_item.setForeground(QBrush(QColor('#2e7d32')))  # Green for income
        self.table.setItem(row, 6, annual_item)

        # Status
        status_item = QTableWidgetItem('Active' if income.is_active else 'Inactive')
        if income.is_active:
            status_item.setForeground(QBrush(QColor('#2e7d32')))  # Green
        else:
            status_item.setForeground(QBrush(QColor('#757575')))  # Gray
        self.table.setItem(row, 7, status_item)

        # Start Date
        start_date = income.start_date or ''
        if income.start_date:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(income.start_date)
                start_date = dt.strftime('%Y-%m-%d')
            except Exception:
                pass
        self.table.setItem(row, 8, QTableWidgetItem(start_date))

    def get_selected_income_id(self) -> Optional[int]:
        """Get the ID of the currently selected income."""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            item = self.table.item(row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_selection_changed(self):
        """Handle selection change."""
        income_id = self.get_selected_income_id()
        if income_id is not None:
            self.income_selected.emit(income_id)

    def _on_double_click(self, item: QTableWidgetItem):
        """Handle double-click on a row."""
        row = item.row()
        name_item = self.table.item(row, 0)
        if name_item:
            income_id = name_item.data(Qt.ItemDataRole.UserRole)
            if income_id is not None:
                self.income_double_clicked.emit(income_id)

    def _show_context_menu(self, position):
        """Show right-click context menu."""
        income_id = self.get_selected_income_id()
        if income_id is None:
            return

        menu = QMenu(self)

        edit_action = QAction('Edit', self)
        edit_action.triggered.connect(lambda: self.edit_requested.emit(income_id))
        menu.addAction(edit_action)

        delete_action = QAction('Delete', self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(income_id))
        menu.addAction(delete_action)

        menu.exec(self.table.mapToGlobal(position))
