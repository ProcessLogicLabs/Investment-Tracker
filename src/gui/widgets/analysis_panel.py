"""Financial analysis panel for net worth optimization recommendations."""

from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QGroupBox,
    QFrame, QGridLayout, QDoubleSpinBox, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush


class AnalysisWorker(QThread):
    """Worker thread for running financial analysis."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, extra_monthly: float = 0):
        super().__init__()
        self.extra_monthly = extra_monthly

    def run(self):
        try:
            from ...services.financial_advisor import FinancialAdvisor
            advisor = FinancialAdvisor()

            result = {
                'net_worth_summary': advisor.get_net_worth_summary(),
                'cash_flow': advisor.get_monthly_cash_flow_analysis(),
                'recommendations': advisor.get_recommendations(self.extra_monthly),
                'debt_strategies': advisor.compare_payoff_strategies(self.extra_monthly),
                'acceleration': advisor.get_payoff_acceleration_analysis(self.extra_monthly) if self.extra_monthly > 0 else None,
                'projections': advisor.project_net_worth(60)
            }

            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class RecommendationCard(QFrame):
    """Card displaying a single recommendation."""

    def __init__(self, recommendation, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        # Priority and category
        header = QHBoxLayout()
        priority_label = QLabel(f"Priority {recommendation.priority}")
        priority_label.setStyleSheet("color: #fff; background-color: #1976D2; padding: 2px 8px; border-radius: 3px; font-size: 11px;")
        header.addWidget(priority_label)

        category_label = QLabel(recommendation.category.upper())
        cat_color = {
            'debt': '#c62828',
            'savings': '#2e7d32',
            'investment': '#1565c0',
            'emergency': '#ff8f00'
        }.get(recommendation.category, '#666')
        category_label.setStyleSheet(f"color: {cat_color}; font-weight: bold; font-size: 11px;")
        header.addWidget(category_label)
        header.addStretch()

        if recommendation.potential_savings > 0:
            savings_label = QLabel(f"Potential savings: ${recommendation.potential_savings:,.0f}")
            savings_label.setStyleSheet("color: #2e7d32; font-weight: bold;")
            header.addWidget(savings_label)

        layout.addLayout(header)

        # Title
        title = QLabel(recommendation.title)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setWordWrap(True)
        layout.addWidget(title)

        # Description
        desc = QLabel(recommendation.description)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #444; margin: 5px 0;")
        layout.addWidget(desc)

        # Action items
        if recommendation.action_items:
            actions_label = QLabel("Action Items:")
            actions_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
            layout.addWidget(actions_label)

            for action in recommendation.action_items:
                action_item = QLabel(f"  • {action}")
                action_item.setWordWrap(True)
                action_item.setStyleSheet("color: #555;")
                layout.addWidget(action_item)


class DebtStrategyTable(QWidget):
    """Table comparing debt payoff strategies."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            'Strategy', 'Months to Payoff', 'Total Interest', 'Total Paid', 'Interest Saved'
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.table)

    def update_data(self, strategies: Dict[str, Any], baseline_interest: float = 0):
        """Update the table with strategy data."""
        self.table.setRowCount(len(strategies))

        row = 0
        for name, strategy in strategies.items():
            display_name = {
                'avalanche': 'Debt Avalanche (Highest Rate First)',
                'snowball': 'Debt Snowball (Smallest Balance First)',
                'minimum': 'Minimum Payments Only'
            }.get(name, name)

            self.table.setItem(row, 0, QTableWidgetItem(display_name))

            months_item = QTableWidgetItem(f"{strategy.total_months} months")
            months_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 1, months_item)

            interest_item = QTableWidgetItem(f"${strategy.total_interest:,.2f}")
            interest_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, interest_item)

            total_item = QTableWidgetItem(f"${strategy.total_paid:,.2f}")
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, total_item)

            # Interest saved vs minimum
            if baseline_interest > 0:
                saved = baseline_interest - strategy.total_interest
                saved_item = QTableWidgetItem(f"${saved:,.2f}")
                saved_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if saved > 0:
                    saved_item.setForeground(QBrush(QColor('#2e7d32')))
                self.table.setItem(row, 4, saved_item)
            else:
                self.table.setItem(row, 4, QTableWidgetItem("—"))

            row += 1


