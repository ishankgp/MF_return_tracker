#!/usr/bin/env python3
"""
Production server for Mutual Fund Returns Tracker (Windows-compatible)
Uses Waitress instead of Gunicorn for Windows compatibility
"""

import os
import sys
import logging
from waitress import serve
from app import app

# Configure logging for production
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/production.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Start the production server"""
    # Set production environment
    os.environ['FLASK_ENV'] = 'production'
    os.environ['LOG_LEVEL'] = 'WARNING'
    os.environ['DEBUG'] = 'False'
    
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Configure Waitress settings
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', 5000))
    threads = int(os.getenv('THREADS', 4))
    
    logger.info(f"Starting production server on {host}:{port}")
    logger.info(f"Using {threads} threads")
    
    try:
        # Start the server
        serve(
            app,
            host=host,
            port=port,
            threads=threads,
            connection_limit=1000,
            cleanup_interval=30,
            channel_timeout=120,
            log_socket_errors=True
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 