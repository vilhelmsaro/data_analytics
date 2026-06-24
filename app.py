from datetime import date, datetime
from io import BytesIO
import warnings
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

MAX_FILTER_CARDINALITY = 100
DATE_PARSE_THRESHOLD = 0.8


@st.cache_data
def load_data(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    buffer = BytesIO(file_bytes)
    if file_name.lower().endswith(".csv"):
        df = pd.read_csv(buffer)
    elif file_name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(buffer)
    else:
        raise ValueError("Unsupported file type. Please upload a CSV or Excel file.")

    df.columns = df.columns.str.strip()
    return parse_datetime_columns(df)


def parse_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    parsed_df = df.copy()
    for col in parsed_df.columns:
        if pd.api.types.is_datetime64_any_dtype(parsed_df[col]):
            continue
        if pd.api.types.is_numeric_dtype(parsed_df[col]):
            continue
        sample = parsed_df[col].dropna().astype(str).head(20)
        if sample.empty:
            continue
        if not _column_name_suggests_date(col) and not _values_look_like_dates(sample):
            continue
        converted = pd.to_datetime(parsed_df[col], errors="coerce", utc=False)
        if len(parsed_df) > 0 and converted.notna().mean() >= DATE_PARSE_THRESHOLD:
            parsed_df[col] = converted
    return parsed_df


def _column_name_suggests_date(column: str) -> bool:
    lowered = column.lower()
    return any(token in lowered for token in ("date", "time", "month", "year", "day"))


def _values_look_like_dates(sample: pd.Series) -> bool:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed = pd.to_datetime(sample, errors="coerce", utc=False)
    return parsed.notna().mean() >= DATE_PARSE_THRESHOLD


def numeric_columns(df: pd.DataFrame) -> List[str]:
    return [
        col
        for col in df.columns
        if pd.api.types.is_numeric_dtype(df[col]) and df[col].notna().any()
    ]


def categorical_columns(df: pd.DataFrame) -> List[str]:
    return [
        col
        for col in df.columns
        if pd.api.types.is_object_dtype(df[col])
        or pd.api.types.is_string_dtype(df[col])
        or pd.api.types.is_categorical_dtype(df[col])
        or pd.api.types.is_bool_dtype(df[col])
    ]


def datetime_columns(df: pd.DataFrame) -> List[str]:
    return [
        col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])
    ]


def filterable_columns(df: pd.DataFrame) -> List[str]:
    return [
        col
        for col in categorical_columns(df)
        if 1 < df[col].nunique(dropna=True) <= MAX_FILTER_CARDINALITY
    ]


def apply_filters(
    df: pd.DataFrame,
    categorical_filters: Dict[str, List[str]],
    date_column: Optional[str],
    date_range: tuple,
) -> pd.DataFrame:
    filtered = df.copy()

    for column, selected_values in categorical_filters.items():
        if selected_values and column in filtered.columns:
            filtered = filtered[filtered[column].isin(selected_values)]

    if (
        date_column
        and date_column in filtered.columns
        and len(date_range) == 2
    ):
        start_date = pd.Timestamp(date_range[0])
        end_date = pd.Timestamp(date_range[1])
        filtered = filtered[
            (filtered[date_column] >= start_date)
            & (filtered[date_column] <= end_date)
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
    cols = categorical_columns(df)
    if not cols:
        return None
    return df[cols].describe()


def largest_monthly_metric_change(
    df: pd.DataFrame, date_column: str, metrics: List[str]
) -> Optional[str]:
    best_metric: Optional[str] = None
    best_period = None
    best_value: Optional[float] = None
    best_abs = -1.0

    for metric in metrics:
        monthly = df.groupby(df[date_column].dt.to_period("M"))[metric].sum()
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
        f"Largest month-over-month change: {best_metric} in {best_period} "
        f"({best_value:+,.2f})."
    )


