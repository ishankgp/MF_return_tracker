from flask import Flask, render_template, send_from_directory, jsonify, request
import pandas as pd
from fetch_mf_returns import fetch_funds_data, funds
import json
from datetime import datetime
from functools import lru_cache, wraps
import logging
import traceback
import os
import time
import webbrowser
import threading
import asyncio
from flask_cors import CORS
from cachetools import TTLCache
import redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Redis configuration for caching
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = None
try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()  # Test connection
    logger.info("Redis connection established")
except Exception as e:
    logger.warning(f"Redis not available: {e}")

# In-memory cache as fallback (increased TTL for better performance)
memory_cache = TTLCache(maxsize=200, ttl=600)  # 10 minutes

# Ensure the static directory exists
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

def cache_response(timeout=600):
    """Decorator for caching API responses with improved performance"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = f"{f.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try Redis first
            if redis_client:
                try:
                    cached = redis_client.get(cache_key)
                    if cached:
                        logger.info(f"Redis cache hit for {cache_key}")
                        return json.loads(cached)
                except Exception as e:
                    logger.warning(f"Redis cache error: {e}")
            
            # Fallback to memory cache
            if cache_key in memory_cache:
                logger.info(f"Memory cache hit for {cache_key}")
                return memory_cache[cache_key]
            
            # Execute function and cache result
            result = f(*args, **kwargs)
            
            # Cache in Redis
            if redis_client:
                try:
                    redis_client.setex(cache_key, timeout, json.dumps(result))
                except Exception as e:
                    logger.warning(f"Redis cache set error: {e}")
            
            # Cache in memory
            memory_cache[cache_key] = result
            
            return result
        return decorated_function
    return decorator

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

@cache_response(timeout=600)
def get_cached_data():
    """Get cached fund data with improved error handling and performance"""
    try:
        logger.info("Starting to fetch fund data")
        
        # Use async function for better performance
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(fetch_funds_data())
        loop.close()
        
        if not results:
            logger.error("No fund data could be fetched")
            return {"error": "No data available", "funds": []}
        
        logger.info(f"Successfully fetched data for {len(results)} funds")
        return {
            "funds": results,
            "timestamp": datetime.now().isoformat(),
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error in get_cached_data: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": str(e), "funds": []}

def process_fund_data(results):
    """Process and format fund data for templates with improved performance"""
    if not results or "funds" not in results:
        return []
    
    funds_data = []
    for result in results["funds"]:
        if not result:
            continue
            
        try:
            # Format the data for template
            fund_info = {
                "name": result["name"],
                "code": result["code"],
                "current_nav": f"{result['current_nav']:.2f}",
                "current_date": result["current_date"],
                "dates": result["dates"],
                "returns": {}
            }
            
            # Format returns as numbers or 0 for sorting
            for period, value in result["returns"].items():
                if isinstance(value, (float, int)):
                    fund_info["returns"][period] = value
                else:
                    fund_info["returns"][period] = 0
            
            funds_data.append(fund_info)
            
        except Exception as e:
            logger.error(f"Error processing fund data for {result.get('name', 'Unknown Fund')}: {str(e)}")
    
    return funds_data

@app.route('/')
def index():
    """Main page route with improved error handling and performance"""
    try:
        results = get_cached_data()
        
        if "error" in results:
            logger.error(f"Error in cached data: {results['error']}")
            return render_template('error.html', 
                                error_message="Unable to fetch fund data. Please try again later.",
                                details=results['error']), 500
        
        funds_data = process_fund_data(results)
        
        if not funds_data:
            logger.error("No valid fund data was processed")
            return render_template('error.html', 
                                error_message="Unable to process fund data. Please try again later.",
                                details="Data processing failed"), 500
        
        current_time = datetime.now().strftime("%d-%b-%Y %I:%M:%S %p IST")
        logger.info(f"Successfully prepared data for template rendering: {len(funds_data)} funds")
        
        return render_template('index.html', 
                             funds=funds_data, 
                             last_updated=current_time,
                             fund_count=len(funds_data))
    
    except Exception as e:
        logger.error(f"Error rendering index page: {str(e)}")
        logger.error(traceback.format_exc())
        return render_template('error.html', 
                            error_message="Unable to fetch fund data. Please try again later.",
                            details=str(e)), 500

@app.route('/api/funds')
def api_funds():
    """API endpoint for fund data with improved formatting and performance"""
    try:
        results = get_cached_data()
        
        if "error" in results:
            return jsonify({"error": results["error"], "funds": []}), 500
        
        funds_data = []
        for idx, result in enumerate(results["funds"], 1):
            if not result:
                continue
                
            fund = {
                "id": str(idx),
                "name": result["name"],
                "nav": float(result["current_nav"]),
                "returns1d": result["returns"].get("1day", 0) or 0,
                "returns1w": result["returns"].get("1week", 0) or 0,
                "returns1m": result["returns"].get("1month", 0) or 0,
                "returns3m": result["returns"].get("3month", 0) or 0,
                "returns6m": result["returns"].get("6month", 0) or 0,
                "returns1y": result["returns"].get("1year", 0) or 0,
                "returns3y": result["returns"].get("3year", 0) or 0,
                "returns5y": result["returns"].get("5year", 0) or 0,
                "dates": result["dates"],
                "current_date": result.get("current_date"),
                "category": "Other",
                "risk": "Medium"
            }
            funds_data.append(fund)
        
        return jsonify({
            "funds": funds_data,
            "timestamp": datetime.now().isoformat(),
            "count": len(funds_data)
        })
        
    except Exception as e:
        logger.error(f"Error in API endpoint: {str(e)}")
        return jsonify({"error": str(e), "funds": []}), 500

@app.route('/api/refresh')
def refresh_data():
    """Force refresh of cached data with improved performance"""
    try:
        # Clear caches
        memory_cache.clear()
        if redis_client:
            redis_client.flushdb()
        
        # Fetch fresh data
        results = get_cached_data()
        
        if "error" in results:
            return jsonify({"error": results["error"]}), 500
        
        return jsonify({
            "message": "Data refreshed successfully",
            "timestamp": datetime.now().isoformat(),
            "count": len(results.get("funds", []))
        })
        
    except Exception as e:
        logger.error(f"Error refreshing data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check if we can fetch data
        results = get_cached_data()
        
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "redis_connected": redis_client is not None,
            "funds_count": len(results.get("funds", [])),
            "cache_size": len(memory_cache)
        }
        
        if "error" in results:
            health_status["status"] = "degraded"
            health_status["error"] = results["error"]
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', 
                         error_message="Page not found",
                         details="The requested page does not exist"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', 
                         error_message="Internal server error",
                         details="Something went wrong on our end"), 500

if __name__ == '__main__':
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Open browser automatically in development
    def open_browser():
        time.sleep(2)  # Wait for server to start
        webbrowser.open('http://127.0.0.1:5000')
    
    # Start browser in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run the app
    app.run(debug=True, host='127.0.0.1', port=5000) 