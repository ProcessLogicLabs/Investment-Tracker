"""Debt payoff simulation wizard with tax-optimized metals liquidation."""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox,
    QComboBox, QLineEdit, QTextEdit, QGroupBox, QFormLayout,
    QCheckBox, QAbstractItemView, QPushButton, QFileDialog, QMessageBox,
    QSlider, QFrame, QSplitter, QSizePolicy, QScrollArea, QWidget,
    QGridLayout, QTabWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QScatterSeries, QAreaSeries
from ...database.operations import AssetOperations, LiabilityOperations, IncomeOperations, SettingsOperations
import json


# 2024 Long-term capital gains thresholds
LTCG_THRESHOLDS = {
    'single': 47025,
    'married_joint': 94050,
    'head_household': 63000
}

LTCG_RATE_15_THRESHOLD = {
    'single': 518900,
    'married_joint': 583750,
    'head_household': 551350
}

# 2024 401k contribution limits
MAX_401K_CONTRIBUTION = 23000  # Standard limit
MAX_401K_CATCHUP = 7500  # Additional for age 50+

# Historical average returns for 401k growth projections (annualized)
# Based on S&P 500 historical data
HISTORICAL_RETURNS = {
    'conservative': 0.05,    # 5% - bonds/stable value heavy
    'moderate': 0.07,        # 7% - balanced portfolio
    'aggressive': 0.10,      # 10% - stock heavy (S&P 500 avg ~10% since 1926)
}
DEFAULT_RETURN_SCENARIO = 'moderate'

# Settings keys for saving/loading simulation preferences
SIMULATION_SETTINGS_KEY = 'debt_payoff_simulation'


def calculate_401k_future_value(monthly_contribution: float, years: int,
                                 annual_return: float, existing_balance: float = 0) -> float:
    """Calculate future value of 401k contributions with compound growth.

    Uses future value of annuity formula for monthly contributions plus
    compound growth on existing balance.

    Args:
        monthly_contribution: Monthly contribution amount
        years: Number of years to project
        annual_return: Expected annual return (decimal, e.g., 0.07 for 7%)
        existing_balance: Current 401k balance to grow

    Returns:
        Projected future value
    """
    if years <= 0:
        return existing_balance

    monthly_rate = annual_return / 12
    months = years * 12

    # Future value of existing balance
    fv_existing = existing_balance * ((1 + monthly_rate) ** months)

    # Future value of monthly contributions (annuity)
    if monthly_rate > 0:
        fv_contributions = monthly_contribution * (((1 + monthly_rate) ** months - 1) / monthly_rate)
    else:
        fv_contributions = monthly_contribution * months

    return fv_existing + fv_contributions


@dataclass
class AssetSelection:
    """Represents a selected asset and quantity to sell."""
    asset: Any
    quantity_to_sell: float

    @property
    def value_to_sell(self) -> float:
        """Calculate value of the portion being sold."""
        if self.asset.asset_type == 'metal':
            # For metals: price is per oz, need to account for weight_per_unit
            price_per_unit = self.asset.current_price * self.asset.weight_per_unit
            return self.quantity_to_sell * price_per_unit
        return self.quantity_to_sell * self.asset.current_price

    @property
    def cost_basis_portion(self) -> float:
        """Calculate cost basis for the portion being sold."""
        if self.asset.quantity == 0:
            return 0
        return (self.quantity_to_sell / self.asset.quantity) * self.asset.total_cost

    @property
    def gain_loss(self) -> float:
        """Calculate gain/loss for the portion being sold."""
        return self.value_to_sell - self.cost_basis_portion


@dataclass
class SimulationResult:
    """Results from a debt payoff simulation."""
    strategy_name: str
    timeline: List[Dict[str, Any]]  # Month-by-month events
    total_proceeds: float
    total_gain: float
    total_tax: float
    net_proceeds: float
    total_interest_saved: float
    months_to_debt_free: int
    debts_eliminated: List[str]
    remaining_debt: float
    years_to_complete: int


class DebtPayoffSimulator:
    """Simulates debt payoff strategies with tax optimization."""

    def __init__(self, selected_assets: List[AssetSelection], liabilities: List,
                 annual_income: float, filing_status: str, efund_allocation: float = 0):
        self.selected_assets = selected_assets
        self.liabilities = sorted(
            [l for l in liabilities if l.current_balance > 0],
            key=lambda x: x.interest_rate, reverse=True
        )
        self.annual_income = annual_income
        self.filing_status = filing_status
        self.ltcg_threshold = LTCG_THRESHOLDS.get(filing_status, 47025)
        self.efund_allocation = efund_allocation

    def calculate_gain_headroom(self) -> float:
        """Calculate how much gain can be realized at 0% tax rate."""
        return max(0, self.ltcg_threshold - self.annual_income)

    def calculate_tax(self, gain: float) -> float:
        """Calculate capital gains tax on a given gain amount."""
        if gain <= 0:
            return 0

        headroom = self.calculate_gain_headroom()

        if gain <= headroom:
            return 0  # All taxed at 0%

        # Amount over threshold taxed at 15%
        taxable_at_15 = gain - headroom
        return taxable_at_15 * 0.15

    def _simulate_baseline_payoff(self) -> Tuple[int, float]:
        """Simulate debt payoff without selling any assets."""
        if not self.liabilities:
            return (0, 0)

        balances = {l.id: l.current_balance for l in self.liabilities}
        payments = {l.id: l.monthly_payment for l in self.liabilities}
        rates = {l.id: l.monthly_interest_rate for l in self.liabilities}

        total_interest = 0
        month = 0

        while any(b > 0.01 for b in balances.values()) and month < 600:
            month += 1

            # Apply interest
            for l in self.liabilities:
                if balances[l.id] > 0:
                    interest = balances[l.id] * rates[l.id]
                    total_interest += interest
                    balances[l.id] += interest

            # Apply payments
            for l in self.liabilities:
                if balances[l.id] > 0:
                    pmt = min(payments[l.id], balances[l.id])
                    balances[l.id] -= pmt

        return (month, total_interest)

    def simulate_immediate_sale(self) -> SimulationResult:
        """Simulate selling all selected assets immediately."""
        if not self.selected_assets:
            return self._empty_result("Immediate Sale")

        # Calculate totals
        total_value = sum(a.value_to_sell for a in self.selected_assets)
        total_basis = sum(a.cost_basis_portion for a in self.selected_assets)
        total_gain = sum(a.gain_loss for a in self.selected_assets)
        total_tax = self.calculate_tax(total_gain)
        net_proceeds = total_value - total_tax

        # Simulate debt payoff
        timeline = []
        balances = {l.id: l.current_balance for l in self.liabilities}
        payments = {l.id: l.monthly_payment for l in self.liabilities}
        rates = {l.id: l.monthly_interest_rate for l in self.liabilities}
        names = {l.id: l.name for l in self.liabilities}

        debts_eliminated = []
        interest_saved = 0

        # Subtract emergency fund allocation from proceeds available for debt
        proceeds_for_debt = net_proceeds - self.efund_allocation

        # Month 1: Apply proceeds to debts
        remaining = proceeds_for_debt
        month1_events = {
            'month': 1,
            'year': 1,
            'assets_sold': [f"{a.asset.name} ({a.quantity_to_sell:.2f} units)" for a in self.selected_assets],
            'proceeds': net_proceeds,
            'efund_allocation': self.efund_allocation,
            'proceeds_for_debt': proceeds_for_debt,
            'tax_paid': total_tax,
            'debts_paid': [],
            'interest_saved_this_month': 0
        }

        for l in self.liabilities:
            if remaining <= 0:
                break
            if balances[l.id] > 0:
                pay_amount = min(remaining, balances[l.id])
                # Calculate interest that would have been paid on this portion
                months_remaining = l.months_to_payoff
                if months_remaining > 0:
                    # Rough estimate of interest saved
                    avg_balance = pay_amount / 2
                    interest_saved += avg_balance * rates[l.id] * months_remaining

                balances[l.id] -= pay_amount
                remaining -= pay_amount

                if balances[l.id] <= 0.01:
                    debts_eliminated.append(names[l.id])
                    month1_events['debts_paid'].append(f"{names[l.id]} - PAID OFF")
                else:
                    month1_events['debts_paid'].append(f"{names[l.id]} - Paid ${pay_amount:,.2f}")

        timeline.append(month1_events)

        # Continue simulation for remaining debt
        month = 1
        while any(b > 0.01 for b in balances.values()) and month < 600:
            month += 1

            # Apply interest
            for l in self.liabilities:
                if balances[l.id] > 0:
                    interest = balances[l.id] * rates[l.id]
                    balances[l.id] += interest

            # Apply payments
            extra = 0
            for l in self.liabilities:
                if balances[l.id] > 0:
                    pmt = min(payments[l.id] + extra, balances[l.id])
                    balances[l.id] -= pmt
                    extra = 0

                    if balances[l.id] <= 0.01 and names[l.id] not in debts_eliminated:
                        debts_eliminated.append(names[l.id])
                        extra = payments[l.id]  # Freed up payment for next debt

        remaining_debt = sum(b for b in balances.values() if b > 0.01)

        # Calculate interest saved compared to baseline
        baseline_months, baseline_interest = self._simulate_baseline_payoff()
        # Recalculate actual interest paid in this scenario
        actual_interest = baseline_interest - interest_saved

        return SimulationResult(
            strategy_name="Immediate Sale",
            timeline=timeline,
            total_proceeds=total_value,
            total_gain=total_gain,
            total_tax=total_tax,
            net_proceeds=net_proceeds,
            total_interest_saved=interest_saved,
            months_to_debt_free=month,
            debts_eliminated=debts_eliminated,
            remaining_debt=remaining_debt,
            years_to_complete=1
        )

    def simulate_tax_optimized_sale(self) -> SimulationResult:
        """Simulate spreading sales across tax years to minimize tax."""
        if not self.selected_assets:
            return self._empty_result("Tax-Optimized Sale")

        headroom = self.calculate_gain_headroom()
        total_gain = sum(a.gain_loss for a in self.selected_assets)

        # If all gains fit in headroom, same as immediate sale
        if total_gain <= headroom:
            result = self.simulate_immediate_sale()
            result.strategy_name = "Tax-Optimized Sale"
            return result

        # Need to spread across years
        timeline = []
        remaining_assets = list(self.selected_assets)

        balances = {l.id: l.current_balance for l in self.liabilities}
        payments = {l.id: l.monthly_payment for l in self.liabilities}
        rates = {l.id: l.monthly_interest_rate for l in self.liabilities}
        names = {l.id: l.name for l in self.liabilities}

        debts_eliminated = []
        total_tax = 0
        total_proceeds = 0
        total_interest_saved = 0
        year = 0
        month = 0

        while remaining_assets and year < 10:  # Cap at 10 years
            year += 1
            year_gain = 0
            year_proceeds = 0
            assets_sold_this_year = []

            # Sell assets up to gain headroom
            assets_to_remove = []
            for i, selection in enumerate(remaining_assets):
                if year_gain >= headroom:
                    break

                asset_gain = selection.gain_loss

                if year_gain + asset_gain <= headroom:
                    # Can sell entire selection
                    year_gain += asset_gain
                    year_proceeds += selection.value_to_sell
                    assets_sold_this_year.append(f"{selection.asset.name} ({selection.quantity_to_sell:.2f} units)")
                    assets_to_remove.append(i)
                else:
                    # Partial sale - calculate how much we can sell
                    gain_room = headroom - year_gain
                    if asset_gain > 0:
                        fraction = gain_room / asset_gain
                        partial_qty = selection.quantity_to_sell * fraction
                        partial_value = selection.value_to_sell * fraction

                        year_gain += gain_room
                        year_proceeds += partial_value
                        assets_sold_this_year.append(f"{selection.asset.name} ({partial_qty:.2f} units - partial)")

                        # Update remaining
                        selection.quantity_to_sell -= partial_qty
                    break

            # Remove fully sold assets
            for i in reversed(assets_to_remove):
                remaining_assets.pop(i)

            # Calculate tax for this year
            year_tax = self.calculate_tax(year_gain)
            total_tax += year_tax
            net_year_proceeds = year_proceeds - year_tax
            total_proceeds += year_proceeds

            # Emergency fund is allocated in year 1 only
            year_efund_allocation = self.efund_allocation if year == 1 else 0
            proceeds_for_debt = net_year_proceeds - year_efund_allocation

            # Apply proceeds to debts (at start of year)
            month = (year - 1) * 12 + 1
            year_event = {
                'month': month,
                'year': year,
                'assets_sold': assets_sold_this_year,
                'proceeds': net_year_proceeds,
                'efund_allocation': year_efund_allocation,
                'proceeds_for_debt': proceeds_for_debt,
                'gain_realized': year_gain,
                'tax_paid': year_tax,
                'debts_paid': [],
                'interest_saved_this_month': 0
            }

            remaining = proceeds_for_debt
            for l in self.liabilities:
                if remaining <= 0:
                    break
                if balances[l.id] > 0:
                    pay_amount = min(remaining, balances[l.id])

                    # Estimate interest saved
                    if l.months_to_payoff > 0:
                        avg_balance = pay_amount / 2
                        total_interest_saved += avg_balance * rates[l.id] * l.months_to_payoff

                    balances[l.id] -= pay_amount
                    remaining -= pay_amount

                    if balances[l.id] <= 0.01:
                        if names[l.id] not in debts_eliminated:
                            debts_eliminated.append(names[l.id])
                        year_event['debts_paid'].append(f"{names[l.id]} - PAID OFF")
                    else:
                        year_event['debts_paid'].append(f"{names[l.id]} - Paid ${pay_amount:,.2f}")

            timeline.append(year_event)

            # Simulate rest of year with regular payments
            for m in range(2, 13):
                month = (year - 1) * 12 + m

                # Apply interest
                for l in self.liabilities:
                    if balances[l.id] > 0:
                        interest = balances[l.id] * rates[l.id]
                        balances[l.id] += interest

                # Apply payments (avalanche)
                extra = 0
                for l in self.liabilities:
                    if balances[l.id] > 0:
                        pmt = min(payments[l.id] + extra, balances[l.id])
                        balances[l.id] -= pmt
                        extra = 0

                        if balances[l.id] <= 0.01 and names[l.id] not in debts_eliminated:
                            debts_eliminated.append(names[l.id])
                            extra = payments[l.id]

        # Continue until debt-free
        while any(b > 0.01 for b in balances.values()) and month < 600:
            month += 1

            for l in self.liabilities:
                if balances[l.id] > 0:
                    interest = balances[l.id] * rates[l.id]
                    balances[l.id] += interest

            extra = 0
            for l in self.liabilities:
                if balances[l.id] > 0:
                    pmt = min(payments[l.id] + extra, balances[l.id])
                    balances[l.id] -= pmt
                    extra = 0

                    if balances[l.id] <= 0.01 and names[l.id] not in debts_eliminated:
                        debts_eliminated.append(names[l.id])
                        extra = payments[l.id]

        remaining_debt = sum(b for b in balances.values() if b > 0.01)

        return SimulationResult(
            strategy_name="Tax-Optimized Sale",
            timeline=timeline,
            total_proceeds=total_proceeds,
            total_gain=sum(a.gain_loss for a in self.selected_assets),
            total_tax=total_tax,
            net_proceeds=total_proceeds - total_tax,
            total_interest_saved=total_interest_saved,
            months_to_debt_free=month,
            debts_eliminated=debts_eliminated,
            remaining_debt=remaining_debt,
            years_to_complete=year
        )

    def _empty_result(self, name: str) -> SimulationResult:
        """Return empty result when no assets selected."""
        return SimulationResult(
            strategy_name=name,
            timeline=[],
            total_proceeds=0,
            total_gain=0,
            total_tax=0,
            net_proceeds=0,
            total_interest_saved=0,
            months_to_debt_free=0,
            debts_eliminated=[],
            remaining_debt=sum(l.current_balance for l in self.liabilities),
            years_to_complete=0
        )


