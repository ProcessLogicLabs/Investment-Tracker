"""Summary panel widget for portfolio overview."""

import json
from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QScrollArea, QProgressBar, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from ..theme import theme, Typography, make_shadow


class SummaryCard(QFrame):
    """A card widget displaying a summary metric."""

    def __init__(self, title: str, value: str = "$0.00", compact: bool = False,
                 show_sparkline: bool = False, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)

        layout = QVBoxLayout(self)
        if compact:
            layout.setContentsMargins(10, 6, 10, 6)
        else:
            layout.setContentsMargins(15, 10, 15, 10)

        self.setGraphicsEffect(make_shadow(self))

        # Title row (title + optional sparkline)
        p = theme().palette
        top_row = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {p.text_secondary}; font-size: {Typography.BODY_SIZE}px; background: transparent;")
        top_row.addWidget(self.title_label)

        self.sparkline = None
        if show_sparkline:
            from .sparkline import SparklineWidget
            self.sparkline = SparklineWidget(self, width=120, height=40)
            top_row.addStretch()
            top_row.addWidget(self.sparkline)

        layout.addLayout(top_row)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("background: transparent;")
        font = QFont()
        font.setPointSize(Typography.H2_SIZE if compact else 16)
        font.setBold(True)
        self.value_label.setFont(font)
        layout.addWidget(self.value_label)

    def set_value(self, value: str, color: str = None):
        """Update the displayed value."""
        self.value_label.setText(value)
        if color:
            self.value_label.setStyleSheet(f"color: {color}; background: transparent;")
        else:
            self.value_label.setStyleSheet("background: transparent;")

    def set_background_tint(self, color: str, alpha: int = 20):
        """Set a subtle background tint on the card."""
        qcolor = QColor(color)
        qcolor.setAlpha(alpha)
        r, g, b, a = qcolor.red(), qcolor.green(), qcolor.blue(), qcolor.alpha()
        self.setStyleSheet(f"SummaryCard {{ background-color: rgba({r}, {g}, {b}, {a}); }}")

    def clear_background_tint(self):
        """Remove background tint."""
        self.setStyleSheet("")

    def set_sparkline_data(self, data: list, color: str = None):
        """Update sparkline data if sparkline exists."""
        if self.sparkline:
            self.sparkline.set_data(data, color)


