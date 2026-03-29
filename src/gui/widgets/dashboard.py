"""Unified dashboard panel combining summary metrics with charts."""

from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QScrollArea, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from .summary_panel import SummaryCard, ProgressCard, GoalCard
from .charts import AllocationPieChart, PerformanceBarChart, ValueHistoryChart, SpotPriceHistoryChart, SpendingCategoryChart
from ..theme import theme, Typography, make_shadow


class DashboardPanel(QWidget):
    """Unified dashboard combining summary metrics with inline charts."""

    goal_add_requested = pyqtSignal()
    goal_edit_requested = pyqtSignal(int)
    goal_delete_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Build the dashboard layout."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(12)

        section_font = QFont()
        section_font.setPointSize(Typography.H2_SIZE)
        section_font.setBold(True)

        # ============ ROW 1: HERO (Quick Glance) ============
        quick_title = QLabel("Quick Glance")
        quick_title.setFont(section_font)
        layout.addWidget(quick_title)

        hero_row = QHBoxLayout()
        hero_row.setSpacing(12)

        self.net_worth_card = SummaryCard("Net Worth", show_sparkline=True)
        hero_row.addWidget(self.net_worth_card, stretch=2)

        self.net_monthly_card = SummaryCard("Net Monthly Cash Flow", show_sparkline=True)
        hero_row.addWidget(self.net_monthly_card, stretch=2)

        self.savings_rate_card = ProgressCard("Savings Rate")
        hero_row.addWidget(self.savings_rate_card, stretch=1)

        self.debt_payoff_card = ProgressCard("Debt Payoff")
        hero_row.addWidget(self.debt_payoff_card, stretch=1)

        layout.addLayout(hero_row)
        self._add_separator(layout)

        # ============ ROW 2: FINANCIAL OVERVIEW + ALLOCATION PIE ============
        overview_title = QLabel("Financial Overview")
        overview_title.setFont(section_font)
        layout.addWidget(overview_title)

        row2 = QHBoxLayout()
        row2.setSpacing(12)

        overview_widget = QWidget()
        overview_grid = QGridLayout(overview_widget)
        overview_grid.setSpacing(8)

        self.total_assets_value_card = SummaryCard("Total Assets")
        overview_grid.addWidget(self.total_assets_value_card, 0, 0)

        self.total_liabilities_card = SummaryCard("Total Liabilities")
        overview_grid.addWidget(self.total_liabilities_card, 0, 1)

        self.gain_loss_card = SummaryCard("Gain/Loss")
        overview_grid.addWidget(self.gain_loss_card, 1, 0)

        self.gain_loss_pct_card = SummaryCard("Return %")
        overview_grid.addWidget(self.gain_loss_pct_card, 1, 1)

        row2.addWidget(overview_widget, stretch=55)

        self.allocation_chart = AllocationPieChart()
        self.allocation_chart.setMinimumHeight(350)
        row2.addWidget(self.allocation_chart, stretch=45)

        layout.addLayout(row2)
        self._add_separator(layout)

        # ============ ROW 3: ASSET BREAKDOWN + PERFORMANCE BAR ============
        assets_title = QLabel("Asset Breakdown")
        assets_title.setFont(section_font)
        layout.addWidget(assets_title)

        row3 = QHBoxLayout()
        row3.setSpacing(12)

        assets_widget = QWidget()
        assets_grid = QGridLayout(assets_widget)
        assets_grid.setSpacing(8)

        self.total_cost_card = SummaryCard("Cost Basis", compact=True)
        assets_grid.addWidget(self.total_cost_card, 0, 0)

        self.asset_count_card = SummaryCard("Assets", compact=True)
        assets_grid.addWidget(self.asset_count_card, 0, 1)

        self.metals_card = SummaryCard("Metals", compact=True)
        assets_grid.addWidget(self.metals_card, 1, 0)

        self.stocks_card = SummaryCard("Securities", compact=True)
        assets_grid.addWidget(self.stocks_card, 1, 1)

        self.retirement_card = SummaryCard("Retirement", compact=True)
        assets_grid.addWidget(self.retirement_card, 2, 0)

        self.other_card = SummaryCard("Other", compact=True)
        assets_grid.addWidget(self.other_card, 2, 1)

        self.realestate_card = SummaryCard("Real Estate", compact=True)
        assets_grid.addWidget(self.realestate_card, 3, 0)

        self.cash_card = SummaryCard("Cash", compact=True)
        assets_grid.addWidget(self.cash_card, 3, 1)

        self.gold_oz_card = SummaryCard("Gold (oz)", compact=True)
        assets_grid.addWidget(self.gold_oz_card, 4, 0)

        self.silver_oz_card = SummaryCard("Silver (oz)", compact=True)
        assets_grid.addWidget(self.silver_oz_card, 4, 1)

        self.platinum_oz_card = SummaryCard("Platinum (oz)", compact=True)
        assets_grid.addWidget(self.platinum_oz_card, 5, 0)

        self.palladium_oz_card = SummaryCard("Palladium (oz)", compact=True)
        assets_grid.addWidget(self.palladium_oz_card, 5, 1)

        row3.addWidget(assets_widget, stretch=55)

        self.performance_chart = PerformanceBarChart()
        self.performance_chart.setMinimumHeight(350)
        row3.addWidget(self.performance_chart, stretch=45)

        layout.addLayout(row3)
        self._add_separator(layout)

        # ============ ROW 4: INCOME/EXPENSES + PORTFOLIO HISTORY ============
        ie_title = QLabel("Monthly Income & Expenses")
        ie_title.setFont(section_font)
        layout.addWidget(ie_title)

        row4 = QHBoxLayout()
        row4.setSpacing(12)

        ie_widget = QWidget()
        ie_grid = QGridLayout(ie_widget)
        ie_grid.setSpacing(8)

        self.monthly_income_card = SummaryCard("Monthly Income", compact=True)
        ie_grid.addWidget(self.monthly_income_card, 0, 0)

        self.monthly_expenses_card = SummaryCard("Monthly Expenses", compact=True)
        ie_grid.addWidget(self.monthly_expenses_card, 0, 1)

        self.monthly_payments_card = SummaryCard("Debt Payments", compact=True)
        ie_grid.addWidget(self.monthly_payments_card, 0, 2)

        self.total_outflow_card = SummaryCard("Total Outflow", compact=True)
        ie_grid.addWidget(self.total_outflow_card, 0, 3)

        self.annual_savings_card = SummaryCard("Annual Savings", compact=True)
        ie_grid.addWidget(self.annual_savings_card, 0, 4)

        self.essential_expenses_card = SummaryCard("Essential", compact=True)
        ie_grid.addWidget(self.essential_expenses_card, 1, 0)

        self.discretionary_expenses_card = SummaryCard("Discretionary", compact=True)
        ie_grid.addWidget(self.discretionary_expenses_card, 1, 1)

        self.income_count_card = SummaryCard("Income Sources", compact=True)
        ie_grid.addWidget(self.income_count_card, 1, 2)

        self.expense_count_card = SummaryCard("Expenses", compact=True)
        ie_grid.addWidget(self.expense_count_card, 1, 3)

        self.annual_income_card = SummaryCard("Annual Income", compact=True)
        ie_grid.addWidget(self.annual_income_card, 1, 4)

        row4.addWidget(ie_widget, stretch=55)

        self.history_chart = ValueHistoryChart()
        self.history_chart.setMinimumHeight(350)
        row4.addWidget(self.history_chart, stretch=45)

        layout.addLayout(row4)
        self._add_separator(layout)

        # ============ ROW 5: LIABILITY BREAKDOWN ============
        liabilities_title = QLabel("Liability Breakdown")
        liabilities_title.setFont(section_font)
        layout.addWidget(liabilities_title)

        liability_row = QHBoxLayout()
        liability_row.setSpacing(8)

        self.liability_count_card = SummaryCard("Liabilities", compact=True)
        liability_row.addWidget(self.liability_count_card)

        self.total_original_card = SummaryCard("Original Amount", compact=True)
        liability_row.addWidget(self.total_original_card)

        self.total_paid_card = SummaryCard("Total Paid Off", compact=True)
        liability_row.addWidget(self.total_paid_card)

        liability_row.addStretch()
        layout.addLayout(liability_row)
        self._add_separator(layout)

        # ============ ROW 6: SPENDING BREAKDOWN ============
        self.spending_title = QLabel("Spending Breakdown")
        self.spending_title.setFont(section_font)
        self.spending_title.setVisible(False)
        layout.addWidget(self.spending_title)

        self.spending_container = QWidget()
        spending_layout = QHBoxLayout(self.spending_container)
        spending_layout.setContentsMargins(0, 0, 0, 0)
        spending_layout.setSpacing(12)

        # Left: spending summary cards
        spending_cards_widget = QWidget()
        self.spending_grid = QGridLayout(spending_cards_widget)
        self.spending_grid.setSpacing(8)

        self.total_spending_card = SummaryCard("Total Spending", compact=True)
        self.spending_grid.addWidget(self.total_spending_card, 0, 0)

        self.txn_count_card = SummaryCard("Transactions", compact=True)
        self.spending_grid.addWidget(self.txn_count_card, 0, 1)

        self.avg_txn_card = SummaryCard("Avg Transaction", compact=True)
        self.spending_grid.addWidget(self.avg_txn_card, 0, 2)

        self.total_income_txn_card = SummaryCard("Total Deposits", compact=True)
        self.spending_grid.addWidget(self.total_income_txn_card, 0, 3)

        # Category spending cards (dynamic, up to 8)
        self._spending_cat_cards = []
        for i in range(8):
            card = SummaryCard("", compact=True)
            card.setVisible(False)
            row_pos = 1 + i // 4
            col_pos = i % 4
            self.spending_grid.addWidget(card, row_pos, col_pos)
            self._spending_cat_cards.append(card)

        spending_layout.addWidget(spending_cards_widget, stretch=55)

        # Right: spending pie chart
        self.spending_chart = SpendingCategoryChart()
        self.spending_chart.setMinimumHeight(350)
        spending_layout.addWidget(self.spending_chart, stretch=45)

        self.spending_container.setVisible(False)
        layout.addWidget(self.spending_container)
        self._add_separator(layout)

        # ============ ROW 7: SPOT PRICES (collapsible) ============
        p = theme().palette
        self.spot_toggle = QPushButton("Spot Prices (10yr)")
        self.spot_toggle.setCheckable(True)
        self.spot_toggle.setChecked(False)
        self.spot_toggle.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 8px 12px;
                font-weight: bold;
                font-size: {Typography.H2_SIZE}px;
                border: 1px solid {p.border};
                border-radius: 4px;
                background: {p.surface_alt};
            }}
            QPushButton:hover {{
                background: {p.accent_bg};
            }}
            QPushButton:checked {{
                border-color: {p.accent};
            }}
        """)
        self.spot_toggle.toggled.connect(self._toggle_spot_prices)
        layout.addWidget(self.spot_toggle)

        self.spot_container = QWidget()
        spot_layout = QVBoxLayout(self.spot_container)
        spot_layout.setContentsMargins(0, 0, 0, 0)
        self.spot_price_chart = SpotPriceHistoryChart()
        spot_layout.addWidget(self.spot_price_chart)
        self.spot_container.setVisible(False)
        layout.addWidget(self.spot_container)

        self._add_separator(layout)

        # ============ ROW 7: GOAL TRACKING ============
        self.goals_title = QLabel("Goal Tracking")
        self.goals_title.setFont(section_font)
        self.goals_title.setVisible(False)
        layout.addWidget(self.goals_title)

        self.goals_container = QVBoxLayout()
        self.goals_container.setSpacing(8)
        layout.addLayout(self.goals_container)

        self.add_goal_btn = QPushButton("+ Add Goal")
        self.add_goal_btn.setStyleSheet(
            f"QPushButton {{ color: {p.accent}; border: 1px dashed {p.accent}; "
            f"padding: 8px; background: transparent; }} "
            f"QPushButton:hover {{ background: {p.accent_bg}; }}"
        )
        self.add_goal_btn.clicked.connect(self.goal_add_requested.emit)
        layout.addWidget(self.add_goal_btn)

        layout.addStretch()
        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _add_separator(self, layout):
        """Add a horizontal separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

    def _toggle_spot_prices(self, checked):
        """Toggle spot prices section visibility."""
        self.spot_container.setVisible(checked)
        arrow = "v" if checked else ">"
        self.spot_toggle.setText(f"{arrow}  Spot Prices (10yr)")

    # ---- Public API ----

    def update_dashboard(self, combined_summary: Dict[str, Any],
                         asset_summary: Dict[str, Any],
                         assets: List[Any],
                         history: List[Dict[str, Any]]):
        """Update all metric cards and charts."""
        self._update_metrics(combined_summary)
        self.allocation_chart.update_chart(asset_summary.get('by_type', {}))
        self.performance_chart.update_chart(assets)
        self.history_chart.update_chart(history)

    def update_spending(self, spending_summary: Dict[str, Any]):
        """Update spending breakdown section from transaction data."""
        p = theme().palette

        # Extract deposits before checking emptiness
        total_deposits = spending_summary.pop('__deposits__', {})

        if not spending_summary:
            self.spending_title.setVisible(False)
            self.spending_container.setVisible(False)
            return

        self.spending_title.setVisible(True)
        self.spending_container.setVisible(True)

        # Calculate spending totals (all values are negative)
        total_spending = sum(d['total'] for d in spending_summary.values())
        total_count = sum(d['count'] for d in spending_summary.values())
        avg_txn = total_spending / total_count if total_count else 0

        self.total_spending_card.set_value(f"${abs(total_spending):,.2f}", p.negative)
        self.txn_count_card.set_value(str(total_count))
        self.avg_txn_card.set_value(f"${abs(avg_txn):,.2f}", p.negative)

        # Total deposits (income from transactions)
        if total_deposits:
            self.total_income_txn_card.set_value(
                f"${total_deposits.get('total', 0):,.2f}", p.positive
            )
        else:
            self.total_income_txn_card.set_value("$0.00")

        # Top category cards (sorted by most spending)
        sorted_cats = sorted(spending_summary.items(), key=lambda x: x[1]['total'])

        for i, card in enumerate(self._spending_cat_cards):
            if i < len(sorted_cats):
                cat, data = sorted_cats[i]
                card.title_label.setText(cat.title())
                card.set_value(f"${abs(data['total']):,.2f}", p.negative)
                card.setVisible(True)
            else:
                card.setVisible(False)

        # Update spending pie chart
        self.spending_chart.update_chart(spending_summary)

    def update_goals(self, goals: list):
        """Update the goals section with current goal data."""
        while self.goals_container.count():
            item = self.goals_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_goals = len(goals) > 0
        self.goals_title.setVisible(has_goals)

        for goal in goals:
            card = GoalCard(goal)
            card.edit_clicked.connect(self.goal_edit_requested.emit)
            card.delete_clicked.connect(self.goal_delete_requested.emit)
            self.goals_container.addWidget(card)

    def apply_theme(self):
        """Re-apply theme to all chart canvases."""
        self.allocation_chart.canvas.apply_theme()
        self.performance_chart.canvas.apply_theme()
        self.history_chart.canvas.apply_theme()
        self.spot_price_chart.canvas.apply_theme()
        self.spending_chart.canvas.apply_theme()

    def refresh_spot_prices(self):
        """Trigger a refresh of spot price history."""
        self.spot_price_chart.fetch_data()

    # ---- Metrics update (transplanted from SummaryPanel.update_summary) ----

    def _update_metrics(self, summary: Dict[str, Any]):
        """Update all metric cards from the combined summary dict."""
        p = theme().palette

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

        total_outflow = monthly_payments + monthly_expenses
        net_monthly = monthly_income - total_outflow
        savings_rate = (net_monthly / monthly_income * 100) if monthly_income > 0 else 0

        # ---- Hero row ----
        nw_color = p.positive if net_worth >= 0 else p.negative
        self.net_worth_card.set_value(f"${net_worth:,.2f}", nw_color)
        self.net_worth_card.set_background_tint(nw_color, alpha=15)

        nw_history = summary.get('net_worth_history', [])
        if nw_history:
            self.net_worth_card.set_sparkline_data(nw_history, nw_color)

        net_color = p.positive if net_monthly >= 0 else p.negative
        self.net_monthly_card.set_value(f"${net_monthly:+,.2f}", net_color)
        self.net_monthly_card.set_background_tint(net_color, alpha=15)

        savings_color = p.positive if savings_rate >= 20 else (p.warning if savings_rate >= 10 else p.negative)
        self.savings_rate_card.set_progress(
            value=savings_rate, label=f"{savings_rate:.1f}%",
            color=savings_color, detail="Target: 20%"
        )

        total_original = liability_summary.get('total_original', 0)
        total_paid = liability_summary.get('total_paid', 0)
        if total_original > 0:
            debt_pct = (total_paid / total_original) * 100
            self.debt_payoff_card.set_progress(
                value=debt_pct, label=f"{debt_pct:.1f}%",
                color=p.positive,
                detail=f"${total_paid:,.0f} of ${total_original:,.0f} paid"
            )
        else:
            self.debt_payoff_card.set_progress(
                value=100, label="Debt Free",
                color=p.positive, detail="No liabilities"
            )

        # ---- Financial overview ----
        self.total_assets_value_card.set_value(f"${total_value:,.2f}", p.positive)
        self.total_assets_value_card.set_background_tint(p.positive, alpha=10)

        self.total_liabilities_card.set_value(f"${total_liabilities:,.2f}", p.negative if total_liabilities > 0 else None)
        if total_liabilities > 0:
            self.total_liabilities_card.set_background_tint(p.negative, alpha=10)
        else:
            self.total_liabilities_card.clear_background_tint()

        gain_loss = summary.get('total_gain_loss', 0)
        gl_color = p.positive if gain_loss >= 0 else p.negative
        self.gain_loss_card.set_value(f"${gain_loss:+,.2f}", gl_color)
        self.gain_loss_card.set_background_tint(gl_color, alpha=12)

        gain_loss_pct = summary.get('gain_loss_percent', 0)
        self.gain_loss_pct_card.set_value(f"{gain_loss_pct:+.2f}%", gl_color)

        # ---- Income & Expenses ----
        self.monthly_income_card.set_value(f"${monthly_income:,.2f}", p.positive if monthly_income > 0 else None)
        self.monthly_expenses_card.set_value(f"${monthly_expenses:,.2f}", p.negative if monthly_expenses > 0 else None)
        self.monthly_payments_card.set_value(f"${monthly_payments:,.2f}", p.negative if monthly_payments > 0 else None)
        self.total_outflow_card.set_value(f"${total_outflow:,.2f}", p.negative if total_outflow > 0 else None)

        annual_savings = net_monthly * 12
        self.annual_savings_card.set_value(f"${annual_savings:+,.2f}", net_color)

        self.essential_expenses_card.set_value(f"${essential_monthly:,.2f}", p.accent if essential_monthly > 0 else None)
        self.discretionary_expenses_card.set_value(f"${discretionary_monthly:,.2f}", p.muted if discretionary_monthly > 0 else None)

        active_sources = income_summary.get('active_sources', 0)
        self.income_count_card.set_value(str(active_sources))

        active_expenses = expense_summary.get('active_expenses', 0)
        self.expense_count_card.set_value(str(active_expenses))

        self.annual_income_card.set_value(f"${annual_income:,.2f}", p.positive if annual_income > 0 else None)

        # ---- Asset breakdown ----
        total_cost = summary.get('total_cost', 0)
        self.total_cost_card.set_value(f"${total_cost:,.2f}")

        asset_count = summary.get('total_assets', 0)
        self.asset_count_card.set_value(str(asset_count))

        by_type = summary.get('by_type', {})

        self.metals_card.set_value(f"${by_type.get('metal', {}).get('current_value', 0):,.2f}")
        self.stocks_card.set_value(f"${by_type.get('stock', {}).get('current_value', 0):,.2f}")
        self.retirement_card.set_value(f"${by_type.get('retirement', {}).get('current_value', 0):,.2f}")
        self.other_card.set_value(f"${by_type.get('other', {}).get('current_value', 0):,.2f}")
        self.realestate_card.set_value(f"${by_type.get('realestate', {}).get('current_value', 0):,.2f}")
        self.cash_card.set_value(f"${by_type.get('cash', {}).get('current_value', 0):,.2f}")

        metal_ounces = summary.get('metal_ounces', {})
        gold_oz = metal_ounces.get('GOLD', 0)
        silver_oz = metal_ounces.get('SILVER', 0)
        platinum_oz = metal_ounces.get('PLATINUM', 0)
        palladium_oz = metal_ounces.get('PALLADIUM', 0)

        self.gold_oz_card.set_value(f"{gold_oz:,.2f}" if gold_oz else "0")
        self.silver_oz_card.set_value(f"{silver_oz:,.2f}" if silver_oz else "0")
        self.platinum_oz_card.set_value(f"{platinum_oz:,.2f}" if platinum_oz else "0")
        self.palladium_oz_card.set_value(f"{palladium_oz:,.2f}" if palladium_oz else "0")

        # ---- Liability breakdown ----
        liability_count = liability_summary.get('total_liabilities', 0)
        self.liability_count_card.set_value(str(liability_count))

        self.total_original_card.set_value(f"${total_original:,.2f}")
        self.total_paid_card.set_value(f"${total_paid:,.2f}", p.positive if total_paid > 0 else None)
