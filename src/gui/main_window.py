"""Main application window for Asset Tracker."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QToolBar, QStatusBar, QMessageBox, QFileDialog, QProgressBar,
    QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon

from ..database.models import init_database
from ..database.operations import AssetOperations, PriceHistoryOperations, SettingsOperations, LiabilityOperations, IncomeOperations, ExpenseOperations, GoalOperations, PaymentOperations, TransactionOperations
from ..services.updater import ScheduledUpdater
from .theme import ThemeManager, theme
from .widgets.asset_table import AssetTableWidget
from .widgets.liability_table import LiabilityTableWidget
from .widgets.income_table import IncomeTableWidget
from .widgets.expense_table import ExpenseTableWidget
from .widgets.dashboard import DashboardPanel
from .widgets.analysis_panel import AnalysisPanel
from .widgets.transaction_table import TransactionTableWidget
from .dialogs.add_asset import AddAssetDialog
from .dialogs.add_liability import AddLiabilityDialog
from .dialogs.add_income import AddIncomeDialog
from .dialogs.add_expense import AddExpenseDialog
from .dialogs.settings import SettingsDialog
from .dialogs.analysis_report import AnalysisReportDialog
from .dialogs.debt_payoff_simulation import DebtPayoffSimulationWizard
from .dialogs.add_goal import AddGoalDialog
from .dialogs.add_transaction import AddTransactionDialog
from .dialogs.import_transactions import ImportTransactionsDialog
from ..utils.export import ExcelExporter


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asset Tracker")
        self.setMinimumSize(1200, 700)

        # Initialize database
        init_database()

        # Initialize updater
        self.updater = ScheduledUpdater()

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        self._load_data()
        self._start_updates()

    def _setup_ui(self):
        """Set up the main UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Main tab widget for Portfolio, Summary, and Charts
        self.main_tabs = QTabWidget()
        self.main_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Tab 1: Dashboard
        dashboard_tab = QWidget()
        dashboard_layout = QVBoxLayout(dashboard_tab)
        dashboard_layout.setContentsMargins(5, 5, 5, 5)
        self.dashboard = DashboardPanel()
        dashboard_layout.addWidget(self.dashboard)
        self.main_tabs.addTab(dashboard_tab, "Dashboard")

        # Tab 2: Assets
        portfolio_tab = QWidget()
        portfolio_layout = QVBoxLayout(portfolio_tab)
        portfolio_layout.setContentsMargins(5, 5, 5, 5)
        self.asset_table = AssetTableWidget()
        portfolio_layout.addWidget(self.asset_table)
        self.main_tabs.addTab(portfolio_tab, "Assets")

        # Tab 3: Liabilities
        liabilities_tab = QWidget()
        liabilities_layout = QVBoxLayout(liabilities_tab)
        liabilities_layout.setContentsMargins(5, 5, 5, 5)
        self.liability_table = LiabilityTableWidget()
        liabilities_layout.addWidget(self.liability_table)
        self.main_tabs.addTab(liabilities_tab, "Liabilities")

        # Tab 4: Income
        income_tab = QWidget()
        income_layout = QVBoxLayout(income_tab)
        income_layout.setContentsMargins(5, 5, 5, 5)
        self.income_table = IncomeTableWidget()
        income_layout.addWidget(self.income_table)
        self.main_tabs.addTab(income_tab, "Income")

        # Tab 5: Expenses
        expenses_tab = QWidget()
        expenses_layout = QVBoxLayout(expenses_tab)
        expenses_layout.setContentsMargins(5, 5, 5, 5)
        self.expense_table = ExpenseTableWidget()
        expenses_layout.addWidget(self.expense_table)
        self.main_tabs.addTab(expenses_tab, "Expenses")

        # Tab 6: Transactions
        transactions_tab = QWidget()
        transactions_layout = QVBoxLayout(transactions_tab)
        transactions_layout.setContentsMargins(5, 5, 5, 5)
        self.transaction_table = TransactionTableWidget()
        transactions_layout.addWidget(self.transaction_table)
        self.main_tabs.addTab(transactions_tab, "Transactions")

        # Tab 7: Analysis
        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        analysis_layout.setContentsMargins(5, 5, 5, 5)
        self.analysis_panel = AnalysisPanel()
        analysis_layout.addWidget(self.analysis_panel)
        self.main_tabs.addTab(analysis_tab, "Analysis")

        main_layout.addWidget(self.main_tabs)

    def _setup_menu(self):
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        import_csv_action = QAction("&Import Transactions (CSV)...", self)
        import_csv_action.setShortcut("Ctrl+Shift+I")
        import_csv_action.triggered.connect(self._import_transactions)
        file_menu.addAction(import_csv_action)

        export_action = QAction("&Export to Excel...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_to_excel)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Asset menu
        asset_menu = menubar.addMenu("&Asset")

        add_action = QAction("&Add Asset...", self)
        add_action.setShortcut("Ctrl+N")
        add_action.triggered.connect(self._add_asset)
        asset_menu.addAction(add_action)

        edit_action = QAction("&Edit Asset...", self)
        edit_action.triggered.connect(self._edit_selected_asset)
        asset_menu.addAction(edit_action)

        delete_action = QAction("&Delete Asset", self)
        delete_action.triggered.connect(self._delete_selected_asset)
        asset_menu.addAction(delete_action)

        asset_menu.addSeparator()

        refresh_action = QAction("&Refresh Prices", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_prices)
        asset_menu.addAction(refresh_action)

        # Liability menu
        liability_menu = menubar.addMenu("&Liability")

        add_liability_action = QAction("&Add Liability...", self)
        add_liability_action.setShortcut("Ctrl+Shift+N")
        add_liability_action.triggered.connect(self._add_liability)
        liability_menu.addAction(add_liability_action)

        edit_liability_action = QAction("&Edit Liability...", self)
        edit_liability_action.triggered.connect(self._edit_selected_liability)
        liability_menu.addAction(edit_liability_action)

        delete_liability_action = QAction("&Delete Liability", self)
        delete_liability_action.triggered.connect(self._delete_selected_liability)
        liability_menu.addAction(delete_liability_action)

        liability_menu.addSeparator()

        apply_payments_action = QAction("A&pply Monthly Payments", self)
        apply_payments_action.setShortcut("Ctrl+P")
        apply_payments_action.triggered.connect(self._apply_payments)
        liability_menu.addAction(apply_payments_action)

        # Income menu
        income_menu = menubar.addMenu("&Income")

        add_income_action = QAction("&Add Income...", self)
        add_income_action.setShortcut("Ctrl+I")
        add_income_action.triggered.connect(self._add_income)
        income_menu.addAction(add_income_action)

        edit_income_action = QAction("&Edit Income...", self)
        edit_income_action.triggered.connect(self._edit_selected_income)
        income_menu.addAction(edit_income_action)

        delete_income_action = QAction("&Delete Income", self)
        delete_income_action.triggered.connect(self._delete_selected_income)
        income_menu.addAction(delete_income_action)

        # Expense menu
        expense_menu = menubar.addMenu("E&xpense")

        add_expense_action = QAction("&Add Expense...", self)
        add_expense_action.setShortcut("Ctrl+X")
        add_expense_action.triggered.connect(self._add_expense)
        expense_menu.addAction(add_expense_action)

        edit_expense_action = QAction("&Edit Expense...", self)
        edit_expense_action.triggered.connect(self._edit_selected_expense)
        expense_menu.addAction(edit_expense_action)

        delete_expense_action = QAction("&Delete Expense", self)
        delete_expense_action.triggered.connect(self._delete_selected_expense)
        expense_menu.addAction(delete_expense_action)

        # Goals menu
        goals_menu = menubar.addMenu("&Goals")

        add_goal_action = QAction("&Add Goal...", self)
        add_goal_action.setShortcut("Ctrl+G")
        add_goal_action.triggered.connect(self._add_goal)
        goals_menu.addAction(add_goal_action)

        # Transactions menu
        txn_menu = menubar.addMenu("&Transactions")

        add_txn_action = QAction("&Add Transaction...", self)
        add_txn_action.setShortcut("Ctrl+T")
        add_txn_action.triggered.connect(self._add_transaction)
        txn_menu.addAction(add_txn_action)

        edit_txn_action = QAction("&Edit Transaction...", self)
        edit_txn_action.triggered.connect(self._edit_selected_transaction)
        txn_menu.addAction(edit_txn_action)

        delete_txn_action = QAction("&Delete Transaction", self)
        delete_txn_action.triggered.connect(self._delete_selected_transaction)
        txn_menu.addAction(delete_txn_action)

        txn_menu.addSeparator()

        import_txn_action = QAction("&Import CSV...", self)
        import_txn_action.setShortcut("Ctrl+Shift+I")
        import_txn_action.triggered.connect(self._import_transactions)
        txn_menu.addAction(import_txn_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        dashboard_action = QAction("&Dashboard", self)
        dashboard_action.setShortcut("Ctrl+1")
        dashboard_action.triggered.connect(lambda: self.main_tabs.setCurrentIndex(0))
        view_menu.addAction(dashboard_action)

        assets_action = QAction("&Assets", self)
        assets_action.setShortcut("Ctrl+2")
        assets_action.triggered.connect(lambda: self.main_tabs.setCurrentIndex(1))
        view_menu.addAction(assets_action)

        liabilities_action = QAction("&Liabilities", self)
        liabilities_action.setShortcut("Ctrl+3")
        liabilities_action.triggered.connect(lambda: self.main_tabs.setCurrentIndex(2))
        view_menu.addAction(liabilities_action)

        income_view_action = QAction("&Income", self)
        income_view_action.setShortcut("Ctrl+4")
        income_view_action.triggered.connect(lambda: self.main_tabs.setCurrentIndex(3))
        view_menu.addAction(income_view_action)

        expenses_view_action = QAction("E&xpenses", self)
        expenses_view_action.setShortcut("Ctrl+5")
        expenses_view_action.triggered.connect(lambda: self.main_tabs.setCurrentIndex(4))
        view_menu.addAction(expenses_view_action)

        transactions_view_action = QAction("&Transactions", self)
        transactions_view_action.setShortcut("Ctrl+6")
        transactions_view_action.triggered.connect(lambda: self.main_tabs.setCurrentIndex(5))
        view_menu.addAction(transactions_view_action)

        analysis_action = QAction("A&nalysis", self)
        analysis_action.setShortcut("Ctrl+7")
        analysis_action.triggered.connect(lambda: self.main_tabs.setCurrentIndex(6))
        view_menu.addAction(analysis_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        analysis_report_action = QAction("&Generate Analysis Report...", self)
        analysis_report_action.setShortcut("Ctrl+R")
        analysis_report_action.triggered.connect(self._show_analysis_report)
        tools_menu.addAction(analysis_report_action)

        debt_simulation_action = QAction("&Debt Payoff Simulation...", self)
        debt_simulation_action.setShortcut("Ctrl+D")
        debt_simulation_action.triggered.connect(self._show_debt_simulation)
        tools_menu.addAction(debt_simulation_action)

        tools_menu.addSeparator()

        settings_action = QAction("&Settings...", self)
        settings_action.triggered.connect(self._show_settings)
        tools_menu.addAction(settings_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        """Set up the toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        add_action = QAction("Add Asset", self)
        add_action.triggered.connect(self._add_asset)
        toolbar.addAction(add_action)

        add_liability_action = QAction("Add Liability", self)
        add_liability_action.triggered.connect(self._add_liability)
        toolbar.addAction(add_liability_action)

        add_income_action = QAction("Add Income", self)
        add_income_action.triggered.connect(self._add_income)
        toolbar.addAction(add_income_action)

        add_expense_action = QAction("Add Expense", self)
        add_expense_action.triggered.connect(self._add_expense)
        toolbar.addAction(add_expense_action)

        toolbar.addSeparator()

        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(self._edit_current_item)
        toolbar.addAction(edit_action)

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._delete_current_item)
        toolbar.addAction(delete_action)

        toolbar.addSeparator()

        refresh_action = QAction("Refresh Prices", self)
        refresh_action.triggered.connect(self._refresh_prices)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        import_csv_action = QAction("Import CSV", self)
        import_csv_action.triggered.connect(self._import_transactions)
        toolbar.addAction(import_csv_action)

        export_action = QAction("Export", self)
        export_action.triggered.connect(self._export_to_excel)
        toolbar.addAction(export_action)

    def _setup_statusbar(self):
        """Set up the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.status_label = QLabel("Ready")
        self.statusbar.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self.progress_bar)

        self.last_update_label = QLabel("")
        self.statusbar.addPermanentWidget(self.last_update_label)

    def _connect_signals(self):
        """Connect widget signals."""
        self.asset_table.asset_double_clicked.connect(self._edit_asset)
        self.asset_table.edit_requested.connect(self._edit_asset)
        self.asset_table.delete_requested.connect(self._delete_asset)

        # Liability table signals
        self.liability_table.liability_double_clicked.connect(self._edit_liability)
        self.liability_table.edit_requested.connect(self._edit_liability)
        self.liability_table.delete_requested.connect(self._delete_liability)

        self.liability_table.payment_history_requested.connect(self._show_payment_history)

        # Income table signals
        self.income_table.income_double_clicked.connect(self._edit_income)
        self.income_table.edit_requested.connect(self._edit_income)
        self.income_table.delete_requested.connect(self._delete_income)

        # Expense table signals
        self.expense_table.expense_double_clicked.connect(self._edit_expense)
        self.expense_table.edit_requested.connect(self._edit_expense)
        self.expense_table.delete_requested.connect(self._delete_expense)

        # Transaction table signals
        self.transaction_table.transaction_double_clicked.connect(self._edit_transaction)
        self.transaction_table.edit_requested.connect(self._edit_transaction)
        self.transaction_table.delete_requested.connect(self._delete_transaction)

        # Goal signals
        self.dashboard.goal_add_requested.connect(self._add_goal)
        self.dashboard.goal_edit_requested.connect(self._edit_goal)
        self.dashboard.goal_delete_requested.connect(self._delete_goal)

        # Tab change - refresh analysis when switching to Analysis tab
        self.main_tabs.currentChanged.connect(self._on_tab_changed)

        # Theme signals
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

        # Updater signals
        self.updater.connect_price_updated(self._on_price_updated)
        self.updater.connect_update_complete(self._on_update_complete)
        self.updater.connect_update_error(self._on_update_error)
        self.updater.connect_progress(self._on_update_progress)

    def _on_theme_changed(self):
        """Handle theme change."""
        self.dashboard.apply_theme()
        self._load_data()

    def _on_tab_changed(self, index: int):
        """Handle tab change."""
        # Refresh analysis when switching to Analysis tab (index 6)
        if index == 6:
            self.analysis_panel.run_analysis()

    def _start_updates(self):
        """Start automatic price updates."""
        auto_update = SettingsOperations.get('auto_update', 'true') == 'true'
        interval = int(SettingsOperations.get('update_interval', '5'))

        if auto_update:
            self.updater.set_interval(interval)
            update_on_start = SettingsOperations.get('update_on_start', 'true') == 'true'
            if update_on_start:
                self.updater.start()
            else:
                # Start timer but don't do immediate update
                self.updater.timer.start(self.updater.interval_ms)

    def _load_data(self):
        """Load and display all data."""
        # Auto-apply monthly payments for any due months
        PaymentOperations.apply_monthly_payments()

        assets = AssetOperations.get_all()
        self.asset_table.set_assets(assets)

        liabilities = LiabilityOperations.get_all()
        self.liability_table.set_liabilities(liabilities)

        incomes = IncomeOperations.get_all()
        self.income_table.set_incomes(incomes)

        expenses = ExpenseOperations.get_all()
        self.expense_table.set_expenses(expenses)

        transactions = TransactionOperations.get_all()
        self.transaction_table.set_transactions(transactions)

        # Get summaries
        asset_summary = AssetOperations.get_portfolio_summary()
        liability_summary = LiabilityOperations.get_liabilities_summary()
        income_summary = IncomeOperations.get_income_summary()
        expense_summary = ExpenseOperations.get_expense_summary()

        # Calculate net worth
        total_assets = asset_summary.get('total_value', 0)
        total_liabilities = liability_summary.get('total_balance', 0)
        net_worth = total_assets - total_liabilities

        # Get portfolio history for sparklines and charts
        history = PriceHistoryOperations.get_portfolio_history(30)

        # Build net worth history for sparkline
        net_worth_history = [h['value'] - total_liabilities for h in history]

        # Combine summaries for display
        combined_summary = {
            **asset_summary,
            'total_liabilities': total_liabilities,
            'net_worth': net_worth,
            'liability_summary': liability_summary,
            'income_summary': income_summary,
            'expense_summary': expense_summary,
            'net_worth_history': net_worth_history,
        }
        self.dashboard.update_dashboard(combined_summary, asset_summary, assets, history)

        # Update spending breakdown from imported transactions
        spending_summary = TransactionOperations.get_spending_summary()
        # Also get deposit totals for the spending section
        deposit_totals = TransactionOperations.get_deposit_totals()
        if deposit_totals:
            spending_summary['__deposits__'] = deposit_totals
        self.dashboard.update_spending(spending_summary)

        # Refresh goal progress from live data
        GoalOperations.refresh_all_goal_progress()
        goals = GoalOperations.get_active()
        self.dashboard.update_goals(goals)

    def _add_asset(self):
        """Show add asset dialog."""
        dialog = AddAssetDialog(self)
        if dialog.exec():
            self._load_data()
            self.status_label.setText("Asset added successfully")

    def _edit_selected_asset(self):
        """Edit the currently selected asset."""
        asset_id = self.asset_table.get_selected_asset_id()
        if asset_id:
            self._edit_asset(asset_id)
        else:
            QMessageBox.information(self, "Edit Asset", "Please select an asset to edit.")

    def _edit_asset(self, asset_id: int):
        """Show edit dialog for an asset."""
        asset = AssetOperations.get_by_id(asset_id)
        if asset:
            dialog = AddAssetDialog(self, asset)
            if dialog.exec():
                self._load_data()
                self.status_label.setText("Asset updated successfully")

    def _delete_selected_asset(self):
        """Delete the currently selected asset."""
        asset_id = self.asset_table.get_selected_asset_id()
        if asset_id:
            self._delete_asset(asset_id)
        else:
            QMessageBox.information(self, "Delete Asset", "Please select an asset to delete.")

    def _delete_asset(self, asset_id: int):
        """Delete an asset after confirmation."""
        confirm_delete = SettingsOperations.get('confirm_delete', 'true') == 'true'

        if confirm_delete:
            asset = AssetOperations.get_by_id(asset_id)
            if not asset:
                return

            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Are you sure you want to delete '{asset.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        AssetOperations.delete(asset_id)
        self._load_data()
        self.status_label.setText("Asset deleted")

    def _add_liability(self):
        """Show add liability dialog."""
        dialog = AddLiabilityDialog(self)
        if dialog.exec():
            self._load_data()
            self.status_label.setText("Liability added successfully")

    def _edit_selected_liability(self):
        """Edit the currently selected liability."""
        liability_id = self.liability_table.get_selected_liability_id()
        if liability_id:
            self._edit_liability(liability_id)
        else:
            QMessageBox.information(self, "Edit Liability", "Please select a liability to edit.")

    def _edit_liability(self, liability_id: int):
        """Show edit dialog for a liability."""
        liability = LiabilityOperations.get_by_id(liability_id)
        if liability:
            dialog = AddLiabilityDialog(self, liability)
            if dialog.exec():
                self._load_data()
                self.status_label.setText("Liability updated successfully")

    def _delete_selected_liability(self):
        """Delete the currently selected liability."""
        liability_id = self.liability_table.get_selected_liability_id()
        if liability_id:
            self._delete_liability(liability_id)
        else:
            QMessageBox.information(self, "Delete Liability", "Please select a liability to delete.")

    def _delete_liability(self, liability_id: int):
        """Delete a liability after confirmation."""
        confirm_delete = SettingsOperations.get('confirm_delete', 'true') == 'true'

        if confirm_delete:
            liability = LiabilityOperations.get_by_id(liability_id)
            if not liability:
                return

            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Are you sure you want to delete '{liability.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        LiabilityOperations.delete(liability_id)
        self._load_data()
        self.status_label.setText("Liability deleted")

    def _show_payment_history(self, liability_id: int):
        """Show payment history for a liability."""
        liability = LiabilityOperations.get_by_id(liability_id)
        if not liability:
            return

        payments = PaymentOperations.get_by_liability(liability_id, limit=50)
        if not payments:
            QMessageBox.information(
                self, "Payment History",
                f"No payment history for '{liability.name}'."
            )
            return

        lines = [f"Payment History: {liability.name}\n"]
        lines.append(f"{'Date':<12} {'Payment':>10} {'Interest':>10} {'Principal':>10} {'Balance':>12}")
        lines.append("-" * 58)
        for p in reversed(payments):
            date_str = p.payment_date or ''
            lines.append(
                f"{date_str:<12} ${p.payment_amount:>9,.2f} ${p.interest_portion:>9,.2f} "
                f"${p.principal_portion:>9,.2f} ${p.balance_after:>11,.2f}"
            )

        total_paid = sum(p.payment_amount for p in payments)
        total_interest = sum(p.interest_portion for p in payments)
        total_principal = sum(p.principal_portion for p in payments)
        lines.append("-" * 58)
        lines.append(
            f"{'Totals':<12} ${total_paid:>9,.2f} ${total_interest:>9,.2f} "
            f"${total_principal:>9,.2f}"
        )

        QMessageBox.information(self, "Payment History", "\n".join(lines))

    def _apply_payments(self):
        """Manually trigger monthly payment application."""
        results = PaymentOperations.apply_monthly_payments()
        self._load_data()

        if results:
            total_applied = sum(r['payment'] for r in results)
            total_principal = sum(r['principal'] for r in results)
            total_interest = sum(r['interest'] for r in results)
            msg = (
                f"Applied {len(results)} payment(s):\n\n"
                f"Total Paid: ${total_applied:,.2f}\n"
                f"Principal: ${total_principal:,.2f}\n"
                f"Interest: ${total_interest:,.2f}"
            )
            QMessageBox.information(self, "Payments Applied", msg)
            self.status_label.setText(f"{len(results)} payment(s) applied")
        else:
            QMessageBox.information(
                self, "Payments",
                "No payments to apply. All liabilities are current."
            )

    def _add_income(self):
        """Show add income dialog."""
        dialog = AddIncomeDialog(self)
        if dialog.exec():
            self._load_data()
            self.status_label.setText("Income added successfully")

    def _edit_selected_income(self):
        """Edit the currently selected income."""
        income_id = self.income_table.get_selected_income_id()
        if income_id:
            self._edit_income(income_id)
        else:
            QMessageBox.information(self, "Edit Income", "Please select an income to edit.")

    def _edit_income(self, income_id: int):
        """Show edit dialog for an income."""
        income = IncomeOperations.get_by_id(income_id)
        if income:
            dialog = AddIncomeDialog(self, income)
            if dialog.exec():
                self._load_data()
                self.status_label.setText("Income updated successfully")

    def _delete_selected_income(self):
        """Delete the currently selected income."""
        income_id = self.income_table.get_selected_income_id()
        if income_id:
            self._delete_income(income_id)
        else:
            QMessageBox.information(self, "Delete Income", "Please select an income to delete.")

    def _delete_income(self, income_id: int):
        """Delete an income after confirmation."""
        confirm_delete = SettingsOperations.get('confirm_delete', 'true') == 'true'

        if confirm_delete:
            income = IncomeOperations.get_by_id(income_id)
            if not income:
                return

            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Are you sure you want to delete '{income.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        IncomeOperations.delete(income_id)
        self._load_data()
        self.status_label.setText("Income deleted")

    def _add_expense(self):
        """Show add expense dialog."""
        dialog = AddExpenseDialog(self)
        if dialog.exec():
            self._load_data()
            self.status_label.setText("Expense added successfully")

    def _edit_selected_expense(self):
        """Edit the currently selected expense."""
        expense_id = self.expense_table.get_selected_expense_id()
        if expense_id:
            self._edit_expense(expense_id)
        else:
            QMessageBox.information(self, "Edit Expense", "Please select an expense to edit.")

    def _edit_expense(self, expense_id: int):
        """Show edit dialog for an expense."""
        expense = ExpenseOperations.get_by_id(expense_id)
        if expense:
            dialog = AddExpenseDialog(self, expense)
            if dialog.exec():
                self._load_data()
                self.status_label.setText("Expense updated successfully")

    def _delete_selected_expense(self):
        """Delete the currently selected expense."""
        expense_id = self.expense_table.get_selected_expense_id()
        if expense_id:
            self._delete_expense(expense_id)
        else:
            QMessageBox.information(self, "Delete Expense", "Please select an expense to delete.")

    def _delete_expense(self, expense_id: int):
        """Delete an expense after confirmation."""
        confirm_delete = SettingsOperations.get('confirm_delete', 'true') == 'true'

        if confirm_delete:
            expense = ExpenseOperations.get_by_id(expense_id)
            if not expense:
                return

            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Are you sure you want to delete '{expense.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        ExpenseOperations.delete(expense_id)
        self._load_data()
        self.status_label.setText("Expense deleted")

    def _add_goal(self):
        """Show add goal dialog."""
        dialog = AddGoalDialog(self)
        if dialog.exec():
            self._load_data()
            self.status_label.setText("Goal added successfully")

    def _edit_goal(self, goal_id: int):
        """Show edit dialog for a goal."""
        goal = GoalOperations.get_by_id(goal_id)
        if goal:
            dialog = AddGoalDialog(self, goal)
            if dialog.exec():
                self._load_data()
                self.status_label.setText("Goal updated successfully")

    def _delete_goal(self, goal_id: int):
        """Delete a goal after confirmation."""
        goal = GoalOperations.get_by_id(goal_id)
        if not goal:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete goal '{goal.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            GoalOperations.delete(goal_id)
            self._load_data()
            self.status_label.setText("Goal deleted")

    def _import_transactions(self):
        """Show import transactions dialog."""
        dialog = ImportTransactionsDialog(self)
        if dialog.exec():
            self._load_data()
            self.status_label.setText("Transactions imported successfully")

    def _add_transaction(self):
        """Show add transaction dialog."""
        dialog = AddTransactionDialog(self)
        if dialog.exec():
            self._load_data()
            self.status_label.setText("Transaction added successfully")

    def _edit_selected_transaction(self):
        """Edit the currently selected transaction."""
        txn_id = self.transaction_table.get_selected_transaction_id()
        if txn_id:
            self._edit_transaction(txn_id)
        else:
            QMessageBox.information(self, "Edit Transaction", "Please select a transaction to edit.")

    def _edit_transaction(self, transaction_id: int):
        """Show edit dialog for a transaction."""
        txn = TransactionOperations.get_by_id(transaction_id)
        if txn:
            dialog = AddTransactionDialog(self, txn)
            if dialog.exec():
                self._load_data()
                self.status_label.setText("Transaction updated successfully")

    def _delete_selected_transaction(self):
        """Delete the currently selected transaction."""
        txn_id = self.transaction_table.get_selected_transaction_id()
        if txn_id:
            self._delete_transaction(txn_id)
        else:
            QMessageBox.information(self, "Delete Transaction", "Please select a transaction to delete.")

    def _delete_transaction(self, transaction_id: int):
        """Delete a transaction after confirmation."""
        txn = TransactionOperations.get_by_id(transaction_id)
        if not txn:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete '{txn.description}' (${txn.amount:,.2f})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            TransactionOperations.delete(transaction_id)
            self._load_data()
            self.status_label.setText("Transaction deleted")

    def _edit_current_item(self):
        """Edit the current item based on active tab."""
        current_tab = self.main_tabs.currentIndex()
        if current_tab == 1:  # Assets tab
            self._edit_selected_asset()
        elif current_tab == 2:  # Liabilities tab
            self._edit_selected_liability()
        elif current_tab == 3:  # Income tab
            self._edit_selected_income()
        elif current_tab == 4:  # Expenses tab
            self._edit_selected_expense()
        elif current_tab == 5:  # Transactions tab
            self._edit_selected_transaction()

    def _delete_current_item(self):
        """Delete the current item based on active tab."""
        current_tab = self.main_tabs.currentIndex()
        if current_tab == 1:  # Assets tab
            self._delete_selected_asset()
        elif current_tab == 2:  # Liabilities tab
            self._delete_selected_liability()
        elif current_tab == 3:  # Income tab
            self._delete_selected_income()
        elif current_tab == 4:  # Expenses tab
            self._delete_selected_expense()
        elif current_tab == 5:  # Transactions tab
            self._delete_selected_transaction()

    def _refresh_prices(self):
        """Trigger a manual price refresh."""
        self.status_label.setText("Updating prices...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.updater.update_now()

    def _on_price_updated(self, asset_id: int, new_price: float):
        """Handle price update for a single asset."""
        self.asset_table.update_asset_price(asset_id, new_price)

    def _on_update_complete(self):
        """Handle completion of price update."""
        self.progress_bar.setVisible(False)
        self._load_data()

        from datetime import datetime
        self.last_update_label.setText(
            f"Last updated: {datetime.now().strftime('%H:%M:%S')}"
        )
        self.status_label.setText("Prices updated")

    def _on_update_error(self, error: str):
        """Handle price update error."""
        self.statusbar.showMessage(f"Update error: {error}", 5000)

    def _on_update_progress(self, current: int, total: int):
        """Handle update progress."""
        if total > 0:
            self.progress_bar.setValue(int(current / total * 100))

    def _export_to_excel(self):
        """Export portfolio to Excel."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export to Excel",
            "portfolio_report.xlsx",
            "Excel Files (*.xlsx)"
        )

        if filename:
            try:
                assets = AssetOperations.get_all()
                summary = AssetOperations.get_portfolio_summary()

                exporter = ExcelExporter()
                exporter.export(filename, assets, summary)

                self.status_label.setText(f"Exported to {filename}")
                QMessageBox.information(
                    self, "Export Complete",
                    f"Portfolio exported to:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error",
                    f"Failed to export: {str(e)}"
                )

    def _show_analysis_report(self):
        """Show comprehensive financial analysis report."""
        dialog = AnalysisReportDialog(self)
        dialog.exec()

    def _show_debt_simulation(self):
        """Show debt payoff simulation wizard."""
        wizard = DebtPayoffSimulationWizard(self)
        wizard.exec()

    def _show_settings(self):
        """Show settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Apply new settings
            self.updater.stop()
            self._start_updates()

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self, "About Asset Tracker",
            "<h3>Asset Tracker v1.0</h3>"
            "<p>Track your precious metals, stocks, and real estate investments.</p>"
            "<p>Features:</p>"
            "<ul>"
            "<li>Real-time price updates from Yahoo Finance</li>"
            "<li>Portfolio visualization with charts</li>"
            "<li>Excel export for reporting</li>"
            "</ul>"
            "<p><small>Prices are for informational purposes only.</small></p>"
        )

    def closeEvent(self, event):
        """Handle window close."""
        self.updater.stop()
        event.accept()
