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

# --- DATA HELPERS ---
def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_data(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

def get_currency_sign(ticker):
    if ticker.endswith('.NS') or ticker.endswith('.BO'):
        return "INR "
    return "$"

def get_google_finance_price(ticker):
    """Backup: Scrapes Google Finance if Yahoo is rate-limited"""
    try:
        url = f"https://www.google.com/search?q=google+finance+{ticker}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        # This looks for the common price div classes in Google Search
        price_text = soup.find('div', {'class': 'BNeawe iBp4i AP7Wnd'}).text
        return float(price_text.split()[0].replace(',', ''))
    except:
        return None

def get_ai_prediction_data(ticker):
    """Calculates predictions with Rate Limit Protection and Backup Logic"""
    for attempt in range(2):
        try:
            time.sleep(1.5) 
            data = yf.download(ticker, period="1y", interval="1d", progress=False)
            
            if data.empty or len(data) < 40:
                return "NEUTRAL", 0.0, None
            
            # AI Logic
            data['MA10'] = data['Close'].rolling(10).mean()
            data['MA50'] = data['Close'].rolling(50).mean()
            data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
            data = data.dropna()
            
            X = data[['MA10', 'MA50']]
            y = data['Target']
            
            model = RandomForestClassifier(n_estimators=50).fit(X[:-1], y[:-1])
            pred = model.predict(X.tail(1))[0]
            
            # Estimated growth based on 10-day trend
            recent_growth = (data['Close'].iloc[-1] / data['Close'].iloc[-10]) - 1
            predicted_pct = recent_growth if pred == 1 else -abs(recent_growth)
            
            return ("UP" if pred == 1 else "DOWN"), float(predicted_pct), float(data['Close'].iloc[-1])
            
        except Exception as e:
            if "Rate" in str(e):
                # Try Google Finance Backup for price if Yahoo times out
                price = get_google_finance_price(ticker)
                if price:
                    return "NEUTRAL", 0.0, price
                time.sleep(3)
                continue
            return "ERROR", 0.0, None
    return "ERROR", 0.0, None

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", [
    "Stock Registration", 
    "My Portfolio", 
    "AI Market Analysis", 
    "New Opportunities", 
    "Activity Logs"
])

st.sidebar.divider()
st.sidebar.subheader("System Tips")
st.sidebar.text("1. Use .NS for India stocks.")
st.sidebar.text("2. Ensure ticker is correct.")
st.sidebar.text("3. AI filters for positive growth.")
st.sidebar.text("4. Backup data active.")

# --- PAGE: REGISTRATION ---
if page == "Stock Registration":
    st.header("Stock Registration")
    col1, col2, col3 = st.columns(3)
    with col1: t_in = st.text_input("Ticker Symbol").upper()
    with col2: s_in = st.number_input("Units Owned", min_value=0.0)
    with col3: p_in = st.number_input("Purchase Price", min_value=0.0)
    
    if st.button("Register Stock"):
        if t_in:
            with st.spinner("Verifying..."):
                _, _, price = get_ai_prediction_data(t_in)
                if price is None:
                    st.error("Ticker not found or service unavailable.")
                else:
                    port = load_data(DB_FILE)
                    port[t_in] = {"shares": s_in, "buy_price": p_in}
                    save_data(DB_FILE, port)
                    st.success(f"Registered {t_in}")

# --- PAGE: MY PORTFOLIO ---
elif page == "My Portfolio":
    st.header("My Portfolio")
    portfolio = load_data(DB_FILE)
    if portfolio:
        df_p = pd.DataFrame.from_dict(portfolio, orient='index').reset_index()
        df_p.columns = ["Stock", "Units", "Cost"]
        edited = st.data_editor(df_p, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("Save Changes"):
            new_port = {row['Stock']: {"shares": row['Units'], "buy_price": row['Cost']} 
                        for _, row in edited.iterrows() if pd.notnull(row['Stock'])}
            save_data(DB_FILE, new_port)
            st.rerun()
    else: st.info("No stocks registered.")

# --- PAGE: AI ANALYSIS ---
elif page == "AI Market Analysis":
    st.header("AI Analysis Report")
    portfolio = load_data(DB_FILE)
    if not portfolio: st.warning("Register stocks first.")
    elif st.button("Run AI Analysis"):
        results = []
        progress = st.progress(0)
        for i, (s, info) in enumerate(portfolio.items()):
            cur_sign = get_currency_sign(s)
            _, pred_pct, price = get_ai_prediction_data(s)
            if price:
                gain_pct = ((price - info['buy_price']) / info['buy_price']) * 100
                money_gain = (price * info['shares']) * pred_pct
                results.append({
                    "Stock": s, "Current Price": f"{cur_sign}{price:,.2f}", 
                    "Total Gain": f"{gain_pct:+.2f}%", "AI Growth Prediction": f"{pred_pct:+.2%}",
                    "Predicted Money Gain": f"{cur_sign}{money_gain:,.2f}"
                })
            progress.progress((i+1)/len(portfolio))
        st.table(pd.DataFrame(results))

# --- PAGE: NEW OPPORTUNITIES ---
elif page == "New Opportunities":
    st.header("Market Recommendations")
    # EXPANDED BIG STOCKS LIST
    scan_list = [
        "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "BRK-B", "V", "JPM",
        "WMT", "MA", "PG", "UNH", "HD", "TCS.NS", "RELIANCE.NS", "INFY.NS", "HDFCBANK.NS",
        "ICICIBANK.NS", "BHARTIARTL.NS", "SBIN.NS", "ITC.NS", "LICI.NS", "ASIANPAINT.NS"
    ]
    
    if st.button("Scan Big Stocks"):
        risky, slow = [], []
        progress = st.progress(0)
        for i, s in enumerate(scan_list):
            pred, pred_pct, price = get_ai_prediction_data(s)
            if pred == "UP" and pred_pct > 0 and price:
                cur_sign = get_currency_sign(s)
                row = {"Stock": s, "Price": f"{cur_sign}{price:,.2f}", "Predicted Growth": f"{pred_pct:+.2%}"}
                if pred_pct > 0.05: risky.append(row)
                else: slow.append(row)
            progress.progress((i+1)/len(scan_list))
        
        st.subheader("High Risk / High Reward")
        if risky: st.table(pd.DataFrame(risky))
        else: st.text("No high risk opportunities found.")
        
        st.subheader("Slow and Steady Growth")
        if slow: st.table(pd.DataFrame(slow))
        else: st.text("No slow growth opportunities found.")

# --- PAGE: LOGS ---
elif page == "Activity Logs":
    st.header("Action History")
    if st.button("Mark Actions as Completed"):
        logs = load_data(LOG_FILE)
        logs[datetime.now().strftime("%Y-%m-%d %H:%M")] = "User completed recommendations."
        save_data(LOG_FILE, logs)
        st.success("Log Updated.")
    
    logs = load_data(LOG_FILE)
    if logs:
        for ts, msg in reversed(list(logs.items())):
            st.text(f"{ts}: {msg}")
    if st.button("Clear Logs"):
        save_data(LOG_FILE, {})
        st.rerun()
