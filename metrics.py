import pandas as pd


def calculate_total_sales(df):
    if "sales" not in df.columns:
        return None
    return df["sales"].sum()


def calculate_order_count(df):
    if "order_id" in df.columns:
        return df["order_id"].nunique()
    return len(df)


def calculate_avg_order_value(df):
    if "sales" not in df.columns:
        return None

    order_count = calculate_order_count(df)
    if order_count == 0:
        return 0

    return df["sales"].sum() / order_count


def calculate_daily_sales(df):
    if "date" not in df.columns or "sales" not in df.columns:
        return None

    daily_sales = (
        df.dropna(subset=["date"])
        .groupby("date", as_index=False)["sales"]
        .sum()
        .sort_values("date")
    )
    return daily_sales


def calculate_top_products(df, top_n=5):
    if "product" not in df.columns or "sales" not in df.columns:
        return None

    top_products = (
        df.groupby("product", as_index=False)["sales"]
        .sum()
        .sort_values("sales", ascending=False)
        .head(top_n)
    )
    return top_products


def calculate_top_cities(df, top_n=5):
    if "city" not in df.columns or "sales" not in df.columns:
        return None

    top_cities = (
        df.groupby("city", as_index=False)["sales"]
        .sum()
        .sort_values("sales", ascending=False)
        .head(top_n)
    )
    return top_cities


def calculate_period_summary(period_df):
    if period_df is None or period_df.empty:
        return None

    return {
        "total_sales": calculate_total_sales(period_df),
        "order_count": calculate_order_count(period_df),
        "avg_order_value": calculate_avg_order_value(period_df),
    }


def calculate_change_rate(current_value, previous_value):
    if previous_value in [None, 0]:
        return None
    if current_value is None:
        return None
    return (current_value - previous_value) / previous_value


def _format_period_label(period_value, period_mode):
    if period_mode == "week":
        start_date = period_value.start_time.strftime("%Y-%m-%d")
        end_date = period_value.end_time.strftime("%Y-%m-%d")
        return f"{start_date} 至 {end_date}"
    elif period_mode == "month":
        return period_value.strftime("%Y-%m")
    return str(period_value)


def split_into_two_periods(df, period_mode="week"):
    """
    按真实自然周 / 自然月切分：
    - week: 本周 vs 上周
    - month: 本月 vs 上月
    """
    if "date" not in df.columns:
        return None, None, None, None

    date_df = df.dropna(subset=["date"]).copy()

    if date_df.empty:
        return None, None, None, None

    date_df["date"] = pd.to_datetime(date_df["date"], errors="coerce")
    date_df = date_df.dropna(subset=["date"]).copy()

    if date_df.empty:
        return None, None, None, None

    if period_mode == "week":
        # 周一到周日
        date_df["period"] = date_df["date"].dt.to_period("W-SUN")
    elif period_mode == "month":
        date_df["period"] = date_df["date"].dt.to_period("M")
    else:
        return None, None, None, None

    current_period = date_df["period"].max()
    previous_period = current_period - 1

    current_period_df = date_df[date_df["period"] == current_period].copy()
    previous_period_df = date_df[date_df["period"] == previous_period].copy()

    if current_period_df.empty or previous_period_df.empty:
        return None, None, None, None

    current_label = _format_period_label(current_period, period_mode)
    previous_label = _format_period_label(previous_period, period_mode)

    return previous_period_df, current_period_df, previous_label, current_label


def calculate_period_comparison(df, period_mode="week"):
    if period_mode == "overall":
        return {
            "period_mode": "overall",
            "previous_label": None,
            "current_label": "全量数据",
            "previous_period": None,
            "current_period": calculate_period_summary(df),
            "sales_change_rate": None,
            "order_change_rate": None,
            "avg_order_value_change_rate": None,
        }

    previous_period_df, current_period_df, previous_label, current_label = split_into_two_periods(
        df, period_mode=period_mode
    )

    if previous_period_df is None or current_period_df is None:
        return None

    previous_summary = calculate_period_summary(previous_period_df)
    current_summary = calculate_period_summary(current_period_df)

    comparison = {
        "period_mode": period_mode,
        "previous_label": previous_label,
        "current_label": current_label,
        "previous_period": previous_summary,
        "current_period": current_summary,
        "sales_change_rate": calculate_change_rate(
            current_summary["total_sales"], previous_summary["total_sales"]
        ),
        "order_change_rate": calculate_change_rate(
            current_summary["order_count"], previous_summary["order_count"]
        ),
        "avg_order_value_change_rate": calculate_change_rate(
            current_summary["avg_order_value"], previous_summary["avg_order_value"]
        ),
    }

    return comparison


def calculate_all_metrics(df, period_mode="week"):
    return {
        "total_sales": calculate_total_sales(df),
        "order_count": calculate_order_count(df),
        "avg_order_value": calculate_avg_order_value(df),
        "daily_sales": calculate_daily_sales(df),
        "top_products": calculate_top_products(df),
        "top_cities": calculate_top_cities(df),
        "period_comparison": calculate_period_comparison(df, period_mode=period_mode),
    }