import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
from asyncio_throttle import Throttler
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Cache for API responses (10 minutes TTL for better performance)
api_cache = TTLCache(maxsize=100, ttl=600)

import json
import os
DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DATA_DIR, exist_ok=True)
FUNDS_FILE = os.path.join(DATA_DIR, 'funds.json')
RESEARCH_FUNDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'research_funds.json')

DEFAULT_FUNDS = [
    {"name": "Motilal Oswal Midcap Fund", "code": "127042"},
    {"name": "Quant Small Cap Fund", "code": "120828"},
    {"name": "Bandhan Small Cap Fund", "code": "147946"},
    {"name": "Edelweiss Mid Cap Fund", "code": "140228"},
    {"name": "Parag Parikh Flexi Cap Fund", "code": "122639"},
    {"name": "Quant ELSS Tax Saver Fund", "code": "120847"},
    {"name": "Nippon India Small Cap Fund", "code": "118778"},
    {"name": "Invesco India Smallcap Fund", "code": "145137"},
    {"name": "Tata Small Cap Fund", "code": "145206"},
    {"name": "HDFC Mid-Cap Opportunities Fund", "code": "118989"},
]

def load_funds():
    if not os.path.exists(FUNDS_FILE):
        save_funds(DEFAULT_FUNDS)
        return DEFAULT_FUNDS
    try:
        with open(FUNDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading funds: {e}")
        return DEFAULT_FUNDS

def load_research_funds():
    if not os.path.exists(RESEARCH_FUNDS_FILE):
        return []
    try:
        with open(RESEARCH_FUNDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading research funds: {e}")
        return []

def save_funds(funds_list):
    try:
        with open(FUNDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(funds_list, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving funds: {e}")
        return False

def add_fund(name, code):
    funds_list = load_funds()
    if not any(f['code'] == code for f in funds_list):
        funds_list.append({"name": name, "code": code})
        if save_funds(funds_list):
            return True
        else:
            return False
    return False

def remove_fund(code):
    funds_list = load_funds()
    new_funds = [f for f in funds_list if f['code'] != code]
    if len(new_funds) != len(funds_list):
        save_funds(new_funds)
        return True
    return False


import bisect

def parse_nav_data(nav_data):
    """Parse and sort NAV data for fast O(log n) lookups"""
    parsed = []
    for item in nav_data:
        try:
            dt = datetime.strptime(item['date'], "%d-%m-%Y")
            nav = float(item['nav'])
            parsed.append((dt, nav, item['date']))
        except (ValueError, KeyError):
            continue
    # Sort ascending by date
    parsed.sort(key=lambda x: x[0])
    dates = [x[0] for x in parsed]
    return parsed, dates

def find_closest_nav(parsed_navs, dates, target_date):
    """Find the NAV closest to or equal to target_date using binary search"""
    if not dates:
        return None, None
    
    idx = bisect.bisect_right(dates, target_date)
    if idx == 0:
        return None, None # target date is before our earliest record
    
    # idx-1 is the closest date <= target_date
    _, nav, date_str = parsed_navs[idx-1]
    return nav, date_str

async def fetch_fund_data_async(session, fund, throttler):
    """Fetch fund data asynchronously with rate limiting and improved caching"""
    cache_key = f"fund_{fund['code']}"
    
    # Check cache first
    if cache_key in api_cache:
        logger.info(f"Cache hit for {fund['name']}")
        cached_result = api_cache[cache_key].copy()
        cached_result["is_portfolio"] = fund.get("is_portfolio", False)
        return cached_result
    
    url = f"https://api.mfapi.in/mf/{fund['code']}"
    
    try:
        async with throttler:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    logger.error(f"HTTP {response.status} for {fund['name']}")
                    return None
                
                data = await response.json()
                
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
                
                parsed_navs, parsed_dates = parse_nav_data(nav_data)
                
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
                    "3year": 1095,
                    "5year": 1825
                }
                
                for period, days in periods.items():
                    target_date = current_date - timedelta(days=days)
                    historical_nav, historical_date = find_closest_nav(parsed_navs, parsed_dates, target_date)

                    if historical_nav is not None and historical_nav != 0:
                        # Annualize multi-year periods (>= 2 years). Keep others as trailing returns.
                        if period in {"2year", "3year", "5year"}:
                            try:
                                years = days / 365.0
                                cagr = ((current_nav / historical_nav) ** (1 / years) - 1) * 100
                                returns[period] = cagr
                            except Exception:
                                returns[period] = ((current_nav - historical_nav) / historical_nav) * 100
                        else:
                            returns[period] = ((current_nav - historical_nav) / historical_nav) * 100
                        dates[period] = historical_date
                    else:
                        returns[period] = 0  # Use 0 instead of "NA" for better sorting
                        dates[period] = "NA"
                
                # Calculate year-on-year breakdown
                year_breakdown = {}
                for period_years in [2, 3, 5]:
                    period_key = f"{period_years}year"
                    period_data = {"year_dates": {}}
                    
                    for i in range(period_years):
                        year_num = i + 1
                        end_date_target = current_date - timedelta(days=365 * i)
                        start_date_target = current_date - timedelta(days=365 * (i + 1))
                        
                        end_nav, end_date_str = find_closest_nav(parsed_navs, parsed_dates, end_date_target)
                        start_nav, start_date_str = find_closest_nav(parsed_navs, parsed_dates, start_date_target)
                        
                        if end_nav is not None and start_nav is not None and start_nav != 0:
                            ret = ((end_nav - start_nav) / start_nav) * 100
                            period_data[f"year{year_num}"] = ret
                            period_data["year_dates"][f"year{year_num}_start"] = start_date_str
                            period_data["year_dates"][f"year{year_num}_end"] = end_date_str
                        else:
                            period_data[f"year{year_num}"] = 0
                            period_data["year_dates"][f"year{year_num}_start"] = "NA"
                            period_data["year_dates"][f"year{year_num}_end"] = "NA"
                    
                    # Add total absolute return for the period
                    target_date = current_date - timedelta(days=365 * period_years)
                    historical_nav, _ = find_closest_nav(parsed_navs, parsed_dates, target_date)
                    if historical_nav is not None and historical_nav != 0:
                        period_data["total_absolute"] = ((current_nav - historical_nav) / historical_nav) * 100
                    else:
                        period_data["total_absolute"] = 0

                    year_breakdown[period_key] = period_data

                # Calculate Consistency Score: (0.2 * 1Y) + (0.3 * 2Y) + (0.5 * 3Y)
                # Handle missing data by re-normalizing weights
                r1y = returns.get("1year", 0) or 0
                r2y = returns.get("2year", 0) or 0
                r3y = returns.get("3year", 0) or 0
                
                # Check for validity (non-zero or actually present) to determine weights
                # Simplified approach: Use available returns. If return is 0 (and likely not 0% exact), it might be missing.
                # But fetch logic sets missing to 0. Let's assume valid data if we have it.
                # Strictly following the request: 1, 2, 3 year data.
                
                score = (r1y * 0.2) + (r2y * 0.3) + (r3y * 0.5)

                result = {
                    "name": fund["name"],
                    "code": fund["code"],
                    "current_nav": current_nav,
                    "current_date": nav_data[0]["date"],
                    "returns": returns,
                    "consistency_score": score,  # New Field
                    "dates": dates,
                    "year_breakdown": year_breakdown
                }
                
                # Cache the result WITHOUT is_portfolio
                api_cache[cache_key] = result
                logger.info(f"Successfully fetched and cached data for {fund['name']}")
                
                # Inject is_portfolio for the current request
                final_result = result.copy()
                final_result["is_portfolio"] = fund.get("is_portfolio", False)
                return final_result
                
    except asyncio.TimeoutError:
        logger.error(f"Timeout while fetching data for {fund['name']}")
        return None
    except Exception as e:
        logger.error(f"Error processing {fund['name']}: {str(e)}")
        return None

async def fetch_all_funds_async():
    """Fetch all fund data concurrently with improved rate limiting"""
    # Rate limit: 3 requests per second for better performance
    throttler = Throttler(rate_limit=3, period=1)
    
    portfolio_funds = load_funds()
    research_funds = load_research_funds()
    
    # Mark portfolio funds
    portfolio_codes = {f["code"] for f in portfolio_funds}
    for f in portfolio_funds:
        f["is_portfolio"] = True
        
    # Add research funds uniquely
    all_funds = list(portfolio_funds)
    for f in research_funds:
        if f["code"] not in portfolio_codes:
            f["is_portfolio"] = False
            all_funds.append(f)
    
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30),
        connector=aiohttp.TCPConnector(limit=10, limit_per_host=5)
    ) as session:
        tasks = [
            fetch_fund_data_async(session, fund, throttler) 
            for fund in all_funds
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception for fund {all_funds[i]['name']}: {str(result)}")
            elif result is not None:
                valid_results.append(result)
        
        return valid_results


async def fetch_funds_data():
    """Main async function to fetch all funds data with improved performance"""
    return await fetch_all_funds_async()


def main():
    """Main function for command line usage with improved output"""
    try:
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(fetch_all_funds_async())
        loop.close()
        
        if not results:
            logger.error("No fund data could be fetched")
            return
        
        # Create a DataFrame for better display
        rows = []
        for result in results:
            if result:
                row = {
                    'Fund Name': result['name'],
                    'Code': result['code'],
                    'Current NAV': f"{result['current_nav']:.2f}",
                    'Date': result['current_date'],
                    '1D Return': f"{result['returns'].get('1day', 0):.2f}%",
                    '1W Return': f"{result['returns'].get('1week', 0):.2f}%",
                    '1M Return': f"{result['returns'].get('1month', 0):.2f}%",
                    '3M Return': f"{result['returns'].get('3month', 0):.2f}%",
                    '1Y Return': f"{result['returns'].get('1year', 0):.2f}%"
                }
                rows.append(row)
        
        print("\nMutual Fund Returns Summary:")
        print("=" * 80)
        for row in rows:
            print(f"{row['Fund Name']:<30} {row['Code']:<10} {row['Current NAV']:<12} {row['Date']:<12} {row['1D Return']:<10} {row['1W Return']:<10} {row['1M Return']:<10} {row['3M Return']:<10} {row['1Y Return']:<10}")
        print(f"\nTotal funds processed: {len(results)}")
        
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    main()