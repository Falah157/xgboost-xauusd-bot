import streamlit as st
import datetime

st.set_page_config(page_title="TRADE CHECKLIST", layout="wide")

st.title("📋 PRE-TRADE CHECKLIST")

st.markdown("""
<style>
    .checklist-box { background: #1e1e2e; border-radius: 15px; padding: 1.5rem; margin: 1rem 0; }
    .rule-green { color: #00ff88; }
    .rule-red { color: #ff4444; }
    .rule-yellow { color: #ffd700; }
    .score-card { background: linear-gradient(135deg, #1e1e2e, #2a2a3a); border-radius: 20px; padding: 1.5rem; text-align: center; }
    .big-score { font-size: 4rem; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Initialize checklist state
if 'checklist' not in st.session_state:
    st.session_state.checklist = {
        'trend': False,
        'rsi': False,
        'power': False,
        'timeframes': False,
        'rr': False,
        'news': False,
        'time': False
    }

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown('<div class="checklist-box">', unsafe_allow_html=True)
    st.subheader("✅ STEP BY STEP CHECKLIST")
    
    st.markdown("### 1️⃣ TREND ALIGNMENT")
    trend_ok = st.checkbox("Price above SMA20 for BUY / below for SELL")
    sma_ok = st.checkbox("SMA20 above SMA50 for BUY / below for SELL")
    
    st.markdown("### 2️⃣ RSI CONFIRMATION")
    rsi_buy = st.checkbox("RSI < 40 (Oversold) for BUY")
    rsi_sell = st.checkbox("RSI > 60 (Overbought) for SELL")
    rsi_ok = rsi_buy or rsi_sell
    
    st.markdown("### 3️⃣ POWER METER")
    power_ok = st.checkbox("Buy Power > 60% OR Sell Power > 60%")
    
    st.markdown("### 4️⃣ MULTIPLE TIMEFRAMES")
    tf_ok = st.checkbox("4h and 1h timeframes AGREE on direction")
    
    st.markdown("### 5️⃣ RISK/REWARD")
    rr_ok = st.checkbox("Risk:Reward ratio > 1:2")
    
    st.markdown("### 6️⃣ NEWS CHECK")
    news_ok = st.checkbox("No high-impact news in next 30 minutes")
    
    st.markdown("### 7️⃣ TIME CHECK")
    time_ok = st.checkbox("Trading during London or NY session")
    
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="score-card">', unsafe_allow_html=True)
    st.subheader("📊 SCORE")
    
    # Calculate score
    score = 0
    if trend_ok and sma_ok:
        score += 15
    if rsi_ok:
        score += 15
    if power_ok:
        score += 15
    if tf_ok:
        score += 15
    if rr_ok:
        score += 15
    if news_ok:
        score += 15
    if time_ok:
        score += 10
    
    # Display score
    if score >= 80:
        color = "#00ff88"
        verdict = "🔥 STRONG TRADE"
        action = "✅ TAKE THIS TRADE"
    elif score >= 60:
        color = "#ffd700"
        verdict = "✅ GOOD TRADE"
        action = "✅ Consider taking"
    elif score >= 40:
        color = "#ff8844"
        verdict = "⚠️ WEAK SIGNAL"
        action = "⏸️ Wait for confirmation"
    else:
        color = "#ff4444"
        verdict = "❌ BAD SIGNAL"
        action = "❌ SKIP this trade"
    
    st.markdown(f'<div class="big-score" style="color: {color};">{score}/100</div>', unsafe_allow_html=True)
    st.markdown(f'<h2 style="color: {color};">{verdict}</h2>', unsafe_allow_html=True)
    st.markdown(f'<p style="font-size: 1.2rem;">{action}</p>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# Trade details
st.markdown("---")
st.subheader("📝 TRADE DETAILS")

col1, col2, col3 = st.columns(3)
with col1:
    entry = st.number_input("ENTRY Price", value=0.00, step=1.0)
    sl = st.number_input("STOP LOSS", value=0.00, step=1.0)
with col2:
    tp1 = st.number_input("TP1", value=0.00, step=1.0)
    tp2 = st.number_input("TP2", value=0.00, step=1.0)
with col3:
    account = st.number_input("Account Balance", value=10000, step=1000)
    risk_pct = st.slider("Risk %", 0.5, 2.0, 1.0)

if entry > 0 and sl > 0:
    risk = abs(entry - sl)
    risk_amount = account * (risk_pct / 100)
    position_size = risk_amount / risk if risk > 0 else 0
    
    st.info(f"""
    📊 **POSITION SIZE CALCULATION**
    - Risk per trade: ${risk_amount:.2f}
    - Position Size: {position_size:.4f} lots
    - Stop Loss distance: ${risk:.2f}
    """)

# Export trade plan
if st.button("📋 COPY TRADE PLAN", type="primary"):
    plan = f"""
═══════════════════════════════════════
           TRADE PLAN
═══════════════════════════════════════

DIRECTION: {'BUY (LONG)' if rsi_buy else 'SELL (SHORT)' if rsi_sell else 'WAIT'}
CONFIDENCE: {score}/100 ({verdict})

ENTRY: ${entry:.2f}
STOP LOSS: ${sl:.2f}
RISK: ${risk:.2f}

TAKE PROFITS:
  TP1: ${tp1:.2f}
  TP2: ${tp2:.2f}

POSITION SIZE: {position_size:.4f} lots
RISK AMOUNT: ${risk_amount:.2f}

CHECKLIST VERDICT: {action}
═══════════════════════════════════════
"""
    st.code(plan, language="text")
    st.success("Trade plan copied!")

st.markdown("---")
st.caption("⚠️ Always follow your checklist before every trade!")
