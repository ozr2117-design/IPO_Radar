import streamlit as st
import akshare as ak
import pandas as pd
import datetime
import pytz  # 引入时区库

# --- 页面配置 (必须是第一行代码) ---
st.set_page_config(
    page_title="IPO Radar | 新股雷达",
    page_icon="📡",
    layout="centered", 
    initial_sidebar_state="expanded"
)

# --- CSS美化 ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    /* 隐藏Metric自带的小箭头，保持界面清爽 */
    div[data-testid="stMetricDelta"] > svg {
        display: none; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- 核心数据获取 ---
# 设置 TTL 为 3 秒，避免频繁请求被封，同时保证数据较新
@st.cache_data(ttl=3)
def get_stock_data(code):
    """获取指定股票的实时数据"""
    try:
        # 获取全市场实时行情
        df = ak.stock_zh_a_spot_em()
        # 筛选
        target = df[df['代码'] == code]
        return target
    except Exception as e:
        return pd.DataFrame()

# --- 侧边栏：参数配置 ---
with st.sidebar:
    st.header("⚙️ 核心参数")
    
    # 默认填入C振石，方便测试
    stock_code = st.text_input("股票代码", value="601112", max_chars=6)
    cost_price = st.number_input("中签/持仓成本 (元)", value=11.18, step=0.1, format="%.2f")
    
    st.markdown("---")
    st.subheader("⚖️ 行业估值锚点")
    st.info("如果不确定，选【传统制造】最保险。")
    
    industry_option = st.radio(
        "选择所属赛道：",
        options=[
            "🏗️ 传统制造/基建 (PE 15x)",
            "🧪 一般制造/化工 (PE 25x)",
            "🍺 消费/医药/食品 (PE 35x)",
            "🤖 高科技/芯片/AI (PE 60x)"
        ],
        index=1 # 默认选中一般制造
    )
    
    # 提取基准PE
    if "15x" in industry_option: benchmark_pe = 15
    elif "25x" in industry_option: benchmark_pe = 25
    elif "35x" in industry_option: benchmark_pe = 35
    else: benchmark_pe = 60

# --- 主界面 ---
st.title("📡 IPO Radar")
st.caption("Don't Trust Your Gut, Trust the Data. | 拒绝情绪，相信数据")

# 检查输入
if len(stock_code) != 6:
    st.warning("请输入 6 位股票代码")
    st.stop()

# 添加手动刷新按钮
if st.button("🔄 立即刷新数据", type="primary", use_container_width=True):
    st.cache_data.clear() # 清除缓存强制刷新

# 获取数据
with st.spinner('正在连接交易所...'):
    df = get_stock_data(stock_code)

if df.empty:
    st.error(f"❌ 未找到代码 {stock_code}，请检查是否上市或代码错误。")
else:
    # 数据解包
    name = df['名称'].values[0]
    price = float(df['最新价'].values[0])
    pct = float(df['涨跌幅'].values[0])
    turnover = float(df['换手率'].values[0])
    pe_ttm = float(df['市盈率-动态'].values[0])
    high = float(df['最高'].values[0])
    
    # 计算收益
    profit_amt = (price - cost_price) * 500 # 假设中签500股
    profit_rate = (price - cost_price) / cost_price * 100
    
    # --- 1. 核心看板 ---
    st.subheader(f"{name} ({stock_code})")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("当前价格", f"¥{price}", f"{pct}%")
    m2.metric("浮动盈亏 (500股)", f"¥{profit_amt:.0f}", f"{profit_rate:.1f}%")
    m3.metric("换手率 (热度)", f"{turnover}%", delta="高危" if turnover > 50 else "正常", delta_color="inverse")

    # --- 2. 估值红绿灯 (最关键的部分) ---
    st.markdown("### 🚦 估值诊断")
    
    # 计算溢价倍数
    ratio = pe_ttm / benchmark_pe
    
    col_light, col_text = st.columns([1, 4])
    
    with col_light:
        if ratio > 2.0:
            st.error("🔴") # 大红灯
        elif ratio > 1.5:
            st.warning("🟠") # 黄灯
        else:
            st.success("🟢") # 绿灯
            
    with col_text:
        st.write(f"当前PE **{pe_ttm:.1f}** / 行业基准 **{benchmark_pe}**")
        if ratio > 2.0:
            st.error(f"**极度高估 (溢价{ratio:.1f}倍)** -> 建议：不用想了，直接卖！")
        elif ratio > 1.5:
            st.warning(f"**明显高估 (溢价{ratio:.1f}倍)** -> 建议：设置止盈，破位就跑。")
        else:
            st.success(f"**估值合理** -> 建议：可以多拿一会儿。")

    # --- 3. 动态止盈线 (帮你算好价格) ---
    st.markdown("### 🛡️ 止盈防线")
    
    # 止盈逻辑：最高点回撤 8%
    stop_price = high * 0.92
    is_danger = price < stop_price
    
    c_stop1, c_stop2 = st.columns(2)
    with c_stop1:
        st.info(f"🛑 动态止盈价\n# **{stop_price:.2f}**")
        st.caption(f"(今日最高 {high} × 0.92)")
    
    with c_stop2:
        if is_danger:
            st.error("⚠️ **已击穿止盈线！**\n\n别犹豫，卖出保命！")
        else:
            # 计算距离止盈线还有多少空间
            buffer = (price - stop_price) / price * 100
            st.success(f"✅ **安全**\n\n距离止盈线还有 {buffer:.1f}%")

    # --- 底部时间更新 (已修复时区) ---
    st.divider()
    # 获取北京时间
    beijing_tz = pytz.timezone('Asia/Shanghai')
    current_time = datetime.datetime.now(beijing_tz).strftime('%H:%M:%S')
    st.caption(f"数据更新时间 (北京时间): {current_time}")
