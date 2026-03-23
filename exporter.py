from datetime import datetime
from html import escape
from typing import Any

import pandas as pd


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def _to_float(value: Any):
    if _is_missing(value):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _to_int(value: Any):
    if _is_missing(value):
        return None
    try:
        return int(round(float(value)))
    except Exception:
        return None


def _safe_text(value: Any, default: str = "暂无") -> str:
    if _is_missing(value):
        return default
    text = str(value).strip()
    return escape(text) if text else default


def _format_currency(value: Any, default: str = "无法计算") -> str:
    num = _to_float(value)
    if num is None:
        return default
    return f"{num:,.2f} 元"


def _format_number(value: Any, default: str = "无法计算") -> str:
    num = _to_float(value)
    if num is None:
        return default

    if abs(num - round(num)) < 1e-9:
        return f"{int(round(num)):,}"
    return f"{num:,.2f}"


def _format_order_count(value: Any, default: str = "无法计算") -> str:
    num = _to_int(value)
    if num is None:
        return default
    return f"{num:,} 单"


def _extract_change_info(comparison: dict | None, key: str):
    if not comparison:
        return None

    current_value = comparison.get(f"current_{key}")
    previous_value = comparison.get(f"previous_{key}")
    pct_change = comparison.get(f"{key}_change_pct")

    current_text = _format_metric_value_by_key(key, current_value)
    previous_text = _format_metric_value_by_key(key, previous_value)

    pct_num = _to_float(pct_change)
    if pct_num is None:
        return {
            "status": "暂无对比",
            "delta_text": "暂无对比",
            "current_text": current_text,
            "previous_text": previous_text,
        }

    if pct_num > 0:
        status = "上升"
        delta_text = f"+{pct_num:.1f}%"
    elif pct_num < 0:
        status = "下降"
        delta_text = f"{pct_num:.1f}%"
    else:
        status = "持平"
        delta_text = "0.0%"

    return {
        "status": status,
        "delta_text": delta_text,
        "current_text": current_text,
        "previous_text": previous_text,
    }


def _format_metric_value_by_key(key: str, value: Any) -> str:
    if key == "sales":
        return _format_currency(value)
    if key == "order_count":
        return _format_order_count(value)
    if key == "avg_order_value":
        return _format_currency(value)
    return _format_number(value)


def _status_class(status: str) -> str:
    mapping = {
        "上升": "status-up",
        "下降": "status-down",
        "持平": "status-flat",
        "暂无对比": "status-muted",
        "整体分析": "status-muted",
    }
    return mapping.get(status, "status-muted")


def _render_plot_html(fig, include_plotlyjs):
    if fig is None:
        return '<div class="empty-chart">当前数据无法生成该图表。</div>'

    try:
        return fig.to_html(
            full_html=False,
            include_plotlyjs=include_plotlyjs,
            config={"displayModeBar": False},
        )
    except Exception as e:
        return f'<div class="empty-chart">图表导出失败：{escape(str(e))}</div>'


def _render_multiline_box(text: Any) -> str:
    safe = _safe_text(text, default="暂无内容")
    return safe.replace("\n", "<br>")


def _render_insight_card(title: str, content: Any) -> str:
    return f"""
    <div class="insight-card">
        <div class="insight-title">{escape(title)}</div>
        <div class="insight-content">{_safe_text(content)}</div>
    </div>
    """


def _render_metric_card(title: str, value_text: str, subtitle: str = "") -> str:
    subtitle_html = f'<div class="metric-subtitle">{escape(subtitle)}</div>' if subtitle else ""
    return f"""
    <div class="metric-card">
        <div class="metric-title">{escape(title)}</div>
        <div class="metric-value">{escape(value_text)}</div>
        {subtitle_html}
    </div>
    """


