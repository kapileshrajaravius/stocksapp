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

# --- HELPERS ---
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
    """Fallback: Scrapes current price from Google Finance."""
    try:
        # Format for Google Finance (e.g., NSE:TCS or NASDAQ:TSLA)
        search_ticker = ticker.replace('.NS', ':NSE').replace('.BO', ':BOM')
        url = f"https://www.google.com/finance/quote/{search_ticker}"
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Find the price class (this changes occasionally, but is the current standard)
        price_class = soup.find(class_="YMlS7e") 
        if price_class:
            return float(price_class.text.replace(',', '').replace('$', '').replace('₹', '').strip())
        return None
    except:
        return None

def get_ai_prediction_data(ticker):
    """Primary: Yahoo Finance. Fallback: Google Finance Price."""
    try:
        time.sleep(1.5) # Basic politeness delay
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        
        if data.empty or len(data) < 50:
            # TRY GOOGLE FALLBACK FOR PRICE ONLY
            price = get_google_finance_price(ticker)
            if price:
                return "NEUTRAL", 0.0, price, "Using Google Finance (Trends unavailable)"
            return "ERROR", 0.0, None, "No data found on Yahoo or Google"
        
        # Technical Logic
        curr_price = float(data['Close'].iloc[-1])
        avg_10 = data['Close'].rolling(10).mean().iloc[-1]
        avg_50 = data['Close'].rolling(50).mean().iloc[-1]
        
        reasons = []
        if curr_price > avg_10: reasons.append("Price is on a hot streak")
        else: reasons.append("Price is cooling down lately")
        
        if avg_10 > avg_50: reasons.append("Overall trend is pointing up")
        else: reasons.append("General trend is slowing down")
        
        # Simple AI Check
        data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        data = data.dropna()
        model = RandomForestClassifier(n_estimators=50).fit(data[['Close']][:-1], data['Target'][:-1])
        pred = model.predict(data[['Close']].tail(1))[0]
        
        recent_growth = (curr_price / data['Close'].iloc[-10]) - 1
        predicted_pct = recent_growth if pred == 1 else -abs(recent_growth)
        
        return ("UP" if pred == 1 else "DOWN"), float(predicted_pct), curr_price, " & ".join(reasons)
    except Exception as e:
        # FINAL ATTEMPT AT GOOGLE PRICE
        price = get_google_finance_price(ticker)
        if price:
            return "NEUTRAL", 0.0, price, "Yahoo Rate Limit hit. Showing Google Price."
        return "ERROR", 0.0, None, f"Connection Issue: {str(e)}"

# --- SIDEBAR ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["Registration", "My Portfolio", "AI Analysis Report", "Global Opportunities"])
st.sidebar.divider()
st.sidebar.subheader("System Tips")
st.sidebar.text("1. Uses Google fallback if Yahoo fails.")
st.sidebar.text("2. 1.5s delay added between stocks.")

# --- PAGES ---
if page == "Registration":
    st.header("Register New Stocks")
    col1, col2, col3 = st.columns(3)
    with col1: t_in = st.text_input("Ticker (e.g. AAPL, TCS.NS)").upper()
    with col2: s_in = st.number_input("Units", min_value=0.0)
    with col3: p_in = st.number_input("Purchase Price", min_value=0.0)
    
    if st.button("Add Stock"):
        if t_in:
            with st.spinner("Checking market data..."):
                _, _, price, _ = get_ai_prediction_data(t_in)
                if price:
                    port = load_data()
                    port[t_in] = {"shares": s_in, "buy_price": p_in}
                    save_data(port)
                    st.success(f"Added {t_in} at current price {get_currency_sign(t_in)}{price:,.2f}")
                else: st.error("Could not find ticker on Yahoo or Google Finance.")

elif page == "My Portfolio":
    st.header("Current Portfolio Status")
    portfolio = load_data()
    if portfolio:
        total_val = 0
        display_list = []
        for s, info in portfolio.items():
            _, _, price, _ = get_ai_prediction_data(s)
            if price:
                cur = get_currency_sign(s)
                val = price * info['shares']
                total_val += val
                display_list.append({"Stock": s, "Units": info['shares'], "Price": f"{cur}{price:,.2f}", "Value": f"{cur}{val:,.2f}"})
        
        st.metric("Total Portfolio Value", f"${total_val:,.2f} (USD Equivalent)")
        df = pd.DataFrame(display_list)
        df.index += 1
        st.table(df)
    else: st.info("No holdings found.")

elif page == "AI Analysis Report":
    st.header("Investment Intelligence")
    portfolio = load_data()
    if st.button("Run Portfolio Analysis"):
        results = []
        for s, info in portfolio.items():
            _, pct, price, why = get_ai_prediction_data(s)
            if price:
                action = "BUY MORE" if pct > 0.01 else "SELL" if pct < -0.01 else "HOLD"
                results.append({"Stock": s, "Action": action, "Prediction": f"{pct:+.2%}", "Reason": why})
        df = pd.DataFrame(results)
        df.index += 1
        st.table(df)

elif page == "Global Opportunities":
    st.header("Market Scanner")
    scan_list = ["TSLA", "AAPL", "NVDA", "RELIANCE.NS", "TCS.NS", "MSFT", "GOOGL"]
    if st.button("Scan Top Opportunities"):
        buys, sells = [], []
        for s in scan_list:
            _, pct, price, why = get_ai_prediction_data(s)
            if price:
                cur = get_currency_sign(s)
                row = {"Stock": s, "Price": f"{cur}{price:,.2f}", "Reason": why}
                if pct > 0: buys.append(row)
                else: sells.append(row)
        
        st.subheader("Strong Picks")
        if buys: 
            df_b = pd.DataFrame(buys)
            df_b.index += 1
            st.table(df_b)
        st.subheader("Exit Signals")
        if sells: 
            df_s = pd.DataFrame(sells)
            df_s.index += 1
            st.table(df_s)
