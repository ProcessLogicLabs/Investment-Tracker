"""Asset table widget for displaying portfolio assets."""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu,
    QAbstractItemView, QWidget, QVBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QAction
from ...database.models import Asset


class AssetTableWidget(QWidget):
    """Widget displaying a table of assets."""

    # Signals
    asset_selected = pyqtSignal(int)  # asset_id
    asset_double_clicked = pyqtSignal(int)  # asset_id
    edit_requested = pyqtSignal(int)  # asset_id
    delete_requested = pyqtSignal(int)  # asset_id

    COLUMNS = [
        ('Name', 150),
        ('Type', 80),
        ('Symbol', 80),
        ('Quantity', 80),
        ('Purchase Price', 100),
        ('Current Price', 100),
        ('Total Cost', 100),
        ('Current Value', 100),
        ('Gain/Loss', 100),
        ('Gain/Loss %', 80),
        ('Last Updated', 140),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._assets: List[Asset] = []
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

    def set_assets(self, assets: List[Asset]):
        """Populate the table with assets."""
        self._assets = assets
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(assets))

        for row, asset in enumerate(assets):
            self._set_row(row, asset)

        self.table.setSortingEnabled(True)

    def _set_row(self, row: int, asset: Asset):
        """Set the data for a single row."""
        # Store asset ID in first column
        name_item = QTableWidgetItem(asset.name)
        name_item.setData(Qt.ItemDataRole.UserRole, asset.id)
        self.table.setItem(row, 0, name_item)

        # Type
        type_display = {
            'metal': 'Metal',
            'stock': 'Stock',
            'realestate': 'Real Estate',
            'retirement': '401k/IRA',
            'cash': 'Cash',
            'other': 'Other'
        }.get(asset.asset_type, asset.asset_type)
        self.table.setItem(row, 1, QTableWidgetItem(type_display))

        # Symbol
        self.table.setItem(row, 2, QTableWidgetItem(asset.symbol or ''))

        # Quantity with unit (show total weight for metals, hide for balance-only)
        if asset.is_balance_only:
            qty_str = "—"  # Balance-only assets don't have quantity
        else:
            qty_str = f"{asset.quantity:,.4f}".rstrip('0').rstrip('.')
            if asset.asset_type == 'metal' and asset.weight_per_unit != 1.0:
                # Show count and total weight for fractional metals
                total_weight = asset.total_weight
                qty_str = f"{qty_str} pcs ({total_weight:,.4f}".rstrip('0').rstrip('.') + " oz)"
            elif asset.unit:
                qty_str = f"{qty_str} {asset.unit}"
        qty_item = QTableWidgetItem(qty_str)
        qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 3, qty_item)

        # Purchase Price (hide for balance-only)
        if asset.is_balance_only:
            pp_item = QTableWidgetItem("—")
        else:
            pp_item = QTableWidgetItem(f"${asset.purchase_price:,.2f}")
        pp_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 4, pp_item)

        # Current Price (shows balance for balance-only assets)
        if asset.is_balance_only:
            cp_item = QTableWidgetItem(f"${asset.current_price:,.2f}")
            cp_item.setToolTip("Current Balance")
        else:
            cp_item = QTableWidgetItem(f"${asset.current_price:,.2f}")
        cp_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 5, cp_item)

        # Total Cost (hide for balance-only)
        if asset.is_balance_only:
            tc_item = QTableWidgetItem("—")
        else:
            tc_item = QTableWidgetItem(f"${asset.total_cost:,.2f}")
        tc_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 6, tc_item)

        # Current Value
        cv_item = QTableWidgetItem(f"${asset.current_value:,.2f}")
        cv_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 7, cv_item)

        # Gain/Loss (N/A for balance-only, unless retirement with tracking)
        has_retirement_tracking = (asset.asset_type == 'retirement' and
                                   asset.baseline_price > 0 and asset.purchase_price > 0)
        if asset.is_balance_only and not has_retirement_tracking:
            gl_item = QTableWidgetItem("N/A")
            gl_item.setForeground(QBrush(QColor('#888888')))  # Gray
        else:
            gl = asset.gain_loss
            gl_item = QTableWidgetItem(f"${gl:+,.2f}")
            if gl > 0:
                gl_item.setForeground(QBrush(QColor('#2e7d32')))  # Green
            elif gl < 0:
                gl_item.setForeground(QBrush(QColor('#c62828')))  # Red
        gl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 8, gl_item)

        # Gain/Loss % (N/A for balance-only, unless retirement with tracking)
        if asset.is_balance_only and not has_retirement_tracking:
            glp_item = QTableWidgetItem("N/A")
            glp_item.setForeground(QBrush(QColor('#888888')))  # Gray
        else:
            glp = asset.gain_loss_percent
            glp_item = QTableWidgetItem(f"{glp:+.2f}%")
            if glp > 0:
                glp_item.setForeground(QBrush(QColor('#2e7d32')))  # Green
            elif glp < 0:
                glp_item.setForeground(QBrush(QColor('#c62828')))  # Red
        glp_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 9, glp_item)

        # Last Updated
        last_updated = asset.last_updated or 'Never'
        if asset.last_updated:
            # Format the datetime string
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(asset.last_updated)
                last_updated = dt.strftime('%Y-%m-%d %H:%M')
            except Exception:
                pass
        self.table.setItem(row, 10, QTableWidgetItem(last_updated))

    def update_asset_price(self, asset_id: int, new_price: float):
        """Update the price display for a specific asset."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == asset_id:
                # Find the asset and update
                for asset in self._assets:
                    if asset.id == asset_id:
                        asset.current_price = new_price
                        self._set_row(row, asset)
                        break
                break

    def get_selected_asset_id(self) -> Optional[int]:
        """Get the ID of the currently selected asset."""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            item = self.table.item(row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_selection_changed(self):
        """Handle selection change."""
        asset_id = self.get_selected_asset_id()
        if asset_id is not None:
            self.asset_selected.emit(asset_id)

    def _on_double_click(self, item: QTableWidgetItem):
        """Handle double-click on a row."""
        row = item.row()
        name_item = self.table.item(row, 0)
        if name_item:
            asset_id = name_item.data(Qt.ItemDataRole.UserRole)
            if asset_id is not None:
                self.asset_double_clicked.emit(asset_id)

    def _show_context_menu(self, position):
        """Show right-click context menu."""
        asset_id = self.get_selected_asset_id()
        if asset_id is None:
            return

        menu = QMenu(self)

        edit_action = QAction('Edit', self)
        edit_action.triggered.connect(lambda: self.edit_requested.emit(asset_id))
        menu.addAction(edit_action)

        delete_action = QAction('Delete', self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(asset_id))
        menu.addAction(delete_action)

        menu.exec(self.table.mapToGlobal(position))
