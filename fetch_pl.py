import os
import json
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- Configuration & Environment Variables ---
# In GitHub, you save these securely under Settings -> Secrets and variables -> Actions
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
            print(f"Response snippet: {response.text[:300]}")
            return None
            
        res_json = response.json()
        
        # Check if Betfair's internal status flag indicates a login failure
        if res_json.get("status") == "FAIL":
            print(f"Betfair Login Rejected: {res_json.get('error')}")
            return None
            
        return res_json.get("token")
    except Exception as e:
        print(f"An error occurred during authentication parsing: {e}")
        return None

def fetch_cleared_orders(session_token):
    """Fetches settled bets from the last 2 days to ensure no data gaps."""
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
    
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch cleared orders. HTTP Status: {response.status_code}")
            print(f"Response: {response.text[:300]}")
            return []
        return response.json().get("clearedOrders", [])
    except Exception as e:
        print(f"Error fetching cleared orders: {e}")
        return []

def process_and_save():
    token = get_session_token()
    if not token:
        print("Authentication step failed. Exiting script execution.")
        return
        
    orders = fetch_cleared_orders(token)
    if not orders:
        print("No new settled orders returned by the Betfair API.")
        return

    parsed_records = []
    for order in orders:
        desc = order.get("itemDescription", {})
        
        profit = order.get("profit", 0.0)
        size = order.get("sizeSettled", 0.0)
        price = order.get("priceRequested", 1.0)
        side = order.get("side")
        
        # Calculate liability dynamically based on market exposure rules
        # Lay Liability = Stake * (Odds - 1) | Back Liability = Stake
        liability = size * (price - 1.0) if side == "LAY" else size
        
        record = {
            "betId": order.get("betId"),
            "settledDate": order.get("placedDate")[:10],  # Isolates YYYY-MM-DD
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

    # Seamlessly merge new batches into historical tracking log without breaking references
    if os.path.exists(DATA_FILE):
        existing_df = pd.read_csv(DATA_FILE)
        combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['betId'], keep='last')
    else:
        combined_df = new_df

    combined_df.to_csv(DATA_FILE, index=False)
    print(f"Database sync successful. Total synchronized rows: {len(combined_df)}")

if __name__ == "__main__":
    process_and_save()
