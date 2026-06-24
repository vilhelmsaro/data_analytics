from datetime import date, datetime
from io import BytesIO
from typing import List, Optional

import pandas as pd
import streamlit as st

NUMERIC_METRICS = [
    "PnL",
    "Transaction_Value",
    "Broker_Fee",
    "Quantity",
    "Price",
    "Portfolio_Value",
    "Risk_Score",
]
CATEGORY_COLUMNS = ["Region", "Asset", "Transaction_Type", "Client_ID"]
DATE_COLUMN = "Transaction_Date"
INSIGHT_NOTE_THRESHOLD = 4


@st.cache_data
def load_data(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    buffer = BytesIO(file_bytes)
    if file_name.lower().endswith(".csv"):
        df = pd.read_csv(buffer)
    elif file_name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(buffer)
    else:
        raise ValueError("Unsupported file type. Please upload a CSV or Excel file.")

    if DATE_COLUMN in df.columns:
        df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN])

    return df


def apply_filters(
    df: pd.DataFrame,
    regions: List[str],
    assets: List[str],
    transaction_types: List[str],
    date_range: tuple,
) -> pd.DataFrame:
    filtered = df.copy()

    if regions and "Region" in filtered.columns:
        filtered = filtered[filtered["Region"].isin(regions)]
    if assets and "Asset" in filtered.columns:
        filtered = filtered[filtered["Asset"].isin(assets)]
    if transaction_types and "Transaction_Type" in filtered.columns:
        filtered = filtered[filtered["Transaction_Type"].isin(transaction_types)]
    if DATE_COLUMN in filtered.columns and len(date_range) == 2:
        start_date = pd.Timestamp(date_range[0])
        end_date = pd.Timestamp(date_range[1])
        filtered = filtered[
            (filtered[DATE_COLUMN] >= start_date) & (filtered[DATE_COLUMN] <= end_date)
        ]

    return filtered


