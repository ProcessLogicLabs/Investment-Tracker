#!/usr/bin/env python3
"""Asset Tracker - Track precious metals, securities, and real estate investments."""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.gui.main_window import MainWindow


def main():
    """Run the Asset Tracker application."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Asset Tracker")
    app.setOrganizationName("AssetTracker")
    
    app.setApplicationVersion("1.0.0")

    # Set application style
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
