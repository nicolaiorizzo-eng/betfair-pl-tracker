import os
import json
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- Configuration & Environment Variables ---
BETFAIR_APP_KEY = os.environ.get("BETFAIR_APP_KEY")
BETFAIR_USERNAME = os.environ.get("BETFAIR_USERNAME")
BETFAIR_PASSWORD = os.environ.get("BETFAIR_PASSWORD")
DATA_FILE = "betfair_history.csv"

def get_session_token():
    """Authenticates with Betfair using the robust interactive automation endpoint."""
    url = f"https://identitysso.betfair.com/api/login?username={BETFAIR_USERNAME}&password={BETFAIR_PASSWORD}&login=true&redirectMethod=POST"
    
    headers = {
        'X-Application': BETFAIR_APP_KEY,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers)
        if response.status_code != 200:
            print(f"Login HTTP Error: {response.status_code}")
            return None
            
        res_json = response.json()
        if res_json.get("status") == "FAIL":
            print(f"Betfair Login Rejected: {res_json.get('error')}")
            return None
            
        return res_json.get("token")
    except Exception as e:
        print(f"An error occurred during authentication parsing: {e}")
        return None

def fetch_cleared_orders(session_token):
    """Fetches settled bets. Looks back 30 days to catch historical data on initial run."""
    url = "https://api.betfair.com/exchange/betting/rest/v1.0/listClearedOrders/"
    headers = {
        'X-Application': BETFAIR_APP_KEY,
        'X-Authentication': session_token,
        'content-type': 'application/json'
    }
    
    # Check if we already have data; if not, go back 30 days to build the baseline database
    lookback_days = 2 if os.path.exists(DATA_FILE) else 30
    from_date = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%Y-%m-%dT00:00:00Z")
    
    print(f"Fetching cleared orders from: {from_date}")
    
    payload = {
        "betStatus": "SETTLED",
        "settledDateRange": {"from": from_date},
        "recordCount": 1000,
        "includeItemDescription": True
    }
    
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch cleared orders. HTTP Status: {response.status_code}")
            return []
        return response.json().get("clearedOrders", [])
    except Exception as e:
        print(f"Error fetching cleared orders: {e}")
        return []

def process_and_save():
    token = get_session_token()
    if not token:
        print("Authentication failed.")
        return
        
    orders = fetch_cleared_orders(token)
    parsed_records = []

    for order in orders:
        desc = order.get("itemDescription", {})
        profit = order.get("profit", 0.0)
        size = order.get("sizeSettled", 0.0)
        price = order.get("priceRequested", 1.0)
        side = order.get("side")
        
        # Lay Liability = Stake * (Odds - 1) | Back Liability = Stake
        liability = size * (price - 1.0) if side == "LAY" else size
        
        record = {
            "betId": order.get("betId"),
            "settledDate": order.get("placedDate")[:10],
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

    # Core Safety Guard: If no orders are found and no baseline file exists, 
    # we initialize a blank DataFrame structure so Git never errors out out again.
    if new_df.empty and not os.path.exists(DATA_FILE):
        new_df = pd.DataFrame(columns=["betId", "settledDate", "event", "market", "selection", "side", "size", "price", "profit", "liability"])

    if os.path.exists(DATA_FILE):
        existing_df = pd.read_csv(DATA_FILE)
        if not new_df.empty:
            combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['betId'], keep='last')
        else:
            combined_df = existing_df
    else:
        combined_df = new_df

    combined_df.to_csv(DATA_FILE, index=False)
    print(f"Database sync successful. Total synchronized rows: {len(combined_df)}")

if __name__ == "__main__":
    process_and_save()
