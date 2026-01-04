import requests
import pandas as pd
import logging
import os
import sys
import time
import subprocess
from requests.exceptions import ConnectionError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs', 'scheduler.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('scheduler')

BASE_URL = "http://127.0.0.1:5000"
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def is_server_running():
    try:
        requests.get(f"{BASE_URL}/health", timeout=2)
        return True
    except:
        return False

def start_server():
    logger.info("Server not running. Starting Flask server...")
    try:
        # Start server in background
        # Use python from the current environment (venv)
        python_exe = sys.executable
        app_path = os.path.join(ROOT_DIR, 'app.py')
        
        # Start process in a new console window to keep it independent
        if os.name == 'nt':
            # CREATE_NEW_CONSOLE = 0x00000010
            kwargs = {'creationflags': subprocess.CREATE_NEW_CONSOLE}
        else:
            kwargs = {'start_new_session': True}
            
        process = subprocess.Popen(
            [python_exe, app_path],
            cwd=ROOT_DIR,
            **kwargs
        )
        
        # Wait for server to initialize
        logger.info("Waiting for server to initialize...")
        for i in range(20):  # Wait up to 20 seconds
            if is_server_running():
                logger.info("Server started successfully.")
                return True
            time.sleep(1)
            
        logger.error("Server failed to start within timeout.")
        return False
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return False

def refresh_and_export():
    try:
        # 1. Check/Start Server
        if not is_server_running():
            if not start_server():
                return False
        
        # 2. Trigger Refresh
        logger.info("Triggering data refresh...")
        refresh_resp = requests.get(f"{BASE_URL}/api/refresh", timeout=30)
        refresh_resp.raise_for_status()
        logger.info(f"Refresh successful: {refresh_resp.json()}")

        # 3. Fetch Latest Data
        logger.info("Fetching latest data for CSV export...")
        funds_resp = requests.get(f"{BASE_URL}/api/funds", timeout=30)
        funds_resp.raise_for_status()
        data = funds_resp.json()
        
        if "funds" not in data:
            logger.error("No funds data received")
            return False

        # 4. Save to CSV
        csv_path = os.path.join(ROOT_DIR, 'mutual_fund_returns.csv')
        
        rows = []
        for fund in data['funds']:
            row = {
                'Fund Name': fund['name'],
                'AMFI Code': fund['code'],
                'Current NAV': fund['nav'],
                '1day': f"{fund['returns1d']:.2f}%",
                '1week': f"{fund['returns1w']:.2f}%",
                '1month': f"{fund['returns1m']:.2f}%",
                '3month': f"{fund['returns3m']:.2f}%",
                '6month': f"{fund['returns6m']:.2f}%",
                '1year': f"{fund['returns1y']:.2f}%",
                '2year': f"{fund['returns2y']:.2f}%",
                '3year': f"{fund['returns3y']:.2f}%",
                '5year': f"{fund['returns5y']:.2f}%"
            }
            rows.append(row)
            
        df = pd.DataFrame(rows)
        columns = ['Fund Name', 'AMFI Code', 'Current NAV', '1day', '1week', '1month', 
                  '3month', '6month', '1year', '2year', '3year', '5year']
        
        for col in columns:
            if col not in df.columns:
                df[col] = "0.00%"
                
        df = df[columns]
        df.to_csv(csv_path, index=False)
        logger.info(f"Successfully updated {csv_path}")
        return True

    except Exception as e:
        logger.error(f"Error in refresh_and_export: {str(e)}")
        return False

if __name__ == "__main__":
    success = refresh_and_export()
    sys.exit(0 if success else 1)
