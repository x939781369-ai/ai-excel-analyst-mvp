import io
from typing import Iterable

import pandas as pd


CSV_ENCODINGS_TO_TRY: list[str] = [
    "utf-8",
    "utf-8-sig",
    "gb18030",
    "gbk",
    "cp936",
]


def _read_uploaded_file_bytes(uploaded_file) -> bytes:
    """
    兼容 Streamlit UploadedFile / 普通文件对象，稳定拿到原始二进制内容。
    """
    if uploaded_file is None:
        raise ValueError("未接收到上传文件。")

    if hasattr(uploaded_file, "getvalue"):
        data = uploaded_file.getvalue()
        if not data:
            raise ValueError("上传文件为空，请重新上传。")
        return data

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    data = uploaded_file.read()

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    if not data:
        raise ValueError("上传文件为空，请重新上传。")

    return data


def _clean_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗列名：
    - 去掉前后空格
    - 去掉 BOM
    - 空列名转成字符串，避免后续映射异常
    """
    cleaned_columns = []
    for col in df.columns:
        col_text = str(col).replace("\ufeff", "").strip()
        cleaned_columns.append(col_text if col_text else "未命名列")
    df.columns = cleaned_columns
    return df


def _try_read_csv_with_encodings(file_bytes: bytes, encodings: Iterable[str]) -> pd.DataFrame:
    """
    依次尝试多种常见编码读取 CSV。
    同时让 pandas 自动猜分隔符，兼容逗号 / 制表符 / 分号。
    """
    errors: list[str] = []

    for encoding in encodings:
        try:
            text = file_bytes.decode(encoding)
            df = pd.read_csv(
                io.StringIO(text),
                sep=None,
                engine="python",
            )
            return _clean_dataframe_columns(df)
        except UnicodeDecodeError as e:
            errors.append(f"{encoding}: 编码解码失败（{e}）")
        except Exception as e:
            errors.append(f"{encoding}: 读取失败（{e}）")

    error_text = "；".join(errors[:3])
    raise ValueError(
        f"CSV 文件读取失败。已尝试 utf-8 / utf-8-sig / gb18030 / gbk 等常见编码，仍无法解析。{error_text}"
    )


def _read_excel(file_bytes: bytes) -> pd.DataFrame:
    try:
        df = pd.read_excel(io.BytesIO(file_bytes))
        return _clean_dataframe_columns(df)
    except Exception as e:
        raise ValueError(f"Excel 文件读取失败，请确认文件未损坏或格式正确。错误信息：{e}") from e


def load_file(uploaded_file):
    """
    根据文件类型读取 CSV 或 Excel 文件，返回 DataFrame
    """
    if uploaded_file is None:
        raise ValueError("请先上传文件。")

    file_name = str(getattr(uploaded_file, "name", "")).lower().strip()
    if not file_name:
        raise ValueError("无法识别文件名，请重新上传。")

    file_bytes = _read_uploaded_file_bytes(uploaded_file)

    if file_name.endswith(".csv"):
        df = _try_read_csv_with_encodings(file_bytes, CSV_ENCODINGS_TO_TRY)
    elif file_name.endswith(".xlsx") or file_name.endswith(".xls"):
        df = _read_excel(file_bytes)
    else:
        raise ValueError("不支持的文件格式，请上传 CSV / XLSX / XLS 文件。")

    if df is None or df.empty:
        raise ValueError("文件读取成功，但内容为空。请确认表格中存在数据。")

    return df