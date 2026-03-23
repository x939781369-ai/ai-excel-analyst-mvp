def analyze_sales_trend(metrics_result):
    comparison = metrics_result.get("period_comparison")

    if comparison is not None:
        sales_change_rate = comparison.get("sales_change_rate")
        current_label = comparison.get("current_label", "本周期")
        previous_label = comparison.get("previous_label", "上周期")
        period_mode = comparison.get("period_mode")

        if period_mode == "week":
            mode_text = "周度"
        elif period_mode == "month":
            mode_text = "月度"
        elif period_mode == "overall":
            mode_text = "整体"
        else:
            mode_text = "周期"

        if period_mode == "overall":
            daily_sales = metrics_result.get("daily_sales")
            if daily_sales is None or len(daily_sales) < 2:
                return "当前为整体分析模式，数据不足，暂时无法判断整体趋势。"

            first_value = daily_sales.iloc[0]["sales"]
            last_value = daily_sales.iloc[-1]["sales"]

            if last_value > first_value:
                return "当前为整体分析模式，从全量时间序列看，销售额整体呈上升趋势。"
            elif last_value < first_value:
                return "当前为整体分析模式，从全量时间序列看，销售额整体呈下降趋势。"
            else:
                return "当前为整体分析模式，从全量时间序列看，销售额整体较为平稳。"

        if sales_change_rate is None:
            return f"当前数据不足，无法完成{mode_text}趋势判断。"

        percentage = abs(sales_change_rate) * 100

        if sales_change_rate > 0:
            return f"从{mode_text}对比看，本周期（{current_label}）较上周期（{previous_label}）销售额上升 {percentage:.1f}%。"
        elif sales_change_rate < 0:
            return f"从{mode_text}对比看，本周期（{current_label}）较上周期（{previous_label}）销售额下降 {percentage:.1f}%。"
        else:
            return f"从{mode_text}对比看，本周期（{current_label}）与上周期（{previous_label}）销售额基本持平。"

    daily_sales = metrics_result.get("daily_sales")

    if daily_sales is None or len(daily_sales) < 2:
        return "数据不足，暂时无法判断销售趋势。"

    first_value = daily_sales.iloc[0]["sales"]
    last_value = daily_sales.iloc[-1]["sales"]

    if last_value > first_value:
        return "从首日到末日看，销售额整体呈上升趋势。"
    elif last_value < first_value:
        return "从首日到末日看，销售额整体呈下降趋势。"
    else:
        return "从首日到末日看，销售额整体较为平稳。"


def analyze_top_product(metrics_result):
    top_products = metrics_result.get("top_products")

    if top_products is None or top_products.empty:
        return "当前数据无法识别核心商品。"

    top_row = top_products.iloc[0]
    product_name = top_row["product"]
    sales_value = top_row["sales"]

    return f"当前销售额最高的商品是「{product_name}」，销售额为 {sales_value:,.2f}。"


def analyze_top_city(metrics_result):
    top_cities = metrics_result.get("top_cities")

    if top_cities is None or top_cities.empty:
        return "当前数据无法识别核心城市。"

    top_row = top_cities.iloc[0]
    city_name = top_row["city"]
    sales_value = top_row["sales"]

    return f"当前销售额最高的城市是「{city_name}」，销售额为 {sales_value:,.2f}。"


def analyze_product_concentration(metrics_result):
    top_products = metrics_result.get("top_products")
    total_sales = metrics_result.get("total_sales")

    if top_products is None or top_products.empty or total_sales in [None, 0]:
        return "当前数据不足，无法判断商品集中度。"

    top_product_sales = top_products.iloc[0]["sales"]
    share = top_product_sales / total_sales

    if share >= 0.4:
        return f"最高销售商品占总销售额的 {share:.1%}，商品集中度较高，需要关注单一商品依赖风险。"
    elif share >= 0.2:
        return f"最高销售商品占总销售额的 {share:.1%}，商品集中度中等。"
    else:
        return f"最高销售商品占总销售额的 {share:.1%}，当前商品结构相对分散。"


def format_change_text(change_rate, metric_name):
    if change_rate is None:
        return f"{metric_name}：当前数据不足，无法完成周期对比。"

    percentage = abs(change_rate) * 100

    if change_rate > 0:
        return f"{metric_name}：本周期较上周期上升 {percentage:.1f}%。"
    elif change_rate < 0:
        return f"{metric_name}：本周期较上周期下降 {percentage:.1f}%。"
    else:
        return f"{metric_name}：本周期与上周期基本持平。"


def analyze_period_comparison(metrics_result):
    comparison = metrics_result.get("period_comparison")

    if comparison is None:
        return {
            "sales_comparison": "销售额：当前数据不足，无法完成周期对比。",
            "order_comparison": "订单数：当前数据不足，无法完成周期对比。",
            "avg_order_value_comparison": "客单价：当前数据不足，无法完成周期对比。",
        }

    if comparison.get("period_mode") == "overall":
        return {
            "sales_comparison": "销售额：当前为整体分析模式，不进行周期对比。",
            "order_comparison": "订单数：当前为整体分析模式，不进行周期对比。",
            "avg_order_value_comparison": "客单价：当前为整体分析模式，不进行周期对比。",
        }

    return {
        "sales_comparison": format_change_text(
            comparison.get("sales_change_rate"), "销售额"
        ),
        "order_comparison": format_change_text(
            comparison.get("order_change_rate"), "订单数"
        ),
        "avg_order_value_comparison": format_change_text(
            comparison.get("avg_order_value_change_rate"), "客单价"
        ),
    }


