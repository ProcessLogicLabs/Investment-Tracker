# Investment Tracker

A desktop application to track precious metals, securities, and real estate investments with live price updates.

## Features

- **Asset Management**: Track gold, silver, platinum, palladium, stocks, real estate, and other assets
- **Live Price Updates**: Automatic price fetching from Yahoo Finance for metals and stocks
- **Fractional Metal Support**: Track fractional coins (1/10 oz, 1/4 oz, etc.) with proper weight calculations
- **Portfolio Dashboard**: View total value, gain/loss, and allocation breakdown
- **Charts & Visualization**:
  - Asset allocation pie chart
  - Performance bar chart
  - Portfolio value history
  - 10-year historical spot prices for precious metals
- **Excel Export**: Export portfolio data to formatted Excel spreadsheets

## Requirements

- Python 3.10+
- PyQt6
- See `requirements.txt` for full dependencies

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/royalpayne/Investment-Tracker.git
   cd Investment-Tracker
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python main.py
   ```

## Usage

### Adding Assets

1. Click "Add Asset" or use the menu
2. Select asset type (Precious Metal, Stock/Security, Real Estate, Other)
3. Enter name, symbol, quantity, and purchase details
4. For metals, specify weight per unit (e.g., 0.1 for 1/10 oz coins)
5. Use "Lookup" to fetch current market price

### Updating Prices

- Prices update automatically in the background (configurable interval)
- Click "Refresh Prices" for manual update
- View historical spot prices in the "Spot Prices (10yr)" chart tab

### Exporting Data

- File > Export to Excel
- Creates formatted spreadsheet with Summary, Assets, and Allocation sheets

## Project Structure

```
Investment-Tracker/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── src/
│   ├── database/          # SQLite database models and operations
│   ├── gui/               # PyQt6 GUI components
│   │   ├── dialogs/       # Add/Edit asset, Settings dialogs
│   │   └── widgets/       # Table, charts, summary panel
│   ├── services/          # Price fetching APIs
│   └── utils/             # Excel export, configuration
```

## License

MIT License