class AssetSelectionPage(QWizardPage):
    """Wizard page for selecting metals assets to sell."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Select Assets to Liquidate")
        self.setSubTitle("Choose which metals assets to sell and the quantity of each.")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Select All toggle
        select_all_layout = QHBoxLayout()
        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.setStyleSheet("font-weight: bold;")
        self.select_all_checkbox.stateChanged.connect(self._toggle_select_all)
        select_all_layout.addWidget(self.select_all_checkbox)
        select_all_layout.addStretch()
        layout.addLayout(select_all_layout)

        # Asset table
        self.asset_table = QTableWidget()
        self.asset_table.setColumnCount(8)
        self.asset_table.setHorizontalHeaderLabels([
            "Sell", "Asset Name", "Available", "Sell Qty",
            "Cost Basis", "Current Value", "Gain/Loss", "Gain %"
        ])
        self.asset_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.asset_table.setAlternatingRowColors(True)

        header = self.asset_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.asset_table)

        # Totals section
        totals_group = QGroupBox("Selection Summary")
        totals_layout = QHBoxLayout(totals_group)

        self.total_value_label = QLabel("Total Value: $0.00")
        self.total_basis_label = QLabel("Total Basis: $0.00")
        self.total_gain_label = QLabel("Total Gain: $0.00")

        for label in [self.total_value_label, self.total_basis_label, self.total_gain_label]:
            label.setStyleSheet("font-weight: bold; font-size: 12px;")
            totals_layout.addWidget(label)

        layout.addWidget(totals_group)

        # Load assets
        self._load_assets()

    def _load_assets(self):
        """Load metals assets into the table."""
        assets = AssetOperations.get_all()
        metals = [a for a in assets if a.asset_type == 'metal' and a.quantity > 0]

        self.asset_table.setRowCount(len(metals))
        self.spinboxes = {}
        self.checkboxes = {}

        for row, asset in enumerate(metals):
            # Checkbox
            checkbox = QCheckBox()
            checkbox.stateChanged.connect(self._update_totals)
            self.checkboxes[row] = checkbox
            self.asset_table.setCellWidget(row, 0, checkbox)

            # Asset name
            name_item = QTableWidgetItem(asset.name)
            name_item.setData(Qt.ItemDataRole.UserRole, asset)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.asset_table.setItem(row, 1, name_item)

            # Available quantity
            qty_item = QTableWidgetItem(f"{asset.quantity:.2f}")
            qty_item.setFlags(qty_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.asset_table.setItem(row, 2, qty_item)

            # Spinbox for quantity to sell
            spinbox = QDoubleSpinBox()
            spinbox.setRange(0, asset.quantity)
            spinbox.setDecimals(2)
            spinbox.setSingleStep(1)
            spinbox.setValue(asset.quantity)  # Default to all
            spinbox.valueChanged.connect(self._update_totals)
            self.spinboxes[row] = spinbox
            self.asset_table.setCellWidget(row, 3, spinbox)

            # Cost basis
            basis_item = QTableWidgetItem(f"${asset.total_cost:,.2f}")
            basis_item.setFlags(basis_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.asset_table.setItem(row, 4, basis_item)

            # Current value
            value_item = QTableWidgetItem(f"${asset.current_value:,.2f}")
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.asset_table.setItem(row, 5, value_item)

            # Gain/Loss
            gain = asset.gain_loss
            gain_item = QTableWidgetItem(f"${gain:,.2f}")
            gain_item.setForeground(QColor("green") if gain >= 0 else QColor("red"))
            gain_item.setFlags(gain_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.asset_table.setItem(row, 6, gain_item)

            # Gain %
            pct = asset.gain_loss_percent
            pct_item = QTableWidgetItem(f"{pct:.1f}%")
            pct_item.setForeground(QColor("green") if pct >= 0 else QColor("red"))
            pct_item.setFlags(pct_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.asset_table.setItem(row, 7, pct_item)

        self.asset_table.resizeColumnsToContents()

    def _update_totals(self):
        """Update the totals based on selection."""
        total_value = 0
        total_basis = 0
        total_gain = 0

        for row in range(self.asset_table.rowCount()):
            if self.checkboxes[row].isChecked():
                asset = self.asset_table.item(row, 1).data(Qt.ItemDataRole.UserRole)
                qty = self.spinboxes[row].value()

                if asset.quantity > 0:
                    fraction = qty / asset.quantity
                    value = asset.current_value * fraction
                    basis = asset.total_cost * fraction

                    total_value += value
                    total_basis += basis
                    total_gain += (value - basis)

        self.total_value_label.setText(f"Total Value: ${total_value:,.2f}")
        self.total_basis_label.setText(f"Total Basis: ${total_basis:,.2f}")

        gain_color = "green" if total_gain >= 0 else "red"
        self.total_gain_label.setText(f"Total Gain: ${total_gain:,.2f}")
        self.total_gain_label.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {gain_color};")

        self.completeChanged.emit()

        # Update select all checkbox state
        self._update_select_all_state()

    def _toggle_select_all(self, state):
        """Toggle all asset checkboxes based on Select All state."""
        checked = state == Qt.CheckState.Checked.value

        # Block signals to prevent multiple updates
        for row, checkbox in self.checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)

        # Single update after all changes
        self._update_totals()

    def _update_select_all_state(self):
        """Update the Select All checkbox based on individual selections."""
        if not self.checkboxes:
            return

        all_checked = all(cb.isChecked() for cb in self.checkboxes.values())
        none_checked = not any(cb.isChecked() for cb in self.checkboxes.values())

        # Block signals to prevent recursion
        self.select_all_checkbox.blockSignals(True)
        if all_checked:
            self.select_all_checkbox.setChecked(True)
        elif none_checked:
            self.select_all_checkbox.setChecked(False)
        else:
            # Partial selection - uncheck but could use tristate if desired
            self.select_all_checkbox.setChecked(False)
        self.select_all_checkbox.blockSignals(False)

    def get_selections(self) -> List[AssetSelection]:
        """Get list of selected assets and quantities."""
        selections = []

        for row in range(self.asset_table.rowCount()):
            if self.checkboxes[row].isChecked():
                asset = self.asset_table.item(row, 1).data(Qt.ItemDataRole.UserRole)
                qty = self.spinboxes[row].value()

                if qty > 0:
                    selections.append(AssetSelection(asset=asset, quantity_to_sell=qty))

        return selections

    def isComplete(self) -> bool:
        """Page is complete if at least one asset is selected."""
        return any(cb.isChecked() and self.spinboxes[row].value() > 0
                   for row, cb in self.checkboxes.items())

    def get_selection_data(self) -> Dict[str, float]:
        """Get current selections as a dict of asset_id -> quantity for saving."""
        selections = {}
        for row in range(self.asset_table.rowCount()):
            if self.checkboxes[row].isChecked():
                asset = self.asset_table.item(row, 1).data(Qt.ItemDataRole.UserRole)
                qty = self.spinboxes[row].value()
                if qty > 0:
                    selections[str(asset.id)] = qty
        return selections

    def restore_selections(self, selections: Dict[str, float]):
        """Restore selections from saved data."""
        # Build lookup of asset_id -> row
        id_to_row = {}
        for row in range(self.asset_table.rowCount()):
            asset = self.asset_table.item(row, 1).data(Qt.ItemDataRole.UserRole)
            id_to_row[str(asset.id)] = row

        # Clear all selections first
        for row, checkbox in self.checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)

        # Restore saved selections
        for asset_id, qty in selections.items():
            if asset_id in id_to_row:
                row = id_to_row[asset_id]
                self.checkboxes[row].blockSignals(True)
                self.checkboxes[row].setChecked(True)
                self.checkboxes[row].blockSignals(False)
                self.spinboxes[row].blockSignals(True)
                self.spinboxes[row].setValue(min(qty, self.spinboxes[row].maximum()))
                self.spinboxes[row].blockSignals(False)

        self._update_totals()


class TaxSettingsPage(QWizardPage):
    """Wizard page for tax settings with interactive 401k slider and chart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Tax Settings & Strategy Options")
        self.setSubTitle("Configure tax optimization, 401k contributions, and emergency fund priority.")
        self._selected_assets = []  # Will be populated from previous page
        self._liabilities = []
        self._silver_price_multiplier = 1.0  # Multiplier from silver outlook slider (1.0 = current price)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Create horizontal splitter for controls and chart
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left panel - Controls in a scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setMinimumWidth(320)

        scroll_content = QWidget()
        left_layout = QVBoxLayout(scroll_content)
        left_layout.setContentsMargins(4, 4, 8, 4)
        left_layout.setSpacing(8)

        # Income settings (compact)
        income_group = QGroupBox("Income & Filing")
        income_layout = QFormLayout(income_group)
        income_layout.setSpacing(4)
        income_layout.setContentsMargins(8, 12, 8, 8)

        self.gross_income_input = QDoubleSpinBox()
        self.gross_income_input.setRange(0, 10000000)
        self.gross_income_input.setDecimals(0)
        self.gross_income_input.setPrefix("$")
        self.gross_income_input.setSingleStep(1000)
        self.gross_income_input.valueChanged.connect(self._on_inputs_changed)
        income_layout.addRow("Gross Income:", self.gross_income_input)

        self.current_401k_input = QDoubleSpinBox()
        self.current_401k_input.setRange(0, MAX_401K_CONTRIBUTION + MAX_401K_CATCHUP)
        self.current_401k_input.setDecimals(0)
        self.current_401k_input.setPrefix("$")
        self.current_401k_input.setSingleStep(500)
        self.current_401k_input.setToolTip(
            "Your current ANNUAL 401k contribution (not balance).\n"
            "This is the amount deducted from your paycheck each year.\n"
            "Pre-tax contributions reduce taxable income and increase LTCG headroom."
        )
        self.current_401k_input.valueChanged.connect(self._on_inputs_changed)
        income_layout.addRow("401k Contrib:", self.current_401k_input)

        self.filing_status = QComboBox()
        self.filing_status.addItem("Single", "single")
        self.filing_status.addItem("Married Filing Jointly", "married_joint")
        self.filing_status.addItem("Head of Household", "head_household")
        self.filing_status.currentIndexChanged.connect(self._on_inputs_changed)
        income_layout.addRow("Filing Status:", self.filing_status)

        self.catchup_checkbox = QCheckBox("Age 50+ (catchup)")
        self.catchup_checkbox.stateChanged.connect(self._update_slider_range)
        income_layout.addRow("", self.catchup_checkbox)

        left_layout.addWidget(income_group)

        # 401k Slider
        slider_group = QGroupBox("Additional 401k Contribution")
        slider_layout = QVBoxLayout(slider_group)
        slider_layout.setSpacing(4)
        slider_layout.setContentsMargins(8, 12, 8, 8)

        # Slider value label
        self.slider_value_label = QLabel("$0")
        self.slider_value_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #0066cc;")
        self.slider_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        slider_layout.addWidget(self.slider_value_label)

        # Slider
        self.contribution_slider = QSlider(Qt.Orientation.Horizontal)
        self.contribution_slider.setRange(0, MAX_401K_CONTRIBUTION)
        self.contribution_slider.setValue(0)
        self.contribution_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.contribution_slider.setTickInterval(5000)
        self.contribution_slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.contribution_slider)

        # Min/Max labels
        range_layout = QHBoxLayout()
        range_layout.setContentsMargins(0, 0, 0, 0)
        self.min_label = QLabel("$0")
        self.max_label = QLabel(f"${MAX_401K_CONTRIBUTION:,}")
        range_layout.addWidget(self.min_label)
        range_layout.addStretch()
        range_layout.addWidget(self.max_label)
        slider_layout.addLayout(range_layout)

        # Quick buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        self.optimal_btn = QPushButton("Optimal")
        self.optimal_btn.setToolTip("Set to optimal amount for 0% LTCG")
        self.optimal_btn.clicked.connect(self._set_optimal)
        self.max_btn = QPushButton("Max")
        self.max_btn.setToolTip("Set to maximum allowed")
        self.max_btn.clicked.connect(self._set_maximum)
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(lambda: self.contribution_slider.setValue(0))
        btn_layout.addWidget(self.optimal_btn)
        btn_layout.addWidget(self.max_btn)
        btn_layout.addWidget(self.reset_btn)
        slider_layout.addLayout(btn_layout)

        left_layout.addWidget(slider_group)

        # Emergency Fund Priority
        efund_group = QGroupBox("Emergency Fund")
        efund_layout = QFormLayout(efund_group)
        efund_layout.setSpacing(4)
        efund_layout.setContentsMargins(8, 12, 8, 8)

        self.efund_checkbox = QCheckBox("Include e-fund goal")
        self.efund_checkbox.setToolTip("Include emergency fund in the debt payoff strategy")
        self.efund_checkbox.stateChanged.connect(self._on_efund_changed)
        efund_layout.addRow("", self.efund_checkbox)

        self.efund_target_input = QDoubleSpinBox()
        self.efund_target_input.setRange(0, 100000)
        self.efund_target_input.setDecimals(0)
        self.efund_target_input.setPrefix("$")
        self.efund_target_input.setSingleStep(500)
        self.efund_target_input.setValue(1000)
        self.efund_target_input.setEnabled(False)
        self.efund_target_input.valueChanged.connect(self._on_inputs_changed)
        efund_layout.addRow("Target:", self.efund_target_input)

        self.efund_current_input = QDoubleSpinBox()
        self.efund_current_input.setRange(0, 100000)
        self.efund_current_input.setDecimals(0)
        self.efund_current_input.setPrefix("$")
        self.efund_current_input.setSingleStep(100)
        self.efund_current_input.setValue(0)
        self.efund_current_input.setEnabled(False)
        self.efund_current_input.valueChanged.connect(self._on_inputs_changed)
        efund_layout.addRow("Current:", self.efund_current_input)

        self.efund_months_label = QLabel("0 mo expenses")
        self.efund_months_label.setStyleSheet("color: #666; font-size: 9px;")
        efund_layout.addRow("", self.efund_months_label)

        # Quick preset buttons
        efund_btn_layout = QHBoxLayout()
        efund_btn_layout.setSpacing(2)
        self.efund_1mo_btn = QPushButton("1mo")
        self.efund_1mo_btn.setMaximumWidth(40)
        self.efund_1mo_btn.clicked.connect(lambda: self._set_efund_months(1))
        self.efund_1mo_btn.setEnabled(False)
        self.efund_3mo_btn = QPushButton("3mo")
        self.efund_3mo_btn.setMaximumWidth(40)
        self.efund_3mo_btn.clicked.connect(lambda: self._set_efund_months(3))
        self.efund_3mo_btn.setEnabled(False)
        self.efund_6mo_btn = QPushButton("6mo")
        self.efund_6mo_btn.setMaximumWidth(40)
        self.efund_6mo_btn.clicked.connect(lambda: self._set_efund_months(6))
        self.efund_6mo_btn.setEnabled(False)
        efund_btn_layout.addWidget(self.efund_1mo_btn)
        efund_btn_layout.addWidget(self.efund_3mo_btn)
        efund_btn_layout.addWidget(self.efund_6mo_btn)
        efund_btn_layout.addStretch()
        efund_layout.addRow("Presets:", efund_btn_layout)

        self.efund_mode_combo = QComboBox()
        self.efund_mode_combo.addItem("Lump sum first", "lump_sum")
        self.efund_mode_combo.addItem("In avalanche", "avalanche")
        self.efund_mode_combo.setToolTip(
            "Lump sum: Allocate to e-fund before any debt payments\n"
            "Avalanche: Treat e-fund as a 'virtual debt' with priority rate"
        )
        self.efund_mode_combo.setEnabled(False)
        self.efund_mode_combo.currentIndexChanged.connect(self._on_efund_mode_changed)
        efund_layout.addRow("Mode:", self.efund_mode_combo)

        self.efund_rate_input = QDoubleSpinBox()
        self.efund_rate_input.setRange(0, 100)
        self.efund_rate_input.setDecimals(1)
        self.efund_rate_input.setSuffix("%")
        self.efund_rate_input.setSingleStep(1)
        self.efund_rate_input.setValue(50.0)
        self.efund_rate_input.setToolTip("Virtual rate for avalanche ordering")
        self.efund_rate_input.setEnabled(False)
        self.efund_rate_input.setVisible(False)
        self.efund_rate_input.valueChanged.connect(self._on_inputs_changed)
        self.efund_rate_label = QLabel("Priority:")
        self.efund_rate_label.setVisible(False)
        efund_layout.addRow(self.efund_rate_label, self.efund_rate_input)

        left_layout.addWidget(efund_group)

        # Debt-Free Goal Timeline
        goal_group = QGroupBox("Debt-Free Goal")
        goal_layout = QVBoxLayout(goal_group)
        goal_layout.setSpacing(4)
        goal_layout.setContentsMargins(8, 12, 8, 8)

        self.goal_value_label = QLabel("No Goal Set")
        self.goal_value_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #006600;")
        self.goal_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        goal_layout.addWidget(self.goal_value_label)

        self.goal_slider = QSlider(Qt.Orientation.Horizontal)
        self.goal_slider.setRange(0, 120)
        self.goal_slider.setValue(0)
        self.goal_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.goal_slider.setTickInterval(12)
        self.goal_slider.valueChanged.connect(self._on_goal_slider_changed)
        goal_layout.addWidget(self.goal_slider)

        goal_range_layout = QHBoxLayout()
        goal_range_layout.setContentsMargins(0, 0, 0, 0)
        goal_range_layout.addWidget(QLabel("None"))
        goal_range_layout.addStretch()
        goal_range_layout.addWidget(QLabel("10yr"))
        goal_layout.addLayout(goal_range_layout)

        self.goal_status_label = QLabel("")
        self.goal_status_label.setStyleSheet("font-size: 10px;")
        self.goal_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        goal_layout.addWidget(self.goal_status_label)

        goal_btn_layout = QHBoxLayout()
        goal_btn_layout.setSpacing(2)
        for text, months in [("1Y", 12), ("2Y", 24), ("3Y", 36), ("5Y", 60)]:
            btn = QPushButton(text)
            btn.setMaximumWidth(35)
            btn.clicked.connect(lambda checked, m=months: self.goal_slider.setValue(m))
            goal_btn_layout.addWidget(btn)
        self.goal_clear_btn = QPushButton("Clear")
        self.goal_clear_btn.setMaximumWidth(45)
        self.goal_clear_btn.clicked.connect(lambda: self.goal_slider.setValue(0))
        goal_btn_layout.addWidget(self.goal_clear_btn)
        goal_layout.addLayout(goal_btn_layout)

        left_layout.addWidget(goal_group)

        # Results summary using grid for better alignment
        results_group = QGroupBox("Impact Summary")
        results_grid = QGridLayout(results_group)
        results_grid.setSpacing(4)
        results_grid.setContentsMargins(8, 12, 8, 8)

        row = 0
        results_grid.addWidget(QLabel("Taxable Income:"), row, 0)
        self.taxable_income_label = QLabel("$0")
        self.taxable_income_label.setStyleSheet("font-weight: bold;")
        results_grid.addWidget(self.taxable_income_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("0% LTCG Room:"), row, 0)
        self.headroom_label = QLabel("$0")
        self.headroom_label.setStyleSheet("font-weight: bold; color: green;")
        results_grid.addWidget(self.headroom_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("Est. Tax:"), row, 0)
        self.tax_owed_label = QLabel("$0")
        self.tax_owed_label.setStyleSheet("font-weight: bold;")
        results_grid.addWidget(self.tax_owed_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("Debt-Free In:"), row, 0)
        self.months_saved_label = QLabel("0")
        self.months_saved_label.setStyleSheet("font-weight: bold;")
        results_grid.addWidget(self.months_saved_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("Cash Reduction:"), row, 0)
        self.monthly_reduction_label = QLabel("$0")
        self.monthly_reduction_label.setStyleSheet("color: #cc6600;")
        results_grid.addWidget(self.monthly_reduction_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("E-Fund Alloc:"), row, 0)
        self.efund_allocation_label = QLabel("$0")
        self.efund_allocation_label.setStyleSheet("font-weight: bold; color: #006699;")
        results_grid.addWidget(self.efund_allocation_label, row, 1)

        # Separator
        row += 1
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        results_grid.addWidget(sep, row, 0, 1, 2)

        row += 1
        results_grid.addWidget(QLabel("401k (10yr):"), row, 0)
        self.projection_401k_label = QLabel("$0")
        self.projection_401k_label.setStyleSheet("font-weight: bold; color: #006600;")
        self.projection_401k_label.setToolTip("Projected 401k value in 10 years (7% return)")
        results_grid.addWidget(self.projection_401k_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("401k (20yr):"), row, 0)
        self.projection_401k_20y_label = QLabel("$0")
        self.projection_401k_20y_label.setStyleSheet("font-weight: bold; color: #006600;")
        self.projection_401k_20y_label.setToolTip("Projected 401k value in 20 years (7% return)")
        results_grid.addWidget(self.projection_401k_20y_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("10Y Net Worth:"), row, 0)
        self.networth_change_label = QLabel("$0")
        self.networth_change_label.setStyleSheet("font-weight: bold; color: #9933cc;")
        self.networth_change_label.setToolTip("Projected 10-year net worth increase")
        results_grid.addWidget(self.networth_change_label, row, 1)

        # Separator before silver price analysis
        row += 1
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        results_grid.addWidget(sep2, row, 0, 1, 2)

        row += 1
        results_grid.addWidget(QLabel("Silver Price:"), row, 0)
        self.current_silver_label = QLabel("$0.00")
        self.current_silver_label.setStyleSheet("font-weight: bold;")
        self.current_silver_label.setToolTip("Current silver spot price")
        results_grid.addWidget(self.current_silver_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("0% Tax Price:"), row, 0)
        self.optimal_silver_label = QLabel("N/A")
        self.optimal_silver_label.setStyleSheet("font-weight: bold; color: #C0C0C0;")
        self.optimal_silver_label.setToolTip("Silver price where total gain equals 0% LTCG headroom (no tax)")
        results_grid.addWidget(self.optimal_silver_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("Price Diff:"), row, 0)
        self.silver_diff_label = QLabel("N/A")
        self.silver_diff_label.setStyleSheet("font-weight: bold;")
        self.silver_diff_label.setToolTip("Difference from current price to reach 0% tax threshold")
        results_grid.addWidget(self.silver_diff_label, row, 1)

        # Silver outlook section
        row += 1
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setFrameShadow(QFrame.Shadow.Sunken)
        results_grid.addWidget(sep3, row, 0, 1, 2)

        row += 1
        outlook_header = QLabel("Silver Outlook (Speculative)")
        outlook_header.setStyleSheet("font-weight: bold; font-size: 10px; color: #888;")
        outlook_header.setToolTip(
            "DISCLAIMER: These are hypothetical scenarios, not financial advice.\n"
            "Silver prices are unpredictable and influenced by many factors.\n"
            "Use for planning purposes only."
        )
        results_grid.addWidget(outlook_header, row, 0, 1, 2)

        # Silver price change slider
        row += 1
        results_grid.addWidget(QLabel("Price Change:"), row, 0)
        self.silver_change_label = QLabel("0%")
        self.silver_change_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        results_grid.addWidget(self.silver_change_label, row, 1)

        row += 1
        self.silver_outlook_slider = QSlider(Qt.Orientation.Horizontal)
        self.silver_outlook_slider.setRange(-50, 100)  # -50% to +100%
        self.silver_outlook_slider.setValue(0)
        self.silver_outlook_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.silver_outlook_slider.setTickInterval(25)
        self.silver_outlook_slider.valueChanged.connect(self._on_silver_outlook_changed)
        results_grid.addWidget(self.silver_outlook_slider, row, 0, 1, 2)

        # Slider range labels
        row += 1
        slider_range_widget = QWidget()
        slider_range_layout = QHBoxLayout(slider_range_widget)
        slider_range_layout.setContentsMargins(0, 0, 0, 0)
        slider_range_layout.addWidget(QLabel("-50%"))
        slider_range_layout.addStretch()
        slider_range_layout.addWidget(QLabel("+100%"))
        results_grid.addWidget(slider_range_widget, row, 0, 1, 2)

        # Projected price and tax at selected change
        row += 1
        results_grid.addWidget(QLabel("Projected:"), row, 0)
        self.silver_projected_label = QLabel("N/A")
        self.silver_projected_label.setStyleSheet("font-weight: bold;")
        self.silver_projected_label.setToolTip("Projected silver price at selected change %")
        results_grid.addWidget(self.silver_projected_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("Tax at Price:"), row, 0)
        self.silver_tax_at_price_label = QLabel("N/A")
        self.silver_tax_at_price_label.setStyleSheet("font-weight: bold;")
        self.silver_tax_at_price_label.setToolTip("Capital gains tax if silver reaches this price")
        results_grid.addWidget(self.silver_tax_at_price_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("To Optimal:"), row, 0)
        self.silver_growth_label = QLabel("N/A")
        self.silver_growth_label.setStyleSheet("font-weight: bold; color: #C0C0C0;")
        self.silver_growth_label.setToolTip("Price change needed to reach 0% tax threshold")
        results_grid.addWidget(self.silver_growth_label, row, 1)

        # Alternative strategy: Invest in 401k instead of debt payoff
        row += 1
        sep4 = QFrame()
        sep4.setFrameShape(QFrame.Shape.HLine)
        sep4.setFrameShadow(QFrame.Shadow.Sunken)
        results_grid.addWidget(sep4, row, 0, 1, 2)

        row += 1
        alt_header = QLabel("Alternative: Invest Instead")
        alt_header.setStyleSheet("font-weight: bold; font-size: 10px; color: #888;")
        alt_header.setToolTip(
            "Compare: What if you invested silver proceeds in 401k\n"
            "instead of paying off debt?\n\n"
            "This assumes you can make after-tax IRA contributions\n"
            "or have 401k room beyond current contributions."
        )
        results_grid.addWidget(alt_header, row, 0, 1, 2)

        row += 1
        results_grid.addWidget(QLabel("Invest (10yr):"), row, 0)
        self.invest_10y_label = QLabel("N/A")
        self.invest_10y_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        self.invest_10y_label.setToolTip("Value if proceeds invested at 7% for 10 years")
        results_grid.addWidget(self.invest_10y_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("Debt Interest:"), row, 0)
        self.debt_interest_label = QLabel("N/A")
        self.debt_interest_label.setStyleSheet("font-weight: bold; color: #cc0000;")
        self.debt_interest_label.setToolTip("Total interest paid on debt over same period")
        results_grid.addWidget(self.debt_interest_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("Net Difference:"), row, 0)
        self.net_diff_label = QLabel("N/A")
        self.net_diff_label.setStyleSheet("font-weight: bold;")
        self.net_diff_label.setToolTip("Investment growth minus debt interest = net benefit")
        results_grid.addWidget(self.net_diff_label, row, 1)

        row += 1
        results_grid.addWidget(QLabel("Recommendation:"), row, 0)
        self.strategy_rec_label = QLabel("N/A")
        self.strategy_rec_label.setStyleSheet("font-weight: bold; font-size: 9px;")
        self.strategy_rec_label.setWordWrap(True)
        results_grid.addWidget(self.strategy_rec_label, row, 1)

        # Set column stretch
        results_grid.setColumnStretch(1, 1)

        left_layout.addWidget(results_group)
        left_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        splitter.addWidget(scroll_area)

        # Right panel - Chart
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(4)

        # Chart type selector and title
        chart_header = QHBoxLayout()
        chart_header.setSpacing(8)

        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItem("Tax Trade-off", "tradeoff")
        self.chart_type_combo.addItem("Debt Waterfall", "waterfall")
        self.chart_type_combo.setToolTip("Switch between chart views")
        self.chart_type_combo.currentIndexChanged.connect(self._on_chart_type_changed)
        chart_header.addWidget(self.chart_type_combo)

        self.chart_label = QLabel("Tax vs Debt Payoff Trade-off")
        self.chart_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_header.addWidget(self.chart_label, 1)

        right_layout.addLayout(chart_header)

        # Create chart
        self._setup_chart()
        right_layout.addWidget(self.chart_view, 1)

        # Trade-off legend
        self.tradeoff_legend = QWidget()
        legend_layout = QHBoxLayout(self.tradeoff_legend)
        legend_layout.setContentsMargins(0, 0, 0, 0)
        legend_layout.setSpacing(8)
        tax_legend = QLabel("● Tax")
        tax_legend.setStyleSheet("color: #cc0000; font-size: 10px;")
        months_legend = QLabel("● Months")
        months_legend.setStyleSheet("color: #0066cc; font-size: 10px;")
        cashflow_legend = QLabel("● Cash Flow")
        cashflow_legend.setStyleSheet("color: #cc6600; font-size: 10px;")
        networth_legend = QLabel("● Net Worth")
        networth_legend.setStyleSheet("color: #9933cc; font-size: 10px;")
        marker_legend = QLabel("◆ Current")
        marker_legend.setStyleSheet("color: #00cc00; font-size: 10px;")
        legend_layout.addWidget(tax_legend)
        legend_layout.addWidget(months_legend)
        legend_layout.addWidget(cashflow_legend)
        legend_layout.addWidget(networth_legend)
        legend_layout.addWidget(marker_legend)
        legend_layout.addStretch()
        right_layout.addWidget(self.tradeoff_legend)

        # Waterfall legend (hidden by default)
        self.waterfall_legend = QWidget()
        self.waterfall_legend.setVisible(False)
        waterfall_legend_layout = QHBoxLayout(self.waterfall_legend)
        waterfall_legend_layout.setContentsMargins(0, 0, 0, 0)
        waterfall_legend_layout.setSpacing(8)
        self.waterfall_legend_label = QLabel("Debt balances over time (stacked)")
        self.waterfall_legend_label.setStyleSheet("color: #666; font-size: 10px;")
        waterfall_legend_layout.addWidget(self.waterfall_legend_label)
        waterfall_legend_layout.addStretch()
        right_layout.addWidget(self.waterfall_legend)

        splitter.addWidget(right_panel)

        # Set splitter sizes and policies
        splitter.setSizes([350, 550])
        splitter.setStretchFactor(0, 0)  # Left panel doesn't stretch
        splitter.setStretchFactor(1, 1)  # Right panel stretches

        layout.addWidget(splitter)

        # Pre-populate income
        self._load_income()

    def _setup_chart(self):
        """Set up the interactive chart."""
        from PyQt6.QtCore import QMargins
        self.chart = QChart()
        self.chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        self.chart.legend().hide()
        self.chart.setMargins(QMargins(5, 5, 5, 5))

        # Tax series (red)
        self.tax_series = QLineSeries()
        self.tax_series.setName("Tax Owed")
        pen = QPen(QColor("#cc0000"))
        pen.setWidth(2)
        self.tax_series.setPen(pen)

        # Months series (blue)
        self.months_series = QLineSeries()
        self.months_series.setName("Months to Debt-Free")
        pen = QPen(QColor("#0066cc"))
        pen.setWidth(2)
        self.months_series.setPen(pen)

        # Current position marker (green diamond)
        self.marker_series = QScatterSeries()
        self.marker_series.setName("Current")
        self.marker_series.setMarkerSize(12)
        self.marker_series.setColor(QColor("#00cc00"))

        # Net worth change series (purple)
        self.networth_series = QLineSeries()
        self.networth_series.setName("Net Worth Change")
        pen = QPen(QColor("#9933cc"))
        pen.setWidth(2)
        self.networth_series.setPen(pen)

        # Net worth marker (purple diamond)
        self.networth_marker_series = QScatterSeries()
        self.networth_marker_series.setName("Current Net Worth")
        self.networth_marker_series.setMarkerSize(10)
        self.networth_marker_series.setColor(QColor("#9933cc"))

        # Cash flow series (orange) - shows monthly cash flow reduction
        self.cashflow_series = QLineSeries()
        self.cashflow_series.setName("Monthly Cash Flow")
        pen = QPen(QColor("#cc6600"))
        pen.setWidth(2)
        self.cashflow_series.setPen(pen)

        # Cash flow marker (orange diamond)
        self.cashflow_marker_series = QScatterSeries()
        self.cashflow_marker_series.setName("Current Cash Flow")
        self.cashflow_marker_series.setMarkerSize(10)
        self.cashflow_marker_series.setColor(QColor("#cc6600"))

        self.chart.addSeries(self.tax_series)
        self.chart.addSeries(self.months_series)
        self.chart.addSeries(self.networth_series)
        self.chart.addSeries(self.cashflow_series)
        self.chart.addSeries(self.marker_series)
        self.chart.addSeries(self.networth_marker_series)
        self.chart.addSeries(self.cashflow_marker_series)

        # X axis (401k contribution)
        self.x_axis = QValueAxis()
        self.x_axis.setTitleText("Additional 401k ($)")
        self.x_axis.setRange(0, MAX_401K_CONTRIBUTION)
        self.x_axis.setLabelFormat("$%.0f")
        self.chart.addAxis(self.x_axis, Qt.AlignmentFlag.AlignBottom)
        self.tax_series.attachAxis(self.x_axis)
        self.months_series.attachAxis(self.x_axis)
        self.marker_series.attachAxis(self.x_axis)
        self.networth_series.attachAxis(self.x_axis)
        self.networth_marker_series.attachAxis(self.x_axis)
        self.cashflow_series.attachAxis(self.x_axis)
        self.cashflow_marker_series.attachAxis(self.x_axis)

        # Y axis for tax (left, red)
        self.y_tax_axis = QValueAxis()
        self.y_tax_axis.setTitleText("Tax ($)")
        self.y_tax_axis.setLabelsColor(QColor("#cc0000"))
        self.y_tax_axis.setLabelFormat("$%.0f")
        self.chart.addAxis(self.y_tax_axis, Qt.AlignmentFlag.AlignLeft)
        self.tax_series.attachAxis(self.y_tax_axis)
        self.marker_series.attachAxis(self.y_tax_axis)

        # Y axis for cash flow (left, orange) - shows monthly cash reduction
        self.y_cashflow_axis = QValueAxis()
        self.y_cashflow_axis.setTitleText("$/mo")
        self.y_cashflow_axis.setLabelsColor(QColor("#cc6600"))
        self.y_cashflow_axis.setLabelFormat("$%.0f")
        self.chart.addAxis(self.y_cashflow_axis, Qt.AlignmentFlag.AlignLeft)
        self.cashflow_series.attachAxis(self.y_cashflow_axis)
        self.cashflow_marker_series.attachAxis(self.y_cashflow_axis)

        # Y axis for months (right, blue)
        self.y_months_axis = QValueAxis()
        self.y_months_axis.setTitleText("Months")
        self.y_months_axis.setLabelsColor(QColor("#0066cc"))
        self.chart.addAxis(self.y_months_axis, Qt.AlignmentFlag.AlignRight)
        self.months_series.attachAxis(self.y_months_axis)

        # Y axis for net worth (far right, purple) - shows projected 10-year net worth increase
        self.y_networth_axis = QValueAxis()
        self.y_networth_axis.setTitleText("10Y Net Worth ($)")
        self.y_networth_axis.setLabelsColor(QColor("#9933cc"))
        self.y_networth_axis.setLabelFormat("$%.0fk")
        self.chart.addAxis(self.y_networth_axis, Qt.AlignmentFlag.AlignRight)
        self.networth_series.attachAxis(self.y_networth_axis)
        self.networth_marker_series.attachAxis(self.y_networth_axis)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setMinimumHeight(300)

    def initializePage(self):
        """Called when page is shown - get data from previous page."""
        wizard = self.wizard()
        asset_page = wizard.page(0)
        self._selected_assets = asset_page.get_selections()
        self._liabilities = LiabilityOperations.get_all()
        self._update_chart()
        self._update_display()  # Refresh silver analysis and other displays with loaded assets

    def _load_income(self):
        """Pre-populate income and expenses from database."""
        from ...database.operations import ExpenseOperations

        incomes = IncomeOperations.get_active()
        annual_income = sum(i.annual_amount for i in incomes)
        self.gross_income_input.setValue(annual_income)

        # Load monthly expenses for emergency fund calculation
        expenses = ExpenseOperations.get_active()
        self._monthly_expenses = sum(e.monthly_amount for e in expenses)
        self._update_efund_months_label()

        self._update_slider_range()

    def _on_efund_changed(self, state):
        """Handle emergency fund checkbox state change."""
        enabled = state == Qt.CheckState.Checked.value
        self.efund_target_input.setEnabled(enabled)
        self.efund_current_input.setEnabled(enabled)
        self.efund_1mo_btn.setEnabled(enabled)
        self.efund_3mo_btn.setEnabled(enabled)
        self.efund_6mo_btn.setEnabled(enabled)
        self.efund_mode_combo.setEnabled(enabled)
        # Show/hide rate input based on mode
        is_avalanche = self.efund_mode_combo.currentData() == "avalanche"
        self.efund_rate_input.setEnabled(enabled and is_avalanche)
        self.efund_rate_input.setVisible(enabled and is_avalanche)
        self.efund_rate_label.setVisible(enabled and is_avalanche)
        self._update_chart()
        self._update_display()

    def _on_efund_mode_changed(self, index):
        """Handle emergency fund allocation mode change."""
        is_avalanche = self.efund_mode_combo.currentData() == "avalanche"
        enabled = self.efund_checkbox.isChecked()
        self.efund_rate_input.setEnabled(enabled and is_avalanche)
        self.efund_rate_input.setVisible(is_avalanche)
        self.efund_rate_label.setVisible(is_avalanche)
        self._update_chart()
        self._update_display()

    def _set_efund_months(self, months: int):
        """Set emergency fund target to specified months of expenses."""
        if hasattr(self, '_monthly_expenses') and self._monthly_expenses > 0:
            target = self._monthly_expenses * months
            self.efund_target_input.setValue(target)

    def _update_efund_months_label(self):
        """Update the emergency fund months label."""
        if not hasattr(self, '_monthly_expenses') or self._monthly_expenses <= 0:
            self.efund_months_label.setText("(no expense data)")
            return

        target = self.efund_target_input.value()
        months = target / self._monthly_expenses if self._monthly_expenses > 0 else 0
        self.efund_months_label.setText(f"≈ {months:.1f} months of expenses (${self._monthly_expenses:,.0f}/mo)")

    def _get_efund_allocation(self) -> float:
        """Calculate how much to allocate to emergency fund (lump sum mode only)."""
        if not self.efund_checkbox.isChecked():
            return 0.0

        # In avalanche mode, e-fund is handled in the simulation, not as lump sum
        if self.efund_mode_combo.currentData() == "avalanche":
            return 0.0

        target = self.efund_target_input.value()
        current = self.efund_current_input.value()
        needed = max(0, target - current)

        # Can't allocate more than we have from selling
        # Calculate tax directly to avoid circular call to _calculate_tax_and_months
        total_value = sum(s.value_to_sell for s in self._selected_assets)
        total_gain = sum(s.gain_loss for s in self._selected_assets)

        gross = self.gross_income_input.value()
        current_401k = self.current_401k_input.value()
        additional_401k = self.contribution_slider.value()
        status = self.filing_status.currentData()
        threshold = LTCG_THRESHOLDS.get(status, 47025)

        taxable_income = gross - current_401k - additional_401k
        headroom = max(0, threshold - taxable_income)

        if total_gain <= 0 or total_gain <= headroom:
            tax = 0
        else:
            tax = (total_gain - headroom) * 0.15

        net_proceeds = total_value - tax

        return min(needed, net_proceeds)

    def _get_efund_settings(self) -> Tuple[bool, str, float, float, float]:
        """Get emergency fund settings: (enabled, mode, target, current, virtual_rate)."""
        if not self.efund_checkbox.isChecked():
            return (False, "lump_sum", 0, 0, 0)

        mode = self.efund_mode_combo.currentData()
        target = self.efund_target_input.value()
        current = self.efund_current_input.value()
        rate = self.efund_rate_input.value() if mode == "avalanche" else 0

        return (True, mode, target, current, rate)

    def _get_adjusted_asset_value(self, selection) -> float:
        """Get the adjusted value for an asset considering silver price outlook.

        If the asset is silver and the silver outlook slider is set, applies the
        price multiplier to calculate a projected value.
        """
        symbol = getattr(selection.asset, 'symbol', '').lower()
        is_silver = symbol == 'silver'

        if is_silver and self._silver_price_multiplier != 1.0:
            # Apply the price multiplier to silver assets
            if selection.asset.asset_type == 'metal':
                adjusted_price = selection.asset.current_price * self._silver_price_multiplier
                price_per_unit = adjusted_price * selection.asset.weight_per_unit
                return selection.quantity_to_sell * price_per_unit
            return selection.quantity_to_sell * selection.asset.current_price * self._silver_price_multiplier

        # Non-silver or no price adjustment
        return selection.value_to_sell

    def _get_adjusted_asset_gain(self, selection) -> float:
        """Get the adjusted gain/loss for an asset considering silver price outlook.

        If the asset is silver and the silver outlook slider is set, calculates gain
        based on the projected price.
        """
        adjusted_value = self._get_adjusted_asset_value(selection)
        return adjusted_value - selection.cost_basis_portion

    def _get_total_adjusted_value(self) -> float:
        """Get total value of all selected assets with silver price adjustment applied."""
        return sum(self._get_adjusted_asset_value(s) for s in self._selected_assets)

    def _get_total_adjusted_gain(self) -> float:
        """Get total gain from all selected assets with silver price adjustment applied."""
        return sum(self._get_adjusted_asset_gain(s) for s in self._selected_assets)

    def _update_slider_range(self):
        """Update slider range based on current 401k and age."""
        current = int(self.current_401k_input.value())
        max_limit = MAX_401K_CONTRIBUTION
        if self.catchup_checkbox.isChecked():
            max_limit += MAX_401K_CATCHUP

        max_additional = max(0, max_limit - current)
        self.contribution_slider.setMaximum(max_additional)
        self.max_label.setText(f"${max_additional:,}")
        self.x_axis.setRange(0, max(max_additional, 1000))
        self._update_chart()
        self._update_display()

    def _on_inputs_changed(self):
        """Handle changes to income/filing inputs."""
        self._update_chart()
        self._update_display()

    def _on_slider_changed(self, value):
        """Handle slider value changes."""
        self.slider_value_label.setText(f"${value:,}")
        self._update_display()
        self._update_marker()

    def _on_goal_slider_changed(self, value):
        """Handle goal slider value changes."""
        if value == 0:
            self.goal_value_label.setText("No Goal Set")
            self.goal_value_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #666;")
            self.goal_status_label.setText("")
        else:
            # Format the goal display
            years = value // 12
            months = value % 12
            if years > 0 and months > 0:
                goal_text = f"{value} months ({years} yr {months} mo)"
            elif years > 0:
                goal_text = f"{value} months ({years} year{'s' if years > 1 else ''})"
            else:
                goal_text = f"{value} month{'s' if value > 1 else ''}"

            self.goal_value_label.setText(goal_text)
            self.goal_value_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #006600;")

            # Compare goal to current projection
            additional_401k = self.contribution_slider.value()
            _, projected_months = self._calculate_tax_and_months(additional_401k)

            if projected_months == 0:
                self.goal_status_label.setText("No debt to pay off")
                self.goal_status_label.setStyleSheet("font-size: 11px; color: #006600;")
            elif projected_months <= value:
                diff = value - projected_months
                if diff == 0:
                    self.goal_status_label.setText("Goal met exactly!")
                else:
                    self.goal_status_label.setText(f"On track! {diff} month{'s' if diff > 1 else ''} ahead of goal")
                self.goal_status_label.setStyleSheet("font-size: 11px; color: #006600; font-weight: bold;")
            else:
                diff = projected_months - value
                self.goal_status_label.setText(f"Behind goal by {diff} month{'s' if diff > 1 else ''}")
                self.goal_status_label.setStyleSheet("font-size: 11px; color: #cc0000; font-weight: bold;")

    def _calculate_tax_and_months(self, additional_401k: float) -> Tuple[float, int]:
        """Calculate tax owed and months to debt-free for given 401k contribution.

        Uses adjusted asset values based on the silver outlook slider to calculate
        tax and debt payoff timeline at the hypothetical silver price.
        """
        gross = self.gross_income_input.value()
        current_401k = self.current_401k_input.value()
        status = self.filing_status.currentData()
        threshold = LTCG_THRESHOLDS.get(status, 47025)

        taxable_income = gross - current_401k - additional_401k
        headroom = max(0, threshold - taxable_income)

        # Calculate total gain from selected assets (using adjusted values for silver outlook)
        total_gain = self._get_total_adjusted_gain()

        # Calculate tax
        if total_gain <= 0:
            tax = 0
        elif total_gain <= headroom:
            tax = 0
        else:
            tax = (total_gain - headroom) * 0.15

        # Calculate net proceeds (using adjusted values for silver outlook)
        total_value = self._get_total_adjusted_value()
        net_proceeds = total_value - tax

        # Calculate emergency fund allocation
        efund_allocation = self._get_efund_allocation() if hasattr(self, 'efund_checkbox') else 0

        # Simulate debt payoff
        months = self._simulate_payoff_months(net_proceeds, additional_401k, efund_allocation)

        return (tax, months)

    def _simulate_payoff_months(self, net_proceeds: float, additional_401k: float, efund_allocation: float = 0) -> int:
        """Simulate months to debt-free with given proceeds and 401k reduction.

        In avalanche mode with e-fund, the emergency fund is treated as a virtual debt
        with a user-specified interest rate, and competes with real debts for payments.
        """
        # Get e-fund settings
        efund_enabled, efund_mode, efund_target, efund_current, efund_rate = self._get_efund_settings()
        efund_needed = max(0, efund_target - efund_current) if efund_enabled else 0

        # Build list of "debts" including virtual e-fund debt if in avalanche mode
        # Each item: (id, balance, payment, monthly_rate, is_efund)
        debt_items = []

        # Add real liabilities
        for l in self._liabilities:
            if l.current_balance > 0:
                debt_items.append({
                    'id': l.id,
                    'name': l.name,
                    'balance': l.current_balance,
                    'payment': l.monthly_payment,
                    'rate': l.interest_rate,  # Annual rate for sorting
                    'monthly_rate': l.monthly_interest_rate,
                    'is_efund': False
                })

        # Add emergency fund as virtual debt if in avalanche mode
        if efund_enabled and efund_mode == "avalanche" and efund_needed > 0:
            # E-fund doesn't have a "payment" - it gets whatever extra is available
            # We'll handle this specially in the simulation
            debt_items.append({
                'id': 'efund',
                'name': 'Emergency Fund',
                'balance': efund_needed,
                'payment': 0,  # No minimum payment
                'rate': efund_rate,  # Virtual rate for sorting
                'monthly_rate': 0,  # No interest accrues on e-fund shortfall
                'is_efund': True
            })

        if not debt_items:
            return 0

        # Sort by interest rate (avalanche order)
        debt_items.sort(key=lambda x: x['rate'], reverse=True)

        # Initialize balances
        balances = {d['id']: d['balance'] for d in debt_items}
        payments = {d['id']: d['payment'] for d in debt_items}
        monthly_rates = {d['id']: d['monthly_rate'] for d in debt_items}

        # Monthly cash flow reduction from 401k
        monthly_401k_increase = additional_401k / 12

        # Subtract lump-sum emergency fund allocation from proceeds (only in lump_sum mode)
        remaining = net_proceeds - efund_allocation

        # Apply initial proceeds to debts in avalanche order
        for d in debt_items:
            if remaining <= 0:
                break
            if balances[d['id']] > 0:
                pay = min(remaining, balances[d['id']])
                balances[d['id']] -= pay
                remaining -= pay

        # Calculate total monthly debt payments (excluding e-fund which has no minimum)
        total_monthly_payments = sum(payments[d['id']] for d in debt_items if not d['is_efund'])

        # Simulate remaining payoff month by month
        month = 0
        freed_payments = 0  # Payments from paid-off debts available for avalanche

        while any(b > 0.01 for b in balances.values()) and month < 600:
            month += 1

            # Accrue interest on real debts (not e-fund)
            for d in debt_items:
                if balances[d['id']] > 0 and not d['is_efund']:
                    interest = balances[d['id']] * monthly_rates[d['id']]
                    balances[d['id']] += interest

            # Make payments in avalanche order
            # Each debt gets its minimum payment, plus any freed payments go to highest rate
            extra_for_avalanche = freed_payments

            for d in debt_items:
                if balances[d['id']] > 0:
                    if d['is_efund']:
                        # E-fund gets whatever extra cash is available
                        pmt = min(extra_for_avalanche, balances[d['id']])
                        extra_for_avalanche -= pmt
                    else:
                        # Real debts get their minimum payment plus any avalanche extra
                        min_pmt = min(payments[d['id']], balances[d['id']])
                        pmt = min_pmt + min(extra_for_avalanche, balances[d['id']] - min_pmt)
                        extra_for_avalanche -= (pmt - min_pmt)

                    balances[d['id']] -= pmt

                    # When a debt is paid off, its payment becomes available for others
                    if balances[d['id']] <= 0.01:
                        balances[d['id']] = 0
                        if not d['is_efund']:
                            freed_payments += payments[d['id']]

        return month

    def _calculate_net_worth_change(self, additional_401k: float) -> float:
        """Calculate 10-year projected net worth change for given 401k contribution.

        Net worth change components:
        1. Debt paid off (immediate increase) - interest saved over time
        2. 401k growth projection (10 years at moderate return)
        3. Emergency fund allocation (liquid savings)
        4. Tax paid (negative)
        """
        tax, months_to_payoff = self._calculate_tax_and_months(additional_401k)

        # Total value from selling assets
        total_value = sum(s.value_to_sell for s in self._selected_assets)
        net_proceeds = total_value - tax

        # Emergency fund allocation
        efund_allocation = self._get_efund_allocation() if hasattr(self, 'efund_checkbox') else 0

        # Calculate interest saved by paying off debt early
        total_interest_saved = 0
        if self._liabilities:
            liabilities = sorted(
                [l for l in self._liabilities if l.current_balance > 0],
                key=lambda x: x.interest_rate, reverse=True
            )

            # Amount available for debt payoff after emergency fund
            debt_payoff_amount = net_proceeds - efund_allocation

            for l in liabilities:
                if debt_payoff_amount <= 0:
                    break
                payoff = min(debt_payoff_amount, l.current_balance)
                # Interest saved = payoff amount * monthly rate * avg remaining months / 2
                # Simplified: approximate interest saved over remaining life
                avg_months = l.months_to_payoff / 2 if l.months_to_payoff > 0 else 60
                total_interest_saved += payoff * l.monthly_interest_rate * min(avg_months, 120)
                debt_payoff_amount -= payoff

        # 401k growth projection (10 years)
        monthly_401k = additional_401k / 12
        annual_return = HISTORICAL_RETURNS[DEFAULT_RETURN_SCENARIO]  # 7%
        fv_401k = calculate_401k_future_value(monthly_401k, 10, annual_return)

        # Total 10-year net worth increase:
        # Debt reduction benefit (immediate) + Interest saved + 401k growth + Emergency fund
        # Note: We're selling metals (reducing assets) but gaining:
        #   - Debt reduction (liability decrease = net worth increase)
        #   - Interest savings over time
        #   - 401k growth from higher contributions
        #   - Emergency fund (liquid asset)

        # The net change from selling metals is the debt reduction minus what you lost
        # Since debt_payoff_amount went to debt, net worth increases by that amount
        # Plus the 401k growth projection

        net_worth_change = (net_proceeds - efund_allocation) + total_interest_saved + fv_401k + efund_allocation - tax
        # Simplify: net_proceeds + total_interest_saved + fv_401k - tax
        # But net_proceeds already has tax subtracted, so:
        net_worth_change = net_proceeds + total_interest_saved + fv_401k

        # Return in thousands for display
        return net_worth_change / 1000

    def _update_chart(self):
        """Update chart with data points across 401k contribution range."""
        self.tax_series.clear()
        self.months_series.clear()
        self.networth_series.clear()
        self.cashflow_series.clear()

        max_contrib = self.contribution_slider.maximum()
        if max_contrib <= 0:
            max_contrib = 1000

        # Calculate points
        step = max(500, max_contrib // 20)
        max_tax = 0
        max_months = 0
        max_networth = 0
        min_networth = float('inf')
        max_cashflow = 0

        for contrib in range(0, max_contrib + 1, step):
            tax, months = self._calculate_tax_and_months(contrib)
            networth = self._calculate_net_worth_change(contrib)
            # Cash flow reduction is monthly 401k contribution (scaled to hundreds for visibility)
            monthly_reduction = contrib / 12
            # Scale to make it visible on the tax axis (divide by 10 for reasonable range)
            cashflow_scaled = monthly_reduction

            self.tax_series.append(contrib, tax)
            self.months_series.append(contrib, months)
            self.networth_series.append(contrib, networth)
            self.cashflow_series.append(contrib, cashflow_scaled)

            max_tax = max(max_tax, tax)
            max_months = max(max_months, months)
            max_networth = max(max_networth, networth)
            min_networth = min(min_networth, networth)
            max_cashflow = max(max_cashflow, cashflow_scaled)

        # Set axis ranges
        self.y_tax_axis.setRange(0, max(max_tax * 1.1, 100))
        self.y_cashflow_axis.setRange(0, max(max_cashflow * 1.1, 100))
        self.y_months_axis.setRange(0, max(max_months * 1.1, 12))

        # Net worth axis - show reasonable range
        if min_networth == float('inf'):
            min_networth = 0
        range_padding = max((max_networth - min_networth) * 0.1, 10)
        self.y_networth_axis.setRange(
            max(0, min_networth - range_padding),
            max_networth + range_padding
        )

        self._update_marker()

    def _update_marker(self):
        """Update the current position marker on chart."""
        self.marker_series.clear()
        self.networth_marker_series.clear()
        self.cashflow_marker_series.clear()
        current_contrib = self.contribution_slider.value()
        tax, _ = self._calculate_tax_and_months(current_contrib)
        networth = self._calculate_net_worth_change(current_contrib)
        cashflow = current_contrib / 12  # Monthly reduction in cash flow
        self.marker_series.append(current_contrib, tax)
        self.networth_marker_series.append(current_contrib, networth)
        self.cashflow_marker_series.append(current_contrib, cashflow)

    def _on_chart_type_changed(self, index):
        """Handle chart type selection change."""
        chart_type = self.chart_type_combo.currentData()
        if chart_type == "tradeoff":
            self.chart_label.setText("Tax vs Debt Payoff Trade-off")
            self.tradeoff_legend.setVisible(True)
            self.waterfall_legend.setVisible(False)
            self._show_tradeoff_chart()
        else:
            self.chart_label.setText("Debt Payoff Timeline")
            self.tradeoff_legend.setVisible(False)
            self.waterfall_legend.setVisible(True)
            self._show_waterfall_chart()

    def _show_tradeoff_chart(self):
        """Show the trade-off chart series and axes."""
        # Show trade-off series
        self.tax_series.setVisible(True)
        self.months_series.setVisible(True)
        self.networth_series.setVisible(True)
        self.cashflow_series.setVisible(True)
        self.marker_series.setVisible(True)
        self.networth_marker_series.setVisible(True)
        self.cashflow_marker_series.setVisible(True)

        # Show trade-off axes
        self.x_axis.setVisible(True)
        self.x_axis.setTitleText("Additional 401k ($)")
        self.y_tax_axis.setVisible(True)
        self.y_months_axis.setVisible(True)
        self.y_networth_axis.setVisible(True)
        self.y_cashflow_axis.setVisible(True)

        # Hide waterfall series
        for series in getattr(self, '_waterfall_series', []):
            series.setVisible(False)
        if hasattr(self, '_waterfall_x_axis'):
            self._waterfall_x_axis.setVisible(False)
        if hasattr(self, '_waterfall_y_axis'):
            self._waterfall_y_axis.setVisible(False)

        self._update_chart()

    def _show_waterfall_chart(self):
        """Show the debt waterfall chart."""
        # Hide trade-off series
        self.tax_series.setVisible(False)
        self.months_series.setVisible(False)
        self.networth_series.setVisible(False)
        self.cashflow_series.setVisible(False)
        self.marker_series.setVisible(False)
        self.networth_marker_series.setVisible(False)
        self.cashflow_marker_series.setVisible(False)

        # Hide trade-off axes
        self.x_axis.setVisible(False)
        self.y_tax_axis.setVisible(False)
        self.y_months_axis.setVisible(False)
        self.y_networth_axis.setVisible(False)
        self.y_cashflow_axis.setVisible(False)

        self._update_waterfall_chart()

    def _simulate_waterfall_timeline(self) -> Dict[str, Any]:
        """Simulate the complete debt payoff timeline, returning balance history for each debt.

        Returns:
            Dict with:
                - 'months': list of month numbers
                - 'debts': list of dicts with 'name', 'color', 'balances' (list parallel to months)
                - 'total_months': total months to payoff
        """
        # Check if we have required data
        if not hasattr(self, '_selected_assets') or not self._selected_assets:
            return {'months': [], 'debts': [], 'total_months': 0}
        if not hasattr(self, '_liabilities') or not self._liabilities:
            return {'months': [], 'debts': [], 'total_months': 0}

        additional_401k = self.contribution_slider.value()
        tax, _ = self._calculate_tax_and_months(additional_401k)

        # Total value from selling assets
        total_value = sum(s.value_to_sell for s in self._selected_assets)
        net_proceeds = total_value - tax

        # Get e-fund settings
        efund_enabled, efund_mode, efund_target, efund_current, efund_rate = self._get_efund_settings()
        efund_needed = max(0, efund_target - efund_current) if efund_enabled else 0
        efund_allocation = self._get_efund_allocation() if efund_mode == "lump_sum" else 0

        # Build list of debts
        debt_items = []
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e']

        for i, l in enumerate(self._liabilities):
            if l.current_balance > 0:
                debt_items.append({
                    'id': l.id,
                    'name': l.name,
                    'balance': l.current_balance,
                    'payment': l.monthly_payment,
                    'rate': l.interest_rate,
                    'monthly_rate': l.monthly_interest_rate,
                    'is_efund': False,
                    'color': colors[i % len(colors)]
                })

        # Add e-fund as virtual debt if in avalanche mode
        if efund_enabled and efund_mode == "avalanche" and efund_needed > 0:
            debt_items.append({
                'id': 'efund',
                'name': 'Emergency Fund',
                'balance': efund_needed,
                'payment': 0,
                'rate': efund_rate,
                'monthly_rate': 0,
                'is_efund': True,
                'color': '#006699'
            })

        if not debt_items:
            return {'months': [], 'debts': [], 'total_months': 0}

        # Sort by interest rate (avalanche order)
        debt_items.sort(key=lambda x: x['rate'], reverse=True)

        # Initialize tracking
        balances = {d['id']: d['balance'] for d in debt_items}
        payments = {d['id']: d['payment'] for d in debt_items}
        monthly_rates = {d['id']: d['monthly_rate'] for d in debt_items}

        # History tracking - each debt gets a list of balances per month
        history = {d['id']: [d['balance']] for d in debt_items}
        months_list = [0]

        # Apply initial proceeds
        remaining = net_proceeds - efund_allocation
        for d in debt_items:
            if remaining <= 0:
                break
            if balances[d['id']] > 0:
                pay = min(remaining, balances[d['id']])
                balances[d['id']] -= pay
                remaining -= pay

        # Record post-lump-sum state
        for d in debt_items:
            history[d['id']].append(balances[d['id']])
        months_list.append(0.5)  # Half-step to show lump sum payment

        # Simulate month by month
        month = 0
        freed_payments = 0

        while any(b > 0.01 for b in balances.values()) and month < 600:
            month += 1

            # Accrue interest
            for d in debt_items:
                if balances[d['id']] > 0 and not d['is_efund']:
                    interest = balances[d['id']] * monthly_rates[d['id']]
                    balances[d['id']] += interest

            # Make payments in avalanche order
            extra_for_avalanche = freed_payments

            for d in debt_items:
                if balances[d['id']] > 0:
                    if d['is_efund']:
                        pmt = min(extra_for_avalanche, balances[d['id']])
                        extra_for_avalanche -= pmt
                    else:
                        min_pmt = min(payments[d['id']], balances[d['id']])
                        pmt = min_pmt + min(extra_for_avalanche, balances[d['id']] - min_pmt)
                        extra_for_avalanche -= (pmt - min_pmt)

                    balances[d['id']] -= pmt

                    if balances[d['id']] <= 0.01:
                        balances[d['id']] = 0
                        if not d['is_efund']:
                            freed_payments += payments[d['id']]

            # Record state
            for d in debt_items:
                history[d['id']].append(balances[d['id']])
            months_list.append(month)

        return {
            'months': months_list,
            'debts': [
                {
                    'id': d['id'],
                    'name': d['name'],
                    'color': d['color'],
                    'balances': history[d['id']],
                    'is_efund': d['is_efund']
                }
                for d in debt_items
            ],
            'total_months': month
        }

    def _update_waterfall_chart(self):
        """Update the waterfall chart with debt timeline data."""
        # Clear any existing waterfall series
        for series in getattr(self, '_waterfall_series', []):
            try:
                self.chart.removeSeries(series)
            except RuntimeError:
                pass  # Series may already be removed
        self._waterfall_series = []

        # Remove old waterfall axes if they exist
        try:
            if hasattr(self, '_waterfall_x_axis') and self._waterfall_x_axis is not None:
                if self._waterfall_x_axis in self.chart.axes():
                    self.chart.removeAxis(self._waterfall_x_axis)
                self._waterfall_x_axis = None
            if hasattr(self, '_waterfall_y_axis') and self._waterfall_y_axis is not None:
                if self._waterfall_y_axis in self.chart.axes():
                    self.chart.removeAxis(self._waterfall_y_axis)
                self._waterfall_y_axis = None
        except RuntimeError:
            pass  # Axes may already be removed

        # Check if we have data to display
        if not hasattr(self, '_selected_assets') or not hasattr(self, '_liabilities'):
            self.waterfall_legend_label.setText("No data available")
            return

        # Get timeline data
        timeline = self._simulate_waterfall_timeline()
        if not timeline['debts'] or not timeline['months']:
            self.waterfall_legend_label.setText("No debts to display")
            return

        months = timeline['months']
        debts = timeline['debts']

        # Create line series for each debt (simpler and more reliable than area series)
        legend_items = []
        max_balance = 0

        for debt in debts:
            line_series = QLineSeries()
            line_series.setName(debt['name'])

            for i, m in enumerate(months):
                balance = debt['balances'][i]
                line_series.append(m, balance)
                max_balance = max(max_balance, balance)

            # Style the line
            color = QColor(debt['color'])
            pen = QPen(color)
            pen.setWidth(3)
            line_series.setPen(pen)

            self.chart.addSeries(line_series)
            self._waterfall_series.append(line_series)
            legend_items.append((debt['name'], debt['color'], debt['is_efund']))

        # Create axes for waterfall
        self._waterfall_x_axis = QValueAxis()
        self._waterfall_x_axis.setTitleText("Months")
        max_months = max(months) if months else 12
        self._waterfall_x_axis.setRange(0, max_months)
        self._waterfall_x_axis.setLabelFormat("%.0f")
        self.chart.addAxis(self._waterfall_x_axis, Qt.AlignmentFlag.AlignBottom)

        self._waterfall_y_axis = QValueAxis()
        self._waterfall_y_axis.setTitleText("Balance ($)")
        self._waterfall_y_axis.setRange(0, max_balance * 1.1 if max_balance > 0 else 1000)
        self._waterfall_y_axis.setLabelFormat("$%.0f")
        self.chart.addAxis(self._waterfall_y_axis, Qt.AlignmentFlag.AlignLeft)

        # Attach axes to all series
        for series in self._waterfall_series:
            series.attachAxis(self._waterfall_x_axis)
            series.attachAxis(self._waterfall_y_axis)

        # Update legend with colored bullets
        legend_parts = []
        for name, color, is_efund in legend_items:
            legend_parts.append(f"<span style='color:{color};'>\u25cf</span> {name}")
        self.waterfall_legend_label.setText(" | ".join(legend_parts))

    def _update_display(self):
        """Update the results display labels."""
        additional_401k = self.contribution_slider.value()
        gross = self.gross_income_input.value()
        current_401k = self.current_401k_input.value()
        status = self.filing_status.currentData()
        threshold = LTCG_THRESHOLDS.get(status, 47025)

        taxable = gross - current_401k - additional_401k
        headroom = max(0, threshold - taxable)

        tax, months = self._calculate_tax_and_months(additional_401k)

        self.taxable_income_label.setText(f"${taxable:,.0f}")
        self.headroom_label.setText(f"${headroom:,.0f}")

        if headroom > 0:
            self.headroom_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.headroom_label.setStyleSheet("font-weight: bold; color: orange;")

        self.tax_owed_label.setText(f"${tax:,.0f}")
        if tax == 0:
            self.tax_owed_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.tax_owed_label.setStyleSheet("font-weight: bold; color: #cc0000;")

        self.months_saved_label.setText(f"{months} months")

        monthly_reduction = additional_401k / 12
        self.monthly_reduction_label.setText(f"-${monthly_reduction:,.0f}/month")

        # Update emergency fund allocation display
        efund_allocation = self._get_efund_allocation()
        self.efund_allocation_label.setText(f"${efund_allocation:,.0f}")
        if efund_allocation > 0:
            self.efund_allocation_label.setStyleSheet("font-weight: bold; color: #006699;")
        else:
            self.efund_allocation_label.setStyleSheet("font-weight: bold; color: #999;")

        # Update efund months label
        self._update_efund_months_label()

        # Update 401k projections
        self._update_401k_projections(additional_401k)

    def _update_401k_projections(self, additional_401k: float):
        """Calculate and display 401k future value projections."""
        monthly_contribution = additional_401k / 12
        annual_return = HISTORICAL_RETURNS[DEFAULT_RETURN_SCENARIO]  # 7% moderate

        # Calculate projections for 10 and 20 years
        fv_10y = calculate_401k_future_value(monthly_contribution, 10, annual_return)
        fv_20y = calculate_401k_future_value(monthly_contribution, 20, annual_return)

        # Total contributions for comparison
        contributions_10y = additional_401k * 10
        contributions_20y = additional_401k * 20

        # Update labels
        if additional_401k > 0:
            growth_10y = fv_10y - contributions_10y
            growth_20y = fv_20y - contributions_20y

            self.projection_401k_label.setText(f"${fv_10y:,.0f}")
            self.projection_401k_label.setToolTip(
                f"${contributions_10y:,.0f} contributed + ${growth_10y:,.0f} growth (7% avg return)"
            )
            self.projection_401k_label.setStyleSheet("font-weight: bold; color: #006600;")

            self.projection_401k_20y_label.setText(f"${fv_20y:,.0f}")
            self.projection_401k_20y_label.setToolTip(
                f"${contributions_20y:,.0f} contributed + ${growth_20y:,.0f} growth (7% avg return)"
            )
            self.projection_401k_20y_label.setStyleSheet("font-weight: bold; color: #006600;")
        else:
            self.projection_401k_label.setText("$0")
            self.projection_401k_label.setToolTip("No additional 401k contributions")
            self.projection_401k_label.setStyleSheet("font-weight: bold; color: #999;")

            self.projection_401k_20y_label.setText("$0")
            self.projection_401k_20y_label.setToolTip("No additional 401k contributions")
            self.projection_401k_20y_label.setStyleSheet("font-weight: bold; color: #999;")

        # Update net worth projection
        networth_change = self._calculate_net_worth_change(additional_401k)
        networth_value = networth_change * 1000  # Convert back from thousands
        if networth_value > 0:
            self.networth_change_label.setText(f"+${networth_value:,.0f}")
            self.networth_change_label.setStyleSheet("font-weight: bold; color: #9933cc;")
        else:
            self.networth_change_label.setText(f"${networth_value:,.0f}")
            self.networth_change_label.setStyleSheet("font-weight: bold; color: #999;")

        # Update optimal silver price analysis
        self._update_silver_price_analysis()

    def _update_silver_price_analysis(self):
        """Calculate and display optimal silver price for 0% tax."""
        # Find silver assets in selections
        silver_assets = []
        non_silver_gain = 0
        non_silver_basis = 0

        for selection in self._selected_assets:
            # Symbol field contains metal type: 'silver', 'gold', etc.
            symbol = getattr(selection.asset, 'symbol', '').lower()
            is_silver = symbol == 'silver'

            if is_silver:
                silver_assets.append(selection)
            else:
                non_silver_gain += selection.gain_loss
                non_silver_basis += selection.cost_basis_portion

        if not silver_assets:
            # No silver selected
            self.current_silver_label.setText("N/A")
            self.current_silver_label.setStyleSheet("font-weight: bold; color: #999;")
            self.optimal_silver_label.setText("No silver selected")
            self.optimal_silver_label.setStyleSheet("font-weight: bold; color: #999;")
            self.silver_diff_label.setText("N/A")
            self.silver_diff_label.setStyleSheet("font-weight: bold; color: #999;")
            return

        # Get current silver spot price (from first silver asset)
        current_silver_price = silver_assets[0].asset.current_price

        # Calculate total silver weight and basis being sold
        total_silver_weight = sum(s.quantity_to_sell * s.asset.weight_per_unit for s in silver_assets)
        total_silver_basis = sum(s.cost_basis_portion for s in silver_assets)

        # Get LTCG headroom
        gross = self.gross_income_input.value()
        current_401k = self.current_401k_input.value()
        additional_401k = self.contribution_slider.value()
        status = self.filing_status.currentData()
        threshold = LTCG_THRESHOLDS.get(status, 47025)
        taxable_income = gross - current_401k - additional_401k
        headroom = max(0, threshold - taxable_income)

        # Calculate optimal silver price for 0% tax
        # Total gain = silver_value - silver_basis + non_silver_gain
        # For 0% tax: total_gain <= headroom
        # silver_value - silver_basis + non_silver_gain <= headroom
        # silver_value <= headroom - non_silver_gain + silver_basis
        # (silver_price * total_weight) <= headroom - non_silver_gain + silver_basis
        # silver_price <= (headroom - non_silver_gain + silver_basis) / total_weight

        available_gain_for_silver = headroom - non_silver_gain
        if total_silver_weight > 0:
            # Optimal price = (basis + available_gain) / weight
            optimal_silver_price = (total_silver_basis + available_gain_for_silver) / total_silver_weight
        else:
            optimal_silver_price = 0

        # Update display
        self.current_silver_label.setText(f"${current_silver_price:.2f}/oz")
        self.current_silver_label.setStyleSheet("font-weight: bold;")

        if optimal_silver_price <= 0:
            # Already over headroom from non-silver gains
            self.optimal_silver_label.setText("Over limit")
            self.optimal_silver_label.setStyleSheet("font-weight: bold; color: #cc0000;")
            self.optimal_silver_label.setToolTip(
                "Non-silver gains already exceed LTCG headroom.\n"
                "Any silver sale will incur 15% tax."
            )
            self.silver_diff_label.setText("N/A")
            self.silver_diff_label.setStyleSheet("font-weight: bold; color: #cc0000;")
        else:
            self.optimal_silver_label.setText(f"${optimal_silver_price:.2f}/oz")
            self.optimal_silver_label.setStyleSheet("font-weight: bold; color: #C0C0C0;")
            self.optimal_silver_label.setToolTip(
                f"At ${optimal_silver_price:.2f}/oz, your total gain equals\n"
                f"the ${headroom:,.0f} LTCG headroom (0% tax bracket)."
            )

            # Calculate and display difference
            price_diff = optimal_silver_price - current_silver_price
            pct_diff = (price_diff / current_silver_price * 100) if current_silver_price > 0 else 0

            if abs(price_diff) < 0.01:
                self.silver_diff_label.setText("At optimal")
                self.silver_diff_label.setStyleSheet("font-weight: bold; color: #006600;")
            elif price_diff > 0:
                # Silver needs to rise to reach optimal
                self.silver_diff_label.setText(f"+${price_diff:.2f} ({pct_diff:+.1f}%)")
                self.silver_diff_label.setStyleSheet("font-weight: bold; color: #006600;")
                self.silver_diff_label.setToolTip(
                    f"Silver needs to rise ${price_diff:.2f}/oz to reach the 0% tax threshold.\n"
                    f"Currently, you're ${abs(price_diff * total_silver_weight):,.0f} under the optimal value."
                )
            else:
                # Silver is above optimal - will pay some tax
                self.silver_diff_label.setText(f"${price_diff:.2f} ({pct_diff:+.1f}%)")
                self.silver_diff_label.setStyleSheet("font-weight: bold; color: #cc6600;")
                excess_gain = abs(price_diff) * total_silver_weight
                tax_on_excess = excess_gain * 0.15
                self.silver_diff_label.setToolTip(
                    f"Silver is ${abs(price_diff):.2f}/oz above the 0% tax threshold.\n"
                    f"Excess gain: ${excess_gain:,.0f} → Tax: ${tax_on_excess:,.0f} (15%)"
                )

        # Update silver outlook section
        self._update_silver_outlook(current_silver_price, optimal_silver_price, total_silver_weight, total_silver_basis, headroom, non_silver_gain)

        # Update invest vs debt comparison
        self._update_invest_vs_debt_analysis()

    def _update_silver_outlook(self, current_price: float, optimal_price: float,
                                total_weight: float, total_basis: float,
                                headroom: float, non_silver_gain: float):
        """Update the speculative silver price outlook section.

        Stores silver data for the slider and updates the display.

        DISCLAIMER: These are hypothetical scenarios for planning purposes only.
        Silver prices are influenced by many unpredictable factors including:
        - Industrial demand (solar, electronics, EV)
        - Investment demand (ETFs, coins/bars)
        - Monetary policy and interest rates
        - Inflation expectations
        - Geopolitical events
        - Mining supply and costs
        - Currency movements (especially USD)
        """
        # Store silver data for slider use
        self._silver_current_price = current_price
        self._silver_optimal_price = optimal_price
        self._silver_total_weight = total_weight
        self._silver_total_basis = total_basis
        self._silver_headroom = headroom
        self._silver_non_silver_gain = non_silver_gain

        if current_price <= 0 or total_weight <= 0:
            # No silver data - reset all labels
            self.silver_change_label.setText("N/A")
            self.silver_change_label.setStyleSheet("font-weight: bold; color: #999;")
            self.silver_projected_label.setText("N/A")
            self.silver_projected_label.setStyleSheet("font-weight: bold; color: #999;")
            self.silver_tax_at_price_label.setText("N/A")
            self.silver_tax_at_price_label.setStyleSheet("font-weight: bold; color: #999;")
            self.silver_growth_label.setText("N/A")
            self.silver_growth_label.setStyleSheet("font-weight: bold; color: #999;")
            return

        # Update display based on current slider value
        self._update_silver_outlook_from_slider()

        # Update growth rate to reach optimal price
        if optimal_price > 0 and optimal_price > current_price:
            growth_needed = (optimal_price - current_price) / current_price
            growth_pct = growth_needed * 100

            if growth_pct <= 5:
                color = "#006600"
                qualifier = "easily achievable"
            elif growth_pct <= 15:
                color = "#006600"
                qualifier = "reasonably achievable"
            elif growth_pct <= 30:
                color = "#cc6600"
                qualifier = "optimistic but possible"
            else:
                color = "#cc0000"
                qualifier = "would require significant rally"

            self.silver_growth_label.setText(f"+{growth_pct:.1f}% needed")
            self.silver_growth_label.setStyleSheet(f"font-weight: bold; color: {color};")
            self.silver_growth_label.setToolTip(
                f"Silver needs to rise {growth_pct:.1f}% to reach ${optimal_price:.2f}/oz\n"
                f"(the price at which you pay 0% tax)\n\n"
                f"This is {qualifier} based on historical silver volatility\n"
                f"(silver moves 15-40% annually on average).\n\n"
                f"DISCLAIMER: Past performance does not predict future results."
            )
        elif optimal_price > 0 and optimal_price <= current_price:
            self.silver_growth_label.setText("Already optimal")
            self.silver_growth_label.setStyleSheet("font-weight: bold; color: #006600;")
            self.silver_growth_label.setToolTip(
                "Current silver price is at or above the optimal 0% tax price.\n"
                "You could sell now and stay within the 0% LTCG bracket\n"
                "(though you'd pay tax on the excess gain)."
            )
        else:
            self.silver_growth_label.setText("N/A")
            self.silver_growth_label.setStyleSheet("font-weight: bold; color: #999;")
            self.silver_growth_label.setToolTip(
                "Cannot calculate - non-silver gains already exceed LTCG headroom."
            )

    def _on_silver_outlook_changed(self, value: int):
        """Handle silver outlook slider value changes.

        Updates the silver price multiplier and triggers full recalculation of
        all dependent fields (tax, months to debt-free, net worth, chart, etc.).
        """
        # Update the silver price multiplier
        self._silver_price_multiplier = 1.0 + (value / 100.0)

        # Update the silver outlook labels
        self._update_silver_outlook_from_slider()

        # Trigger full recalculation with the new silver price
        self._update_chart()
        self._update_display()
        self._update_marker()

    def _update_silver_outlook_from_slider(self):
        """Update silver outlook display based on current slider value."""
        # Check if we have silver data
        if not hasattr(self, '_silver_current_price') or self._silver_current_price <= 0:
            return

        change_pct = self.silver_outlook_slider.value()
        current_price = self._silver_current_price
        total_weight = self._silver_total_weight
        total_basis = self._silver_total_basis
        headroom = self._silver_headroom
        non_silver_gain = self._silver_non_silver_gain

        # Update change label with color coding
        if change_pct < 0:
            self.silver_change_label.setText(f"{change_pct}%")
            self.silver_change_label.setStyleSheet("font-weight: bold; color: #cc6600;")
        elif change_pct > 0:
            self.silver_change_label.setText(f"+{change_pct}%")
            self.silver_change_label.setStyleSheet("font-weight: bold; color: #006600;")
        else:
            self.silver_change_label.setText("0%")
            self.silver_change_label.setStyleSheet("font-weight: bold; color: #0066cc;")

        # Calculate projected price
        projected_price = current_price * (1 + change_pct / 100)
        self.silver_projected_label.setText(f"${projected_price:.2f}/oz")
        self.silver_projected_label.setToolTip(
            f"Silver price at {change_pct:+}% from current ${current_price:.2f}/oz"
        )

        # Calculate tax at projected price
        silver_value = projected_price * total_weight
        silver_gain = silver_value - total_basis
        total_gain = silver_gain + non_silver_gain

        if total_gain <= 0 or total_gain <= headroom:
            tax = 0
        else:
            tax = (total_gain - headroom) * 0.15

        # Update tax label with color coding
        if tax == 0:
            self.silver_tax_at_price_label.setText(f"$0 (0%)")
            self.silver_tax_at_price_label.setStyleSheet("font-weight: bold; color: #006600;")
            self.silver_tax_at_price_label.setToolTip(
                f"At ${projected_price:.2f}/oz:\n"
                f"Silver value: ${silver_value:,.0f}\n"
                f"Silver gain: ${silver_gain:,.0f}\n"
                f"Total gain: ${total_gain:,.0f}\n"
                f"Headroom: ${headroom:,.0f}\n\n"
                f"Gain is within 0% LTCG bracket - no tax!"
            )
        else:
            excess = total_gain - headroom
            self.silver_tax_at_price_label.setText(f"${tax:,.0f}")
            self.silver_tax_at_price_label.setStyleSheet("font-weight: bold; color: #cc0000;")
            self.silver_tax_at_price_label.setToolTip(
                f"At ${projected_price:.2f}/oz:\n"
                f"Silver value: ${silver_value:,.0f}\n"
                f"Silver gain: ${silver_gain:,.0f}\n"
                f"Total gain: ${total_gain:,.0f}\n"
                f"Headroom: ${headroom:,.0f}\n"
                f"Excess gain: ${excess:,.0f}\n\n"
                f"Tax (15% LTCG): ${tax:,.0f}"
            )

    def _update_invest_vs_debt_analysis(self):
        """Calculate and display comparison of investing proceeds vs paying off debt.

        Compares two strategies:
        1. Sell silver, invest proceeds in 401k/IRA at historical returns
        2. Sell silver, pay off debt immediately

        Shows 10-year projection of net benefit/cost of each approach.
        """
        # Calculate net proceeds from silver sale
        if not self._selected_assets:
            self._reset_invest_labels("No assets")
            return

        total_value = sum(s.value_to_sell for s in self._selected_assets)
        total_gain = sum(s.gain_loss for s in self._selected_assets)

        # Get current tax settings
        gross = self.gross_income_input.value()
        current_401k = self.current_401k_input.value()
        additional_401k = self.contribution_slider.value()
        status = self.filing_status.currentData()
        threshold = LTCG_THRESHOLDS.get(status, 47025)
        taxable_income = gross - current_401k - additional_401k
        headroom = max(0, threshold - taxable_income)

        # Calculate tax on sale
        if total_gain <= 0:
            tax = 0
        elif total_gain <= headroom:
            tax = 0
        else:
            tax = (total_gain - headroom) * 0.15

        net_proceeds = total_value - tax

        if net_proceeds <= 0:
            self._reset_invest_labels("No proceeds")
            return

        # Check if we have debt to compare against
        if not self._liabilities:
            self._reset_invest_labels("No debt")
            return

        # Calculate 10-year investment growth (7% moderate return, lump sum)
        investment_return = HISTORICAL_RETURNS['moderate']  # 7%
        years = 10
        investment_value = net_proceeds * ((1 + investment_return) ** years)
        investment_growth = investment_value - net_proceeds

        # Calculate debt interest over 10 years if debt is kept
        # Simulate continuing to pay minimum payments without the lump sum payoff
        total_debt_interest = self._calculate_debt_interest_over_period(years * 12)

        # Also calculate what happens if we pay off debt with proceeds
        # (interest saved vs keeping the debt)
        interest_saved_if_payoff = self._calculate_interest_saved_with_payoff(net_proceeds)

        # Net difference: investment growth minus interest that would accrue
        # If positive, investing is better; if negative, paying debt is better
        net_difference = investment_growth - interest_saved_if_payoff

        # Update UI labels
        self.invest_10y_label.setText(f"${investment_value:,.0f}")
        self.invest_10y_label.setToolTip(
            f"If you invest ${net_proceeds:,.0f} at 7% annual return:\n"
            f"After 10 years: ${investment_value:,.0f}\n"
            f"Growth: ${investment_growth:,.0f}"
        )

        self.debt_interest_label.setText(f"${interest_saved_if_payoff:,.0f}")
        self.debt_interest_label.setToolTip(
            f"Interest you would save by paying off debt now:\n"
            f"${interest_saved_if_payoff:,.0f} over the life of the debt\n\n"
            f"(This is interest avoided, not total debt interest)"
        )

        if net_difference >= 0:
            self.net_diff_label.setText(f"+${net_difference:,.0f}")
            self.net_diff_label.setStyleSheet("font-weight: bold; color: #006600;")
            self.net_diff_label.setToolTip(
                f"Investment growth exceeds debt interest by ${net_difference:,.0f}\n"
                f"Over 10 years, investing MAY be more profitable."
            )
            self.strategy_rec_label.setText("Consider investing")
            self.strategy_rec_label.setStyleSheet("font-weight: bold; font-size: 9px; color: #006600;")
            self.strategy_rec_label.setToolTip(
                "Based on historical 7% returns vs your debt interest rates,\n"
                "investing the proceeds may yield higher returns.\n\n"
                "HOWEVER: Paying off debt provides guaranteed 'return'\n"
                "equal to your interest rate, while investment returns\n"
                "are not guaranteed. Consider your risk tolerance."
            )
        else:
            self.net_diff_label.setText(f"-${abs(net_difference):,.0f}")
            self.net_diff_label.setStyleSheet("font-weight: bold; color: #cc0000;")
            self.net_diff_label.setToolTip(
                f"Debt interest exceeds investment growth by ${abs(net_difference):,.0f}\n"
                f"Paying off debt is likely the better financial choice."
            )
            self.strategy_rec_label.setText("Pay off debt")
            self.strategy_rec_label.setStyleSheet("font-weight: bold; font-size: 9px; color: #0066cc;")
            self.strategy_rec_label.setToolTip(
                "Your debt interest rates are high enough that paying off\n"
                "debt provides a better guaranteed 'return' than the\n"
                "expected 7% market return.\n\n"
                "Debt payoff is the mathematically optimal choice."
            )

    def _reset_invest_labels(self, reason: str):
        """Reset investment vs debt labels to N/A state."""
        style = "font-weight: bold; color: #999;"
        self.invest_10y_label.setText("N/A")
        self.invest_10y_label.setStyleSheet(style)
        self.invest_10y_label.setToolTip(reason)
        self.debt_interest_label.setText("N/A")
        self.debt_interest_label.setStyleSheet(style)
        self.debt_interest_label.setToolTip(reason)
        self.net_diff_label.setText("N/A")
        self.net_diff_label.setStyleSheet(style)
        self.net_diff_label.setToolTip(reason)
        self.strategy_rec_label.setText("N/A")
        self.strategy_rec_label.setStyleSheet("font-weight: bold; font-size: 9px; color: #999;")
        self.strategy_rec_label.setToolTip(reason)

    def _calculate_debt_interest_over_period(self, months: int) -> float:
        """Calculate total interest paid on all debts over a given period."""
        if not self._liabilities:
            return 0

        total_interest = 0
        balances = {l.id: l.current_balance for l in self._liabilities}

        for month in range(months):
            for l in self._liabilities:
                if balances[l.id] > 0:
                    interest = balances[l.id] * l.monthly_interest_rate
                    total_interest += interest
                    balances[l.id] += interest
                    # Apply minimum payment
                    pmt = min(l.monthly_payment, balances[l.id])
                    balances[l.id] -= pmt

        return total_interest

    def _calculate_interest_saved_with_payoff(self, lump_sum: float) -> float:
        """Calculate interest saved by applying lump sum to debt (avalanche method).

        Compares:
        - Interest paid if debts are paid normally with minimum payments
        - Interest paid if lump sum is applied to highest-rate debt first

        Returns the difference (interest saved).
        """
        if not self._liabilities or lump_sum <= 0:
            return 0

        # First, calculate total interest WITHOUT lump sum (baseline)
        baseline_interest = 0
        balances_baseline = {l.id: l.current_balance for l in self._liabilities}

        month = 0
        max_months = 600  # 50 year cap
        while any(b > 0.01 for b in balances_baseline.values()) and month < max_months:
            month += 1
            for l in self._liabilities:
                if balances_baseline[l.id] > 0:
                    interest = balances_baseline[l.id] * l.monthly_interest_rate
                    baseline_interest += interest
                    balances_baseline[l.id] += interest
                    pmt = min(l.monthly_payment, balances_baseline[l.id])
                    balances_baseline[l.id] -= pmt

        # Now calculate interest WITH lump sum applied (avalanche: highest rate first)
        payoff_interest = 0
        balances_payoff = {l.id: l.current_balance for l in self._liabilities}
        remaining_lump = lump_sum

        # Apply lump sum to debts in order of interest rate (highest first)
        sorted_liabilities = sorted(self._liabilities, key=lambda x: x.interest_rate, reverse=True)
        for l in sorted_liabilities:
            if remaining_lump <= 0:
                break
            payoff_amount = min(remaining_lump, balances_payoff[l.id])
            balances_payoff[l.id] -= payoff_amount
            remaining_lump -= payoff_amount

        # Simulate remaining payoff
        month = 0
        while any(b > 0.01 for b in balances_payoff.values()) and month < max_months:
            month += 1
            for l in self._liabilities:
                if balances_payoff[l.id] > 0:
                    interest = balances_payoff[l.id] * l.monthly_interest_rate
                    payoff_interest += interest
                    balances_payoff[l.id] += interest
                    pmt = min(l.monthly_payment, balances_payoff[l.id])
                    balances_payoff[l.id] -= pmt

        # Interest saved = baseline - with_payoff
        return max(0, baseline_interest - payoff_interest)

    def _set_optimal(self):
        """Set slider to optimal value for 0% LTCG."""
        gross = self.gross_income_input.value()
        current_401k = self.current_401k_input.value()
        status = self.filing_status.currentData()
        threshold = LTCG_THRESHOLDS.get(status, 47025)

        current_taxable = gross - current_401k
        total_gain = sum(s.gain_loss for s in self._selected_assets)

        # Need to get taxable income down so headroom >= total_gain
        needed_headroom = total_gain
        needed_taxable = threshold - needed_headroom
        needed_reduction = max(0, current_taxable - needed_taxable)

        optimal = min(needed_reduction, self.contribution_slider.maximum())
        self.contribution_slider.setValue(int(optimal))

    def _set_maximum(self):
        """Set slider to maximum value."""
        self.contribution_slider.setValue(self.contribution_slider.maximum())

    def get_settings(self) -> Tuple[float, str, float, float, Tuple[bool, str, float, float, float]]:
        """Return (adjusted_annual_income, filing_status, additional_401k, efund_allocation, efund_settings).

        efund_settings is a tuple: (enabled, mode, target, current, virtual_rate)
        """
        gross_income = self.gross_income_input.value()
        current_401k = self.current_401k_input.value()
        additional_401k = self.contribution_slider.value()
        efund_allocation = self._get_efund_allocation()
        efund_settings = self._get_efund_settings()

        adjusted_income = gross_income - current_401k - additional_401k
        return (adjusted_income, self.filing_status.currentData(), float(additional_401k), efund_allocation, efund_settings)

    def get_settings_data(self) -> Dict[str, Any]:
        """Get all tax settings as a dict for saving."""
        return {
            'gross_income': self.gross_income_input.value(),
            'current_401k': self.current_401k_input.value(),
            'filing_status': self.filing_status.currentData(),
            'catchup_enabled': self.catchup_checkbox.isChecked(),
            'additional_401k': self.contribution_slider.value(),
            'efund_enabled': self.efund_checkbox.isChecked(),
            'efund_target': self.efund_target_input.value(),
            'efund_current': self.efund_current_input.value(),
            'efund_mode': self.efund_mode_combo.currentData(),
            'efund_rate': self.efund_rate_input.value(),
            'goal_months': self.goal_slider.value(),
        }

    def restore_settings(self, data: Dict[str, Any]):
        """Restore tax settings from saved data."""
        if 'gross_income' in data:
            self.gross_income_input.setValue(data['gross_income'])
        if 'current_401k' in data:
            self.current_401k_input.setValue(data['current_401k'])
        if 'filing_status' in data:
            idx = self.filing_status.findData(data['filing_status'])
            if idx >= 0:
                self.filing_status.setCurrentIndex(idx)
        if 'catchup_enabled' in data:
            self.catchup_checkbox.setChecked(data['catchup_enabled'])
        if 'additional_401k' in data:
            self.contribution_slider.setValue(int(data['additional_401k']))
            self.slider_value_label.setText(f"${int(data['additional_401k']):,}")
        if 'efund_enabled' in data:
            self.efund_checkbox.setChecked(data['efund_enabled'])
            self._on_efund_changed(Qt.CheckState.Checked.value if data['efund_enabled'] else Qt.CheckState.Unchecked.value)
        if 'efund_target' in data:
            self.efund_target_input.setValue(data['efund_target'])
        if 'efund_current' in data:
            self.efund_current_input.setValue(data['efund_current'])
        if 'efund_mode' in data:
            idx = self.efund_mode_combo.findData(data['efund_mode'])
            if idx >= 0:
                self.efund_mode_combo.setCurrentIndex(idx)
        if 'efund_rate' in data:
            self.efund_rate_input.setValue(data['efund_rate'])
        if 'goal_months' in data:
            self.goal_slider.setValue(data['goal_months'])


class ResultsPage(QWizardPage):
    """Wizard page displaying simulation results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Simulation Results")
        self.setSubTitle("Compare strategies for paying down debt with your metals.")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Results text
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        font = QFont("Courier New", 10)
        self.results_text.setFont(font)
        layout.addWidget(self.results_text)

        # Export button
        btn_layout = QHBoxLayout()
        export_btn = QPushButton("Export Results")
        export_btn.clicked.connect(self._export_results)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def initializePage(self):
        """Run simulation when page is shown."""
        wizard = self.wizard()

        # Get selections from page 0
        asset_page = wizard.page(0)
        selections = asset_page.get_selections()

        # Get settings from page 1
        tax_page = wizard.page(1)
        annual_income, filing_status, additional_401k, efund_allocation, efund_settings = tax_page.get_settings()

        # Get liabilities
        liabilities = LiabilityOperations.get_all()

        # Run simulation
        simulator = DebtPayoffSimulator(
            selections, liabilities, annual_income, filing_status, efund_allocation
        )

        immediate = simulator.simulate_immediate_sale()
        optimized = simulator.simulate_tax_optimized_sale()
        baseline_months, baseline_interest = simulator._simulate_baseline_payoff()

        # Generate report
        self._generate_report(selections, simulator, immediate, optimized,
                             baseline_months, baseline_interest, additional_401k, efund_allocation, efund_settings)

    def _generate_report(self, selections: List[AssetSelection],
                         simulator: DebtPayoffSimulator,
                         immediate: SimulationResult,
                         optimized: SimulationResult,
                         baseline_months: int,
                         baseline_interest: float,
                         additional_401k: float = 0,
                         efund_allocation: float = 0,
                         efund_settings: Tuple[bool, str, float, float, float] = None):
        """Generate the results report."""
        if efund_settings is None:
            efund_settings = (False, "lump_sum", 0, 0, 0)
        efund_enabled, efund_mode, efund_target, efund_current, efund_rate = efund_settings
        lines = []

        def section(title: str):
            lines.append("")
            lines.append("=" * 70)
            lines.append(f" {title}")
            lines.append("=" * 70)

        def fmt(amount: float) -> str:
            return f"${amount:,.2f}"

        # Header
        lines.append("DEBT PAYOFF SIMULATION RESULTS")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        # 401k Strategy (if applicable)
        if additional_401k > 0:
            section("401K OPTIMIZATION STRATEGY")
            lines.append("")
            lines.append(f"  Additional 401k Contribution: {fmt(additional_401k)}/year")
            lines.append(f"  Monthly Increase: {fmt(additional_401k / 12)}/month")
            lines.append("")
            lines.append("  Benefits:")
            lines.append(f"    • Reduces taxable income by {fmt(additional_401k)}")
            lines.append(f"    • Increases 0% LTCG headroom by {fmt(additional_401k)}")
            lines.append(f"    • Builds retirement savings (tax-deferred growth)")
            lines.append("")
            lines.append("  Trade-offs:")
            lines.append(f"    • {fmt(additional_401k / 12)}/month less cash flow")
            lines.append("    • Funds locked until age 59½ (with exceptions)")

            # 401k Growth Projections
            lines.append("")
            lines.append("  PROJECTED 401K GROWTH (from additional contributions only):")
            lines.append("  Based on historical S&P 500 average returns")
            lines.append("")

            monthly_contrib = additional_401k / 12
            for scenario, rate in HISTORICAL_RETURNS.items():
                fv_10y = calculate_401k_future_value(monthly_contrib, 10, rate)
                fv_20y = calculate_401k_future_value(monthly_contrib, 20, rate)
                fv_30y = calculate_401k_future_value(monthly_contrib, 30, rate)
                contrib_10y = additional_401k * 10
                contrib_20y = additional_401k * 20
                contrib_30y = additional_401k * 30
                growth_10y = fv_10y - contrib_10y
                growth_20y = fv_20y - contrib_20y
                growth_30y = fv_30y - contrib_30y

                lines.append(f"    {scenario.upper()} ({rate*100:.0f}% annual return):")
                lines.append(f"      10 years: {fmt(fv_10y)} ({fmt(contrib_10y)} + {fmt(growth_10y)} growth)")
                lines.append(f"      20 years: {fmt(fv_20y)} ({fmt(contrib_20y)} + {fmt(growth_20y)} growth)")
                lines.append(f"      30 years: {fmt(fv_30y)} ({fmt(contrib_30y)} + {fmt(growth_30y)} growth)")
                lines.append("")

        # Emergency Fund Priority (if applicable)
        efund_needed = max(0, efund_target - efund_current) if efund_enabled else 0
        if efund_enabled and efund_needed > 0:
            section("EMERGENCY FUND PRIORITY")
            lines.append("")
            lines.append(f"  Target Amount: {fmt(efund_target)}")
            lines.append(f"  Current Savings: {fmt(efund_current)}")
            lines.append(f"  Amount Needed: {fmt(efund_needed)}")
            lines.append("")

            if efund_mode == "lump_sum":
                lines.append("  Mode: LUMP SUM (allocated upfront before debt payments)")
                lines.append(f"  Amount Allocated: {fmt(efund_allocation)}")
            else:
                lines.append("  Mode: AVALANCHE (included in debt payoff order)")
                lines.append(f"  Virtual Interest Rate: {efund_rate:.1f}%")
                lines.append("  E-fund competes with debts for payment priority based on this rate.")

            lines.append("")
            lines.append("  Benefits:")
            lines.append("    • Financial safety net for unexpected expenses")
            lines.append("    • Prevents need to go into debt for emergencies")
            lines.append("    • Reduces financial stress during debt payoff")
            lines.append("")
            lines.append("  Trade-offs:")
            if efund_mode == "lump_sum":
                lines.append(f"    • {fmt(efund_allocation)} less applied to debt immediately")
            else:
                lines.append("    • Monthly payments split between e-fund and debts")
            lines.append("    • Slightly longer debt payoff timeline")
            lines.append("    • Emergency fund earns less than debt interest costs")

        # Selected Assets
        section("SELECTED ASSETS FOR LIQUIDATION")
        lines.append("")

        total_value = sum(s.value_to_sell for s in selections)
        total_basis = sum(s.cost_basis_portion for s in selections)
        total_gain = sum(s.gain_loss for s in selections)

        for s in selections:
            lines.append(f"  • {s.asset.name}")
            lines.append(f"    Quantity: {s.quantity_to_sell:.2f} units")
            lines.append(f"    Value: {fmt(s.value_to_sell)} | Basis: {fmt(s.cost_basis_portion)}")
            gain_str = f"+{fmt(s.gain_loss)}" if s.gain_loss >= 0 else fmt(s.gain_loss)
            lines.append(f"    Gain/Loss: {gain_str}")
            lines.append("")

        lines.append(f"  TOTALS:")
        lines.append(f"    Total Value: {fmt(total_value)}")
        lines.append(f"    Total Basis: {fmt(total_basis)}")
        gain_str = f"+{fmt(total_gain)}" if total_gain >= 0 else fmt(total_gain)
        lines.append(f"    Total Gain:  {gain_str}")

        # Tax Analysis
        section("TAX ANALYSIS")
        lines.append("")
        if additional_401k > 0:
            lines.append(f"  (With {fmt(additional_401k)} additional 401k contribution)")
            lines.append("")
        lines.append(f"  Annual Income:      {fmt(simulator.annual_income)}")
        lines.append(f"  Filing Status:      {simulator.filing_status.replace('_', ' ').title()}")
        lines.append(f"  0% LTCG Threshold:  {fmt(simulator.ltcg_threshold)}")
        lines.append(f"  Gain Headroom:      {fmt(simulator.calculate_gain_headroom())}")

        # Strategy Comparison
        section("STRATEGY COMPARISON")
        lines.append("")
        lines.append("  OPTION A - IMMEDIATE SALE (sell all now)")
        lines.append(f"    Total Gain Realized:  {fmt(immediate.total_gain)}")
        lines.append(f"    Capital Gains Tax:    {fmt(immediate.total_tax)}")
        lines.append(f"    Net Proceeds:         {fmt(immediate.net_proceeds)}")
        lines.append(f"    Months to Debt-Free:  {immediate.months_to_debt_free}")
        lines.append(f"    Interest Saved:       {fmt(immediate.total_interest_saved)}")

        lines.append("")
        lines.append("  OPTION B - TAX-OPTIMIZED SALE (spread across years)")
        lines.append(f"    Total Gain Realized:  {fmt(optimized.total_gain)}")
        lines.append(f"    Capital Gains Tax:    {fmt(optimized.total_tax)}")
        lines.append(f"    Net Proceeds:         {fmt(optimized.net_proceeds)}")
        lines.append(f"    Years to Complete:    {optimized.years_to_complete}")
        lines.append(f"    Months to Debt-Free:  {optimized.months_to_debt_free}")
        lines.append(f"    Interest Saved:       {fmt(optimized.total_interest_saved)}")

        # Comparison
        tax_diff = immediate.total_tax - optimized.total_tax
        time_diff = optimized.months_to_debt_free - immediate.months_to_debt_free
        interest_diff = immediate.total_interest_saved - optimized.total_interest_saved

        lines.append("")
        lines.append("  COMPARISON:")
        lines.append(f"    Tax Savings (B vs A):     {fmt(tax_diff)}")
        lines.append(f"    Extra Time (B vs A):      {time_diff} months")
        lines.append(f"    Interest Cost (B vs A):   {fmt(interest_diff)}")

        net_benefit = tax_diff - interest_diff
        lines.append("")
        if net_benefit > 0:
            lines.append(f"    >>> Tax-Optimized saves {fmt(net_benefit)} overall")
        elif net_benefit < 0:
            lines.append(f"    >>> Immediate Sale saves {fmt(abs(net_benefit))} overall")
        else:
            lines.append("    >>> Both strategies have similar financial outcomes")

        # Baseline comparison
        section("BASELINE COMPARISON (without selling)")
        lines.append("")
        lines.append(f"  Without selling assets:")
        lines.append(f"    Months to Debt-Free:  {baseline_months}")
        lines.append(f"    Total Interest Paid:  {fmt(baseline_interest)}")
        lines.append("")
        lines.append(f"  With Immediate Sale:")
        lines.append(f"    Months Accelerated:   {baseline_months - immediate.months_to_debt_free}")
        lines.append(f"    Interest Saved:       {fmt(baseline_interest - (baseline_interest - immediate.total_interest_saved))}")

        # Timeline for optimized strategy
        if optimized.timeline:
            section("TAX-OPTIMIZED TIMELINE")
            for event in optimized.timeline:
                lines.append("")
                lines.append(f"  YEAR {event['year']} (Month {event['month']}):")
                lines.append(f"    Assets Sold:")
                for asset in event['assets_sold']:
                    lines.append(f"      • {asset}")
                if 'gain_realized' in event:
                    lines.append(f"    Gain Realized: {fmt(event['gain_realized'])}")
                lines.append(f"    Tax Paid: {fmt(event['tax_paid'])}")
                lines.append(f"    Net Proceeds: {fmt(event['proceeds'])}")
                if event.get('efund_allocation', 0) > 0:
                    lines.append(f"    → Emergency Fund: {fmt(event['efund_allocation'])}")
                    lines.append(f"    → Applied to Debt: {fmt(event.get('proceeds_for_debt', event['proceeds']))}")
                if event['debts_paid']:
                    lines.append(f"    Debt Actions:")
                    for debt in event['debts_paid']:
                        lines.append(f"      • {debt}")

        # Debts eliminated
        if optimized.debts_eliminated:
            section("DEBTS ELIMINATED")
            lines.append("")
            for i, debt in enumerate(optimized.debts_eliminated, 1):
                lines.append(f"  {i}. {debt}")

        # Recommendation
        section("RECOMMENDATION")
        lines.append("")

        if tax_diff > 0 and time_diff <= 12:
            lines.append(f"  RECOMMENDED: Tax-Optimized Sale")
            lines.append(f"  ")
            lines.append(f"  Saves {fmt(tax_diff)} in taxes with only {time_diff} months")
            lines.append(f"  additional time to become debt-free.")
        elif tax_diff > 0 and net_benefit > 0:
            lines.append(f"  RECOMMENDED: Tax-Optimized Sale")
            lines.append(f"  ")
            lines.append(f"  Despite taking {time_diff} months longer, you save")
            lines.append(f"  {fmt(net_benefit)} overall after accounting for extra interest.")
        elif tax_diff == 0:
            lines.append(f"  RECOMMENDED: Immediate Sale")
            lines.append(f"  ")
            lines.append(f"  Your gains fit within the 0% tax bracket, so there's")
            lines.append(f"  no benefit to spreading sales across years.")
        else:
            lines.append(f"  RECOMMENDED: Immediate Sale")
            lines.append(f"  ")
            lines.append(f"  Getting debt-free {abs(time_diff)} months faster outweighs")
            lines.append(f"  the {fmt(abs(tax_diff))} in additional taxes.")

        lines.append("")
        lines.append("=" * 70)
        lines.append(" END OF SIMULATION")
        lines.append("=" * 70)

        self.results_text.setPlainText("\n".join(lines))
        self.report_content = "\n".join(lines)

    def _export_results(self):
        """Export results to a file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Simulation Results",
            f"debt_payoff_simulation_{datetime.now().strftime('%Y%m%d')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.report_content)
                QMessageBox.information(
                    self, "Export Complete",
                    f"Results exported to:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error",
                    f"Failed to export: {str(e)}"
                )


class DebtPayoffSimulationWizard(QWizard):
    """Wizard for debt payoff simulation with tax optimization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Debt Payoff Simulation")
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)  # Default size larger than minimum
        self.setSizeGripEnabled(True)  # Allow resizing from corner

        # Add pages
        self.addPage(AssetSelectionPage())
        self.addPage(TaxSettingsPage())
        self.addPage(ResultsPage())

        # Configure buttons
        self.setButtonText(QWizard.WizardButton.FinishButton, "Close")

        # Add custom Save/Load buttons
        self.setOption(QWizard.WizardOption.HaveCustomButton1, True)
        self.setOption(QWizard.WizardOption.HaveCustomButton2, True)
        self.setButtonText(QWizard.WizardButton.CustomButton1, "Save Settings")
        self.setButtonText(QWizard.WizardButton.CustomButton2, "Load Settings")
        self.customButtonClicked.connect(self._on_custom_button)

        # Try to load saved settings on startup
        self._load_saved_settings()

    def _on_custom_button(self, button_id):
        """Handle custom button clicks."""
        if button_id == QWizard.WizardButton.CustomButton1.value:
            self._save_settings()
        elif button_id == QWizard.WizardButton.CustomButton2.value:
            self._load_settings_with_confirm()

    def _save_settings(self):
        """Save current wizard state to database."""
        asset_page = self.page(0)
        tax_page = self.page(1)

        data = {
            'asset_selections': asset_page.get_selection_data(),
            'tax_settings': tax_page.get_settings_data(),
        }

        try:
            json_data = json.dumps(data)
            SettingsOperations.set(SIMULATION_SETTINGS_KEY, json_data)
            QMessageBox.information(
                self, "Settings Saved",
                "Your simulation settings have been saved.\n"
                "They will be automatically loaded next time you open this wizard."
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Save Error",
                f"Failed to save settings: {str(e)}"
            )

    def _load_settings_with_confirm(self):
        """Load saved settings with user confirmation."""
        saved = SettingsOperations.get(SIMULATION_SETTINGS_KEY, "")
        if not saved:
            QMessageBox.information(
                self, "No Saved Settings",
                "No previously saved simulation settings were found."
            )
            return

        reply = QMessageBox.question(
            self, "Load Settings",
            "Load previously saved settings?\n"
            "This will replace your current selections.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._load_saved_settings()
            QMessageBox.information(
                self, "Settings Loaded",
                "Your saved simulation settings have been restored."
            )

    def _load_saved_settings(self):
        """Load saved settings from database."""
        saved = SettingsOperations.get(SIMULATION_SETTINGS_KEY, "")
        if not saved:
            return

        try:
            data = json.loads(saved)

            # Restore asset selections
            if 'asset_selections' in data:
                asset_page = self.page(0)
                asset_page.restore_selections(data['asset_selections'])

            # Restore tax settings
            if 'tax_settings' in data:
                tax_page = self.page(1)
                tax_page.restore_settings(data['tax_settings'])

        except (json.JSONDecodeError, Exception) as e:
            # Silently ignore load errors on startup
            pass
