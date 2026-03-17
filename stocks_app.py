import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Market Intelligence Systems", layout="wide")

# PROFESSIONAL CSS: Centered Content, Large Buttons, Dark Headers
st.markdown("""
    <style>
    .main { max-width: 1000px; margin: 0 auto; }
    thead tr th { background-color: #1e2630 !important; color: white !important; font-weight: bold !important; }
    
    .stButton>button { 
        border-radius: 4px; 
        height: 3.5em; 
        font-weight: bold;
        background-color: #004a99; 
        color: white; 
        border: 1px solid #003366;
    }
    .stButton>button:hover { background-color: #005bc1; border: 1px solid #004a99; }
    </style>
    """, unsafe_allow_html=True)

DB_FILE = 'portfolio.json'
HISTORY_FILE = 'history.json'

# --- CURRENCY MAPPING ---
CURRENCY_SYMBOLS = {
    'USD': '$', 'INR': '₹', 'GBP': '£', 'EUR': '€', 'JPY': '¥', 
    'CAD': 'C$', 'AUD': 'A$', 'CNY': '¥', 'HKD': 'HK$'
}

def get_currency_symbol(ticker_obj):
    try:
        code = ticker_obj.history_metadata.get('currency', 'USD')
        return CURRENCY_SYMBOLS.get(code, f"{code} ")
    except:
        return "$"

# --- DATA HELPERS ---
def load_json(file):
    if os.path.exists(file):
        try:
            with open(file, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_json(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

def get_suggestion(query):
    try:
        search = yf.Search(query, max_results=1).quotes
        if search: return search[0]['symbol']
    except: return None
    return None

# --- APP TABS ---
tab1, tab2 = st.tabs(["Current Portfolio", "Analysis History"])

with tab1:
    st.title("Market Intelligence Portal")
    
    # UPDATED BLUE WARNING BOX
    st.info("""
    **Market Entry Tips:**
    * For international stocks, try **stock.NS** (NSE) or **stock.BO** (BSE).
    * If those do not work, try entering just the **stock** ticker by itself.
    * For indices like the S&P 500, add a **^** in front (e.g., **^GSPC**).
    """)
    
    st.subheader("Stock Registration")
    col1, col2, col3 = st.columns(3)
    with col1: stock_in = st.text_input("Stock Ticker", placeholder="AAPL, TCS.NS, ^GSPC").upper()
    with col2: shares_in = st.number_input("Stock Units", min_value=0.0)
    with col3: price_in = st.number_input("Cost Basis", min_value=0.0)

    if st.button("Register Stock"):
        if stock_in:
            ticker_obj = yf.Ticker(stock_in)
            try:
                check = ticker_obj.history(period="1d")
                if check.empty:
                    suggestion = get_suggestion(stock_in)
                    # UPDATED ERROR MESSAGE
                    st.error(f"something is wrong with the ticker {stock_in}")
                    if suggestion: st.info(f"System Suggestion: Did you mean {suggestion}?")
                else:
                    port = load_json(DB_FILE)
                    port[stock_in] = {"shares": shares_in, "buy_price": price_in}
                    save_json(DB_FILE, port)
                    st.success(f"Stock {stock_in} Registered.")
                    st.rerun()
            except:
                st.error(f"something is wrong with the ticker {stock_in}")

    st.divider()

    # 2. EDITABLE PORTFOLIO
    portfolio_data = load_json(DB_FILE)
    if portfolio_data:
        st.subheader("Active Holdings Management")
        df_display = pd.DataFrame.from_dict(portfolio_data, orient='index').reset_index()
        df_display.columns = ["Stock", "Units", "Cost Basis"]
        
        edited_df = st.data_editor(
            df_display, 
            num_rows="dynamic", 
            use_container_width=True, 
            hide_index=True,
            key="portfolio_editor"
        )
        
        if st.button("Save Changes to Portfolio"):
            new_port = {}
            for _, row in edited_df.iterrows():
                if pd.notnull(row['Stock']):
                    new_port[row['Stock']] = {"shares": row['Units'], "buy_price": row['Cost Basis']}
            save_json(DB_FILE, new_port)
            st.rerun()

        st.divider()

        # 3. ANALYSIS ENGINE
        if st.button('Run Market Evaluation'):
            results = []
            with st.spinner('Synchronizing with Global Exchanges...'):
                for symbol, info in portfolio_data.items():
                    try:
                        ticker_obj = yf.Ticker(symbol)
                        price = ticker_obj.history(period="1d")['Close'].iloc[-1]
                        sym = get_currency_symbol(ticker_obj)
                        gain = ((price - info['buy_price']) / info['buy_price']) * 100 if info['buy_price'] > 0 else 0
                        
                        advice = "HOLD"
                        if gain > 15: advice = "LIQUIDATE / SELL"
                        elif gain < -10: advice = "ACCUMULATE / BUY"
                        
                        results.append({
                            "Stock": symbol, 
                            "Units": info['shares'], 
                            "Market Price": f"{sym}{price:,.2f}", 
                            "Return": f"{gain:.2f}%", 
                            "Action": advice
                        })
                    except: st.error(f"Data link failed for {symbol}")

            if results:
                res_df = pd.DataFrame(results)
                st.subheader("Performance Analysis")
                st.table(res_df)
                
                history = load_json(HISTORY_FILE)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                history[timestamp] = results
                save_json(HISTORY_FILE, history)
                st.toast("Analysis archived in History.")

with tab2:
    st.title("Analysis Archive")
    history_logs = load_json(HISTORY_FILE)
    if not history_logs:
        st.info("No historical logs found.")
    else:
        for ts in reversed(list(history_logs.keys())):
            with st.expander(f"Report: {ts}"):
                st.table(pd.DataFrame(history_logs[ts]))
        
        if st.button("Delete All History?"):
            save_json(HISTORY_FILE, {})
            st.rerun()