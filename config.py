import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration class"""
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # Server settings
    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', 5000))
    
    # Redis settings
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
    REDIS_TTL = int(os.getenv('REDIS_TTL', 600))  # 10 minutes
    
    # Cache settings
    MEMORY_CACHE_SIZE = int(os.getenv('MEMORY_CACHE_SIZE', 200))
    MEMORY_CACHE_TTL = int(os.getenv('MEMORY_CACHE_TTL', 600))  # 10 minutes
    
    # API settings
    API_TIMEOUT = int(os.getenv('API_TIMEOUT', 15))
    API_RATE_LIMIT = int(os.getenv('API_RATE_LIMIT', 3))  # requests per second
    API_RATE_PERIOD = int(os.getenv('API_RATE_PERIOD', 1))  # seconds
    
    # Logging settings
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')
    
    # Database settings (for future use)
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///mutual_funds.db')
    
    # External API settings
    MF_API_BASE_URL = os.getenv('MF_API_BASE_URL', 'https://api.mfapi.in/mf')
    
    # Performance settings
    MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', 10))
    CONNECTION_POOL_SIZE = int(os.getenv('CONNECTION_POOL_SIZE', 5))

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'
    LOG_LEVEL = 'WARNING'

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default']) 