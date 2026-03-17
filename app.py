import yfinance as yf
import json
import pandas as pd
from datetime import datetime

# 1. Load your portfolio from the JSON file
with open('portfolio.json', 'r') as f:
    my_stocks = json.load(f)

# 2. This list will hold our daily analysis
daily_report = []

print("Checking the market...")

for ticker, data in my_stocks.items():
    # Fetch live data from the web for free
    stock = yf.Ticker(ticker)
    current_price = stock.fast_info['last_price']
    
    # Simple logic for Advice
    # (If price is 10% higher than buy price, maybe Sell. If lower, Hold.)
    profit_pct = ((current_price - data['buy_price']) / data['buy_price']) * 100
    
    if profit_pct > 15:
        advice = "SELL (High Profit)"
    elif profit_pct < -10:
        advice = "BUY (Discount)"
    else:
        advice = "HOLD"

    daily_report.append({
        "Ticker": ticker,
        "Shares": data['shares'],
        "Buy Price": data['buy_price'],
        "Current Price": round(current_price, 2),
        "Profit %": f"{round(profit_pct, 2)}%",
        "ADVICE": advice
    })

# 3. Convert to a clean table
df = pd.DataFrame(daily_report)
print(df)

# 4. Save to Excel with today's date
today = datetime.now().strftime("%Y-%m-%d")
filename = f"Stock_Report_{today}.xlsx"
df.to_excel(filename, index=False)

print(f"Success! Your Excel sheet '{filename}' is ready.")