import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
import time
import requests
from bs4 import BeautifulSoup
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
    return "INR " if ticker.endswith('.NS') or ticker.endswith('.BO') else "$"

def get_ai_prediction_data(ticker):
    """Calculates predictions and provides the 'Why' behind the signal"""
    try:
        time.sleep(1.5) 
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        if data.empty or len(data) < 50: return "NEUTRAL", 0.0, None, "Insufficient Data"
        
        # Technical Inputs (Features)
        data['MA10'] = data['Close'].rolling(10).mean()
        data['MA50'] = data['Close'].rolling(50).mean()
        curr_price = float(data['Close'].iloc[-1])
        ma10 = float(data['MA10'].iloc[-1])
        ma50 = float(data['MA50'].iloc[-1])
        
        # Reason Logic
        reasons = []
        if curr_price > ma10: reasons.append("Price above 10-day average (Short-term strength)")
        else: reasons.append("Price below 10-day average (Short-term weakness)")
        
        if ma10 > ma50: reasons.append("Fast average above slow average (Bullish trend)")
        else: reasons.append("Fast average below slow average (Bearish trend)")
        
        # AI Training
        data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        data = data.dropna()
        model = RandomForestClassifier(n_estimators=50).fit(data[['MA10', 'MA50']][:-1], data['Target'][:-1])
        pred = model.predict(data[['MA10', 'MA50']].tail(1))[0]
        
        recent_growth = (curr_price / data['Close'].iloc[-10]) - 1
        predicted_pct = recent_growth if pred == 1 else -abs(recent_growth)
        
        return ("UP" if pred == 1 else "DOWN"), float(predicted_pct), curr_price, " & ".join(reasons)
    except:
        return "ERROR", 0.0, None, "Connection Issue"

# --- SIDEBAR ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["Stock Registration", "My Portfolio", "AI Market Analysis", "New Opportunities"])
st.sidebar.divider()
st.sidebar.subheader("System Tips")
st.sidebar.text("1. Use .NS for India stocks.")
st.sidebar.text("2. AI scans 10-day & 50-day trends.")

# --- PAGE: MY PORTFOLIO ---
if page == "My Portfolio":
    st.header("My Portfolio")
    portfolio = load_data(DB_FILE)
    if portfolio:
        df_p = pd.DataFrame.from_dict(portfolio, orient='index').reset_index()
        df_p.columns = ["Stock", "Units", "Cost"]
        df_p.index += 1
        st.data_editor(df_p, use_container_width=True)
    else: st.info("No stocks registered.")

# --- PAGE: AI ANALYSIS ---
elif page == "AI Market Analysis":
    st.header("AI Analysis & Reasons")
    portfolio = load_data(DB_FILE)
    if st.button("Analyze Holdings"):
        results = []
        for s, info in portfolio.items():
            _, pct, price, why = get_ai_prediction_data(s)
            if price:
                action = "BUY MORE" if pct > 0.01 else "SELL" if pct < -0.02 else "HOLD"
                results.append({"Stock": s, "Action": action, "Prediction": f"{pct:+.2%}", "Reason": why})
        df_res = pd.DataFrame(results)
        df_res.index += 1
        st.table(df_res)

# --- PAGE: NEW OPPORTUNITIES ---
elif page == "New Opportunities":
    st.header("Opportunities & Exit Signals")
    scan_list = ["NVDA", "AAPL", "TSLA", "TCS.NS", "RELIANCE.NS", "MSFT", "GOOGL"]
    
    if st.button("Scan Market"):
        buys, sells = [], []
        for s in scan_list:
            pred, pct, price, why = get_ai_prediction_data(s)
            cur = get_currency_sign(s)
            if price:
                row = {"Stock": s, "Price": f"{cur}{price:,.2f}", "Reason": why}
                # BUY: Growth > 0 and Bullish Trend
                if pct > 0: buys.append(row)
                # SELL: Growth < 0 or Bearish Trend
                elif pct < -0.01: sells.append(row)
        
        st.subheader("Stocks to Buy/Watch")
        if buys: 
            df_b = pd.DataFrame(buys)
            df_b.index += 1
            st.table(df_b)
            
        st.subheader("Exit Signals (Time to Sell)")
        if sells: 
            df_s = pd.DataFrame(sells)
            df_s.index += 1
            st.table(df_s)