class SummaryCard(QFrame):
    """Simple summary card with title and value."""

    def __init__(self, title: str, value: str = "$0.00", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        font = QFont()
        font.setPointSize(16)
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


class AnalysisPanel(QWidget):
    """Main analysis panel with recommendations and projections."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.analysis_data = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Controls row
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Extra Monthly Payment:"))

        self.extra_payment_spin = QDoubleSpinBox()
        self.extra_payment_spin.setRange(0, 10000)
        self.extra_payment_spin.setDecimals(2)
        self.extra_payment_spin.setPrefix("$")
        self.extra_payment_spin.setValue(0)
        self.extra_payment_spin.setToolTip("Additional amount to apply to debt payoff each month")
        controls.addWidget(self.extra_payment_spin)

        self.analyze_btn = QPushButton("Run Analysis")
        self.analyze_btn.clicked.connect(self.run_analysis)
        controls.addWidget(self.analyze_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        controls.addWidget(self.status_label)

        controls.addStretch()
        layout.addLayout(controls)

        # Tab widget for different analysis views
        self.tabs = QTabWidget()

        # Tab 1: Overview
        overview_scroll = QScrollArea()
        overview_scroll.setWidgetResizable(True)
        overview_widget = QWidget()
        self.overview_layout = QVBoxLayout(overview_widget)
        self.overview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        overview_scroll.setWidget(overview_widget)
        self.tabs.addTab(overview_scroll, "Overview")

        # Summary cards
        self.summary_cards_widget = QWidget()
        summary_grid = QGridLayout(self.summary_cards_widget)
        summary_grid.setSpacing(10)

        self.net_worth_card = SummaryCard("Net Worth")
        summary_grid.addWidget(self.net_worth_card, 0, 0)

        self.monthly_interest_card = SummaryCard("Monthly Interest Paid")
        summary_grid.addWidget(self.monthly_interest_card, 0, 1)

        self.future_interest_card = SummaryCard("Future Interest (All Debts)")
        summary_grid.addWidget(self.future_interest_card, 0, 2)

        self.debt_free_card = SummaryCard("Debt-Free In")
        summary_grid.addWidget(self.debt_free_card, 0, 3)

        self.overview_layout.addWidget(self.summary_cards_widget)

        # Recommendations section
        self.recommendations_group = QGroupBox("Recommendations")
        self.recommendations_layout = QVBoxLayout(self.recommendations_group)
        self.overview_layout.addWidget(self.recommendations_group)

        # Tab 2: Debt Payoff Strategies
        strategies_widget = QWidget()
        strategies_layout = QVBoxLayout(strategies_widget)

        strategies_layout.addWidget(QLabel("Compare different debt payoff strategies:"))

        self.strategy_table = DebtStrategyTable()
        strategies_layout.addWidget(self.strategy_table)

        # Acceleration impact
        self.acceleration_group = QGroupBox("Impact of Extra Payments")
        accel_layout = QGridLayout(self.acceleration_group)

        self.accel_months_label = QLabel("Months saved: —")
        accel_layout.addWidget(self.accel_months_label, 0, 0)

        self.accel_interest_label = QLabel("Interest saved: —")
        accel_layout.addWidget(self.accel_interest_label, 0, 1)

        self.accel_payoff_label = QLabel("New payoff date: —")
        accel_layout.addWidget(self.accel_payoff_label, 0, 2)

        strategies_layout.addWidget(self.acceleration_group)

        # Debt payoff order
        self.payoff_order_group = QGroupBox("Recommended Payoff Order (Avalanche Method)")
        self.payoff_order_layout = QVBoxLayout(self.payoff_order_group)
        strategies_layout.addWidget(self.payoff_order_group)

        self.tabs.addTab(strategies_widget, "Debt Strategies")

        # Tab 3: Cash Flow
        cashflow_widget = QWidget()
        cashflow_layout = QVBoxLayout(cashflow_widget)

        self.cashflow_text = QTextEdit()
        self.cashflow_text.setReadOnly(True)
        cashflow_layout.addWidget(self.cashflow_text)

        self.tabs.addTab(cashflow_widget, "Cash Flow")

        layout.addWidget(self.tabs)

    def run_analysis(self):
        """Run financial analysis in background thread."""
        self.status_label.setText("Analyzing...")
        self.analyze_btn.setEnabled(False)

        extra = self.extra_payment_spin.value()
        self.worker = AnalysisWorker(extra)
        self.worker.finished.connect(self._on_analysis_complete)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _on_analysis_complete(self, data: dict):
        """Handle completed analysis."""
        self.analysis_data = data
        self.analyze_btn.setEnabled(True)
        self.status_label.setText("Analysis complete")
        self._update_display()

    def _on_analysis_error(self, error: str):
        """Handle analysis error."""
        self.analyze_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error}")

    def _update_display(self):
        """Update all display elements with analysis data."""
        if not self.analysis_data:
            return

        # Update summary cards
        summary = self.analysis_data.get('net_worth_summary', {})
        net_worth = summary.get('net_worth', 0)
        nw_color = '#2e7d32' if net_worth >= 0 else '#c62828'
        self.net_worth_card.set_value(f"${net_worth:,.2f}", nw_color)

        cash_flow = self.analysis_data.get('cash_flow', {})
        interest = cash_flow.get('interest_portion', 0)
        self.monthly_interest_card.set_value(f"${interest:,.2f}", '#c62828' if interest > 0 else None)

        future_interest = summary.get('total_future_interest', 0)
        if future_interest == float('inf'):
            self.future_interest_card.set_value("Cannot pay off", '#c62828')
        else:
            self.future_interest_card.set_value(f"${future_interest:,.2f}", '#c62828' if future_interest > 0 else None)

        # Debt-free timeline
        strategies = self.analysis_data.get('debt_strategies', {})
        avalanche = strategies.get('avalanche')
        if avalanche and avalanche.total_months > 0:
            years = avalanche.total_months // 12
            months = avalanche.total_months % 12
            if years > 0:
                self.debt_free_card.set_value(f"{years}y {months}m")
            else:
                self.debt_free_card.set_value(f"{months} months")
        else:
            self.debt_free_card.set_value("Debt-free!", '#2e7d32')

        # Update recommendations
        self._update_recommendations()

        # Update strategy table
        minimum = strategies.get('minimum')
        baseline_interest = minimum.total_interest if minimum else 0
        self.strategy_table.update_data(strategies, baseline_interest)

        # Update acceleration info
        accel = self.analysis_data.get('acceleration')
        if accel:
            self.accel_months_label.setText(f"Months saved: {accel.get('months_saved', 0)}")
            self.accel_interest_label.setText(f"Interest saved: ${accel.get('interest_saved', 0):,.2f}")
            if accel.get('accelerated_payoff_date'):
                self.accel_payoff_label.setText(f"New payoff date: {accel['accelerated_payoff_date']}")

        # Update payoff order
        self._update_payoff_order()

        # Update cash flow
        self._update_cashflow()

    def _update_recommendations(self):
        """Update recommendations display."""
        # Clear existing
        while self.recommendations_layout.count():
            item = self.recommendations_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        recommendations = self.analysis_data.get('recommendations', [])

        if not recommendations:
            label = QLabel("No recommendations available. Add assets and liabilities to get personalized advice.")
            label.setStyleSheet("color: #666; font-style: italic;")
            self.recommendations_layout.addWidget(label)
        else:
            for rec in recommendations:
                card = RecommendationCard(rec)
                self.recommendations_layout.addWidget(card)

    def _update_payoff_order(self):
        """Update payoff order display."""
        # Clear existing
        while self.payoff_order_layout.count():
            item = self.payoff_order_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        strategies = self.analysis_data.get('debt_strategies', {})
        avalanche = strategies.get('avalanche')

        if avalanche and avalanche.payoff_order:
            for i, debt_name in enumerate(avalanche.payoff_order, 1):
                label = QLabel(f"{i}. {debt_name}")
                label.setStyleSheet("font-size: 12px; margin: 3px 0;")
                self.payoff_order_layout.addWidget(label)
        else:
            label = QLabel("No debts to pay off or add liabilities to see payoff order.")
            label.setStyleSheet("color: #666; font-style: italic;")
            self.payoff_order_layout.addWidget(label)

    def _update_cashflow(self):
        """Update cash flow analysis display."""
        cash_flow = self.analysis_data.get('cash_flow', {})
        summary = self.analysis_data.get('net_worth_summary', {})

        text = []
        text.append("=" * 50)
        text.append("MONTHLY CASH FLOW ANALYSIS")
        text.append("=" * 50)
        text.append("")

        text.append("DEBT PAYMENTS:")
        text.append(f"  Total Monthly Payments:  ${cash_flow.get('total_debt_payments', 0):>12,.2f}")
        text.append(f"    └─ Interest Portion:   ${cash_flow.get('interest_portion', 0):>12,.2f}")
        text.append(f"    └─ Principal Portion:  ${cash_flow.get('principal_portion', 0):>12,.2f}")
        text.append("")

        interest_pct = cash_flow.get('interest_percentage', 0)
        text.append(f"  Interest as % of Payment: {interest_pct:>11.1f}%")
        text.append("")

        text.append("RETIREMENT CONTRIBUTIONS:")
        text.append(f"  Monthly Contributions:   ${cash_flow.get('retirement_contributions', 0):>12,.2f}")
        text.append("")

        text.append("TOTAL COMMITTED MONTHLY:")
        text.append(f"  Debt + Retirement:       ${cash_flow.get('total_committed', 0):>12,.2f}")
        text.append("")

        text.append("=" * 50)
        text.append("NET WORTH BREAKDOWN")
        text.append("=" * 50)
        text.append("")

        text.append("ASSETS:")
        for asset_type, data in summary.get('assets_by_type', {}).items():
            type_name = {
                'metal': 'Precious Metals',
                'stock': 'Securities',
                'realestate': 'Real Estate',
                'retirement': 'Retirement',
                'cash': 'Cash/Savings',
                'other': 'Other'
            }.get(asset_type, asset_type)
            text.append(f"  {type_name:20s}  ${data['value']:>12,.2f}  ({data['count']} items)")

        text.append(f"  {'─' * 40}")
        text.append(f"  {'Total Assets':20s}  ${summary.get('total_assets', 0):>12,.2f}")
        text.append("")

        text.append("LIABILITIES:")
        for liab_type, data in summary.get('liabilities_by_type', {}).items():
            type_name = {
                'mortgage': 'Mortgage',
                'auto': 'Auto Loan',
                'student': 'Student Loan',
                'credit': 'Credit Card',
                'personal': 'Personal Loan',
                'other': 'Other'
            }.get(liab_type, liab_type)
            text.append(f"  {type_name:20s}  ${data['balance']:>12,.2f}  ({data['count']} items)")

        text.append(f"  {'─' * 40}")
        text.append(f"  {'Total Liabilities':20s}  ${summary.get('total_liabilities', 0):>12,.2f}")
        text.append("")

        text.append("=" * 50)
        net_worth = summary.get('net_worth', 0)
        text.append(f"NET WORTH:                   ${net_worth:>12,.2f}")
        text.append("=" * 50)

        self.cashflow_text.setPlainText("\n".join(text))

    def refresh(self):
        """Refresh analysis with current data."""
        self.run_analysis()
