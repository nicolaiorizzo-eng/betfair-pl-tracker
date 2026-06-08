import os
import json
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- Configuration & Environment Variables ---
# In GitHub, you will save these securely under Settings -> Secrets
BETFAIR_APP_KEY = os.environ.get("BETFAIR_APP_KEY")
BETFAIR_USERNAME = os.environ.get("BETFAIR_USERNAME")
BETFAIR_PASSWORD = os.environ.get("BETFAIR_PASSWORD")
DATA_FILE = "betfair_history.csv"

def get_session_token():
    """Authenticates with Betfair to retrieve a session token."""
    payload = f"username={BETFAIR_USERNAME}&password={BETFAIR_PASSWORD}"
    headers = {
        'X-Application': BETFAIR_APP_KEY,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    # Using the standard non-interactive login endpoint
    url = "https://identitysso.betfair.com/api/login"
    response = requests.post(url, data=payload, headers=headers)
    return response.json().get("token")

def fetch_cleared_orders(session_token):
    """Fetches settled bets from the last 2 days to ensure no gaps."""
    url = "https://api.betfair.com/exchange/betting/rest/v1.0/listClearedOrders/"
    headers = {
        'X-Application': BETFAIR_APP_KEY,
        'X-Authentication': session_token,
        'content-type': 'application/json'
    }
    
    from_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
    
    payload = {
        "betStatus": "SETTLED",
        "settledDateRange": {"from": from_date},
        "recordCount": 1000,
        "includeItemDescription": True
    }
    
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    return response.json().get("clearedOrders", [])

def process_and_save():
    token = get_session_token()
    if not token:
        print("Authentication failed.")
        return
        
    orders = fetch_cleared_orders(token)
    if not orders:
        print("No new settled orders found.")
        return

    parsed_records = []
    for order in orders:
        desc = order.get("itemDescription", {})
        
        # Core metrics required
        profit = order.get("profit", 0.0)
        size = order.get("sizeSettled", 0.0)
        price = order.get("priceRequested", 1.0)
        side = order.get("side")
        
        # Calculate liability dynamically based on Back or Lay
        # For a Lay bet, liability is Stake * (Price - 1)
        liability = size * (price - 1.0) if side == "LAY" else size
        
        record = {
            "betId": order.get("betId"),
            "settledDate": order.get("placedDate")[:10], # YYYY-MM-DD
            "event": desc.get("eventName", "Unknown Event"),
            "market": desc.get("marketName", "Unknown Market"),
            "selection": desc.get("runnerName", "Unknown Selection"),
            "side": side,
            "size": size,
            "price": price,
            "profit": profit,
            "liability": round(liability, 2)
        }
        parsed_records.append(record)
        
    new_df = pd.DataFrame(parsed_records)

    # Merge with existing file to prevent duplicates
    if os.path.exists(DATA_FILE):
        existing_df = pd.read_csv(DATA_FILE)
        combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['betId'], keep='last')
    else:
        combined_df = new_df

    combined_df.to_csv(DATA_FILE, index=False)
    print(f"Database updated successfully. Total records: {len(combined_df)}")

if __name__ == "__main__":
    process_and_save()