"""Main application window for Asset Tracker."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QToolBar, QStatusBar, QMessageBox, QFileDialog, QProgressBar,
    QLabel
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon

from ..database.models import init_database
from ..database.operations import AssetOperations, PriceHistoryOperations, SettingsOperations
from ..services.updater import ScheduledUpdater
from .widgets.asset_table import AssetTableWidget
from .widgets.summary_panel import SummaryPanel
from .widgets.charts import ChartWidget
from .dialogs.add_asset import AddAssetDialog
from .dialogs.settings import SettingsDialog
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

        # Summary panel at top
        self.summary_panel = SummaryPanel()
        main_layout.addWidget(self.summary_panel)

        # Splitter for table and charts
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Asset table (left side)
        self.asset_table = AssetTableWidget()
        self.splitter.addWidget(self.asset_table)

        # Charts (right side)
        self.chart_widget = ChartWidget()
        self.splitter.addWidget(self.chart_widget)

        # Set splitter sizes (60% table, 40% charts)
        self.splitter.setSizes([600, 400])

        main_layout.addWidget(self.splitter)

    def _setup_menu(self):
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

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
        edit_action.setShortcut("Ctrl+E")
        edit_action.triggered.connect(self._edit_selected_asset)
        asset_menu.addAction(edit_action)

        delete_action = QAction("&Delete Asset", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self._delete_selected_asset)
        asset_menu.addAction(delete_action)

        asset_menu.addSeparator()

        refresh_action = QAction("&Refresh Prices", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_prices)
        asset_menu.addAction(refresh_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        toggle_charts_action = QAction("Show &Charts", self)
        toggle_charts_action.setCheckable(True)
        toggle_charts_action.setChecked(True)
        toggle_charts_action.triggered.connect(self._toggle_charts)
        view_menu.addAction(toggle_charts_action)
        self.toggle_charts_action = toggle_charts_action

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

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
        self.addToolBar(toolbar)

        add_action = QAction("Add Asset", self)
        add_action.triggered.connect(self._add_asset)
        toolbar.addAction(add_action)

        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(self._edit_selected_asset)
        toolbar.addAction(edit_action)

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._delete_selected_asset)
        toolbar.addAction(delete_action)

        toolbar.addSeparator()

        refresh_action = QAction("Refresh Prices", self)
        refresh_action.triggered.connect(self._refresh_prices)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

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

        # Updater signals
        self.updater.connect_price_updated(self._on_price_updated)
        self.updater.connect_update_complete(self._on_update_complete)
        self.updater.connect_update_error(self._on_update_error)
        self.updater.connect_progress(self._on_update_progress)

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
        assets = AssetOperations.get_all()
        self.asset_table.set_assets(assets)

        summary = AssetOperations.get_portfolio_summary()
        self.summary_panel.update_summary(summary)

        history = PriceHistoryOperations.get_portfolio_history(30)
        self.chart_widget.update_charts(summary, assets, history)

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

    def _toggle_charts(self, checked: bool):
        """Toggle charts panel visibility."""
        self.chart_widget.setVisible(checked)

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

    def _show_settings(self):
        """Show settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Apply new settings
            self.updater.stop()
            self._start_updates()

            # Update charts visibility
            show_charts = SettingsOperations.get('show_charts', 'true') == 'true'
            self.chart_widget.setVisible(show_charts)
            self.toggle_charts_action.setChecked(show_charts)

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
