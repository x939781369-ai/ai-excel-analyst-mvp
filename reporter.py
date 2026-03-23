import os
from dotenv import load_dotenv
from openai import OpenAI


def get_dashscope_api_key():
    """
    优先顺序：
    1. 本地 .env
    2. Streamlit secrets
    """
    load_dotenv()
    api_key = os.getenv("DASHSCOPE_API_KEY")

    if api_key:
        return api_key

    try:
        import streamlit as st
        if "DASHSCOPE_API_KEY" in st.secrets:
            return st.secrets["DASHSCOPE_API_KEY"]
    except Exception:
        pass

    return None


def generate_text_report(metrics_result, rule_analysis):
    total_sales = metrics_result.get("total_sales")
    order_count = metrics_result.get("order_count")
    avg_order_value = metrics_result.get("avg_order_value")

    total_sales_text = f"{total_sales:,.2f}" if total_sales is not None else "无法计算"
    order_count_text = f"{order_count:,}" if order_count is not None else "无法计算"
    avg_order_value_text = f"{avg_order_value:,.2f}" if avg_order_value is not None else "无法计算"

    report = f"""
一、数据概览
本周期总销售额为 {total_sales_text} 元，订单数为 {order_count_text} 单，客单价为 {avg_order_value_text} 元。

二、趋势与周期对比
{rule_analysis.get("sales_trend", "暂无趋势判断结果。")}
{rule_analysis.get("sales_comparison", "暂无销售额周期对比结果。")}
{rule_analysis.get("order_comparison", "暂无订单数周期对比结果。")}
{rule_analysis.get("avg_order_value_comparison", "暂无客单价周期对比结果。")}

三、商品分析
{rule_analysis.get("top_product", "暂无商品分析结果。")}
{rule_analysis.get("product_concentration", "暂无商品集中度分析结果。")}

四、城市分析
{rule_analysis.get("top_city", "暂无城市分析结果。")}

五、风险提示与关注点
{rule_analysis.get("top_risk", "暂无风险提示。")}

六、行动建议
{rule_analysis.get("top_action", "暂无行动建议。")}
"""
    return report.strip()


def generate_text_brief(metrics_result, rule_analysis):
    total_sales = metrics_result.get("total_sales")
    order_count = metrics_result.get("order_count")
    avg_order_value = metrics_result.get("avg_order_value")

    total_sales_text = f"{total_sales:,.2f}" if total_sales is not None else "无法计算"
    order_count_text = f"{order_count:,}" if order_count is not None else "无法计算"
    avg_order_value_text = f"{avg_order_value:,.2f}" if avg_order_value is not None else "无法计算"

    brief = f"""
本周期总销售额为 {total_sales_text} 元，订单数为 {order_count_text} 单，客单价为 {avg_order_value_text} 元。

{rule_analysis.get("top_change", "暂无最重要变化结论。")}

主要风险是：{rule_analysis.get("top_risk", "暂无主要风险。")}
建议优先动作：{rule_analysis.get("top_action", "暂无优先动作建议。")}
"""
    return brief.strip()


