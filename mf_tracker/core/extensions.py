import logging
import redis
from authlib.integrations.flask_client import OAuth
from flask_login import LoginManager
from flask_cors import CORS
from cachetools import TTLCache

login_manager = LoginManager()
login_manager.login_view = "web.login"

oauth = OAuth()
cors = CORS()

# Global cache instances
memory_cache = None
research_memory_cache = None
redis_client = None

logger = logging.getLogger(__name__)

def init_caches(app):
    global memory_cache, research_memory_cache, redis_client
    
    memory_cache = TTLCache(
        maxsize=app.config.get("MEMORY_CACHE_SIZE", 200),
        ttl=app.config.get("MEMORY_CACHE_TTL", 600),
    )
    research_cache_ttl = int(app.config.get("RESEARCH_CACHE_TTL", 35 * 86400))
    research_memory_cache = TTLCache(
        maxsize=app.config.get("MEMORY_CACHE_SIZE", 200),
        ttl=research_cache_ttl,
    )

    REDIS_URL = app.config.get("REDIS_URL", "redis://localhost:6379")
    try:
        redis_client = redis.from_url(REDIS_URL)
        redis_client.ping()
        logger.info("Redis connection established")
    except Exception as exc:
        logger.warning("Redis not available: %s", exc)
        redis_client = None
    
    return redis_client
