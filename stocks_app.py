import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier

# --- INITIALIZATION ---
st.set_page_config(page_title="AI Investment Strategist", layout="wide")

st.markdown("""
    <style>
    thead tr th { background-color: #1e2630 !important; color: white !important; }
    .stButton>button { border-radius: 4px; height: 3em; background-color: #004a99; color: white; width: 100%; }
    .success-text { color: #28a745; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

DB_FILE = 'portfolio.json'
COMPLETED_FILE = 'actions_completed.json'

# --- AI CORE ---
def get_ai_signal(ticker):
    try:
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(data) < 40: return "NEUTRAL", 0.5
        data['MA10'] = data['Close'].rolling(10).mean()
        data['MA50'] = data['Close'].rolling(50).mean()
        data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        data = data.dropna()
        X = data[['MA10', 'MA50']]
        y = data['Target']
        model = RandomForestClassifier(n_estimators=50).fit(X[:-1], y[:-1])
        pred = model.predict(X.tail(1))[0]
        prob = model.predict_proba(X.tail(1))[0][pred]
        return ("BULLISH" if pred == 1 else "BEARISH"), prob
    except: return "ERROR", 0

def load_data(file):
    if os.path.exists(file):
        with open(file, 'r') as f: return json.load(f)
    return {}

def save_data(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

# --- MAIN INTERFACE ---
st.title("AI Investment Strategist")

# 1. PORTFOLIO REGISTRATION
with st.expander("Update Current Holdings"):
    c1, c2, c3 = st.columns(3)
    with c1: t_in = st.text_input("Stock Ticker").upper()
    with c2: s_in = st.number_input("Units", min_value=0.0)
    with c3: p_in = st.number_input("Buy Price", min_value=0.0)
    if st.button("Add Stock"):
        port = load_data(DB_FILE)
        port[t_in] = {"shares": s_in, "buy_price": p_in}
        save_data(DB_FILE, port)
        st.rerun()

st.divider()

if st.button("Generate AI Market Strategy"):
    portfolio = load_data(DB_FILE)
    
    # 2. DISCOVERY (Stocks to Buy - Not Owned)
    st.subheader("1. Market Discovery: Recommended to Buy")
    watch_list = ["NVDA", "TSLA", "AAPL", "MSFT", "RELIANCE.NS", "TCS.NS", "GOOGL"]
    new_buys = []
    for s in watch_list:
        if s not in portfolio:
            sig, conf = get_ai_signal(s)
            if sig == "BULLISH" and conf > 0.6:
                new_buys.append({"Stock": s, "Signal": "STRONG BUY", "Confidence": f"{conf:.0%}"})
    st.table(pd.DataFrame(new_buys) if new_buys else "No new high-confidence buys detected.")

    if portfolio:
        buy_more, hold, sell = [], [], []
        
        for s, info in portfolio.items():
            curr_price = yf.Ticker(s).history(period="1d")['Close'].iloc[-1]
            gain = ((curr_price - info['buy_price']) / info['buy_price']) * 100
            sig, conf = get_ai_signal(s)
            
            row = {"Stock": s, "Current Price": f"${curr_price:,.2f}", "Profit/Loss": f"{gain:.1f}%"}
            
            if sig == "BEARISH" or gain > 25:
                sell.append(row)
            elif sig == "BULLISH" and gain < 5:
                buy_more.append(row)
            else:
                hold.append(row)

        # 3. BUY MORE TABLE
        st.subheader("2. Accumulate: Buy More of These")
        st.table(pd.DataFrame(buy_more) if buy_more else "No current accumulation signals.")

        # 4. HOLD TABLE
        st.subheader("3. Core Positions: Maintain & Hold")
        st.table(pd.DataFrame(hold) if hold else "No hold positions.")

        # 5. SELL TABLE
        st.subheader("4. Liquidate: Recommended to Sell")
        st.table(pd.DataFrame(sell) if sell else "No sell signals.")

        st.divider()
        
        # 6. ACTION COMPLETED BUTTON
        st.subheader("Task Management")
        if st.button("Mark All Recommended Actions as Completed"):
            done_log = load_data(COMPLETED_FILE)
            done_log[datetime.now().strftime("%Y-%m-%d %H:%M")] = "Actions Executed"
            save_data(COMPLETED_FILE, done_log)
            st.success("Log Updated: Your dad's actions have been recorded in history.")
