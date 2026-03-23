import re

import pandas as pd


STANDARD_FIELDS = ["date", "sales", "product", "quantity", "city", "order_id"]


def _normalize_text_value(value):
    if pd.isna(value):
        return pd.NA

    text = str(value)
    text = text.replace("\u3000", " ")   # 中文全角空格
    text = text.replace("\xa0", " ")     # 不换行空格
    text = text.strip()

    if text == "":
        return pd.NA

    return text


def _clean_text_series(series: pd.Series) -> pd.Series:
    return series.apply(_normalize_text_value)


def _clean_numeric_text(text: str) -> str:
    """
    尽量兼容真实业务里常见的金额/数量字符串：
    - ¥1,299.00
    - 1 299
    - 1，299
    - (1299.00)
    - RMB 1299
    """
    text = text.strip()

    if not text:
        return ""

    # 负数括号写法：(123.45) -> -123.45
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]

    # 去掉货币、中文单位、空格
    text = text.replace("￥", "")
    text = text.replace("¥", "")
    text = text.replace("RMB", "")
    text = text.replace("rmb", "")
    text = text.replace("元", "")
    text = text.replace("单", "")
    text = text.replace("件", "")
    text = text.replace("个", "")
    text = text.replace("\u3000", "")
    text = text.replace("\xa0", "")
    text = text.replace(" ", "")

    # 全角逗号/句号转半角
    text = text.replace("，", ",")
    text = text.replace("。", ".")

    # 只保留数字 / 小数点 / 逗号 / 负号
    text = re.sub(r"[^0-9,\.\-]", "", text)

    if text in {"", "-", ".", ","}:
        return ""

    # 处理逗号和小数点
    if "," in text and "." in text:
        # 典型千分位：1,234.56 -> 1234.56
        text = text.replace(",", "")
    elif "," in text and "." not in text:
        # 如果最后一段长度为 1-2，倾向把逗号当小数点：12,5 -> 12.5
        last_part = text.split(",")[-1]
        if len(last_part) in (1, 2):
            text = text.replace(",", ".")
        else:
            # 否则当千分位处理：1,234 -> 1234
            text = text.replace(",", "")

    # 避免多个负号 / 多个点造成异常
    if text.count("-") > 1:
        text = text.replace("-", "")
    if text.count(".") > 1:
        first_dot_index = text.find(".")
        text = text[: first_dot_index + 1] + text[first_dot_index + 1 :].replace(".", "")

    return text


def _clean_numeric_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    cleaned = series.apply(_normalize_text_value)
    cleaned = cleaned.apply(lambda x: _clean_numeric_text(x) if pd.notna(x) else x)
    return pd.to_numeric(cleaned, errors="coerce")


def _parse_excel_serial_date(series: pd.Series) -> pd.Series:
    """
    兼容 Excel 序列日期，例如 45291 这类数字日期。
    """
    numeric_series = pd.to_numeric(series, errors="coerce")

    # Excel 序列日期常见范围大致在这个区间内
    valid_mask = numeric_series.between(20000, 60000, inclusive="both")
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    if valid_mask.any():
        parsed.loc[valid_mask] = pd.to_datetime(
            numeric_series.loc[valid_mask],
            unit="D",
            origin="1899-12-30",
            errors="coerce",
        )

    return parsed


def _clean_date_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    raw = series.copy()

    # 先尝试把明显的 Excel 数字日期转掉
    excel_date_parsed = _parse_excel_serial_date(raw)

    # 再处理文本日期
    text_series = raw.apply(_normalize_text_value)

    def normalize_date_text(value):
        if pd.isna(value):
            return pd.NA
        text = str(value)
        text = text.replace("年", "-").replace("月", "-").replace("日", "")
        text = text.replace("/", "-").replace(".", "-")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    text_series = text_series.apply(normalize_date_text)
    text_date_parsed = pd.to_datetime(text_series, errors="coerce")

    # 优先使用文本解析结果，解析不到再回退 Excel 序列日期
    final_date = text_date_parsed.copy()
    final_date = final_date.where(final_date.notna(), excel_date_parsed)

    return final_date


def standardize_dataframe(df, mapping_result):
    """
    根据用户选择的字段映射，将原始 DataFrame 转换为标准字段 DataFrame
    """
    if df is None or df.empty:
        raise ValueError("原始数据为空，无法进行字段标准化。")

    if not isinstance(mapping_result, dict):
        raise ValueError("字段映射结果格式不正确。")

    standardized_data = {}

    for standard_field in STANDARD_FIELDS:
        selected_column = mapping_result.get(standard_field)

        if (
            selected_column
            and selected_column != "-- 请选择 --"
            and selected_column in df.columns
        ):
            standardized_data[standard_field] = df[selected_column].copy()

    standardized_df = pd.DataFrame(standardized_data)

    if standardized_df.empty:
        raise ValueError("没有可用的字段映射结果，请至少选择日期和销售额等核心字段。")

    if "date" in standardized_df.columns:
        standardized_df["date"] = _clean_date_series(standardized_df["date"])

    if "sales" in standardized_df.columns:
        standardized_df["sales"] = _clean_numeric_series(standardized_df["sales"])

    if "quantity" in standardized_df.columns:
        standardized_df["quantity"] = _clean_numeric_series(standardized_df["quantity"])

    if "product" in standardized_df.columns:
        standardized_df["product"] = _clean_text_series(standardized_df["product"])

    if "city" in standardized_df.columns:
        standardized_df["city"] = _clean_text_series(standardized_df["city"])

    if "order_id" in standardized_df.columns:
        standardized_df["order_id"] = _clean_text_series(standardized_df["order_id"])

    # 去掉所有字段都为空的空行
    standardized_df = standardized_df.dropna(how="all").reset_index(drop=True)

    return standardized_df