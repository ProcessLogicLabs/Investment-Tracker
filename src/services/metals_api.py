"""Precious metals price fetcher using Yahoo Finance."""

from datetime import datetime
from typing import Dict
import yfinance as yf
from .price_fetcher import PriceFetcher, PriceResult


# Yahoo Finance symbols for precious metals
METAL_SYMBOLS = {
    'GOLD': 'GC=F',      # Gold Futures
    'XAU': 'GC=F',       # Gold (alternate)
    'SILVER': 'SI=F',    # Silver Futures
    'XAG': 'SI=F',       # Silver (alternate)
    'PLATINUM': 'PL=F',  # Platinum Futures
    'XPT': 'PL=F',       # Platinum (alternate)
    'PALLADIUM': 'PA=F', # Palladium Futures
    'XPD': 'PA=F',       # Palladium (alternate)
}

# Per-ounce divisors (futures contracts are per oz already)
METAL_NAMES = {
    'GC=F': 'Gold',
    'SI=F': 'Silver',
    'PL=F': 'Platinum',
    'PA=F': 'Palladium',
}


class MetalsAPI(PriceFetcher):
    """Fetch precious metals prices from Yahoo Finance."""

    def __init__(self):
        self.symbol_map = METAL_SYMBOLS

    def get_price(self, symbol: str) -> PriceResult:
        """Fetch the current price for a metal symbol."""
        symbol_upper = symbol.upper()

        # Map common names to Yahoo Finance symbols
        yf_symbol = self.symbol_map.get(symbol_upper, symbol_upper)

        try:
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(period='1d')

            if data.empty:
                return PriceResult(
                    symbol=symbol,
                    price=0.0,
                    success=False,
                    error=f"No data found for {symbol}"
                )

            price = float(data['Close'].iloc[-1])

            return PriceResult(
                symbol=symbol,
                price=price,
                currency="USD",
                source="Yahoo Finance",
                timestamp=datetime.now().isoformat(),
                success=True
            )

        except Exception as e:
            return PriceResult(
                symbol=symbol,
                price=0.0,
                success=False,
                error=str(e)
            )

    def get_multiple_prices(self, symbols: list) -> Dict[str, PriceResult]:
        """Fetch prices for multiple metal symbols."""
        results = {}
        for symbol in symbols:
            results[symbol] = self.get_price(symbol)
        return results

    def is_valid_symbol(self, symbol: str) -> bool:
        """Check if a symbol is a valid metal symbol."""
        symbol_upper = symbol.upper()
        return symbol_upper in self.symbol_map or symbol_upper in METAL_NAMES

    @staticmethod
    def get_available_metals() -> Dict[str, str]:
        """Get list of available metal symbols and names."""
        return {
            'GOLD': 'Gold (per oz)',
            'SILVER': 'Silver (per oz)',
            'PLATINUM': 'Platinum (per oz)',
            'PALLADIUM': 'Palladium (per oz)',
        }

    def get_historical_prices(self, symbol: str, period: str = "10y") -> Dict:
        """Fetch historical prices for a metal symbol.

        Args:
            symbol: Metal symbol (GOLD, SILVER, etc.)
            period: Time period - 1y, 2y, 5y, 10y, max

        Returns:
            Dictionary with dates and prices arrays
        """
        symbol_upper = symbol.upper()
        yf_symbol = self.symbol_map.get(symbol_upper, symbol_upper)

        try:
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(period=period)

            if data.empty:
                return {'dates': [], 'prices': [], 'symbol': symbol, 'error': f"No data for {symbol}"}

            # Convert to lists for easy use
            dates = data.index.strftime('%Y-%m-%d').tolist()
            prices = data['Close'].tolist()

            return {
                'dates': dates,
                'prices': prices,
                'symbol': symbol,
                'name': METAL_NAMES.get(yf_symbol, symbol),
                'period': period,
                'success': True
            }

        except Exception as e:
            return {'dates': [], 'prices': [], 'symbol': symbol, 'error': str(e)}
