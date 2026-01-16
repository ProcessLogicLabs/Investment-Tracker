"""Summary panel widget for portfolio overview."""

from typing import Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class SummaryCard(QFrame):
    """A card widget displaying a summary metric."""

    def __init__(self, title: str, value: str = "$0.00", compact: bool = False, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)

        layout = QVBoxLayout(self)
        if compact:
            layout.setContentsMargins(10, 6, 10, 6)
        else:
            layout.setContentsMargins(15, 10, 15, 10)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        font = QFont()
        font.setPointSize(14 if compact else 16)
        font.setBold(True)
        self.value_label.setFont(font)
        layout.addWidget(self.value_label)

    def set_value(self, value: str, color: str = None):
        """Update the displayed value."""
        self.value_label.setText(value)
        if color:
            self.value_label.setStyleSheet(f"color: {color};")
        else:
            self.value_label.setStyleSheet("")


class SummaryPanel(QWidget):
    """Panel displaying portfolio summary information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the summary panel UI."""
        # Create scroll area for the content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        # Container widget for scrollable content
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(8)

        # Section title font
        section_font = QFont()
        section_font.setPointSize(12)
        section_font.setBold(True)

        # ============ NET WORTH & CASH FLOW (Top Priority) ============
        top_title = QLabel("Financial Overview")
        top_title.setFont(section_font)
        layout.addWidget(top_title)

        top_layout = QGridLayout()
        top_layout.setSpacing(8)

        self.net_worth_card = SummaryCard("Net Worth")
        top_layout.addWidget(self.net_worth_card, 0, 0)

        self.total_assets_value_card = SummaryCard("Total Assets")
        top_layout.addWidget(self.total_assets_value_card, 0, 1)

        self.total_liabilities_card = SummaryCard("Total Liabilities")
        top_layout.addWidget(self.total_liabilities_card, 0, 2)

        self.net_monthly_card = SummaryCard("Net Monthly Cash Flow")
        top_layout.addWidget(self.net_monthly_card, 0, 3)

        self.savings_rate_card = SummaryCard("Savings Rate")
        top_layout.addWidget(self.savings_rate_card, 0, 4)

        layout.addLayout(top_layout)

        # Separator
        self._add_separator(layout)

        # ============ INCOME & EXPENSES ============
        income_expense_title = QLabel("Monthly Income & Expenses")
        income_expense_title.setFont(section_font)
        layout.addWidget(income_expense_title)

        ie_layout = QGridLayout()
        ie_layout.setSpacing(8)

        # Income row
        self.monthly_income_card = SummaryCard("Monthly Income", compact=True)
        ie_layout.addWidget(self.monthly_income_card, 0, 0)

        self.monthly_expenses_card = SummaryCard("Monthly Expenses", compact=True)
        ie_layout.addWidget(self.monthly_expenses_card, 0, 1)

        self.monthly_payments_card = SummaryCard("Debt Payments", compact=True)
        ie_layout.addWidget(self.monthly_payments_card, 0, 2)

        self.total_outflow_card = SummaryCard("Total Outflow", compact=True)
        ie_layout.addWidget(self.total_outflow_card, 0, 3)

        self.annual_savings_card = SummaryCard("Annual Savings", compact=True)
        ie_layout.addWidget(self.annual_savings_card, 0, 4)

        # Expense breakdown row
        self.essential_expenses_card = SummaryCard("Essential", compact=True)
        ie_layout.addWidget(self.essential_expenses_card, 1, 0)

        self.discretionary_expenses_card = SummaryCard("Discretionary", compact=True)
        ie_layout.addWidget(self.discretionary_expenses_card, 1, 1)

        self.income_count_card = SummaryCard("Income Sources", compact=True)
        ie_layout.addWidget(self.income_count_card, 1, 2)

        self.expense_count_card = SummaryCard("Expenses", compact=True)
        ie_layout.addWidget(self.expense_count_card, 1, 3)

        self.annual_income_card = SummaryCard("Annual Income", compact=True)
        ie_layout.addWidget(self.annual_income_card, 1, 4)

        layout.addLayout(ie_layout)

        # Separator
        self._add_separator(layout)

        # ============ ASSET SUMMARY ============
        assets_title = QLabel("Asset Breakdown")
        assets_title.setFont(section_font)
        layout.addWidget(assets_title)

        assets_layout = QGridLayout()
        assets_layout.setSpacing(8)

        # Row 1: Core metrics
        self.total_cost_card = SummaryCard("Cost Basis", compact=True)
        assets_layout.addWidget(self.total_cost_card, 0, 0)

        self.gain_loss_card = SummaryCard("Gain/Loss", compact=True)
        assets_layout.addWidget(self.gain_loss_card, 0, 1)

        self.gain_loss_pct_card = SummaryCard("Return %", compact=True)
        assets_layout.addWidget(self.gain_loss_pct_card, 0, 2)

        self.asset_count_card = SummaryCard("Assets", compact=True)
        assets_layout.addWidget(self.asset_count_card, 0, 3)

        # Row 2: Asset type breakdown
        self.metals_card = SummaryCard("Metals", compact=True)
        assets_layout.addWidget(self.metals_card, 1, 0)

        self.stocks_card = SummaryCard("Securities", compact=True)
        assets_layout.addWidget(self.stocks_card, 1, 1)

        self.retirement_card = SummaryCard("Retirement", compact=True)
        assets_layout.addWidget(self.retirement_card, 1, 2)

        self.other_card = SummaryCard("Other", compact=True)
        assets_layout.addWidget(self.other_card, 1, 3)

        # Row 3: More types
        self.realestate_card = SummaryCard("Real Estate", compact=True)
        assets_layout.addWidget(self.realestate_card, 2, 0)

        self.cash_card = SummaryCard("Cash", compact=True)
        assets_layout.addWidget(self.cash_card, 2, 1)

        # Row 4: Metal ounces
        self.gold_oz_card = SummaryCard("Gold (oz)", compact=True)
        assets_layout.addWidget(self.gold_oz_card, 3, 0)

        self.silver_oz_card = SummaryCard("Silver (oz)", compact=True)
        assets_layout.addWidget(self.silver_oz_card, 3, 1)

        self.platinum_oz_card = SummaryCard("Platinum (oz)", compact=True)
        assets_layout.addWidget(self.platinum_oz_card, 3, 2)

        self.palladium_oz_card = SummaryCard("Palladium (oz)", compact=True)
        assets_layout.addWidget(self.palladium_oz_card, 3, 3)

        layout.addLayout(assets_layout)

        # Separator
        self._add_separator(layout)

        # ============ LIABILITY SUMMARY ============
        liabilities_title = QLabel("Liability Breakdown")
        liabilities_title.setFont(section_font)
        layout.addWidget(liabilities_title)

        liabilities_layout = QGridLayout()
        liabilities_layout.setSpacing(8)

        self.liability_count_card = SummaryCard("Liabilities", compact=True)
        liabilities_layout.addWidget(self.liability_count_card, 0, 0)

        self.total_original_card = SummaryCard("Original Amount", compact=True)
        liabilities_layout.addWidget(self.total_original_card, 0, 1)

        self.total_paid_card = SummaryCard("Total Paid Off", compact=True)
        liabilities_layout.addWidget(self.total_paid_card, 0, 2)

        layout.addLayout(liabilities_layout)

        # Add stretch to push everything up
        layout.addStretch()

        scroll.setWidget(container)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _add_separator(self, layout):
        """Add a horizontal separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

    def update_summary(self, summary: Dict[str, Any]):
        """Update the summary display with new data."""
        # Get all the data
        total_value = summary.get('total_value', 0)
        total_liabilities = summary.get('total_liabilities', 0)
        net_worth = summary.get('net_worth', total_value - total_liabilities)

        liability_summary = summary.get('liability_summary', {})
        monthly_payments = liability_summary.get('total_monthly_payments', 0)

        income_summary = summary.get('income_summary', {})
        monthly_income = income_summary.get('total_monthly', 0)
        annual_income = income_summary.get('total_annual', 0)

        expense_summary = summary.get('expense_summary', {})
        monthly_expenses = expense_summary.get('total_monthly', 0)
        essential_monthly = expense_summary.get('essential_monthly', 0)
        discretionary_monthly = expense_summary.get('discretionary_monthly', 0)

        # Calculate cash flow
        total_outflow = monthly_payments + monthly_expenses
        net_monthly = monthly_income - total_outflow
        savings_rate = (net_monthly / monthly_income * 100) if monthly_income > 0 else 0

        # ============ TOP SECTION ============
        nw_color = '#2e7d32' if net_worth >= 0 else '#c62828'
        self.net_worth_card.set_value(f"${net_worth:,.2f}", nw_color)
        self.total_assets_value_card.set_value(f"${total_value:,.2f}", '#2e7d32')
        self.total_liabilities_card.set_value(f"${total_liabilities:,.2f}", '#c62828' if total_liabilities > 0 else None)

        net_color = '#2e7d32' if net_monthly >= 0 else '#c62828'
        self.net_monthly_card.set_value(f"${net_monthly:+,.2f}", net_color)

        savings_color = '#2e7d32' if savings_rate >= 20 else ('#ff9800' if savings_rate >= 10 else '#c62828')
        self.savings_rate_card.set_value(f"{savings_rate:.1f}%", savings_color)

        # ============ INCOME & EXPENSES ============
        self.monthly_income_card.set_value(f"${monthly_income:,.2f}", '#2e7d32' if monthly_income > 0 else None)
        self.monthly_expenses_card.set_value(f"${monthly_expenses:,.2f}", '#c62828' if monthly_expenses > 0 else None)
        self.monthly_payments_card.set_value(f"${monthly_payments:,.2f}", '#c62828' if monthly_payments > 0 else None)
        self.total_outflow_card.set_value(f"${total_outflow:,.2f}", '#c62828' if total_outflow > 0 else None)

        annual_savings = net_monthly * 12
        self.annual_savings_card.set_value(f"${annual_savings:+,.2f}", net_color)

        self.essential_expenses_card.set_value(f"${essential_monthly:,.2f}", '#1565c0' if essential_monthly > 0 else None)
        self.discretionary_expenses_card.set_value(f"${discretionary_monthly:,.2f}", '#757575' if discretionary_monthly > 0 else None)

        active_sources = income_summary.get('active_sources', 0)
        self.income_count_card.set_value(str(active_sources))

        active_expenses = expense_summary.get('active_expenses', 0)
        self.expense_count_card.set_value(str(active_expenses))

        self.annual_income_card.set_value(f"${annual_income:,.2f}", '#2e7d32' if annual_income > 0 else None)

        # ============ ASSET BREAKDOWN ============
        total_cost = summary.get('total_cost', 0)
        self.total_cost_card.set_value(f"${total_cost:,.2f}")

        gain_loss = summary.get('total_gain_loss', 0)
        gl_color = '#2e7d32' if gain_loss >= 0 else '#c62828'
        self.gain_loss_card.set_value(f"${gain_loss:+,.2f}", gl_color)

        gain_loss_pct = summary.get('gain_loss_percent', 0)
        self.gain_loss_pct_card.set_value(f"{gain_loss_pct:+.2f}%", gl_color)

        asset_count = summary.get('total_assets', 0)
        self.asset_count_card.set_value(str(asset_count))

        by_type = summary.get('by_type', {})

        metals = by_type.get('metal', {})
        self.metals_card.set_value(f"${metals.get('current_value', 0):,.2f}")

        stocks = by_type.get('stock', {})
        self.stocks_card.set_value(f"${stocks.get('current_value', 0):,.2f}")

        retirement = by_type.get('retirement', {})
        self.retirement_card.set_value(f"${retirement.get('current_value', 0):,.2f}")

        other = by_type.get('other', {})
        self.other_card.set_value(f"${other.get('current_value', 0):,.2f}")

        realestate = by_type.get('realestate', {})
        self.realestate_card.set_value(f"${realestate.get('current_value', 0):,.2f}")

        cash = by_type.get('cash', {})
        self.cash_card.set_value(f"${cash.get('current_value', 0):,.2f}")

        # Metal ounces
        metal_ounces = summary.get('metal_ounces', {})
        gold_oz = metal_ounces.get('GOLD', 0)
        silver_oz = metal_ounces.get('SILVER', 0)
        platinum_oz = metal_ounces.get('PLATINUM', 0)
        palladium_oz = metal_ounces.get('PALLADIUM', 0)

        self.gold_oz_card.set_value(f"{gold_oz:,.2f}" if gold_oz else "0")
        self.silver_oz_card.set_value(f"{silver_oz:,.2f}" if silver_oz else "0")
        self.platinum_oz_card.set_value(f"{platinum_oz:,.2f}" if platinum_oz else "0")
        self.palladium_oz_card.set_value(f"{palladium_oz:,.2f}" if palladium_oz else "0")

        # ============ LIABILITY BREAKDOWN ============
        liability_count = liability_summary.get('total_liabilities', 0)
        self.liability_count_card.set_value(str(liability_count))

        total_original = liability_summary.get('total_original', 0)
        self.total_original_card.set_value(f"${total_original:,.2f}")

        total_paid = liability_summary.get('total_paid', 0)
        self.total_paid_card.set_value(f"${total_paid:,.2f}", '#2e7d32' if total_paid > 0 else None)
