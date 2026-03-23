from datetime import datetime


def build_html_report(
    metrics_result,
    rule_analysis,
    boss_report,
    operations_report,
    daily_sales_chart,
    top_products_chart,
    top_cities_chart,
):
    total_sales = metrics_result.get("total_sales")
    order_count = metrics_result.get("order_count")
    avg_order_value = metrics_result.get("avg_order_value")

    total_sales_text = f"{total_sales:,.2f}" if total_sales is not None else "无法计算"
    order_count_text = f"{order_count:,}" if order_count is not None else "无法计算"
    avg_order_value_text = f"{avg_order_value:,.2f}" if avg_order_value is not None else "无法计算"

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
            comparison_text = "当前数据不足以完成真实周期对比"
    else:
        period_mode_text = "无法识别"
        comparison_text = "当前数据不足以完成真实周期对比"

    daily_sales_chart_html = (
        daily_sales_chart.to_html(full_html=False, include_plotlyjs="cdn")
        if daily_sales_chart is not None
        else "<p>当前数据无法生成销售趋势图。</p>"
    )

    top_products_chart_html = (
        top_products_chart.to_html(full_html=False, include_plotlyjs=False)
        if top_products_chart is not None
        else "<p>当前数据无法生成商品排行图。</p>"
    )

    top_cities_chart_html = (
        top_cities_chart.to_html(full_html=False, include_plotlyjs=False)
        if top_cities_chart is not None
        else "<p>当前数据无法生成城市排行图。</p>"
    )

    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>AI 数据分析报告</title>
    <style>
        body {{
            font-family: Arial, "Microsoft YaHei", sans-serif;
            margin: 40px;
            line-height: 1.8;
            color: #243447;
            background: #ffffff;
        }}

        h1 {{
            font-size: 2.15rem;
            font-weight: 800;
            color: #123761;
            margin-bottom: 8px;
            letter-spacing: -0.02em;
        }}

        h2 {{
            font-size: 1.45rem;
            font-weight: 800;
            color: #17457d;
            margin-top: 0;
            margin-bottom: 14px;
            letter-spacing: -0.01em;
        }}

        h3 {{
            font-size: 1.08rem;
            font-weight: 700;
            color: #2f5fa7;
            margin-top: 24px;
            margin-bottom: 10px;
        }}

        .meta {{
            color: #5f7288;
            font-size: 0.98rem;
            margin-bottom: 24px;
        }}

        .section {{
            margin-bottom: 38px;
        }}

        .section-title-line {{
            width: 60px;
            height: 4px;
            border-radius: 999px;
            background: linear-gradient(90deg, #7cc0ff 0%, #2f80ed 100%);
            margin-top: -4px;
            margin-bottom: 16px;
        }}

        .metrics {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }}

        .metric-card {{
            border: 1px solid #dfe9f5;
            border-radius: 14px;
            padding: 18px;
            min-width: 210px;
            background: linear-gradient(180deg, #fbfdff 0%, #f4f9ff 100%);
            box-shadow: 0 6px 18px rgba(17, 24, 39, 0.05);
        }}

        .metric-title {{
            font-size: 0.95rem;
            font-weight: 600;
            color: #6a7f95;
            margin-bottom: 10px;
        }}

        .metric-value {{
            font-size: 1.95rem;
            font-weight: 800;
            color: #163a70;
            line-height: 1.2;
        }}

        .box {{
            border: 1px solid #dde7f2;
            border-radius: 14px;
            padding: 18px 20px;
            background: #fcfdff;
            box-shadow: 0 6px 16px rgba(17, 24, 39, 0.04);
            white-space: pre-wrap;
            font-size: 1.05rem;
            line-height: 1.9;
            color: #22384f;
        }}

        .info-box {{
            border-left: 4px solid #4a90e2;
            background: linear-gradient(180deg, #f5f9ff 0%, #eef6ff 100%);
            padding: 16px 18px;
            margin-top: 10px;
            border-radius: 10px;
            font-size: 1.02rem;
            color: #24405f;
        }}

        ul {{
            padding-left: 22px;
            margin-top: 0;
        }}

        li {{
            margin-bottom: 10px;
            font-size: 1.03rem;
            color: #243447;
        }}

        strong {{
            color: #163a70;
        }}

        p {{
            font-size: 1.02rem;
            color: #243447;
        }}
    </style>
</head>
<body>
    <h1>AI 数据分析报告</h1>
    <div class="meta">生成时间：{generated_time}</div>

    <div class="section">
        <h2>一、分析设置</h2>
        <div class="section-title-line"></div>
        <div class="info-box">
            <p><strong>当前分析口径：</strong>{period_mode_text}</p>
            <p><strong>当前对比区间：</strong>{comparison_text}</p>
        </div>
    </div>

    <div class="section">
        <h2>二、核心指标</h2>
        <div class="section-title-line"></div>
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-title">总销售额</div>
                <div class="metric-value">{total_sales_text}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">订单数</div>
                <div class="metric-value">{order_count_text}</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">客单价</div>
                <div class="metric-value">{avg_order_value_text}</div>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>三、图表</h2>
        <div class="section-title-line"></div>
        <h3>销售趋势图</h3>
        {daily_sales_chart_html}

        <h3>商品销售排行图</h3>
        {top_products_chart_html}

        <h3>城市销售排行图</h3>
        {top_cities_chart_html}
    </div>

    <div class="section">
        <h2>四、系统分析结论</h2>
        <div class="section-title-line"></div>
        <ul>
            <li><strong>销售趋势判断：</strong>{rule_analysis.get("sales_trend", "暂无")}</li>
            <li><strong>销售额周期对比：</strong>{rule_analysis.get("sales_comparison", "暂无")}</li>
            <li><strong>订单数周期对比：</strong>{rule_analysis.get("order_comparison", "暂无")}</li>
            <li><strong>客单价周期对比：</strong>{rule_analysis.get("avg_order_value_comparison", "暂无")}</li>
            <li><strong>核心商品判断：</strong>{rule_analysis.get("top_product", "暂无")}</li>
            <li><strong>核心城市判断：</strong>{rule_analysis.get("top_city", "暂无")}</li>
            <li><strong>商品集中度判断：</strong>{rule_analysis.get("product_concentration", "暂无")}</li>
        </ul>
    </div>

    <div class="section">
        <h2>五、当前最值得关注的结论</h2>
        <div class="section-title-line"></div>
        <ul>
            <li><strong>最重要变化：</strong>{rule_analysis.get("top_change", "暂无")}</li>
            <li><strong>主要风险：</strong>{rule_analysis.get("top_risk", "暂无")}</li>
            <li><strong>建议优先动作：</strong>{rule_analysis.get("top_action", "暂无")}</li>
        </ul>
    </div>

    <div class="section">
        <h2>六、老板版摘要</h2>
        <div class="section-title-line"></div>
        <div class="box">{boss_report}</div>
    </div>

    <div class="section">
        <h2>七、运营版报告</h2>
        <div class="section-title-line"></div>
        <div class="box">{operations_report}</div>
    </div>
</body>
</html>
"""
    return html