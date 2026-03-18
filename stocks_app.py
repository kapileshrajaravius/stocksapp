import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
import time
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier

# --- INITIALIZATION ---
st.set_page_config(page_title="Market Intelligence Portal", layout="wide")

DB_FILE = 'portfolio.json'
LOG_FILE = 'task_log.json'

# --- HELPERS ---
def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_data(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

def get_currency_sign(ticker):
    return "₹" if ticker.endswith('.NS') or ticker.endswith('.BO') else "$"

def get_ai_prediction_data(ticker):
    """Calculates predictions with heavy rate-limit protection to fix b43689.png errors"""
    for attempt in range(3):
        try:
            time.sleep(1.5) # Increased delay to prevent YFRateLimitError
            data = yf.download(ticker, period="1y", interval="1d", progress=False)
            if len(data) < 40: return "NEUTRAL", 0.0
            
            data['MA10'] = data['Close'].rolling(10).mean()
            data['MA50'] = data['Close'].rolling(50).mean()
            data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
            data = data.dropna()
            
            X = data[['MA10', 'MA50']]
            y = data['Target']
            
            model = RandomForestClassifier(n_estimators=50).fit(X[:-1], y[:-1])
            pred = model.predict(X.tail(1))[0]
            
            # Use volatility to estimate risk/reward potential
            recent_growth = (data['Close'].iloc[-1] / data['Close'].iloc[-10]) - 1
            predicted_pct = recent_growth if pred == 1 else -abs(recent_growth)
            
            return ("UP" if pred == 1 else "DOWN"), float(predicted_pct)
        except Exception as e:
            if "Rate" in str(e):
                time.sleep(5) # Long sleep if blocked
                continue
            return "ERROR", 0.0
    return "ERROR", 0.0

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["Stock Registration", "My Portfolio", "AI Market Analysis", "New Opportunities", "Activity Logs"])

st.sidebar.divider()
st.sidebar.subheader("System Tips")
st.sidebar.info("The AI now filters for positive growth before recommending a stock.")

# --- PAGE: REGISTRATION ---
if page == "Stock Registration":
    st.header("Stock Registration")
    col1, col2, col3 = st.columns(3)
    with col1: t_in = st.text_input("Ticker Symbol").upper()
    with col2: s_in = st.number_input("Units Owned", min_value=0.0)
    with col3: p_in = st.number_input("Buy Price", min_value=0.0)
    
    if st.button("Register Stock"):
        if t_in:
            with st.spinner("Checking Market..."):
                try:
                    check = yf.Ticker(t_in).history(period="1d")
                    if check.empty: st.error(f"Ticker {t_in} not found.")
                    else:
                        port = load_data(DB_FILE)
                        port[t_in] = {"shares": s_in, "buy_price": p_in}
                        save_data(DB_FILE, port)
                        st.success(f"Registered {t_in}")
                except: st.error("Rate limit hit. Wait 1 minute and try again.")

# --- PAGE: MY PORTFOLIO ---
elif page == "My Portfolio":
    st.header("Current Portfolio")
    portfolio = load_data(DB_FILE)
    if portfolio:
        df_p = pd.DataFrame.from_dict(portfolio, orient='index').reset_index()
        df_p.columns = ["Stock", "Units", "Cost"]
        edited = st.data_editor(df_p, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("Save Updates"):
            new_port = {row['Stock']: {"shares": row['Units'], "buy_price": row['Cost']} for _, row in edited.iterrows() if pd.notnull(row['Stock'])}
            save_data(DB_FILE, new_port)
            st.rerun()

# --- PAGE: AI ANALYSIS ---
elif page == "AI Market Analysis":
    st.header("AI Strategy Report")
    portfolio = load_data(DB_FILE)
    if not portfolio: st.warning("Add stocks to begin.")
    elif st.button("Analyze My Holdings"):
        results = []
        with st.spinner("Processing AI Brain..."):
            for s, info in portfolio.items():
                price_data = yf.Ticker(s).history(period="1d")
                if price_data.empty: continue
                cur = get_currency_sign(s)
                price = float(price_data['Close'].iloc[-1])
                gain_pct = ((price - info['buy_price']) / info['buy_price']) * 100
                _, pred_pct = get_ai_prediction_data(s)
                results.append({"Stock": s, "Price": f"{cur}{price:,.2f}", "Gain": f"{gain_pct:+.2f}%", "AI Predict": f"{pred_pct:+.2%}"})
        st.table(pd.DataFrame(results))

# --- PAGE: NEW OPPORTUNITIES ---
elif page == "New Opportunities":
    st.header("Investment Tiers")
    st.write("AI scans global markets for specific growth profiles.")
    
    scan_list = ["NVDA", "AAPL", "TSLA", "TCS.NS", "RELIANCE.NS", "BTC-USD", "COIN", "MSFT", "AMD", "GOOGL"]
    
    if st.button("Scan for New Opportunities"):
        risky, slow = [], []
        with st.spinner("Filtering opportunities..."):
            for s in scan_list:
                pred, pred_pct = get_ai_prediction_data(s)
                # Only recommend if prediction is POSITIVE
                if pred == "UP" and pred_pct > 0:
                    cur = get_currency_sign(s)
                    price = yf.Ticker(s).history(period="1d")['Close'].iloc[-1]
                    row = {"Stock": s, "Price": f"{cur}{price:,.2f}", "Est. Growth": f"{pred_pct:+.2%}"}
                    
                    if pred_pct > 0.05: # Over 5% predicted growth is "High Risk"
                        risky.append(row)
                    else:
                        slow.append(row)

        st.subheader("🔥 High Risk / High Reward")
        st.write("Volatile stocks with potential for massive short-term gains.")
        st.table(pd.DataFrame(risky)) if risky else st.write("No high-risk breakouts detected.")

        st.subheader("🛡️ Slow & Steady Growth")
        st.write("Lower volatility stocks for consistent, reliable wealth building.")
        st.table(pd.DataFrame(slow)) if slow else st.write("No steady growth signals detected.")

# --- PAGE: LOGS ---
elif page == "Activity Logs":
    st.header("History")
    logs = load_data(LOG_FILE)
    if logs:
        for ts, msg in reversed(list(logs.items())): st.write(f"**{ts}**: {msg}")
    if st.button("Clear All Logs"):
        save_data(LOG_FILE, {})
        st.rerun()
