import re
from typing import Any

import pandas as pd


NO_SELECTION = "-- 请选择 --"
STANDARD_FIELDS = ["date", "sales", "product", "quantity", "city", "order_id"]
FIELD_PRIORITY = ["date", "sales", "product", "quantity", "city", "order_id"]


def get_field_options(columns):
    """
    根据上传数据的列名，生成字段映射选项
    """
    return [NO_SELECTION] + [str(col) for col in columns]


def get_default_mapping(df: pd.DataFrame) -> dict:
    """
    自动识别标准字段映射，返回：
    {
        "date": "下单日期",
        "sales": "销售额",
        ...
    }
    未识别到时返回 NO_SELECTION
    """
    if df is None or df.empty:
        return {field: NO_SELECTION for field in STANDARD_FIELDS}

    columns = [str(col) for col in df.columns]
    if not columns:
        return {field: NO_SELECTION for field in STANDARD_FIELDS}

    score_table = {field: {} for field in STANDARD_FIELDS}

    for col in columns:
        series = df[col]
        profile = _build_series_profile(series)
        norm_name = _normalize_column_name(col)

        score_table["date"][col] = _score_date_column(col, norm_name, profile)
        score_table["sales"][col] = _score_sales_column(col, norm_name, profile)
        score_table["product"][col] = _score_product_column(col, norm_name, profile)
        score_table["quantity"][col] = _score_quantity_column(col, norm_name, profile)
        score_table["city"][col] = _score_city_column(col, norm_name, profile)
        score_table["order_id"][col] = _score_order_id_column(col, norm_name, profile)

    thresholds = {
        "date": 4.0,
        "sales": 4.5,
        "product": 4.0,
        "quantity": 4.0,
        "city": 4.0,
        "order_id": 4.0,
    }

    mapping = {field: NO_SELECTION for field in STANDARD_FIELDS}
    used_columns = set()

    for field in FIELD_PRIORITY:
        candidates = sorted(
            score_table[field].items(),
            key=lambda x: x[1],
            reverse=True
        )

        for col, score in candidates:
            if col in used_columns:
                continue
            if score >= thresholds[field]:
                mapping[field] = col
                used_columns.add(col)
                break

    return mapping


def get_default_mapping_indices(df: pd.DataFrame, options: list[str]) -> dict:
    """
    给 Streamlit selectbox 用的默认 index。
    options 一般来自 get_field_options(df.columns)
    """
    mapping = get_default_mapping(df)
    result = {}

    for field in STANDARD_FIELDS:
        selected_col = mapping.get(field, NO_SELECTION)
        result[field] = options.index(selected_col) if selected_col in options else 0

    return result


# =========================
# 基础工具
# =========================

def _normalize_column_name(name: Any) -> str:
    text = str(name).strip().lower()
    text = text.replace("\ufeff", "")
    text = text.replace("\u3000", " ")
    text = text.replace("\xa0", " ")
    text = text.replace("_", "")
    text = text.replace("-", "")
    text = text.replace(" ", "")
    text = text.replace("/", "")
    text = text.replace("\\", "")
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("[", "").replace("]", "")
    text = text.replace("(", "").replace(")", "")
    return text


def _normalize_text_value(value: Any):
    if pd.isna(value):
        return pd.NA

    text = str(value)
    text = text.replace("\u3000", " ")
    text = text.replace("\xa0", " ")
    text = text.strip()

    if text == "":
        return pd.NA
    return text


def _clean_numeric_text_for_scoring(text: str) -> str:
    text = str(text).strip()
    if not text:
        return ""

    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]

    text = text.replace("￥", "")
    text = text.replace("¥", "")
    text = text.replace("RMB", "")
    text = text.replace("rmb", "")
    text = text.replace("元", "")
    text = text.replace("件", "")
    text = text.replace("个", "")
    text = text.replace("单", "")
    text = text.replace("\u3000", "")
    text = text.replace("\xa0", "")
    text = text.replace(" ", "")
    text = text.replace("，", ",")
    text = text.replace("。", ".")

    text = re.sub(r"[^0-9,\.\-]", "", text)

    if text in {"", "-", ".", ","}:
        return ""

    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text and "." not in text:
        last_part = text.split(",")[-1]
        if len(last_part) in (1, 2):
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")

    if text.count("-") > 1:
        text = text.replace("-", "")
    if text.count(".") > 1:
        first_dot = text.find(".")
        text = text[: first_dot + 1] + text[first_dot + 1 :].replace(".", "")

    return text


