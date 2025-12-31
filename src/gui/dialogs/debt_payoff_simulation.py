"""Debt payoff simulation wizard with tax-optimized metals liquidation."""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox,
    QComboBox, QLineEdit, QTextEdit, QGroupBox, QFormLayout,
    QCheckBox, QAbstractItemView, QPushButton, QFileDialog, QMessageBox,
    QSlider, QFrame, QSplitter, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QScatterSeries
from ...database.operations import AssetOperations, LiabilityOperations, IncomeOperations


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


class TaxSettingsPage(QWizardPage):
    """Wizard page for tax settings with interactive 401k slider and chart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Tax Settings & Strategy Options")
        self.setSubTitle("Configure tax optimization, 401k contributions, and emergency fund priority.")
        self._selected_assets = []  # Will be populated from previous page
        self._liabilities = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Create horizontal splitter for controls and chart
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Controls
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)

        # Income settings (compact)
        income_group = QGroupBox("Income & Filing")
        income_layout = QFormLayout(income_group)
        income_layout.setSpacing(8)

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
        income_layout.addRow("Current 401k Contrib:", self.current_401k_input)

        self.filing_status = QComboBox()
        self.filing_status.addItem("Single", "single")
        self.filing_status.addItem("Married Filing Jointly", "married_joint")
        self.filing_status.addItem("Head of Household", "head_household")
        self.filing_status.currentIndexChanged.connect(self._on_inputs_changed)
        income_layout.addRow("Filing Status:", self.filing_status)

        self.catchup_checkbox = QCheckBox("Age 50+")
        self.catchup_checkbox.stateChanged.connect(self._update_slider_range)
        income_layout.addRow("", self.catchup_checkbox)

        left_layout.addWidget(income_group)

        # 401k Slider
        slider_group = QGroupBox("Additional 401k Contribution")
        slider_layout = QVBoxLayout(slider_group)

        # Slider value label
        self.slider_value_label = QLabel("$0")
        self.slider_value_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #0066cc;")
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
        self.min_label = QLabel("$0")
        self.max_label = QLabel(f"${MAX_401K_CONTRIBUTION:,}")
        range_layout.addWidget(self.min_label)
        range_layout.addStretch()
        range_layout.addWidget(self.max_label)
        slider_layout.addLayout(range_layout)

        # Quick buttons
        btn_layout = QHBoxLayout()
        self.optimal_btn = QPushButton("Optimal")
        self.optimal_btn.setToolTip("Set to optimal amount for 0% LTCG")
        self.optimal_btn.clicked.connect(self._set_optimal)
        self.max_btn = QPushButton("Maximum")
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
        efund_group = QGroupBox("Emergency Fund Priority")
        efund_layout = QFormLayout(efund_group)
        efund_layout.setSpacing(8)

        self.efund_checkbox = QCheckBox("Include emergency fund goal")
        self.efund_checkbox.setToolTip("Include emergency fund in the debt payoff strategy")
        self.efund_checkbox.stateChanged.connect(self._on_efund_changed)
        efund_layout.addRow("", self.efund_checkbox)

        self.efund_target_input = QDoubleSpinBox()
        self.efund_target_input.setRange(0, 100000)
        self.efund_target_input.setDecimals(0)
        self.efund_target_input.setPrefix("$")
        self.efund_target_input.setSingleStep(500)
        self.efund_target_input.setValue(1000)  # Default starter emergency fund
        self.efund_target_input.setEnabled(False)
        self.efund_target_input.valueChanged.connect(self._on_inputs_changed)
        efund_layout.addRow("Target Amount:", self.efund_target_input)

        self.efund_current_input = QDoubleSpinBox()
        self.efund_current_input.setRange(0, 100000)
        self.efund_current_input.setDecimals(0)
        self.efund_current_input.setPrefix("$")
        self.efund_current_input.setSingleStep(100)
        self.efund_current_input.setValue(0)
        self.efund_current_input.setEnabled(False)
        self.efund_current_input.valueChanged.connect(self._on_inputs_changed)
        efund_layout.addRow("Current Savings:", self.efund_current_input)

        # Months of expenses calculator
        self.efund_months_label = QLabel("0 months of expenses")
        self.efund_months_label.setStyleSheet("color: #666; font-size: 10px;")
        efund_layout.addRow("", self.efund_months_label)

        # Quick preset buttons
        efund_btn_layout = QHBoxLayout()
        self.efund_1mo_btn = QPushButton("1 mo")
        self.efund_1mo_btn.setToolTip("Set target to 1 month of expenses")
        self.efund_1mo_btn.clicked.connect(lambda: self._set_efund_months(1))
        self.efund_1mo_btn.setEnabled(False)
        self.efund_3mo_btn = QPushButton("3 mo")
        self.efund_3mo_btn.setToolTip("Set target to 3 months of expenses")
        self.efund_3mo_btn.clicked.connect(lambda: self._set_efund_months(3))
        self.efund_3mo_btn.setEnabled(False)
        self.efund_6mo_btn = QPushButton("6 mo")
        self.efund_6mo_btn.setToolTip("Set target to 6 months of expenses")
        self.efund_6mo_btn.clicked.connect(lambda: self._set_efund_months(6))
        self.efund_6mo_btn.setEnabled(False)
        efund_btn_layout.addWidget(self.efund_1mo_btn)
        efund_btn_layout.addWidget(self.efund_3mo_btn)
        efund_btn_layout.addWidget(self.efund_6mo_btn)
        efund_layout.addRow("Presets:", efund_btn_layout)

        # Allocation mode
        self.efund_mode_combo = QComboBox()
        self.efund_mode_combo.addItem("Lump sum first", "lump_sum")
        self.efund_mode_combo.addItem("Include in avalanche", "avalanche")
        self.efund_mode_combo.setToolTip(
            "Lump sum: Allocate to e-fund before any debt payments\n"
            "Avalanche: Treat e-fund as a 'virtual debt' with priority rate"
        )
        self.efund_mode_combo.setEnabled(False)
        self.efund_mode_combo.currentIndexChanged.connect(self._on_efund_mode_changed)
        efund_layout.addRow("Allocation Mode:", self.efund_mode_combo)

        # Virtual interest rate for avalanche mode
        self.efund_rate_input = QDoubleSpinBox()
        self.efund_rate_input.setRange(0, 100)
        self.efund_rate_input.setDecimals(1)
        self.efund_rate_input.setSuffix("%")
        self.efund_rate_input.setSingleStep(1)
        self.efund_rate_input.setValue(50.0)  # Default: high priority (higher than most debts)
        self.efund_rate_input.setToolTip(
            "Virtual interest rate for avalanche ordering.\n"
            "Higher = higher priority (paid before lower-rate debts)\n"
            "e.g., 50% = pay e-fund before any debt under 50% APR\n"
            "Set to 0% to pay e-fund last (after all debts)"
        )
        self.efund_rate_input.setEnabled(False)
        self.efund_rate_input.setVisible(False)
        self.efund_rate_input.valueChanged.connect(self._on_inputs_changed)
        self.efund_rate_label = QLabel("Priority Rate:")
        self.efund_rate_label.setVisible(False)
        efund_layout.addRow(self.efund_rate_label, self.efund_rate_input)

        left_layout.addWidget(efund_group)

        # Results summary
        results_group = QGroupBox("Current Selection Impact")
        results_layout = QFormLayout(results_group)
        results_layout.setSpacing(6)

        self.taxable_income_label = QLabel("$0")
        self.taxable_income_label.setStyleSheet("font-weight: bold;")
        results_layout.addRow("Taxable Income:", self.taxable_income_label)

        self.headroom_label = QLabel("$0")
        self.headroom_label.setStyleSheet("font-weight: bold; color: green;")
        results_layout.addRow("0% LTCG Headroom:", self.headroom_label)

        self.tax_owed_label = QLabel("$0")
        self.tax_owed_label.setStyleSheet("font-weight: bold;")
        results_layout.addRow("Est. Capital Gains Tax:", self.tax_owed_label)

        self.months_saved_label = QLabel("0")
        self.months_saved_label.setStyleSheet("font-weight: bold;")
        results_layout.addRow("Months to Debt-Free:", self.months_saved_label)

        self.monthly_reduction_label = QLabel("$0")
        self.monthly_reduction_label.setStyleSheet("color: #cc6600;")
        results_layout.addRow("Monthly Cash Reduction:", self.monthly_reduction_label)

        self.efund_allocation_label = QLabel("$0")
        self.efund_allocation_label.setStyleSheet("font-weight: bold; color: #006699;")
        results_layout.addRow("Emergency Fund Alloc:", self.efund_allocation_label)

        # 401k projection separator
        results_layout.addRow(QLabel(""))  # spacer

        self.projection_401k_label = QLabel("$0")
        self.projection_401k_label.setStyleSheet("font-weight: bold; color: #006600;")
        self.projection_401k_label.setToolTip("Projected 401k value in 10 years from additional contributions (7% avg return)")
        results_layout.addRow("401k in 10 years:", self.projection_401k_label)

        self.projection_401k_20y_label = QLabel("$0")
        self.projection_401k_20y_label.setStyleSheet("font-weight: bold; color: #006600;")
        self.projection_401k_20y_label.setToolTip("Projected 401k value in 20 years from additional contributions (7% avg return)")
        results_layout.addRow("401k in 20 years:", self.projection_401k_20y_label)

        results_layout.addRow(QLabel(""))  # spacer

        self.networth_change_label = QLabel("$0")
        self.networth_change_label.setStyleSheet("font-weight: bold; color: #9933cc;")
        self.networth_change_label.setToolTip("Projected 10-year net worth increase from this strategy\n(Debt payoff + Interest saved + 401k growth)")
        results_layout.addRow("10Y Net Worth Δ:", self.networth_change_label)

        left_layout.addWidget(results_group)

        left_layout.addStretch()
        splitter.addWidget(left_panel)

        # Right panel - Chart
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)

        chart_label = QLabel("Tax vs Debt Payoff Trade-off")
        chart_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(chart_label)

        # Create chart
        self._setup_chart()
        right_layout.addWidget(self.chart_view)

        # Legend
        legend_layout = QHBoxLayout()
        tax_legend = QLabel("● Tax Owed")
        tax_legend.setStyleSheet("color: #cc0000;")
        months_legend = QLabel("● Months to Debt-Free")
        months_legend.setStyleSheet("color: #0066cc;")
        networth_legend = QLabel("● 10Y Net Worth")
        networth_legend.setStyleSheet("color: #9933cc;")
        marker_legend = QLabel("◆ Current Selection")
        marker_legend.setStyleSheet("color: #00cc00;")
        legend_layout.addWidget(tax_legend)
        legend_layout.addWidget(months_legend)
        legend_layout.addWidget(networth_legend)
        legend_layout.addWidget(marker_legend)
        legend_layout.addStretch()
        right_layout.addLayout(legend_layout)

        splitter.addWidget(right_panel)

        # Set splitter sizes (40% controls, 60% chart)
        splitter.setSizes([400, 600])

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

        self.chart.addSeries(self.tax_series)
        self.chart.addSeries(self.months_series)
        self.chart.addSeries(self.networth_series)
        self.chart.addSeries(self.marker_series)
        self.chart.addSeries(self.networth_marker_series)

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

        # Y axis for tax (left, red)
        self.y_tax_axis = QValueAxis()
        self.y_tax_axis.setTitleText("Tax ($)")
        self.y_tax_axis.setLabelsColor(QColor("#cc0000"))
        self.y_tax_axis.setLabelFormat("$%.0f")
        self.chart.addAxis(self.y_tax_axis, Qt.AlignmentFlag.AlignLeft)
        self.tax_series.attachAxis(self.y_tax_axis)
        self.marker_series.attachAxis(self.y_tax_axis)

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

    def _calculate_tax_and_months(self, additional_401k: float) -> Tuple[float, int]:
        """Calculate tax owed and months to debt-free for given 401k contribution."""
        gross = self.gross_income_input.value()
        current_401k = self.current_401k_input.value()
        status = self.filing_status.currentData()
        threshold = LTCG_THRESHOLDS.get(status, 47025)

        taxable_income = gross - current_401k - additional_401k
        headroom = max(0, threshold - taxable_income)

        # Calculate total gain from selected assets
        total_gain = sum(s.gain_loss for s in self._selected_assets)

        # Calculate tax
        if total_gain <= 0:
            tax = 0
        elif total_gain <= headroom:
            tax = 0
        else:
            tax = (total_gain - headroom) * 0.15

        # Calculate net proceeds
        total_value = sum(s.value_to_sell for s in self._selected_assets)
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
        while any(b > 0.01 for b in balances.values()) and month < 600:
            month += 1

            # Accrue interest on real debts (not e-fund)
            for d in debt_items:
                if balances[d['id']] > 0 and not d['is_efund']:
                    interest = balances[d['id']] * monthly_rates[d['id']]
                    balances[d['id']] += interest

            # Calculate available cash for this month
            # Start with total payments, reduced by 401k increase
            available_cash = max(0, total_monthly_payments - monthly_401k_increase)

            # Make payments in avalanche order
            for d in debt_items:
                if balances[d['id']] > 0 and available_cash > 0:
                    if d['is_efund']:
                        # E-fund gets whatever extra cash is available after minimums
                        pmt = min(available_cash, balances[d['id']])
                    else:
                        # Real debts get their minimum payment first, then extra
                        min_pmt = min(payments[d['id']], balances[d['id']])
                        pmt = min(available_cash, balances[d['id']])
                        pmt = max(pmt, min_pmt)  # At least minimum

                    balances[d['id']] -= pmt
                    available_cash -= pmt

                    # When a debt is paid off, its payment becomes available for others
                    if balances[d['id']] <= 0.01:
                        balances[d['id']] = 0

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

        max_contrib = self.contribution_slider.maximum()
        if max_contrib <= 0:
            max_contrib = 1000

        # Calculate points
        step = max(500, max_contrib // 20)
        max_tax = 0
        max_months = 0
        max_networth = 0
        min_networth = float('inf')

        for contrib in range(0, max_contrib + 1, step):
            tax, months = self._calculate_tax_and_months(contrib)
            networth = self._calculate_net_worth_change(contrib)

            self.tax_series.append(contrib, tax)
            self.months_series.append(contrib, months)
            self.networth_series.append(contrib, networth)

            max_tax = max(max_tax, tax)
            max_months = max(max_months, months)
            max_networth = max(max_networth, networth)
            min_networth = min(min_networth, networth)

        # Set axis ranges
        self.y_tax_axis.setRange(0, max(max_tax * 1.1, 100))
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
        current_contrib = self.contribution_slider.value()
        tax, _ = self._calculate_tax_and_months(current_contrib)
        networth = self._calculate_net_worth_change(current_contrib)
        self.marker_series.append(current_contrib, tax)
        self.networth_marker_series.append(current_contrib, networth)

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
        self.setMinimumSize(800, 600)

        # Add pages
        self.addPage(AssetSelectionPage())
        self.addPage(TaxSettingsPage())
        self.addPage(ResultsPage())

        # Configure buttons
        self.setButtonText(QWizard.WizardButton.FinishButton, "Close")
