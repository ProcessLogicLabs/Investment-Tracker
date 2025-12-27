"""Base price fetcher class for Asset Tracker."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class PriceResult:
    """Result from a price fetch operation."""
    symbol: str
    price: float
    currency: str = "USD"
    source: str = ""
    timestamp: str = ""
    success: bool = True
    error: str = ""


class PriceFetcher(ABC):
    """Abstract base class for price fetchers."""

    @abstractmethod
    def get_price(self, symbol: str) -> PriceResult:
        """Fetch the current price for a symbol."""
        pass

    @abstractmethod
    def get_multiple_prices(self, symbols: list) -> Dict[str, PriceResult]:
        """Fetch prices for multiple symbols."""
        pass

    @abstractmethod
    def is_valid_symbol(self, symbol: str) -> bool:
        """Check if a symbol is valid for this fetcher."""
        pass
