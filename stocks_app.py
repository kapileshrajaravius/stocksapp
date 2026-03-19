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
st.set_page_config(page_title="Global Market Intelligence", layout="wide")

DB_FILE = 'portfolio.json'

# --- DATA HELPERS ---
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_data(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=4)

def get_currency_sign(ticker):
    """Detects currency based on exchange suffix."""
    if ticker.endswith('.NS') or ticker.endswith('.BO'):
        return "INR "
    return "$"

def get_google_finance_price(ticker):
    """Fallback: Scrapes current price from Google Finance if Yahoo is blocked."""
    try:
        # Standardize ticker for Google (e.g., AAPL -> NASDAQ:AAPL)
        search_ticker = ticker.replace('.NS', ':NSE').replace('.BO', ':BOM')
        url = f"https://www.google.com/finance/quote/{search_ticker}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Standard Google Finance price class
        price_element = soup.find(class_="YMlS7e")
        if price_element:
            return float(price_element.text.replace(',', '').replace('$', '').replace('₹', '').strip())
        return None
    except:
        return None

def get_ai_prediction_data(ticker):
    """Fetches data from Yahoo with a Google fallback for prices."""
    try:
        # 2-second delay to prevent Yahoo IP blocking
        time.sleep(2.0) 
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        
        if data.empty or len(data) < 50:
            price = get_google_finance_price(ticker)
            if price:
                return "NEUTRAL", 0.0, price, "Using Google Finance (Trends unavailable)"
            return "ERROR", 0.0, None, "No data found"
        
        curr_price = float(data['Close'].iloc[-1])
        avg_10 = data['Close'].rolling(10).mean().iloc[-1]
        avg_50 = data['Close'].rolling(50).mean().iloc[-1]
        
        # Simplified Reasons
        reasons = []
        if curr_price > avg_10: reasons.append("Price is on a short-term hot streak")
        else: reasons.append("Price is cooling down lately")
        
        if avg_10 > avg_50: reasons.append("The overall trend is pointing up")
        else: reasons.append("The general trend is slowing down")
        
        # AI Logic
        data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        data = data.dropna()
        model = RandomForestClassifier(n_estimators=50).fit(data[['Close']][:-1], data['Target'][:-1])
        pred = model.predict(data[['Close']].tail(1))[0]
        
        recent_growth = (curr_price / data['Close'].iloc[-10]) - 1
        predicted_pct = recent_growth if pred == 1 else -abs(recent_growth)
        
        return ("UP" if pred == 1 else "DOWN"), float(predicted_pct), curr_price, " & ".join(reasons)
    except:
        price = get_google_finance_price(ticker)
        if price:
            return "NEUTRAL", 0.0, price, "Yahoo Rate Limit hit. Showing Google Price."
        return "ERROR", 0.0, None, "Connection issue"

# --- SIDEBAR MENU ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["Registration", "My Portfolio", "AI Analysis Report", "Global Opportunities"])
st.sidebar.divider()
st.sidebar.subheader("System Tips")
st.sidebar.text("1. Works for all International stocks.")
st.sidebar.text("2. Tables start at 1 for clarity.")
st.sidebar.text("3. Using Google Fallback system.")

# --- PAGE: REGISTRATION ---
if page == "Registration":
    st.header("Register New Stocks")
    col1, col2, col3 = st.columns(3)
    with col1: t_in = st.text_input("Stock Ticker (e.g. TSLA, NVDA)").upper()
    with col2: s_in = st.number_input("Units Owned", min_value=0.0)
    with col3: p_in = st.number_input("Purchase Price", min_value=0.0)
    
    if st.button("Add to Portfolio"):
        if t_in:
            with st.spinner("Finding stock..."):
                _, _, price, _ = get_ai_prediction_data(t_in)
                if price:
                    port = load_data()
                    port[t_in] = {"shares": s_in, "buy_price": p_in}
                    save_data(port)
                    st.success(f"Added {t_in} successfully.")
                else:
                    st.error("Stock not found. Try a different ticker.")

# --- PAGE: MY PORTFOLIO ---
elif page == "My Portfolio":
    st.header("Portfolio Overview")
    portfolio = load_data()
    if portfolio:
        total_val = 0
        display_list = []
        with st.spinner("Updating live prices..."):
            for s, info in portfolio.items():
                _, _, price, _ = get_ai_prediction_data(s)
                if price:
                    val = price * info['shares']
                    total_val += val
                    display_list.append({
                        "Stock": s, 
                        "Units": info['shares'], 
                        "Live Price": f"{get_currency_sign(s)}{price:,.2f}", 
                        "Value": f"{get_currency_sign(s)}{val:,.2f}"
                    })
        
        # TOTAL VALUE DISPLAY
        st.metric("Total Portfolio Value", f"${total_val:,.2f} (USD Est.)")
        
        df = pd.DataFrame(display_list)
        df.index += 1
        st.table(df)
    else:
        st.info("No stocks registered.")

# --- PAGE: AI ANALYSIS REPORT ---
elif page == "AI Analysis Report":
    st.header("AI Recommendations")
    portfolio = load_data()
    if st.button("Run Detailed Analysis"):
        results = []
        for s, info in portfolio.items():
            _, pct, price, why = get_ai_prediction_data(s)
            if price:
                action = "BUY MORE" if pct > 0.01 else "SELL" if pct < -0.01 else "HOLD"
                money_gain = (price * info['shares']) * pct
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
    st.header("Global Market Scanner")
    scan_list = ["TSLA", "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "NFLX"]
    
    if st.button("Scan International Markets"):
        buys, sells = [], []
        for s in scan_list:
            _, pct, price, why = get_ai_prediction_data(s)
            if price:
                row = {"Stock": s, "Price": f"${price:,.2f}", "Reason": why}
                if pct > 0:
                    row["When to Sell"] = "Sell if price drops below 10-day average"
                    buys.append(row)
                else:
                    sells.append(row)
        
        st.subheader("Strong Picks (Buy)")
        if buys:
            df_b = pd.DataFrame(buys)
            df_b.index += 1
            st.table(df_b)
            
        st.subheader("Exit Signals (Sell)")
        if sells:
            df_s = pd.DataFrame(sells)
            df_s.index += 1
            st.table(df_s)
