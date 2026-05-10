"""Import transactions dialog for CSV bank/card statements."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QLineEdit,
    QMessageBox, QGroupBox, QFormLayout, QHeaderView,
    QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush

from ...utils.csv_importer import parse_csv
from ...database.operations import TransactionOperations


class ImportTransactionsDialog(QDialog):
    """Dialog for importing transactions from CSV files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Transactions")
        self.setMinimumSize(800, 500)
        self._parsed = []
        self._file_path = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # File selection
        file_group = QGroupBox("CSV File")
        file_layout = QHBoxLayout(file_group)

        self.file_label = QLabel("No file selected")
        file_layout.addWidget(self.file_label, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        # Account name
        account_group = QGroupBox("Account")
        account_layout = QFormLayout(account_group)
        self.account_input = QLineEdit()
        self.account_input.setPlaceholderText("e.g. SoFi Checking, Chase Visa")
        account_layout.addRow("Account Name:", self.account_input)
        layout.addWidget(account_group)

        # Preview table
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.status_label = QLabel("Select a CSV file to preview transactions.")
        preview_layout.addWidget(self.status_label)

        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(5)
        self.preview_table.setHorizontalHeaderLabels(
            ['Date', 'Description', 'Category', 'Amount', 'Type']
        )
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setColumnWidth(0, 100)
        self.preview_table.setColumnWidth(1, 250)
        self.preview_table.setColumnWidth(2, 120)
        self.preview_table.setColumnWidth(3, 100)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.import_btn = QPushButton("Import")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._do_import)
        btn_layout.addWidget(self.import_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _browse_file(self):
        """Open file dialog to select a CSV."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "",
            "CSV Files (*.csv *.CSV);;All Files (*)"
        )
        if file_path:
            self._file_path = file_path
            self.file_label.setText(file_path)
            self._parse_file(file_path)

    def _parse_file(self, file_path: str):
        """Parse the selected CSV and populate the preview."""
        account_name = self.account_input.text().strip()
        transactions, fmt = parse_csv(file_path, account_name)

        if not transactions:
            self.status_label.setText("Could not parse file. Unknown format or empty file.")
            self.preview_table.setRowCount(0)
            self.import_btn.setEnabled(False)
            self._parsed = []
            return

        # Auto-fill account name from format if empty
        if not account_name:
            if fmt == 'sofi':
                self.account_input.setText("SoFi Checking")
            elif fmt == 'chase':
                self.account_input.setText("Chase")
            elif fmt == 'fidelity':
                self.account_input.setText("Fidelity 401K")

        # Check for duplicates
        new_txns = []
        dup_count = 0
        for txn in transactions:
            if TransactionOperations.exists(txn.transaction_date, txn.amount, txn.original_description):
                dup_count += 1
            else:
                new_txns.append(txn)

        self._parsed = new_txns

        # Update status
        total = len(transactions)
        new = len(new_txns)
        self.status_label.setText(
            f"Format: {fmt.upper()}  |  "
            f"{total} transactions found  |  "
            f"{new} new, {dup_count} duplicates skipped"
        )

        # Populate preview (show all, but mark duplicates)
        self.preview_table.setRowCount(len(transactions))
        for row, txn in enumerate(transactions):
            is_dup = txn not in new_txns

            date_item = QTableWidgetItem(txn.transaction_date or '')
            self.preview_table.setItem(row, 0, date_item)

            desc = txn.description
            if is_dup:
                desc = f"[DUP] {desc}"
            desc_item = QTableWidgetItem(desc)
            if is_dup:
                desc_item.setForeground(QBrush(QColor('#999999')))
            self.preview_table.setItem(row, 1, desc_item)

            cat_item = QTableWidgetItem(txn.category.title() if txn.category else '')
            self.preview_table.setItem(row, 2, cat_item)

            amt_item = QTableWidgetItem(f"${txn.amount:,.2f}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            color = QColor('#2e7d32') if txn.amount >= 0 else QColor('#c62828')
            if is_dup:
                color = QColor('#999999')
            amt_item.setForeground(QBrush(color))
            self.preview_table.setItem(row, 3, amt_item)

            type_display = txn.transaction_type.replace('_', ' ').title() if txn.transaction_type else ''
            self.preview_table.setItem(row, 4, QTableWidgetItem(type_display))

        self.import_btn.setEnabled(len(new_txns) > 0)

    def _do_import(self):
        """Import the parsed transactions into the database."""
        if not self._parsed:
            return

        # Apply account name from input
        account_name = self.account_input.text().strip()
        if account_name:
            for txn in self._parsed:
                txn.account_name = account_name

        count = TransactionOperations.create_bulk(self._parsed)

        QMessageBox.information(
            self, "Import Complete",
            f"Successfully imported {count} transaction(s)."
        )
        self.accept()
