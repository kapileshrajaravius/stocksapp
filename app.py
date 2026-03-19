import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import json
import os
import time

# --- CONFIG ---
st.set_page_config(page_title="Stock Intelligence v2", layout="wide")
DB_FILE = 'portfolio.json'

def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f: return json.load(f)
    return {}

def save_data(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=4)

# --- THE DUAL-ENGINE FETCH (STOPS THE ERRORS) ---
def get_google_price(ticker):
    try:
        symbol = ticker.replace('.NS', ':NSE').replace('.BO', ':BOM')
        url = f"https://www.google.com/finance/quote/{symbol}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        price_div = soup.find("div", {"class": "YMlS7e"})
        if price_div:
            return float(price_div.text.replace('$', '').replace('₹', '').replace(',', '').strip())
    except: return None

def fetch_data(ticker):
    # Try Yahoo First
    try:
        time.sleep(1) # Delay to prevent IP blocking
        data = yf.download(ticker, period="5d", interval="1d", progress=False)
        if not data.empty:
            price = float(data['Close'].iloc[-1])
            prev = float(data['Close'].iloc[-2])
            change = (price - prev) / prev
            return price, change
    except: pass
    
    # Google Fallback if Yahoo fails
    price = get_google_price(ticker)
    return price, 0.0 # Return 0.0 change if using fallback

# --- UI ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["My Portfolio", "Registration", "AI Analysis"])

if page == "My Portfolio":
    st.header("My Portfolio")
    portfolio = load_data()
    if portfolio:
        total_value = 0
        rows = []
        for t, info in portfolio.items():
            price, _ = fetch_data(t)
            if price:
                current_val = price * info['shares']
                total_value += current_val
                rows.append({"Stock": t, "Shares": info['shares'], "Price": f"${price:,.2f}", "Total Value": f"${current_val:,.2f}"})
        
        st.metric("Total Portfolio Value", f"${total_value:,.2f}")
        df = pd.DataFrame(rows)
        df.index += 1
        st.table(df)
    else: st.info("Portfolio is empty.")

elif page == "Registration":
    st.header("Add Stock")
    with st.form("reg"):
        t_in = st.text_input("Ticker").upper()
        s_in = st.number_input("Shares", min_value=0.0)
        p_in = st.number_input("Buy Price", min_value=0.0)
        if st.form_submit_button("Save"):
            d = load_data()
            d[t_in] = {"shares": s_in, "buy_price": p_in}
            save_data(d)
            st.success(f"Saved {t_in}")

elif page == "AI Analysis":
    st.header("AI Report")
    portfolio = load_data()
    if portfolio:
        reports = []
        for t, info in portfolio.items():
            price, change = fetch_data(t)
            if price:
                action = "BUY MORE" if change > 0.01 else "SELL" if change < -0.01 else "HOLD"
                reason = "On a hot streak" if change > 0 else "Cooling down"
                reports.append({"Stock": t, "Action": action, "Reason": reason})
        df_ai = pd.DataFrame(reports)
        df_ai.index += 1
        st.table(df_ai)
