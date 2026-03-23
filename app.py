import csv
import json
import os
import re
from datetime import datetime, timedelta
from html import escape

import pandas as pd
import streamlit as st
import numpy as np

from charts import (
    create_daily_sales_chart,
    create_top_cities_chart,
    create_top_products_chart,
)
from data_loader import load_file
from exporter import build_html_report
from metrics import calculate_all_metrics
from reporter import generate_ai_report
from rules import generate_rule_based_analysis
from standardizer import standardize_dataframe

try:
    from field_mapper import (
        NO_SELECTION as FIELD_MAPPER_PLACEHOLDER,
        get_default_mapping,
        get_field_options,
    )
except Exception:
    FIELD_MAPPER_PLACEHOLDER = "-- 请选择 --"

    def get_field_options(columns):
        return [FIELD_MAPPER_PLACEHOLDER] + [str(col) for col in columns]

    def get_default_mapping(df):
        columns = [str(col) for col in getattr(df, "columns", [])]
        return {
            "date": columns[0] if len(columns) > 0 else FIELD_MAPPER_PLACEHOLDER,
            "sales": columns[1] if len(columns) > 1 else FIELD_MAPPER_PLACEHOLDER,
            "product": FIELD_MAPPER_PLACEHOLDER,
            "quantity": FIELD_MAPPER_PLACEHOLDER,
            "city": FIELD_MAPPER_PLACEHOLDER,
            "order_id": FIELD_MAPPER_PLACEHOLDER,
        }

st.set_page_config(page_title="AI Excel 数据分析助手", layout="wide")


# =========================
# 基础配置
# =========================
EVENT_LOG_FILE = "event_log.csv"
FEEDBACK_LOG_FILE = "feedback_log.csv"
SESSION_SUMMARY_FILE = "session_summary.csv"
PLACEHOLDER = "-- 请选择 --"
DEFAULT_TESTER_ID = "guest"
DEFAULT_TESTER_ROLE = ""
DEFAULT_TESTER_CONTACT = ""
FIELD_LABELS = {
    "date": "日期",
    "sales": "销售额",
    "product": "商品",
    "quantity": "数量",
    "city": "城市",
    "order_id": "订单号",
}


# =========================
# 日志与状态
# =========================
def init_session_state():
    defaults = {
        "tester_id": DEFAULT_TESTER_ID,
        "tester_role": DEFAULT_TESTER_ROLE,
        "tester_contact": DEFAULT_TESTER_CONTACT,
        "analysis_result": None,
        "analysis_signature": None,
        "last_logged_analysis_signature": None,
        "last_logged_file_signature": None,
        "active_source": "none",
        "demo_mode": False,
        "demo_logged": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# =========================
# 基础工具函数
# =========================
def append_row_to_csv(file_path: str, row: dict, fieldnames: list[str]):
    file_exists = os.path.exists(file_path)
    with open(file_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def make_json_safe(obj):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [make_json_safe(v) for v in obj]
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    if isinstance(obj, pd.Period):
        return str(obj)
    if obj is pd.NA:
        return None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    if hasattr(obj, "item") and callable(getattr(obj, "item")):
        try:
            return make_json_safe(obj.item())
        except Exception:
            pass
    return obj


def log_event(event_name: str, payload: dict | None = None):
    safe_payload = make_json_safe(payload or {})
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tester_id": st.session_state.get("tester_id", DEFAULT_TESTER_ID),
        "role": st.session_state.get("tester_role", ""),
        "contact": st.session_state.get("tester_contact", ""),
        "event_name": event_name,
        "payload_json": json.dumps(safe_payload, ensure_ascii=False),
    }
    append_row_to_csv(
        EVENT_LOG_FILE,
        row,
        fieldnames=[
            "timestamp",
            "tester_id",
            "role",
            "contact",
            "event_name",
            "payload_json",
        ],
    )


def save_feedback_row(row: dict):
    base_row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tester_id": st.session_state.get("tester_id", DEFAULT_TESTER_ID),
        "role": st.session_state.get("tester_role", ""),
        "contact": st.session_state.get("tester_contact", ""),
    }
    base_row.update(row)

    append_row_to_csv(
        FEEDBACK_LOG_FILE,
        base_row,
        fieldnames=[
            "timestamp",
            "tester_id",
            "role",
            "contact",
            "helpful",
            "favorite_module",
            "unclear_step",
            "preferred_mode",
            "next_feature",
            "continue_testing",
            "feedback_contact",
        ],
    )


def save_session_summary(row: dict):
    base_row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tester_id": st.session_state.get("tester_id", DEFAULT_TESTER_ID),
        "role": st.session_state.get("tester_role", ""),
        "contact": st.session_state.get("tester_contact", ""),
    }
    base_row.update(row)

    append_row_to_csv(
        SESSION_SUMMARY_FILE,
        base_row,
        fieldnames=[
            "timestamp",
            "tester_id",
            "role",
            "contact",
            "file_name",
            "period_mode",
            "current_label",
            "previous_label",
            "rows",
            "cols",
            "total_sales",
            "order_count",
            "avg_order_value",
            "selected_date_col",
            "selected_sales_col",
            "selected_product_col",
            "selected_quantity_col",
            "selected_city_col",
            "selected_order_id_col",
            "source_type",
        ],
    )


def reset_analysis_only():
    st.session_state["analysis_result"] = None
    st.session_state["analysis_signature"] = None


def humanize_source_error_message(error: Exception) -> str:
    text = str(error)
    if "不支持的文件格式" in text:
        return "这份文件格式暂不支持。请上传 CSV、XLSX 或 XLS 文件。"
    if "CSV 文件读取失败" in text:
        return "文件已收到，但 CSV 读取失败。常见原因是编码或分隔符不标准。你可以先用 Excel 重新另存为 UTF-8 CSV，或直接上传 XLSX。"
    if "Excel 文件读取失败" in text:
        return "Excel 文件已收到，但暂时无法解析。请确认文件未损坏、未加密，或重新另存一份后再上传。"
    if "文件读取成功，但内容为空" in text or "上传文件为空" in text:
        return "文件已经读到，但里面没有可分析的数据。请确认表格里确实有正文数据，而不只是表头。"
    return f"文件已收到，但读取失败。建议先确认文件格式、编码和内容是否完整。原始提示：{text}"


def humanize_analysis_error_message(error: Exception) -> str:
    text = str(error)
    lowered = text.lower()

    if "没有可用的字段映射结果" in text or "至少选择日期和销售额" in text:
        return "系统还没识别到可用字段。至少需要【日期列】和【销售额列】才能生成基础分析。你可以在高级设置里手动指定。"
    if "out of bounds" in lowered or "date" in lowered and "timestamp" in lowered:
        return "日期列里存在异常日期，系统暂时无法稳定解析。建议检查是否混入了错误日期、纯文本说明或极端年份。"
    if "sales" in lowered and "keyerror" in lowered:
        return "销售额列暂时不可用。建议检查该列是否被误选，或金额格式是否过于混杂。"
    if "json serializable" in lowered:
        return "系统在记录分析过程时遇到了异常数据格式。你可以直接重试；如果仍失败，把文件样例发我继续修。"
    if "division by zero" in lowered:
        return "当前数据里有效订单数过少，导致部分指标无法稳定计算。建议补充订单号列，或先使用整体分析。"
    return f"这份数据已经进入分析流程，但中途失败了。你可以先检查字段识别是否正确，或先切到整体分析试一次。原始提示：{text}"


