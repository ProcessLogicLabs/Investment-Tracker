"""Real estate valuation service for Asset Tracker.

Note: Real estate values are typically entered manually by the user
since automated valuation APIs (Zillow, Redfin) require API keys
and have usage restrictions. This module provides structure for
manual entry and potential future API integration.
"""

from datetime import datetime
from typing import Dict, Optional
import requests
from bs4 import BeautifulSoup
from .price_fetcher import PriceFetcher, PriceResult


class RealEstateAPI(PriceFetcher):
    """Handle real estate valuations.

    Currently supports manual entry. Future versions could integrate
    with Zillow, Redfin, or other real estate APIs.
    """

    def __init__(self):
        self._manual_values = {}  # Store manual valuations

    def get_price(self, symbol: str) -> PriceResult:
        """Get the current value for a property.

        For real estate, 'symbol' is typically an address or property ID.
        Values are manually entered by the user.
        """
        # Check if we have a manual value stored
        if symbol in self._manual_values:
            return PriceResult(
                symbol=symbol,
                price=self._manual_values[symbol],
                currency="USD",
                source="Manual Entry",
                timestamp=datetime.now().isoformat(),
                success=True
            )

        return PriceResult(
            symbol=symbol,
            price=0.0,
            success=False,
            error="No value set. Real estate values must be entered manually."
        )

    def get_multiple_prices(self, symbols: list) -> Dict[str, PriceResult]:
        """Get values for multiple properties."""
        return {symbol: self.get_price(symbol) for symbol in symbols}

    def is_valid_symbol(self, symbol: str) -> bool:
        """Real estate symbols are always valid (they're addresses/IDs)."""
        return bool(symbol and symbol.strip())

    def set_manual_value(self, symbol: str, value: float):
        """Set a manual valuation for a property."""
        self._manual_values[symbol] = value

    def estimate_from_zillow_url(self, url: str) -> Optional[PriceResult]:
        """Attempt to scrape a Zillow listing for the price.

        Note: This is for educational purposes. Web scraping may violate
        Zillow's terms of service. Use the official Zillow API for production.
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code != 200:
                return PriceResult(
                    symbol=url,
                    price=0.0,
                    success=False,
                    error=f"Failed to fetch page: {response.status_code}"
                )

            soup = BeautifulSoup(response.text, 'html.parser')

            # Try to find price in various locations
            price_element = soup.find('span', {'data-testid': 'price'})
            if price_element:
                price_text = price_element.get_text()
                # Remove $ and commas, convert to float
                price = float(price_text.replace('$', '').replace(',', ''))
                return PriceResult(
                    symbol=url,
                    price=price,
                    currency="USD",
                    source="Zillow (scraped)",
                    timestamp=datetime.now().isoformat(),
                    success=True
                )

            return PriceResult(
                symbol=url,
                price=0.0,
                success=False,
                error="Could not find price on page"
            )

        except Exception as e:
            return PriceResult(
                symbol=url,
                price=0.0,
                success=False,
                error=str(e)
            )

    @staticmethod
    def get_property_types() -> Dict[str, str]:
        """Get list of property types for categorization."""
        return {
            'single_family': 'Single Family Home',
            'condo': 'Condominium',
            'townhouse': 'Townhouse',
            'multi_family': 'Multi-Family',
            'land': 'Land/Lot',
            'commercial': 'Commercial Property',
            'other': 'Other'
        }
