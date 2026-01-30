import streamlit as st
import akshare as ak
import pandas as pd
import datetime
import pytz

# --- 页面配置 ---
st.set_page_config(
    page_title="IPO Radar | 新股雷达",
    page_icon="📡",
    layout="centered", 
    initial_sidebar_state="expanded"
)

# --- CSS美化 ---
st.markdown("""
    <style>
    .stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 5px;}
    div[data-testid="stMetricDelta"] > svg {display: none;}
    </style>
    """, unsafe_allow_html=True)

# --- 核心数据获取 (双保险版) ---
@st.cache_data(ttl=3)
def get_stock_data(code):
    """
    获取股票数据，包含降级策略：
    1. 尝试从全市场列表获取（数据最全，含PE、换手率）
    2. 失败则尝试从个股盘口获取（只有价格，保底显示）
    """
    code = str(code).strip() # 去除可能存在的空格
    
    # --- 方案A：全市场快照 (首选) ---
    try:
        df_all = ak.stock_zh_a_spot_em()
        target = df_all[df_all['代码'] == code]
        if not target.empty:
            return target, "full" # 返回数据和模式标识
    except Exception:
        pass # 方案A失败，静默转方案B
    
    # --- 方案B：个股盘口 (备选，针对新股搜不到的情况) ---
    try:
        # 获取买卖五档盘口
        df_ask_bid = ak.stock_bid_ask_em(symbol=code)
        if not df_ask_bid.empty:
            # 构造一个简易的DataFrame，模拟方案A的格式
            # 注意：盘口接口没有PE和换手率，我们需要手动处理这些缺失
            latest_price = float(df_ask_bid[df_ask_bid['item'] == 'sell_1']['value'].values[0])
            # 如果跌停或无卖单，尝试取买1
            if latest_price == 0:
                 latest_price = float(df_ask_bid[df_ask_bid['item'] == 'buy_1']['value'].values[0])
                 
            mock_data = {
                '代码': [code],
                '名称': ['N/C新股(备用源)'], 
                '最新价': [latest_price],
                '涨跌幅': [0.0], # 备用源很难算涨跌幅，暂置0
                '换手率': [0.0], # 缺失
                '市盈率-动态': [0.0], # 缺失
                '最高': [latest_price * 1.1] # 估算一个最高价防止报错
            }
            return pd.DataFrame(mock_data), "backup"
    except Exception as e:
        pass
        
    return pd.DataFrame(), "none"

# --- 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 核心参数")
    stock_code = st.text_input("股票代码", value="601112", max_chars=6)
    cost_price = st.number_input("中签成本 (元)", value=11.18, step=0.1, format="%.2f")
    st.markdown("---")
    st.subheader("⚖️ 行业估值锚点")
    industry_option = st.radio("选择赛道：", ["🏗️ 传统 (15x)", "🧪 一般 (25x)", "🍺 消费 (35x)", "🤖 科技 (60x)"], index=1)
    
    if "15x" in industry_option: benchmark_pe = 15
    elif "25x" in industry_option: benchmark_pe = 25
    elif "35x" in industry_option: benchmark_pe = 35
    else: benchmark_pe = 60

# --- 主界面 ---
st.title("📡 IPO Radar")

if len(stock_code) != 6:
    st.warning("请输入 6 位股票代码")
    st.stop()

if st.button("🔄 立即刷新数据", type="primary", use_container_width=True):
    st.cache_data.clear()

# 获取数据
with st.spinner('正在连接交易所...'):
    df, mode = get_stock_data(stock_code)

if df.empty:
    st.error(f"❌ 依然未找到代码 {stock_code}。可能是刚上市数据源延迟，请稍后刷新。")
    # 添加调试建议
    st.info("💡 提示：如果持续报错，请检查 requirements.txt 中的 akshare 版本是否已更新。")
else:
    # 数据提取
    price = float(df['最新价'].values[0])
    
    # 如果是备用模式，名称可能拿不到，尝试显示代码
    name = df['名称'].values[0] if mode == "full" else f"代码 {stock_code}"
    
    # 只有全量模式才有这些数据
    pct = float(df['涨跌幅'].values[0]) if mode == "full" else 0.0
    turnover = float(df['换手率'].values[0]) if mode == "full" else 0.0
    pe_ttm = float(df['市盈率-动态'].values[0]) if mode == "full" else 0.0
    high = float(df['最高'].values[0]) if mode == "full" else price

    # 计算收益
    profit_amt = (price - cost_price) * 500 
    profit_rate = (price - cost_price) / cost_price * 100
    
    # --- 1. 核心看板 ---
    st.subheader(f"{name}")
    if mode == "backup":
        st.warning("⚠️ 正在使用备用数据源（仅显示价格，PE/换手率暂时不可用）")

    m1, m2, m3 = st.columns(3)
    m1.metric("当前价格", f"¥{price}", f"{pct}%" if mode=="full" else None)
    m2.metric("浮动盈亏", f"¥{profit_amt:.0f}", f"{profit_rate:.1f}%")
    
    if mode == "full":
        m3.metric("换手率", f"{turnover}%", delta="高危" if turnover > 50 else "正常", delta_color="inverse")
    else:
        m3.metric("换手率", "--", "数据源暂缺")

    # --- 2. 估值红绿灯 ---
    st.markdown("### 🚦 估值诊断")
    if mode == "full" and pe_ttm > 0:
        ratio = pe_ttm / benchmark_pe
        col_light, col_text = st.columns([1, 4])
        with col_light:
            if ratio > 2.0: st.error("🔴")
            elif ratio > 1.5: st.warning("🟠")
            else: st.success("🟢")
        with col_text:
            st.write(f"当前PE **{pe_ttm:.1f}** / 基准 **{benchmark_pe}**")
            if ratio > 2.0: st.error(f"极度高估 (溢价{ratio:.1f}倍) -> 建议卖出")
            elif ratio > 1.5: st.warning(f"明显高估 (溢价{ratio:.1f}倍) -> 建议止盈")
            else: st.success("估值合理 -> 可持有")
    else:
        st.info("ℹ️ 暂无市盈率数据，无法进行估值评级（可能是新股数据源尚未同步PE）。请主要参考【止盈防线】。")

    # --- 3. 止盈防线 ---
    st.markdown("### 🛡️ 止盈防线")
    stop_price = high * 0.92
    
    # 如果是备用模式，high可能不准，我们用(当前价+成本)/2 做一个粗略支撑位，或者仅提示
    if mode == "backup":
        st.caption("注：备用模式下，止盈线基于当前价动态计算。")
        stop_price = price * 0.95 # 备用模式下收紧止损，回撤5%就跑
    
    is_danger = price < stop_price
    
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"🛑 动态止盈价\n# **{stop_price:.2f}**")
    with c2:
        if is_danger:
            st.error("⚠️ **击穿止盈线！建议卖出**")
        else:
            buffer = (price - stop_price) / price * 100
            st.success(f"✅ 安全 (缓冲 {buffer:.1f}%)")

    # --- 时间 ---
    st.divider()
    beijing_tz = pytz.timezone('Asia/Shanghai')
    st.caption(f"更新时间 (北京): {datetime.datetime.now(beijing_tz).strftime('%H:%M:%S')}")
