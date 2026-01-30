import streamlit as st
import pandas as pd
import datetime
import pytz
import requests

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="IPO Radar | 极速版",
    page_icon="📡",
    layout="centered",
    initial_sidebar_state="expanded"
)

# --- 2. CSS 美化 (手机端优化) ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    div[data-testid="stMetricDelta"] > svg {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 核心数据获取 (纯腾讯源) ---
@st.cache_data(ttl=2) # 2秒缓存，近乎实时
def get_stock_data_tencent(code):
    """
    只使用腾讯 HTTP 接口获取行情，追求极致速度。
    """
    code = str(code).strip()
    
    # 自动判断市场前缀 (兼容沪深京)
    if code.startswith('6'): 
        prefix = 'sh'
    elif code.startswith('8') or code.startswith('4'): 
        prefix = 'bj'
    else: 
        prefix = 'sz'
    
    # 腾讯极速接口
    url = f"http://qt.gtimg.cn/q={prefix}{code}"
    
    try:
        # 设置1秒超时，秒开秒回
        r = requests.get(url, timeout=1)
        data_str = r.text
        
        # 腾讯返回格式验证: v_sh601112="1~名称~..."
        if f'v_{prefix}{code}="' not in data_str:
            return pd.DataFrame() 
            
        # 解析数据
        content = data_str.split('"')[1]
        parts = content.split('~')
        
        if len(parts) < 30:
            return pd.DataFrame() 

        # 提取关键字段
        # 1:名称, 3:当前价, 32:涨跌幅, 33:最高, 38:换手率, 39:市盈率
        name = parts[1]
        price = float(parts[3])
        pct = float(parts[32])
        high = float(parts[33])
        
        # 容错处理：新股可能暂无换手率或PE
        try:
            turnover = float(parts[38]) if parts[38] != '' else 0.0
        except:
            turnover = 0.0
            
        try:
            pe_ttm = float(parts[39]) if parts[39] != '' else 0.0
        except:
            pe_ttm = 0.0

        # 构造 DataFrame
        df = pd.DataFrame({
            '名称': [name],
            '最新价': [price],
            '涨跌幅': [pct],
            '换手率': [turnover],
            '市盈率-动态': [pe_ttm],
            '最高': [high]
        })
        return df

    except Exception as e:
        # 极其罕见的网络波动，返回空即可
        return pd.DataFrame()

# --- 4. 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 参数配置")
    stock_code = st.text_input("股票代码", value="601112", max_chars=6)
    cost_price = st.number_input("成本价 (元)", value=11.18, step=0.1, format="%.2f")
    
    st.markdown("---")
    st.subheader("⚖️ 行业估值参考")
    industry_option = st.radio(
        "选择所属赛道：",
        options=["🏗️ 传统 (15x)", "🧪 一般 (25x)", "🍺 消费 (35x)", "🤖 科技 (60x)"],
        index=1 
    )
    if "15x" in industry_option: benchmark_pe = 15
    elif "25x" in industry_option: benchmark_pe = 25
    elif "35x" in industry_option: benchmark_pe = 35
    else: benchmark_pe = 60

# --- 5. 主界面逻辑 ---
st.title("📡 IPO Radar (极速版)")

if len(stock_code) != 6:
    st.warning("请输入 6 位股票代码")
    st.stop()

# 刷新按钮 (腾讯源极快，点这个基本上是秒刷)
if st.button("🔄 刷新数据", type="primary", use_container_width=True):
    st.cache_data.clear()

with st.spinner('正在连接腾讯接口...'):
    df = get_stock_data_tencent(stock_code)

if df.empty:
    st.error(f"❌ 未找到代码 {stock_code}，请检查代码或等待上市。")
else:
    # 解包数据
    row = df.iloc[0]
    name = row['名称']
    price = row['最新价']
    pct = row['涨跌幅']
    turnover = row['换手率']
    pe_ttm = row['市盈率-动态']
    high = row['最高']
    
    # --- 模块1：核心看板 ---
    st.subheader(f"{name} ({stock_code})")
    
    profit_amt = (price - cost_price) * 500
    profit_rate = (price - cost_price) / cost_price * 100

    m1, m2, m3 = st.columns(3)
    m1.metric("当前价格", f"¥{price}", f"{pct}%")
    m2.metric("浮动盈亏", f"¥{profit_amt:.0f}", f"{profit_rate:.1f}%")
    
    if turnover > 0:
        m3.metric("换手率", f"{turnover}%", delta="高危" if turnover > 50 else "正常", delta_color="inverse")
    else:
        m3.metric("换手率", "--", "暂无")

    # --- 模块2：估值诊断 ---
    st.markdown("### 🚦 估值诊断")
    if pe_ttm > 0:
        ratio = pe_ttm / benchmark_pe
        c_light, c_text = st.columns([1, 4])
        with c_light:
            if ratio > 2.0: st.error("🔴")
            elif ratio > 1.5: st.warning("🟠")
            else: st.success("🟢")
        with c_text:
            st.write(f"当前PE **{pe_ttm:.1f}** / 基准 **{benchmark_pe}**")
            if ratio > 2.0: st.error(f"极度高估 (溢价{ratio:.1f}倍) -> 建议：坚决卖出")
            elif ratio > 1.5: st.warning(f"明显高估 (溢价{ratio:.1f}倍) -> 建议：设置止盈")
            else: st.success("估值合理 -> 建议：持有观察")
    else:
        st.info("ℹ️ 腾讯源暂无PE数据（可能是首日数据尚未入库），请重点参考下方的【止盈防线】。")

    # --- 模块3：止盈防线 ---
    st.markdown("### 🛡️ 止盈防线")
    # 如果最高价是0（极端情况），用当前价兜底
    if high == 0: high = price 
    stop_price = high * 0.92
    
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"🛑 动态止盈价\n# **{stop_price:.2f}**")
    with c2:
        if price < stop_price:
            st.error("⚠️ **已击穿止盈线！建议卖出**")
        else:
            buffer = (price - stop_price) / price * 100
            st.success(f"✅ 安全 (缓冲 {buffer:.1f}%)")

    # --- 底部时间 ---
    st.divider()
    beijing_tz = pytz.timezone('Asia/Shanghai')
    current_time = datetime.datetime.now(beijing_tz).strftime('%H:%M:%S')
    st.caption(f"数据源: 腾讯财经 | 更新时间: {current_time}")
