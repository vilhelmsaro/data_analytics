# Phase 2 Plan — Analytics, Insights, and Final Delivery

Use this document **after Phase 1 (MVP) is complete and working**. Phase 1 should already provide: file upload, Overview tab, light filters, and CSV/Excel export in a single `app.py`.

This phase completes the **full assignment specification** and prepares the repository for submission.

---

## Prerequisites (verify before starting)

- [ ] MVP runs locally: `streamlit run app.py`
- [ ] Upload of `global_brokerage_dataset.xlsx` works
- [ ] Sidebar filters (Region, Asset, date range, transaction type) work
- [ ] Overview tab shows shape, dtypes, null counts, preview
- [ ] Export tab downloads filtered CSV and Excel
- [ ] Changes are committed and pushed to `git@github.com:vilhelmsaro/data_analytics.git`

If any MVP item fails, fix it before continuing.

---

## Assignment requirements covered in Phase 2

| Assignment requirement | Phase 2 deliverable |
|------------------------|---------------------|
| Summary statistics | Analytics tab |
| Top / worst values by metric | Analytics tab |
| Grouping by category | Analytics tab |
| Time dynamics (date column) | Analytics tab |
| Sort table | Overview tab (enhanced) |
| Choose column/metric for analysis | Sidebar selectors |
| Insights (what changed most, etc.) | Insights tab |
| Export simple report | Export tab (text/Markdown report) |
| README: stack, implemented, limitations, improvements | README update |

---

## Step-by-step implementation order

Work in this order. Each step builds on the previous one.

### Step 1 — Add sidebar analysis controls (~15 min)

**Where:** sidebar block in `app.py`, below existing filters (only visible when data is loaded).

**Add these widgets:**

1. **Metric selector** (`st.selectbox`)
   - Label: `Metric for analysis`
   - Options (numeric columns only):
     - `PnL`
     - `Transaction_Value`
     - `Broker_Fee`
     - `Quantity`
     - `Price`
     - `Portfolio_Value`
     - `Risk_Score`

2. **Category selector** (`st.selectbox`)
   - Label: `Group by`
   - Options:
     - `Region`
     - `Asset`
     - `Transaction_Type`
     - `Client_ID`

3. **Sort controls** (`st.selectbox` + `st.radio` or checkbox)
   - Label: `Sort table by`
   - Options: all columns from the dataframe
   - Sort direction: `Ascending` / `Descending`

**Store selections in variables** used by all tabs, e.g. `selected_metric`, `selected_category`, `sort_column`, `sort_ascending`.

**Apply sort** to `filtered_df` before displaying in Overview:

```python
sorted_df = filtered_df.sort_values(sort_column, ascending=sort_ascending)
```

Use `sorted_df` in the Overview preview instead of raw `filtered_df`.

---

### Step 2 — Register new tabs (~5 min)

**Change** the tab definition from MVP (Overview + Export) to:

```python
tab_overview, tab_analytics, tab_insights, tab_export = st.tabs(
    ["Overview", "Analytics", "Insights", "Export"]
)
```

Move existing Overview and Export content into the correct tab blocks. Add empty placeholders for Analytics and Insights.

---

### Step 3 — Build the Analytics tab (~30–40 min)

Inside `with tab_analytics:`

#### 3a. Summary statistics

```python
st.subheader("Summary Statistics")
st.dataframe(filtered_df.describe())
```

Optional: wrap in `st.expander("Full numeric summary")` if the table feels too large.

#### 3b. Top and worst values by selected metric

```python
st.subheader(f"Top 5 by {selected_metric}")
st.dataframe(filtered_df.nlargest(5, selected_metric))

st.subheader(f"Bottom 5 by {selected_metric}")
st.dataframe(filtered_df.nsmallest(5, selected_metric))
```

Show relevant columns only if the full row is too wide (optional): keep `Client_ID`, `Region`, `Asset`, `Transaction_Date`, and the metric.

#### 3c. Group by selected category

```python
st.subheader(f"{selected_metric} by {selected_category}")
grouped = (
    filtered_df.groupby(selected_category)[selected_metric]
    .agg(total="sum", average="mean", count="count")
    .sort_values("total", ascending=False)
)
st.dataframe(grouped)
st.bar_chart(grouped["total"])
```

#### 3d. Time dynamics

Parse dates if not already done in MVP:

```python
filtered_df["Transaction_Date"] = pd.to_datetime(filtered_df["Transaction_Date"])
```

Then:

```python
st.subheader(f"{selected_metric} over time")
time_series = (
    filtered_df.groupby("Transaction_Date")[selected_metric]
    .sum()
    .reset_index()
    .sort_values("Transaction_Date")
)
st.line_chart(time_series, x="Transaction_Date", y=selected_metric)
```

If the date column is missing, show `st.warning("No date column found for time series.")`.

---

### Step 4 — Build the Insights tab (~25–30 min)

Inside `with tab_insights:`

Create a helper function `generate_insights(df) -> list[str]` that returns English bullet strings. Call it on `filtered_df`.

**Implement these insights (minimum 5):**

