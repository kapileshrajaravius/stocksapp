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
    .main { max-width: 1100px; margin: 0 auto; }
    </style>
    """, unsafe_allow_html=True)

DB_FILE = 'portfolio.json'
HIST_FILE = 'history.json'
LOG_FILE = 'task_log.json'

# --- AI CORE ENGINE ---
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
        try:
            with open(file, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_data(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

# --- TABBED NAVIGATION ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📂 Portfolio Management", 
    "🧠 AI Strategy & Actions", 
    "🌍 Market Discovery", 
    "📜 History Logs"
])

# --- TAB 1: REGISTRATION ---
with tab1:
    st.header("Asset Registration")
    col1, col2, col3 = st.columns(3)
    with col1: t_in = st.text_input("Ticker Symbol", placeholder="e.g., AAPL or TCS.NS").upper()
    with col2: s_in = st.number_input("Shares Owned", min_value=0.0, step=1.0)
    with col3: p_in = st.number_input("Purchase Price (Unit Cost)", min_value=0.0, step=0.01)
    
    if st.button("Add to Portfolio"):
        if t_in:
            if yf.Ticker(t_in).history(period="1d").empty:
                st.error(f"something is wrong with the ticker {t_in}")
            else:
                port = load_data(DB_FILE)
                port[t_in] = {"shares": s_in, "buy_price": p_in}
                save_data(DB_FILE, port)
                st.success(f"Registered {t_in}")
                st.rerun()
    
    st.divider()
    portfolio = load_data(DB_FILE)
    if portfolio:
        st.subheader("Current Holdings Management")
        df_p = pd.DataFrame.from_dict(portfolio, orient='index').reset_index()
        df_p.columns = ["Stock", "Units", "Buy Price"]
        edited = st.data_editor(df_p, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("Save Changes / Delete Asset"):
            new_port = {row['Stock']: {"shares": row['Units'], "buy_price": row['Buy Price']} 
                        for _, row in edited.iterrows() if pd.notnull(row['Stock'])}
            save_data(DB_FILE, new_port)
            st.rerun()

# --- TAB 2: AI STRATEGY ---
with tab2:
    st.header("AI Market Strategy")
    if st.button("Generate Current Strategy Tables"):
        portfolio = load_data(DB_FILE)
        if not portfolio:
            st.warning("Please add stocks in the Portfolio tab first.")
        else:
            with st.spinner("Analyzing your portfolio..."):
                buy_more, hold, sell = [], [], []
                for s, info in portfolio.items():
                    price = yf.Ticker(s).history(period="1d")['Close'].iloc[-1]
                    gain = ((price - info['buy_price']) / info['buy_price']) * 100
                    sig, conf = get_ai_signal(s)
                    row = {"Stock": s, "Live Price": f"${price:,.2f}", "P/L %": f"{gain:.2f}%", "AI Confidence": f"{conf:.0%}"}
                    
                    if sig == "BEARISH" or gain > 30: sell.append(row)
                    elif sig == "BULLISH" and gain < 10: buy_more.append(row)
                    else: hold.append(row)

                st.subheader("🚀 Accumulate (Buy More)")
                st.table(pd.DataFrame(buy_more)) if buy_more else st.write("No accumulation signals.")
                
                st.subheader("💎 Hold (Maintain Position)")
                st.table(pd.DataFrame(hold)) if hold else st.write("No hold signals.")
                
                st.subheader("⚠️ Liquidate (Recommended Sell)")
                st.table(pd.DataFrame(sell)) if sell else st.write("No sell signals.")
                
                st.divider()
                if st.button("I Have Completed These Actions"):
                    logs = load_data(LOG_FILE)
                    logs[datetime.now().strftime("%Y-%m-%d %H:%M")] = "User executed strategy actions."
                    save_data(LOG_FILE, logs)
                    st.success("Action logged successfully.")

# --- TAB 3: DISCOVERY ---
with tab3:
    st.header("New Opportunities")
    st.write("Strong 'BUY' signals for stocks not currently in your portfolio.")
    watch_list = ["NVDA", "AAPL", "TCS.NS", "RELIANCE.NS", "TSLA", "MSFT", "GOOGL"]
    discoveries = []
    portfolio = load_data(DB_FILE)
    for s in watch_list:
        if s not in portfolio:
            sig, conf = get_ai_signal(s)
            if sig == "BULLISH" and conf > 0.65:
                discoveries.append({"Stock": s, "Signal": "BULLISH", "Confidence": f"{conf:.0%}"})
    st.table(pd.DataFrame(discoveries)) if discoveries else st.write("Scanning for new opportunities...")

# --- TAB 4: LOGS ---
with tab4:
    st.header("Task & Analysis History")
    logs = load_data(LOG_FILE)
    if logs:
        st.subheader("Completed Actions")
        for ts, msg in reversed(list(logs.items())):
            st.write(f"✅ **{ts}**: {msg}")
    
    if st.button("Delete All Logs"):
        save_data(LOG_FILE, {})
        st.rerun()
