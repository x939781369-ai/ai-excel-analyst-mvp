import pandas as pd


SUPPORTED_PERIOD_MODES = {"week", "month", "overall"}


def _safe_copy(df):
    if df is None:
        return pd.DataFrame()
    return df.copy()


def _to_native_number(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    try:
        number = float(value)
    except Exception:
        return None

    if abs(number - round(number)) < 1e-12:
        return int(round(number))
    return float(number)


def _get_numeric_series(df, column_name):
    if column_name not in df.columns:
        return None
    return pd.to_numeric(df[column_name], errors="coerce")


def _get_datetime_series(df, column_name="date"):
    if column_name not in df.columns:
        return None
    return pd.to_datetime(df[column_name], errors="coerce")


def _get_clean_text_series(df, column_name):
    if column_name not in df.columns:
        return None

    series = df[column_name].copy()
    series = series.where(series.notna(), pd.NA)
    series = series.astype("string")
    series = series.str.replace("\u3000", " ", regex=False)
    series = series.str.replace("\xa0", " ", regex=False)
    series = series.str.strip()
    series = series.replace("", pd.NA)
    return series


def _infer_order_rows(df):
    if df is None or df.empty:
        return pd.DataFrame()

    candidate_cols = [col for col in ["sales", "product", "date", "city", "quantity", "order_id"] if col in df.columns]
    if not candidate_cols:
        return df.dropna(how="all")

    return df.dropna(subset=candidate_cols, how="all")


def _find_latest_consecutive_period_pair(period_series):
    unique_periods = sorted(period_series.dropna().unique())
    if len(unique_periods) < 2:
        return None, None

    period_set = set(unique_periods)
    for current_period in reversed(unique_periods):
        previous_period = current_period - 1
        if previous_period in period_set:
            return previous_period, current_period

    return None, None


def _format_period_label(period_value, period_mode):
    if period_value is None:
        return None

    if period_mode == "week":
        start_date = period_value.start_time.strftime("%Y-%m-%d")
        end_date = period_value.end_time.strftime("%Y-%m-%d")
        return f"{start_date} 至 {end_date}"

    if period_mode == "month":
        return period_value.strftime("%Y-%m")

    return str(period_value)


def _change_rate_to_pct(change_rate):
    if change_rate is None:
        return None
    return float(change_rate * 100)


def calculate_total_sales(df):
    if df is None or df.empty or "sales" not in df.columns:
        return None

    sales = _get_numeric_series(df, "sales")
    if sales is None or sales.notna().sum() == 0:
        return None

    return float(sales.sum())


def calculate_order_count(df):
    if df is None or df.empty:
        return 0

    if "order_id" in df.columns:
        order_ids = _get_clean_text_series(df, "order_id")
        if order_ids is not None:
            valid_order_ids = order_ids.dropna()
            if not valid_order_ids.empty:
                return int(valid_order_ids.nunique())

    inferred_rows = _infer_order_rows(df)
    return int(len(inferred_rows))


def calculate_avg_order_value(df):
    total_sales = calculate_total_sales(df)
    if total_sales is None:
        return None

    order_count = calculate_order_count(df)
    if order_count <= 0:
        return None

    return float(total_sales / order_count)


def calculate_daily_sales(df):
    if df is None or df.empty or "date" not in df.columns or "sales" not in df.columns:
        return None

    working_df = _safe_copy(df)
    working_df["date"] = _get_datetime_series(working_df, "date")
    working_df["sales"] = _get_numeric_series(working_df, "sales")
    working_df = working_df.dropna(subset=["date", "sales"])

    if working_df.empty:
        return None

    working_df["date"] = working_df["date"].dt.floor("D")
    daily_sales = (
        working_df.groupby("date", as_index=False)["sales"]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )
    return daily_sales


def calculate_top_products(df, top_n=5):
    if df is None or df.empty or "product" not in df.columns or "sales" not in df.columns:
        return None

    working_df = _safe_copy(df)
    working_df["product"] = _get_clean_text_series(working_df, "product")
    working_df["sales"] = _get_numeric_series(working_df, "sales")
    working_df = working_df.dropna(subset=["product", "sales"])

    if working_df.empty:
        return None

    top_products = (
        working_df.groupby("product", as_index=False)["sales"]
        .sum()
        .sort_values(["sales", "product"], ascending=[False, True])
        .head(top_n)
        .reset_index(drop=True)
    )
    return top_products


def calculate_top_cities(df, top_n=5):
    if df is None or df.empty or "city" not in df.columns or "sales" not in df.columns:
        return None

    working_df = _safe_copy(df)
    working_df["city"] = _get_clean_text_series(working_df, "city")
    working_df["sales"] = _get_numeric_series(working_df, "sales")
    working_df = working_df.dropna(subset=["city", "sales"])

    if working_df.empty:
        return None

    top_cities = (
        working_df.groupby("city", as_index=False)["sales"]
        .sum()
        .sort_values(["sales", "city"], ascending=[False, True])
        .head(top_n)
        .reset_index(drop=True)
    )
    return top_cities


def calculate_period_summary(period_df):
    if period_df is None or period_df.empty:
        return None

    total_sales = calculate_total_sales(period_df)
    order_count = calculate_order_count(period_df)
    avg_order_value = calculate_avg_order_value(period_df)

    return {
        "row_count": int(len(period_df)),
        "total_sales": total_sales,
        "order_count": order_count,
        "avg_order_value": avg_order_value,
    }


def calculate_change_rate(current_value, previous_value):
    current_value = _to_native_number(current_value)
    previous_value = _to_native_number(previous_value)

    if current_value is None or previous_value in [None, 0]:
        return None

    return float((current_value - previous_value) / previous_value)


def split_into_two_periods(df, period_mode="week"):
    """
    按真实自然周 / 自然月切分：
    - week: 找到最近一组连续自然周
    - month: 找到最近一组连续自然月
    """
    if df is None or df.empty or "date" not in df.columns:
        return None, None, None, None

    if period_mode not in {"week", "month"}:
        return None, None, None, None

    working_df = _safe_copy(df)
    working_df["date"] = _get_datetime_series(working_df, "date")
    working_df = working_df.dropna(subset=["date"]).copy()

    if working_df.empty:
        return None, None, None, None

    if period_mode == "week":
        working_df["period"] = working_df["date"].dt.to_period("W-SUN")
    else:
        working_df["period"] = working_df["date"].dt.to_period("M")

    previous_period, current_period = _find_latest_consecutive_period_pair(working_df["period"])
    if previous_period is None or current_period is None:
        return None, None, None, None

    previous_period_df = working_df.loc[working_df["period"] == previous_period].copy()
    current_period_df = working_df.loc[working_df["period"] == current_period].copy()

    if previous_period_df.empty or current_period_df.empty:
        return None, None, None, None

    previous_label = _format_period_label(previous_period, period_mode)
    current_label = _format_period_label(current_period, period_mode)

    return previous_period_df, current_period_df, previous_label, current_label


def calculate_period_comparison(df, period_mode="week"):
    if period_mode not in SUPPORTED_PERIOD_MODES:
        period_mode = "week"

    if period_mode == "overall":
        overall_summary = calculate_period_summary(df)
        return {
            "period_mode": "overall",
            "previous_label": None,
            "current_label": "全量数据",
            "previous_period": None,
            "current_period": overall_summary,
            "previous_sales": None,
            "current_sales": overall_summary.get("total_sales") if overall_summary else None,
            "previous_order_count": None,
            "current_order_count": overall_summary.get("order_count") if overall_summary else None,
            "previous_avg_order_value": None,
            "current_avg_order_value": overall_summary.get("avg_order_value") if overall_summary else None,
            "sales_change_rate": None,
            "order_change_rate": None,
            "avg_order_value_change_rate": None,
            "sales_change_pct": None,
            "order_count_change_pct": None,
            "avg_order_value_change_pct": None,
        }

    previous_period_df, current_period_df, previous_label, current_label = split_into_two_periods(df, period_mode=period_mode)
    if previous_period_df is None or current_period_df is None:
        return None

    previous_summary = calculate_period_summary(previous_period_df)
    current_summary = calculate_period_summary(current_period_df)

    sales_change_rate = calculate_change_rate(
        current_summary.get("total_sales") if current_summary else None,
        previous_summary.get("total_sales") if previous_summary else None,
    )
    order_change_rate = calculate_change_rate(
        current_summary.get("order_count") if current_summary else None,
        previous_summary.get("order_count") if previous_summary else None,
    )
    avg_order_value_change_rate = calculate_change_rate(
        current_summary.get("avg_order_value") if current_summary else None,
        previous_summary.get("avg_order_value") if previous_summary else None,
    )

    return {
        "period_mode": period_mode,
        "previous_label": previous_label,
        "current_label": current_label,
        "previous_period": previous_summary,
        "current_period": current_summary,
        "previous_sales": previous_summary.get("total_sales") if previous_summary else None,
        "current_sales": current_summary.get("total_sales") if current_summary else None,
        "previous_order_count": previous_summary.get("order_count") if previous_summary else None,
        "current_order_count": current_summary.get("order_count") if current_summary else None,
        "previous_avg_order_value": previous_summary.get("avg_order_value") if previous_summary else None,
        "current_avg_order_value": current_summary.get("avg_order_value") if current_summary else None,
        "sales_change_rate": sales_change_rate,
        "order_change_rate": order_change_rate,
        "avg_order_value_change_rate": avg_order_value_change_rate,
        "sales_change_pct": _change_rate_to_pct(sales_change_rate),
        "order_count_change_pct": _change_rate_to_pct(order_change_rate),
        "avg_order_value_change_pct": _change_rate_to_pct(avg_order_value_change_rate),
    }


def calculate_all_metrics(df, period_mode="week"):
    working_df = _safe_copy(df)

    total_sales = calculate_total_sales(working_df)
    order_count = calculate_order_count(working_df)
    avg_order_value = calculate_avg_order_value(working_df)
    daily_sales = calculate_daily_sales(working_df)
    top_products = calculate_top_products(working_df)
    top_cities = calculate_top_cities(working_df)
    period_comparison = calculate_period_comparison(working_df, period_mode=period_mode)

    date_series = _get_datetime_series(working_df, "date") if "date" in working_df.columns else None
    valid_dates = date_series.dropna() if date_series is not None else pd.Series(dtype="datetime64[ns]")

    return {
        "row_count": int(len(working_df)),
        "valid_sales_rows": int(_get_numeric_series(working_df, "sales").notna().sum()) if "sales" in working_df.columns else 0,
        "date_min": valid_dates.min().strftime("%Y-%m-%d") if not valid_dates.empty else None,
        "date_max": valid_dates.max().strftime("%Y-%m-%d") if not valid_dates.empty else None,
        "total_sales": total_sales,
        "order_count": order_count,
        "avg_order_value": avg_order_value,
        "daily_sales": daily_sales,
        "top_products": top_products,
        "top_cities": top_cities,
        "period_comparison": period_comparison,
    }
