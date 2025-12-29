"""Chart widgets for visualizing portfolio data."""

from typing import Dict, List, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QSizePolicy,
    QComboBox, QLabel, QPushButton, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime


class MplCanvas(FigureCanvas):
    """Matplotlib canvas for embedding in PyQt."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 150)
        self.updateGeometry()

    def resizeEvent(self, event):
        """Handle resize events to redraw the figure."""
        super().resizeEvent(event)
        self.fig.tight_layout()
        self.draw()


class AllocationPieChart(QWidget):
    """Pie chart showing asset allocation by type."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = MplCanvas(self, width=5, height=4)
        layout.addWidget(self.canvas)

    def update_chart(self, by_type: Dict[str, Dict[str, Any]]):
        """Update the pie chart with allocation data."""
        self.canvas.axes.clear()

        if not by_type:
            self.canvas.axes.text(
                0.5, 0.5, 'No data available',
                ha='center', va='center', transform=self.canvas.axes.transAxes
            )
            self.canvas.draw()
            return

        # Prepare data
        labels = []
        sizes = []
        colors = ['#FFD700', '#4169E1', '#32CD32', '#808080']  # Gold, Blue, Green, Gray
        type_names = {
            'metal': 'Precious Metals',
            'stock': 'Securities',
            'realestate': 'Real Estate',
            'other': 'Other'
        }

        for asset_type, data in by_type.items():
            value = data.get('current_value', 0)
            if value > 0:
                labels.append(type_names.get(asset_type, asset_type))
                sizes.append(value)

        if not sizes:
            self.canvas.axes.text(
                0.5, 0.5, 'No valued assets',
                ha='center', va='center', transform=self.canvas.axes.transAxes
            )
            self.canvas.draw()
            return

        # Create pie chart
        wedges, texts, autotexts = self.canvas.axes.pie(
            sizes,
            labels=labels,
            autopct='%1.1f%%',
            colors=colors[:len(sizes)],
            startangle=90
        )

        self.canvas.axes.set_title('Asset Allocation')
        self.canvas.fig.tight_layout()
        self.canvas.draw()


class PerformanceBarChart(QWidget):
    """Bar chart showing individual asset performance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = MplCanvas(self, width=6, height=4)
        layout.addWidget(self.canvas)

    def update_chart(self, assets: List[Any]):
        """Update the bar chart with asset performance data."""
        self.canvas.axes.clear()

        if not assets:
            self.canvas.axes.text(
                0.5, 0.5, 'No data available',
                ha='center', va='center', transform=self.canvas.axes.transAxes
            )
            self.canvas.draw()
            return

        # Prepare data - show top 10 by absolute gain/loss
        sorted_assets = sorted(assets, key=lambda a: abs(a.gain_loss), reverse=True)[:10]

        names = [a.name[:15] + '...' if len(a.name) > 15 else a.name for a in sorted_assets]
        gains = [a.gain_loss_percent for a in sorted_assets]
        colors = ['#2e7d32' if g >= 0 else '#c62828' for g in gains]

        # Create horizontal bar chart
        y_pos = range(len(names))
        self.canvas.axes.barh(y_pos, gains, color=colors)
        self.canvas.axes.set_yticks(y_pos)
        self.canvas.axes.set_yticklabels(names)
        self.canvas.axes.set_xlabel('Gain/Loss %')
        self.canvas.axes.set_title('Asset Performance (Top 10)')
        self.canvas.axes.axvline(x=0, color='black', linewidth=0.5)

        self.canvas.fig.tight_layout()
        self.canvas.draw()


class ValueHistoryChart(QWidget):
    """Line chart showing portfolio value over time."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = MplCanvas(self, width=6, height=4)
        layout.addWidget(self.canvas)

    def update_chart(self, history: List[Dict[str, Any]]):
        """Update the line chart with historical data."""
        self.canvas.axes.clear()

        if not history:
            self.canvas.axes.text(
                0.5, 0.5, 'No historical data available',
                ha='center', va='center', transform=self.canvas.axes.transAxes
            )
            self.canvas.draw()
            return

        dates = [h['date'] for h in history]
        values = [h['value'] for h in history]

        self.canvas.axes.plot(dates, values, 'b-', linewidth=2, marker='o', markersize=4)
        self.canvas.axes.fill_between(dates, values, alpha=0.3)
        self.canvas.axes.set_xlabel('Date')
        self.canvas.axes.set_ylabel('Portfolio Value ($)')
        self.canvas.axes.set_title('Portfolio Value History')

        # Rotate x-axis labels for readability
        self.canvas.axes.tick_params(axis='x', rotation=45)

        self.canvas.fig.tight_layout()
        self.canvas.draw()