def generate_insights(
    df: pd.DataFrame,
    metric: Optional[str],
    category: Optional[str],
    date_column: Optional[str],
) -> List[str]:
    if df.empty:
        return ["No data available for the current filters."]

    insights: List[str] = []
    metrics = numeric_columns(df)

    if metric and metric in df.columns:
        insights.append(
            f"Highest {metric}: {df[metric].max():,.4g} "
            f"(lowest: {df[metric].min():,.4g})."
        )

    if category and metric and {category, metric}.issubset(df.columns):
        grouped = df.groupby(category)[metric].sum()
        if not grouped.empty:
            top_category = grouped.idxmax()
            top_value = grouped.max()
            insights.append(
                f"Highest total {metric} by {category}: "
                f"{top_category} ({top_value:,.4g})."
            )

    if category and category in df.columns:
        counts = df[category].value_counts(normalize=True, dropna=False).head(5) * 100
        parts = [f"{label}: {value:.1f}%" for label, value in counts.items()]
        insights.append(f"Top values in {category}: {', '.join(parts)}.")

    if date_column and metric and {date_column, metric}.issubset(df.columns):
        monthly = df.groupby(df[date_column].dt.to_period("M"))[metric].sum()
        if len(monthly) > 1:
            changes = monthly.diff().dropna()
            largest_change_period = changes.abs().idxmax()
            largest_change_value = changes.loc[largest_change_period]
            insights.append(
                f"Largest month-over-month {metric} change: "
                f"{largest_change_period} ({largest_change_value:+,.4g})."
            )

    if date_column and metrics:
        cross_metric_change = largest_monthly_metric_change(df, date_column, metrics)
        if cross_metric_change:
            insights.append(cross_metric_change)

    if len(metrics) > 1:
        variability = df[metrics].std().sort_values(ascending=False)
        top_metric = variability.index[0]
        insights.append(
            f"Most variable numeric column (std dev): {top_metric} "
            f"({variability.iloc[0]:,.4g})."
        )

    missing_pct = df.isna().mean().max() * 100
    if missing_pct > 0:
        most_missing = df.isna().mean().idxmax()
        insights.append(
            f"Column with most missing values: {most_missing} "
            f"({missing_pct:.1f}% missing)."
        )

    insights.append(f"Dataset size after filters: {len(df)} rows.")

    return insights


def build_report(
    df: pd.DataFrame,
    insights: List[str],
    categorical_filters: Dict[str, List[str]],
    date_column: Optional[str],
    date_range: tuple,
    metric: Optional[str],
    category: Optional[str],
) -> str:
    lines = [
        "# Data Analysis Report",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"Rows: {len(df)}",
        f"Columns: {len(df.columns)}",
        "",
        "## Active filters",
    ]

    for column, values in categorical_filters.items():
        label = ", ".join(str(value) for value in values) if values else "All"
        lines.append(f"- {column}: {label}")

    if date_column and len(date_range) == 2:
        lines.append(f"- {date_column}: {date_range[0]} to {date_range[1]}")

    lines.extend(["", "## Analysis settings"])
    lines.append(f"- Metric: {metric or 'Not selected'}")
    lines.append(f"- Group by: {category or 'Not selected'}")

    lines.extend(["", "## Key aggregates"])
    if metric and metric in df.columns:
        lines.append(f"- Total {metric}: {df[metric].sum():,.4g}")
        lines.append(f"- Average {metric}: {df[metric].mean():,.4g}")

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


def analytics_preview_columns(
    df: pd.DataFrame,
    metric: Optional[str],
    category: Optional[str],
    date_column: Optional[str],
) -> List[str]:
    preferred = [date_column, category, metric]
    columns = [col for col in preferred if col and col in df.columns]
    for col in df.columns:
        if col not in columns:
            columns.append(col)
        if len(columns) >= 6:
            break
    return columns


def render_disabled_selectbox(label: str, reason: str) -> None:
    st.selectbox(label, ["Not available for this file"], disabled=True, help=reason)