def _render_change_card(title: str, change_info: dict | None, overall_value_text: str = "") -> str:
    if not change_info:
        status = "整体分析"
        value_block = escape(overall_value_text or "暂无数据")
        compare_html = """
        <div class="compare-box">
            <div class="compare-line"><span>当前</span><strong>全量数据</strong></div>
            <div class="compare-line muted-line">当前为整体分析模式，不进行周期对比。</div>
        </div>
        """
    else:
        status = change_info["status"]
        value_block = escape(change_info["delta_text"])
        compare_html = f"""
        <div class="compare-box">
            <div class="compare-line"><span>当前周期</span><strong>{escape(change_info["current_text"])}</strong></div>
            <div class="compare-line"><span>对比周期</span><strong>{escape(change_info["previous_text"])}</strong></div>
        </div>
        """

    return f"""
    <div class="change-card">
        <div class="change-head">
            <div class="change-title">{escape(title)}</div>
            <div class="status-pill {_status_class(status)}">{escape(status)}</div>
        </div>
        <div class="change-value">{value_block}</div>
        {compare_html}
    </div>
    """


def build_html_report(
    metrics_result,
    rule_analysis,
    boss_report,
    operations_report,
    daily_sales_chart,
    top_products_chart,
    top_cities_chart,
):
    metrics_result = metrics_result or {}
    rule_analysis = rule_analysis or {}

    total_sales = metrics_result.get("total_sales")
    order_count = metrics_result.get("order_count")
    avg_order_value = metrics_result.get("avg_order_value")

    total_sales_text = _format_currency(total_sales)
    order_count_text = _format_order_count(order_count)
    avg_order_value_text = _format_currency(avg_order_value)

    generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    comparison = metrics_result.get("period_comparison")
    if comparison is not None:
        period_mode = comparison.get("period_mode")

        if period_mode == "week":
            period_mode_text = "按周对比"
            current_label = comparison.get("current_label", "本周期")
            previous_label = comparison.get("previous_label", "上周期")
            comparison_text = f"本周期 = {current_label}，上周期 = {previous_label}"
        elif period_mode == "month":
            period_mode_text = "按月对比"
            current_label = comparison.get("current_label", "本周期")
            previous_label = comparison.get("previous_label", "上周期")
            comparison_text = f"本周期 = {current_label}，上周期 = {previous_label}"
        elif period_mode == "overall":
            period_mode_text = "整体分析"
            comparison_text = "当前结果基于全量数据生成，不进行周期对比。"
        else:
            period_mode_text = "无法识别"
            comparison_text = "当前数据不足以完成真实周期对比。"
    else:
        period_mode_text = "无法识别"
        comparison_text = "当前数据不足以完成真实周期对比。"

    sales_change = _extract_change_info(comparison, "sales")
    order_change = _extract_change_info(comparison, "order_count")
    aov_change = _extract_change_info(comparison, "avg_order_value")

    daily_sales_chart_html = _render_plot_html(daily_sales_chart, include_plotlyjs=True)
    top_products_chart_html = _render_plot_html(top_products_chart, include_plotlyjs=False)
    top_cities_chart_html = _render_plot_html(top_cities_chart, include_plotlyjs=False)

    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>AI 数据分析报告</title>
    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            font-family: Arial, "Microsoft YaHei", sans-serif;
            margin: 0;
            padding: 36px;
            line-height: 1.7;
            color: #243447;
            background: #f6f8fb;
        }}

        .page {{
            max-width: 1220px;
            margin: 0 auto;
            background: #ffffff;
            border: 1px solid #e6edf5;
            border-radius: 24px;
            padding: 34px;
            box-shadow: 0 18px 48px rgba(17, 24, 39, 0.06);
        }}

        h1 {{
            font-size: 2.2rem;
            font-weight: 800;
            color: #123761;
            margin: 0 0 8px 0;
            letter-spacing: -0.02em;
        }}

        h2 {{
            font-size: 1.4rem;
            font-weight: 800;
            color: #17457d;
            margin: 0 0 12px 0;
        }}

        h3 {{
            font-size: 1.08rem;
            font-weight: 700;
            color: #2f5fa7;
            margin: 0 0 12px 0;
        }}

        .meta {{
            color: #66788a;
            font-size: 0.98rem;
            margin-bottom: 28px;
        }}

        .section {{
            margin-bottom: 34px;
        }}

        .section-title-line {{
            width: 62px;
            height: 4px;
            border-radius: 999px;
            background: linear-gradient(90deg, #7cc0ff 0%, #2f80ed 100%);
            margin-bottom: 16px;
        }}

        .section-desc {{
            color: #7b8b9a;
            font-size: 0.98rem;
            margin-bottom: 16px;
        }}

        .info-box {{
            border-left: 4px solid #4a90e2;
            background: linear-gradient(180deg, #f5f9ff 0%, #eef6ff 100%);
            padding: 16px 18px;
            border-radius: 12px;
            color: #24405f;
        }}

        .info-box p {{
            margin: 6px 0;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 16px;
        }}

        .metric-card {{
            border: 1px solid #dfe9f5;
            border-radius: 16px;
            padding: 18px;
            background: linear-gradient(180deg, #fbfdff 0%, #f4f9ff 100%);
            box-shadow: 0 6px 18px rgba(17, 24, 39, 0.05);
        }}

        .metric-title {{
            font-size: 0.95rem;
            font-weight: 700;
            color: #6a7f95;
            margin-bottom: 10px;
        }}

        .metric-value {{
            font-size: 1.95rem;
            font-weight: 800;
            color: #163a70;
            line-height: 1.2;
        }}

        .metric-subtitle {{
            font-size: 0.94rem;
            color: #7c8b98;
            margin-top: 10px;
        }}

        .summary-box {{
            border: 1px solid #dbe7f3;
            border-radius: 18px;
            padding: 18px 20px;
            background: #f9fcff;
        }}

        .summary-title {{
            font-size: 1rem;
            font-weight: 800;
            color: #1d447a;
            margin-bottom: 10px;
        }}

        .summary-content {{
            font-size: 1.16rem;
            color: #1f3550;
            font-weight: 700;
        }}

        .changes-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 16px;
            margin-top: 18px;
        }}

        .change-card {{
            border-radius: 18px;
            padding: 18px;
            border: 1px solid #deebf5;
            background: #fcfdff;
        }}

        .change-head {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: center;
            margin-bottom: 14px;
        }}

        .change-title {{
            font-size: 0.98rem;
            font-weight: 800;
            color: #5e7286;
        }}

        .status-pill {{
            display: inline-block;
            padding: 8px 14px;
            border-radius: 999px;
            font-size: 0.95rem;
            font-weight: 800;
        }}

        .status-up {{
            color: #13824c;
            background: #eaf8f0;
        }}

        .status-down {{
            color: #d04c40;
            background: #fff1ef;
        }}

        .status-flat {{
            color: #5f7287;
            background: #f3f5f7;
        }}

        .status-muted {{
            color: #6d7d8b;
            background: #f4f6f8;
        }}

        .change-value {{
            font-size: 2.15rem;
            font-weight: 900;
            color: #163a70;
            line-height: 1.2;
            margin-bottom: 14px;
        }}

        .compare-box {{
            border-radius: 14px;
            background: #f5f8fc;
            padding: 14px;
        }}

        .compare-line {{
            display: flex;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 8px;
            color: #4a5f74;
            font-size: 0.98rem;
        }}

        .compare-line:last-child {{
            margin-bottom: 0;
        }}

        .compare-line strong {{
            color: #163a70;
        }}

        .muted-line {{
            display: block;
            color: #758697;
        }}

        .insights-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
        }}

        .insight-card {{
            border: 1px solid #dfe8f2;
            border-radius: 16px;
            background: #fcfdff;
            padding: 18px;
            min-height: 122px;
        }}

        .insight-title {{
            font-size: 0.98rem;
            font-weight: 800;
            color: #2d5da2;
            margin-bottom: 10px;
        }}

        .insight-content {{
            font-size: 1.05rem;
            color: #22384f;
            font-weight: 700;
        }}

        .chart-card {{
            border: 1px solid #e4ebf3;
            border-radius: 18px;
            background: #ffffff;
            padding: 18px;
            box-shadow: 0 8px 20px rgba(17, 24, 39, 0.04);
            margin-bottom: 16px;
        }}

        .empty-chart {{
            border: 1px dashed #d9e3ef;
            border-radius: 14px;
            padding: 20px;
            color: #6f8090;
            background: #f9fbfd;
        }}

        .text-box {{
            border: 1px solid #dde7f2;
            border-radius: 16px;
            padding: 18px 20px;
            background: #fcfdff;
            box-shadow: 0 6px 16px rgba(17, 24, 39, 0.04);
            font-size: 1.03rem;
            line-height: 1.9;
            color: #22384f;
            white-space: normal;
            word-break: break-word;
        }}

        .footer-note {{
            margin-top: 12px;
            font-size: 0.92rem;
            color: #7a8998;
        }}

        @media (max-width: 960px) {{
            body {{
                padding: 18px;
            }}

            .page {{
                padding: 20px;
            }}

            .metrics-grid,
            .changes-grid,
            .insights-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="page">
        <h1>AI 数据分析报告</h1>
        <div class="meta">生成时间：{generated_time}</div>

        <div class="section">
            <h2>一、分析设置</h2>
            <div class="section-title-line"></div>
            <div class="info-box">
                <p><strong>当前分析口径：</strong>{escape(period_mode_text)}</p>
                <p><strong>当前对比区间：</strong>{escape(comparison_text)}</p>
            </div>
        </div>

        <div class="section">
            <h2>二、核心指标</h2>
            <div class="section-title-line"></div>
            <div class="metrics-grid">
                {_render_metric_card("总销售额", total_sales_text)}
                {_render_metric_card("订单数", order_count_text)}
                {_render_metric_card("客单价", avg_order_value_text)}
            </div>
        </div>

        <div class="section">
            <h2>三、当前最值得关注的结论</h2>
            <div class="section-title-line"></div>
            <div class="summary-box">
                <div class="summary-title">核心判断</div>
                <div class="summary-content">{_safe_text(rule_analysis.get("top_change", "暂无"))}</div>
            </div>

            <div class="changes-grid">
                {_render_change_card("销售额变化", sales_change, total_sales_text)}
                {_render_change_card("订单数变化", order_change, order_count_text)}
                {_render_change_card("客单价变化", aov_change, avg_order_value_text)}
            </div>

            <div class="insights-grid" style="margin-top:16px;">
                {_render_insight_card("主要风险", rule_analysis.get("top_risk", "暂无"))}
                {_render_insight_card("建议优先动作", rule_analysis.get("top_action", "暂无"))}
            </div>
        </div>

        <div class="section">
            <h2>四、系统分析结论</h2>
            <div class="section-title-line"></div>
            <div class="insights-grid">
                {_render_insight_card("销售趋势判断", rule_analysis.get("sales_trend", "暂无"))}
                {_render_insight_card("销售额周期对比", rule_analysis.get("sales_comparison", "暂无"))}
                {_render_insight_card("订单数周期对比", rule_analysis.get("order_comparison", "暂无"))}
                {_render_insight_card("客单价周期对比", rule_analysis.get("avg_order_value_comparison", "暂无"))}
                {_render_insight_card("核心商品判断", rule_analysis.get("top_product", "暂无"))}
                {_render_insight_card("核心城市判断", rule_analysis.get("top_city", "暂无"))}
                {_render_insight_card("商品集中度判断", rule_analysis.get("product_concentration", "暂无"))}
            </div>
        </div>

        <div class="section">
            <h2>五、图表</h2>
            <div class="section-title-line"></div>

            <div class="chart-card">
                <h3>销售趋势图</h3>
                {daily_sales_chart_html}
            </div>

            <div class="chart-card">
                <h3>商品销售排行图</h3>
                {top_products_chart_html}
            </div>

            <div class="chart-card">
                <h3>城市销售排行图</h3>
                {top_cities_chart_html}
            </div>
        </div>

        <div class="section">
            <h2>六、老板版摘要</h2>
            <div class="section-title-line"></div>
            <div class="text-box">{_render_multiline_box(boss_report)}</div>
        </div>

        <div class="section">
            <h2>七、运营版报告</h2>
            <div class="section-title-line"></div>
            <div class="text-box">{_render_multiline_box(operations_report)}</div>
            <div class="footer-note">说明：导出报告保留原始文本结构，便于后续复制、转发和二次编辑。</div>
        </div>
    </div>
</body>
</html>
"""
    return html