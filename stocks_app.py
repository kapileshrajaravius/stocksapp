import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
import time
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier

# --- INITIALIZATION ---
st.set_page_config(page_title="Market Intelligence Portal", layout="wide")

# Persistent Data Files
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
    return "₹" if ticker.endswith('.NS') or ticker.endswith('.BO') else "$"

def get_ai_prediction_data(ticker):
    try:
        # Rate limit protection
        time.sleep(0.5) 
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(data) < 40: return "NEUTRAL", 0.0
        
        data['MA10'] = data['Close'].rolling(10).mean()
        data['MA50'] = data['Close'].rolling(50).mean()
        data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        data = data.dropna()
        
        X = data[['MA10', 'MA50']]
        y = data['Target']
        
        model = RandomForestClassifier(n_estimators=50).fit(X[:-1], y[:-1])
        pred = model.predict(X.tail(1))[0]
        
        recent_growth = (data['Close'].iloc[-1] / data['Close'].iloc[-5]) - 1
        predicted_pct = recent_growth if pred == 1 else -abs(recent_growth)
        
        return ("UP" if pred == 1 else "DOWN"), float(predicted_pct)
    except: 
        return "ERROR", 0.0

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["Stock Registration", "My Portfolio", "AI Market Analysis", "Top 10 Picks", "Activity Logs"])

st.sidebar.divider()
st.sidebar.subheader("System Tips")
st.sidebar.info("Use .NS for India stocks (e.g., TCS.NS) or ^ for Indices (e.g., ^GSPC).")

# --- PAGE 1: REGISTRATION ---
if page == "Stock Registration":
    st.header("Stock Registration")
    col1, col2, col3 = st.columns(3)
    with col1: t_in = st.text_input("Ticker Symbol").upper()
    with col2: s_in = st.number_input("Units Owned", min_value=0.0)
    with col3: p_in = st.number_input("Buy Price (Cost Basis)", min_value=0.0)
    
    if st.button("Register Stock"):
        if t_in:
            with st.spinner("Verifying ticker..."):
                check = yf.Ticker(t_in).history(period="1d")
                if check.empty:
                    st.error(f"Ticker {t_in} not found. Check the suffix.")
                else:
                    port = load_data(DB_FILE)
                    port[t_in] = {"shares": s_in, "buy_price": p_in}
                    save_data(DB_FILE, port)
                    st.success(f"Registered {t_in}")

# --- PAGE 2: MY PORTFOLIO ---
elif page == "My Portfolio":
    st.header("Current Portfolio Holdings")
    portfolio = load_data(DB_FILE)
    if portfolio:
        df_p = pd.DataFrame.from_dict(portfolio, orient='index').reset_index()
        df_p.columns = ["Stock", "Units", "Cost"]
        edited = st.data_editor(df_p, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("Update Portfolio"):
            new_port = {row['Stock']: {"shares": row['Units'], "buy_price": row['Cost']} 
                        for _, row in edited.iterrows() if pd.notnull(row['Stock'])}
            save_data(DB_FILE, new_port)
            st.rerun()
    else:
        st.warning("No stocks registered yet.")

# --- PAGE 3: ANALYSIS ---
elif page == "AI Market Analysis":
    st.header("AI Market Analysis")
    portfolio = load_data(DB_FILE)
    if not portfolio:
        st.warning("Register stocks first to see analysis.")
    elif st.button("Generate Strategy Tables"):
        buy_more, hold, sell = [], [], []
        with st.spinner("Analyzing market patterns..."):
            for s, info in portfolio.items():
                price_data = yf.Ticker(s).history(period="1d")
                if price_data.empty: continue
                
                cur = get_currency_sign(s)
                price = float(price_data['Close'].iloc[-1])
                gain_pct = ((price - info['buy_price']) / info['buy_price']) * 100
                prediction, pred_pct = get_ai_prediction_data(s)
                
                money_change = (price * info['shares']) * pred_pct
                
                row = {
                    "Stock": s, "Price": f"{cur}{price:,.2f}", 
                    "Total Gain": f"{gain_pct:+.2f}%",
                    "Predicted Increase (%)": f"{pred_pct:+.2%}",
                    "Predicted Gain (Cash)": f"{cur}{money_change:,.2f}"
                }
                if prediction == "DOWN" or gain_pct > 30: sell.append(row)
                elif prediction == "UP" and gain_pct < 10: buy_more.append(row)
                else: hold.append(row)

        st.subheader("Accumulate (Buy)")
        st.table(pd.DataFrame(buy_more)) if buy_more else st.write("None.")
        st.subheader("Hold (Keep)")
        st.table(pd.DataFrame(hold)) if hold else st.write("None.")
        st.subheader("Liquidate (Sell)")
        st.table(pd.DataFrame(sell)) if sell else st.write("None.")

# --- PAGE 4: TOP 10 ---
elif page == "Top 10 Picks":
    st.header("Top 10 Investment Opportunities")
    top_picks = ["NVDA", "AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "META", "TCS.NS", "RELIANCE.NS", "INFY.NS"]
    if st.button("Scan Global Market"):
        recs = []
        with st.spinner("Scanning..."):
            for s in top_picks:
                prediction, pred_pct = get_ai_prediction_data(s)
                if prediction == "UP":
                    cur = get_currency_sign(s)
                    price = yf.Ticker(s).history(period="1d")['Close'].iloc[-1]
                    recs.append({"Stock": s, "Price": f"{cur}{price:,.2f}", "Est. Growth": f"{pred_pct:+.2%}"})
        st.table(pd.DataFrame(recs).head(10)) if recs else st.write("No strong buys found.")

# --- PAGE 5: LOGS ---
elif page == "Activity Logs":
    st.header("Action History")
    logs = load_data(LOG_FILE)
    if logs:
        for ts, msg in reversed(list(logs.items())):
            st.write(f"**{ts}**: {msg}")
    else: st.write("No history found.")