class ProgressCard(QFrame):
    """A card widget with a progress bar for rate/completion metrics."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setGraphicsEffect(make_shadow(self))

        p = theme().palette
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {p.text_secondary}; font-size: {Typography.BODY_SIZE}px;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel("0%")
        font = QFont()
        font.setPointSize(Typography.H2_SIZE)
        font.setBold(True)
        self.value_label.setFont(font)
        layout.addWidget(self.value_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet(f"color: {p.text_disabled}; font-size: {Typography.CAPTION_SIZE + 1}px;")
        layout.addWidget(self.detail_label)

    def set_progress(self, value: float, label: str, color: str = None,
                     detail: str = ""):
        """Update the progress display."""
        if color is None:
            color = theme().palette.accent
        self.value_label.setText(label)
        self.value_label.setStyleSheet(f"color: {color};")
        self.progress_bar.setValue(int(min(100, max(0, value))))
        self.progress_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; }}"
        )
        self.detail_label.setText(detail)


class GoalCard(QFrame):
    """Card displaying a financial goal with progress bar and milestone dots."""
    edit_clicked = pyqtSignal(int)
    delete_clicked = pyqtSignal(int)

    TYPE_LABELS = {
        'savings': 'Savings',
        'debt_payoff': 'Debt Payoff',
        'net_worth': 'Net Worth',
        'asset_acquisition': 'Acquisition'
    }

    @staticmethod
    def _type_color(goal_type: str) -> str:
        p = theme().palette
        return {
            'savings': p.positive,
            'debt_payoff': p.negative,
            'net_worth': p.accent,
            'asset_acquisition': p.warning
        }.get(goal_type, p.muted)

    def __init__(self, goal, parent=None):
        super().__init__(parent)
        self.goal = goal
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setGraphicsEffect(make_shadow(self))

        p = theme().palette
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        badge_color = self._type_color(goal.goal_type)

        # Header row
        header = QHBoxLayout()
        name_label = QLabel(goal.name)
        name_font = QFont()
        name_font.setPointSize(Typography.H2_SIZE - 2)
        name_font.setBold(True)
        name_label.setFont(name_font)
        header.addWidget(name_label)

        badge = QLabel(self.TYPE_LABELS.get(goal.goal_type, goal.goal_type))
        badge.setStyleSheet(
            f"color: {p.text_on_primary}; background-color: {badge_color}; "
            f"padding: 2px 8px; border-radius: 3px; font-size: {Typography.CAPTION_SIZE + 1}px;"
        )
        header.addWidget(badge)

        header.addStretch()

        # On-track indicator
        on_track = goal.is_on_track
        if on_track is True:
            status = QLabel("On Track")
            status.setStyleSheet(f"color: {p.positive}; font-size: {Typography.CAPTION_SIZE + 1}px; font-weight: bold;")
            header.addWidget(status)
        elif on_track is False:
            status = QLabel("Behind")
            status.setStyleSheet(f"color: {p.negative}; font-size: {Typography.CAPTION_SIZE + 1}px; font-weight: bold;")
            header.addWidget(status)

        edit_btn = QPushButton("Edit")
        edit_btn.setFlat(True)
        edit_btn.setStyleSheet(f"color: {p.accent}; font-size: {Typography.CAPTION_SIZE + 1}px;")
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(goal.id))
        header.addWidget(edit_btn)

        delete_btn = QPushButton("Del")
        delete_btn.setFlat(True)
        delete_btn.setStyleSheet(f"color: {p.negative}; font-size: {Typography.CAPTION_SIZE + 1}px;")
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(goal.id))
        header.addWidget(delete_btn)

        layout.addLayout(header)

        # Progress row
        progress_row = QHBoxLayout()

        if goal.goal_type == 'debt_payoff':
            current_label = QLabel(f"${goal.current_amount:,.0f} remaining")
        else:
            current_label = QLabel(f"${goal.current_amount:,.0f}")
        current_label.setStyleSheet("font-weight: bold;")
        progress_row.addWidget(current_label)

        progress_bar = QProgressBar()
        progress_bar.setMaximumHeight(12)
        progress_bar.setTextVisible(False)
        progress_bar.setRange(0, 100)
        progress_bar.setValue(int(goal.progress_percent))
        progress_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {badge_color}; }}"
        )
        progress_row.addWidget(progress_bar, stretch=1)

        target_label = QLabel(f"${goal.target_amount:,.0f}")
        target_label.setStyleSheet(f"color: {p.text_secondary};")
        progress_row.addWidget(target_label)

        pct_label = QLabel(f"{goal.progress_percent:.0f}%")
        pct_label.setStyleSheet(f"color: {badge_color}; font-weight: bold;")
        progress_row.addWidget(pct_label)

        layout.addLayout(progress_row)

        # Milestone dots
        milestones = self._parse_milestones(goal.milestones)
        if milestones:
            milestone_row = QHBoxLayout()
            milestone_row.setSpacing(4)
            for ms in milestones:
                dot_color = p.positive if ms.get('reached') else p.text_disabled
                dot_char = 'o' if ms.get('reached') else 'o'
                dot = QLabel(f"  {dot_char} {ms.get('label', '')}")
                dot.setStyleSheet(f"color: {dot_color}; font-size: {Typography.CAPTION_SIZE}px;")
                milestone_row.addWidget(dot)
            milestone_row.addStretch()
            layout.addLayout(milestone_row)

        # Target date
        if goal.target_date:
            date_label = QLabel(f"Target: {goal.target_date}")
            date_label.setStyleSheet(f"color: {p.text_disabled}; font-size: {Typography.CAPTION_SIZE + 1}px;")
            layout.addWidget(date_label)

    @staticmethod
    def _parse_milestones(milestones_json: str) -> list:
        try:
            return json.loads(milestones_json) if milestones_json else []
        except (json.JSONDecodeError, TypeError):
            return []


class SummaryPanel(QWidget):
    """Panel displaying portfolio summary information."""
    goal_add_requested = pyqtSignal()
    goal_edit_requested = pyqtSignal(int)
    goal_delete_requested = pyqtSignal(int)

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
        section_font.setPointSize(Typography.H2_SIZE)
        section_font.setBold(True)

        # ============ QUICK GLANCE (Hero section) ============
        quick_title = QLabel("Quick Glance")
        quick_title.setFont(section_font)
        layout.addWidget(quick_title)

        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(12)

        # Net Worth - hero card with sparkline
        self.net_worth_card = SummaryCard("Net Worth", show_sparkline=True)
        quick_layout.addWidget(self.net_worth_card, stretch=2)

        # Net Monthly Cash Flow - hero card with sparkline
        self.net_monthly_card = SummaryCard("Net Monthly Cash Flow", show_sparkline=True)
        quick_layout.addWidget(self.net_monthly_card, stretch=2)

        # Savings Rate - progress card
        self.savings_rate_card = ProgressCard("Savings Rate")
        quick_layout.addWidget(self.savings_rate_card, stretch=1)

        # Debt Payoff Progress - progress card
        self.debt_payoff_card = ProgressCard("Debt Payoff")
        quick_layout.addWidget(self.debt_payoff_card, stretch=1)

        layout.addLayout(quick_layout)

        # Separator
        self._add_separator(layout)

        # ============ FINANCIAL OVERVIEW ============
        top_title = QLabel("Financial Overview")
        top_title.setFont(section_font)
        layout.addWidget(top_title)

        top_layout = QGridLayout()
        top_layout.setSpacing(8)

        self.total_assets_value_card = SummaryCard("Total Assets")
        top_layout.addWidget(self.total_assets_value_card, 0, 0)

        self.total_liabilities_card = SummaryCard("Total Liabilities")
        top_layout.addWidget(self.total_liabilities_card, 0, 1)

        self.gain_loss_card = SummaryCard("Gain/Loss")
        top_layout.addWidget(self.gain_loss_card, 0, 2)

        self.gain_loss_pct_card = SummaryCard("Return %")
        top_layout.addWidget(self.gain_loss_pct_card, 0, 3)

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

        self.asset_count_card = SummaryCard("Assets", compact=True)
        assets_layout.addWidget(self.asset_count_card, 0, 1)

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

        # Separator
        self._add_separator(layout)

        # ============ GOAL TRACKING ============
        self.goals_title = QLabel("Goal Tracking")
        self.goals_title.setFont(section_font)
        self.goals_title.setVisible(False)
        layout.addWidget(self.goals_title)

        self.goals_container = QVBoxLayout()
        self.goals_container.setSpacing(8)
        layout.addLayout(self.goals_container)

        p = theme().palette
        self.add_goal_btn = QPushButton("+ Add Goal")
        self.add_goal_btn.setStyleSheet(
            f"QPushButton {{ color: {p.accent}; border: 1px dashed {p.accent}; "
            f"padding: 8px; background: transparent; }} "
            f"QPushButton:hover {{ background: {p.accent_bg}; }}"
        )
        self.add_goal_btn.clicked.connect(self.goal_add_requested.emit)
        layout.addWidget(self.add_goal_btn)

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

        # ============ QUICK GLANCE ============
        p = theme().palette
        nw_color = p.positive if net_worth >= 0 else p.negative
        self.net_worth_card.set_value(f"${net_worth:,.2f}", nw_color)
        self.net_worth_card.set_background_tint(nw_color, alpha=15)

        # Sparkline data
        nw_history = summary.get('net_worth_history', [])
        if nw_history:
            self.net_worth_card.set_sparkline_data(nw_history, nw_color)

        net_color = p.positive if net_monthly >= 0 else p.negative
        self.net_monthly_card.set_value(f"${net_monthly:+,.2f}", net_color)
        self.net_monthly_card.set_background_tint(net_color, alpha=15)

        # Savings Rate progress
        savings_color = p.positive if savings_rate >= 20 else (p.warning if savings_rate >= 10 else p.negative)
        self.savings_rate_card.set_progress(
            value=savings_rate,
            label=f"{savings_rate:.1f}%",
            color=savings_color,
            detail="Target: 20%"
        )

        # Debt Payoff progress
        total_original = liability_summary.get('total_original', 0)
        total_paid = liability_summary.get('total_paid', 0)
        if total_original > 0:
            debt_pct = (total_paid / total_original) * 100
            self.debt_payoff_card.set_progress(
                value=debt_pct,
                label=f"{debt_pct:.1f}%",
                color=p.positive,
                detail=f"${total_paid:,.0f} of ${total_original:,.0f} paid"
            )
        else:
            self.debt_payoff_card.set_progress(
                value=100,
                label="Debt Free",
                color=p.positive,
                detail="No liabilities"
            )

        # ============ FINANCIAL OVERVIEW ============
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

        # ============ INCOME & EXPENSES ============
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

        # ============ ASSET BREAKDOWN ============
        total_cost = summary.get('total_cost', 0)
        self.total_cost_card.set_value(f"${total_cost:,.2f}")

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

        self.total_original_card.set_value(f"${total_original:,.2f}")

        self.total_paid_card.set_value(f"${total_paid:,.2f}", p.positive if total_paid > 0 else None)

    def update_goals(self, goals: list):
        """Update the goals section with current goal data."""
        # Clear existing goal cards
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
