"""Transaction table widget for displaying imported bank/card transactions."""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu,
    QAbstractItemView, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QLineEdit, QDateEdit, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QColor, QBrush, QAction
from ...database.models import Transaction
from ..theme import theme


class TransactionTableWidget(QWidget):
    """Widget displaying a table of transactions with filters."""

    # Signals
    transaction_selected = pyqtSignal(int)
    transaction_double_clicked = pyqtSignal(int)
    edit_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    COLUMNS = [
        ('Date', 100),
        ('Description', 220),
        ('Category', 110),
        ('Amount', 110),
        ('Account', 130),
        ('Type', 100),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._transactions: List[Transaction] = []
        self._filtered: List[Transaction] = []
        self._setup_ui()

    def _setup_ui(self):
        """Set up the table widget with filter bar."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 5)

        filter_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.dateChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.dateChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.date_to)

        filter_layout.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("All", "")
        self.category_combo.setMinimumWidth(120)
        self.category_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.category_combo)

        filter_layout.addWidget(QLabel("Account:"))
        self.account_combo = QComboBox()
        self.account_combo.addItem("All", "")
        self.account_combo.setMinimumWidth(120)
        self.account_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.account_combo)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.setMaximumWidth(200)
        self.search_box.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_box)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_filters)
        filter_layout.addWidget(clear_btn)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([col[0] for col in self.COLUMNS])

        for i, (_, width) in enumerate(self.COLUMNS):
            self.table.setColumnWidth(i, width)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)

        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

        # Summary bar
        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

    def set_transactions(self, transactions: List[Transaction]):
        """Populate the table with transactions."""
        self._transactions = transactions
        self._update_filter_combos()
        self._apply_filters()

    def _update_filter_combos(self):
        """Update category and account combo boxes from data."""
        # Save current selections
        current_cat = self.category_combo.currentData()
        current_acc = self.account_combo.currentData()

        self.category_combo.blockSignals(True)
        self.account_combo.blockSignals(True)

        self.category_combo.clear()
        self.category_combo.addItem("All", "")
        categories = sorted(set(t.category for t in self._transactions if t.category))
        for cat in categories:
            self.category_combo.addItem(cat.title(), cat)

        self.account_combo.clear()
        self.account_combo.addItem("All", "")
        accounts = sorted(set(t.account_name for t in self._transactions if t.account_name))
        for acc in accounts:
            self.account_combo.addItem(acc, acc)

        # Restore selections
        idx = self.category_combo.findData(current_cat)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        idx = self.account_combo.findData(current_acc)
        if idx >= 0:
            self.account_combo.setCurrentIndex(idx)

        self.category_combo.blockSignals(False)
        self.account_combo.blockSignals(False)

    def _apply_filters(self):
        """Filter and display transactions."""
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        category = self.category_combo.currentData() or ""
        account = self.account_combo.currentData() or ""
        search = self.search_box.text().lower().strip()

        filtered = []
        for t in self._transactions:
            if t.transaction_date and (t.transaction_date < date_from or t.transaction_date > date_to):
                continue
            if category and t.category != category:
                continue
            if account and t.account_name != account:
                continue
            if search and search not in t.description.lower():
                continue
            filtered.append(t)

        self._filtered = filtered
        self._populate_table(filtered)

    def _populate_table(self, transactions: List[Transaction]):
        """Fill the table with filtered transactions."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(transactions))

        for row, txn in enumerate(transactions):
            self._set_row(row, txn)

        self.table.setSortingEnabled(True)
        self._update_summary(transactions)

    def _set_row(self, row: int, txn: Transaction):
        """Set the data for a single row."""
        p = theme().palette

        # Date
        date_item = QTableWidgetItem(txn.transaction_date or '')
        date_item.setData(Qt.ItemDataRole.UserRole, txn.id)
        self.table.setItem(row, 0, date_item)

        # Description
        self.table.setItem(row, 1, QTableWidgetItem(txn.description))

        # Category
        cat_item = QTableWidgetItem(txn.category.title() if txn.category else '')
        self.table.setItem(row, 2, cat_item)

        # Amount
        amt_item = QTableWidgetItem(f"${txn.amount:,.2f}")
        amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        color = p.positive if txn.amount >= 0 else p.negative
        amt_item.setForeground(QBrush(QColor(color)))
        self.table.setItem(row, 3, amt_item)

        # Account
        self.table.setItem(row, 4, QTableWidgetItem(txn.account_name))

        # Type
        type_display = txn.transaction_type.replace('_', ' ').title() if txn.transaction_type else ''
        self.table.setItem(row, 5, QTableWidgetItem(type_display))

    def _update_summary(self, transactions: List[Transaction]):
        """Update the summary bar."""
        if not transactions:
            self.summary_label.setText("No transactions")
            return

        total_in = sum(t.amount for t in transactions if t.amount > 0)
        total_out = sum(t.amount for t in transactions if t.amount < 0)
        net = total_in + total_out
        self.summary_label.setText(
            f"{len(transactions)} transactions  |  "
            f"Income: ${total_in:,.2f}  |  "
            f"Spending: ${total_out:,.2f}  |  "
            f"Net: ${net:,.2f}"
        )

    def _clear_filters(self):
        """Reset all filters."""
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_to.setDate(QDate.currentDate())
        self.category_combo.setCurrentIndex(0)
        self.account_combo.setCurrentIndex(0)
        self.search_box.clear()

    def get_selected_transaction_id(self) -> Optional[int]:
        """Get the ID of the currently selected transaction."""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            item = self.table.item(row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_selection_changed(self):
        """Handle selection change."""
        txn_id = self.get_selected_transaction_id()
        if txn_id is not None:
            self.transaction_selected.emit(txn_id)

    def _on_double_click(self, item: QTableWidgetItem):
        """Handle double-click on a row."""
        row = item.row()
        date_item = self.table.item(row, 0)
        if date_item:
            txn_id = date_item.data(Qt.ItemDataRole.UserRole)
            if txn_id is not None:
                self.transaction_double_clicked.emit(txn_id)

    def _show_context_menu(self, position):
        """Show right-click context menu."""
        txn_id = self.get_selected_transaction_id()
        if txn_id is None:
            return

        menu = QMenu(self)

        edit_action = QAction('Edit', self)
        edit_action.triggered.connect(lambda: self.edit_requested.emit(txn_id))
        menu.addAction(edit_action)

        delete_action = QAction('Delete', self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(txn_id))
        menu.addAction(delete_action)

        menu.exec(self.table.mapToGlobal(position))
