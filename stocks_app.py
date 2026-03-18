import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
import uuid
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier

# --- INITIALIZATION ---
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

st.set_page_config(page_title="Market Intelligence Portal", layout="wide")

# Professional CSS
st.markdown("""
    <style>
    thead tr th { background-color: #1e2630 !important; color: white !important; }
    .stButton>button { border-radius: 4px; height: 3em; background-color: #004a99; color: white; width: 100%; }
    .main { max-width: 1100px; margin: 0 auto; }
    </style>
    """, unsafe_allow_html=True)

DB_FILE = 'portfolio.json'
LOG_FILE = 'task_log.json'

# --- HELPERS ---
def get_currency_sign(ticker):
    """Detects correct currency sign based on ticker suffix"""
    if ticker.endswith('.NS') or ticker.endswith('.BO'):
        return "₹"
    return "$"

def get_ai_prediction_data(ticker):
    """Calculates directional prediction and estimated growth percentage"""
    try:
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
        
        # Simple momentum-based predicted growth estimate
        recent_growth = (data['Close'].iloc[-1] / data['Close'].iloc[-5]) - 1
        predicted_pct = recent_growth if pred == 1 else -abs(recent_growth)
        
        return ("UP" if pred == 1 else "DOWN"), predicted_pct
    except: 
        return "ERROR", 0.0

def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_data(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

# --- DASHBOARD START ---
st.title("Market Intelligence Portal")

# 1. STOCK REGISTRATION
st.subheader("Stock Registration")
col1, col2, col3 = st.columns(3)
with col1: t_in = st.text_input("Stock Ticker", key=f"t_{st.session_state.session_id}").upper()
with col2: s_in = st.number_input("Stock Units", min_value=0.0, step=1.0, key=f"s_{st.session_state.session_id}")
with col3: p_in = st.number_input("Cost Basis", min_value=0.0, step=0.01, key=f"p_{st.session_state.session_id}")

if st.button("Register Stock"):
    if t_in:
        check = yf.Ticker(t_in).history(period="1d")
        if check.empty:
            st.error(f"Something is wrong with the ticker {t_in}")
        else:
            port = load_data(DB_FILE)
            port[t_in] = {"shares": s_in, "buy_price": p_in}
            save_data(DB_FILE, port)
            st.session_state.session_id = str(uuid.uuid4())
            st.success(f"Stock {t_in} Registered.")
            st.rerun()

st.divider()

# 2. CURRENT HOLDINGS
portfolio = load_data(DB_FILE)
if portfolio:
    st.subheader("Current Holdings")
    df_p = pd.DataFrame.from_dict(portfolio, orient='index').reset_index()
    df_p.columns = ["Stock", "Units", "Cost"]
    edited = st.data_editor(df_p, num_rows="dynamic", use_container_width=True, hide_index=True)
    
    if st.button("Save Changes"):
        new_port = {row['Stock']: {"shares": row['Units'], "buy_price": row['Cost']} 
                    for _, row in edited.iterrows() if pd.notnull(row['Stock'])}
        save_data(DB_FILE, new_port)
        st.rerun()

    st.divider()

    # 3. AI ANALYSIS & STRATEGY
    if st.button("Generate Market Analysis"):
        buy_more, hold, sell = [], [], []
        
        for s, info in portfolio.items():
            price_data = yf.Ticker(s).history(period="1d")
            if price_data.empty: continue
            
            cur = get_currency_sign(s)
            price = price_data['Close'].iloc[-1]
            gain_pct = ((price - info['buy_price']) / info['buy_price']) * 100
            
            prediction, pred_pct = get_ai_prediction_data(s)
            
            # Money-based prediction calculation
            total_value = price * info['shares']
            pred_money_change = total_value * pred_pct
            
            row = {
                "Stock": s, 
                "Price": f"{cur}{price:,.2f}", 
                "Total Gain": f"{gain_pct:+.2f}%",
                "Predicted Increase (%)": f"{pred_pct:+.2f}%",
                "Predicted Gain (Cash)": f"{cur}{pred_money_change:,.2f}"
            }
            
            if prediction == "DOWN" or gain_pct > 30: sell.append(row)
            elif prediction == "UP" and gain_pct < 10: buy_more.append(row)
            else: hold.append(row)

        st.subheader("Accumulate (Buy More)")
        if buy_more: st.table(pd.DataFrame(buy_more))
        else: st.write("No accumulation signals.")
        
        st.subheader("Hold (Maintain Position)")
        if hold: st.table(pd.DataFrame(hold))
        else: st.write("No hold signals.")
        
        st.subheader("Liquidate (Recommended Sell)")
        if sell: st.table(pd.DataFrame(sell))
        else: st.write("No sell signals.")
        
        st.divider()
        if st.button("Confirm Actions Completed"):
            logs = load_data(LOG_FILE)
            logs[datetime.now().strftime("%Y-%m-%d %H:%M")] = "User completed strategy actions."
            save_data(LOG_FILE, logs)
            st.success("Action logged.")

st.divider()

# 4. DISCOVERY: TOP 10 RECOMMENDATIONS
st.subheader("Top 10 Investment Recommendations")
top_picks = ["NVDA", "AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "META", "TCS.NS", "RELIANCE.NS", "INFY.NS"]
recommendations = []

if st.button("Scan Top 10 Market Opportunities"):
    with st.spinner("Analyzing market data..."):
        for s in top_picks:
            if s not in portfolio:
                prediction, pred_pct = get_ai_prediction_data(s)
                if prediction == "UP":
                    cur = get_currency_sign(s)
                    price = yf.Ticker(s).history(period="1d")['Close'].iloc[-1]
                    recommendations.append({
                        "Stock": s, 
                        "Current Price": f"{cur}{price:,.2f}",
                        "Est. 5-Day Growth": f"{pred_pct:+.2f}%"
                    })
    
    if recommendations:
        st.table(pd.DataFrame(recommendations).head(10))
    else:
        st.write("No high-confidence new buys found at this time.")

st.divider()

# 5. HISTORY LOGS
st.subheader("Action History")
logs = load_data(LOG_FILE)
if logs:
    for ts, msg in reversed(list(logs.items())):
        st.write(f"{ts}: {msg}")
else:
    st.write("No actions logged yet.")
