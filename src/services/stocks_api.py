"""Stock/securities price fetcher using Yahoo Finance."""

from datetime import datetime
from typing import Dict, Optional
import yfinance as yf
from .price_fetcher import PriceFetcher, PriceResult


class StocksAPI(PriceFetcher):
    """Fetch stock prices from Yahoo Finance."""

    def __init__(self):
        self._cache = {}  # Simple cache to reduce API calls

    def get_price(self, symbol: str) -> PriceResult:
        """Fetch the current price for a stock symbol."""
        symbol_upper = symbol.upper()

        try:
            ticker = yf.Ticker(symbol_upper)
            data = ticker.history(period='1d')

            if data.empty:
                # Try getting info as fallback
                info = ticker.info
                if 'regularMarketPrice' in info:
                    price = float(info['regularMarketPrice'])
                else:
                    return PriceResult(
                        symbol=symbol,
                        price=0.0,
                        success=False,
                        error=f"No data found for {symbol}"
                    )
            else:
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
        """Fetch prices for multiple stock symbols efficiently."""
        results = {}

        if not symbols:
            return results

        try:
            # Use yfinance's batch download for efficiency
            symbols_str = ' '.join([s.upper() for s in symbols])
            data = yf.download(symbols_str, period='1d', progress=False, threads=True)

            if len(symbols) == 1:
                # Single symbol returns different structure
                symbol = symbols[0].upper()
                if not data.empty:
                    price = float(data['Close'].iloc[-1])
                    results[symbols[0]] = PriceResult(
                        symbol=symbols[0],
                        price=price,
                        currency="USD",
                        source="Yahoo Finance",
                        timestamp=datetime.now().isoformat(),
                        success=True
                    )
                else:
                    results[symbols[0]] = self.get_price(symbols[0])
            else:
                # Multiple symbols
                for symbol in symbols:
                    symbol_upper = symbol.upper()
                    try:
                        if symbol_upper in data['Close'].columns:
                            price = float(data['Close'][symbol_upper].iloc[-1])
                            results[symbol] = PriceResult(
                                symbol=symbol,
                                price=price,
                                currency="USD",
                                source="Yahoo Finance",
                                timestamp=datetime.now().isoformat(),
                                success=True
                            )
                        else:
                            results[symbol] = self.get_price(symbol)
                    except Exception:
                        results[symbol] = self.get_price(symbol)

        except Exception as e:
            # Fall back to individual fetches
            for symbol in symbols:
                results[symbol] = self.get_price(symbol)

        return results

    def is_valid_symbol(self, symbol: str) -> bool:
        """Check if a symbol is a valid stock ticker."""
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info
            return 'symbol' in info or 'shortName' in info
        except Exception:
            return False

    def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """Get detailed information about a stock."""
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info
            return {
                'symbol': info.get('symbol', symbol),
                'name': info.get('shortName', info.get('longName', '')),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'dividend_yield': info.get('dividendYield', 0),
                '52_week_high': info.get('fiftyTwoWeekHigh', 0),
                '52_week_low': info.get('fiftyTwoWeekLow', 0),
            }
        except Exception:
            return None

    def search_symbol(self, query: str) -> list:
        """Search for stock symbols matching a query."""
        try:
            ticker = yf.Ticker(query.upper())
            info = ticker.info
            if 'symbol' in info:
                return [{
                    'symbol': info.get('symbol'),
                    'name': info.get('shortName', info.get('longName', ''))
                }]
            return []
        except Exception:
            return []