def main() -> None:
    st.set_page_config(page_title="Data Analyzer", layout="wide")

    st.title("Data Analyzer")
    st.caption("Upload a tabular file, explore it, run basic analytics, and export results.")

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
        except ValueError as exc:
            st.error("Unsupported file type.")
            st.markdown(str(exc))
            st.markdown(
                "**What you can do:** upload a `.csv`, `.xlsx`, or `.xls` file."
            )
        except Exception:
            st.error("Could not read the uploaded file.")
            st.markdown(
                "The file may be corrupted, password-protected, or not a valid "
                "spreadsheet."
            )
            st.markdown(
                "**What you can do:**\n"
                "- Open the file in Excel or a text editor and confirm it is a "
                "readable table.\n"
                "- Re-export it as CSV or Excel and try again."
            )

    if df is None:
        st.info("Upload a CSV or Excel file using the sidebar to get started.")
        st.stop()

    numeric_cols = numeric_columns(df)
    category_cols = categorical_columns(df)
    date_cols = datetime_columns(df)

    with st.sidebar:
        st.header("Filters")
        st.caption("Apply to all tabs. Clearing every option in a list includes all values.")

        categorical_filters: Dict[str, List[str]] = {}
        filter_cols = filterable_columns(df)
        if filter_cols:
            for column in filter_cols:
                options = sorted(df[column].dropna().astype(str).unique())
                selected = st.multiselect(column, options, default=options)
                categorical_filters[column] = selected
        else:
            st.caption("No categorical columns with a filterable number of values.")

        selected_date_column: Optional[str] = None
        selected_date_range: tuple = ()
        if date_cols:
            selected_date_column = st.selectbox(
                "Date column for range filter",
                date_cols,
                help="Used for the date range filter and time-series charts.",
            )
            min_date = df[selected_date_column].min().date()
            max_date = df[selected_date_column].max().date()
            selected_date_range = st.date_input(
                "Date range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
            )

        st.header("Analysis")
        st.caption("Metric and group-by drive the Analytics tab (charts, top/bottom, summaries).")

        if numeric_cols:
            selected_metric = st.selectbox(
                "Metric for analysis",
                numeric_cols,
                help="Numeric column for top/bottom rows, group charts, and time series.",
            )
        else:
            selected_metric = None
            render_disabled_selectbox(
                "Metric for analysis",
                "This file has no numeric columns. Analytics that need a metric are limited.",
            )

        if category_cols:
            selected_category = st.selectbox(
                "Group by",
                category_cols,
                help="Category column for the group-by table and bar chart.",
            )
        else:
            selected_category = None
            render_disabled_selectbox(
                "Group by",
                "This file has no text or categorical columns to group by.",
            )

        st.subheader("Overview table sort")
        st.caption(
            "Row order in the Overview tab only. Independent of the metric above."
        )
        sort_column = st.selectbox("Sort table by", list(df.columns))
        sort_ascending = st.radio("Sort direction", ["Ascending", "Descending"]) == "Ascending"

    if isinstance(selected_date_range, date):
        selected_date_range = (selected_date_range, selected_date_range)

    filtered_df = apply_filters(
        df,
        categorical_filters,
        selected_date_column,
        selected_date_range,
    )

    sorted_df = filtered_df.sort_values(sort_column, ascending=sort_ascending)
    insights = generate_insights(
        filtered_df,
        selected_metric,
        selected_category,
        selected_date_column,
    )

    st.sidebar.metric("Filtered rows", f"{len(filtered_df)} of {len(df)}")

    tab_overview, tab_analytics, tab_insights, tab_export = st.tabs(
        ["Overview", "Analytics", "Insights", "Export"]
    )

    with tab_overview:
        sort_label = "ascending" if sort_ascending else "descending"
        st.caption(
            f"Table sorted by **{sort_column}** ({sort_label}). "
            "Change \"Sort table by\" in the sidebar to reorder rows."
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
            numeric_stats = build_numeric_summary(filtered_df)
            categorical_stats = build_categorical_summary(filtered_df)

            if numeric_stats is None and categorical_stats is None:
                st.info("No summary statistics available for the current data.")
            else:
                st.subheader("Summary statistics")

                if numeric_stats is not None:
                    st.markdown("**Numeric summary**")
                    st.caption(
                        "Numbers and dates: count, mean, std, min, max, "
                        "and quartiles (25%, 50%, 75%)."
                    )
                    st.dataframe(numeric_stats, use_container_width=True)

                if categorical_stats is not None:
                    st.markdown("**Categorical summary**")
                    st.caption(
                        "Text fields: count, unique (distinct values), "
                        "top (most common), freq (how often top appears)."
                    )
                    st.dataframe(categorical_stats, use_container_width=True)

            if selected_metric is None:
                st.info(
                    "Top/bottom rows, grouping, and time series need a numeric "
                    "column. This file has none — summary statistics above are "
                    "still available when applicable."
                )
            elif selected_category is None:
                st.info(
                    "Grouping charts need a categorical column. Top and bottom "
                    f"rows by **{selected_metric}** are shown below."
                )
                preview_columns = analytics_preview_columns(
                    filtered_df, selected_metric, None, selected_date_column
                )
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
            else:
                st.caption(
                    f"Using **{selected_metric}** grouped by **{selected_category}**."
                )

                preview_columns = analytics_preview_columns(
                    filtered_df,
                    selected_metric,
                    selected_category,
                    selected_date_column,
                )

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

            if selected_metric and selected_date_column:
                st.subheader(f"{selected_metric} over time")
                st.caption("Sums the selected metric per day or per calendar month.")
                time_granularity = st.radio(
                    "Time granularity",
                    ["Daily", "Monthly"],
                    horizontal=True,
                )
                if time_granularity == "Daily":
                    time_series = (
                        filtered_df.groupby(selected_date_column)[selected_metric]
                        .sum()
                        .reset_index()
                        .sort_values(selected_date_column)
                    )
                    st.line_chart(
                        time_series, x=selected_date_column, y=selected_metric
                    )
                else:
                    time_series = (
                        filtered_df.assign(
                            Month=filtered_df[selected_date_column]
                            .dt.to_period("M")
                            .astype(str)
                        )
                        .groupby("Month")[selected_metric]
                        .sum()
                        .reset_index()
                        .sort_values("Month")
                    )
                    st.line_chart(time_series, x="Month", y=selected_metric)
            elif selected_metric and not date_cols:
                st.caption("No date column detected — time series is not available.")

    with tab_insights:
        st.subheader("Key insights")
        st.caption("Rule-based highlights from the current filtered data.")
        if insights == ["No data available for the current filters."]:
            st.warning(insights[0])
        else:
            for insight in insights:
                st.markdown(f"- {insight}")
            if not numeric_cols:
                st.caption(
                    "Limited insights: add numeric columns for richer change and "
                    "variability analysis."
                )

    with tab_export:
        st.subheader("Download filtered data")
        st.caption(
            "CSV and Excel contain filtered rows. The Markdown report adds "
            "filter summary, aggregates, and insights."
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
                categorical_filters,
                selected_date_column,
                selected_date_range,
                selected_metric,
                selected_category,
            )

            col_csv, col_excel, col_report = st.columns(3)
            with col_csv:
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=f"filtered_data_{export_stamp}.csv",
                    mime="text/csv",
                )
            with col_excel:
                st.download_button(
                    label="Download Excel",
                    data=excel_data,
                    file_name=f"filtered_data_{export_stamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            with col_report:
                st.download_button(
                    label="Download report (.md)",
                    data=report_text,
                    file_name=f"data_report_{export_stamp}.md",
                    mime="text/markdown",
                )


if __name__ == "__main__":
    main()