def generate_ai_report(metrics_result, rule_analysis, report_type="operations"):
    """
    report_type:
    - operations: 运营版完整报告
    - boss: 老板版摘要
    """
    api_key = get_dashscope_api_key()

    fallback_report = (
        generate_text_brief(metrics_result, rule_analysis)
        if report_type == "boss"
        else generate_text_report(metrics_result, rule_analysis)
    )

    if not api_key:
        return fallback_report + "\n\n[提示：未检测到 DASHSCOPE_API_KEY，已回退到本地模板报告。]"

    total_sales = metrics_result.get("total_sales")
    order_count = metrics_result.get("order_count")
    avg_order_value = metrics_result.get("avg_order_value")

    total_sales_text = f"{total_sales:,.2f}" if total_sales is not None else "无法计算"
    order_count_text = f"{order_count:,}" if order_count is not None else "无法计算"
    avg_order_value_text = f"{avg_order_value:,.2f}" if avg_order_value is not None else "无法计算"

    if report_type == "boss":
        prompt = f"""
你是一名谨慎、专业、不过度推断的数据分析师。

请基于下面信息，生成一份“老板版摘要”。

要求：
1. 只能基于给定信息，不得编造原因。
2. 语言要非常简洁，适合老板快速阅读。
3. 输出控制在 3 段以内。
4. 只需要讲：当前表现、最重要变化、主要风险和优先动作。
5. 不要写空话，不要写市场环境、活动效果、未来预测。

已知指标：
- 总销售额：{total_sales_text}
- 订单数：{order_count_text}
- 客单价：{avg_order_value_text}

已知规则分析结果：
- 销售趋势：{rule_analysis.get("sales_trend", "暂无")}
- 销售额周期对比：{rule_analysis.get("sales_comparison", "暂无")}
- 订单数周期对比：{rule_analysis.get("order_comparison", "暂无")}
- 客单价周期对比：{rule_analysis.get("avg_order_value_comparison", "暂无")}
- 核心商品：{rule_analysis.get("top_product", "暂无")}
- 核心城市：{rule_analysis.get("top_city", "暂无")}
- 商品集中度：{rule_analysis.get("product_concentration", "暂无")}
- 最重要变化：{rule_analysis.get("top_change", "暂无")}
- 主要风险：{rule_analysis.get("top_risk", "暂无")}
- 建议优先动作：{rule_analysis.get("top_action", "暂无")}

现在直接输出老板版摘要。
"""
    else:
        prompt = f"""
你是一名谨慎、专业、面向业务的数据分析师。

你的任务是：基于系统已经计算好的指标和规则分析结果，生成一份中文运营分析报告。

要求：
1. 只能基于已提供的数据和规则结果进行分析。
2. 不允许编造不存在的原因、背景、活动、市场环境、用户行为或业务动作。
3. 不允许做因果推断。
4. 不允许声称“未发现异常”“增长潜力较大”“市场表现良好”等无依据结论。
5. 语言简洁、明确、专业。
6. 如果信息不足，就明确写“当前数据不足以支持进一步判断”。

请严格按照以下结构输出：
一、数据概览
二、趋势与周期对比
三、商品分析
四、城市分析
五、风险提示与关注点
六、行动建议

已知指标：
- 总销售额：{total_sales_text}
- 订单数：{order_count_text}
- 客单价：{avg_order_value_text}

已知规则分析结果：
- 销售趋势：{rule_analysis.get("sales_trend", "暂无")}
- 销售额周期对比：{rule_analysis.get("sales_comparison", "暂无")}
- 订单数周期对比：{rule_analysis.get("order_comparison", "暂无")}
- 客单价周期对比：{rule_analysis.get("avg_order_value_comparison", "暂无")}
- 核心商品：{rule_analysis.get("top_product", "暂无")}
- 核心城市：{rule_analysis.get("top_city", "暂无")}
- 商品集中度：{rule_analysis.get("product_concentration", "暂无")}
- 最重要变化：{rule_analysis.get("top_change", "暂无")}
- 主要风险：{rule_analysis.get("top_risk", "暂无")}
- 建议优先动作：{rule_analysis.get("top_action", "暂无")}

现在开始生成运营版报告。
"""

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        completion = client.chat.completions.create(
            model="qwen-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "你是一名谨慎、专业、不过度推断的数据分析师。你只能基于给定信息写报告，不能编造原因。"
                },
                {
                    "role": "user",
                    "content": prompt
                },
            ],
            temperature=0.2,
        )

        content = completion.choices[0].message.content
        if content and content.strip():
            return content.strip()

        return fallback_report + "\n\n[提示：模型返回空结果，已回退到本地模板报告。]"

    except Exception as e:
        return fallback_report + f"\n\n[提示：AI 调用失败，已回退到本地模板报告。错误信息：{e}]"