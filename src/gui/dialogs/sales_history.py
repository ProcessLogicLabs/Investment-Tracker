"""Sales history dialog showing all recorded asset sales."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont

from ...database.operations import AssetSaleOperations
from ..theme import theme


class SalesHistoryDialog(QDialog):
    """Dialog showing the full history of asset sales."""

    COLUMNS = [
        ('Date', 100),
        ('Asset', 180),
        ('Type', 90),
        ('Quantity', 90),
        ('Price / unit', 100),
        ('Proceeds', 110),
        ('Cost Basis', 110),
        ('Profit / Loss', 120),
        ('Return %', 80),
        ('Sold To', 160),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sales History")
        self.setMinimumSize(1100, 520)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Summary section
        self.summary_group = QGroupBox("Summary")
        summary_layout = QGridLayout(self.summary_group)

        self.count_label = QLabel("0")
        self.proceeds_label = QLabel("$0.00")
        self.cost_basis_label = QLabel("$0.00")
        self.profit_label = QLabel("$0.00")

        bold = QFont()
        bold.setBold(True)
        for lbl in (self.count_label, self.proceeds_label,
                    self.cost_basis_label, self.profit_label):
            lbl.setFont(bold)

        summary_layout.addWidget(QLabel("Total Sales:"), 0, 0)
        summary_layout.addWidget(self.count_label, 0, 1)
        summary_layout.addWidget(QLabel("Total Proceeds:"), 0, 2)
        summary_layout.addWidget(self.proceeds_label, 0, 3)
        summary_layout.addWidget(QLabel("Total Cost Basis:"), 1, 0)
        summary_layout.addWidget(self.cost_basis_label, 1, 1)
        summary_layout.addWidget(QLabel("Total Profit/Loss:"), 1, 2)
        summary_layout.addWidget(self.profit_label, 1, 3)

        layout.addWidget(self.summary_group)

        # Sales table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in self.COLUMNS])
        for i, (_, width) in enumerate(self.COLUMNS):
            self.table.setColumnWidth(i, width)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # Buttons
        btn_row = QHBoxLayout()

        self.delete_btn = QPushButton("Delete Sale Record")
        self.delete_btn.setToolTip("Remove this sale from history. Does not restore the asset.")
        self.delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _load_data(self):
        sales = AssetSaleOperations.get_all()
        summary = AssetSaleOperations.get_summary()

        p = theme().palette

        # Update summary
        self.count_label.setText(str(summary['count']))
        self.proceeds_label.setText(f"${summary['total_proceeds']:,.2f}")
        self.cost_basis_label.setText(f"${summary['total_cost_basis']:,.2f}")
        profit = summary['total_profit']
        self.profit_label.setText(f"${profit:+,.2f}")
        self.profit_label.setStyleSheet(
            f"color: {p.positive if profit >= 0 else p.negative};"
        )

        # Populate table
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(sales))

        for row, sale in enumerate(sales):
            # Date
            date_item = QTableWidgetItem(sale.sale_date or '')
            date_item.setData(Qt.ItemDataRole.UserRole, sale.id)
            self.table.setItem(row, 0, date_item)

            # Asset name
            self.table.setItem(row, 1, QTableWidgetItem(sale.asset_name))

            # Type
            type_display = {
                'metal': 'Metal', 'stock': 'Stock', 'realestate': 'Real Estate',
                'retirement': '401k/IRA', 'cash': 'Cash', 'other': 'Other',
            }.get(sale.asset_type, sale.asset_type)
            self.table.setItem(row, 2, QTableWidgetItem(type_display))

            # Quantity
            qty_item = QTableWidgetItem(f"{sale.quantity_sold:,.4f}".rstrip('0').rstrip('.'))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, qty_item)

            # Price per unit
            price_item = QTableWidgetItem(f"${sale.sale_price_per_unit:,.2f}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 4, price_item)

            # Proceeds
            proceeds_item = QTableWidgetItem(f"${sale.total_proceeds:,.2f}")
            proceeds_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 5, proceeds_item)

            # Cost basis
            cb_item = QTableWidgetItem(f"${sale.cost_basis_sold:,.2f}")
            cb_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 6, cb_item)

            # Profit/Loss
            pl = sale.profit_loss
            pl_item = QTableWidgetItem(f"${pl:+,.2f}")
            pl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            pl_item.setForeground(QBrush(QColor(p.positive if pl >= 0 else p.negative)))
            self.table.setItem(row, 7, pl_item)

            # Return %
            pct = sale.profit_loss_percent
            pct_item = QTableWidgetItem(f"{pct:+.2f}%")
            pct_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            pct_item.setForeground(QBrush(QColor(p.positive if pl >= 0 else p.negative)))
            self.table.setItem(row, 8, pct_item)

            # Sold to
            self.table.setItem(row, 9, QTableWidgetItem(sale.buyer_name or ''))

        self.table.setSortingEnabled(True)

    def _delete_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "Delete Sale", "Please select a sale record to delete.")
            return
        sale_id = self.table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if sale_id is None:
            return

        reply = QMessageBox.question(
            self, "Delete Sale Record",
            "Remove this sale from history?\n\n"
            "Note: This does NOT restore the asset or remove the income transaction.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            AssetSaleOperations.delete(sale_id)
            self._load_data()
