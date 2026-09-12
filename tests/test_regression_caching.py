from unittest.mock import MagicMock, patch
import pytest

from mf_tracker.core import extensions
from mf_tracker.services.cache_service import (
    clear_response_caches,
    invalidate_scope_cache,
    read_response_cache,
    write_response_cache,
)


@pytest.mark.regression
@pytest.mark.unit
class TestRegressionCaching:
    def setup_method(self):
        """Ensure clean cache state before each test."""
        if extensions.memory_cache is not None:
            extensions.memory_cache.clear()
        if extensions.research_memory_cache is not None:
            extensions.research_memory_cache.clear()

    def test_scope_invalidation_isolation_portfolio(self):
        """
        Invalidating 'portfolio' scope must delete portfolio and all caches,
        but strictly preserve research cache.
        """
        extensions.memory_cache["funds_cache:portfolio:latest"] = {"scope": "portfolio"}
        extensions.memory_cache["funds_cache:all:latest"] = {"scope": "all"}
        extensions.research_memory_cache["funds_cache:research:latest"] = {"scope": "research"}

        invalidate_scope_cache("portfolio")

        assert "funds_cache:portfolio:latest" not in extensions.memory_cache
        assert "funds_cache:all:latest" not in extensions.memory_cache
        assert "funds_cache:research:latest" in extensions.research_memory_cache

    def test_scope_invalidation_isolation_research(self):
        """
        Invalidating 'research' scope must delete research and all caches,
        but strictly preserve portfolio cache.
        """
        extensions.memory_cache["funds_cache:portfolio:latest"] = {"scope": "portfolio"}
        extensions.memory_cache["funds_cache:all:latest"] = {"scope": "all"}
        extensions.research_memory_cache["funds_cache:research:latest"] = {"scope": "research"}

        invalidate_scope_cache("research")

        assert "funds_cache:research:latest" not in extensions.research_memory_cache
        assert "funds_cache:all:latest" not in extensions.memory_cache
        assert "funds_cache:portfolio:latest" in extensions.memory_cache

    def test_scope_invalidation_all_clears_everything(self):
        """
        Invalidating 'all' scope must clear all cache stores.
        """
        extensions.memory_cache["funds_cache:portfolio:latest"] = {"scope": "portfolio"}
        extensions.memory_cache["funds_cache:all:latest"] = {"scope": "all"}
        extensions.research_memory_cache["funds_cache:research:latest"] = {"scope": "research"}

        invalidate_scope_cache("all")

        assert len(extensions.memory_cache) == 0
        assert len(extensions.research_memory_cache) == 0

    def test_read_and_write_response_cache_in_memory(self):
        """
        Verify write_response_cache and read_response_cache roundtrip for both
        portfolio/all (memory_cache) and research (research_memory_cache).
        """
        port_payload = {"name": "Portfolio Payload", "funds": [1, 2, 3]}
        res_payload = {"name": "Research Payload", "funds": [4, 5, 6]}

        write_response_cache("funds_cache:portfolio:2026-05-20", port_payload)
        write_response_cache("funds_cache:research:2026-05-20", res_payload)

        read_port = read_response_cache("funds_cache:portfolio:2026-05-20")
        read_res = read_response_cache("funds_cache:research:2026-05-20")

        assert read_port == port_payload
        assert read_res == res_payload

    def test_graceful_redis_failure_fallback(self):
        """
        When Redis raises a connection or timeout error,
        read and write operations must fall back to in-memory TTLCache without crashing.
        """
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("Redis connection refused")
        mock_redis.setex.side_effect = Exception("Redis connection refused")

        with patch.object(extensions, "redis_client", mock_redis):
            payload = {"status": "redis_down_fallback"}
            # Write should catch exception and store in memory_cache
            write_response_cache("funds_cache:portfolio:test", payload)

            assert extensions.memory_cache["funds_cache:portfolio:test"] == payload

            # Read should catch Redis exception and read from memory_cache
            cached = read_response_cache("funds_cache:portfolio:test")
            assert cached == payload