def _keyword_score(name: str, weighted_keywords: list[tuple[str, float]]) -> float:
    score = 0.0
    for keyword, weight in weighted_keywords:
        if keyword in name:
            score += weight
    return score


def _build_series_profile(series: pd.Series) -> dict:
    s = series.copy()

    non_null = s.dropna()
    if non_null.empty:
        return {
            "non_null_count": 0,
            "unique_ratio": 0.0,
            "avg_len": 0.0,
            "numeric_ratio": 0.0,
            "int_like_ratio": 0.0,
            "datetime_ratio": 0.0,
            "excel_date_ratio": 0.0,
            "text_ratio": 0.0,
            "distinct_count": 0,
        }

    sample = non_null.head(120)
    sample_text = sample.apply(_normalize_text_value).dropna().astype(str)

    distinct_count = int(sample_text.nunique())
    unique_ratio = distinct_count / max(len(sample_text), 1)
    avg_len = sample_text.map(len).mean() if len(sample_text) else 0.0

    cleaned_numeric = sample_text.map(_clean_numeric_text_for_scoring)
    numeric_series = pd.to_numeric(cleaned_numeric, errors="coerce")
    numeric_ratio = float(numeric_series.notna().mean()) if len(sample_text) else 0.0

    int_like_ratio = 0.0
    if numeric_series.notna().any():
        valid_numeric = numeric_series.dropna()
        int_like_ratio = float((valid_numeric.round().eq(valid_numeric)).mean())

    parsed_dt = pd.to_datetime(sample_text, errors="coerce")
    datetime_ratio = float(parsed_dt.notna().mean()) if len(sample_text) else 0.0

    excel_date_ratio = 0.0
    if numeric_series.notna().any():
        valid_numeric = numeric_series.dropna()
        excel_mask = valid_numeric.between(20000, 60000, inclusive="both")
        excel_date_ratio = float(excel_mask.mean())

    text_ratio = 1.0 - numeric_ratio

    return {
        "non_null_count": int(len(non_null)),
        "unique_ratio": float(unique_ratio),
        "avg_len": float(avg_len),
        "numeric_ratio": float(numeric_ratio),
        "int_like_ratio": float(int_like_ratio),
        "datetime_ratio": float(datetime_ratio),
        "excel_date_ratio": float(excel_date_ratio),
        "text_ratio": float(text_ratio),
        "distinct_count": int(distinct_count),
    }


# =========================
# 各字段评分
# =========================

def _score_date_column(col: str, name: str, profile: dict) -> float:
    positive = [
        ("下单日期", 9), ("支付时间", 9), ("订单时间", 9), ("成交时间", 9),
        ("创建时间", 8), ("付款时间", 8), ("日期", 7), ("时间", 6),
        ("date", 7), ("time", 6),
    ]
    negative = [
        ("天数", 4), ("时长", 4), ("小时", 3),
    ]

    score = 0.0
    score += _keyword_score(name, positive)
    score -= _keyword_score(name, negative)

    if profile["datetime_ratio"] >= 0.85:
        score += 8
    elif profile["datetime_ratio"] >= 0.55:
        score += 5
    elif profile["excel_date_ratio"] >= 0.7:
        score += 5

    if profile["numeric_ratio"] >= 0.95 and profile["excel_date_ratio"] < 0.3 and profile["datetime_ratio"] < 0.3:
        score -= 3

    return score


def _score_sales_column(col: str, name: str, profile: dict) -> float:
    positive = [
        ("销售额", 12), ("成交金额", 12), ("支付金额", 11), ("实付金额", 11),
        ("订单金额", 11), ("总金额", 10), ("实付", 9), ("成交额", 10),
        ("销售金额", 10), ("gmv", 10), ("revenue", 9), ("sales", 8),
        ("amount", 6), ("金额", 5),
    ]
    negative = [
        ("商品单价", 14), ("客单价", 13), ("单价", 12), ("售价", 12),
        ("原价", 10), ("价格", 10), ("price", 12), ("cost", 8),
        ("成本", 8), ("折扣", 5), ("退款", 4),
        ("商品类别", 6), ("品类", 6), ("类目", 6), ("分类", 6),
    ]

    score = 0.0
    score += _keyword_score(name, positive)
    score -= _keyword_score(name, negative)

    if profile["numeric_ratio"] >= 0.9:
        score += 4
    elif profile["numeric_ratio"] >= 0.65:
        score += 2

    if profile["int_like_ratio"] < 0.95 and profile["numeric_ratio"] >= 0.7:
        score += 1

    if profile["text_ratio"] > 0.4:
        score -= 2

    return score