def build_field_health_summary(mapping_result: dict) -> dict:
    recognized_fields = []
    missing_optional_fields = []
    impact_messages = []

    for field_key, field_label in FIELD_LABELS.items():
        selected_value = mapping_result.get(field_key)
        if selected_value and selected_value != PLACEHOLDER:
            recognized_fields.append(field_label)
        elif field_key not in {"date", "sales"}:
            missing_optional_fields.append(field_label)

    if mapping_result.get("product") in {None, PLACEHOLDER}:
        impact_messages.append("未识别商品列：不会输出商品排行和核心商品判断。")
    if mapping_result.get("city") in {None, PLACEHOLDER}:
        impact_messages.append("未识别城市列：不会输出城市排行和核心城市判断。")
    if mapping_result.get("quantity") in {None, PLACEHOLDER}:
        impact_messages.append("未识别数量列：销量 / 件数相关分析会减少。")
    if mapping_result.get("order_id") in {None, PLACEHOLDER}:
        impact_messages.append("未识别订单号列：订单数将按明细行估算，客单价可信度会略低。")

    recognized_count = len(recognized_fields)
    if recognized_count >= 5:
        level = "good"
    elif recognized_count >= 3:
        level = "medium"
    else:
        level = "low"

    return {
        "recognized_fields": recognized_fields,
        "recognized_count": recognized_count,
        "missing_optional_fields": missing_optional_fields,
        "impact_messages": impact_messages,
        "level": level,
    }


def build_quality_summary(standardized_df: pd.DataFrame, mapping_result: dict, requested_mode: str, effective_mode: str, metrics_result: dict, fallback_notes: list[str]) -> dict:
    row_count = int(len(standardized_df)) if standardized_df is not None else 0
    valid_sales_rows = int(metrics_result.get("valid_sales_rows") or 0)
    date_min = metrics_result.get("date_min")
    date_max = metrics_result.get("date_max")
    coverage_days = None
    if date_min and date_max:
        try:
            coverage_days = (pd.to_datetime(date_max) - pd.to_datetime(date_min)).days + 1
        except Exception:
            coverage_days = None

    issues = []
    next_steps = []
    score = 100

    if row_count < 10:
        issues.append("有效数据行较少，结果更适合作为初步参考。")
        score -= 28
    elif row_count < 30:
        issues.append("数据量偏少，趋势和结构判断的稳定性一般。")
        score -= 16

    if valid_sales_rows == 0:
        issues.append("销售额列几乎没有可用数值，核心指标可信度较低。")
        score -= 40
    elif valid_sales_rows < max(5, row_count * 0.6):
        issues.append("部分销售额数据未成功清洗，可用数值占比偏低。")
        score -= 20

    if mapping_result.get("order_id") in {None, PLACEHOLDER}:
        issues.append("未识别订单号列，订单数与客单价按明细估算。")
        next_steps.append("补充订单号列后，订单数和客单价会更稳。")
        score -= 10

    if mapping_result.get("product") in {None, PLACEHOLDER}:
        next_steps.append("补充商品列后，可以获得商品排行和核心商品分析。")
        score -= 4

    if mapping_result.get("city") in {None, PLACEHOLDER}:
        next_steps.append("补充城市列后，可以获得城市排行和区域贡献分析。")
        score -= 4

    if requested_mode in {"week", "month"} and effective_mode == "overall":
        issues.append("当前文件不足以完成连续周期对比，系统已自动降级为整体分析。")
        next_steps.append("补充覆盖连续两个自然周 / 自然月的数据后，再使用周期对比会更合适。")
        score -= 12

    if coverage_days is not None and coverage_days < 7:
        issues.append(f"当前数据仅覆盖 {coverage_days} 天，趋势判断容易受短期波动影响。")
        score -= 12
    elif coverage_days is not None and coverage_days < 21 and requested_mode == "month":
        issues.append("当前数据覆盖天数偏短，按月对比的参考价值有限。")
        score -= 10

    for note in fallback_notes or []:
        if note not in issues:
            issues.append(note)

    if score >= 82:
        level = "high"
        title = "结果可信度：较高"
        summary = "关键字段和数据量整体较完整，当前结果可直接用于初步判断。"
    elif score >= 60:
        level = "medium"
        title = "结果可信度：中等"
        summary = "基础结论可看，但部分字段或数据覆盖不足，建议结合原始表再确认。"
    else:
        level = "low"
        title = "结果可信度：偏低"
        summary = "这次结果更适合用来排查方向，不建议直接拿去做正式判断。"

    if not next_steps:
        next_steps.append("若你准备给同事或朋友试用，建议优先上传覆盖更完整时间范围的数据。")

    return {
        "level": level,
        "title": title,
        "summary": summary,
        "issues": issues[:4],
        "next_steps": next_steps[:4],
        "row_count": row_count,
        "valid_sales_rows": valid_sales_rows,
        "coverage_days": coverage_days,
    }


def render_field_health_summary(field_health: dict, compact: bool = False):
    recognized = "、".join(field_health.get("recognized_fields") or []) or "暂无"
    impacts = field_health.get("impact_messages") or []
    missing_optional = field_health.get("missing_optional_fields") or []

    if compact:
        st.info(
            f"已识别 {field_health.get('recognized_count', 0)}/6 个关键字段：{recognized}。"
            + (f" 未识别：{'、'.join(missing_optional)}。" if missing_optional else "")
        )
        return

    if field_health.get("level") == "good":
        st.success(f"字段识别情况：已识别 {field_health.get('recognized_count', 0)}/6 个关键字段（{recognized}）。")
    elif field_health.get("level") == "medium":
        st.info(f"字段识别情况：已识别 {field_health.get('recognized_count', 0)}/6 个关键字段（{recognized}）。")
    else:
        st.warning(f"字段识别情况：当前仅识别到 {field_health.get('recognized_count', 0)}/6 个关键字段（{recognized}）。")

    if impacts:
        st.caption("；".join(impacts))


def render_quality_notice(quality_summary: dict):
    message = quality_summary.get("summary", "")
    issues = quality_summary.get("issues") or []
    if issues:
        message = message + " 需要注意：" + "；".join(issues)

    if quality_summary.get("level") == "high":
        st.success(f"{quality_summary.get('title')}｜{message}")
    elif quality_summary.get("level") == "medium":
        st.info(f"{quality_summary.get('title')}｜{message}")
    else:
        st.warning(f"{quality_summary.get('title')}｜{message}")


