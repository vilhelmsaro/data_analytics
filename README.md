# Data Analyzer

Internal tool for analyzing tabular data from CSV or Excel files. Upload a file, explore the data, run basic analytics, and export filtered results or a simple report.

## Stack

- **Python 3.9+**
- **Streamlit**: web UI
- **Pandas**: data loading, filtering, and analytics
- **OpenPyXL**: Excel read/write
- **FPDF2**: PDF report generation
- **Matplotlib**: chart images embedded in PDF reports

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

With optional server settings from `.env` (copy the example first if you want to customize port or other Streamlit server options):

```bash
cp .env.example .env   # optional; Streamlit defaults work if you skip this
set -a && source .env && set +a && streamlit run app.py
```

Or without `.env`:

```bash
streamlit run app.py
```

Open the URL shown in the terminal (usually `http://localhost:8501`).

## Usage

1. Upload any CSV or Excel file via the sidebar.
2. Apply filters on categorical columns (when available) and an optional date range.
   - Clearing all options in a multiselect includes every value (same as selecting all).
3. Explore tabs:
   - **Overview**: schema, missing values, sorted data preview (expandable full table)
   - **Analytics**: numeric and categorical summary stats, top/bottom rows, group-by chart, daily or monthly time series (when a date column exists)
   - **Insights**: auto-generated bullet points from the uploaded columns
   - **Export**: download filtered CSV, Excel, Markdown report, or PDF report
4. Use sidebar controls to choose a numeric metric, grouping category, and table sort order.

## Features

- [x] File upload (CSV, Excel)
- [x] Data preview (first rows, columns, row/column counts, dtypes, missing values)
- [x] Summary statistics
- [x] Top / worst values by selected metric
- [x] Grouping by selected category
- [x] Time dynamics (daily or monthly line chart when a date column exists)
- [x] Filtering and sorting
- [x] Metric and category selection for analysis
- [x] Auto-generated insights
- [x] Export: filtered CSV, Excel, Markdown report, and PDF report (see [PDF export](#pdf-export))

## Limitations

- Single-user session tool; no authentication
- Data is not persisted to a database
- Streamlit reruns the full script on each interaction (fine for datasets around a few hundred rows); a production deployment would likely need a different UI stack or performance tuning for larger files
- Column types are inferred automatically; unusual formats may need cleanup in the source file

## PDF export

The PDF report is a multi-page document built from the current filters and analysis settings. See the **Export** tab in the app to download it.

### Included today

- Report metadata (title, timestamp, row/column counts, page numbers)
- Active filters and analysis settings (metric, group-by)
- Key aggregates (total and average for the selected metric)
- Data preview table (first rows)
- Bar chart for the selected metric by category
- Monthly time-series line chart (when a date column exists)
- Key insights as bullet points

### Possible PDF enhancements

- Branding (logo, color theme, cover section)
- Summary-statistics tables (the numeric/categorical `describe()` tables from the Analytics tab)
- Daily time-series chart (the UI supports daily or monthly; the PDF is monthly only today)

## Future improvements

Possible next steps for the application:

- Unit tests for filter, insight, and report generation logic
- Split `app.py` into modules as the app grows
- Deploy to Streamlit Cloud or another hosting option
- Optimizations for much larger files (chunked reads, smarter caching)

## Project structure

```
.
├── app.py
├── .env.example
├── requirements.txt
├── README.md
└── .gitignore
```
