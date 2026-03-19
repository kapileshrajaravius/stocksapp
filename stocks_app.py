import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
import time
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier

# --- INITIALIZATION ---
st.set_page_config(page_title="Global Market Intelligence", layout="wide")

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

def get_ai_prediction_data(ticker):
    """Calculates predictions with simplified 'Why' logic"""
    try:
        time.sleep(1.2) # Patience filter for rate limits
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        if data.empty or len(data) < 50: 
            return "NEUTRAL", 0.0, None, "Not enough data to decide"
        
        # Simple Logic check
        price = float(data['Close'].iloc[-1])
        avg_short = data['Close'].rolling(10).mean().iloc[-1]
        avg_long = data['Close'].rolling(50).mean().iloc[-1]
        
        reasons = []
        if price > avg_short: reasons.append("Price is on a short-term hot streak")
        else: reasons.append("Price is cooling down lately")
        
        if avg_short > avg_long: reasons.append("The overall trend is pointing up")
        else: reasons.append("The general trend is slowing down")
        
        # AI Training (Simple Up/Down)
        data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        data = data.dropna()
        model = RandomForestClassifier(n_estimators=30).fit(data[['Close']][:-1], data['Target'][:-1])
        pred = model.predict(data[['Close']].tail(1))[0]
        
        recent_change = (price / data['Close'].iloc[-10]) - 1
        return ("UP" if pred == 1 else "DOWN"), float(recent_change), price, " & ".join(reasons)
    except:
        return "ERROR", 0.0, None, "Technical glitch - try again"

# --- SIDEBAR ---
st.sidebar.title("Menu")
page = st.sidebar.radio("Go to:", ["Portfolio", "AI Analysis", "Global Opportunities"])
st.sidebar.divider()
st.sidebar.subheader("Quick Tips")
st.sidebar.text("1. Works for all International stocks.")
st.sidebar.text("2. AI looks at simple price trends.")
st.sidebar.text("3. 'Buy More' means trend is strong.")

# --- PAGE: PORTFOLIO ---
if page == "Portfolio":
    st.header("My Global Portfolio")
    portfolio = load_data(DB_FILE)
    if portfolio:
        df_p = pd.DataFrame.from_dict(portfolio, orient='index').reset_index()
        df_p.columns = ["Ticker", "Units", "Buy Price"]
        df_p.index += 1
        st.table(df_p)
    else: st.info("Add stocks in the Registration page.")

# --- PAGE: AI ANALYSIS ---
elif page == "AI Analysis":
    st.header("AI Report: Sell, Hold, or Buy?")
    portfolio = load_data(DB_FILE)
    if st.button("Check My Stocks"):
        results = []
        for s, info in portfolio.items():
            _, pct, price, why = get_ai_prediction_data(s)
            if price:
                action = "BUY MORE" if pct > 0.01 else "SELL" if pct < -0.02 else "HOLD"
                results.append({"Stock": s, "What to do": action, "Prediction": f"{pct:+.2%}", "Reason": why})
        df_res = pd.DataFrame(results)
        df_res.index += 1
        st.table(df_res)

# --- PAGE: GLOBAL OPPORTUNITIES ---
elif page == "Global Opportunities":
    st.header("Global Recommendations")
    # INTERNATIONAL STOCK LIST
    globals_list = ["TSLA", "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "AMD"]
    
    if st.button("Scan International Markets"):
        buys, sells = [], []
        for s in globals_list:
            _, pct, price, why = get_ai_prediction_data(s)
            if price:
                row = {"Stock": s, "Price": f"${price:,.2f}", "Reason": why}
                if pct > 0: buys.append(row)
                else: sells.append(row)
        
        st.subheader("Strong Picks to Buy")
        if buys:
            df_b = pd.DataFrame(buys)
            df_b.index += 1
            st.table(df_b)
            
        st.subheader("Stocks Showing Exit Signals (Sell)")
        if sells:
            df_s = pd.DataFrame(sells)
            df_s.index += 1
            st.table(df_s)
