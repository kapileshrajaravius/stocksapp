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

# --- DATA HELPERS ---
def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_data(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

def get_ai_prediction_data(ticker):
    """Calculates predictions with simple reasons and rate-limit protection"""
    try:
        time.sleep(1.5) 
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        if data.empty or len(data) < 50:
            return "NEUTRAL", 0.0, None, "Not enough data yet"
        
        price = float(data['Close'].iloc[-1])
        avg_10 = data['Close'].rolling(10).mean().iloc[-1]
        avg_50 = data['Close'].rolling(50).mean().iloc[-1]
        
        # Simplified Reason Logic
        reasons = []
        if price > avg_10: reasons.append("Price is on a short-term hot streak")
        else: reasons.append("Price is cooling down lately")
        
        if avg_10 > avg_50: reasons.append("The overall trend is pointing up")
        else: reasons.append("The general trend is slowing down")
        
        # AI Training
        data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        data = data.dropna()
        model = RandomForestClassifier(n_estimators=50).fit(data[['Close']][:-1], data['Target'][:-1])
        pred = model.predict(data[['Close']].tail(1))[0]
        
        recent_growth = (price / data['Close'].iloc[-10]) - 1
        predicted_pct = recent_growth if pred == 1 else -abs(recent_growth)
        
        return ("UP" if pred == 1 else "DOWN"), float(predicted_pct), price, " & ".join(reasons)
    except:
        return "ERROR", 0.0, None, "Connection issue"

# --- SIDEBAR ---
st.sidebar.title("Menu")
page = st.sidebar.radio("Go to:", ["Registration", "My Portfolio", "AI Analysis Report", "Global Opportunities"])
st.sidebar.divider()
st.sidebar.subheader("System Tips")
st.sidebar.text("1. Works for all International stocks.")
st.sidebar.text("2. AI looks at 10-day & 50-day trends.")
st.sidebar.text("3. Table starts at 1 for easy reading.")

# --- PAGE: REGISTRATION ---
if page == "Registration":
    st.header("Register New Stocks")
    col1, col2, col3 = st.columns(3)
    with col1: t_in = st.text_input("Stock Ticker (e.g., TSLA, NVDA)").upper()
    with col2: s_in = st.number_input("Units Owned", min_value=0.0)
    with col3: p_in = st.number_input("Purchase Price", min_value=0.0)
    
    if st.button("Add to Portfolio"):
        if t_in:
            with st.spinner("Checking ticker..."):
                _, _, price, _ = get_ai_prediction_data(t_in)
                if price:
                    port = load_data(DB_FILE)
                    port[t_in] = {"shares": s_in, "buy_price": p_in}
                    save_data(DB_FILE, port)
                    st.success(f"Added {t_in} to your list.")
                else: st.error("Could not find that stock.")

# --- PAGE: MY PORTFOLIO ---
elif page == "My Portfolio":
    st.header("Current Holdings")
    portfolio = load_data(DB_FILE)
    if portfolio:
        df_p = pd.DataFrame.from_dict(portfolio, orient='index').reset_index()
        df_p.columns = ["Ticker", "Units", "Cost"]
        df_p.index += 1
        st.table(df_p)
    else: st.info("Your portfolio is empty.")

# --- PAGE: AI ANALYSIS REPORT ---
elif page == "AI Analysis Report":
    st.header("AI Analysis: What to do now")
    portfolio = load_data(DB_FILE)
    if not portfolio: st.warning("Add stocks first.")
    elif st.button("Generate Report"):
        results = []
        for s, info in portfolio.items():
            _, pct, price, why = get_ai_prediction_data(s)
            if price:
                action = "BUY MORE" if pct > 0.01 else "SELL" if pct < -0.02 else "HOLD"
                money_change = (price * info['shares']) * pct
                results.append({
                    "Stock": s, 
                    "Action": action, 
                    "Predicted Gain": f"${money_change:,.2f}",
                    "AI Prediction": f"{pct:+.2%}", 
                    "Reason": why
                })
        df_res = pd.DataFrame(results)
        df_res.index += 1
        st.table(df_res)

# --- PAGE: GLOBAL OPPORTUNITIES ---
elif page == "Global Opportunities":
    st.header("Global Market Opportunities")
    scan_list = ["TSLA", "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "AMD"]
    
    if st.button("Scan International Markets"):
        buys, sells = [], []
        for s in scan_list:
            _, pct, price, why = get_ai_prediction_data(s)
            if price:
                row = {"Stock": s, "Current Price": f"${price:,.2f}", "Reason": why}
                if pct > 0: 
                    row["When to Sell"] = "Sell if price drops below the 10-day average."
                    buys.append(row)
                else: 
                    row["Status"] = "Already losing momentum"
                    sells.append(row)
        
        st.subheader("Strong Picks to Buy")
        if buys:
            df_b = pd.DataFrame(buys)
            df_b.index += 1
            st.table(df_b)
            
        st.subheader("Exit Signals (When to Sell)")
        if sells:
            df_s = pd.DataFrame(sells)
            df_s.index += 1
            st.table(df_s)
