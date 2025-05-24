import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import logging

logger = logging.getLogger(__name__)

# List of funds with their AMFI codes
funds = [
    {"name": "Quant Small Cap Fund", "code": "120828"},
    {"name": "Bandhan Small Cap Fund", "code": "147946"},
    {"name": "Nippon India Small Cap Fund", "code": "118778"},
    {"name": "Quant Mid Cap Fund", "code": "120841"},
    {"name": "Edelweiss Mid Cap Fund", "code": "140228"},
    {"name": "Motilal Oswal Midcap 30 Fund", "code": "127042"},
    {"name": "Parag Parikh Flexi Cap Direct-Growth", "code": "122639"},
    {"name": "Quant ELSS Tax Saver Direct-Growth", "code": "120847"},
    {"name": "Nippon India Growth Fund", "code": "118668"}
]

def find_closest_nav(nav_data, target_date):
    """Find the NAV closest to the target date"""
    try:
        target_date_str = target_date.strftime("%d-%m-%Y")
        
        # First try exact match
        for nav in nav_data:
            if nav['date'] == target_date_str:
                return float(nav['nav']), nav['date']
        
        # If no exact match, find closest previous date
        closest_nav = None
        closest_date = None
        
        for nav in nav_data:
            nav_date = datetime.strptime(nav['date'], "%d-%m-%Y")
            if nav_date <= target_date:
                if closest_date is None or nav_date > closest_date:
                    closest_date = nav_date
                    closest_nav = float(nav['nav'])
                    closest_date_str = nav['date']
        
        return closest_nav, closest_date_str if closest_nav is not None else None
    except Exception as e:
        logger.error(f"Error finding closest NAV: {str(e)}")
        return None, None

def fetch_fund_data(fund):
    url = f"https://api.mfapi.in/mf/{fund['code']}"
    try:
        # Add timeout to prevent hanging
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        
        if "data" not in data:
            logger.error(f"Invalid response format for {fund['name']}: 'data' key missing")
            return None
        
        nav_data = data["data"]
        if not nav_data:
            logger.error(f"Empty NAV data for {fund['name']}")
            return None
            
        try:
            current_nav = float(nav_data[0]["nav"])
            current_date = datetime.strptime(nav_data[0]["date"], "%d-%m-%Y")
        except (ValueError, KeyError, IndexError) as e:
            logger.error(f"Error parsing current NAV data for {fund['name']}: {str(e)}")
            return None
        
        # Calculate returns for different periods
        returns = {}
        dates = {}
        periods = {
            "1day": 1,
            "1week": 7,
            "1month": 30,
            "3month": 90,
            "6month": 180,
            "1year": 365,
            "2year": 730,
            "3year": 1095,  # 3 years
            "5year": 1825   # 5 years
        }
        
        for period, days in periods.items():
            target_date = current_date - timedelta(days=days)
            historical_nav, historical_date = find_closest_nav(nav_data, target_date)
            
            if historical_nav is not None:
                returns[period] = ((current_nav - historical_nav) / historical_nav) * 100
                dates[period] = historical_date
            else:
                returns[period] = "NA"
                dates[period] = "NA"
        
        return {
            "name": fund["name"],
            "code": fund["code"],
            "current_nav": current_nav,
            "current_date": nav_data[0]["date"],
            "returns": returns,
            "dates": dates
        }
    except requests.Timeout:
        logger.error(f"Timeout while fetching data for {fund['name']}")
        return None
    except requests.RequestException as e:
        logger.error(f"Network error while fetching data for {fund['name']}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error processing {fund['name']}: {str(e)}")
        return None

def main():
    results = []
    for fund in funds:
        logger.info(f"Fetching data for {fund['name']}...")
        fund_data = fetch_fund_data(fund)
        if fund_data:
            results.append(fund_data)
        time.sleep(1)  # Add delay to avoid hitting API rate limits
    
    # Create a DataFrame for better display
    rows = []
    for result in results:
        row = {
            "Fund Name": result["name"],
            "AMFI Code": result["code"],
            "Current NAV": result["current_nav"]
        }
        row.update({k: f"{v:.2f}%" if isinstance(v, float) else v for k, v in result["returns"].items()})
        rows.append(row)
    
    df = pd.DataFrame(rows)
    print("\nMutual Fund Returns:")
    print(df.to_string(index=False))
    
    # Save to CSV
    df.to_csv("mutual_fund_returns.csv", index=False)
    print("\nResults have been saved to 'mutual_fund_returns.csv'")

if __name__ == "__main__":
    main() 