def _score_product_column(col: str, name: str, profile: dict) -> float:
    positive = [
        ("商品类别", 13), ("商品类目", 13), ("商品分类", 13),
        ("sku类别", 11), ("一级类目", 11), ("二级类目", 10),
        ("品类", 11), ("类目", 10), ("类别", 10), ("分类", 9),
        ("商品名称", 9), ("商品名", 9), ("品名", 8), ("商品", 6),
        ("sku", 7), ("spu", 6), ("产品", 5),
    ]
    negative = [
        ("商品单价", 16), ("单价", 14), ("售价", 14), ("价格", 12),
        ("price", 14), ("金额", 12), ("销售额", 12),
        ("数量", 8), ("件数", 8), ("城市", 7), ("日期", 7),
        ("时间", 7), ("订单", 6), ("id", 4),
    ]

    score = 0.0
    score += _keyword_score(name, positive)
    score -= _keyword_score(name, negative)

    if profile["text_ratio"] >= 0.8:
        score += 3
    if 0.02 <= profile["unique_ratio"] <= 0.95:
        score += 2
    if profile["avg_len"] >= 2:
        score += 1

    if profile["numeric_ratio"] >= 0.8:
        score -= 6

    return score


def _score_quantity_column(col: str, name: str, profile: dict) -> float:
    positive = [
        ("购买数量", 12), ("销售数量", 11), ("下单数量", 11),
        ("数量", 10), ("件数", 10), ("销量", 9),
        ("qty", 9), ("quantity", 9), ("pcs", 7),
        ("件", 5), ("个", 4),
    ]
    negative = [
        ("金额", 10), ("销售额", 10), ("单价", 10), ("售价", 10),
        ("价格", 9), ("price", 10), ("日期", 6), ("城市", 6),
    ]

    score = 0.0
    score += _keyword_score(name, positive)
    score -= _keyword_score(name, negative)

    if profile["numeric_ratio"] >= 0.9:
        score += 4
    elif profile["numeric_ratio"] >= 0.65:
        score += 2

    if profile["int_like_ratio"] >= 0.85:
        score += 3

    if profile["unique_ratio"] <= 0.35:
        score += 1.5

    return score


def _score_city_column(col: str, name: str, profile: dict) -> float:
    positive = [
        ("收货城市", 13), ("所属城市", 11), ("发货城市", 11),
        ("城市", 10), ("地区", 8), ("区域", 7), ("城市名", 8),
        ("省市", 8), ("city", 8), ("region", 6),
    ]
    negative = [
        ("城市编码", 12), ("cityid", 12), ("城市id", 12),
        ("地址", 4), ("经度", 8), ("纬度", 8), ("邮编", 8),
        ("金额", 6), ("数量", 6),
    ]

    score = 0.0
    score += _keyword_score(name, positive)
    score -= _keyword_score(name, negative)

    if profile["text_ratio"] >= 0.8:
        score += 2.5
    if 2 <= profile["distinct_count"] <= 100:
        score += 2
    if profile["unique_ratio"] > 0.85:
        score -= 2
    if 2 <= profile["avg_len"] <= 12:
        score += 1

    return score


def _score_order_id_column(col: str, name: str, profile: dict) -> float:
    positive = [
        ("订单编号", 14), ("订单号", 14), ("订单id", 12), ("订单流水号", 12),
        ("交易号", 11), ("交易单号", 11), ("单号", 8),
        ("orderid", 12), ("order_id", 12), ("orderno", 11),
    ]
    negative = [
        ("商品id", 14), ("skuid", 13), ("spuid", 13), ("用户id", 13),
        ("会员id", 13), ("城市id", 13), ("类目id", 13), ("分类id", 13),
        ("sku", 8), ("spu", 8), ("商品", 6), ("城市", 6),
    ]

    score = 0.0
    score += _keyword_score(name, positive)
    score -= _keyword_score(name, negative)

    if profile["unique_ratio"] >= 0.9:
        score += 4
    elif profile["unique_ratio"] >= 0.7:
        score += 2

    if profile["avg_len"] >= 6:
        score += 1.5

    if profile["distinct_count"] <= 3:
        score -= 4

    return score