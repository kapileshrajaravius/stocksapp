import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
import time

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

def get_stock_data(ticker):
    """Fetches price and trend info with rate-limit safety."""
    try:
        time.sleep(2.0) # Increased delay to stop Rate Limit errors
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        if data.empty: return None
        
        curr_price = float(data['Close'].iloc[-1])
        avg_10 = data['Close'].rolling(10).mean().iloc[-1]
        avg_50 = data['Close'].rolling(50).mean().iloc[-1]
        
        # Simple Logic for "The Why"
        reasons = []
        if curr_price > avg_10: reasons.append("Price is on a hot streak")
        else: reasons.append("Price is cooling down lately")
        
        if avg_10 > avg_50: reasons.append("Overall trend is pointing up")
        else: reasons.append("General trend is slowing down")
        
        # Prediction logic
        growth = (curr_price / data['Close'].iloc[-10]) - 1
        return {"price": curr_price, "growth": growth, "reason": " & ".join(reasons)}
    except:
        return None

# --- SIDEBAR ---
st.sidebar.title("Menu")
page = st.sidebar.radio("Go to:", ["Registration", "My Portfolio", "AI Analysis", "Global Opportunities"])
st.sidebar.divider()
st.sidebar.subheader("Quick Tips")
st.sidebar.text("1. International stocks work best.")
st.sidebar.text("2. Tables start at 1 for clarity.")

# --- PAGE: PORTFOLIO & TOTAL VALUE ---
if page == "My Portfolio":
    st.header("Current Holdings")
    portfolio = load_data()
    
    if portfolio:
        # Calculate Total Value Header
        total_value = 0
        display_list = []
        
        with st.spinner("Calculating total value..."):
            for s, info in portfolio.items():
                data = get_stock_data(s)
                if data:
                    current_val = data['price'] * info['shares']
                    total_value += current_val
                    display_list.append({
                        "Stock": s,
                        "Units": info['shares'],
                        "Current Price": f"${data['price']:,.2f}",
                        "Current Value": f"${current_val:,.2f}"
                    })

        # TOTAL VALUE DISPLAY
        st.metric(label="Total Portfolio Value (USD)", value=f"${total_value:,.2f}")
        
        df = pd.DataFrame(display_list)
        df.index += 1
        st.table(df)
    else:
        st.info("No stocks registered yet.")

# --- PAGE: REGISTRATION ---
elif page == "Registration":
    st.header("Add International Stocks")
    col1, col2, col3 = st.columns(3)
    with col1: t_in = st.text_input("Ticker (e.g. TSLA, NVDA)").upper()
    with col2: s_in = st.number_input("Shares", min_value=0.0)
    with col3: p_in = st.number_input("Buy Price", min_value=0.0)
    
    if st.button("Register Stock"):
        if t_in:
            port = load_data()
            port[t_in] = {"shares": s_in, "buy_price": p_in}
            save_data(port)
            st.success(f"Successfully registered {t_in}")

# --- PAGE: AI ANALYSIS ---
elif page == "AI Analysis":
    st.header("AI Report: Simplified Why")
    portfolio = load_data()
    if st.button("Analyze My Portfolio"):
        results = []
        for s, info in portfolio.items():
            data = get_stock_data(s)
            if data:
                action = "BUY MORE" if data['growth'] > 0 else "SELL" if data['growth'] < -0.02 else "HOLD"
                results.append({
                    "Stock": s,
                    "Action": action,
                    "Prediction": f"{data['growth']:+.2%}",
                    "Simplified Reason": data['reason']
                })
        df = pd.DataFrame(results)
        df.index += 1
        st.table(df)

# --- PAGE: GLOBAL OPPORTUNITIES ---
elif page == "Global Opportunities":
    st.header("Global Market Picks")
    scan_list = ["TSLA", "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN"]
    
    if st.button("Scan Markets"):
        buys, sells = [], []
        for s in scan_list:
            data = get_stock_data(s)
            if data:
                row = {"Stock": s, "Price": f"${data['price']:,.2f}", "Why": data['reason']}
                if data['growth'] > 0:
                    row["When to Sell"] = "Sell if the hot streak ends"
                    buys.append(row)
                else:
                    sells.append(row)
        
        st.subheader("Strong Picks to Buy")
        if buys:
            df_b = pd.DataFrame(buys)
            df_b.index += 1
            st.table(df_b)
            
        st.subheader("Exit Signals (Time to Sell)")
        if sells:
            df_s = pd.DataFrame(sells)
            df_s.index += 1
            st.table(df_s)
