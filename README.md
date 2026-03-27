# Financial Statement Analyzer

A Streamlit web app that ingests financial statements from Excel, CSV, basic PDF exports, or Yahoo Finance ticker data and produces:

- Key accounting ratios
- Multi-period trend analysis
- Interactive dashboards
- Analyst-style narrative highlights

## Features

- Upload `.xlsx`, `.xls`, `.csv`, or `.pdf`
- Enter a stock ticker to pull financial statements and investor-facing market data from Yahoo Finance
- Parse common financial line items across income statement and balance sheet data
- Calculate ROA, ROE, current ratio, debt-to-equity, gross margin, net margin, asset turnover, and more
- Visualize historical trends with Plotly
- Review a normalized data table and downloadable ratio output

## Expected spreadsheet format

The easiest supported format is a table with:

- `statement`: `income_statement`, `balance_sheet`, or `cash_flow`
- `line_item`: account name such as `Revenue`, `Net Income`, `Total Assets`
- One column per period such as `2022`, `2023`, `2024`

Example:

```csv
statement,line_item,2022,2023,2024
income_statement,Revenue,1250000,1410000,1565000
income_statement,Net Income,118000,134000,162000
balance_sheet,Total Assets,980000,1105000,1230000
balance_sheet,Shareholders Equity,420000,470000,550000
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy as a website

### Option 1: Streamlit Community Cloud

Best if you want the fastest hosted version and are fine connecting a GitHub repo.

1. Put this project in a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Choose your repo and branch
4. Set the main file path to `app.py`
5. Deploy

### Option 2: Render or Railway with Docker

This repo includes a [Dockerfile](C:\Users\selen\Desktop\codex\Dockerfile) so you can deploy it as a normal web service.

For Render:

1. Create a new Web Service from your GitHub repo
2. Select `Docker` as the environment
3. Render will detect the Dockerfile automatically
4. Deploy

For Railway:

1. Create a new project from your GitHub repo
2. Railway will detect the Dockerfile
3. Deploy

### Notes

- Streamlit runs on port `8501` locally
- In hosted environments, the app reads the platform `PORT` variable automatically
- Yahoo Finance mode requires internet access from the deployed host
- PDF uploads work after dependencies install from `requirements.txt`

## Yahoo Finance mode

The app can also analyze a public ticker symbol, such as `AAPL`, `MSFT`, or `NVDA`, using the `yfinance` package.

Note: according to the current `yfinance` documentation and PyPI page, the library is an open-source wrapper around Yahoo Finance public endpoints and the data is intended for research/educational and personal-use contexts. See:

- [yfinance docs](https://ranaroussi.github.io/yfinance/index.html)
- [yfinance on PyPI](https://pypi.org/project/yfinance/)

## Sample data

Use [sample_financials.csv](C:\Users\selen\Desktop\codex\sample_financials.csv) to test the app quickly.
