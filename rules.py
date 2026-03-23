from __future__ import annotations

from typing import Any

import pandas as pd


def _to_float(value: Any):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    try:
        return float(value)
    except Exception:
        return None


def _format_currency(value: Any, default: str = "无法计算") -> str:
    number = _to_float(value)
    if number is None:
        return default
    return f"{number:,.2f}"


def _format_pct_from_rate(change_rate: Any, default: str = "无法计算") -> str:
    number = _to_float(change_rate)
    if number is None:
        return default
    return f"{abs(number) * 100:.1f}%"


def _get_comparison(metrics_result: dict) -> dict | None:
    comparison = metrics_result.get("period_comparison")
    return comparison if isinstance(comparison, dict) else None


def _get_period_context(metrics_result: dict) -> dict:
    comparison = _get_comparison(metrics_result)
    if comparison is None:
        return {
            "period_mode": None,
            "mode_text": "周期",
            "current_label": "本周期",
            "previous_label": "上周期",
        }

    period_mode = comparison.get("period_mode")
    mode_text = {
        "week": "周度",
        "month": "月度",
        "overall": "整体",
    }.get(period_mode, "周期")

    return {
        "period_mode": period_mode,
        "mode_text": mode_text,
        "current_label": comparison.get("current_label") or "本周期",
        "previous_label": comparison.get("previous_label") or "上周期",
    }


def _describe_change(metric_name: str, change_rate: Any, current_label: str, previous_label: str) -> str:
    rate = _to_float(change_rate)
    if rate is None:
        return f"{metric_name}：当前数据不足，无法完成周期对比。"

    pct_text = _format_pct_from_rate(rate)
    if abs(rate) < 0.03:
        return f"{metric_name}：本周期（{current_label}）与上周期（{previous_label}）基本持平。"
    if rate > 0:
        return f"{metric_name}：本周期（{current_label}）较上周期（{previous_label}）上升 {pct_text}。"
    return f"{metric_name}：本周期（{current_label}）较上周期（{previous_label}）下降 {pct_text}。"


