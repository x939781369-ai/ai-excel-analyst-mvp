import csv
import json
import os
from datetime import datetime

import streamlit as st
from data_loader import load_file
from field_mapper import get_field_options
from standardizer import standardize_dataframe
from metrics import calculate_all_metrics
from rules import generate_rule_based_analysis
from reporter import generate_ai_report
from exporter import build_html_report
from charts import (
    create_daily_sales_chart,
    create_top_products_chart,
    create_top_cities_chart,
)

st.set_page_config(page_title="AI Excel 数据分析助手", layout="wide")


# =========================
# 基础工具函数
# =========================
EVENT_LOG_FILE = "event_log.csv"
FEEDBACK_LOG_FILE = "feedback_log.csv"
SESSION_SUMMARY_FILE = "session_summary.csv"


def append_row_to_csv(file_path: str, row: dict, fieldnames: list[str]):
    file_exists = os.path.exists(file_path)
    with open(file_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def log_event(event_name: str, payload: dict | None = None):
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tester_id": st.session_state.get("tester_id", ""),
        "role": st.session_state.get("tester_role", ""),
        "contact": st.session_state.get("tester_contact", ""),
        "event_name": event_name,
        "payload_json": json.dumps(payload or {}, ensure_ascii=False),
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
        "tester_id": st.session_state.get("tester_id", ""),
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
        "tester_id": st.session_state.get("tester_id", ""),
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
        ],
    )


def reset_test_session():
    keep_keys = {"last_file_signature", "last_logged_file_signature", "last_logged_analysis_signature"}
    keys_to_delete = [k for k in st.session_state.keys() if k not in keep_keys]
    for k in keys_to_delete:
        del st.session_state[k]


