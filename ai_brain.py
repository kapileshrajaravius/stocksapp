import yfinance as yf
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import json

def get_ai_prediction(ticker):
    # 1. Get 2 years of history to train the AI
    data = yf.download(ticker, period="2y", interval="1d")
    if data.empty: return "No Data"

    # 2. Create "Features" (What the AI studies)
    data['Return'] = data['Close'].pct_change()
    data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int) # 1 if price goes up tomorrow
    
    # Simple Technical Indicators
    data['MA10'] = data['Close'].rolling(10).mean()
    data['MA50'] = data['Close'].rolling(50).mean()
    data.dropna(inplace=True)

    # 3. Train the Brain (Random Forest)
    X = data[['Return', 'MA10', 'MA50']]
    y = data['Target']
    
    model = RandomForestClassifier(n_estimators=100)
    model.fit(X[:-1], y[:-1]) # Train on everything except the very last day

    # 4. Predict for Tomorrow
    last_day_features = X.tail(1)
    prediction = model.predict(last_day_features)[0]
    confidence = model.predict_proba(last_day_features)[0][prediction]

    return "UP" if prediction == 1 else "DOWN", confidence

# RUN THE CHECK
with open('portfolio.json', 'r') as f:
    portfolio = json.load(f)

print("--- DAILY AI MARKET REPORT ---")
for stock in portfolio:
    pred, conf = get_ai_prediction(stock)
    advice = "HOLD" if pred == "UP" else "EXIT / CAUTION"
    print(f"{stock}: AI predicts {pred} ({conf:.1%} confidence) -> Recommended: {advice}")
