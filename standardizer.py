import pandas as pd


STANDARD_FIELDS = ["date", "sales", "product", "quantity", "city", "order_id"]


def standardize_dataframe(df, mapping_result):
    """
    根据用户选择的字段映射，将原始 DataFrame 转换为标准字段 DataFrame
    """
    standardized_data = {}

    for standard_field in STANDARD_FIELDS:
        selected_column = mapping_result.get(standard_field)

        if selected_column and selected_column != "-- 请选择 --":
            standardized_data[standard_field] = df[selected_column]

    standardized_df = pd.DataFrame(standardized_data)

    if "date" in standardized_df.columns:
        standardized_df["date"] = pd.to_datetime(
            standardized_df["date"], errors="coerce"
        )

    if "sales" in standardized_df.columns:
        standardized_df["sales"] = pd.to_numeric(
            standardized_df["sales"], errors="coerce"
        )

    if "quantity" in standardized_df.columns:
        standardized_df["quantity"] = pd.to_numeric(
            standardized_df["quantity"], errors="coerce"
        )

    return standardized_df