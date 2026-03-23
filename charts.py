import plotly.express as px


def create_daily_sales_chart(daily_sales_df):
    if daily_sales_df is None or daily_sales_df.empty:
        return None

    fig = px.line(
        daily_sales_df,
        x="date",
        y="sales",
        title="按天销售趋势"
    )
    fig.update_layout(xaxis_title="日期", yaxis_title="销售额")
    return fig


def create_top_products_chart(top_products_df):
    if top_products_df is None or top_products_df.empty:
        return None

    fig = px.bar(
        top_products_df,
        x="product",
        y="sales",
        title="Top 商品销售额"
    )
    fig.update_layout(xaxis_title="商品", yaxis_title="销售额")
    return fig


def create_top_cities_chart(top_cities_df):
    if top_cities_df is None or top_cities_df.empty:
        return None

    fig = px.bar(
        top_cities_df,
        x="city",
        y="sales",
        title="Top 城市销售额"
    )
    fig.update_layout(xaxis_title="城市", yaxis_title="销售额")
    return fig