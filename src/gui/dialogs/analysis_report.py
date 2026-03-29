"""Financial analysis report dialog."""

from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ...database.operations import AssetOperations, LiabilityOperations, IncomeOperations, ExpenseOperations, TransactionOperations


class AnalysisReportDialog(QDialog):
    """Dialog displaying comprehensive financial analysis report."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Financial Analysis Report")
        self.setMinimumSize(800, 600)
        self._setup_ui()
        self._generate_report()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Report text area
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        font = QFont("Courier New", 10)
        self.report_text.setFont(font)
        layout.addWidget(self.report_text)

        # Buttons
        button_layout = QHBoxLayout()

        export_btn = QPushButton("Export to File")
        export_btn.clicked.connect(self._export_report)
        button_layout.addWidget(export_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _format_currency(self, amount: float) -> str:
        """Format a currency amount."""
        return f"${amount:,.2f}"

    def _simulate_avalanche_payoff(self, liabilities: List, extra_monthly: float = 0) -> Dict[str, Any]:
        """Simulate debt avalanche payoff."""
        if not liabilities:
            return {'total_months': 0, 'total_interest': 0, 'payoff_order': []}

        debts = sorted([l for l in liabilities if l.current_balance > 0],
                       key=lambda x: x.interest_rate, reverse=True)

        balances = {d.id: d.current_balance for d in debts}
        payments = {d.id: d.monthly_payment for d in debts}
        rates = {d.id: d.monthly_interest_rate for d in debts}
        names = {d.id: d.name for d in debts}

        total_interest = 0
        month = 0
        extra = extra_monthly
        payoff_order = []

        while any(b > 0.01 for b in balances.values()) and month < 600:
            month += 1

            for d in debts:
                if balances[d.id] > 0:
                    interest = balances[d.id] * rates[d.id]
                    total_interest += interest
                    balances[d.id] += interest

            for d in debts:
                if balances[d.id] > 0:
                    pmt = min(payments[d.id], balances[d.id])
                    balances[d.id] -= pmt

            remaining_extra = extra
            for d in debts:
                if balances[d.id] > 0.01 and remaining_extra > 0:
                    apply = min(remaining_extra, balances[d.id])
                    balances[d.id] -= apply
                    remaining_extra -= apply

                    if balances[d.id] <= 0.01:
                        extra += payments[d.id]
                        if names[d.id] not in payoff_order:
                            payoff_order.append(names[d.id])
                    break

        return {
            'total_months': month,
            'total_interest': total_interest,
            'payoff_order': payoff_order
        }

    def _calculate_freed_cashflow_invested(self, lump_sum: float, debts: List,
                                            years: int = 10, investment_return: float = 0.07) -> float:
        """Calculate value of freed-up monthly payments invested over time.

        When debt is paid off early with a lump sum, the monthly payments are freed up
        and could be invested. This calculates the future value of those freed payments.
        """
        if not debts or lump_sum <= 0:
            return 0.0

        monthly_return = (1 + investment_return) ** (1/12) - 1
        total_months = years * 12
        max_sim_months = 600

        # Calculate payoff month for each debt WITHOUT lump sum (baseline)
        baseline_payoff_months = {}
        balances_baseline = {d.id: d.current_balance for d in debts}

        month = 0
        while any(b > 0.01 for b in balances_baseline.values()) and month < max_sim_months:
            month += 1
            for d in debts:
                if balances_baseline[d.id] > 0:
                    interest = balances_baseline[d.id] * d.monthly_interest_rate
                    balances_baseline[d.id] += interest
                    pmt = min(d.monthly_payment, balances_baseline[d.id])
                    balances_baseline[d.id] -= pmt
                    if balances_baseline[d.id] <= 0.01 and d.id not in baseline_payoff_months:
                        baseline_payoff_months[d.id] = month

        for d in debts:
            if d.id not in baseline_payoff_months:
                baseline_payoff_months[d.id] = max_sim_months

        # Calculate payoff month for each debt WITH lump sum (avalanche method)
        lumpsum_payoff_months = {}
        balances_payoff = {d.id: d.current_balance for d in debts}
        remaining_lump = lump_sum

        # Apply lump sum to debts in order of interest rate (highest first)
        sorted_debts = sorted(debts, key=lambda x: x.interest_rate, reverse=True)
        for d in sorted_debts:
            if remaining_lump <= 0:
                break
            payoff_amount = min(remaining_lump, balances_payoff[d.id])
            balances_payoff[d.id] -= payoff_amount
            remaining_lump -= payoff_amount
            if balances_payoff[d.id] <= 0.01:
                lumpsum_payoff_months[d.id] = 0

        # Simulate remaining payoff
        month = 0
        while any(b > 0.01 for b in balances_payoff.values()) and month < max_sim_months:
            month += 1
            for d in debts:
                if balances_payoff[d.id] > 0:
                    interest = balances_payoff[d.id] * d.monthly_interest_rate
                    balances_payoff[d.id] += interest
                    pmt = min(d.monthly_payment, balances_payoff[d.id])
                    balances_payoff[d.id] -= pmt
                    if balances_payoff[d.id] <= 0.01 and d.id not in lumpsum_payoff_months:
                        lumpsum_payoff_months[d.id] = month

        for d in debts:
            if d.id not in lumpsum_payoff_months:
                lumpsum_payoff_months[d.id] = max_sim_months

        # Calculate value of freed cashflow invested
        total_invested_value = 0.0

        for month in range(1, total_months + 1):
            freed_this_month = 0.0
            for d in debts:
                if lumpsum_payoff_months[d.id] < month <= baseline_payoff_months[d.id]:
                    freed_this_month += d.monthly_payment

            if freed_this_month > 0:
                months_to_grow = total_months - month
                future_value = freed_this_month * ((1 + monthly_return) ** months_to_grow)
                total_invested_value += future_value

        return total_invested_value

    def _analyze_liquidation(self, asset, liabilities: List) -> Dict[str, Any]:
        """Analyze selling an asset to pay off debt.

        Includes both interest saved and the value of freed-up monthly payments
        that could be invested over a 10-year period.
        """
        cost_basis = asset.total_cost
        current_value = asset.current_value
        gain_loss = current_value - cost_basis

        tax_rate = 0.15 if gain_loss > 0 else 0
        tax_liability = max(0, gain_loss * tax_rate)
        net_proceeds = current_value - tax_liability

        debts_by_rate = sorted([l for l in liabilities if l.current_balance > 0],
                               key=lambda x: x.interest_rate, reverse=True)

        remaining = net_proceeds
        debts_eliminated = []
        interest_saved = 0

        for debt in debts_by_rate:
            if remaining <= 0:
                break
            if debt.current_balance <= remaining:
                debts_eliminated.append(debt.name)
                interest_saved += debt.total_interest_remaining
                remaining -= debt.current_balance
            else:
                pct_paid = remaining / debt.current_balance
                interest_saved += debt.total_interest_remaining * pct_paid * 0.8
                remaining = 0

        # Calculate value of freed-up cashflow invested over 10 years
        freed_cashflow_invested = self._calculate_freed_cashflow_invested(net_proceeds, liabilities)

        # Total benefit = interest saved + freed cashflow invested
        total_benefit = interest_saved + freed_cashflow_invested

        total_debt = sum(l.current_balance for l in liabilities)
        debt_remaining = total_debt - (net_proceeds - remaining)

        high_interest = any(d.interest_rate > 15 for d in debts_by_rate)
        is_at_loss = gain_loss < 0

        # Compare against investing the proceeds at 7% for 10 years
        investment_value = net_proceeds * ((1 + 0.07) ** 10) if net_proceeds > 0 else 0
        investment_growth = investment_value - net_proceeds
        favors_debt_payoff = total_benefit > investment_growth

        if high_interest and total_benefit > tax_liability:
            if is_at_loss:
                rec = "STRONGLY RECOMMENDED: Sell to eliminate high-interest debt. Loss offsets gains."
            elif favors_debt_payoff:
                rec = f"RECOMMENDED: Debt payoff benefit (${total_benefit:,.0f}) exceeds expected investment growth."
            elif total_benefit > tax_liability * 2:
                rec = "RECOMMENDED: Total benefit significantly exceeds tax cost."
            else:
                rec = "CONSIDER: Benefits exceed tax cost, but investing may yield more."
        elif is_at_loss and high_interest:
            rec = "CONSIDER: Tax-loss harvesting opportunity."
        elif cost_basis > 0 and gain_loss / cost_basis > 0.5:
            rec = "CAUTION: Large unrealized gain. Consider partial sale."
        elif favors_debt_payoff:
            rec = f"CONSIDER: Debt payoff benefit (${total_benefit:,.0f}) exceeds investment growth."
        else:
            rec = "OPTIONAL: May help accelerate debt freedom."

        return {
            'asset_name': asset.name,
            'asset_type': asset.asset_type,
            'current_value': current_value,
            'cost_basis': cost_basis,
            'gain_loss': gain_loss,
            'estimated_tax': tax_liability,
            'net_proceeds': net_proceeds,
            'debts_eliminated': debts_eliminated,
            'interest_saved': interest_saved,
            'freed_cashflow_invested': freed_cashflow_invested,
            'total_benefit': total_benefit,
            'remaining_debt': max(0, debt_remaining),
            'recommendation': rec
        }

    def _generate_report(self):
        """Generate the financial analysis report."""
        assets = AssetOperations.get_all()
        liabilities = LiabilityOperations.get_all()
        incomes = IncomeOperations.get_active()
        expenses = ExpenseOperations.get_active()

        lines = []

        def section(title: str):
            lines.append("")
            lines.append("=" * 70)
            lines.append(f" {title}")
            lines.append("=" * 70)

        if not assets and not liabilities and not incomes and not expenses:
            lines.append("NO FINANCIAL DATA FOUND")
            lines.append("")
            lines.append("Please add assets, liabilities, income, and expenses to generate analysis.")
            self.report_text.setPlainText("\n".join(lines))
            return

        # Financial Overview
        total_assets = sum(a.current_value for a in assets)
        total_liabilities = sum(l.current_balance for l in liabilities)
        net_worth = total_assets - total_liabilities
        total_monthly_income = sum(i.monthly_amount for i in incomes)
        total_annual_income = sum(i.annual_amount for i in incomes)
        total_monthly_expenses = sum(e.monthly_amount for e in expenses)
        total_annual_expenses = sum(e.annual_amount for e in expenses)

        section("FINANCIAL OVERVIEW")
        lines.append("")
        lines.append(f"  Total Assets:       {self._format_currency(total_assets)}")
        lines.append(f"  Total Liabilities:  {self._format_currency(total_liabilities)}")
        lines.append(f"  Net Worth:          {self._format_currency(net_worth)}")
        lines.append("")
        lines.append(f"  Monthly Income:     {self._format_currency(total_monthly_income)}")
        lines.append(f"  Annual Income:      {self._format_currency(total_annual_income)}")
        lines.append(f"  Monthly Expenses:   {self._format_currency(total_monthly_expenses)}")
        lines.append(f"  Annual Expenses:    {self._format_currency(total_annual_expenses)}")

        # Income Analysis
        if incomes:
            section("INCOME ANALYSIS")
            lines.append("")
            lines.append(f"  Active Income Sources:  {len(incomes)}")
            lines.append(f"  Total Monthly Income:   {self._format_currency(total_monthly_income)}")
            lines.append(f"  Total Annual Income:    {self._format_currency(total_annual_income)}")

            # Income by type
            income_by_type = {}
            for income in incomes:
                if income.income_type not in income_by_type:
                    income_by_type[income.income_type] = {'count': 0, 'monthly': 0, 'annual': 0}
                income_by_type[income.income_type]['count'] += 1
                income_by_type[income.income_type]['monthly'] += income.monthly_amount
                income_by_type[income.income_type]['annual'] += income.annual_amount

            type_names = {
                'salary': 'Salary/Wages',
                'bonus': 'Bonus',
                'investment': 'Investment',
                'rental': 'Rental',
                'side_gig': 'Side Gig',
                'other': 'Other'
            }

            lines.append("")
            lines.append("  Income Breakdown by Type:")
            for itype, data in sorted(income_by_type.items(), key=lambda x: x[1]['monthly'], reverse=True):
                type_label = type_names.get(itype, itype)
                lines.append(f"    {type_label}: {self._format_currency(data['monthly'])}/mo "
                           f"({self._format_currency(data['annual'])}/yr)")

            # Individual income sources
            lines.append("")
            lines.append("  Individual Income Sources:")
            for income in sorted(incomes, key=lambda x: x.monthly_amount, reverse=True):
                freq_display = {'weekly': 'Weekly', 'biweekly': 'Bi-weekly',
                              'monthly': 'Monthly', 'annual': 'Annual'}.get(income.frequency, income.frequency)
                lines.append(f"    - {income.name} ({type_names.get(income.income_type, income.income_type)})")
                lines.append(f"      {self._format_currency(income.amount)} {freq_display} = "
                           f"{self._format_currency(income.monthly_amount)}/mo")

        # Expense Analysis
        if expenses:
            section("EXPENSE ANALYSIS")
            lines.append("")

            essential_expenses = [e for e in expenses if e.is_essential]
            discretionary_expenses = [e for e in expenses if not e.is_essential]

            essential_monthly = sum(e.monthly_amount for e in essential_expenses)
            discretionary_monthly = sum(e.monthly_amount for e in discretionary_expenses)

            lines.append(f"  Active Expenses:          {len(expenses)}")
            lines.append(f"  Total Monthly Expenses:   {self._format_currency(total_monthly_expenses)}")
            lines.append(f"  Total Annual Expenses:    {self._format_currency(total_annual_expenses)}")
            lines.append("")
            lines.append(f"  Essential (Needs):        {self._format_currency(essential_monthly)}/mo")
            lines.append(f"  Discretionary (Wants):    {self._format_currency(discretionary_monthly)}/mo")

            if total_monthly_income > 0:
                expense_ratio = (total_monthly_expenses / total_monthly_income) * 100
                essential_ratio = (essential_monthly / total_monthly_income) * 100
                discretionary_ratio = (discretionary_monthly / total_monthly_income) * 100
                lines.append("")
                lines.append(f"  Expense-to-Income Ratio:  {expense_ratio:.1f}%")
                lines.append(f"    Essential Ratio:        {essential_ratio:.1f}%")
                lines.append(f"    Discretionary Ratio:    {discretionary_ratio:.1f}%")

                # 50/30/20 Budget Analysis
                lines.append("")
                lines.append("  50/30/20 Budget Analysis:")
                ideal_needs = total_monthly_income * 0.50
                ideal_wants = total_monthly_income * 0.30
                ideal_savings = total_monthly_income * 0.20

                lines.append(f"    Needs (50% target):     {self._format_currency(essential_monthly)} "
                           f"(Target: {self._format_currency(ideal_needs)})")
                if essential_monthly <= ideal_needs:
                    lines.append("      - ON TRACK")
                else:
                    lines.append(f"      - OVER by {self._format_currency(essential_monthly - ideal_needs)}")

                lines.append(f"    Wants (30% target):     {self._format_currency(discretionary_monthly)} "
                           f"(Target: {self._format_currency(ideal_wants)})")
                if discretionary_monthly <= ideal_wants:
                    lines.append("      - ON TRACK")
                else:
                    lines.append(f"      - OVER by {self._format_currency(discretionary_monthly - ideal_wants)}")

            # Expense by type
            expense_by_type = {}
            for expense in expenses:
                if expense.expense_type not in expense_by_type:
                    expense_by_type[expense.expense_type] = {'count': 0, 'monthly': 0, 'annual': 0}
                expense_by_type[expense.expense_type]['count'] += 1
                expense_by_type[expense.expense_type]['monthly'] += expense.monthly_amount
                expense_by_type[expense.expense_type]['annual'] += expense.annual_amount

            type_names_expense = {
                'housing': 'Housing',
                'utilities': 'Utilities',
                'transportation': 'Transportation',
                'food': 'Food/Groceries',
                'insurance': 'Insurance',
                'healthcare': 'Healthcare',
                'entertainment': 'Entertainment',
                'subscriptions': 'Subscriptions',
                'debt': 'Debt Payments',
                'childcare': 'Childcare/Education',
                'personal': 'Personal Care',
                'other': 'Other'
            }

            lines.append("")
            lines.append("  Expense Breakdown by Type:")
            for etype, data in sorted(expense_by_type.items(), key=lambda x: x[1]['monthly'], reverse=True):
                type_label = type_names_expense.get(etype, etype)
                pct = (data['monthly'] / total_monthly_expenses * 100) if total_monthly_expenses > 0 else 0
                lines.append(f"    {type_label}: {self._format_currency(data['monthly'])}/mo ({pct:.1f}%)")

            # Top expenses
            lines.append("")
            lines.append("  Top 5 Monthly Expenses:")
            for i, expense in enumerate(sorted(expenses, key=lambda x: x.monthly_amount, reverse=True)[:5], 1):
                category_label = "Essential" if expense.is_essential else "Discretionary"
                lines.append(f"    {i}. {expense.name}: {self._format_currency(expense.monthly_amount)}/mo ({category_label})")

        # Transaction Spending Analysis
        spending_summary = TransactionOperations.get_spending_summary()
        non_spending = TransactionOperations.get_non_spending_summary()
        deposit_totals = TransactionOperations.get_deposit_totals()

        if spending_summary or non_spending:
            section("ACTUAL SPENDING (FROM TRANSACTIONS)")
            lines.append("")

            total_spending = abs(sum(d['total'] for d in spending_summary.values()))
            total_txn_count = sum(d['count'] for d in spending_summary.values())
            total_deposits = deposit_totals.get('total', 0)
            deposit_count = deposit_totals.get('count', 0)
            total_non_spending = abs(sum(d['total'] for d in non_spending.values()))

            lines.append(f"  Income (deposits):      {self._format_currency(total_deposits)}  ({deposit_count} transactions)")
            lines.append(f"  Spending:               {self._format_currency(total_spending)}  ({total_txn_count} transactions)")
            lines.append(f"  Debt/Transfers Out:     {self._format_currency(total_non_spending)}")
            lines.append(f"  Net (Income - Spending): {self._format_currency(total_deposits - total_spending)}")

            if spending_summary:
                lines.append("")
                lines.append("  Spending by Category:")
                lines.append(f"    {'Category':<20s}  {'Count':>5s}  {'Total':>12s}  {'Average':>10s}  {'% of Total':>10s}")
                lines.append(f"    {'─' * 62}")

                sorted_cats = sorted(spending_summary.items(), key=lambda x: x[1]['total'])
                for cat, data in sorted_cats:
                    pct = (abs(data['total']) / total_spending * 100) if total_spending > 0 else 0
                    lines.append(f"    {cat.title():<20s}  {data['count']:>5d}  "
                               f"${abs(data['total']):>11,.2f}  ${abs(data['avg']):>9,.2f}  {pct:>9.1f}%")

                lines.append(f"    {'─' * 62}")
                avg_txn = total_spending / total_txn_count if total_txn_count else 0
                lines.append(f"    {'TOTAL':<20s}  {total_txn_count:>5d}  "
                           f"${total_spending:>11,.2f}  ${avg_txn:>9,.2f}  {'100.0':>9s}%")

            if non_spending:
                lines.append("")
                lines.append("  Non-Spending Outflows:")
                for cat, data in sorted(non_spending.items(), key=lambda x: x[1]['total']):
                    lines.append(f"    {cat.title():<20s}  {data['count']:>5d}  ${abs(data['total']):>11,.2f}")

            # Compare budgeted vs actual
            if expenses and total_spending > 0:
                lines.append("")
                lines.append("  Budget vs Actual Comparison:")

                all_txns = TransactionOperations.get_all(limit=10000)
                dates = [t.transaction_date for t in all_txns if t.transaction_date]
                if dates:
                    from datetime import datetime
                    try:
                        d1 = datetime.strptime(min(dates), '%Y-%m-%d')
                        d2 = datetime.strptime(max(dates), '%Y-%m-%d')
                        days_span = max((d2 - d1).days, 1)
                        months_span = max(days_span / 30.44, 1)
                    except ValueError:
                        months_span = 1

                    actual_monthly = total_spending / months_span
                    lines.append(f"    Transaction Period:    {min(dates)} to {max(dates)} ({months_span:.1f} months)")
                    lines.append(f"    Actual Monthly Avg:    {self._format_currency(actual_monthly)}")
                    lines.append(f"    Budgeted Monthly:      {self._format_currency(total_monthly_expenses)}")

                    diff = total_monthly_expenses - actual_monthly
                    if diff >= 0:
                        lines.append(f"    Under Budget:          {self._format_currency(diff)}/mo")
                    else:
                        lines.append(f"    OVER Budget:           {self._format_currency(abs(diff))}/mo  *** WARNING ***")

            # Top merchants (spending only, exclude debt/transfers)
            non_spending_cats = TransactionOperations.NON_SPENDING_CATEGORIES
            merchant_totals = {}
            all_txns = TransactionOperations.get_all(limit=10000)
            for txn in all_txns:
                if txn.amount < 0 and txn.category not in non_spending_cats:
                    merchant_totals[txn.description] = merchant_totals.get(txn.description, 0) + txn.amount
            if merchant_totals:
                top = sorted(merchant_totals.items(), key=lambda x: x[1])[:10]
                lines.append("")
                lines.append("  Top 10 Merchants by Spending:")
                for i, (merchant, amount) in enumerate(top, 1):
                    lines.append(f"    {i:>2d}. {merchant:<40s}  {self._format_currency(abs(amount))}")

        # Debt Analysis
        if liabilities:
            total_monthly_debt = sum(l.monthly_payment for l in liabilities)
            total_interest = sum(l.monthly_interest_charge for l in liabilities)
            total_future_interest = sum(l.total_interest_remaining for l in liabilities
                                        if l.total_interest_remaining != float('inf'))

            section("DEBT ANALYSIS")
            lines.append("")
            lines.append(f"  Monthly Debt Payments:  {self._format_currency(total_monthly_debt)}")
            lines.append(f"  Monthly Interest Cost:  {self._format_currency(total_interest)}")
            lines.append(f"  Total Future Interest:  {self._format_currency(total_future_interest)}")

            avalanche = self._simulate_avalanche_payoff(liabilities, 0)
            if avalanche['total_months'] > 0:
                years = avalanche['total_months'] // 12
                months = avalanche['total_months'] % 12
                lines.append("")
                lines.append(f"  Time to Debt-Free:      {years} years, {months} months")
                lines.append(f"  Recommended Strategy:   AVALANCHE (highest rate first)")

                if avalanche['payoff_order']:
                    lines.append("")
                    lines.append("  Payoff Order:")
                    for i, debt in enumerate(avalanche['payoff_order'], 1):
                        lines.append(f"    {i}. {debt}")

            # Individual debts
            section("INDIVIDUAL DEBT BREAKDOWN")
            for liability in liabilities:
                lines.append("")
                lines.append(f"  {liability.name} ({liability.liability_type})")
                lines.append(f"    Balance:          {self._format_currency(liability.current_balance)}")
                lines.append(f"    Interest Rate:    {liability.interest_rate:.2f}%")
                lines.append(f"    Monthly Payment:  {self._format_currency(liability.monthly_payment)}")
                lines.append(f"    Monthly Interest: {self._format_currency(liability.monthly_interest_charge)}")
                lines.append(f"    Principal/Month:  {self._format_currency(liability.principal_payment)}")
                if liability.months_to_payoff > 0:
                    lines.append(f"    Months to Payoff: {liability.months_to_payoff}")
                    lines.append(f"    Future Interest:  {self._format_currency(liability.total_interest_remaining)}")
                elif liability.months_to_payoff < 0:
                    lines.append("    WARNING: Payment doesn't cover interest - balance will grow!")
                if liability.is_revolving:
                    lines.append(f"    Credit Limit:     {self._format_currency(liability.credit_limit)}")
                    lines.append(f"    Utilization:      {liability.utilization_rate:.1f}%")

        # Asset Liquidation Analysis
        liquid_assets = [a for a in assets if a.asset_type not in ('retirement',)]
        if liquid_assets and liabilities:
            section("ASSET LIQUIDATION ANALYSIS")
            lines.append("")
            lines.append("  Analyzing potential asset sales to accelerate debt payoff...")
            lines.append("")

            scenarios = []
            for asset in liquid_assets:
                if asset.current_value > 0:
                    scenario = self._analyze_liquidation(asset, liabilities)
                    scenarios.append(scenario)

            scenarios.sort(key=lambda x: x['total_benefit'], reverse=True)

            for i, scenario in enumerate(scenarios, 1):
                lines.append(f"  OPTION {i}: Sell {scenario['asset_name']} ({scenario['asset_type']})")
                lines.append(f"    Current Value:    {self._format_currency(scenario['current_value'])}")
                lines.append(f"    Cost Basis:       {self._format_currency(scenario['cost_basis'])}")
                gl = scenario['gain_loss']
                gl_str = f"+{self._format_currency(gl)}" if gl >= 0 else self._format_currency(gl)
                lines.append(f"    Gain/Loss:        {gl_str}")
                lines.append(f"    Est. Tax:         {self._format_currency(scenario['estimated_tax'])}")
                lines.append(f"    Net Proceeds:     {self._format_currency(scenario['net_proceeds'])}")
                lines.append(f"    Interest Saved:   {self._format_currency(scenario['interest_saved'])}")
                lines.append(f"    Cashflow Invested:{self._format_currency(scenario['freed_cashflow_invested'])} (10yr @ 7%)")
                lines.append(f"    Total Benefit:    {self._format_currency(scenario['total_benefit'])}")
                if scenario['debts_eliminated']:
                    lines.append(f"    Debts Eliminated: {', '.join(scenario['debts_eliminated'])}")
                lines.append(f"    Remaining Debt:   {self._format_currency(scenario['remaining_debt'])}")
                lines.append(f"    >>> {scenario['recommendation']}")
                lines.append("")

        # Extra Payment Analysis
        if liabilities:
            section("EXTRA PAYMENT IMPACT ANALYSIS")
            baseline = self._simulate_avalanche_payoff(liabilities, 0)

            for extra in [100, 250, 500, 1000]:
                accelerated = self._simulate_avalanche_payoff(liabilities, extra)
                if baseline['total_months'] > 0:
                    months_saved = baseline['total_months'] - accelerated['total_months']
                    interest_saved = baseline['total_interest'] - accelerated['total_interest']
                    lines.append("")
                    lines.append(f"  With ${extra}/month extra:")
                    lines.append(f"    Months Saved:     {months_saved}")
                    lines.append(f"    Interest Saved:   {self._format_currency(interest_saved)}")
                    lines.append(f"    New Payoff Time:  {accelerated['total_months']} months")

        # Cash Flow Analysis
        if incomes or liabilities or expenses:
            section("CASH FLOW ANALYSIS")
            lines.append("")

            monthly_debt_payments = sum(l.monthly_payment for l in liabilities) if liabilities else 0
            total_outflow = monthly_debt_payments + total_monthly_expenses
            net_monthly_cash_flow = total_monthly_income - total_outflow

            lines.append(f"  Monthly Income:         {self._format_currency(total_monthly_income)}")
            lines.append(f"  Monthly Expenses:       {self._format_currency(total_monthly_expenses)}  (budgeted)")
            lines.append(f"  Monthly Debt Payments:  {self._format_currency(monthly_debt_payments)}")
            lines.append(f"  Total Monthly Outflow:  {self._format_currency(total_outflow)}")
            lines.append(f"  Net Monthly Cash Flow:  {self._format_currency(net_monthly_cash_flow)}")
            lines.append(f"  Projected Annual:       {self._format_currency(net_monthly_cash_flow * 12)}")

            # Show actual spending from transactions if available
            if spending_summary:
                actual_total = abs(sum(d['total'] for d in spending_summary.values()))
                txn_dates = [t.transaction_date for t in TransactionOperations.get_all(limit=10000) if t.transaction_date]
                if txn_dates:
                    from datetime import datetime as dt
                    try:
                        d1 = dt.strptime(min(txn_dates), '%Y-%m-%d')
                        d2 = dt.strptime(max(txn_dates), '%Y-%m-%d')
                        m_span = max((d2 - d1).days / 30.44, 1)
                        actual_monthly_avg = actual_total / m_span
                        lines.append("")
                        lines.append(f"  Actual Spending (txns): {self._format_currency(actual_monthly_avg)}/mo avg")
                        actual_outflow = monthly_debt_payments + actual_monthly_avg
                        actual_net = total_monthly_income - actual_outflow
                        lines.append(f"  Actual Net Cash Flow:   {self._format_currency(actual_net)}")
                    except ValueError:
                        pass

            if total_monthly_income > 0:
                # Debt-to-Income Ratio (only debt payments, not expenses)
                debt_to_income = (monthly_debt_payments / total_monthly_income) * 100
                lines.append("")
                lines.append(f"  Debt-to-Income Ratio:   {debt_to_income:.1f}% (debt only)")
                if debt_to_income > 43:
                    lines.append("    WARNING: DTI exceeds 43% - may affect loan eligibility")
                elif debt_to_income > 36:
                    lines.append("    CAUTION: DTI above 36% - consider debt reduction")
                elif debt_to_income > 28:
                    lines.append("    ACCEPTABLE: DTI is manageable but could be lower")
                else:
                    lines.append("    EXCELLENT: DTI is healthy")

                # Total Outflow Ratio (debt + expenses)
                outflow_ratio = (total_outflow / total_monthly_income) * 100
                lines.append("")
                lines.append(f"  Total Outflow Ratio:    {outflow_ratio:.1f}% (debt + expenses)")
                if outflow_ratio > 90:
                    lines.append("    CRITICAL: Very little room for savings")
                elif outflow_ratio > 80:
                    lines.append("    WARNING: Consider reducing expenses")
                elif outflow_ratio > 70:
                    lines.append("    ACCEPTABLE: Some room for savings")
                else:
                    lines.append("    EXCELLENT: Good financial margin")

            if net_monthly_cash_flow > 0:
                lines.append("")
                lines.append("  Surplus Allocation Options:")
                lines.append(f"    - Emergency Fund:     {self._format_currency(net_monthly_cash_flow * 0.20)}/mo (20%)")
                lines.append(f"    - Extra Debt Payment: {self._format_currency(net_monthly_cash_flow * 0.50)}/mo (50%)")
                lines.append(f"    - Investments:        {self._format_currency(net_monthly_cash_flow * 0.30)}/mo (30%)")

                # Calculate savings rate
                savings_rate = (net_monthly_cash_flow / total_monthly_income) * 100 if total_monthly_income > 0 else 0
                lines.append("")
                lines.append(f"  Actual Savings Rate:    {savings_rate:.1f}%")
                if savings_rate >= 20:
                    lines.append("    EXCELLENT: On track for financial independence")
                elif savings_rate >= 15:
                    lines.append("    GOOD: Solid savings rate")
                elif savings_rate >= 10:
                    lines.append("    ACCEPTABLE: Consider increasing savings")
                else:
                    lines.append("    LOW: Try to increase income or reduce expenses")

                # Financial Freedom calculation
                if net_monthly_cash_flow > 0:
                    annual_expenses = total_monthly_expenses * 12
                    years_to_ff = (annual_expenses * 25) / (net_monthly_cash_flow * 12)  # 4% rule
                    lines.append("")
                    lines.append(f"  Years to Financial Independence: ~{years_to_ff:.1f} years")
                    lines.append("    (Based on 4% safe withdrawal rate)")

            elif net_monthly_cash_flow < 0:
                lines.append("")
                lines.append(f"  WARNING: Negative cash flow of {self._format_currency(abs(net_monthly_cash_flow))}/month")
                lines.append("    - Review discretionary expenses for cuts")
                disc_expenses = [e for e in expenses if not e.is_essential]
                disc_monthly = sum(e.monthly_amount for e in disc_expenses)
                if disc_monthly > 0:
                    lines.append(f"    - Potential savings from discretionary: {self._format_currency(disc_monthly)}/mo")
                lines.append("    - Look for ways to increase income")
                lines.append("    - Consider debt consolidation or refinancing")

        # Recommendations
        section("RECOMMENDATIONS")

        if liabilities:
            high_interest = [l for l in liabilities if l.interest_rate > 15 and l.current_balance > 0]
            if high_interest:
                lines.append("")
                lines.append("  [1] ELIMINATE HIGH-INTEREST DEBT FIRST")
                lines.append(f"      You have {self._format_currency(sum(l.current_balance for l in high_interest))} "
                           f"in debt at >15% APR.")
                lines.append(f"      Target: {high_interest[0].name} ({high_interest[0].interest_rate:.1f}% APR)")

            revolving = [l for l in liabilities if l.is_revolving and l.credit_limit > 0]
            if revolving:
                total_bal = sum(l.current_balance for l in revolving)
                total_limit = sum(l.credit_limit for l in revolving)
                util = (total_bal / total_limit * 100) if total_limit > 0 else 0
                if util > 30:
                    lines.append("")
                    lines.append("  [2] REDUCE CREDIT UTILIZATION")
                    lines.append(f"      Current utilization: {util:.1f}% - hurts credit score")
                    lines.append(f"      Pay down {self._format_currency(total_bal - total_limit * 0.30)} to reach 30%")

        cash = sum(a.current_value for a in assets if a.asset_type == 'cash')
        emergency_target = total_monthly_expenses * 6 if total_monthly_expenses > 0 else 10000
        if cash < emergency_target:
            lines.append("")
            lines.append("  [3] BUILD EMERGENCY FUND")
            lines.append(f"      Current cash: {self._format_currency(cash)}")
            if total_monthly_expenses > 0:
                months_covered = cash / total_monthly_expenses if total_monthly_expenses > 0 else 0
                lines.append(f"      Current coverage: {months_covered:.1f} months of expenses")
                lines.append(f"      Target: {self._format_currency(emergency_target)} (6 months expenses)")
            else:
                lines.append("      Target: 3-6 months expenses in high-yield savings")

        # Expense-related recommendations
        if expenses:
            disc_expenses = [e for e in expenses if not e.is_essential]
            disc_monthly = sum(e.monthly_amount for e in disc_expenses)

            if disc_monthly > total_monthly_income * 0.30 and total_monthly_income > 0:
                lines.append("")
                lines.append("  [4] REDUCE DISCRETIONARY SPENDING")
                lines.append(f"      Current discretionary: {self._format_currency(disc_monthly)}/mo")
                lines.append(f"      Target (30% of income): {self._format_currency(total_monthly_income * 0.30)}/mo")
                lines.append(f"      Potential savings: {self._format_currency(disc_monthly - total_monthly_income * 0.30)}/mo")

            # Check for subscription bloat
            subscriptions = [e for e in expenses if e.expense_type == 'subscriptions']
            sub_monthly = sum(e.monthly_amount for e in subscriptions)
            if sub_monthly > 100:
                lines.append("")
                lines.append("  [5] REVIEW SUBSCRIPTIONS")
                lines.append(f"      Total subscriptions: {self._format_currency(sub_monthly)}/mo")
                lines.append(f"      Annual cost: {self._format_currency(sub_monthly * 12)}")
                lines.append("      Consider: Which services do you actually use regularly?")

        lines.append("")
        lines.append("=" * 70)
        lines.append(" END OF ANALYSIS")
        lines.append("=" * 70)

        self.report_text.setPlainText("\n".join(lines))

    def _export_report(self):
        """Export report to a file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Report",
            "financial_analysis.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.report_text.toPlainText())
                QMessageBox.information(
                    self, "Export Complete",
                    f"Report exported to:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error",
                    f"Failed to export: {str(e)}"
                )
