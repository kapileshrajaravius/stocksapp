import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
import time
import requests
from bs4 import BeautifulSoup
from sklearn.ensemble import RandomForestClassifier

# --- INITIALIZATION ---
st.set_page_config(page_title="Global Market Intelligence", layout="wide")
DB_FILE = 'portfolio.json'

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_data(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=4)

def get_currency_sign(ticker):
    return "INR " if ticker.endswith(('.NS', '.BO')) else "$"

def get_google_finance_price(ticker):
    """Fallback: Scrapes price from Google Finance if Yahoo is blocked."""
    try:
        # Format for Google (e.g., TSLA -> NASDAQ:TSLA, TCS.NS -> NSE:TCS)
        search_ticker = ticker.replace('.NS', ':NSE').replace('.BO', ':BOM')
        url = f"https://www.google.com/finance/quote/{search_ticker}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Google's current price class
        price_element = soup.find(class_="YMlS7e")
        if price_element:
            return float(price_element.text.replace(',', '').replace('$', '').replace('₹', '').strip())
    except:
        return None
    return None

def get_ai_prediction_data(ticker):
    """Primary fetch via Yahoo with Google Fallback."""
    try:
        time.sleep(1.0) # Small delay to be polite to servers
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        
        if data.empty or len(data) < 20:
            price = get_google_finance_price(ticker)
            return ("NEUTRAL", 0.0, price, "Using Google Finance (No Trend Data)") if price else ("ERROR", 0.0, None, "No data found")
        
        curr_price = float(data['Close'].iloc[-1])
        avg_10 = data['Close'].rolling(10).mean().iloc[-1]
        
        # Simple AI Logic
        data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        model = RandomForestClassifier(n_estimators=10).fit(data[['Close']][:-1], data['Target'][:-1])
        pred = model.predict(data[['Close']].tail(1))[0]
        
        reason = "Price is above 10-day average" if curr_price > avg_10 else "Price is below 10-day average"
        return ("UP" if pred == 1 else "DOWN"), 0.02 if pred == 1 else -0.02, curr_price, reason

    except Exception:
        price = get_google_finance_price(ticker)
        if price:
            return "NEUTRAL", 0.0, price, "Yahoo Blocked. Showing Google Price."
        return "ERROR", 0.0, None, "All sources blocked"

# --- PAGE LOGIC ---
page = st.sidebar.radio("Go to:", ["Registration", "My Portfolio", "AI Analysis", "Global Scan"])

if page == "Registration":
    st.header("Register Stocks")
    t_in = st.text_input("Ticker").upper()
    s_in = st.number_input("Shares", min_value=0.0)
    p_in = st.number_input("Buy Price", min_value=0.0)
    if st.button("Add"):
        port = load_data()
        port[t_in] = {"shares": s_in, "buy_price": p_in}
        save_data(port)
        st.success(f"Added {t_in}")

elif page == "My Portfolio":
    st.header("Portfolio Overview")
    portfolio = load_data()
    total_val = 0
    display = []
    for s, info in portfolio.items():
        _, _, price, _ = get_ai_prediction_data(s)
        if price:
            val = price * info['shares']
            total_val += val
            display.append({"Stock": s, "Price": f"{get_currency_sign(s)}{price:,.2f}", "Value": f"${val:,.2f}"})
    
    st.metric("Total Value (USD Est.)", f"${total_val:,.2f}")
    if display:
        df = pd.DataFrame(display)
        df.index += 1
        st.table(df)

elif page == "AI Analysis":
    st.header("AI Predictions")
    portfolio = load_data()
    results = []
    for s in portfolio.keys():
        move, _, price, why = get_ai_prediction_data(s)
        if price:
            results.append({"Stock": s, "Prediction": move, "Reason": why})
    if results:
        df = pd.DataFrame(results)
        df.index += 1
        st.table(df)

elif page == "Global Scan":
    st.header("Market Scanner")
    for s in ["TSLA", "AAPL", "NVDA", "RELIANCE.NS"]:
        _, _, price, why = get_ai_prediction_data(s)
        if price:
            st.write(f"**{s}**: {get_currency_sign(s)}{price} — *{why}*")
