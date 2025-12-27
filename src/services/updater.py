"""Background price update service for Asset Tracker."""

from datetime import datetime
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from ..database.operations import AssetOperations, PriceHistoryOperations
from ..database.models import Asset
from .metals_api import MetalsAPI
from .stocks_api import StocksAPI
from .realestate_api import RealEstateAPI


class PriceUpdater(QThread):
    """Background thread for updating asset prices."""

    # Signals
    price_updated = pyqtSignal(int, float)  # asset_id, new_price
    update_complete = pyqtSignal()
    update_error = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total

    def __init__(self, parent=None):
        super().__init__(parent)
        self.metals_api = MetalsAPI()
        self.stocks_api = StocksAPI()
        self.realestate_api = RealEstateAPI()
        self._running = False

    def run(self):
        """Execute price updates for all assets."""
        self._running = True
        assets = AssetOperations.get_all()
        total = len(assets)

        for i, asset in enumerate(assets):
            if not self._running:
                break

            self.progress.emit(i + 1, total)

            try:
                new_price = self._fetch_price(asset)
                if new_price is not None and new_price > 0:
                    # Update price in database
                    AssetOperations.update_price(asset.id, new_price)
                    # Record in price history
                    PriceHistoryOperations.add(asset.id, new_price)
                    # Emit signal
                    self.price_updated.emit(asset.id, new_price)

            except Exception as e:
                self.update_error.emit(f"Error updating {asset.name}: {str(e)}")

        self._running = False
        self.update_complete.emit()

    def _fetch_price(self, asset: Asset) -> Optional[float]:
        """Fetch the current price for an asset based on its type."""
        if not asset.symbol:
            return None

        if asset.asset_type == 'metal':
            result = self.metals_api.get_price(asset.symbol)
        elif asset.asset_type == 'stock':
            result = self.stocks_api.get_price(asset.symbol)
        elif asset.asset_type == 'realestate':
            # Real estate prices are manual, skip auto-update
            return None
        else:
            # Try stock API for 'other' types with symbols
            result = self.stocks_api.get_price(asset.symbol)

        if result.success:
            return result.price
        return None

    def stop(self):
        """Stop the update thread."""
        self._running = False


class ScheduledUpdater:
    """Manages scheduled price updates."""

    def __init__(self, interval_minutes: int = 5):
        self.interval_ms = interval_minutes * 60 * 1000
        self.timer = QTimer()
        self.updater: Optional[PriceUpdater] = None
        self._callbacks = {
            'price_updated': [],
            'update_complete': [],
            'update_error': [],
            'progress': []
        }

    def set_interval(self, minutes: int):
        """Set the update interval in minutes."""
        self.interval_ms = minutes * 60 * 1000
        if self.timer.isActive():
            self.timer.setInterval(self.interval_ms)

    def start(self):
        """Start scheduled updates."""
        self.timer.timeout.connect(self._do_update)
        self.timer.start(self.interval_ms)
        # Do an immediate update on start
        self._do_update()

    def stop(self):
        """Stop scheduled updates."""
        self.timer.stop()
        if self.updater and self.updater.isRunning():
            self.updater.stop()
            self.updater.wait()

    def update_now(self):
        """Trigger an immediate update."""
        self._do_update()

    def _do_update(self):
        """Execute an update cycle."""
        if self.updater and self.updater.isRunning():
            return  # Don't start a new update if one is already running

        self.updater = PriceUpdater()

        # Connect signals to callbacks
        for callback in self._callbacks['price_updated']:
            self.updater.price_updated.connect(callback)
        for callback in self._callbacks['update_complete']:
            self.updater.update_complete.connect(callback)
        for callback in self._callbacks['update_error']:
            self.updater.update_error.connect(callback)
        for callback in self._callbacks['progress']:
            self.updater.progress.connect(callback)

        self.updater.start()

    def connect_price_updated(self, callback):
        """Connect a callback to price update events."""
        self._callbacks['price_updated'].append(callback)

    def connect_update_complete(self, callback):
        """Connect a callback to update complete events."""
        self._callbacks['update_complete'].append(callback)

    def connect_update_error(self, callback):
        """Connect a callback to update error events."""
        self._callbacks['update_error'].append(callback)

    def connect_progress(self, callback):
        """Connect a callback to progress events."""
        self._callbacks['progress'].append(callback)
