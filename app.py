from flask import Flask, render_template, send_from_directory, jsonify, request, redirect, url_for, flash, session
import pandas as pd
from fetch_mf_returns import fetch_funds_data, funds
import json
from datetime import datetime, timedelta
from functools import wraps
import logging
import traceback
import os
import asyncio
from flask_cors import CORS
from cachetools import TTLCache
import redis
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from authlib.integrations.flask_client import OAuth
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Secure session key
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
# Session configuration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

CORS(app)

# --- Authentication Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
)

ALLOWED_USERS = ["ishan.kgp@gmail.com"]

class User(UserMixin):
    def __init__(self, id, email, name):
        self.id = id
        self.email = email
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    # In a real app, you'd load from DB. Here we trust the session info if it exists.
    # Since we don't have a DB, we'll reconstruct User from session if possible, 
    # but flask-login calls this with the ID. 
    # For a simple single-user app without DB, we can be a bit hacky or use session directly.
    # BETTER APPROACH: secure session stores the user info.
    if 'user_email' in session:
         return User(session['user_id'], session['user_email'], session.get('user_name', 'User'))
    return None

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/auth/login')
def auth_login():
    redirect_uri = url_for('auth_callback', _external=True)
    # Ensure http/https consistency for local dev vs prod
    if not IS_VERCEL and 'localhost' in redirect_uri:
        redirect_uri = redirect_uri.replace('https://', 'http://')
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def auth_callback():
    try:
        token = google.authorize_access_token()
        user_info = google.get('userinfo').json()
        email = user_info['email']
        
        if email not in ALLOWED_USERS:
            flash("Access denied: You are not authorized to view this application.", "error")
            return redirect(url_for('login'))
        
        # Create user object
        user = User(user_info['id'], email, user_info['name'])
        
        # Login user
        login_user(user)
        session['user_id'] = user.id
        session['user_email'] = user.email
        session['user_name'] = user.name
        session.permanent = True
        
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Auth failed: {e}")
        flash(f"Authentication failed: {str(e)}", "error")
        return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

# ------------------------------------

IS_VERCEL = os.environ.get('VERCEL') == '1'

# Ensure the logs directory exists and configure logging early with absolute paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Data Directory for Persistence (Volumes)
DATA_DIR = os.getenv('DATA_DIR', BASE_DIR)
logs_dir = os.path.join(DATA_DIR, 'logs')

log_handlers = [logging.StreamHandler()]
if not IS_VERCEL:
    os.makedirs(logs_dir, exist_ok=True)
    log_handlers.append(logging.FileHandler(os.path.join(logs_dir, 'app.log')))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
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
                "returns": {},
                "year_breakdown": result.get("year_breakdown", {})
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
@login_required
def index():
    """Main dashboard page"""
    try:
        results = get_cached_data()
        funds_data = process_fund_data(results)
        
        # Handle empty funds list
        if not funds_data:
            return render_template('error.html', 
                                 error_message="No fund data available",
                                 details="Unable to fetch fund data from the API"), 500
        
        # Format timestamp for display
        timestamp = results.get("timestamp", datetime.now().isoformat())
        try:
            dt = datetime.fromisoformat(timestamp)
            last_updated = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            last_updated = timestamp
        
        return render_template('index.html', 
                             funds=funds_data,
                             last_updated=last_updated)
    except Exception as e:
        logger.error(f"Error rendering index: {str(e)}")
        logger.error(traceback.format_exc())
        return render_template('error.html', 
                             error_message="Error loading fund data",
                             details=str(e)), 500

@app.route('/api/funds')
@login_required
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
                "code": result.get("code", ""),
                "nav": float(result["current_nav"]),
                "returns1d": result["returns"].get("1day", 0) or 0,
                "returns1w": result["returns"].get("1week", 0) or 0,
                "returns1m": result["returns"].get("1month", 0) or 0,
                "returns3m": result["returns"].get("3month", 0) or 0,
                "returns6m": result["returns"].get("6month", 0) or 0,
                "returns1y": result["returns"].get("1year", 0) or 0,
                "returns2y": result["returns"].get("2year", 0) or 0,
                "returns3y": result["returns"].get("3year", 0) or 0,
                "returns5y": result["returns"].get("5year", 0) or 0,
                "dates": result["dates"],
                "current_date": result.get("current_date"),
                "year_breakdown": result.get("year_breakdown", {}),
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
@login_required
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

# Notes Management
NOTES_FILE = os.path.join(DATA_DIR, 'notes.json')
CSV_FILE = os.path.join(DATA_DIR, 'mutual_fund_returns.csv')

# In-memory storage for Vercel
memory_notes = []

