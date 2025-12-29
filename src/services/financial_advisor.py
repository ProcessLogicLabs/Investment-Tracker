"""Financial analysis and optimization advisor for net worth growth."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from ..database.models import Asset, Liability
from ..database.operations import AssetOperations, LiabilityOperations


@dataclass
class PayoffSchedule:
    """Monthly payoff projection for a liability."""
    month: int
    date: str
    starting_balance: float
    interest_charge: float
    payment: float
    principal_paid: float
    ending_balance: float


@dataclass
class DebtPayoffPlan:
    """Complete payoff plan for a single debt."""
    liability: Liability
    total_months: int
    total_interest: float
    total_paid: float
    monthly_schedule: List[PayoffSchedule] = field(default_factory=list)
    payoff_date: str = ""


@dataclass
class DebtPayoffStrategy:
    """Complete debt payoff strategy analysis."""
    strategy_name: str  # 'avalanche', 'snowball', 'hybrid'
    total_months: int
    total_interest: float
    total_paid: float
    monthly_extra: float  # Extra money applied each month
    payoff_order: List[str]  # Order of debts to pay off
    debt_plans: List[DebtPayoffPlan] = field(default_factory=list)
    monthly_projections: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Recommendation:
    """Financial recommendation."""
    priority: int  # 1 = highest
    category: str  # 'debt', 'savings', 'investment', 'emergency'
    title: str
    description: str
    potential_savings: float = 0.0
    action_items: List[str] = field(default_factory=list)


class FinancialAdvisor:
    """Analyzes financial data and provides optimization recommendations."""

    def __init__(self):
        self.assets: List[Asset] = []
        self.liabilities: List[Liability] = []
        self._load_data()

    def _load_data(self):
        """Load current assets and liabilities."""
        self.assets = AssetOperations.get_all()
        self.liabilities = LiabilityOperations.get_all()

    def refresh_data(self):
        """Refresh data from database."""
        self._load_data()

    # ==================== DEBT ANALYSIS ====================

    def calculate_debt_payoff(self, liability: Liability,
                              extra_payment: float = 0.0) -> DebtPayoffPlan:
        """Calculate complete payoff schedule for a single debt."""
        schedule = []
        balance = liability.current_balance
        monthly_rate = liability.monthly_interest_rate
        payment = liability.monthly_payment + extra_payment
        total_interest = 0
        month = 0
        current_date = datetime.now()

        while balance > 0.01 and month < 600:
            month += 1
            date = current_date + relativedelta(months=month)
            starting = balance

            interest = balance * monthly_rate
            total_interest += interest

            principal = min(payment - interest, balance)
            if principal < 0:
                principal = 0
                balance += interest  # Balance grows if payment doesn't cover interest
            else:
                balance -= principal

            schedule.append(PayoffSchedule(
                month=month,
                date=date.strftime('%Y-%m'),
                starting_balance=starting,
                interest_charge=interest,
                payment=min(payment, starting + interest),
                principal_paid=principal,
                ending_balance=max(0, balance)
            ))

            if balance <= 0:
                break

        payoff_date = ""
        if schedule:
            payoff_date = schedule[-1].date

        return DebtPayoffPlan(
            liability=liability,
            total_months=month,
            total_interest=total_interest,
            total_paid=liability.current_balance + total_interest,
            monthly_schedule=schedule,
            payoff_date=payoff_date
        )

    def analyze_avalanche_strategy(self, extra_monthly: float = 0.0) -> DebtPayoffStrategy:
        """Debt avalanche: pay highest interest rate first."""
        return self._analyze_strategy('avalanche', extra_monthly)

    def analyze_snowball_strategy(self, extra_monthly: float = 0.0) -> DebtPayoffStrategy:
        """Debt snowball: pay smallest balance first."""
        return self._analyze_strategy('snowball', extra_monthly)

    def _analyze_strategy(self, strategy: str, extra_monthly: float) -> DebtPayoffStrategy:
        """Analyze a debt payoff strategy."""
        debts = [l for l in self.liabilities if l.current_balance > 0]

        if not debts:
            return DebtPayoffStrategy(
                strategy_name=strategy,
                total_months=0,
                total_interest=0,
                total_paid=0,
                monthly_extra=extra_monthly,
                payoff_order=[]
            )

        # Sort based on strategy
        if strategy == 'avalanche':
            debts = sorted(debts, key=lambda x: x.interest_rate, reverse=True)
        elif strategy == 'snowball':
            debts = sorted(debts, key=lambda x: x.current_balance)
        else:  # hybrid - balance of both
            debts = sorted(debts, key=lambda x: x.interest_rate * x.current_balance, reverse=True)

        # Simulate payoff
        balances = {d.id: d.current_balance for d in debts}
        min_payments = {d.id: d.monthly_payment for d in debts}
        rates = {d.id: d.monthly_interest_rate for d in debts}

        total_interest = 0
        month = 0
        projections = []
        debt_plans = []
        extra = extra_monthly
        current_date = datetime.now()
        payoff_order = []

        while any(b > 0.01 for b in balances.values()) and month < 600:
            month += 1
            date = current_date + relativedelta(months=month)
            month_data = {'month': month, 'date': date.strftime('%Y-%m')}

            # Apply interest to all
            for d in debts:
                if balances[d.id] > 0:
                    interest = balances[d.id] * rates[d.id]
                    total_interest += interest
                    balances[d.id] += interest

            # Make minimum payments on all
            for d in debts:
                if balances[d.id] > 0:
                    payment = min(min_payments[d.id], balances[d.id])
                    balances[d.id] -= payment

            # Apply extra to target debt
            remaining_extra = extra
            for d in debts:
                if balances[d.id] > 0.01 and remaining_extra > 0:
                    apply = min(remaining_extra, balances[d.id])
                    balances[d.id] -= apply
                    remaining_extra -= apply

                    if balances[d.id] <= 0.01:
                        # Debt paid off, add its payment to snowball
                        extra += min_payments[d.id]
                        if d.name not in payoff_order:
                            payoff_order.append(d.name)
                    break  # Only apply extra to first unpaid debt

            # Record month state
            month_data['balances'] = dict(balances)
            month_data['total_debt'] = sum(balances.values())
            projections.append(month_data)

        # Create individual debt plans
        for d in debts:
            plan = self.calculate_debt_payoff(d)
            debt_plans.append(plan)

        total_paid = sum(d.current_balance for d in debts) + total_interest

        return DebtPayoffStrategy(
            strategy_name=strategy,
            total_months=month,
            total_interest=total_interest,
            total_paid=total_paid,
            monthly_extra=extra_monthly,
            payoff_order=payoff_order,
            debt_plans=debt_plans,
            monthly_projections=projections
        )

    def compare_payoff_strategies(self, extra_monthly: float = 0.0) -> Dict[str, DebtPayoffStrategy]:
        """Compare all debt payoff strategies."""
        return {
            'avalanche': self.analyze_avalanche_strategy(extra_monthly),
            'snowball': self.analyze_snowball_strategy(extra_monthly),
            'minimum': self._analyze_strategy('minimum', 0)  # No extra payments
        }

    # ==================== NET WORTH ANALYSIS ====================

    def get_net_worth_summary(self) -> Dict[str, Any]:
        """Get comprehensive net worth breakdown."""
        total_assets = sum(a.current_value for a in self.assets)
        total_liabilities = sum(l.current_balance for l in self.liabilities)
        net_worth = total_assets - total_liabilities

        # Asset breakdown
        assets_by_type = {}
        for a in self.assets:
            t = a.asset_type
            if t not in assets_by_type:
                assets_by_type[t] = {'count': 0, 'value': 0}
            assets_by_type[t]['count'] += 1
            assets_by_type[t]['value'] += a.current_value

        # Liability breakdown
        liabilities_by_type = {}
        total_monthly_payments = 0
        total_interest_cost = 0

        for l in self.liabilities:
            t = l.liability_type
            if t not in liabilities_by_type:
                liabilities_by_type[t] = {'count': 0, 'balance': 0, 'monthly': 0}
            liabilities_by_type[t]['count'] += 1
            liabilities_by_type[t]['balance'] += l.current_balance
            liabilities_by_type[t]['monthly'] += l.monthly_payment
            total_monthly_payments += l.monthly_payment
            total_interest_cost += l.total_interest_remaining

        # Retirement contributions
        retirement_contributions = sum(
            a.monthly_contribution for a in self.assets
            if a.asset_type == 'retirement'
        )

        return {
            'net_worth': net_worth,
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'assets_by_type': assets_by_type,
            'liabilities_by_type': liabilities_by_type,
            'monthly_debt_payments': total_monthly_payments,
            'total_future_interest': total_interest_cost,
            'retirement_contributions': retirement_contributions,
            'debt_to_asset_ratio': (total_liabilities / total_assets * 100) if total_assets > 0 else 0
        }

    def project_net_worth(self, months: int = 60,
                          monthly_income: float = 0,
                          monthly_expenses: float = 0,
                          investment_return: float = 7.0) -> List[Dict[str, Any]]:
        """Project net worth growth over time."""
        projections = []
        current_date = datetime.now()

        # Starting values
        assets = {a.id: a.current_value for a in self.assets}
        asset_types = {a.id: a.asset_type for a in self.assets}
        retirement_contrib = {a.id: a.monthly_contribution for a in self.assets if a.asset_type == 'retirement'}

        liabilities = {l.id: l.current_balance for l in self.liabilities}
        liability_rates = {l.id: l.monthly_interest_rate for l in self.liabilities}
        liability_payments = {l.id: l.monthly_payment for l in self.liabilities}

        monthly_return = (investment_return / 100) / 12
        available_cash = monthly_income - monthly_expenses

        for month in range(1, months + 1):
            date = current_date + relativedelta(months=month)

            # Grow investments
            for aid, val in assets.items():
                if asset_types[aid] in ['stock', 'retirement']:
                    assets[aid] = val * (1 + monthly_return)
                # Add retirement contributions
                if aid in retirement_contrib:
                    assets[aid] += retirement_contrib[aid]

            # Apply debt payments and interest
            for lid in list(liabilities.keys()):
                if liabilities[lid] > 0:
                    # Add interest
                    liabilities[lid] += liabilities[lid] * liability_rates.get(lid, 0)
                    # Subtract payment
                    payment = min(liability_payments.get(lid, 0), liabilities[lid])
                    liabilities[lid] -= payment

            total_assets = sum(assets.values())
            total_liabilities = sum(max(0, l) for l in liabilities.values())

            projections.append({
                'month': month,
                'date': date.strftime('%Y-%m'),
                'total_assets': total_assets,
                'total_liabilities': total_liabilities,
                'net_worth': total_assets - total_liabilities
            })

        return projections

    # ==================== RECOMMENDATIONS ====================

    def get_recommendations(self, monthly_surplus: float = 0) -> List[Recommendation]:
        """Generate prioritized financial recommendations."""
        recommendations = []
        summary = self.get_net_worth_summary()

        # 1. High-interest debt warning
        high_interest_debts = [
            l for l in self.liabilities
            if l.interest_rate > 15 and l.current_balance > 0
        ]
        if high_interest_debts:
            total_high = sum(d.current_balance for d in high_interest_debts)
            interest_cost = sum(d.total_interest_remaining for d in high_interest_debts)
            recommendations.append(Recommendation(
                priority=1,
                category='debt',
                title='Eliminate High-Interest Debt',
                description=f'You have ${total_high:,.2f} in high-interest debt (>15% APR). '
                           f'This will cost ${interest_cost:,.2f} in interest if paid at minimum.',
                potential_savings=interest_cost * 0.5,  # Estimate savings from accelerated payoff
                action_items=[
                    f'Focus extra payments on {high_interest_debts[0].name} ({high_interest_debts[0].interest_rate:.1f}% APR)',
                    'Consider balance transfer to lower-rate card',
                    'Avoid adding new charges until paid off'
                ]
            ))

        # 2. Credit utilization warning
        revolving_debts = [l for l in self.liabilities if l.is_revolving and l.credit_limit > 0]
        if revolving_debts:
            total_balance = sum(l.current_balance for l in revolving_debts)
            total_limit = sum(l.credit_limit for l in revolving_debts)
            utilization = (total_balance / total_limit * 100) if total_limit > 0 else 0

            if utilization > 30:
                recommendations.append(Recommendation(
                    priority=2,
                    category='debt',
                    title='Reduce Credit Utilization',
                    description=f'Credit utilization is {utilization:.1f}% (${total_balance:,.2f} of ${total_limit:,.2f} limit). '
                               f'High utilization hurts credit score. Target under 30%.',
                    potential_savings=0,
                    action_items=[
                        f'Pay down ${total_balance - (total_limit * 0.30):,.2f} to reach 30% utilization',
                        'Request credit limit increases',
                        'Spread balances across multiple cards'
                    ]
                ))

        # 3. Debt avalanche vs snowball comparison
        if self.liabilities:
            strategies = self.compare_payoff_strategies(monthly_surplus)
            avalanche = strategies.get('avalanche')
            snowball = strategies.get('snowball')
            minimum = strategies.get('minimum')

            if avalanche and minimum and avalanche.total_interest < minimum.total_interest:
                savings = minimum.total_interest - avalanche.total_interest
                time_saved = minimum.total_months - avalanche.total_months
                recommendations.append(Recommendation(
                    priority=3,
                    category='debt',
                    title='Optimize Debt Payoff Strategy',
                    description=f'Using the debt avalanche method (highest interest first) with ${monthly_surplus:,.2f}/mo extra '
                               f'saves ${savings:,.2f} in interest and {time_saved} months vs minimum payments.',
                    potential_savings=savings,
                    action_items=[
                        f'Target: {avalanche.payoff_order[0] if avalanche.payoff_order else "highest rate debt"} first',
                        f'Debt-free by: {avalanche.debt_plans[0].payoff_date if avalanche.debt_plans else "N/A"}',
                        'Redirect paid-off debt payments to next target'
                    ]
                ))

        # 4. Emergency fund check
        cash_assets = sum(a.current_value for a in self.assets if a.asset_type == 'cash')
        monthly_expenses_estimate = summary['monthly_debt_payments'] + 2000  # Rough estimate

        if cash_assets < monthly_expenses_estimate * 3:
            target = monthly_expenses_estimate * 6
            recommendations.append(Recommendation(
                priority=4 if not high_interest_debts else 5,
                category='emergency',
                title='Build Emergency Fund',
                description=f'Current cash reserves: ${cash_assets:,.2f}. '
                           f'Recommended: 3-6 months expenses (${target:,.2f}).',
                potential_savings=0,
                action_items=[
                    f'Save ${(target - cash_assets):,.2f} for full 6-month cushion',
                    'Keep in high-yield savings account',
                    'Automate monthly transfers'
                ]
            ))

        # 5. Retirement contribution optimization
        retirement_assets = [a for a in self.assets if a.asset_type == 'retirement']
        if retirement_assets:
            total_contribution = sum(a.monthly_contribution for a in retirement_assets)
            if total_contribution < 500:  # Below typical max contribution
                recommendations.append(Recommendation(
                    priority=5,
                    category='investment',
                    title='Maximize Retirement Contributions',
                    description=f'Current monthly retirement contributions: ${total_contribution:,.2f}. '
                               f'Consider increasing to maximize tax benefits.',
                    potential_savings=total_contribution * 0.25 * 12,  # Tax savings estimate
                    action_items=[
                        'Contribute at least enough to get full employer match',
                        'Consider Roth IRA for tax-free growth',
                        'Increase contribution by 1% annually'
                    ]
                ))

        # 6. Asset allocation review
        total_assets = summary['total_assets']
        if total_assets > 0:
            stock_pct = summary['assets_by_type'].get('stock', {}).get('value', 0) / total_assets * 100
            retirement_pct = summary['assets_by_type'].get('retirement', {}).get('value', 0) / total_assets * 100
            metals_pct = summary['assets_by_type'].get('metal', {}).get('value', 0) / total_assets * 100

            if metals_pct > 20:
                recommendations.append(Recommendation(
                    priority=6,
                    category='investment',
                    title='Review Precious Metals Allocation',
                    description=f'Precious metals are {metals_pct:.1f}% of assets. '
                               f'Consider diversifying - typical recommendation is 5-10%.',
                    potential_savings=0,
                    action_items=[
                        'Consider rebalancing to index funds for growth',
                        'Metals are a hedge, not primary growth vehicle',
                        'Review allocation annually'
                    ]
                ))

        # Sort by priority
        recommendations.sort(key=lambda x: x.priority)
        return recommendations

    def get_monthly_cash_flow_analysis(self) -> Dict[str, Any]:
        """Analyze monthly cash flow for debt payments and contributions."""
        total_debt_payments = sum(l.monthly_payment for l in self.liabilities)
        retirement_contributions = sum(
            a.monthly_contribution for a in self.assets
            if a.asset_type == 'retirement'
        )

        # Calculate interest vs principal breakdown
        total_interest = sum(l.monthly_interest_charge for l in self.liabilities)
        total_principal = total_debt_payments - total_interest

        return {
            'total_debt_payments': total_debt_payments,
            'interest_portion': total_interest,
            'principal_portion': total_principal,
            'retirement_contributions': retirement_contributions,
            'total_committed': total_debt_payments + retirement_contributions,
            'interest_percentage': (total_interest / total_debt_payments * 100) if total_debt_payments > 0 else 0
        }

    def get_payoff_acceleration_analysis(self, extra_monthly: float) -> Dict[str, Any]:
        """Show impact of extra monthly payments."""
        current = self._analyze_strategy('avalanche', 0)
        accelerated = self._analyze_strategy('avalanche', extra_monthly)

        months_saved = current.total_months - accelerated.total_months
        interest_saved = current.total_interest - accelerated.total_interest

        return {
            'extra_monthly': extra_monthly,
            'current_months': current.total_months,
            'accelerated_months': accelerated.total_months,
            'months_saved': months_saved,
            'current_interest': current.total_interest,
            'accelerated_interest': accelerated.total_interest,
            'interest_saved': interest_saved,
            'current_payoff_date': current.debt_plans[0].payoff_date if current.debt_plans else None,
            'accelerated_payoff_date': accelerated.debt_plans[0].payoff_date if accelerated.debt_plans else None
        }

    # ==================== ASSET LIQUIDATION ANALYSIS ====================

    def get_liquid_assets(self) -> List[Dict[str, Any]]:
        """Get assets that could potentially be sold to pay off debt."""
        liquid_assets = []

        for asset in self.assets:
            # Skip retirement accounts (penalties for early withdrawal)
            if asset.asset_type == 'retirement':
                continue

            # Calculate gain/loss and tax implications
            cost_basis = asset.total_cost
            current_value = asset.current_value
            gain_loss = current_value - cost_basis

            # Estimate capital gains tax (simplified: 15% long-term, 22% short-term)
            tax_rate = 0.15 if gain_loss > 0 else 0
            tax_liability = max(0, gain_loss * tax_rate)
            net_proceeds = current_value - tax_liability

            liquid_assets.append({
                'asset': asset,
                'name': asset.name,
                'type': asset.asset_type,
                'current_value': current_value,
                'cost_basis': cost_basis,
                'gain_loss': gain_loss,
                'gain_loss_pct': (gain_loss / cost_basis * 100) if cost_basis > 0 else 0,
                'estimated_tax': tax_liability,
                'net_proceeds': net_proceeds,
                'is_at_loss': gain_loss < 0
            })

        # Sort by value (highest first)
        liquid_assets.sort(key=lambda x: x['current_value'], reverse=True)
        return liquid_assets

    def analyze_asset_liquidation_scenarios(self) -> List[Dict[str, Any]]:
        """Analyze scenarios for selling assets to accelerate debt payoff."""
        scenarios = []
        liquid_assets = self.get_liquid_assets()

        if not liquid_assets or not self.liabilities:
            return scenarios

        # Get baseline (no asset sales)
        baseline = self._analyze_strategy('avalanche', 0)
        total_debt = sum(l.current_balance for l in self.liabilities)
        baseline_interest = baseline.total_interest
        baseline_months = baseline.total_months

        # Sort debts by interest rate for targeting
        debts_by_rate = sorted(self.liabilities, key=lambda x: x.interest_rate, reverse=True)

        for liquid_asset in liquid_assets:
            net_proceeds = liquid_asset['net_proceeds']
            if net_proceeds <= 0:
                continue

            # Calculate what debt could be paid off
            remaining = net_proceeds
            debts_eliminated = []
            interest_saved = 0

            for debt in debts_by_rate:
                if remaining <= 0:
                    break
                if debt.current_balance <= remaining:
                    # Can pay off entirely
                    debts_eliminated.append(debt.name)
                    interest_saved += debt.total_interest_remaining
                    remaining -= debt.current_balance
                else:
                    # Partial payoff - calculate interest savings
                    # Approximate: reduce balance proportionally reduces future interest
                    pct_paid = remaining / debt.current_balance
                    interest_saved += debt.total_interest_remaining * pct_paid * 0.8  # Conservative estimate
                    remaining = 0

            # Calculate new payoff timeline
            debt_remaining = total_debt - (net_proceeds - remaining)
            if debt_remaining > 0:
                # Estimate new timeline (simplified)
                total_monthly_payments = sum(l.monthly_payment for l in self.liabilities)
                avg_rate = sum(l.interest_rate * l.current_balance for l in self.liabilities) / total_debt if total_debt > 0 else 0
                # Simple approximation
                new_months = self._estimate_payoff_months(debt_remaining, total_monthly_payments, avg_rate / 100 / 12)
            else:
                new_months = 0

            months_saved = baseline_months - new_months

            scenarios.append({
                'asset_name': liquid_asset['name'],
                'asset_type': liquid_asset['type'],
                'asset_value': liquid_asset['current_value'],
                'cost_basis': liquid_asset['cost_basis'],
                'gain_loss': liquid_asset['gain_loss'],
                'estimated_tax': liquid_asset['estimated_tax'],
                'net_proceeds': net_proceeds,
                'debts_eliminated': debts_eliminated,
                'interest_saved': interest_saved,
                'months_saved': max(0, months_saved),
                'remaining_debt': max(0, debt_remaining),
                'recommendation': self._get_liquidation_recommendation(liquid_asset, interest_saved, debts_by_rate)
            })

        # Sort by interest saved (best options first)
        scenarios.sort(key=lambda x: x['interest_saved'], reverse=True)
        return scenarios

    def _estimate_payoff_months(self, balance: float, payment: float, monthly_rate: float) -> int:
        """Estimate months to pay off a balance."""
        if payment <= balance * monthly_rate:
            return 600  # Will never pay off

        months = 0
        while balance > 0.01 and months < 600:
            balance = balance * (1 + monthly_rate) - payment
            months += 1
        return months

    def _get_liquidation_recommendation(self, asset: Dict, interest_saved: float,
                                         debts: List[Liability]) -> str:
        """Generate recommendation for asset liquidation."""
        high_interest_debt = any(d.interest_rate > 15 for d in debts)
        is_at_loss = asset['is_at_loss']
        gain_loss_pct = asset['gain_loss_pct']

        if high_interest_debt and interest_saved > asset['estimated_tax']:
            if is_at_loss:
                return "STRONGLY RECOMMENDED: Sell to eliminate high-interest debt. Loss can offset capital gains elsewhere."
            elif interest_saved > asset['estimated_tax'] * 2:
                return "RECOMMENDED: Interest savings significantly exceed tax liability."
            else:
                return "CONSIDER: Interest savings exceed tax cost, but margin is modest."
        elif is_at_loss and high_interest_debt:
            return "CONSIDER: Tax-loss harvesting opportunity while eliminating debt."
        elif gain_loss_pct > 50:
            return "CAUTION: Large unrealized gain. Consider partial sale or holding."
        else:
            return "OPTIONAL: May help if you want to accelerate debt freedom."

    def get_comprehensive_debt_elimination_plan(self,
                                                 extra_monthly: float = 0,
                                                 consider_asset_sales: bool = True) -> Dict[str, Any]:
        """Generate comprehensive plan for fastest debt elimination."""
        summary = self.get_net_worth_summary()
        cash_flow = self.get_monthly_cash_flow_analysis()

        # Baseline analysis
        avalanche = self.analyze_avalanche_strategy(extra_monthly)
        snowball = self.analyze_snowball_strategy(extra_monthly)

        # Determine best strategy
        best_strategy = 'avalanche' if avalanche.total_interest <= snowball.total_interest else 'snowball'
        best_plan = avalanche if best_strategy == 'avalanche' else snowball

        result = {
            'current_debt': summary['total_liabilities'],
            'current_assets': summary['total_assets'],
            'net_worth': summary['net_worth'],
            'monthly_debt_payments': cash_flow['total_debt_payments'],
            'monthly_interest_cost': cash_flow['interest_portion'],
            'total_future_interest': summary['total_future_interest'],
            'best_strategy': best_strategy,
            'payoff_months': best_plan.total_months,
            'payoff_order': best_plan.payoff_order,
            'total_interest_cost': best_plan.total_interest,
            'extra_monthly_applied': extra_monthly,
            'asset_liquidation_scenarios': [],
            'recommendations': []
        }

        # Add asset liquidation analysis if requested
        if consider_asset_sales:
            scenarios = self.analyze_asset_liquidation_scenarios()
            result['asset_liquidation_scenarios'] = scenarios

            # Add specific recommendations
            for scenario in scenarios[:3]:  # Top 3 scenarios
                if 'RECOMMENDED' in scenario['recommendation']:
                    result['recommendations'].append({
                        'action': f"Sell {scenario['asset_name']}",
                        'proceeds': scenario['net_proceeds'],
                        'interest_saved': scenario['interest_saved'],
                        'months_saved': scenario['months_saved'],
                        'debts_eliminated': scenario['debts_eliminated'],
                        'rationale': scenario['recommendation']
                    })

        # Add general recommendations
        general_recs = self.get_recommendations(extra_monthly)
        result['general_recommendations'] = [
            {'priority': r.priority, 'title': r.title, 'description': r.description}
            for r in general_recs[:5]
        ]

        return result
