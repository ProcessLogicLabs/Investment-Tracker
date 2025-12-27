"""Summary panel widget for portfolio overview."""

from typing import Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class SummaryCard(QFrame):
    """A card widget displaying a summary metric."""

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


class SummaryPanel(QWidget):
    """Panel displaying portfolio summary information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the summary panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)

        # Title
        title = QLabel("Portfolio Summary")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Cards grid
        cards_layout = QGridLayout()
        cards_layout.setSpacing(10)

        # Create summary cards
        self.total_value_card = SummaryCard("Total Value")
        cards_layout.addWidget(self.total_value_card, 0, 0)

        self.total_cost_card = SummaryCard("Total Cost")
        cards_layout.addWidget(self.total_cost_card, 0, 1)

        self.gain_loss_card = SummaryCard("Total Gain/Loss")
        cards_layout.addWidget(self.gain_loss_card, 0, 2)

        self.gain_loss_pct_card = SummaryCard("Return %")
        cards_layout.addWidget(self.gain_loss_pct_card, 0, 3)

        self.asset_count_card = SummaryCard("Total Assets")
        cards_layout.addWidget(self.asset_count_card, 1, 0)

        # Type breakdown cards
        self.metals_card = SummaryCard("Precious Metals")
        cards_layout.addWidget(self.metals_card, 1, 1)

        self.stocks_card = SummaryCard("Securities")
        cards_layout.addWidget(self.stocks_card, 1, 2)

        self.realestate_card = SummaryCard("Real Estate")
        cards_layout.addWidget(self.realestate_card, 1, 3)

        layout.addLayout(cards_layout)

    def update_summary(self, summary: Dict[str, Any]):
        """Update the summary display with new data."""
        # Total Value
        total_value = summary.get('total_value', 0)
        self.total_value_card.set_value(f"${total_value:,.2f}")

        # Total Cost
        total_cost = summary.get('total_cost', 0)
        self.total_cost_card.set_value(f"${total_cost:,.2f}")

        # Gain/Loss
        gain_loss = summary.get('total_gain_loss', 0)
        gl_color = '#2e7d32' if gain_loss >= 0 else '#c62828'
        self.gain_loss_card.set_value(f"${gain_loss:+,.2f}", gl_color)

        # Gain/Loss %
        gain_loss_pct = summary.get('gain_loss_percent', 0)
        self.gain_loss_pct_card.set_value(f"{gain_loss_pct:+.2f}%", gl_color)

        # Asset count
        asset_count = summary.get('total_assets', 0)
        self.asset_count_card.set_value(str(asset_count))

        # Type breakdown
        by_type = summary.get('by_type', {})

        metals = by_type.get('metal', {})
        metals_value = metals.get('current_value', 0)
        self.metals_card.set_value(f"${metals_value:,.2f}")

        stocks = by_type.get('stock', {})
        stocks_value = stocks.get('current_value', 0)
        self.stocks_card.set_value(f"${stocks_value:,.2f}")

        realestate = by_type.get('realestate', {})
        realestate_value = realestate.get('current_value', 0)
        self.realestate_card.set_value(f"${realestate_value:,.2f}")
