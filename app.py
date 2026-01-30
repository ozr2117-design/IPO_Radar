import streamlit as st
import akshare as ak
import pandas as pd
import datetime
import pytz
import requests  # 用于请求腾讯接口

# --- 1. 页面配置 (必须位于代码最开头) ---
st.set_page_config(
    page_title="IPO Radar | 新股雷达",
    page_icon="📡",
    layout="centered",
    initial_sidebar_state="expanded"
)

# --- 2. CSS 美化 (优化手机端显示) ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    /* 隐藏 Metric 自带的小箭头，保持界面清爽 */
    div[data-testid="stMetricDelta"] > svg {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 核心数据获取 (三级火箭策略) ---
@st.cache_data(ttl=3)
def get_stock_data(code):
    """
    获取股票数据，执行【三级火箭】容错策略：
    1. 东财-新股列表 (针对C/N类新股，数据最详尽)
    2. 东财-全市场列表 (针对普通股票)
    3. 腾讯-HTTP接口 (终极兜底，只有价格，速度最快，永不挂)
    """
    code = str(code).strip()
    
    # 辅助函数：统一数据格式，方便后续调用
    def format_df(name, price, pct, turnover, pe, high, source):
        return pd.DataFrame({
            '名称': [str(name)],
            '最新价': [float(price)],
            '涨跌幅': [float(pct)],
            '换手率': [float(turnover)],
            '市盈率-动态': [float(pe) if pe != "" else 0.0],
            '最高': [float(high)],
            'source': [source] # 标记数据来源
        })

    # === 🚀 第1级：东财新股专属表 (数据质量最高) ===
    try:
        df_new = ak.stock_new_a_spot_em()
        target = df_new[df_new['代码'] == code]
        if not target.empty:
            return format_df(
                target['名称'].values[0], target['最新价'].values[0],
                target['涨跌幅'].values[0], target['换手率'].values[0],
                target['市盈率-动态'].values[0], target['最高'].values[0],
                "东财新股表"
            ), "full"
    except Exception:
        pass # 失败，静默进入下一级

    # === 🚀 第2级：东财全市场列表 (覆盖面最广) ===
    try:
        df_all = ak.stock_zh_a_spot_em()
        target = df_all[df_all['代码'] == code]
        if not target.empty:
            return format_df(
                target['名称'].values[0], target['最新价'].values[0],
                target['涨跌幅'].values[0], target['换手率'].values[0],
                target['市盈率-动态'].values[0], target['最高'].values[0],
                "东财全市场"
            ), "full"
    except Exception:
        pass

    # === 🚀 第3级：腾讯 HTTP 接口 (速度快，死得慢，兜底神器) ===
    try:
        # 判断前缀
        if code.startswith('6'): prefix = 'sh'
        elif code.startswith('8') or code.startswith('4'): prefix = 'bj'
        else: prefix = 'sz'
        
        url = f"http://qt.gtimg.cn/q={prefix}{code}"
        r = requests.get(url, timeout=2)
        
        # 腾讯返回格式: v_sh601112="1~C振石~601112~22.14~..."
        data_str = r.text
        if f'v_{prefix}{code}="' in data_str:
            parts = data_str.split('~')
            if len(parts) > 35: # 确保数据够长
                name = parts[1]
                price = parts[3]
                pct = parts[32] 
                high = parts[33]
                turnover = parts[38] if len(parts) > 38 else 0
                pe = parts[39] if len(parts) > 39 else 0 # 腾讯PE有时候为空
                
                return format_df(name, price, pct, turnover, pe, high, "腾讯接口"), "tencent"
    except Exception as e:
        print(f"腾讯接口报错: {e}")
        pass
        
    return pd.DataFrame(), "none"

# --- 4. 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 参数配置")
    
    # 输入框
    stock_code = st.text_input("股票代码", value="601112", max_chars=6)
    cost_price = st.number_input("中签成本 (元)", value=11.18, step=0.1, format="%.2f")
    
    st.markdown("---")
    st.subheader("⚖️ 行业估值参考")
    
    industry_option = st.radio(
        "选择所属赛道：",
        options=[
            "🏗️ 传统制造/基建 (PE 15x)",
            "🧪 一般制造/化工 (PE 25x)",
            "🍺 消费/医药/食品 (PE 35x)",
            "🤖 高科技/芯片/AI (PE 60x)"
        ],
        index=1 
    )
    
    # 提取基准PE
    if "15x" in industry_option: benchmark_pe = 15
    elif "25x" in industry_option: benchmark_pe = 25
    elif "35x" in industry_option: benchmark_pe = 35
    else: benchmark_pe = 60

# --- 5. 主界面逻辑 ---
st.title("📡 IPO Radar")
st.caption("拒绝情绪，相信数据 | Data-Driven Decisions")

if len(stock_code) != 6:
    st.warning("请输入 6 位股票代码")
    st.stop()

# 刷新按钮
if st.button("🔄 立即刷新数据", type="primary", use_container_width=True):
    st.cache_data.clear()

# 获取数据
with st.spinner('正在全网搜索行情...'):
    df, mode = get_stock_data(stock_code)

if df.empty:
    st.error(f"❌ 依然未找到代码 {stock_code}。请确认代码正确或等待开盘。")
else:
    # --- 解包数据 ---
    row = df.iloc[0]
    name = row['名称']
    price = row['最新价']
    pct = row['涨跌幅']
    turnover = row['换手率']
    pe_ttm = row['市盈率-动态']
    high = row['最高']
    source = row['source'] # 数据源

    # --- 模块1：核心看板 ---
    st.subheader(f"{name} ({stock_code})")
    st.caption(f"📡 数据通道: **{source}**") # <--- 这里会显示你正在用哪个源

    # 收益计算
    profit_amt = (price - cost_price) * 500
    profit_rate = (price - cost_price) / cost_price * 100

    m1, m2, m3 = st.columns(3)
    m1.metric("当前价格", f"¥{price}", f"{pct}%")
    m2.metric("浮动盈亏", f"¥{profit_amt:.0f}", f"{profit_rate:.1f}%")
    
    if mode == "full" and turnover > 0:
        m3.metric("换手率", f"{turnover}%", delta="高危" if turnover > 50 else "正常", delta_color="inverse")
    else:
        m3.metric("换手率", "--", "暂缺")

    # --- 模块2：估值红绿灯 ---
    st.markdown("### 🚦 估值诊断")
    
    # 只有当 PE 有效且大于0时才计算
    if pe_ttm > 0:
        ratio = pe_ttm / benchmark_pe
        col_light, col_text = st.columns([1, 4])
        
        with col_light:
            if ratio > 2.0: st.error("🔴")
            elif ratio > 1.5: st.warning("🟠")
            else: st.success("🟢")
            
        with col_text:
            st.write(f"当前PE **{pe_ttm:.1f}** / 行业基准 **{benchmark_pe}**")
            if ratio > 2.0: st.error(f"**极度高估 (溢价{ratio:.1f}倍)** -> 建议：立刻卖出")
            elif ratio > 1.5: st.warning(f"**明显高估 (溢价{ratio:.1f}倍)** -> 建议：设置止盈")
            else: st.success(f"**估值合理** -> 建议：可以持有")
    else:
        st.info("ℹ️ 当前数据源暂无PE数据（可能是新股尚未录入），无法评级。请重点参考下方的【止盈防线】。")

    # --- 模块3：动态止盈线 ---
    st.markdown("### 🛡️ 止盈防线")
    
    # 如果最高价获取失败（极少情况），用当前价兜底
    if high == 0: high = price
    
    stop_price = high * 0.92
    is_danger = price < stop_price
    
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"🛑 动态止盈价\n# **{stop_price:.2f}**")
        st.caption(f"(基于日内最高 {high} × 0.92)")
    with c2:
        if is_danger:
            st.error("⚠️ **已击穿止盈线！**\n\n建议卖出保命！")
        else:
            buffer = (price - stop_price) / price * 100
            st.success(f"✅ **安全**\n\n距离红线还有 {buffer:.1f}%")

    # --- 底部时间 (北京时间) ---
    st.divider()
    beijing_tz = pytz.timezone('Asia/Shanghai')
    current_time = datetime.datetime.now(beijing_tz).strftime('%H:%M:%S')
    st.caption(f"更新时间 (北京): {current_time}")