def render_next_step_guidance(quality_summary: dict):
    next_steps = quality_summary.get("next_steps") or []
    if not next_steps:
        return

    bullet_html = "".join([f"<li style='margin-bottom:6px;'>{escape(str(item))}</li>" for item in next_steps])
    st.markdown(
        f"""
        <div style="
            border-radius:16px;
            padding:16px 18px;
            margin: 0.2rem 0 0.9rem 0;
            background: linear-gradient(180deg, #f8fbff 0%, #f2f7ff 100%);
            border:1px solid #dce9f7;
        ">
            <div style="font-size:1rem;font-weight:800;color:#163a70;margin-bottom:8px;">建议下一步这样做</div>
            <ul style="margin:0 0 0 1.1rem;padding:0;color:#36506b;line-height:1.75;">{bullet_html}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================
# 页面组件
# =========================
def inject_custom_css():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 3rem;
            max-width: 1180px;
        }

        div.stButton > button,
        div.stDownloadButton > button {
            background: linear-gradient(90deg, #79beff 0%, #2f80ed 100%);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 0.62rem 1.25rem;
            font-weight: 700;
            font-size: 0.98rem;
            box-shadow: 0 6px 16px rgba(47, 128, 237, 0.22);
            transition: all 0.2s ease-in-out;
        }

        div.stButton > button:hover,
        div.stDownloadButton > button:hover {
            background: linear-gradient(90deg, #6fb6ff 0%, #236ad1 100%);
            color: white;
            transform: translateY(-1px);
            box-shadow: 0 8px 18px rgba(47, 128, 237, 0.28);
        }

        div[data-testid="stAlert"] {
            border-radius: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_custom_css()


def render_section_title(text: str, caption: str | None = None):
    st.markdown(
        f"""
        <div style="margin-top: 1rem; margin-bottom: 0.45rem;">
            <div style="
                font-size: 1.42rem;
                font-weight: 800;
                color: #163a70;
                letter-spacing: -0.01em;
                line-height: 1.2;
            ">{text}</div>
            <div style="
                width: 58px;
                height: 4px;
                margin-top: 8px;
                border-radius: 999px;
                background: linear-gradient(90deg, #7cc0ff 0%, #2f80ed 100%);
            "></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if caption:
        st.caption(caption)


def render_multiline_text(text: str):
    if text:
        st.markdown(text.replace("\n", "  \n"))


def highlight_report_text(text: str) -> str:
    if not text:
        return ""

    escaped_text = escape(str(text))

    number_styles = [
        (r"[+-]?\d[\d,]*(?:\.\d+)?\s*%", "#eaf3ff", "#1559c1"),
        (r"[+-]?\d[\d,]*(?:\.\d+)?\s*元", "#eefaf2", "#18794e"),
        (r"[+-]?\d[\d,]*(?:\.\d+)?\s*单", "#eefaf2", "#18794e"),
        (r"[+-]?\d[\d,]*(?:\.\d+)?\s*(?:件|个)", "#eefaf2", "#18794e"),
        (r"(?:\d{1,3}(?:,\d{3})+|\d+\.\d+)", "#f4f7fb", "#20456d"),
    ]

    word_styles = [
        (["集中度较高", "依赖过强", "上升", "增长", "提升", "提高", "带动", "增加"], "#edf9f1", "#1f8f57"),
        (["下降", "减少", "下滑", "走弱", "风险"], "#fff2f0", "#d14d41"),
        (["整体分析", "数据不足", "无法完成", "无法识别", "无法计算", "持平"], "#f4f6f8", "#68778a"),
    ]

    token_specs = []
    for idx, (pattern, bg, color) in enumerate(number_styles):
        token_specs.append((f"num_{idx}", pattern, bg, color, "number"))

    word_idx = 0
    for words, bg, color in word_styles:
        for word in sorted(words, key=len, reverse=True):
            token_specs.append((f"word_{word_idx}", re.escape(word), bg, color, "word"))
            word_idx += 1

    style_map = {name: (bg, color, token_type) for name, _, bg, color, token_type in token_specs}
    combined_pattern = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern, _, _, _ in token_specs))

    parts = []
    last_end = 0
    for match in combined_pattern.finditer(escaped_text):
        parts.append(escaped_text[last_end:match.start()])
        bg, color, token_type = style_map[match.lastgroup]
        token = match.group(0)
        if token_type == "number":
            parts.append(
                f"<span style='display:inline-block;padding:0.04rem 0.42rem;margin:0 0.06rem;"
                f"border-radius:0.55rem;background:{bg};color:{color};font-weight:800;'>"
                f"{token}</span>"
            )
        else:
            parts.append(
                f"<span style='padding:0.02rem 0.34rem;border-radius:0.48rem;"
                f"background:{bg};color:{color};font-weight:700;'>{token}</span>"
            )
        last_end = match.end()

    parts.append(escaped_text[last_end:])
    return "".join(parts).replace("\n", "<br>")




def render_subsection_title(text: str):
    st.markdown(
        f"""
        <div style="
            margin-top: 0.55rem;
            margin-bottom: 0.4rem;
            font-size: 1.05rem;
            font-weight: 800;
            color: #1a4f93;
            line-height: 1.45;
        ">{text}</div>
        """,
        unsafe_allow_html=True,
    )

