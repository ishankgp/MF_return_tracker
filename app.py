from flask import Flask, render_template, send_from_directory
import pandas as pd
from fetch_mf_returns import fetch_fund_data, funds
import json
from datetime import datetime
from functools import lru_cache
import logging
import traceback
import os
import time
import webbrowser
import threading

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure the static directory exists
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Cache the fund data for 5 minutes to avoid hitting the API too frequently
@lru_cache(maxsize=1)
def get_cached_data():
    try:
        current_time = datetime.now().strftime("%Y%m%d%H%M")  # Changes every minute
        results = []
        
        # Add delay between API calls to prevent rate limiting
        for fund in funds:
            try:
                logger.info(f"Fetching data for fund: {fund['name']}")
                fund_data = fetch_fund_data(fund)
                if fund_data:
                    logger.info(f"Successfully fetched data for {fund['name']}")
                    results.append(fund_data)
                else:
                    logger.warning(f"No data returned for fund: {fund['name']}")
            except Exception as e:
                logger.error(f"Error fetching data for fund {fund['name']}: {str(e)}")
                logger.error(traceback.format_exc())
            # Add a small delay between requests
            time.sleep(0.5)
        
        if not results:
            raise Exception("No fund data could be fetched")
            
        return results, current_time
    except Exception as e:
        logger.error(f"Error in get_cached_data: {str(e)}")
        logger.error(traceback.format_exc())
        raise

@app.route('/')
def index():
    try:
        logger.info("Starting to fetch fund data")
        results, _ = get_cached_data()
        
        if not results:
            logger.error("No results returned from get_cached_data")
            return render_template('error.html', 
                                error_message="Unable to fetch fund data. Please try again later.",
                                details="No data available from the API"), 500
        
        # Process the data once
        funds_data = []
        for result in results:
            if not result:  # Skip if result is None
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
                
                # Format returns as numbers or NA
                for period, value in result["returns"].items():
                    if isinstance(value, (float, int)):
                        fund_info["returns"][period] = value
                    else:
                        fund_info["returns"][period] = 0  # Use 0 for NA values for sorting
                
                funds_data.append(fund_info)
                logger.info(f"Successfully processed data for {result['name']}")
            except Exception as e:
                logger.error(f"Error processing fund data for {result.get('name', 'Unknown Fund')}: {str(e)}")
                logger.error(traceback.format_exc())
        
        if not funds_data:  # If no valid data was processed
            logger.error("No valid fund data was processed")
            return render_template('error.html', 
                                error_message="Unable to process fund data. Please try again later.",
                                details="Data processing failed"), 500
            
        current_time = datetime.now().strftime("%d-%b-%Y %I:%M:%S %p IST")
        logger.info("Successfully prepared data for template rendering")
        return render_template('index.html', funds=funds_data, last_updated=current_time)
    
    except Exception as e:
        logger.error(f"Error rendering index page: {str(e)}")
        logger.error(traceback.format_exc())
        return render_template('error.html', 
                            error_message="Unable to fetch fund data. Please try again later.",
                            details=str(e)), 500

if __name__ == '__main__':
    threading.Timer(1.0, lambda: webbrowser.open_new('http://127.0.0.1:5000')).start()
    # Ensure all required directories exist
    for dir_name in ['static', 'templates']:
        dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), dir_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    
    app.run(debug=True) 