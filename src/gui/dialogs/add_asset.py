"""Add/Edit asset dialog."""

from datetime import date
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QDateEdit,
    QTextEdit, QPushButton, QLabel, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt, QDate
from ...database.models import Asset
from ...database.operations import AssetOperations
from ...services.metals_api import MetalsAPI
from ...services.stocks_api import StocksAPI


class AddAssetDialog(QDialog):
    """Dialog for adding or editing an asset."""

    def __init__(self, parent=None, asset: Optional[Asset] = None):
        super().__init__(parent)
        self.asset = asset
        self.is_edit = asset is not None
        self._setup_ui()
        if self.is_edit:
            self._populate_fields()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Edit Asset" if self.is_edit else "Add Asset")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Basic info group
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout(basic_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Gold Eagle Coin, AAPL Stock")
        basic_layout.addRow("Name:", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Precious Metal", "metal")
        self.type_combo.addItem("Stock/Security", "stock")
        self.type_combo.addItem("Real Estate", "realestate")
        self.type_combo.addItem("Other", "other")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        basic_layout.addRow("Type:", self.type_combo)

        self.symbol_edit = QLineEdit()
        self.symbol_edit.setPlaceholderText("e.g., GOLD, AAPL, or property address")
        basic_layout.addRow("Symbol/ID:", self.symbol_edit)

        # Symbol lookup button
        self.lookup_btn = QPushButton("Lookup")
        self.lookup_btn.clicked.connect(self._lookup_symbol)
        symbol_layout = QHBoxLayout()
        symbol_layout.addWidget(self.symbol_edit)
        symbol_layout.addWidget(self.lookup_btn)
        basic_layout.addRow("Symbol/ID:", symbol_layout)
        # Remove the duplicate row
        basic_layout.removeRow(2)

        layout.addWidget(basic_group)

        # Purchase info group
        purchase_group = QGroupBox("Purchase Information")
        purchase_layout = QFormLayout(purchase_group)

        # Quantity with unit
        quantity_layout = QHBoxLayout()
        self.quantity_spin = QDoubleSpinBox()
        self.quantity_spin.setRange(0.0001, 999999999)
        self.quantity_spin.setDecimals(4)
        self.quantity_spin.setValue(1)
        quantity_layout.addWidget(self.quantity_spin)

        self.unit_combo = QComboBox()
        self.unit_combo.setEditable(True)
        self.unit_combo.addItem("pcs", "pcs")       # pieces (for metals)
        self.unit_combo.addItem("shares", "shares") # stocks
        self.unit_combo.addItem("units", "units")   # generic
        self.unit_combo.addItem("sqft", "sqft")     # real estate
        self.unit_combo.setMinimumWidth(80)
        quantity_layout.addWidget(self.unit_combo)

        purchase_layout.addRow("Quantity:", quantity_layout)

        # Weight per unit (for fractional metals like 1/10 oz coins)
        self.weight_per_unit_spin = QDoubleSpinBox()
        self.weight_per_unit_spin.setRange(0.0001, 1000)
        self.weight_per_unit_spin.setDecimals(4)
        self.weight_per_unit_spin.setValue(1.0)
        self.weight_per_unit_spin.setSuffix(" oz/unit")
        self.weight_per_unit_spin.setToolTip("Weight per coin/bar (e.g., 0.1 for 1/10 oz coins)")
        self.weight_per_unit_label = QLabel("Weight/Unit:")
        purchase_layout.addRow(self.weight_per_unit_label, self.weight_per_unit_spin)

        # Total weight display (calculated, read-only)
        self.total_weight_label = QLabel("Total Weight:")
        self.total_weight_value = QLabel("1.0 oz")
        self.total_weight_value.setStyleSheet("font-weight: bold;")
        purchase_layout.addRow(self.total_weight_label, self.total_weight_value)

        # Connect signals to update total weight
        self.quantity_spin.valueChanged.connect(self._update_total_weight)
        self.weight_per_unit_spin.valueChanged.connect(self._update_total_weight)

        self.purchase_price_spin = QDoubleSpinBox()
        self.purchase_price_spin.setRange(0.01, 999999999)
        self.purchase_price_spin.setDecimals(2)
        self.purchase_price_spin.setPrefix("$")
        purchase_layout.addRow("Purchase Price:", self.purchase_price_spin)

        self.purchase_date_edit = QDateEdit()
        self.purchase_date_edit.setCalendarPopup(True)
        self.purchase_date_edit.setDate(QDate.currentDate())
        purchase_layout.addRow("Purchase Date:", self.purchase_date_edit)

        # Current price (optional for new assets)
        self.current_price_spin = QDoubleSpinBox()
        self.current_price_spin.setRange(0, 999999999)
        self.current_price_spin.setDecimals(2)
        self.current_price_spin.setPrefix("$")
        purchase_layout.addRow("Current Price:", self.current_price_spin)

        layout.addWidget(purchase_group)

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
        """Handle asset type change."""
        asset_type = self.type_combo.currentData()
        is_metal = asset_type == 'metal'

        # Show/hide weight fields for metals
        self.weight_per_unit_label.setVisible(is_metal)
        self.weight_per_unit_spin.setVisible(is_metal)
        self.total_weight_label.setVisible(is_metal)
        self.total_weight_value.setVisible(is_metal)

        if is_metal:
            self.symbol_edit.setPlaceholderText("e.g., GOLD, SILVER, PLATINUM")
            self.unit_combo.setCurrentText("pcs")
            self._update_total_weight()
        elif asset_type == 'stock':
            self.symbol_edit.setPlaceholderText("e.g., AAPL, MSFT, SPY")
            self.unit_combo.setCurrentText("shares")
        elif asset_type == 'realestate':
            self.symbol_edit.setPlaceholderText("e.g., 123 Main St, Anytown USA")
            self.unit_combo.setCurrentText("sqft")
        else:
            self.symbol_edit.setPlaceholderText("Identifier or description")
            self.unit_combo.setCurrentText("units")

    def _update_total_weight(self):
        """Update the total weight display."""
        quantity = self.quantity_spin.value()
        weight_per_unit = self.weight_per_unit_spin.value()
        total = quantity * weight_per_unit
        self.total_weight_value.setText(f"{total:,.4f}".rstrip('0').rstrip('.') + " oz")

    def _populate_fields(self):
        """Populate fields with existing asset data."""
        if not self.asset:
            return

        self.name_edit.setText(self.asset.name)

        # Find and set the correct type index
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == self.asset.asset_type:
                self.type_combo.setCurrentIndex(i)
                break

        self.symbol_edit.setText(self.asset.symbol or "")
        self.quantity_spin.setValue(self.asset.quantity)
        if self.asset.unit:
            self.unit_combo.setCurrentText(self.asset.unit)
        self.weight_per_unit_spin.setValue(self.asset.weight_per_unit)
        self._update_total_weight()
        # Trigger type change to show/hide weight fields
        self._on_type_changed(self.type_combo.currentIndex())
        self.purchase_price_spin.setValue(self.asset.purchase_price)
        self.current_price_spin.setValue(self.asset.current_price)

        if self.asset.purchase_date:
            try:
                qdate = QDate.fromString(self.asset.purchase_date, Qt.DateFormat.ISODate)
                if qdate.isValid():
                    self.purchase_date_edit.setDate(qdate)
            except Exception:
                pass

        self.notes_edit.setPlainText(self.asset.notes or "")

    def _lookup_symbol(self):
        """Look up current price for the symbol."""
        symbol = self.symbol_edit.text().strip()
        if not symbol:
            QMessageBox.warning(self, "Lookup", "Please enter a symbol first.")
            return

        asset_type = self.type_combo.currentData()

        try:
            if asset_type == 'metal':
                api = MetalsAPI()
                result = api.get_price(symbol)
            elif asset_type == 'stock':
                api = StocksAPI()
                result = api.get_price(symbol)
            else:
                QMessageBox.information(
                    self, "Lookup",
                    "Automatic lookup is only available for metals and stocks."
                )
                return

            if result.success:
                self.current_price_spin.setValue(result.price)
                QMessageBox.information(
                    self, "Lookup",
                    f"Current price: ${result.price:,.2f}\nSource: {result.source}"
                )
            else:
                QMessageBox.warning(
                    self, "Lookup Failed",
                    f"Could not fetch price: {result.error}"
                )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Lookup failed: {str(e)}")

    def _save(self):
        """Save the asset."""
        # Validate
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Please enter a name.")
            return

        # Create or update asset
        if self.is_edit:
            asset = self.asset
        else:
            asset = Asset()

        asset.name = name
        asset.asset_type = self.type_combo.currentData()
        asset.symbol = self.symbol_edit.text().strip()
        asset.quantity = self.quantity_spin.value()
        asset.unit = self.unit_combo.currentText()
        asset.weight_per_unit = self.weight_per_unit_spin.value() if asset.asset_type == 'metal' else 1.0
        asset.purchase_price = self.purchase_price_spin.value()
        asset.current_price = self.current_price_spin.value()
        asset.purchase_date = self.purchase_date_edit.date().toString(Qt.DateFormat.ISODate)
        asset.notes = self.notes_edit.toPlainText().strip()

        try:
            if self.is_edit:
                AssetOperations.update(asset)
            else:
                AssetOperations.create(asset)

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")

    def get_asset(self) -> Optional[Asset]:
        """Get the created/edited asset."""
        return self.asset