def _get_overall_trend_from_daily_sales(metrics_result: dict) -> tuple[str, float | None]:
    daily_sales = metrics_result.get("daily_sales")
    if daily_sales is None or len(daily_sales) < 4 or "sales" not in daily_sales.columns:
        return "当前为整体分析模式，数据不足，暂时无法判断整体趋势。", None

    working_df = daily_sales.copy().sort_values("date").reset_index(drop=True)
    sales_series = pd.to_numeric(working_df["sales"], errors="coerce").dropna()
    if len(sales_series) < 4:
        return "当前为整体分析模式，数据不足，暂时无法判断整体趋势。", None

    window = max(2, min(7, len(sales_series) // 3 if len(sales_series) >= 6 else 2))
    first_avg = float(sales_series.iloc[:window].mean())
    last_avg = float(sales_series.iloc[-window:].mean())

    if first_avg == 0:
        return "当前为整体分析模式，起始阶段销售额过低，暂时无法稳定判断整体趋势。", None

    pct = (last_avg - first_avg) / first_avg
    date_min = metrics_result.get("date_min")
    date_max = metrics_result.get("date_max")
    date_text = f"（{date_min} 至 {date_max}）" if date_min and date_max else ""

    if pct >= 0.05:
        return f"当前为整体分析模式，结合首尾阶段的日均销售额{date_text}，销售额整体呈上升趋势，提升约 {_format_pct_from_rate(pct)}。", pct
    if pct <= -0.05:
        return f"当前为整体分析模式，结合首尾阶段的日均销售额{date_text}，销售额整体呈下降趋势，降幅约 {_format_pct_from_rate(pct)}。", pct
    return f"当前为整体分析模式，结合首尾阶段的日均销售额{date_text}，销售额整体较为平稳。", pct


def analyze_sales_trend(metrics_result: dict) -> str:
    comparison = _get_comparison(metrics_result)
    period_context = _get_period_context(metrics_result)

    if comparison is not None and period_context["period_mode"] in {"week", "month"}:
        sales_change_rate = comparison.get("sales_change_rate")
        order_change_rate = comparison.get("order_change_rate")
        aov_change_rate = comparison.get("avg_order_value_change_rate")

        rate = _to_float(sales_change_rate)
        if rate is None:
            return f"当前数据不足，无法完成{period_context['mode_text']}趋势判断。"

        prefix = _describe_change(
            "销售额",
            rate,
            period_context["current_label"],
            period_context["previous_label"],
        )

        order_rate = _to_float(order_change_rate)
        aov_rate = _to_float(aov_change_rate)

        if abs(rate) < 0.03:
            if order_rate is not None and aov_rate is not None:
                if order_rate > 0.03 and aov_rate < -0.03:
                    return prefix + " 订单数增长与客单价回落基本相互抵消。"
                if order_rate < -0.03 and aov_rate > 0.03:
                    return prefix + " 订单数回落与客单价提升基本相互抵消。"
            return prefix

        if rate > 0:
            if order_rate is not None and aov_rate is not None:
                if order_rate >= 0.03 and aov_rate >= 0.03:
                    return prefix + " 增长同时受到订单数提升和客单价改善的共同带动。"
                if order_rate >= 0.03 and aov_rate < 0.03:
                    return prefix + " 增长主要来自订单数增加。"
                if order_rate < 0.03 and aov_rate >= 0.03:
                    return prefix + " 增长主要来自客单价提升。"
            return prefix

        if order_rate is not None and aov_rate is not None:
            if order_rate <= -0.03 and aov_rate <= -0.03:
                return prefix + " 下滑同时受到订单数减少和客单价回落的双重影响。"
            if order_rate <= -0.03 and aov_rate > -0.03:
                return prefix + " 下滑主要由订单数减少驱动。"
            if order_rate > -0.03 and aov_rate <= -0.03:
                return prefix + " 下滑主要由客单价回落驱动。"
        return prefix

    return _get_overall_trend_from_daily_sales(metrics_result)[0]


def analyze_top_product(metrics_result: dict) -> str:
    top_products = metrics_result.get("top_products")
    total_sales = _to_float(metrics_result.get("total_sales"))

    if top_products is None or top_products.empty:
        return "当前数据无法识别核心商品。"

    top_row = top_products.iloc[0]
    product_name = str(top_row.get("product", "未知商品"))
    sales_value = _to_float(top_row.get("sales"))

    if sales_value is None:
        return f"当前销售额最高的商品是「{product_name}」，但销售额暂时无法计算。"

    if total_sales and total_sales > 0:
        share = sales_value / total_sales
        return f"当前销售额最高的商品是「{product_name}」，销售额为 {_format_currency(sales_value)}，占总销售额的 {share:.1%}。"

    return f"当前销售额最高的商品是「{product_name}」，销售额为 {_format_currency(sales_value)}。"


def analyze_top_city(metrics_result: dict) -> str:
    top_cities = metrics_result.get("top_cities")
    total_sales = _to_float(metrics_result.get("total_sales"))

    if top_cities is None or top_cities.empty:
        return "当前数据无法识别核心城市。"

    top_row = top_cities.iloc[0]
    city_name = str(top_row.get("city", "未知城市"))
    sales_value = _to_float(top_row.get("sales"))

    if sales_value is None:
        return f"当前销售额最高的城市是「{city_name}」，但销售额暂时无法计算。"

    if total_sales and total_sales > 0:
        share = sales_value / total_sales
        return f"当前销售额最高的城市是「{city_name}」，销售额为 {_format_currency(sales_value)}，占总销售额的 {share:.1%}。"

    return f"当前销售额最高的城市是「{city_name}」，销售额为 {_format_currency(sales_value)}。"


def analyze_product_concentration(metrics_result: dict) -> str:
    top_products = metrics_result.get("top_products")
    total_sales = _to_float(metrics_result.get("total_sales"))

    if top_products is None or top_products.empty or total_sales in [None, 0]:
        return "当前数据不足，无法判断商品集中度。"

    top1_sales = _to_float(top_products.iloc[0].get("sales"))
    if top1_sales is None:
        return "当前数据不足，无法判断商品集中度。"

    top1_share = top1_sales / total_sales
    top3_share = None
    if "sales" in top_products.columns:
        top3_total = pd.to_numeric(top_products["sales"], errors="coerce").head(3).sum()
        if pd.notna(top3_total):
            top3_share = float(top3_total) / total_sales if total_sales else None

    if top1_share >= 0.45:
        if top3_share is not None:
            return f"最高销售商品占总销售额的 {top1_share:.1%}，Top 3 商品合计占比 {top3_share:.1%}，商品集中度较高，需要关注对头部商品的依赖风险。"
        return f"最高销售商品占总销售额的 {top1_share:.1%}，商品集中度较高，需要关注对头部商品的依赖风险。"
    if top1_share >= 0.25:
        if top3_share is not None:
            return f"最高销售商品占总销售额的 {top1_share:.1%}，Top 3 商品合计占比 {top3_share:.1%}，商品集中度中等。"
        return f"最高销售商品占总销售额的 {top1_share:.1%}，商品集中度中等。"
    if top3_share is not None:
        return f"最高销售商品占总销售额的 {top1_share:.1%}，Top 3 商品合计占比 {top3_share:.1%}，当前商品结构相对分散。"
    return f"最高销售商品占总销售额的 {top1_share:.1%}，当前商品结构相对分散。"


def analyze_period_comparison(metrics_result: dict) -> dict:
    comparison = _get_comparison(metrics_result)
    period_context = _get_period_context(metrics_result)

    if comparison is None:
        return {
            "sales_comparison": "销售额：当前数据不足，无法完成周期对比。",
            "order_comparison": "订单数：当前数据不足，无法完成周期对比。",
            "avg_order_value_comparison": "客单价：当前数据不足，无法完成周期对比。",
        }

    if period_context["period_mode"] == "overall":
        return {
            "sales_comparison": f"销售额：当前为整体分析模式，总销售额为 {_format_currency(metrics_result.get('total_sales'))}。",
            "order_comparison": f"订单数：当前为整体分析模式，总订单数为 {int(_to_float(metrics_result.get('order_count')) or 0):,} 单。",
            "avg_order_value_comparison": f"客单价：当前为整体分析模式，客单价为 {_format_currency(metrics_result.get('avg_order_value'))}。",
        }

    return {
        "sales_comparison": _describe_change(
            "销售额",
            comparison.get("sales_change_rate"),
            period_context["current_label"],
            period_context["previous_label"],
        ),
        "order_comparison": _describe_change(
            "订单数",
            comparison.get("order_change_rate"),
            period_context["current_label"],
            period_context["previous_label"],
        ),
        "avg_order_value_comparison": _describe_change(
            "客单价",
            comparison.get("avg_order_value_change_rate"),
            period_context["current_label"],
            period_context["previous_label"],
        ),
    }


def _get_concentration_level(concentration_text: str) -> str:
    if "集中度较高" in concentration_text:
        return "high"
    if "集中度中等" in concentration_text:
        return "medium"
    if "相对分散" in concentration_text:
        return "low"
    return "unknown"


def get_priority_insights(metrics_result: dict) -> dict:
    comparison = _get_comparison(metrics_result)
    concentration_text = analyze_product_concentration(metrics_result)
    concentration_level = _get_concentration_level(concentration_text)

    if comparison is None:
        return {
            "top_change": "当前数据不足，暂时无法识别最重要变化。",
            "top_risk": "当前数据不足，暂时无法识别主要风险。",
            "top_action": "建议先补充完整且连续的时间数据后，再进行按周或按月分析。",
        }

    if comparison.get("period_mode") == "overall":
        trend_text, trend_pct = _get_overall_trend_from_daily_sales(metrics_result)
        total_sales_text = _format_currency(metrics_result.get("total_sales"))
        order_count = int(_to_float(metrics_result.get("order_count")) or 0)
        aov_text = _format_currency(metrics_result.get("avg_order_value"))

        if trend_pct is None:
            top_change = f"当前为整体分析模式，系统已基于全量数据生成整体概览：总销售额 {total_sales_text}，订单数 {order_count:,} 单，客单价 {aov_text}。"
        else:
            direction = "提升" if trend_pct > 0.05 else "回落" if trend_pct < -0.05 else "基本稳定"
            top_change = f"当前为整体分析模式，核心变化是：总销售额 {total_sales_text}，订单数 {order_count:,} 单，客单价 {aov_text}，整体趋势{direction}。"

        risk_parts = []
        if concentration_level == "high":
            risk_parts.append("商品销售过于集中，存在对头部商品依赖过强的风险")
        elif concentration_level == "medium":
            risk_parts.append("头部商品占比较高，后续需要持续关注结构是否进一步集中")

        if trend_pct is not None and trend_pct <= -0.05:
            risk_parts.append("整体销售趋势偏弱，需要尽快确认是流量走弱还是转化效率下降")

        top_risk = "；".join(risk_parts) + "。" if risk_parts else "当前未识别出特别突出的结构性风险，但仍建议持续跟踪整体趋势与头部商品表现。"

        action_parts = ["优先查看核心商品与核心城市的贡献情况"]
        if concentration_level in {"high", "medium"}:
            action_parts.append("继续跟踪头部商品占比，避免销售过度集中")
        if trend_pct is not None:
            if trend_pct <= -0.05:
                action_parts.append("建议切换到按周或按月模式，定位趋势转弱发生在哪个周期")
            elif trend_pct >= 0.05:
                action_parts.append("建议拆解增长来源，确认是订单增长还是客单价提升更可持续")

        return {
            "top_change": top_change,
            "top_risk": top_risk,
            "top_action": "；".join(action_parts) + "。",
        }

    sales_change = _to_float(comparison.get("sales_change_rate"))
    order_change = _to_float(comparison.get("order_change_rate"))
    aov_change = _to_float(comparison.get("avg_order_value_change_rate"))

    if sales_change is None:
        top_change = "当前数据不足，暂时无法识别最重要变化。"
    elif sales_change >= 0.10:
        if (order_change or 0) >= 0.03 and (aov_change or 0) >= 0.03:
            top_change = "当前最重要的变化是：销售额明显增长，且增长同时来自订单数增加和客单价提升。"
        elif (order_change or 0) >= 0.03:
            top_change = "当前最重要的变化是：销售额明显增长，主要由订单数增加带动。"
        elif (aov_change or 0) >= 0.03:
            top_change = "当前最重要的变化是：销售额明显增长，主要由客单价提升带动。"
        else:
            top_change = "当前最重要的变化是：销售额较上周期明显增长。"
    elif sales_change <= -0.10:
        if (order_change or 0) <= -0.03 and (aov_change or 0) <= -0.03:
            top_change = "当前最重要的变化是：销售额明显下滑，同时受到订单数减少和客单价回落的双重影响。"
        elif (order_change or 0) <= -0.03:
            top_change = "当前最重要的变化是：销售额明显下滑，主要由订单数减少驱动。"
        elif (aov_change or 0) <= -0.03:
            top_change = "当前最重要的变化是：销售额明显下滑，主要由客单价回落驱动。"
        else:
            top_change = "当前最重要的变化是：销售额较上周期明显下滑。"
    else:
        if (order_change or 0) >= 0.03 and (aov_change or 0) <= -0.03:
            top_change = "当前最重要的变化是：销售额整体接近平稳，但订单数增长与客单价下降相互抵消。"
        elif (order_change or 0) <= -0.03 and (aov_change or 0) >= 0.03:
            top_change = "当前最重要的变化是：销售额整体接近平稳，但订单数回落与客单价提升相互抵消。"
        else:
            top_change = "当前最重要的变化是：销售额整体较为平稳。"

    risk_parts = []
    if sales_change is not None and sales_change <= -0.10:
        risk_parts.append("销售额已明显走弱，需要确认问题主要出在流量、转化还是客单价")
    if aov_change is not None and aov_change <= -0.05:
        risk_parts.append("客单价出现明显下降，需要关注低价订单占比是否上升")
    if order_change is not None and order_change <= -0.08:
        risk_parts.append("订单数明显回落，需要尽快检查流量获取和转化效率")
    if concentration_level == "high":
        risk_parts.append("商品销售过于集中，存在对头部商品依赖过强的风险")
    elif concentration_level == "medium":
        risk_parts.append("头部商品占比较高，需要持续关注商品结构是否进一步集中")

    if risk_parts:
        top_risk = "；".join(risk_parts) + "。"
    else:
        top_risk = "当前未识别出特别突出的结构性风险，但仍建议持续跟踪关键指标变化。"

    action_parts = []
    if sales_change is not None and sales_change <= -0.10:
        action_parts.append("优先拆分检查订单数和客单价，先确认下滑主因")
    if order_change is not None and order_change <= -0.08:
        action_parts.append("重点检查流量、转化链路和异常渠道波动")
    if aov_change is not None and aov_change <= -0.05:
        action_parts.append("检查促销力度、低价订单占比和商品结构变化")
    if concentration_level in {"high", "medium"}:
        action_parts.append("持续跟踪头部商品销售占比，降低单一商品依赖")
    if sales_change is not None and sales_change >= 0.10 and (aov_change or 0) < 0.03 and (order_change or 0) >= 0.03:
        action_parts.append("验证增长是否主要依赖冲量订单，避免增长质量走弱")
    if sales_change is not None and sales_change >= 0.10 and (aov_change or 0) >= 0.03:
        action_parts.append("复盘高价值订单来源，优先放大可持续增长动作")

    if not action_parts:
        action_parts.append("继续观察核心指标在下一个周期的变化情况")

    return {
        "top_change": top_change,
        "top_risk": top_risk,
        "top_action": "；".join(action_parts) + "。",
    }


def generate_rule_based_analysis(metrics_result: dict) -> dict:
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