def render_highlight_paragraph(text: str, bg: str = "#fbfdff"):
    if not text:
        return

    st.markdown(
        f"""
        <div style="
            border-radius: 14px;
            padding: 14px 16px;
            margin-bottom: 10px;
            background: {bg};
            border: 1px solid #e4edf7;
            color: #16324f;
            line-height: 1.9;
            font-size: 0.98rem;
            font-weight: 600;
        ">
            {highlight_report_text(text)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_highlighted_report(text: str):
    if not text:
        return

    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    for line in lines:
        if re.match(r"^[一二三四五六七八九十]+、", line):
            render_subsection_title(line)
        else:
            render_highlight_paragraph(line)


def render_rule_item(label: str, text: str):
    st.markdown(
        f"""
        <div style="
            border-radius: 14px;
            padding: 15px 16px;
            margin-bottom: 12px;
            background: linear-gradient(180deg, #fcfdff 0%, #f6faff 100%);
            border: 1px solid #e2ecf8;
            box-shadow: 0 4px 12px rgba(17, 24, 39, 0.04);
        ">
            <div style="
                display: inline-block;
                margin-bottom: 10px;
                padding: 0.26rem 0.72rem;
                border-radius: 999px;
                background: #eaf3ff;
                color: #1c5bb8;
                font-size: 0.84rem;
                font-weight: 800;
            ">{label}</div>
            <div style="
                color: #16324f;
                line-height: 1.9;
                font-size: 0.98rem;
                font-weight: 600;
            ">{highlight_report_text(text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_insight_card(title: str, content: str, accent: str, bg: str):
    st.markdown(
        f"""
        <div style="
            border-radius: 16px;
            padding: 18px 18px 16px 18px;
            background: {bg};
            border: 1px solid rgba(28, 76, 140, 0.08);
            box-shadow: 0 6px 18px rgba(17, 24, 39, 0.05);
            min-height: 188px;
        ">
            <div style="
                display: inline-block;
                font-size: 0.84rem;
                font-weight: 700;
                color: white;
                background: {accent};
                border-radius: 999px;
                padding: 0.28rem 0.72rem;
                margin-bottom: 12px;
            ">{title}</div>
            <div style="
                font-size: 1rem;
                font-weight: 600;
                color: #16324f;
                line-height: 1.7;
            ">{highlight_report_text(content)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_change_meta(change_rate):
    if change_rate is None or pd.isna(change_rate):
        return {
            "direction": "暂无对比",
            "display": "--",
            "chip_bg": "#f4f6f8",
            "chip_color": "#68778a",
            "accent": "linear-gradient(90deg, #9fb3c8 0%, #7f95ad 100%)",
            "card_bg": "linear-gradient(180deg, #fbfdff 0%, #f6f9fc 100%)",
            "border": "#dfe7f0",
        }

    pct = abs(change_rate) * 100
    if change_rate > 0:
        return {
            "direction": "上升",
            "display": f"+{pct:.1f}%",
            "chip_bg": "#edf9f1",
            "chip_color": "#1f8f57",
            "accent": "linear-gradient(90deg, #39b36f 0%, #1f9d59 100%)",
            "card_bg": "linear-gradient(180deg, #f3fcf7 0%, #ecf9f1 100%)",
            "border": "#d8efe1",
        }
    elif change_rate < 0:
        return {
            "direction": "下降",
            "display": f"-{pct:.1f}%",
            "chip_bg": "#fff2f0",
            "chip_color": "#d14d41",
            "accent": "linear-gradient(90deg, #f28a7b 0%, #d95c4f 100%)",
            "card_bg": "linear-gradient(180deg, #fff8f7 0%, #fff1ef 100%)",
            "border": "#f5ddd8",
        }
    else:
        return {
            "direction": "持平",
            "display": "0.0%",
            "chip_bg": "#f4f6f8",
            "chip_color": "#68778a",
            "accent": "linear-gradient(90deg, #93a7bc 0%, #6f879f 100%)",
            "card_bg": "linear-gradient(180deg, #fbfdff 0%, #f5f8fb 100%)",
            "border": "#dfe7f0",
        }



def build_value_pill(value_text: str, bg: str = "#f4f7fb", color: str = "#20456d") -> str:
    return (
        f"<span style=\"display:inline-block;padding:0.1rem 0.5rem;border-radius:999px;"
        f"background:{bg};color:{color};font-weight:800;\">{escape(str(value_text))}</span>"
    )


def render_numeric_conclusion_card(
    title: str,
    current_value: str,
    previous_value: str | None,
    change_rate,
    current_label: str,
    previous_label: str | None,
):
    is_overall_mode = not previous_value or not previous_label
    if is_overall_mode:
        meta = {
            "direction": "整体分析",
            "display": current_value,
            "chip_bg": "#eef4fb",
            "chip_color": "#1c5bb8",
            "card_bg": "linear-gradient(180deg, #fbfdff 0%, #f6f9fc 100%)",
            "border": "#dfe7f0",
        }
    else:
        meta = get_change_meta(change_rate)

    current_line = (
        f"<div style='margin-bottom:8px;'>"
        f"<span style='font-weight:700;color:#1d4f91;'>当前：</span>"
        f"<span style='color:#5b6f86;'>{escape(str(current_label))}</span>｜"
        f"{build_value_pill(current_value, bg='#eef4fb', color='#163a70')}"
        f"</div>"
    )

    if previous_value and previous_label:
        secondary_line = (
            f"<div>"
            f"<span style='font-weight:700;color:#7a8795;'>对比：</span>"
            f"<span style='color:#5b6f86;'>{escape(str(previous_label))}</span>｜"
            f"{build_value_pill(previous_value, bg='#f5f7fa', color='#5b6f86')}"
            f"</div>"
        )
    else:
        secondary_line = (
            f"<div>"
            f"<span style='font-weight:700;color:#7a8795;'>说明：</span>"
            f"<span style='color:#5b6f86;'>当前为整体分析模式，不进行周期对比。</span>"
            f"</div>"
        )

    compare_html = (
        f"<div style='margin-top:12px;font-size:0.92rem;color:#5b6f86;line-height:1.8;'>"
        f"{current_line}{secondary_line}"
        f"</div>"
    )

    st.markdown(
        f"""
        <div style="
            border-radius: 18px;
            padding: 18px;
            background: {meta['card_bg']};
            border: 1px solid {meta['border']};
            box-shadow: 0 8px 20px rgba(17, 24, 39, 0.05);
            min-height: 188px;
        ">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
                <div>
                    <div style="font-size: 0.95rem; color: #64788f; font-weight: 700; margin-bottom: 10px;">{escape(str(title))}</div>
                    <div style="font-size: 2rem; color: #163a70; font-weight: 900; line-height: 1.08;">{escape(str(meta['display']))}</div>
                </div>
                <div style="padding:0.28rem 0.72rem;border-radius:999px;background:{meta['chip_bg']};color:{meta['chip_color']};font-size:0.9rem;font-weight:800;">{meta['direction']}</div>
            </div>
            {compare_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def extract_report_key_badges(text: str) -> list[str]:
    if not text:
        return []

    patterns = [
        r"[+-]?\d[\d,]*(?:\.\d+)?\s*%",
        r"[+-]?\d[\d,]*(?:\.\d+)?\s*元",
        r"[+-]?\d[\d,]*(?:\.\d+)?\s*单",
        r"[+-]?\d[\d,]*(?:\.\d+)?\s*(?:件|个)",
        r"[“\"「『][^”\"」』]{1,20}[”\"」』]",
        r"\[[^\]]{1,20}\]",
    ]
    found = []
    for pattern in patterns:
        found.extend(re.findall(pattern, str(text)))

    cleaned = []
    seen = set()
    for item in found:
        token = str(item).strip()
        if token and token not in seen:
            seen.add(token)
            cleaned.append(token)
        if len(cleaned) >= 4:
            break
    return cleaned


def render_professional_rule_card(title: str, text: str):
    badges = extract_report_key_badges(text)
    badges_html = ""
    if badges:
        badge_parts = []
        for token in badges:
            badge_parts.append(
                f"<span style='display:inline-block;padding:0.18rem 0.55rem;border-radius:999px;"
                f"background:#eef4fb;color:#1c5bb8;font-size:0.84rem;font-weight:800;margin:0 0.45rem 0.45rem 0;'>"
                f"{escape(token)}</span>"
            )
        badges_html = (
            "<div style='margin-top:14px;'>"
            "<div style='font-size:0.82rem;color:#7a8a9a;font-weight:700;margin-bottom:8px;'>关键数据</div>"
            f"{''.join(badge_parts)}"
            "</div>"
        )

    st.markdown(
        f"""
        <div style="
            border-radius: 16px;
            padding: 18px 18px 16px 18px;
            margin-bottom: 12px;
            background: linear-gradient(180deg, #fcfdff 0%, #f7fbff 100%);
            border: 1px solid #e2ecf8;
            box-shadow: 0 6px 18px rgba(17, 24, 39, 0.04);
            min-height: 210px;
        ">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;">
                <div style="font-size:1rem;font-weight:800;color:#163a70;">{escape(str(title))}</div>
                <div style="padding:0.24rem 0.68rem;border-radius:999px;background:#eaf3ff;color:#1c5bb8;font-size:0.8rem;font-weight:800;">系统判断</div>
            </div>
            <div style="font-size:0.82rem;color:#7a8a9a;font-weight:700;margin-bottom:8px;">核心结论</div>
            <div style="color:#16324f;line-height:1.9;font-size:0.98rem;font-weight:600;">{highlight_report_text(text)}</div>
            {badges_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_priority_summary_text(metrics_result: dict, rule_analysis: dict) -> str:
    comparison = metrics_result.get("period_comparison")
    if comparison is None:
        return rule_analysis.get("top_change", "当前数据不足，暂时无法识别最重要变化。")

    if comparison.get("period_mode") == "overall":
        total_sales = format_value(metrics_result.get("total_sales"), 2, " 元")
        order_count = format_value(metrics_result.get("order_count"), 0, " 单")
        avg_order_value = format_value(metrics_result.get("avg_order_value"), 2, " 元")
        return f"整体概览：总销售额 {total_sales}，订单数 {order_count}，客单价 {avg_order_value}。{rule_analysis.get('top_change', '')}"

    sales_meta = get_change_meta(comparison.get("sales_change_rate"))
    order_meta = get_change_meta(comparison.get("order_change_rate"))
    avg_meta = get_change_meta(comparison.get("avg_order_value_change_rate"))
    return (
        f"核心结论：销售额{sales_meta['direction']} {sales_meta['display']}，"
        f"订单数{order_meta['direction']} {order_meta['display']}，"
        f"客单价{avg_meta['direction']} {avg_meta['display']}。"
        f"{rule_analysis.get('top_change', '')}"
    )


def render_priority_summary(metrics_result: dict, rule_analysis: dict):
    summary_text = build_priority_summary_text(metrics_result, rule_analysis)
    render_highlight_paragraph(summary_text, bg="#f7fbff")


def render_hero_banner():
    st.markdown(
        """
        <div style="
            border-radius: 22px;
            padding: 26px 24px;
            background: linear-gradient(135deg, #f5fbff 0%, #eef6ff 48%, #f9fcff 100%);
            border: 1px solid rgba(52, 121, 212, 0.12);
            box-shadow: 0 10px 30px rgba(18, 55, 97, 0.06);
            margin-bottom: 14px;
        ">
            <div style="font-size: 2rem; font-weight: 900; color: #123761; line-height: 1.15; margin-bottom: 10px;">
                AI Excel 数据分析助手
            </div>
            <div style="font-size: 1.05rem; color: #304a63; line-height: 1.8; margin-bottom: 12px;">
                先看价值，再决定是否上传自己的数据。支持直接体验示例数据，也支持上传 Excel / CSV 自动生成结论、图表和汇报报告。
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px;">
                <div style="background: white; border: 1px solid #d8e7f7; color: #234a75; padding: 8px 12px; border-radius: 999px; font-weight: 700; font-size: 0.92rem;">可先试示例数据</div>
                <div style="background: white; border: 1px solid #d8e7f7; color: #234a75; padding: 8px 12px; border-radius: 999px; font-weight: 700; font-size: 0.92rem;">支持按周 / 按月分析</div>
                <div style="background: white; border: 1px solid #d8e7f7; color: #234a75; padding: 8px 12px; border-radius: 999px; font-weight: 700; font-size: 0.92rem;">默认自动识别字段</div>
                <div style="background: white; border: 1px solid #d8e7f7; color: #234a75; padding: 8px 12px; border-radius: 999px; font-weight: 700; font-size: 0.92rem;">结果支持导出</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_value(value, decimals=2, suffix=""):
    if value is None or pd.isna(value):
        return "无法计算"
    if decimals == 0:
        return f"{int(round(value)):,}{suffix}"
    return f"{value:,.{decimals}f}{suffix}"


def format_delta(change_rate):
    if change_rate is None or pd.isna(change_rate):
        return None
    return f"{change_rate * 100:+.1f}%"


def metric_card(label, value_text, delta_text=None, help_text=None):
    extra = ""
    if delta_text:
        extra = f"<div style='margin-top:8px;font-size:0.92rem;font-weight:700;color:#2f80ed;'>{delta_text}</div>"
    help_html = ""
    if help_text:
        help_html = f"<div style='margin-top:8px;font-size:0.9rem;color:#5c7089;line-height:1.6;'>{help_text}</div>"

    st.markdown(
        f"""
        <div style="
            border-radius: 16px;
            padding: 18px;
            background: white;
            border: 1px solid #dfe9f5;
            box-shadow: 0 8px 20px rgba(17, 24, 39, 0.05);
            min-height: 132px;
        ">
            <div style="font-size: 0.94rem; color: #6a7f95; font-weight: 600; margin-bottom: 12px;">{label}</div>
            <div style="font-size: 1.9rem; color: #163a70; font-weight: 900; line-height: 1.15;">{value_text}</div>
            {extra}
            {help_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================
# 示例数据与字段识别
# =========================
def build_demo_dataframe() -> pd.DataFrame:
    base_date = datetime.now().date() - timedelta(days=59)
    cities = ["北京", "上海", "广州", "深圳", "杭州"]
    products = ["轻奢保温杯", "无线耳机", "办公椅", "筋膜枪", "护眼台灯"]
    rows = []

    for day_offset in range(60):
        current_date = base_date + timedelta(days=day_offset)
        for idx, city in enumerate(cities):
            product = products[(day_offset + idx) % len(products)]
            quantity = (day_offset + idx) % 4 + 1
            base_sales = 129 + (idx * 23)
            seasonality = (day_offset % 7) * 6
            trend = day_offset * 2.3
            sales = round((base_sales + seasonality + trend) * quantity, 2)
            rows.append(
                {
                    "订单日期": current_date.strftime("%Y-%m-%d"),
                    "订单编号": f"DEMO{current_date.strftime('%Y%m%d')}{idx + 1:02d}",
                    "商品名称": product,
                    "城市": city,
                    "销量": quantity,
                    "实付金额": sales,
                }
            )

    return pd.DataFrame(rows)


def selectbox_index(options: list, selected_value: str) -> int:
    return options.index(selected_value) if selected_value in options else 0


def build_mapping_result(
    date_col: str,
    sales_col: str,
    product_col: str,
    quantity_col: str,
    city_col: str,
    order_id_col: str,
) -> dict:
    return {
        "date": date_col,
        "sales": sales_col,
        "product": product_col,
        "quantity": quantity_col,
        "city": city_col,
        "order_id": order_id_col,
    }


# =========================
# 数据源
# =========================
def get_current_source():
    render_section_title("开始体验", "可以直接上传你的数据，也可以先用示例数据体验完整流程。")

    source_col1, source_col2 = st.columns([1.2, 1])
    with source_col1:
        uploaded_file = st.file_uploader(
            "上传 Excel 或 CSV 数据文件",
            type=["csv", "xlsx", "xls"],
            help="建议优先上传脱敏后的销售数据。",
        )
    with source_col2:
        st.markdown("#### 还不想上传真实数据？")
        st.caption("先体验示例数据，看到结果后再决定是否上传自己的文件。")
        if st.button("一键体验示例数据", use_container_width=True):
            st.session_state["demo_mode"] = True
            st.session_state["active_source"] = "demo"
            reset_analysis_only()
            if not st.session_state.get("demo_logged", False):
                log_event("use_demo_data")
                st.session_state["demo_logged"] = True
            st.rerun()

        if st.session_state.get("demo_mode", False):
            if st.button("退出示例数据模式", use_container_width=True):
                st.session_state["demo_mode"] = False
                st.session_state["active_source"] = "none"
                reset_analysis_only()
                st.rerun()

    if uploaded_file is not None:
        st.session_state["demo_mode"] = False
        st.session_state["active_source"] = "upload"
        return {
            "source_type": "upload",
            "name": uploaded_file.name,
            "signature": f"upload::{uploaded_file.name}::{uploaded_file.size}",
            "df": load_file(uploaded_file),
            "uploaded_file": uploaded_file,
        }

    if st.session_state.get("demo_mode", False):
        demo_df = build_demo_dataframe()
        return {
            "source_type": "demo",
            "name": "示例销售数据",
            "signature": f"demo::{len(demo_df)}::{demo_df['订单日期'].min()}::{demo_df['订单日期'].max()}",
            "df": demo_df,
            "uploaded_file": None,
        }

    return None


# =========================
# 分析执行
# =========================
def build_analysis_signature(file_signature: str, period_mode: str, mapping_result: dict) -> str:
    ordered_values = [mapping_result.get(k, "") for k in ["date", "sales", "product", "quantity", "city", "order_id"]]
    return f"{file_signature}::{period_mode}::{'|'.join(ordered_values)}"


def analyze_dataset(df: pd.DataFrame, mapping_result: dict, period_mode: str) -> dict:
    standardized_df = standardize_dataframe(df, mapping_result)
    if standardized_df is None or standardized_df.empty:
        raise ValueError("字段已识别，但清洗后没有剩余可分析数据。请检查日期列和销售额列是否真的包含有效内容。")

    requested_period_mode = period_mode
    effective_period_mode = period_mode
    fallback_notes = []

    metrics_result = calculate_all_metrics(standardized_df, period_mode=requested_period_mode)
    if requested_period_mode in {"week", "month"} and metrics_result.get("period_comparison") is None:
        effective_period_mode = "overall"
        if requested_period_mode == "week":
            fallback_notes.append("当前文件未覆盖连续两个自然周，系统已自动切换为整体分析，基础结果仍可正常查看。")
        else:
            fallback_notes.append("当前文件未覆盖连续两个自然月，系统已自动切换为整体分析，基础结果仍可正常查看。")
        metrics_result = calculate_all_metrics(standardized_df, period_mode=effective_period_mode)

    if not metrics_result.get("valid_sales_rows"):
        raise ValueError("系统识别到了销售额列，但有效销售额数据不足。建议检查金额格式，或确认是否误选成了单价列。")

    rule_analysis = generate_rule_based_analysis(metrics_result)

    try:
        boss_report = generate_ai_report(metrics_result, rule_analysis, report_type="boss")
    except Exception:
        boss_report = "AI 摘要暂时生成失败，当前已优先展示系统分析结论。建议先查看上面的关键结论和指标卡。"
        fallback_notes.append("AI 摘要生成失败，已自动保留系统规则结论。")

    try:
        operations_report = generate_ai_report(metrics_result, rule_analysis, report_type="operations")
    except Exception:
        operations_report = "运营版详细报告暂时生成失败，但本次核心指标、图表和系统结论仍可继续使用。"
        fallback_notes.append("运营版报告生成失败，已自动保留核心指标与系统结论。")

    daily_sales_chart = create_daily_sales_chart(metrics_result.get("daily_sales"))
    top_products_chart = create_top_products_chart(metrics_result.get("top_products"))
    top_cities_chart = create_top_cities_chart(metrics_result.get("top_cities"))

    html_report = build_html_report(
        metrics_result=metrics_result,
        rule_analysis=rule_analysis,
        boss_report=boss_report,
        operations_report=operations_report,
        daily_sales_chart=daily_sales_chart,
        top_products_chart=top_products_chart,
        top_cities_chart=top_cities_chart,
    )

    field_health = build_field_health_summary(mapping_result)
    quality_summary = build_quality_summary(
        standardized_df=standardized_df,
        mapping_result=mapping_result,
        requested_mode=requested_period_mode,
        effective_mode=effective_period_mode,
        metrics_result=metrics_result,
        fallback_notes=fallback_notes,
    )

    return {
        "standardized_df": standardized_df,
        "metrics_result": metrics_result,
        "rule_analysis": rule_analysis,
        "boss_report": boss_report,
        "operations_report": operations_report,
        "daily_sales_chart": daily_sales_chart,
        "top_products_chart": top_products_chart,
        "top_cities_chart": top_cities_chart,
        "html_report": html_report,
        "requested_period_mode": requested_period_mode,
        "effective_period_mode": effective_period_mode,
        "fallback_notes": fallback_notes,
        "field_health": field_health,
        "quality_summary": quality_summary,
    }


def maybe_log_file_upload(source: dict):
    if source["source_type"] != "upload":
        return

    current_file_signature = source["signature"]
    if st.session_state.get("last_logged_file_signature") == current_file_signature:
        return

    df = source["df"]
    log_event(
        "upload_file",
        {
            "file_name": source["name"],
            "rows": df.shape[0],
            "cols": df.shape[1],
        },
    )
    st.session_state["last_logged_file_signature"] = current_file_signature


def maybe_log_analysis_success(source: dict, mapping_result: dict, period_mode: str, analysis_signature: str, metrics_result: dict):
    if st.session_state.get("last_logged_analysis_signature") == analysis_signature:
        return

    comparison = metrics_result.get("period_comparison")
    log_event(
        "analysis_success",
        {
            "file_name": source["name"],
            "source_type": source["source_type"],
            "period_mode": period_mode,
            "comparison_current_label": comparison.get("current_label") if comparison else "",
            "comparison_previous_label": comparison.get("previous_label") if comparison else "",
            "rows": source["df"].shape[0],
            "cols": source["df"].shape[1],
            "total_sales": metrics_result.get("total_sales"),
            "order_count": metrics_result.get("order_count"),
            "avg_order_value": metrics_result.get("avg_order_value"),
        },
    )

    save_session_summary(
        {
            "file_name": source["name"],
            "source_type": source["source_type"],
            "period_mode": period_mode,
            "current_label": comparison.get("current_label") if comparison else "",
            "previous_label": comparison.get("previous_label") if comparison else "",
            "rows": source["df"].shape[0],
            "cols": source["df"].shape[1],
            "total_sales": metrics_result.get("total_sales"),
            "order_count": metrics_result.get("order_count"),
            "avg_order_value": metrics_result.get("avg_order_value"),
            "selected_date_col": mapping_result.get("date"),
            "selected_sales_col": mapping_result.get("sales"),
            "selected_product_col": mapping_result.get("product"),
            "selected_quantity_col": mapping_result.get("quantity"),
            "selected_city_col": mapping_result.get("city"),
            "selected_order_id_col": mapping_result.get("order_id"),
        }
    )

    st.session_state["last_logged_analysis_signature"] = analysis_signature


# =========================
# 结果展示
# =========================
def render_comparison_hint(metrics_result: dict, analysis_bundle: dict | None = None):
    comparison = metrics_result.get("period_comparison")
    fallback_notes = (analysis_bundle or {}).get("fallback_notes") or []
    for note in fallback_notes:
        st.warning(note)

    if comparison is None:
        st.warning("当前数据不足以完成真实周/月对比。你仍可先看整体结果；若想做周期分析，建议补充覆盖连续两个自然周或自然月的数据。")
        return

    current_mode = comparison.get("period_mode")
    if current_mode == "week":
        st.info(
            f"当前分析口径：按周对比｜本周期 = {comparison['current_label']}｜上周期 = {comparison['previous_label']}"
        )
    elif current_mode == "month":
        st.info(
            f"当前分析口径：按月对比｜本周期 = {comparison['current_label']}｜上周期 = {comparison['previous_label']}"
        )
    elif current_mode == "overall":
        st.info("当前分析口径：整体分析｜当前结果基于全量数据生成，不进行周期对比。")


def render_results(source: dict, mapping_result: dict, period_mode: str, analysis_bundle: dict):
    metrics_result = analysis_bundle["metrics_result"]
    rule_analysis = analysis_bundle["rule_analysis"]
    comparison = metrics_result.get("period_comparison")

    st.success("分析完成，结果已生成。")
    render_field_health_summary(analysis_bundle.get("field_health") or build_field_health_summary(mapping_result), compact=False)
    render_quality_notice(analysis_bundle.get("quality_summary") or {})
    render_next_step_guidance(analysis_bundle.get("quality_summary") or {})
    render_comparison_hint(metrics_result, analysis_bundle)

    render_section_title("当前最值得关注的结论", "先看重点，再决定是否继续查看图表和详细报告。")
    render_priority_summary(metrics_result, rule_analysis)

    if comparison and comparison.get("period_mode") in {"week", "month"}:
        current_summary = comparison.get("current_period") or {}
        previous_summary = comparison.get("previous_period") or {}
        current_label = comparison.get("current_label", "本周期")
        previous_label = comparison.get("previous_label", "上周期")

        card_col1, card_col2, card_col3 = st.columns(3)
        with card_col1:
            render_numeric_conclusion_card(
                "销售额变化",
                format_value(current_summary.get("total_sales"), 2, " 元"),
                format_value(previous_summary.get("total_sales"), 2, " 元"),
                comparison.get("sales_change_rate"),
                current_label,
                previous_label,
            )
        with card_col2:
            render_numeric_conclusion_card(
                "订单数变化",
                format_value(current_summary.get("order_count"), 0, " 单"),
                format_value(previous_summary.get("order_count"), 0, " 单"),
                comparison.get("order_change_rate"),
                current_label,
                previous_label,
            )
        with card_col3:
            render_numeric_conclusion_card(
                "客单价变化",
                format_value(current_summary.get("avg_order_value"), 2, " 元"),
                format_value(previous_summary.get("avg_order_value"), 2, " 元"),
                comparison.get("avg_order_value_change_rate"),
                current_label,
                previous_label,
            )
    else:
        current_label = comparison.get("current_label", "全量数据") if comparison else "全量数据"
        card_col1, card_col2, card_col3 = st.columns(3)
        with card_col1:
            render_numeric_conclusion_card(
                "当前总销售额",
                format_value(metrics_result.get("total_sales"), 2, " 元"),
                None,
                None,
                current_label,
                None,
            )
        with card_col2:
            render_numeric_conclusion_card(
                "当前订单数",
                format_value(metrics_result.get("order_count"), 0, " 单"),
                None,
                None,
                current_label,
                None,
            )
        with card_col3:
            render_numeric_conclusion_card(
                "当前客单价",
                format_value(metrics_result.get("avg_order_value"), 2, " 元"),
                None,
                None,
                current_label,
                None,
            )

    insight_col1, insight_col2 = st.columns(2)
    with insight_col1:
        render_insight_card(
            "主要风险",
            rule_analysis["top_risk"],
            accent="linear-gradient(90deg, #f3a23f 0%, #e2871f 100%)",
            bg="linear-gradient(180deg, #fffaf2 0%, #fff4e6 100%)",
        )
    with insight_col2:
        render_insight_card(
            "建议优先动作",
            rule_analysis["top_action"],
            accent="linear-gradient(90deg, #35b36f 0%, #1f9d59 100%)",
            bg="linear-gradient(180deg, #f2fcf6 0%, #e9f9f0 100%)",
        )

    render_section_title("核心指标", "把最关键的数先抬出来。")
    m1, m2, m3 = st.columns(3)

    sales_delta = None
    order_delta = None
    avg_delta = None
    help_sales = None
    help_orders = None
    help_avg = None

    if comparison and comparison.get("period_mode") in {"week", "month"}:
        sales_delta = format_delta(comparison.get("sales_change_rate"))
        order_delta = format_delta(comparison.get("order_change_rate"))
        avg_delta = format_delta(comparison.get("avg_order_value_change_rate"))
        help_sales = f"对比区间：{comparison.get('previous_label')} → {comparison.get('current_label')}"
        help_orders = help_sales
        help_avg = help_sales

    with m1:
        metric_card("总销售额", format_value(metrics_result.get("total_sales"), 2, " 元"), sales_delta, help_sales)
    with m2:
        metric_card("订单数", format_value(metrics_result.get("order_count"), 0, " 单"), order_delta, help_orders)
    with m3:
        metric_card("客单价", format_value(metrics_result.get("avg_order_value"), 2, " 元"), avg_delta, help_avg)

    render_section_title("老板版摘要", "适合快速汇报，优先给管理者看。")
    with st.container(border=True):
        render_highlighted_report(analysis_bundle["boss_report"])

    render_section_title("图表", "图表默认保留，但放到结论之后。")
    chart_tab1, chart_tab2, chart_tab3 = st.tabs(["销售趋势", "商品排行", "城市排行"])

    with chart_tab1:
        if analysis_bundle["daily_sales_chart"] is not None:
            st.plotly_chart(analysis_bundle["daily_sales_chart"], use_container_width=True)
        else:
            st.info("当前数据无法生成销售趋势图。")

    with chart_tab2:
        if analysis_bundle["top_products_chart"] is not None:
            st.plotly_chart(analysis_bundle["top_products_chart"], use_container_width=True)
        else:
            st.info("当前数据无法生成商品排行图。")

    with chart_tab3:
        if analysis_bundle["top_cities_chart"] is not None:
            st.plotly_chart(analysis_bundle["top_cities_chart"], use_container_width=True)
        else:
            st.info("当前数据无法生成城市排行图。")

    render_section_title("系统分析结论", "按趋势、交易和结构拆开，更接近可直接汇报的业务分析报告。")
    system_rule_cards = [
        ("销售趋势判断", rule_analysis["sales_trend"]),
        ("销售额周期对比", rule_analysis["sales_comparison"]),
        ("订单数周期对比", rule_analysis["order_comparison"]),
        ("客单价周期对比", rule_analysis["avg_order_value_comparison"]),
        ("核心商品判断", rule_analysis["top_product"]),
        ("核心城市判断", rule_analysis["top_city"]),
        ("商品集中度判断", rule_analysis["product_concentration"]),
    ]
    with st.container(border=True):
        col_left, col_right = st.columns(2)
        for idx, (title, content) in enumerate(system_rule_cards):
            with col_left if idx % 2 == 0 else col_right:
                render_professional_rule_card(title, content)

    with st.expander("展开查看运营版详细报告", expanded=False):
        render_highlighted_report(analysis_bundle["operations_report"])

    render_section_title("导出报告")
    st.download_button(
        label="下载 HTML 分析报告",
        data=analysis_bundle["html_report"],
        file_name="ai_data_report.html",
        mime="text/html",
        on_click=lambda: log_event("download_html_report", {"period_mode": period_mode, "source_type": source["source_type"]}),
    )

    with st.expander("留下反馈（可选）", expanded=False):
        feedback_helpful = st.radio(
            "这次分析结果对你有帮助吗？",
            ["很有帮助", "有一点帮助", "一般", "没什么帮助"],
            horizontal=True,
        )
        feedback_favorite = st.selectbox(
            "你最喜欢哪个模块？",
            ["当前最值得关注的结论", "老板版摘要", "系统分析结论", "图表", "运营版报告", "HTML 导出"],
        )
        feedback_unclear = st.selectbox(
            "你觉得最不清楚的是哪一步？",
            ["没有不清楚的地方", "上传文件", "字段识别", "分析口径", "看结果", "导出报告"],
        )
        feedback_preferred_mode = st.radio(
            "你更希望继续使用哪种分析方式？",
            ["整体分析", "按周对比", "按月对比", "都会用"],
            horizontal=True,
        )
        feedback_next_feature = st.text_area(
            "如果继续优化，你最希望增加什么？",
            placeholder="例如：自动识别更准、导出 PDF、异常检测、自动高亮关键数字、更多图表等",
        )
        feedback_continue = st.radio(
            "你愿意继续参加内测吗？",
            ["愿意", "视情况而定", "暂时不想"],
            horizontal=True,
        )
        feedback_contact_optional = st.text_input("可选联系方式", placeholder="微信 / 邮箱")

        if st.button("提交反馈"):
            save_feedback_row(
                {
                    "helpful": feedback_helpful,
                    "favorite_module": feedback_favorite,
                    "unclear_step": feedback_unclear,
                    "preferred_mode": feedback_preferred_mode,
                    "next_feature": feedback_next_feature.strip(),
                    "continue_testing": feedback_continue,
                    "feedback_contact": feedback_contact_optional.strip(),
                }
            )
            log_event(
                "submit_feedback",
                {
                    "helpful": feedback_helpful,
                    "favorite_module": feedback_favorite,
                    "unclear_step": feedback_unclear,
                    "preferred_mode": feedback_preferred_mode,
                    "continue_testing": feedback_continue,
                },
            )
            st.success("感谢反馈，已提交成功。")

    with st.expander("查看数据与分析过程（可选）", expanded=False):
        st.markdown("### 原始数据预览")
        st.dataframe(source["df"].head(10), use_container_width=True)

        st.markdown("### 原始列名")
        st.write(list(source["df"].columns))

        st.markdown("### 当前字段选择结果")
        st.json(mapping_result)

        st.markdown("### 标准化后的数据预览")
        st.dataframe(analysis_bundle["standardized_df"].head(10), use_container_width=True)

        st.markdown("### 标准化后的数据类型")
        st.write(analysis_bundle["standardized_df"].dtypes.astype(str).to_dict())

        st.markdown("### 明细数据表")
        st.markdown("**按天销售趋势数据**")
        if metrics_result["daily_sales"] is not None:
            st.dataframe(metrics_result["daily_sales"], use_container_width=True)
        else:
            st.info("当前数据无法生成按天销售趋势。")

        st.markdown("**Top 商品**")
        if metrics_result["top_products"] is not None:
            st.dataframe(metrics_result["top_products"], use_container_width=True)
        else:
            st.info("当前数据无法生成商品排行。")

        st.markdown("**Top 城市**")
        if metrics_result["top_cities"] is not None:
            st.dataframe(metrics_result["top_cities"], use_container_width=True)
        else:
            st.info("当前数据无法生成城市排行。")


# =========================
# 主页面
# =========================
render_hero_banner()

with st.expander("测试信息与数据说明（可选）", expanded=False):
    info_col1, info_col2 = st.columns(2)
    with info_col1:
        tester_id = st.text_input("测试编号 / 邀请码", value=st.session_state.get("tester_id", DEFAULT_TESTER_ID))
        tester_role = st.selectbox(
            "你的身份",
            ["未填写", "电商卖家", "运营", "数据分析", "朋友试用", "其他"],
            index=0,
        )
    with info_col2:
        tester_contact = st.text_input("联系方式", value=st.session_state.get("tester_contact", ""), placeholder="微信 / 邮箱")
        st.caption("建议上传脱敏数据，不要包含手机号、客户姓名、详细地址等敏感信息。")

    if st.button("保存测试信息"):
        st.session_state["tester_id"] = tester_id.strip() or DEFAULT_TESTER_ID
        st.session_state["tester_role"] = "" if tester_role == "未填写" else tester_role
        st.session_state["tester_contact"] = tester_contact.strip()
        log_event("save_tester_profile")
        st.success("已保存。")

source = None
try:
    source = get_current_source()
except Exception as e:
    log_event("source_load_error", {"error_message": str(e)})
    st.error(humanize_source_error_message(e))

if source is None:
    st.info("先上传一个 Excel / CSV 文件，或者直接点击“ 一键体验示例数据 ”。")
    st.stop()

maybe_log_file_upload(source)

source_df = source["df"]
column_options = get_field_options(source_df.columns)
auto_mapping = get_default_mapping(source_df)

with st.container(border=True):
    render_section_title("分析设置", "默认已经帮你猜了一版字段；识别不准时再手动改。")

    preview_col1, preview_col2 = st.columns([1.1, 1])
    with preview_col1:
        st.write(f"**当前数据源：** {source['name']}")
        st.write(f"**数据规模：** {source_df.shape[0]} 行 × {source_df.shape[1]} 列")
        if source["source_type"] == "demo":
            st.caption("这是系统内置的示例销售数据，用来体验完整流程。")
        else:
            st.caption("已读取你的文件。下面可以直接分析，或者微调字段识别结果。")
    with preview_col2:
        st.dataframe(source_df.head(6), use_container_width=True, height=220)

    period_mode_label = st.radio(
        "分析口径",
        ["整体分析", "按周对比", "按月对比"],
        horizontal=True,
        index=0,
    )
    if period_mode_label == "按周对比":
        period_mode = "week"
    elif period_mode_label == "按月对比":
        period_mode = "month"
    else:
        period_mode = "overall"

    with st.expander("高级设置：字段识别与手动调整", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            date_col = st.selectbox(
                "日期列",
                column_options,
                index=selectbox_index(column_options, auto_mapping.get("date", PLACEHOLDER)),
            )
            sales_col = st.selectbox(
                "销售额列",
                column_options,
                index=selectbox_index(column_options, auto_mapping.get("sales", PLACEHOLDER)),
            )
            product_col = st.selectbox(
                "商品列（可选）",
                column_options,
                index=selectbox_index(column_options, auto_mapping.get("product", PLACEHOLDER)),
            )
        with col2:
            quantity_col = st.selectbox(
                "数量列（可选）",
                column_options,
                index=selectbox_index(column_options, auto_mapping.get("quantity", PLACEHOLDER)),
            )
            city_col = st.selectbox(
                "城市列（可选）",
                column_options,
                index=selectbox_index(column_options, auto_mapping.get("city", PLACEHOLDER)),
            )
            order_id_col = st.selectbox(
                "订单号列（可选）",
                column_options,
                index=selectbox_index(column_options, auto_mapping.get("order_id", PLACEHOLDER)),
            )

    current_mapping = build_mapping_result(
        date_col=date_col,
        sales_col=sales_col,
        product_col=product_col,
        quantity_col=quantity_col,
        city_col=city_col,
        order_id_col=order_id_col,
    )

    field_health = build_field_health_summary(current_mapping)
    render_field_health_summary(field_health, compact=True)

    required_fields_selected = (
        current_mapping["date"] != PLACEHOLDER and current_mapping["sales"] != PLACEHOLDER
    )

    if not required_fields_selected:
        st.warning("当前还缺少【日期列】或【销售额列】。补齐这两个字段后就能生成基础分析；如果自动识别不准，请在上面的高级设置里手动调整。")
    elif field_health.get("impact_messages"):
        st.caption("当前可继续生成基础结果。说明：" + "；".join(field_health.get("impact_messages")[:3]))

    analyze_col1, analyze_col2 = st.columns([1, 2])
    with analyze_col1:
        analyze_clicked = st.button("生成分析结果", type="primary", use_container_width=True)
    with analyze_col2:
        st.caption("按周适合看短期波动；按月适合看阶段趋势；整体分析适合快速看全量概况。")

analysis_signature = build_analysis_signature(source["signature"], period_mode, current_mapping)

if analyze_clicked:
    if not required_fields_selected:
        reset_analysis_only()
        log_event("click_analyze_failed", {"reason": "missing_required_fields", "source_type": source["source_type"]})
    else:
        try:
            with st.spinner("分析中，请稍等...系统正在读取数据、计算指标并生成报告。"):
                analysis_bundle = analyze_dataset(source_df, current_mapping, period_mode)

            st.session_state["analysis_result"] = {
                "bundle": analysis_bundle,
                "source_name": source["name"],
                "source_signature": source["signature"],
                "source_type": source["source_type"],
                "mapping_result": current_mapping,
                "period_mode": period_mode,
            }
            st.session_state["analysis_signature"] = analysis_signature

            log_event(
                "click_analyze",
                {
                    "source_type": source["source_type"],
                    "requested_period_mode": period_mode,
                    "effective_period_mode": analysis_bundle.get("effective_period_mode", period_mode),
                    "selected_date_col": current_mapping["date"],
                    "selected_sales_col": current_mapping["sales"],
                    "selected_product_col": current_mapping["product"],
                    "selected_quantity_col": current_mapping["quantity"],
                    "selected_city_col": current_mapping["city"],
                    "selected_order_id_col": current_mapping["order_id"],
                },
            )

            maybe_log_analysis_success(
                source=source,
                mapping_result=current_mapping,
                period_mode=analysis_bundle.get("effective_period_mode", period_mode),
                analysis_signature=analysis_signature,
                metrics_result=analysis_bundle["metrics_result"],
            )
        except Exception as e:
            reset_analysis_only()
            log_event("analysis_error", {"error_message": str(e)})
            st.error(humanize_analysis_error_message(e))

stored_result = st.session_state.get("analysis_result")
if stored_result:
    stored_signature = st.session_state.get("analysis_signature")
    if stored_signature == analysis_signature and stored_result.get("source_signature") == source["signature"]:
        render_results(
            source=source,
            mapping_result=stored_result["mapping_result"],
            period_mode=stored_result["period_mode"],
            analysis_bundle=stored_result["bundle"],
        )
    else:
        st.info("你已经修改了数据源、字段选择或分析口径。点击“生成分析结果”即可刷新结果。")