def get_priority_insights(metrics_result):
    comparison = metrics_result.get("period_comparison")

    if comparison is None:
        return {
            "top_change": "当前数据不足，暂时无法识别最重要变化。",
            "top_risk": "当前数据不足，暂时无法识别主要风险。",
            "top_action": "建议先补充完整时间数据后再进行进一步分析。"
        }

    concentration_text = analyze_product_concentration(metrics_result)

    if comparison.get("period_mode") == "overall":
        top_change = "当前为整体分析模式，系统已基于全量数据生成整体概览，不提供周期变化判断。"

        risk_parts = []
        if "集中度较高" in concentration_text:
            risk_parts.append("商品销售过于集中，存在对单一商品依赖过强的风险")
        elif "集中度中等" in concentration_text:
            risk_parts.append("核心商品占比较高，需要持续关注商品结构是否进一步集中")

        if risk_parts:
            top_risk = "；".join(risk_parts) + "。"
        else:
            top_risk = "当前未识别出特别突出的结构性风险，但仍建议持续跟踪核心指标表现。"

        top_action = "建议先查看核心商品、核心城市与整体趋势，再决定是否切换到按周或按月模式进行进一步分析。"

        return {
            "top_change": top_change,
            "top_risk": top_risk,
            "top_action": top_action,
        }

    sales_change = comparison.get("sales_change_rate")
    order_change = comparison.get("order_change_rate")
    avg_order_value_change = comparison.get("avg_order_value_change_rate")

    if sales_change is not None and sales_change > 0:
        if order_change is not None and order_change > 0 and avg_order_value_change is not None and avg_order_value_change < 0:
            top_change = "当前最重要的变化是：销售额增长主要由订单数增长带动，但客单价略有下降。"
        elif order_change is not None and order_change > 0 and avg_order_value_change is not None and avg_order_value_change > 0:
            top_change = "当前最重要的变化是：销售额增长同时受到订单数增长和客单价提升的共同带动。"
        elif order_change is not None and order_change <= 0 and avg_order_value_change is not None and avg_order_value_change > 0:
            top_change = "当前最重要的变化是：销售额增长主要由客单价提升带动，而不是订单数增加。"
        else:
            top_change = "当前最重要的变化是：销售额较上周期有所增长。"
    elif sales_change is not None and sales_change < 0:
        if order_change is not None and order_change < 0 and avg_order_value_change is not None and avg_order_value_change >= 0:
            top_change = "当前最重要的变化是：销售额下降主要由订单数减少导致，客单价未明显改善。"
        elif order_change is not None and order_change < 0 and avg_order_value_change is not None and avg_order_value_change < 0:
            top_change = "当前最重要的变化是：销售额下降同时受到订单数减少和客单价下降的双重影响。"
        else:
            top_change = "当前最重要的变化是：销售额较上周期有所下降。"
    else:
        top_change = "当前最重要的变化是：销售额整体较为平稳。"

    risk_parts = []

    if avg_order_value_change is not None and avg_order_value_change < 0:
        risk_parts.append("客单价出现下降，需要关注增长质量是否走弱")

    if "集中度较高" in concentration_text:
        risk_parts.append("商品销售过于集中，存在对单一商品依赖过强的风险")
    elif "集中度中等" in concentration_text:
        risk_parts.append("核心商品占比较高，需要持续关注商品结构是否进一步集中")

    if risk_parts:
        top_risk = "；".join(risk_parts) + "。"
    else:
        top_risk = "当前未识别出特别突出的结构性风险，但仍建议持续跟踪关键指标变化。"

    action_parts = []

    if avg_order_value_change is not None and avg_order_value_change < 0:
        action_parts.append("优先检查低价订单占比是否上升")

    if "集中度较高" in concentration_text or "集中度中等" in concentration_text:
        action_parts.append("持续跟踪核心商品销售占比变化")

    if order_change is not None and order_change > 0 and avg_order_value_change is not None and avg_order_value_change < 0:
        action_parts.append("关注订单增长是否建立在价格下探基础上")

    if not action_parts:
        action_parts.append("继续观察核心指标在下一个周期的变化情况")

    top_action = "；".join(action_parts) + "。"

    return {
        "top_change": top_change,
        "top_risk": top_risk,
        "top_action": top_action,
    }


def generate_rule_based_analysis(metrics_result):
    comparison_result = analyze_period_comparison(metrics_result)
    priority_insights = get_priority_insights(metrics_result)

    return {
        "sales_trend": analyze_sales_trend(metrics_result),
        "top_product": analyze_top_product(metrics_result),
        "top_city": analyze_top_city(metrics_result),
        "product_concentration": analyze_product_concentration(metrics_result),
        "sales_comparison": comparison_result["sales_comparison"],
        "order_comparison": comparison_result["order_comparison"],
        "avg_order_value_comparison": comparison_result["avg_order_value_comparison"],
        "top_change": priority_insights["top_change"],
        "top_risk": priority_insights["top_risk"],
        "top_action": priority_insights["top_action"],
    }