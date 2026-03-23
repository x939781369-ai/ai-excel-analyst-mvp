import pandas as pd


def load_file(uploaded_file):
    """
    根据文件类型读取 CSV 或 Excel 文件，返回 DataFrame
    """
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    elif file_name.endswith(".xlsx") or file_name.endswith(".xls"):
        return pd.read_excel(uploaded_file)
    else:
        raise ValueError("不支持的文件格式，请上传 CSV 或 Excel 文件。")