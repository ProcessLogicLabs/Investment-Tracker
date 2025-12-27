"""Settings dialog for Asset Tracker."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QSpinBox, QCheckBox, QPushButton, QGroupBox, QLabel
)
from ...database.operations import SettingsOperations


class SettingsDialog(QDialog):
    """Dialog for application settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Settings")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        # Update settings group
        update_group = QGroupBox("Price Updates")
        update_layout = QFormLayout(update_group)

        self.auto_update_check = QCheckBox()
        self.auto_update_check.setChecked(True)
        update_layout.addRow("Auto-update prices:", self.auto_update_check)

        self.update_interval_spin = QSpinBox()
        self.update_interval_spin.setRange(1, 60)
        self.update_interval_spin.setValue(5)
        self.update_interval_spin.setSuffix(" minutes")
        update_layout.addRow("Update interval:", self.update_interval_spin)

        self.update_on_start_check = QCheckBox()
        self.update_on_start_check.setChecked(True)
        update_layout.addRow("Update on startup:", self.update_on_start_check)

        layout.addWidget(update_group)

        # Display settings group
        display_group = QGroupBox("Display")
        display_layout = QFormLayout(display_group)

        self.show_charts_check = QCheckBox()
        self.show_charts_check.setChecked(True)
        display_layout.addRow("Show charts panel:", self.show_charts_check)

        self.confirm_delete_check = QCheckBox()
        self.confirm_delete_check.setChecked(True)
        display_layout.addRow("Confirm before delete:", self.confirm_delete_check)

        layout.addWidget(display_group)

        # Info label
        info_label = QLabel(
            "Note: Price data is fetched from Yahoo Finance for metals and stocks. "
            "Real estate values must be entered manually."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(info_label)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def _load_settings(self):
        """Load settings from database."""
        self.auto_update_check.setChecked(
            SettingsOperations.get('auto_update', 'true') == 'true'
        )
        self.update_interval_spin.setValue(
            int(SettingsOperations.get('update_interval', '5'))
        )
        self.update_on_start_check.setChecked(
            SettingsOperations.get('update_on_start', 'true') == 'true'
        )
        self.show_charts_check.setChecked(
            SettingsOperations.get('show_charts', 'true') == 'true'
        )
        self.confirm_delete_check.setChecked(
            SettingsOperations.get('confirm_delete', 'true') == 'true'
        )

    def _save(self):
        """Save settings to database."""
        SettingsOperations.set(
            'auto_update',
            'true' if self.auto_update_check.isChecked() else 'false'
        )
        SettingsOperations.set(
            'update_interval',
            str(self.update_interval_spin.value())
        )
        SettingsOperations.set(
            'update_on_start',
            'true' if self.update_on_start_check.isChecked() else 'false'
        )
        SettingsOperations.set(
            'show_charts',
            'true' if self.show_charts_check.isChecked() else 'false'
        )
        SettingsOperations.set(
            'confirm_delete',
            'true' if self.confirm_delete_check.isChecked() else 'false'
        )

        self.accept()

    def get_update_interval(self) -> int:
        """Get the update interval in minutes."""
        return self.update_interval_spin.value()

    def is_auto_update_enabled(self) -> bool:
        """Check if auto-update is enabled."""
        return self.auto_update_check.isChecked()

    def is_update_on_start_enabled(self) -> bool:
        """Check if update on start is enabled."""
        return self.update_on_start_check.isChecked()

    def is_charts_visible(self) -> bool:
        """Check if charts panel should be visible."""
        return self.show_charts_check.isChecked()

    def is_confirm_delete_enabled(self) -> bool:
        """Check if delete confirmation is enabled."""
        return self.confirm_delete_check.isChecked()
