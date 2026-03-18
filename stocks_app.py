import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier

# --- CONFIGURATION ---
st.set_page_config(page_title="AI Market Intelligence", layout="wide")

# CSS for large buttons and dark headers
st.markdown("""
    <style>
    .main { max-width: 1000px; margin: 0 auto; }
    thead tr th { background-color: #1e2630 !important; color: white !important; }
    .stButton>button { border-radius: 4px; height: 3.5em; font-weight: bold; background-color: #004a99; color: white; }
    </style>
    """, unsafe_allow_html=True)

DB_FILE = 'portfolio.json'
HISTORY_FILE = 'history.json'

# --- AI PREDICTION ENGINE ---
def get_ai_advice(ticker):
    try:
        data = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(data) < 50: return "Insufficient Data", "0%"
        
        # Prepare Data
        data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        data['MA10'] = data['Close'].rolling(10).mean()
        data['MA50'] = data['Close'].rolling(50).mean()
        data = data.dropna()

        # Simple Random Forest
        X = data[['MA10', 'MA50']]
        y = data['Target']
        model = RandomForestClassifier(n_estimators=50)
        model.fit(X[:-1], y[:-1])

        # Prediction for tomorrow
        pred = model.predict(X.tail(1))[0]
        prob = model.predict_proba(X.tail(1))[0][pred]
        
        advice = "🚀 BUY / UP" if pred == 1 else "⚠️ SELL / DOWN"
        return advice, f"{prob:.0%}"
    except:
        return "Analysis Failed", "0%"

# --- DATA HELPERS ---
def load_json(file):
    if os.path.exists(file):
        try:
            with open(file, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_json(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

# --- APP TABS ---
tab1, tab2 = st.tabs(["Active Portfolio", "Analysis History"])

with tab1:
    st.title("Market Intelligence Portal")
    
    st.info("""
    **Tips:** International stocks use **.NS** or **.BO**. 
    For indices (S&P 500), use **^GSPC**.
    """)
    
    # 1. INPUT AREA
    st.subheader("Add New Stock")
    col1, col2, col3 = st.columns(3)
    with col1: stock_in = st.text_input("Stock Ticker", key="ticker_input").upper()
    with col2: shares_in = st.number_input("Units", min_value=0.0, key="unit_input")
    with col3: price_in = st.number_input("Cost Basis", min_value=0.0, key="price_input")

    if st.button("Register Stock"):
        if stock_in:
            t_obj = yf.Ticker(stock_in)
            if t_obj.history(period="1d").empty:
                st.error(f"Ticker '{stock_in}' not found. Check spelling or suffix.")
            else:
                port = load_json(DB_FILE)
                port[stock_in] = {"shares": shares_in, "buy_price": price_in}
                save_json(DB_FILE, port)
                st.success(f"Added {stock_in}")
                st.rerun()

    st.divider()

    # 2. PORTFOLIO MANAGEMENT
    portfolio = load_json(DB_FILE)
    if portfolio:
        st.subheader("Current Holdings")
        df_p = pd.DataFrame.from_dict(portfolio, orient='index').reset_index()
        df_p.columns = ["Stock", "Units", "Cost"]
        
        edited = st.data_editor(df_p, num_rows="dynamic", use_container_width=True, hide_index=True)
        
        if st.button("Save Changes"):
            new_port = {row['Stock']: {"shares": row['Units'], "buy_price": row['Cost']} 
                        for _, row in edited.iterrows() if pd.notnull(row['Stock'])}
            save_json(DB_FILE, new_port)
            st.rerun()

        st.divider()

        # 3. AI EVALUATION
        if st.button('Execute AI Market Analysis'):
            results = []
            with st.spinner('AI Brain is calculating trends...'):
                for s, info in portfolio.items():
                    price = yf.Ticker(s).history(period="1d")['Close'].iloc[-1]
                    gain = ((price - info['buy_price']) / info['buy_price']) * 100
                    ai_pred, conf = get_ai_advice(s)
                    
                    results.append({
                        "Stock": s, "Price": f"${price:,.2f}", 
                        "Gain %": f"{gain:.2f}%", "AI Prediction": ai_pred, "Confidence": conf
                    })
            
            if results:
                st.subheader("AI Recommendations")
                st.table(pd.DataFrame(results))
                
                # Save to History
                history = load_json(HISTORY_FILE)
                history[datetime.now().strftime("%Y-%m-%d %H:%M")] = results
                save_json(HISTORY_FILE, history)

with tab2:
    st.title("Saved Analysis History")
    hist = load_json(HISTORY_FILE)
    if not hist:
        st.write("No history saved yet.")
    else:
        for ts in reversed(list(hist.keys())):
            with st.expander(f"Report: {ts}"):
                st.table(pd.DataFrame(hist[ts]))
        
        if st.button("Delete All History?"):
            save_json(HISTORY_FILE, {})
            st.rerun()