def load_notes():
    """Load notes from JSON file or memory"""
    if IS_VERCEL:
        return memory_notes
        
    if not os.path.exists(NOTES_FILE):
        return []
    try:
        with open(NOTES_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading notes: {e}")
        return []

def save_notes(notes):
    """Save notes to JSON file or memory"""
    if IS_VERCEL:
        global memory_notes
        memory_notes = notes
        return True

    try:
        with open(NOTES_FILE, 'w') as f:
            json.dump(notes, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving notes: {e}")
        return False

# Scheduled Task for Data Refresh
def scheduled_refresh():
    """Function to be called by APScheduler"""
    logger.info("Starting scheduled data refresh...")
    with app.app_context():
        try:
            # 1. Refresh Cache (Side effect of calling the logic, ignoring return)
            # We call get_cached_data directly to strip the caching decorator if we want fresh?
            # Actually, refresh_data() clears cache then calls get_cached_data.
            # But refresh_data() returns a Response object.
            # Let's reproduce the refresh_data logic here for clarity and safety.
            
            memory_cache.clear()
            if redis_client:
                redis_client.flushdb()
                
            results = get_cached_data() # fetches fresh because cache is clear
            
            if "funds" not in results:
                logger.error("Scheduled refresh: No funds data fetched.")
                return

            # 2. Save to CSV (Persistence)
            funds_data = process_fund_data(results)
            
            csv_rows = []
            for fund in funds_data:
                row = {
                    'Fund Name': fund['name'],
                    'AMFI Code': fund['code'],
                    'Current NAV': fund['current_nav'],
                    '1day': f"{fund['returns'].get('1day', 0):.2f}%",
                    '1week': f"{fund['returns'].get('1week', 0):.2f}%",
                    '1month': f"{fund['returns'].get('1month', 0):.2f}%",
                    '3month': f"{fund['returns'].get('3month', 0):.2f}%",
                    '6month': f"{fund['returns'].get('6month', 0):.2f}%",
                    '1year': f"{fund['returns'].get('1year', 0):.2f}%",
                    '2year': f"{fund['returns'].get('2year', 0):.2f}%",
                    '3year': f"{fund['returns'].get('3year', 0):.2f}%",
                    '5year': f"{fund['returns'].get('5year', 0):.2f}%"
                }
                csv_rows.append(row)
            
            df = pd.DataFrame(csv_rows)
            columns = ['Fund Name', 'AMFI Code', 'Current NAV', '1day', '1week', '1month', 
                      '3month', '6month', '1year', '2year', '3year', '5year']
            
            # Ensure columns exist
            for col in columns:
                if col not in df.columns:
                    df[col] = "0.00%"
            
            df = df[columns]
            df.to_csv(CSV_FILE, index=False)
            logger.info(f"Scheduled refresh success. Saved CSV to {CSV_FILE}")
                
        except Exception as e:
            logger.error(f"Scheduled refresh failed: {e}")
            logger.error(traceback.format_exc())

# Initialize Scheduler
# Only start scheduler if not in debug mode (prevents double run with reloader)
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler = BackgroundScheduler()
    # Run every day at 11:00 AM IST
    scheduler.add_job(func=scheduled_refresh, trigger="cron", hour=11, minute=0, timezone=pytz.timezone('Asia/Kolkata'))
    scheduler.start()
    logger.info("Scheduler started (11:00 AM daily)")


@app.route('/api/notes', methods=['GET'])
@login_required
def get_notes():
    """Get all notes"""
    return jsonify(load_notes())

@app.route('/api/notes', methods=['POST'])
@login_required
def add_note():
    """Add a new note"""
    try:
        data = request.json
        if not data or 'text' not in data or 'date' not in data:
            return jsonify({"error": "Invalid data"}), 400
            
        notes = load_notes()
        notes.append({
            "date": data['date'],
            "text": data['text'],
            "created_at": datetime.now().isoformat()
        })
        
        if save_notes(notes):
            return jsonify({"message": "Note added successfully", "notes": notes})
        else:
            return jsonify({"error": "Failed to save note"}), 500
            
    except Exception as e:
        logger.error(f"Error adding note: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/notes/<int:index>', methods=['DELETE'])
@login_required
def delete_note(index):
    """Delete a note by index"""
    try:
        notes = load_notes()
        if 0 <= index < len(notes):
            notes.pop(index)
            if save_notes(notes):
                return jsonify({"message": "Note deleted successfully", "notes": notes})
            else:
                return jsonify({"error": "Failed to save changes"}), 500
        else:
            return jsonify({"error": "Note not found"}), 404
            
    except Exception as e:
        logger.error(f"Error deleting note: {e}")
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
    
    # Check environment mode
    flask_env = os.getenv('FLASK_ENV', 'development')
    debug_mode = flask_env != 'production'
    
    if debug_mode:
        logger.info("Starting Flask in DEVELOPMENT mode (debug=True)")
    else:
        logger.info("Starting Flask in PRODUCTION mode (debug=False)")
    
    # Run the app with appropriate settings
    app.run(debug=debug_mode, host='127.0.0.1', port=5000, use_reloader=debug_mode)