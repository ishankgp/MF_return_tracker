import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
from asyncio_throttle import Throttler
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Cache for API responses (10 minutes TTL for better performance)
api_cache = TTLCache(maxsize=100, ttl=600)

# List of mutual funds to track
funds = [
    {"name": "HDFC Flexi Cap Fund", "code": "120503"},
    {"name": "Parag Parikh Flexi Cap Fund", "code": "122639"},
    {"name": "Motilal Oswal Midcap Fund", "code": "135777"},
    {"name": "Quant Small Cap Fund", "code": "112316"},
    {"name": "Nippon India Small Cap Fund", "code": "118989"},
    {"name": "Axis Small Cap Fund", "code": "120594"},
    {"name": "SBI Small Cap Fund", "code": "119597"},
    {"name": "Kotak Equity Opportunities Fund", "code": "119551"},
    {"name": "Edelweiss Mid Cap Fund", "code": "147769"},
    {"name": "Invesco India Smallcap Fund", "code": "120686"},
]

def find_closest_nav(nav_data, target_date):
    """Find the NAV closest to the target date with improved performance"""
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

async def fetch_fund_data_async(session, fund, throttler):
    """Fetch fund data asynchronously with rate limiting and improved caching"""
    cache_key = f"fund_{fund['code']}"
    
    # Check cache first
    if cache_key in api_cache:
        logger.info(f"Cache hit for {fund['name']}")
        return api_cache[cache_key]
    
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
                    historical_nav, historical_date = find_closest_nav(nav_data, target_date)

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
                        
                        end_nav, end_date_str = find_closest_nav(nav_data, end_date_target)
                        start_nav, start_date_str = find_closest_nav(nav_data, start_date_target)
                        
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
                    historical_nav, _ = find_closest_nav(nav_data, target_date)
                    if historical_nav is not None and historical_nav != 0:
                        period_data["total_absolute"] = ((current_nav - historical_nav) / historical_nav) * 100
                    else:
                        period_data["total_absolute"] = 0

                    year_breakdown[period_key] = period_data

                result = {
                    "name": fund["name"],
                    "code": fund["code"],
                    "current_nav": current_nav,
                    "current_date": nav_data[0]["date"],
                    "returns": returns,
                    "dates": dates,
                    "year_breakdown": year_breakdown
                }
                
                # Cache the result
                api_cache[cache_key] = result
                logger.info(f"Successfully fetched and cached data for {fund['name']}")
                return result
                
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
    
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30),
        connector=aiohttp.TCPConnector(limit=10, limit_per_host=5)
    ) as session:
        tasks = [
            fetch_fund_data_async(session, fund, throttler) 
            for fund in funds
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception for fund {funds[i]['name']}: {str(result)}")
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