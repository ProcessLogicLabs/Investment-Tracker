"""Sell asset dialog."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDoubleSpinBox,
    QDateEdit, QTextEdit, QPushButton, QHBoxLayout, QLabel,
    QGroupBox, QMessageBox
)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QFont

from ...database.models import Asset
from ...database.operations import AssetSaleOperations


class SellAssetDialog(QDialog):
    """Dialog for recording the sale of an asset (full or partial)."""

    def __init__(self, parent, asset: Asset):
        super().__init__(parent)
        self.asset = asset
        self.sale_result = None
        self.setWindowTitle(f"Sell: {asset.name}")
        self.setMinimumWidth(460)
        self._setup_ui()
        self._update_preview()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Asset info header
        info_group = QGroupBox("Asset Details")
        info_form = QFormLayout(info_group)

        info_form.addRow("Name:", QLabel(self.asset.name))
        info_form.addRow("Type:", QLabel(self.asset.asset_type.title()))

        if self.asset.is_balance_only:
            info_form.addRow("Current Balance:", QLabel(f"${self.asset.current_price:,.2f}"))
        else:
            unit = self.asset.unit or "units"
            info_form.addRow("Available Quantity:", QLabel(f"{self.asset.quantity:,.4f} {unit}"))
            info_form.addRow("Cost Basis / unit:", QLabel(f"${self.asset.purchase_price:,.2f}"))
            info_form.addRow("Current Price / unit:", QLabel(f"${self.asset.current_price:,.2f}"))

        info_form.addRow("Current Value:", QLabel(f"${self.asset.current_value:,.2f}"))

        layout.addWidget(info_group)

        # Sale form
        form_group = QGroupBox("Sale Details")
        form = QFormLayout(form_group)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Sale Date:", self.date_edit)

        if self.asset.is_balance_only:
            self.quantity_spin = QDoubleSpinBox()
            self.quantity_spin.setDecimals(2)
            self.quantity_spin.setRange(0.01, max(self.asset.current_price, 0.01))
            self.quantity_spin.setValue(self.asset.current_price)
            self.quantity_spin.setPrefix("$")
            self.quantity_spin.valueChanged.connect(self._update_preview)
            form.addRow("Amount to Withdraw:", self.quantity_spin)

            # For balance-only, sale_price_per_unit is always 1 (the amount itself is the proceeds)
            self.price_spin = None
        else:
            self.quantity_spin = QDoubleSpinBox()
            self.quantity_spin.setDecimals(4)
            self.quantity_spin.setRange(0.0001, max(self.asset.quantity, 0.0001))
            self.quantity_spin.setValue(self.asset.quantity)
            self.quantity_spin.setSuffix(f" {self.asset.unit or 'units'}")
            self.quantity_spin.valueChanged.connect(self._update_preview)
            form.addRow("Quantity to Sell:", self.quantity_spin)

            self.price_spin = QDoubleSpinBox()
            self.price_spin.setDecimals(2)
            self.price_spin.setRange(0, 100_000_000)
            self.price_spin.setPrefix("$")
            self.price_spin.setValue(self.asset.current_price)
            self.price_spin.valueChanged.connect(self._update_preview)
            form.addRow("Sale Price / unit:", self.price_spin)

        self.buyer_edit = QLineEdit()
        self.buyer_edit.setPlaceholderText("Name of the person or entity buying")
        form.addRow("Sold To:", self.buyer_edit)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        self.notes_edit.setPlaceholderText("Optional notes about the sale")
        form.addRow("Notes:", self.notes_edit)

        layout.addWidget(form_group)

        # Preview of proceeds and profit/loss
        self.preview_group = QGroupBox("Preview")
        preview_layout = QFormLayout(self.preview_group)

        self.proceeds_label = QLabel("$0.00")
        self.cost_basis_label = QLabel("$0.00")
        self.profit_loss_label = QLabel("$0.00")
        self.profit_loss_pct_label = QLabel("0.00%")
        self.remaining_label = QLabel("—")

        bold = QFont()
        bold.setBold(True)
        self.proceeds_label.setFont(bold)
        self.profit_loss_label.setFont(bold)

        preview_layout.addRow("Total Proceeds:", self.proceeds_label)
        preview_layout.addRow("Cost Basis Sold:", self.cost_basis_label)
        preview_layout.addRow("Profit / Loss:", self.profit_loss_label)
        preview_layout.addRow("Return:", self.profit_loss_pct_label)
        preview_layout.addRow("Remaining After Sale:", self.remaining_label)

        layout.addWidget(self.preview_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        self.sell_btn = QPushButton("Record Sale")
        self.sell_btn.setDefault(True)
        self.sell_btn.clicked.connect(self._accept)
        btn_row.addWidget(self.sell_btn)

        layout.addLayout(btn_row)

    def _compute_preview(self):
        """Compute proceeds, cost basis, profit/loss, remaining based on form values."""
        if self.asset.is_balance_only:
            amount = self.quantity_spin.value()
            total_proceeds = amount
            # For balance-only, cost basis is the amount withdrawn (no gain/loss tracking)
            cost_basis_sold = min(amount, self.asset.current_price)
            remaining_text = f"${max(0, self.asset.current_price - amount):,.2f} balance"
            return total_proceeds, cost_basis_sold, remaining_text

        qty = self.quantity_spin.value()
        price = self.price_spin.value() if self.price_spin else 0
        total_proceeds = qty * price
        cost_basis_sold = qty * self.asset.purchase_price
        remaining_qty = self.asset.quantity - qty
        if remaining_qty <= 0.0001:
            remaining_text = "Asset will be deleted"
        else:
            unit = self.asset.unit or "units"
            remaining_text = f"{remaining_qty:,.4f} {unit}"
        return total_proceeds, cost_basis_sold, remaining_text

    def _update_preview(self):
        proceeds, cost_basis, remaining_text = self._compute_preview()
        profit_loss = proceeds - cost_basis
        pct = (profit_loss / cost_basis * 100) if cost_basis > 0 else 0

        self.proceeds_label.setText(f"${proceeds:,.2f}")
        self.cost_basis_label.setText(f"${cost_basis:,.2f}")

        pl_color = "#2E7D32" if profit_loss >= 0 else "#C62828"
        self.profit_loss_label.setText(f"${profit_loss:+,.2f}")
        self.profit_loss_label.setStyleSheet(f"color: {pl_color};")
        self.profit_loss_pct_label.setText(f"{pct:+.2f}%")
        self.profit_loss_pct_label.setStyleSheet(f"color: {pl_color};")
        self.remaining_label.setText(remaining_text)

    def _accept(self):
        sale_date = self.date_edit.date().toString("yyyy-MM-dd")
        quantity = self.quantity_spin.value()
        price_per_unit = 1.0 if self.asset.is_balance_only else self.price_spin.value()
        buyer = self.buyer_edit.text().strip()
        notes = self.notes_edit.toPlainText().strip()

        if quantity <= 0:
            QMessageBox.warning(self, "Invalid Quantity", "Quantity must be greater than zero.")
            return

        # Confirm
        proceeds, _, _ = self._compute_preview()
        confirm = QMessageBox.question(
            self, "Confirm Sale",
            f"Record sale of {self.asset.name} for ${proceeds:,.2f}?\n\n"
            f"This will reduce the asset's quantity and create an income transaction.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self.sale_result = AssetSaleOperations.record_sale(
                asset_id=self.asset.id,
                sale_date=sale_date,
                quantity_sold=quantity,
                sale_price_per_unit=price_per_unit,
                buyer_name=buyer,
                notes=notes,
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Sale Failed", f"Could not record sale:\n{e}")