def inject_custom_css():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        div.stButton > button {
            background: linear-gradient(90deg, #79beff 0%, #2f80ed 100%);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 0.6rem 1.25rem;
            font-weight: 700;
            font-size: 0.98rem;
            box-shadow: 0 6px 16px rgba(47, 128, 237, 0.22);
            transition: all 0.2s ease-in-out;
        }

        div.stButton > button:hover {
            background: linear-gradient(90deg, #6fb6ff 0%, #236ad1 100%);
            color: white;
            transform: translateY(-1px);
            box-shadow: 0 8px 18px rgba(47, 128, 237, 0.28);
        }

        div.stButton > button:focus:not(:active) {
            color: white;
            border: none;
            box-shadow: 0 0 0 0.2rem rgba(47, 128, 237, 0.18);
        }

        div.stDownloadButton > button {
            background: linear-gradient(90deg, #79beff 0%, #2f80ed 100%);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 0.62rem 1.3rem;
            font-weight: 700;
            font-size: 0.98rem;
            box-shadow: 0 6px 16px rgba(47, 128, 237, 0.22);
            transition: all 0.2s ease-in-out;
        }

        div.stDownloadButton > button:hover {
            background: linear-gradient(90deg, #6fb6ff 0%, #236ad1 100%);
            color: white;
            transform: translateY(-1px);
            box-shadow: 0 8px 18px rgba(47, 128, 237, 0.28);
        }

        div.stDownloadButton > button:focus:not(:active) {
            color: white;
            border: none;
            box-shadow: 0 0 0 0.2rem rgba(47, 128, 237, 0.18);
        }

        div[data-testid="stAlert"] {
            border-radius: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def render_multiline_text(text: str):
    if not text:
        return
    st.markdown(text.replace("\n", "  \n"))


def render_section_title(text: str):
    st.markdown(
        f"""
        <div style="margin-top: 1.25rem; margin-bottom: 0.45rem;">
            <div style="
                font-size: 1.46rem;
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
        unsafe_allow_html=True
    )


def render_subsection_title(text: str):
    st.markdown(
        f"""
        <div style="
            margin-top: 1rem;
            margin-bottom: 0.35rem;
            font-size: 1.08rem;
            font-weight: 700;
            color: #2f5fa7;
            line-height: 1.25;
        ">{text}</div>
        """,
        unsafe_allow_html=True
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
            min-height: 200px;
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
            ">{content}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


inject_custom_css()

# =========================
# 顶部标题
# =========================
st.title("AI Excel 数据分析助手")
st.write("上传销售数据，自动生成整体概览、周/月对比分析、重点结论与汇报报告。")


# =========================
# 内测入口页
# =========================
if not st.session_state.get("entered_test_mode", False):
    with st.container(border=True):
        render_section_title("内测入口")
        st.caption("当前为邀请制内测版，请先填写测试信息，再进入分析页面。")

        st.markdown("### 适用对象")
        st.write("电商卖家、运营人员、需要快速看懂 Excel 数据的人。")

        st.markdown("### 使用建议")
        st.write("- 建议上传脱敏数据。")
        st.write("- 请尽量不要上传手机号、客户姓名、详细地址等敏感信息。")
        st.write("- 当前测试版优先支持销售类 Excel / CSV 数据。")

        st.markdown("### 数据说明")
        st.write("- 数据仅用于本次分析。")
        st.write("- 当前为测试版本，不建议上传敏感业务数据。")

        tester_id = st.text_input("测试编号 / 邀请码（必填）", placeholder="例如：test001")
        tester_role = st.selectbox(
            "你的身份（选填）",
            ["未填写", "电商卖家", "运营", "数据分析", "朋友试用", "其他"]
        )
        tester_contact = st.text_input("联系方式（选填）", placeholder="微信 / 邮箱")

        agreed = st.checkbox("我已知晓当前为内测版，并会优先上传脱敏数据。")

        enter_clicked = st.button("进入分析", type="primary", use_container_width=False)

        if enter_clicked:
            if not tester_id.strip():
                st.warning("请先填写测试编号 / 邀请码。")
            elif not agreed:
                st.warning("请先勾选同意说明后再进入。")
            else:
                st.session_state["entered_test_mode"] = True
                st.session_state["tester_id"] = tester_id.strip()
                st.session_state["tester_role"] = "" if tester_role == "未填写" else tester_role
                st.session_state["tester_contact"] = tester_contact.strip()
                st.session_state["analysis_requested"] = False

                log_event(
                    "enter_test_mode",
                    {
                        "agreed": True,
                    }
                )
                st.rerun()

    st.stop()


# =========================
# 已进入内测后：顶部测试信息
# =========================
top_col1, top_col2 = st.columns([5, 1])
with top_col1:
    st.caption(
        f"当前测试编号：{st.session_state.get('tester_id', '')}"
        f"｜身份：{st.session_state.get('tester_role', '未填写') or '未填写'}"
        f"｜联系方式：{st.session_state.get('tester_contact', '未填写') or '未填写'}"
    )
with top_col2:
    if st.button("退出内测", use_container_width=True):
        log_event("exit_test_mode")
        reset_test_session()
        st.rerun()


# =========================
# 主分析页
# =========================
uploaded_file = st.file_uploader(
    "请上传 Excel 或 CSV 数据文件",
    type=["csv", "xlsx", "xls"]
)

if uploaded_file is not None:
    try:
        df = load_file(uploaded_file)
        column_options = get_field_options(df.columns)

        current_file_signature = f"{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.get("last_file_signature") != current_file_signature:
            st.session_state["last_file_signature"] = current_file_signature
            st.session_state["analysis_requested"] = False

        if st.session_state.get("last_logged_file_signature") != current_file_signature:
            log_event(
                "upload_file",
                {
                    "file_name": uploaded_file.name,
                    "file_size": uploaded_file.size,
                    "rows": df.shape[0],
                    "cols": df.shape[1],
                }
            )
            st.session_state["last_logged_file_signature"] = current_file_signature

        with st.container(border=True):
            render_subsection_title("分析设置")
            st.caption("先选择关键数据列，再选择分析口径，最后点击“生成分析结果”。")

            col1, col2 = st.columns(2)

            with col1:
                date_col = st.selectbox(
                    "日期列（例如：下单日期、支付时间、订单时间）",
                    column_options
                )
                sales_col = st.selectbox(
                    "销售额列（例如：销售额、成交金额、实付金额）",
                    column_options
                )
                product_col = st.selectbox(
                    "商品列（例如：商品名称、商品类别、SKU类别）",
                    column_options,
                    help="请选择最能代表商品本身的列，不要选择单价或金额列。"
                )

            with col2:
                quantity_col = st.selectbox(
                    "数量列（例如：购买数量、件数）",
                    column_options
                )
                city_col = st.selectbox(
                    "城市列（例如：城市、收货城市、地区）",
                    column_options
                )
                order_id_col = st.selectbox(
                    "订单号列（例如：订单编号、订单号）",
                    column_options
                )

            st.markdown("#### 分析口径")
            st.caption("按周适合看短期波动，按月适合看阶段趋势，整体分析适合快速查看全量数据概况。")

            period_mode_label = st.radio(
                "请选择分析口径",
                ["整体分析", "按周对比", "按月对比"],
                horizontal=True,
                index=0,
                label_visibility="collapsed"
            )

            if period_mode_label == "按周对比":
                period_mode = "week"
            elif period_mode_label == "按月对比":
                period_mode = "month"
            else:
                period_mode = "overall"

            analyze_clicked = st.button(
                "生成分析结果",
                type="secondary",
                use_container_width=False
            )

        mapping_result = {
            "date": date_col,
            "sales": sales_col,
            "product": product_col,
            "quantity": quantity_col,
            "city": city_col,
            "order_id": order_id_col
        }

        required_fields_selected = (
            date_col != "-- 请选择 --" and
            sales_col != "-- 请选择 --"
        )

        if analyze_clicked:
            if required_fields_selected:
                st.session_state["analysis_requested"] = True
                log_event(
                    "click_analyze",
                    {
                        "period_mode": period_mode,
                        "selected_date_col": date_col,
                        "selected_sales_col": sales_col,
                        "selected_product_col": product_col,
                        "selected_quantity_col": quantity_col,
                        "selected_city_col": city_col,
                        "selected_order_id_col": order_id_col,
                    }
                )
            else:
                st.session_state["analysis_requested"] = False
                st.warning("请至少选择日期列和销售额列，系统才能生成基础分析结果。")

        if st.session_state.get("analysis_requested", False) and required_fields_selected:
            with st.spinner("分析中，请稍等...系统正在读取数据、计算指标并生成报告。"):
                standardized_df = standardize_dataframe(df, mapping_result)
                metrics_result = calculate_all_metrics(standardized_df, period_mode=period_mode)
                rule_analysis = generate_rule_based_analysis(metrics_result)

                boss_report = generate_ai_report(metrics_result, rule_analysis, report_type="boss")
                operations_report = generate_ai_report(metrics_result, rule_analysis, report_type="operations")

                daily_sales_chart = create_daily_sales_chart(metrics_result["daily_sales"])
                top_products_chart = create_top_products_chart(metrics_result["top_products"])
                top_cities_chart = create_top_cities_chart(metrics_result["top_cities"])

            analysis_signature = f"{current_file_signature}_{period_mode}_{date_col}_{sales_col}_{product_col}_{quantity_col}_{city_col}_{order_id_col}"
        if st.session_state.get("last_logged_analysis_signature") != analysis_signature:
            comparison = metrics_result.get("period_comparison")

            log_event(
                "analysis_success",
                {
                    "file_name": uploaded_file.name,
                    "period_mode": period_mode,
                    "comparison_current_label": comparison.get("current_label") if comparison else "",
                    "comparison_previous_label": comparison.get("previous_label") if comparison else "",
                    "rows": df.shape[0],
                    "cols": df.shape[1],
                    "total_sales": metrics_result.get("total_sales"),
                    "order_count": metrics_result.get("order_count"),
                    "avg_order_value": metrics_result.get("avg_order_value"),
                }
            )

            save_session_summary(
                {
                    "file_name": uploaded_file.name,
                    "period_mode": period_mode,
                    "current_label": comparison.get("current_label") if comparison else "",
                    "previous_label": comparison.get("previous_label") if comparison else "",
                    "rows": df.shape[0],
                    "cols": df.shape[1],
                    "total_sales": metrics_result.get("total_sales"),
                    "order_count": metrics_result.get("order_count"),
                    "avg_order_value": metrics_result.get("avg_order_value"),
                    "selected_date_col": date_col,
                    "selected_sales_col": sales_col,
                    "selected_product_col": product_col,
                    "selected_quantity_col": quantity_col,
                    "selected_city_col": city_col,
                    "selected_order_id_col": order_id_col,
                }
            )

            st.session_state["last_logged_analysis_signature"] = analysis_signature

            st.success("分析完成，结果已生成。")

            comparison = metrics_result.get("period_comparison")
            if comparison is not None:
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
            else:
                st.warning("当前数据不足以完成真实周/月对比，请确认数据是否覆盖连续两个自然周或自然月。")

            render_section_title("当前最值得关注的结论")
            st.caption("先看重点，再决定是否继续查看图表和详细报告。")

            insight_col1, insight_col2, insight_col3 = st.columns(3)

            with insight_col1:
                render_insight_card(
                    "最重要变化",
                    rule_analysis["top_change"],
                    accent="linear-gradient(90deg, #4f8df7 0%, #2f80ed 100%)",
                    bg="linear-gradient(180deg, #f5faff 0%, #eef6ff 100%)"
                )

            with insight_col2:
                render_insight_card(
                    "主要风险",
                    rule_analysis["top_risk"],
                    accent="linear-gradient(90deg, #f3a23f 0%, #e2871f 100%)",
                    bg="linear-gradient(180deg, #fffaf2 0%, #fff4e6 100%)"
                )

            with insight_col3:
                render_insight_card(
                    "建议优先动作",
                    rule_analysis["top_action"],
                    accent="linear-gradient(90deg, #35b36f 0%, #1f9d59 100%)",
                    bg="linear-gradient(180deg, #f2fcf6 0%, #e9f9f0 100%)"
                )

            render_section_title("老板版摘要")
            st.caption("适合快速汇报，建议优先给管理者查看。")
            with st.container(border=True):
                render_multiline_text(boss_report)

            render_subsection_title("核心指标")
            m1, m2, m3 = st.columns(3)

            with m1:
                total_sales = metrics_result["total_sales"]
                st.metric(
                    "总销售额",
                    f"{total_sales:,.2f}" if total_sales is not None else "无法计算"
                )

            with m2:
                order_count = metrics_result["order_count"]
                st.metric(
                    "订单数",
                    f"{order_count:,}" if order_count is not None else "无法计算"
                )

            with m3:
                avg_order_value = metrics_result["avg_order_value"]
                st.metric(
                    "客单价",
                    f"{avg_order_value:,.2f}" if avg_order_value is not None else "无法计算"
                )

            render_subsection_title("系统分析结论")
            with st.container(border=True):
                st.write(f"**销售趋势判断：** {rule_analysis['sales_trend']}")
                st.write(f"**销售额周期对比：** {rule_analysis['sales_comparison']}")
                st.write(f"**订单数周期对比：** {rule_analysis['order_comparison']}")
                st.write(f"**客单价周期对比：** {rule_analysis['avg_order_value_comparison']}")
                st.write(f"**核心商品判断：** {rule_analysis['top_product']}")
                st.write(f"**核心城市判断：** {rule_analysis['top_city']}")
                st.write(f"**商品集中度判断：** {rule_analysis['product_concentration']}")

            render_subsection_title("核心图表")
            chart_tab1, chart_tab2, chart_tab3 = st.tabs(["销售趋势", "商品排行", "城市排行"])

            with chart_tab1:
                if daily_sales_chart is not None:
                    st.plotly_chart(daily_sales_chart, use_container_width=True)
                else:
                    st.info("当前数据无法生成销售趋势图。")

            with chart_tab2:
                if top_products_chart is not None:
                    st.plotly_chart(top_products_chart, use_container_width=True)
                else:
                    st.info("当前数据无法生成商品排行图。")

            with chart_tab3:
                if top_cities_chart is not None:
                    st.plotly_chart(top_cities_chart, use_container_width=True)
                else:
                    st.info("当前数据无法生成城市排行图。")

            render_subsection_title("运营版报告")
            with st.expander("展开查看详细运营报告", expanded=False):
                render_multiline_text(operations_report)

            html_report = build_html_report(
                metrics_result=metrics_result,
                rule_analysis=rule_analysis,
                boss_report=boss_report,
                operations_report=operations_report,
                daily_sales_chart=daily_sales_chart,
                top_products_chart=top_products_chart,
                top_cities_chart=top_cities_chart,
            )

            render_subsection_title("导出完整报告")
            st.download_button(
                label="下载 HTML 分析报告",
                data=html_report,
                file_name="ai_data_report.html",
                mime="text/html",
                on_click=lambda: log_event("download_html_report", {"period_mode": period_mode})
            )

            # =========================
            # 反馈区
            # =========================
            render_section_title("试用反馈")
            st.caption("你的反馈会直接影响下一轮产品优化，填写耗时约 30 秒。")

            with st.container(border=True):
                feedback_helpful = st.radio(
                    "这次分析结果对你有帮助吗？",
                    ["很有帮助", "有一点帮助", "一般", "没什么帮助"],
                    horizontal=True
                )

                feedback_favorite = st.selectbox(
                    "你最喜欢哪个模块？",
                    [
                        "当前最值得关注的结论",
                        "老板版摘要",
                        "系统分析结论",
                        "图表",
                        "运营版报告",
                        "HTML 导出"
                    ]
                )

                feedback_unclear = st.selectbox(
                    "你觉得最不清楚的是哪一步？",
                    [
                        "没有不清楚的地方",
                        "上传文件",
                        "选择字段",
                        "选择分析口径",
                        "看结果",
                        "导出报告"
                    ]
                )

                feedback_preferred_mode = st.radio(
                    "你更希望继续使用哪种分析方式？",
                    ["整体分析", "按周对比", "按月对比", "都会用"],
                    horizontal=True
                )

                feedback_next_feature = st.text_area(
                    "如果继续优化，你最希望增加什么？",
                    placeholder="可以写：自动识别字段、导出 PDF、更多图表、异常检测、更适合老板的汇报页等"
                )

                feedback_continue = st.radio(
                    "你愿意继续参加内测吗？",
                    ["愿意", "视情况而定", "暂时不想"],
                    horizontal=True
                )

                feedback_contact_optional = st.text_input(
                    "如果愿意继续参加内测，可补充联系方式（选填）",
                    placeholder="微信 / 邮箱"
                )

                submit_feedback = st.button("提交反馈", use_container_width=False)

                if submit_feedback:
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
                        }
                    )

                    st.success("感谢反馈，已提交成功。")

            # =========================
            # 过程信息折叠
            # =========================
            with st.expander("查看数据与分析过程（可选）", expanded=False):
                st.markdown("### 原始数据预览")
                st.dataframe(df.head(10), use_container_width=True)

                st.markdown("### 原始列名")
                st.write(list(df.columns))

                st.markdown("### 数据基本信息")
                st.write(f"行数: {df.shape[0]}")
                st.write(f"列数: {df.shape[1]}")

                st.markdown("### 当前字段选择结果")
                st.json(mapping_result)

                st.markdown("### 标准化后的数据预览")
                st.dataframe(standardized_df.head(10), use_container_width=True)

                st.markdown("### 标准化后的列名")
                st.write(list(standardized_df.columns))

                st.markdown("### 标准化后的数据类型")
                st.write(standardized_df.dtypes.astype(str).to_dict())

                st.markdown("### 查看明细数据表")
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

    except Exception as e:
        log_event("analysis_error", {"error_message": str(e)})
        st.error(f"读取文件失败：{e}")
else:
    st.info("请先上传一个 Excel 或 CSV 文件，然后完成分析设置。")