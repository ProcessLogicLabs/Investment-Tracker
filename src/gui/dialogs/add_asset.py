"""Add/Edit asset dialog."""

from datetime import date
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QDateEdit,
    QTextEdit, QPushButton, QLabel, QMessageBox, QGroupBox, QWidget
)
from PyQt6.QtCore import Qt, QDate
from ...database.models import Asset, BALANCE_ONLY_TYPES
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
        self.type_combo.addItem("Retirement (401k/IRA)", "retirement")
        self.type_combo.addItem("Cash/Savings", "cash")
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

        # Purchase info group (for non-balance-only assets)
        self.purchase_group = QGroupBox("Purchase Information")
        purchase_layout = QFormLayout(self.purchase_group)

        # Quantity with unit
        self.quantity_layout_widget = QWidget()
        quantity_layout = QHBoxLayout(self.quantity_layout_widget)
        quantity_layout.setContentsMargins(0, 0, 0, 0)
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

        self.quantity_label = QLabel("Quantity:")
        purchase_layout.addRow(self.quantity_label, self.quantity_layout_widget)

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
        self.purchase_price_spin.setRange(0, 999999999)
        self.purchase_price_spin.setDecimals(2)
        self.purchase_price_spin.setPrefix("$")
        self.purchase_price_label = QLabel("Purchase Price:")
        purchase_layout.addRow(self.purchase_price_label, self.purchase_price_spin)

        self.purchase_date_edit = QDateEdit()
        self.purchase_date_edit.setCalendarPopup(True)
        self.purchase_date_edit.setDate(QDate.currentDate())
        self.purchase_date_label = QLabel("Purchase Date:")
        purchase_layout.addRow(self.purchase_date_label, self.purchase_date_edit)

        # Current price / balance
        self.current_price_spin = QDoubleSpinBox()
        self.current_price_spin.setRange(0, 999999999)
        self.current_price_spin.setDecimals(2)
        self.current_price_spin.setPrefix("$")
        self.current_price_label = QLabel("Current Price:")
        purchase_layout.addRow(self.current_price_label, self.current_price_spin)

        # Monthly contribution (for retirement accounts)
        self.monthly_contribution_spin = QDoubleSpinBox()
        self.monthly_contribution_spin.setRange(0, 999999)
        self.monthly_contribution_spin.setDecimals(2)
        self.monthly_contribution_spin.setPrefix("$")
        self.monthly_contribution_spin.setToolTip("Monthly contribution amount for retirement accounts")
        self.monthly_contribution_label = QLabel("Monthly Contribution:")
        purchase_layout.addRow(self.monthly_contribution_label, self.monthly_contribution_spin)
        # Initially hide - will show for retirement accounts
        self.monthly_contribution_label.setVisible(False)
        self.monthly_contribution_spin.setVisible(False)

        layout.addWidget(self.purchase_group)

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
        is_balance_only = asset_type in BALANCE_ONLY_TYPES
        is_retirement = asset_type == 'retirement'

        # Show/hide weight fields for metals
        self.weight_per_unit_label.setVisible(is_metal)
        self.weight_per_unit_spin.setVisible(is_metal)
        self.total_weight_label.setVisible(is_metal)
        self.total_weight_value.setVisible(is_metal)

        # Show/hide fields for balance-only assets (but not retirement - it needs symbol for tracking)
        is_balance_only_no_symbol = is_balance_only and not is_retirement
        self.quantity_label.setVisible(not is_balance_only)
        self.quantity_layout_widget.setVisible(not is_balance_only)
        self.purchase_price_label.setVisible(not is_balance_only)
        self.purchase_price_spin.setVisible(not is_balance_only)
        self.purchase_date_label.setVisible(not is_balance_only)
        self.purchase_date_edit.setVisible(not is_balance_only)

        # Show/hide monthly contribution for retirement accounts
        self.monthly_contribution_label.setVisible(is_retirement)
        self.monthly_contribution_spin.setVisible(is_retirement)

        # Update current price label for balance-only assets
        if is_balance_only:
            self.current_price_label.setText("Current Balance:")
            self.purchase_group.setTitle("Balance Information")
            if is_retirement:
                # Retirement accounts can have a fund symbol for market tracking
                self.symbol_edit.setPlaceholderText("e.g., FXAIX, VFIAX (fund ticker for tracking)")
                self.lookup_btn.setVisible(True)
            else:
                self.symbol_edit.setPlaceholderText("e.g., Savings Account, Emergency Fund")
                self.lookup_btn.setVisible(False)
        else:
            self.current_price_label.setText("Current Price:")
            self.purchase_group.setTitle("Purchase Information")
            self.lookup_btn.setVisible(True)

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
        elif asset_type == 'retirement':
            # Already set above with fund ticker placeholder
            pass
        elif asset_type == 'cash':
            self.symbol_edit.setPlaceholderText("e.g., Emergency Fund, Savings Account")
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
        self.monthly_contribution_spin.setValue(self.asset.monthly_contribution)

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
            elif asset_type in ('stock', 'retirement'):
                # Both stocks and retirement funds use stock API
                api = StocksAPI()
                result = api.get_price(symbol)
            else:
                QMessageBox.information(
                    self, "Lookup",
                    "Automatic lookup is only available for metals, stocks, and retirement funds."
                )
                return

            if result.success:
                if asset_type == 'retirement':
                    # For retirement accounts, show the fund price but don't change the balance
                    QMessageBox.information(
                        self, "Fund Price Lookup",
                        f"Fund: {symbol}\n"
                        f"Current Share Price: ${result.price:,.2f}\n"
                        f"Source: {result.source}\n\n"
                        f"This price will be used as the baseline for tracking\n"
                        f"market performance of your retirement account."
                    )
                else:
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

        asset_type = self.type_combo.currentData()
        is_balance_only = asset_type in BALANCE_ONLY_TYPES

        # Validate balance for balance-only assets
        if is_balance_only and self.current_price_spin.value() <= 0:
            QMessageBox.warning(self, "Validation", "Please enter the current balance.")
            return

        # Create or update asset
        if self.is_edit:
            asset = self.asset
        else:
            asset = Asset()

        asset.name = name
        asset.asset_type = asset_type
        asset.symbol = self.symbol_edit.text().strip()

        # For balance-only assets, set quantity to 1 and use current_price as balance
        if is_balance_only:
            asset.quantity = 1
            asset.unit = "account"
            asset.weight_per_unit = 1.0
            asset.current_price = self.current_price_spin.value()
            # Monthly contribution for retirement accounts
            if asset_type == 'retirement':
                asset.monthly_contribution = self.monthly_contribution_spin.value()
                # For retirement accounts with a fund symbol, fetch current fund price as baseline
                symbol = self.symbol_edit.text().strip()
                if symbol:
                    try:
                        api = StocksAPI()
                        result = api.get_price(symbol)
                        if result.success:
                            asset.baseline_price = result.price
                            # Store the entered balance as purchase_price (base for tracking)
                            asset.purchase_price = self.current_price_spin.value()
                        else:
                            asset.baseline_price = 0.0
                            asset.purchase_price = 0.0
                    except Exception:
                        asset.baseline_price = 0.0
                        asset.purchase_price = 0.0
                else:
                    asset.baseline_price = 0.0
                    asset.purchase_price = 0.0
            else:
                asset.monthly_contribution = 0.0
                asset.purchase_price = 0  # No cost basis for non-retirement balance-only
                asset.baseline_price = 0.0
        else:
            asset.quantity = self.quantity_spin.value()
            asset.unit = self.unit_combo.currentText()
            asset.weight_per_unit = self.weight_per_unit_spin.value() if asset_type == 'metal' else 1.0
            asset.purchase_price = self.purchase_price_spin.value()
            asset.current_price = self.current_price_spin.value()
            asset.monthly_contribution = 0.0
            asset.baseline_price = 0.0  # Not used for regular assets

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