def build_numeric_summary(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    cols = [
        col
        for col in df.columns
        if pd.api.types.is_numeric_dtype(df[col])
        or pd.api.types.is_datetime64_any_dtype(df[col])
    ]
    if not cols:
        return None
    return df[cols].describe()


def build_categorical_summary(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    cols = [
        col
        for col in df.columns
        if pd.api.types.is_object_dtype(df[col])
        or pd.api.types.is_string_dtype(df[col])
        or pd.api.types.is_categorical_dtype(df[col])
    ]
    if not cols:
        return None
    return df[cols].describe()


def largest_monthly_metric_change(df: pd.DataFrame) -> Optional[str]:
    if DATE_COLUMN not in df.columns:
        return None

    numeric_cols = [col for col in NUMERIC_METRICS if col in df.columns]
    if not numeric_cols:
        return None

    best_metric: Optional[str] = None
    best_period = None
    best_value: Optional[float] = None
    best_abs = -1.0

    for metric in numeric_cols:
        monthly = df.groupby(df[DATE_COLUMN].dt.to_period("M"))[metric].sum()
        if len(monthly) <= 1:
            continue
        changes = monthly.diff().dropna()
        if changes.empty:
            continue
        period = changes.abs().idxmax()
        value = float(changes.loc[period])
        if abs(value) > best_abs:
            best_abs = abs(value)
            best_metric = metric
            best_period = period
            best_value = value

    if best_metric is None or best_period is None or best_value is None:
        return None

    return (
        f"Largest month-over-month change by metric: {best_metric} in {best_period} "
        f"({best_value:+,.2f})."
    )


def generate_insights(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return ["No data available for the current filters."]

    insights: List[str] = []

    if "Region" in df.columns and "PnL" in df.columns:
        best_region = df.groupby("Region")["PnL"].sum().idxmax()
        best_pnl = df.groupby("Region")["PnL"].sum().max()
        insights.append(f"Highest total PnL region: {best_region} ({best_pnl:,.2f}).")

    if "Asset" in df.columns and "Transaction_Value" in df.columns:
        best_asset = df.groupby("Asset")["Transaction_Value"].mean().idxmax()
        best_avg = df.groupby("Asset")["Transaction_Value"].mean().max()
        insights.append(
            f"Highest average transaction value asset: {best_asset} ({best_avg:,.2f})."
        )

    if "Transaction_Type" in df.columns:
        counts = df["Transaction_Type"].value_counts(normalize=True) * 100
        parts = [f"{label}: {value:.1f}%" for label, value in counts.items()]
        insights.append(f"Buy vs Sell split: {', '.join(parts)}.")

    if DATE_COLUMN in df.columns and "PnL" in df.columns:
        monthly = df.groupby(df[DATE_COLUMN].dt.to_period("M"))["PnL"].sum()
        if len(monthly) > 1:
            changes = monthly.diff().dropna()
            largest_change_period = changes.abs().idxmax()
            largest_change_value = changes.loc[largest_change_period]
            insights.append(
                f"Largest month-over-month PnL change: {largest_change_period} "
                f"({largest_change_value:+,.2f})."
            )

    cross_metric_change = largest_monthly_metric_change(df)
    if cross_metric_change:
        insights.append(cross_metric_change)

    numeric_cols = [col for col in NUMERIC_METRICS if col in df.columns]
    if numeric_cols:
        variability = df[numeric_cols].std().sort_values(ascending=False)
        top_metric = variability.index[0]
        insights.append(
            f"Metric with highest variability (std dev): {top_metric} "
            f"({variability.iloc[0]:,.2f})."
        )

    if {"Broker_Fee", "Transaction_Value", "Region"}.issubset(df.columns):
        fee_ratio = (
            (df["Broker_Fee"] / df["Transaction_Value"].replace(0, pd.NA))
            .groupby(df["Region"])
            .mean()
            .dropna()
        )
        if not fee_ratio.empty:
            highest_fee_region = fee_ratio.idxmax()
            highest_fee_ratio = fee_ratio.max() * 100
            insights.append(
                f"Highest average broker fee ratio by region: {highest_fee_region} "
                f"({highest_fee_ratio:.2f}% of transaction value)."
            )

    return insights


def build_report(
    df: pd.DataFrame,
    insights: List[str],
    regions: List[str],
    assets: List[str],
    transaction_types: List[str],
    date_range: tuple,
) -> str:
    lines = [
        "# Brokerage Data Report",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"Rows: {len(df)}",
        f"Columns: {len(df.columns)}",
        "",
        "## Active filters",
        f"- Regions: {', '.join(regions) if regions else 'All'}",
        f"- Assets: {', '.join(assets) if assets else 'All'}",
        f"- Transaction types: {', '.join(transaction_types) if transaction_types else 'All'}",
    ]

    if len(date_range) == 2:
        lines.append(f"- Date range: {date_range[0]} to {date_range[1]}")

    lines.extend(["", "## Key aggregates"])
    if "PnL" in df.columns:
        lines.append(f"- Total PnL: {df['PnL'].sum():,.2f}")
        lines.append(f"- Average PnL: {df['PnL'].mean():,.2f}")
    if "Transaction_Value" in df.columns:
        lines.append(f"- Total transaction value: {df['Transaction_Value'].sum():,.2f}")
        lines.append(f"- Average transaction value: {df['Transaction_Value'].mean():,.2f}")

    lines.extend(["", "## Key insights"])
    lines.extend(f"- {insight}" for insight in insights)
    return "\n".join(lines)


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    export_df = df.copy()
    for col in export_df.columns:
        if pd.api.types.is_datetime64_any_dtype(export_df[col]):
            export_df[col] = export_df[col].dt.strftime("%Y-%m-%d")

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="FilteredData")
    return buffer.getvalue()


def main() -> None:
    st.set_page_config(page_title="Brokerage Data Analyzer", layout="wide")

    st.title("Brokerage Data Analyzer")
    st.caption("Upload brokerage transaction data, explore insights, and export results.")

    with st.sidebar:
        st.header("Data")
        uploaded_file = st.file_uploader(
            "Upload a data file",
            type=["csv", "xlsx", "xls"],
            help="Supported formats: CSV and Excel.",
        )

    df: Optional[pd.DataFrame] = None
    if uploaded_file is not None:
        try:
            df = load_data(uploaded_file.getvalue(), uploaded_file.name)
        except Exception as exc:
            st.error(f"Could not read the uploaded file: {exc}")

    if df is None:
        st.info("Upload a CSV or Excel file using the sidebar to get started.")
        st.stop()

    with st.sidebar:
        st.header("Filters")
        st.caption("Apply to all tabs. Clearing every option in a list includes all values.")

        region_options = sorted(df["Region"].dropna().unique()) if "Region" in df.columns else []
        asset_options = sorted(df["Asset"].dropna().unique()) if "Asset" in df.columns else []
        type_options = (
            sorted(df["Transaction_Type"].dropna().unique())
            if "Transaction_Type" in df.columns
            else []
        )

        selected_regions = st.multiselect("Region", region_options, default=region_options)
        selected_assets = st.multiselect("Asset", asset_options, default=asset_options)
        selected_types = st.multiselect(
            "Transaction type", type_options, default=type_options
        )

        if DATE_COLUMN in df.columns:
            min_date = df[DATE_COLUMN].min().date()
            max_date = df[DATE_COLUMN].max().date()
            selected_date_range = st.date_input(
                "Date range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
            )
        else:
            selected_date_range = ()

        st.header("Analysis")
        st.caption("Metric and group-by drive the Analytics tab (charts, top/bottom, summaries).")

        available_metrics = [col for col in NUMERIC_METRICS if col in df.columns]
        selected_metric = st.selectbox(
            "Metric for analysis",
            available_metrics,
            index=available_metrics.index("PnL") if "PnL" in available_metrics else 0,
            help="Used for top/bottom rows, group-by charts, and the time series in Analytics.",
        )

        available_categories = [col for col in CATEGORY_COLUMNS if col in df.columns]
        selected_category = st.selectbox(
            "Group by",
            available_categories,
            index=available_categories.index("Region") if "Region" in available_categories else 0,
            help="Category for the group-by table and bar chart in Analytics.",
        )

        st.subheader("Overview table sort")
        st.caption(
            "Row order in the Overview tab only. Independent of the metric above; "
            "pick the column you want to sort by."
        )
        sort_column = st.selectbox("Sort table by", list(df.columns))
        sort_ascending = st.radio("Sort direction", ["Ascending", "Descending"]) == "Ascending"

    if isinstance(selected_date_range, date):
        selected_date_range = (selected_date_range, selected_date_range)

    filtered_df = apply_filters(
        df,
        selected_regions,
        selected_assets,
        selected_types,
        selected_date_range,
    )

    sorted_df = filtered_df.sort_values(sort_column, ascending=sort_ascending)
    insights = generate_insights(filtered_df)

    st.sidebar.metric("Filtered rows", f"{len(filtered_df)} of {len(df)}")

    tab_overview, tab_analytics, tab_insights, tab_export = st.tabs(
        ["Overview", "Analytics", "Insights", "Export"]
    )

    with tab_overview:
        sort_label = "ascending" if sort_ascending else "descending"
        st.caption(
            f"Table sorted by **{sort_column}** ({sort_label}). "
            "Other columns may look out of order. Change \"Sort table by\" in the sidebar."
        )

        st.subheader("Dataset summary")
        summary_cols = st.columns(3)
        summary_cols[0].metric("Rows", len(filtered_df))
        summary_cols[1].metric("Columns", len(filtered_df.columns))
        summary_cols[2].metric("Missing values", int(filtered_df.isna().sum().sum()))

        st.subheader("Columns and data types")
        dtype_df = filtered_df.dtypes.reset_index()
        dtype_df.columns = ["Column", "Data type"]
        st.dataframe(dtype_df, use_container_width=True, hide_index=True)

        st.subheader("Missing values by column")
        null_df = filtered_df.isna().sum().reset_index()
        null_df.columns = ["Column", "Missing count"]
        st.dataframe(null_df, use_container_width=True, hide_index=True)

        st.subheader("Data preview")
        if sorted_df.empty:
            st.warning("No rows match the current filters.")
        else:
            st.dataframe(sorted_df.head(20), use_container_width=True, hide_index=True)
            with st.expander(f"Show all rows ({len(sorted_df)})"):
                st.dataframe(sorted_df, use_container_width=True, hide_index=True)

    with tab_analytics:
        if filtered_df.empty:
            st.warning("No rows match the current filters.")
        else:
            st.caption(
                f"Using **{selected_metric}** grouped by **{selected_category}** "
                "(sidebar Analysis controls). Table sort does not affect this tab."
            )

            st.subheader("Summary statistics")

            numeric_stats = build_numeric_summary(filtered_df)
            if numeric_stats is not None:
                st.markdown("**Numeric summary**")
                st.caption(
                    "Numbers and dates: count, mean, std, min, max, "
                    "and quartiles (25%, 50%, 75%)."
                )
                st.dataframe(numeric_stats, use_container_width=True)

            categorical_stats = build_categorical_summary(filtered_df)
            if categorical_stats is not None:
                st.markdown("**Categorical summary**")
                st.caption(
                    "Text fields: count, unique (distinct values), "
                    "top (most common), freq (how often top appears)."
                )
                st.dataframe(categorical_stats, use_container_width=True)

            preview_columns = [
                col
                for col in [DATE_COLUMN, "Client_ID", "Region", "Asset", selected_metric]
                if col in filtered_df.columns
            ]

            col_top, col_bottom = st.columns(2)
            with col_top:
                st.subheader(f"Top 5 by {selected_metric}")
                st.dataframe(
                    filtered_df.nlargest(5, selected_metric)[preview_columns],
                    use_container_width=True,
                    hide_index=True,
                )
            with col_bottom:
                st.subheader(f"Bottom 5 by {selected_metric}")
                st.dataframe(
                    filtered_df.nsmallest(5, selected_metric)[preview_columns],
                    use_container_width=True,
                    hide_index=True,
                )

            st.subheader(f"{selected_metric} by {selected_category}")
            st.caption("Bar chart shows total; table also includes average and row count.")
            grouped = (
                filtered_df.groupby(selected_category)[selected_metric]
                .agg(total="sum", average="mean", count="count")
                .sort_values("total", ascending=False)
            )
            st.dataframe(grouped, use_container_width=True)
            st.bar_chart(grouped["total"])

            if DATE_COLUMN in filtered_df.columns:
                st.subheader(f"{selected_metric} over time")
                st.caption("Sums the selected metric per day or per calendar month.")
                time_granularity = st.radio(
                    "Time granularity",
                    ["Daily", "Monthly"],
                    horizontal=True,
                )
                if time_granularity == "Daily":
                    time_series = (
                        filtered_df.groupby(DATE_COLUMN)[selected_metric]
                        .sum()
                        .reset_index()
                        .sort_values(DATE_COLUMN)
                    )
                    st.line_chart(time_series, x=DATE_COLUMN, y=selected_metric)
                else:
                    time_series = (
                        filtered_df.assign(
                            Month=filtered_df[DATE_COLUMN].dt.to_period("M").astype(str)
                        )
                        .groupby("Month")[selected_metric]
                        .sum()
                        .reset_index()
                        .sort_values("Month")
                    )
                    st.line_chart(time_series, x="Month", y=selected_metric)
            else:
                st.warning("No date column found for time series.")

    with tab_insights:
        st.subheader("Key insights")
        st.caption(
            "Rule-based highlights from the current filtered data. "
            "Not affected by Overview table sort."
        )
        for insight in insights:
            st.markdown(f"- {insight}")
        if (
            not filtered_df.empty
            and insights != ["No data available for the current filters."]
            and len(insights) < INSIGHT_NOTE_THRESHOLD
        ):
            st.caption(
                "Some insights are unavailable because required columns or "
                "enough date history are missing."
            )

    with tab_export:
        st.subheader("Download filtered data")
        st.caption(
            "CSV and Excel contain filtered rows in dataset order. "
            "The Markdown report adds filter summary, aggregates, and insights."
        )
        if filtered_df.empty:
            st.warning("No rows match the current filters.")
        else:
            export_stamp = date.today().isoformat()
            csv_data = filtered_df.to_csv(index=False).encode("utf-8")
            excel_data = to_excel_bytes(filtered_df)
            report_text = build_report(
                filtered_df,
                insights,
                selected_regions,
                selected_assets,
                selected_types,
                selected_date_range,
            )

            col_csv, col_excel, col_report = st.columns(3)
            with col_csv:
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=f"brokerage_filtered_{export_stamp}.csv",
                    mime="text/csv",
                )
            with col_excel:
                st.download_button(
                    label="Download Excel",
                    data=excel_data,
                    file_name=f"brokerage_filtered_{export_stamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            with col_report:
                st.download_button(
                    label="Download report (.md)",
                    data=report_text,
                    file_name=f"brokerage_report_{export_stamp}.md",
                    mime="text/markdown",
                )


if __name__ == "__main__":
    main()
