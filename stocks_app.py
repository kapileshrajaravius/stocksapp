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

# --- THE "BYPASS" SESSION ---
# This makes your app look like a regular Chrome browser to Yahoo/Google
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
})

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_data(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=4)

def get_currency_sign(ticker):
    return "₹" if ticker.endswith(('.NS', '.BO')) else "$"

def get_google_finance_price(ticker):
    """SCRAPER FALLBACK: Gets price from Google if Yahoo is blocked."""
    try:
        # Convert tickers for Google (e.g. TCS.NS -> NSE:TCS)
        g_ticker = ticker.replace('.NS', ':NSE').replace('.BO', ':BOM')
        url = f"https://www.google.com/finance/quote/{g_ticker}"
        response = session.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Google's live price class (as of 2026)
        price_tag = soup.find(class_="YMlS7e")
        if price_tag:
            return float(price_tag.text.replace(',', '').replace('$', '').replace('₹', '').strip())
    except:
        return None
    return None

def get_market_data(ticker):
    """The master fetcher: Tries Yahoo, then Google."""
    try:
        # 1.5s delay to prevent further IP flagging
        time.sleep(1.5) 
        
        # Try Yahoo first (Pass the 'session' to bypass blocks)
        df = yf.download(ticker, period="1y", interval="1d", progress=False, session=session)
        
        if df.empty or len(df) < 10:
            raise ValueError("Yahoo Returned Empty")

        curr_price = float(df['Close'].iloc[-1])
        # AI/Trend calculation
        avg_10 = df['Close'].rolling(10).mean().iloc[-1]
        change = (curr_price / df['Close'].iloc[-10]) - 1
        
        reason = "Trending Up" if curr_price > avg_10 else "Cooling Down"
        return curr_price, change, reason, "Yahoo Live"

    except Exception:
        # 2. GOOGLE FALLBACK if Yahoo fails
        price = get_google_finance_price(ticker)
        if price:
            return price, 0.0, "Trend Data Unavailable", "Google Fallback"
        return None, None, None, "ERROR: Both Blocked"

# --- SIDEBAR ---
page = st.sidebar.radio("Navigation", ["Registration", "My Portfolio", "AI Analysis"])

# --- PAGE: MY PORTFOLIO (Total Value Included) ---
if page == "My Portfolio":
    st.header("Portfolio & Total Value")
    portfolio = load_data()
    
    if portfolio:
        total_portfolio_usd = 0
        table_data = []
        
        with st.spinner("Fetching live data (including Google fallback)..."):
            for ticker, info in portfolio.items():
                price, change, reason, source = get_market_data(ticker)
                
                if price:
                    current_val = price * info['shares']
                    total_portfolio_usd += current_val
                    
                    table_data.append({
                        "Ticker": ticker,
                        "Shares": info['shares'],
                        "Live Price": f"{get_currency_sign(ticker)}{price:,.2f}",
                        "Total Value": f"{get_currency_sign(ticker)}{current_val:,.2f}",
                        "Data Source": source
                    })
        
        # The "Total Portfolio Value" display
        st.metric(label="Estimated Portfolio Total (USD/Local Combined)", value=f"${total_portfolio_usd:,.2f}")
        
        if table_data:
            df = pd.DataFrame(table_data)
            df.index += 1 # Make table start at 1
            st.table(df)
    else:
        st.info("No stocks registered. Go to Registration to add some!")

# --- PAGE: REGISTRATION ---
elif page == "Registration":
    st.header("Add Assets")
    c1, c2, c3 = st.columns(3)
    with c1: t_in = st.text_input("Ticker (e.g. TSLA or TCS.NS)").upper()
    with c2: s_in = st.number_input("Shares", min_value=0.1)
    with c3: p_in = st.number_input("Buy Price", min_value=0.1)
    
    if st.button("Add to Portfolio"):
        if t_in:
            port = load_data()
            port[t_in] = {"shares": s_in, "buy_price": p_in}
            save_data(port)
            st.success(f"Registered {t_in} successfully!")

# --- PAGE: AI ANALYSIS ---
elif page == "AI Analysis":
    st.header("Simplified AI Report")
    portfolio = load_data()
    if st.button("Generate Recommendations"):
        results = []
        for ticker in portfolio.keys():
            price, change, reason, source = get_market_data(ticker)
            if price:
                action = "BUY" if change > 0 else "HOLD" if change > -0.02 else "SELL"
                results.append({
                    "Stock": ticker,
                    "Recommendation": action,
                    "Why?": reason,
                    "10D Trend": f"{change:+.2%}"
                })
        if results:
            df_ai = pd.DataFrame(results)
            df_ai.index += 1
            st.table(df_ai)
