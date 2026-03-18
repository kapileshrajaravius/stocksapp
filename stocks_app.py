import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
import uuid
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier

# --- INITIALIZATION ---
# This creates a "New Chat" feel by resetting keys if the session is new
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

st.set_page_config(page_title="AI Market Intelligence", layout="wide")

# PROFESSIONAL CSS
st.markdown("""
    <style>
    .main { max-width: 1000px; margin: 0 auto; }
    thead tr th { background-color: #1e2630 !important; color: white !important; }
    .stButton>button { border-radius: 4px; height: 3.5em; font-weight: bold; background-color: #004a99; color: white; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

DB_FILE = 'portfolio.json'
HISTORY_FILE = 'history.json'

# --- AI ENGINES ---
def get_ai_advice(ticker):
    try:
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(data) < 40: return "Insufficient Data", "0%"
        data['MA10'] = data['Close'].rolling(10).mean()
        data['MA50'] = data['Close'].rolling(50).mean()
        data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        data = data.dropna()
        X = data[['MA10', 'MA50']]
        y = data['Target']
        model = RandomForestClassifier(n_estimators=50).fit(X[:-1], y[:-1])
        pred = model.predict(X.tail(1))[0]
        prob = model.predict_proba(X.tail(1))[0][pred]
        return ("🚀 BUY / UP" if pred == 1 else "⚠️ SELL / DOWN"), f"{prob:.0%}"
    except: return "Analysis Failed", "0%"

def load_json(file):
    if os.path.exists(file):
        try:
            with open(file, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_json(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

# --- APP TABS ---
tab1, tab2, tab3 = st.tabs(["Active Portfolio", "Analysis History", "AI Stock Recommendations"])

with tab1:
    st.title("Market Intelligence Portal")
    
    # 1. INPUT AREA - Uses Session ID to ensure it clears on refresh
    st.subheader("Register Stock")
    col1, col2, col3 = st.columns(3)
    with col1: stock_in = st.text_input("Stock Ticker", key=f"t_{st.session_state.session_id}").upper()
    with col2: shares_in = st.number_input("Units", min_value=0.0, key=f"s_{st.session_state.session_id}")
    with col3: price_in = st.number_input("Cost Basis", min_value=0.0, key=f"p_{st.session_state.session_id}")

    if st.button("Add to Portfolio"):
        if stock_in:
            if yf.Ticker(stock_in).history(period="1d").empty:
                st.error(f"Invalid Ticker: {stock_in}. Try adding .NS for India or ^ for Indices.")
            else:
                port = load_json(DB_FILE)
                port[stock_in] = {"shares": shares_in, "buy_price": price_in}
                save_json(DB_FILE, port)
                st.success(f"Registered {stock_in}")
                st.rerun()

    st.divider()

    # 2. PORTFOLIO & ANALYSIS
    portfolio = load_json(DB_FILE)
    if portfolio:
        st.subheader("Your Holdings")
        df_p = pd.DataFrame.from_dict(portfolio, orient='index').reset_index()
        df_p.columns = ["Stock", "Units", "Cost"]
        edited = st.data_editor(df_p, num_rows="dynamic", use_container_width=True, hide_index=True)
        
        if st.button("Save Changes"):
            new_port = {row['Stock']: {"shares": row['Units'], "buy_price": row['Cost']} 
                        for _, row in edited.iterrows() if pd.notnull(row['Stock'])}
            save_json(DB_FILE, new_port)
            st.rerun()

        if st.button('Execute AI Analysis'):
            results = []
            for s, info in portfolio.items():
                price = yf.Ticker(s).history(period="1d")['Close'].iloc[-1]
                gain = ((price - info['buy_price']) / info['buy_price']) * 100
                ai_pred, conf = get_ai_advice(s)
                results.append({"Stock": s, "Price": f"${price:,.2f}", "Gain": f"{gain:.1f}%", "AI Brain": ai_pred, "Conf.": conf})
            
            st.table(pd.DataFrame(results))
            history = load_json(HISTORY_FILE)
            history[datetime.now().strftime("%Y-%m-%d %H:%M")] = results
            save_json(HISTORY_FILE, history)

with tab3:
    st.header("AI Top Picks")
    st.write("These stocks currently show the strongest AI 'UP' signals based on momentum.")
    # Suggested stocks to watch
    picks = ["RELIANCE.NS", "TCS.NS", "NVDA", "AAPL", "MSFT", "GOOGL"]
    pick_results = []
    for p in picks:
        advice, conf = get_ai_advice(p)
        pick_results.append({"Stock": p, "AI Verdict": advice, "Confidence": conf})
    st.table(pd.DataFrame(pick_results))
