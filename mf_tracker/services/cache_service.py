import json
import logging
from typing import Any, Dict, Optional
from mf_tracker.core import extensions

logger = logging.getLogger(__name__)

def clear_response_caches() -> None:
    if extensions.memory_cache is not None:
        extensions.memory_cache.clear()
    if extensions.research_memory_cache is not None:
        extensions.research_memory_cache.clear()
    
    if extensions.redis_client:
        for pattern in ("funds_cache:*", "get_cached_data:*"):
            for key in extensions.redis_client.scan_iter(pattern):
                extensions.redis_client.delete(key)

def invalidate_scope_cache(scope: str) -> None:
    if scope == "all":
        clear_response_caches()
        return

    for target in (scope, "all"):
        prefix = f"funds_cache:{target}:"
        
        if extensions.memory_cache is not None:
            for k in list(extensions.memory_cache.keys()):
                if k.startswith(prefix) or k.startswith(f"get_cached_data:{target}"):
                    extensions.memory_cache.pop(k, None)
                    
        if extensions.research_memory_cache is not None:
            for k in list(extensions.research_memory_cache.keys()):
                if k.startswith(prefix):
                    extensions.research_memory_cache.pop(k, None)
                    
        if extensions.redis_client:
            try:
                for pattern in (f"funds_cache:{target}:*", f"get_cached_data:{target}:*"):
                    for key in extensions.redis_client.scan_iter(pattern):
                        extensions.redis_client.delete(key)
            except Exception as exc:
                logger.warning("Redis invalidate error for %s: %s", target, exc)

def read_response_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    if extensions.redis_client:
        try:
            cached = extensions.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.warning("Redis cache read error: %s", exc)

    if "research" in cache_key and extensions.research_memory_cache is not None and cache_key in extensions.research_memory_cache:
        return extensions.research_memory_cache[cache_key]

    if extensions.memory_cache is not None and cache_key in extensions.memory_cache:
        return extensions.memory_cache[cache_key]

    return None

def write_response_cache(cache_key: str, payload: Dict[str, Any], ttl: Optional[int] = None) -> None:
    # We retrieve the default TTLs from the initialized caches
    research_cache_ttl = extensions.research_memory_cache.ttl if extensions.research_memory_cache else 35 * 86400
    redis_cache_ttl = extensions.memory_cache.ttl if extensions.memory_cache else 600
    
    expire_seconds = ttl or (research_cache_ttl if "research" in cache_key else redis_cache_ttl)
    
    if extensions.redis_client:
        try:
            extensions.redis_client.setex(cache_key, expire_seconds, json.dumps(payload))
        except Exception as exc:
            logger.warning("Redis cache set error: %s", exc)

    if "research" in cache_key and extensions.research_memory_cache is not None:
        extensions.research_memory_cache[cache_key] = payload
    elif extensions.memory_cache is not None:
        extensions.memory_cache[cache_key] = payload