class SpotPriceWorker(QThread):
    """Worker thread to fetch historical spot prices."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, metals: List[str], period: str = "10y"):
        super().__init__()
        self.metals = metals
        self.period = period

    def run(self):
        """Fetch historical data for all selected metals."""
        try:
            from ...services.metals_api import MetalsAPI
            api = MetalsAPI()
            results = {}

            for metal in self.metals:
                data = api.get_historical_prices(metal, self.period)
                if data.get('success') or data.get('dates'):
                    results[metal] = data

            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class SpotPriceHistoryChart(QWidget):
    """Line chart showing historical spot prices for precious metals over 10 years."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.worker = None
        self.historical_data = {}
        self._secondary_axis = None  # Track secondary axis for proper cleanup
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI with controls and chart."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Controls row
        controls = QHBoxLayout()

        # Metal selection checkboxes
        controls.addWidget(QLabel("Metals:"))

        self.gold_check = QCheckBox("Gold")
        self.gold_check.setChecked(True)
        self.gold_check.stateChanged.connect(self._update_chart_display)
        controls.addWidget(self.gold_check)

        self.silver_check = QCheckBox("Silver")
        self.silver_check.setChecked(True)
        self.silver_check.stateChanged.connect(self._update_chart_display)
        controls.addWidget(self.silver_check)

        self.platinum_check = QCheckBox("Platinum")
        self.platinum_check.stateChanged.connect(self._update_chart_display)
        controls.addWidget(self.platinum_check)

        self.palladium_check = QCheckBox("Palladium")
        self.palladium_check.stateChanged.connect(self._update_chart_display)
        controls.addWidget(self.palladium_check)

        controls.addStretch()

        # Period selector
        controls.addWidget(QLabel("Period:"))
        self.period_combo = QComboBox()
        self.period_combo.addItem("1 Year", "1y")
        self.period_combo.addItem("2 Years", "2y")
        self.period_combo.addItem("5 Years", "5y")
        self.period_combo.addItem("10 Years", "10y")
        self.period_combo.addItem("Max", "max")
        self.period_combo.setCurrentIndex(3)  # Default to 10 years
        self.period_combo.currentIndexChanged.connect(self._on_period_changed)
        controls.addWidget(self.period_combo)

        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.fetch_data)
        controls.addWidget(self.refresh_btn)

        layout.addLayout(controls)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)

        # Chart canvas
        self.canvas = MplCanvas(self, width=8, height=5)
        layout.addWidget(self.canvas)

    def _get_selected_metals(self) -> List[str]:
        """Get list of selected metal symbols."""
        metals = []
        if self.gold_check.isChecked():
            metals.append("GOLD")
        if self.silver_check.isChecked():
            metals.append("SILVER")
        if self.platinum_check.isChecked():
            metals.append("PLATINUM")
        if self.palladium_check.isChecked():
            metals.append("PALLADIUM")
        return metals

    def _on_period_changed(self):
        """Handle period change - refetch data."""
        self.fetch_data()

    def fetch_data(self):
        """Fetch historical data from API."""
        metals = self._get_selected_metals()
        if not metals:
            self.status_label.setText("Please select at least one metal")
            return

        period = self.period_combo.currentData()
        self.status_label.setText(f"Fetching {period} historical data...")
        self.refresh_btn.setEnabled(False)

        # Start worker thread
        self.worker = SpotPriceWorker(metals, period)
        self.worker.finished.connect(self._on_data_received)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_data_received(self, data: Dict):
        """Handle received historical data."""
        self.historical_data = data
        self.refresh_btn.setEnabled(True)

        if data:
            self.status_label.setText(f"Data loaded for {', '.join(data.keys())}")
        else:
            self.status_label.setText("No data received")

        self._update_chart_display()

    def _on_error(self, error_msg: str):
        """Handle fetch error."""
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error_msg}")

    def _update_chart_display(self):
        """Update the chart with current data and selections."""
        # Clear the figure completely to remove any secondary axes
        self.canvas.fig.clear()
        self.canvas.axes = self.canvas.fig.add_subplot(111)
        self._secondary_axis = None

        if not self.historical_data:
            self.canvas.axes.text(
                0.5, 0.5, 'Click "Refresh" to load historical spot prices',
                ha='center', va='center', transform=self.canvas.axes.transAxes,
                fontsize=12
            )
            self.canvas.draw()
            return

        selected = self._get_selected_metals()
        if not selected:
            self.canvas.axes.text(
                0.5, 0.5, 'Select at least one metal to display',
                ha='center', va='center', transform=self.canvas.axes.transAxes
            )
            self.canvas.draw()
            return

        # Color map for metals
        colors = {
            'GOLD': '#FFD700',
            'SILVER': '#C0C0C0',
            'PLATINUM': '#E5E4E2',
            'PALLADIUM': '#CED0DD'
        }
        line_colors = {
            'GOLD': '#DAA520',
            'SILVER': '#708090',
            'PLATINUM': '#8B8682',
            'PALLADIUM': '#9090A0'
        }

        # Determine if we need dual y-axis (gold/platinum vs silver/palladium price ranges differ significantly)
        has_gold_platinum = any(m in selected for m in ['GOLD', 'PLATINUM', 'PALLADIUM'])
        has_silver = 'SILVER' in selected

        ax1 = self.canvas.axes
        ax2 = None

        if has_gold_platinum and has_silver:
            ax2 = ax1.twinx()
            self._secondary_axis = ax2

        plotted = False
        for metal in selected:
            if metal not in self.historical_data:
                continue

            data = self.historical_data[metal]
            if not data.get('dates') or not data.get('prices'):
                continue

            # Parse dates
            dates = [datetime.strptime(d, '%Y-%m-%d') for d in data['dates']]
            prices = data['prices']

            # Choose axis
            if metal == 'SILVER' and ax2 is not None:
                ax = ax2
                ax.plot(dates, prices, color=line_colors.get(metal, 'gray'),
                       label=f"{metal} (right axis)", linewidth=1.5)
                ax.set_ylabel('Silver Price ($/oz)', color=line_colors['SILVER'])
                ax.tick_params(axis='y', labelcolor=line_colors['SILVER'])
            else:
                ax1.plot(dates, prices, color=line_colors.get(metal, 'blue'),
                        label=metal, linewidth=1.5)

            plotted = True

        if not plotted:
            self.canvas.axes.text(
                0.5, 0.5, 'No data available for selected metals',
                ha='center', va='center', transform=self.canvas.axes.transAxes
            )
            self.canvas.draw()
            return

        # Format axes
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Price ($/oz)')
        ax1.set_title('Historical Precious Metal Spot Prices')

        # Format x-axis dates
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax1.xaxis.set_major_locator(mdates.YearLocator())
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Add legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        if ax2:
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        else:
            ax1.legend(loc='upper left')

        # Add grid
        ax1.grid(True, alpha=0.3)

        self.canvas.fig.tight_layout()
        self.canvas.draw()


class ChartWidget(QWidget):
    """Tabbed widget containing all charts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the chart tabs."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.allocation_chart = AllocationPieChart()
        self.tabs.addTab(self.allocation_chart, "Allocation")

        self.performance_chart = PerformanceBarChart()
        self.tabs.addTab(self.performance_chart, "Performance")

        self.history_chart = ValueHistoryChart()
        self.tabs.addTab(self.history_chart, "Portfolio History")

        self.spot_price_chart = SpotPriceHistoryChart()
        self.tabs.addTab(self.spot_price_chart, "Spot Prices (10yr)")

        layout.addWidget(self.tabs)

    def update_charts(self, summary: Dict[str, Any], assets: List[Any], history: List[Dict[str, Any]]):
        """Update all charts with new data."""
        self.allocation_chart.update_chart(summary.get('by_type', {}))
        self.performance_chart.update_chart(assets)
        self.history_chart.update_chart(history)

    def refresh_spot_prices(self):
        """Trigger a refresh of spot price history."""
        self.spot_price_chart.fetch_data()