| # | Insight | Logic |
|---|---------|-------|
| 1 | Best region by PnL | `df.groupby("Region")["PnL"].sum().idxmax()` |
| 2 | Asset with highest avg transaction value | `df.groupby("Asset")["Transaction_Value"].mean().idxmax()` |
| 3 | Buy vs Sell split | `df["Transaction_Type"].value_counts()` → format as percentages |
| 4 | Month with largest PnL change | Group by month, sum PnL, compute month-over-month diff, take max absolute change |
| 5 | Metric that varies most | For numeric cols, compute `std()` or `max - min`, pick highest |
| 6 | Highest broker fee ratio | `(Broker_Fee / Transaction_Value).groupby(Region).mean().idxmax()` |

**Display:**

```python
st.subheader("Key Insights")
insights = generate_insights(filtered_df)
for insight in insights:
    st.markdown(f"- {insight}")
```

Keep insights **deterministic** (no ML, no randomness). Handle empty filtered data with a single message: `No data available for the current filters.`

---

### Step 5 — Enhance the Export tab (~15 min)

Keep existing CSV and Excel download buttons.

**Add a simple text/Markdown report download:**

Build a string report containing:

1. Report title and generation timestamp
2. Dataset shape (`rows x columns`)
3. Active filters (which regions/assets/dates/types are selected)
4. Summary stats for `PnL` and `Transaction_Value` (sum, mean)
5. The same insights from Step 4 (copy the bullet list into the report)

```python
report_text = "\n".join([
    "# Brokerage Data Report",
    f"Generated: {datetime.now():%Y-%m-%d %H:%M}",
    "",
    f"Rows: {len(filtered_df)}",
    "",
    "## Active filters",
    # ... describe filters ...
    "",
    "## Key insights",
    *[f"- {i}" for i in insights],
])
st.download_button(
    label="Download report (.md)",
    data=report_text,
    file_name=f"brokerage_report_{date.today()}.md",
    mime="text/markdown",
)
```

This satisfies the assignment requirement: *"filtered dataset **or** simple report"* — you will offer both.

---

### Step 6 — Update README for final submission (~15 min)

Add or expand these sections in `README.md`:

#### Stack
- Python 3.x, Streamlit, Pandas, OpenPyXL

#### What is implemented (map to assignment)
- [x] File upload (CSV, Excel)
- [x] Data preview (rows, columns, dtypes, nulls)
- [x] Summary statistics
- [x] Top/worst by metric
- [x] Group by category
- [x] Time dynamics
- [x] Filtering and sorting
- [x] Metric/category selection
- [x] Auto-generated insights
- [x] Export: CSV, Excel, Markdown report

#### Limitations
- Single-user, no authentication
- Data lives in session only (not persisted to database)
- Streamlit reruns the full script on each interaction (fine for ~300 rows)
- Insights are rule-based, not ML-based
- Report is Markdown, not PDF

#### What I would improve with more time
- PDF export
- Unit tests for `generate_insights` and filter logic
- Split `app.py` into modules once it grows
- Streamlit Cloud deployment
- Support for much larger files (chunked reads, caching strategy)

---

### Step 7 — Manual testing checklist (~15 min)

Run through every item before committing:

| # | Test | Expected result |
|---|------|-----------------|
| 1 | Upload `.xlsx` | All 4 tabs visible |
| 2 | Change metric to `Broker_Fee` | Top/bottom tables and charts update |
| 3 | Change group-by to `Asset` | Group table and bar chart update |
| 4 | Line chart | Shows daily trend for selected metric |
| 5 | Apply filter (e.g. Region = UAE) | Analytics, insights, and export all reflect filtered rows |
| 6 | Sort by `PnL` descending | Overview table order changes |
| 7 | Insights tab | At least 5 readable English bullets |
| 8 | Download CSV / Excel / report | Files open correctly; row counts match |
| 9 | Upload `.csv` | Still works |
| 10 | Empty filter (select no regions) | Graceful message, no crash |

---

### Step 8 — Git commit and push (~5 min)

```bash
git add app.py README.md
git status
git commit -m "$(cat <<'EOF'
Add analytics, insights, and export report

Complete assignment spec: summary stats, top/worst metrics,
group-by charts, time series, auto insights, and Markdown report.
EOF
)"
git push origin main
```

Use your actual default branch name if it is not `main`.

---

## Final file tree (after Phase 2)

```
.
├── app.py              # single file: MVP + analytics + insights
├── requirements.txt
├── README.md           # full submission README
├── .gitignore
├── PHASE2_PLAN.md      # this guide (optional to commit)
└── venv/               # local only
```

---

## Assignment submission checklist

Before sending the repo to the employer:

- [ ] Git repo is public or access is granted
- [ ] README has clear run instructions (`venv`, `pip install`, `streamlit run`)
- [ ] All UI text is in English
- [ ] App works with the provided `global_brokerage_dataset.xlsx`
- [ ] README describes stack, what was built, limitations, future improvements
- [ ] Latest code is pushed to GitHub

---

## Time budget

| Step | Estimated time |
|------|----------------|
| 1. Sidebar controls | 15 min |
| 2. Tab registration | 5 min |
| 3. Analytics tab | 35 min |
| 4. Insights tab | 25 min |
| 5. Export report | 15 min |
| 6. README | 15 min |
| 7. Testing | 15 min |
| 8. Git push | 5 min |
| **Total** | **~2 hours** |

---

## When you are ready

Tell the agent: **"Execute Phase 2"** or **"Implement according to PHASE2_PLAN.md"** and it will apply these steps to your existing `app.py`.
