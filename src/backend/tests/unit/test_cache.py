"""
Unit tests for Redis cache implementation.

Tests cover:
- Redis client singleton and connection pooling
- Cache CRUD operations and error handling
- TTL functionality and expiration
- Pattern-based cache clearing
- Cache manager context behavior

Version: 1.0
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
import fakeredis
import json
import time
from typing import Dict, Any

from core.cache import (
    get_redis_client,
    CacheManager
)
from config.cache import (
    CACHE_TTL,
    get_cache_key_pattern
)

# Test constants
TEST_KEY = "test:key"
TEST_VALUE = {"data": "test_value"}
TEST_PATTERN = "test:*"
MOCK_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0
}

@pytest.fixture
class TestCacheFixture:
    """Pytest fixture providing isolated Redis test environment."""
    
    def __init__(self) -> None:
        """Initialize test fixture with mock Redis configuration."""
        self._redis_mock = fakeredis.FakeStrictRedis()
        self._mock_config = MOCK_CONFIG.copy()
        self._active_keys = []
        
        # Configure connection pool settings
        self._redis_mock.connection_pool = MagicMock()
        self._redis_mock.connection_pool.max_connections = 100
        self._redis_mock.connection_pool.timeout = 20
    
    def setup(self) -> None:
        """Set up isolated test environment before each test."""
        # Reset Redis mock state
        self._redis_mock.flushall()
        self._active_keys.clear()
        
        # Configure mock responses
        self._redis_mock.ping = Mock(return_value=True)
        self._redis_mock.set = Mock(side_effect=self._redis_mock.set)
        self._redis_mock.get = Mock(side_effect=self._redis_mock.get)
        self._redis_mock.delete = Mock(side_effect=self._redis_mock.delete)
        self._redis_mock.scan = Mock(side_effect=self._redis_mock.scan)
        
        # Patch Redis client
        self.redis_patcher = patch('core.cache.Redis', return_value=self._redis_mock)
        self.redis_patcher.start()
    
    def teardown(self) -> None:
        """Clean up test environment after each test."""
        # Stop Redis mock patch
        self.redis_patcher.stop()
        
        # Clear test data
        self._redis_mock.flushall()
        self._active_keys.clear()
        
        # Reset mock configuration
        self._mock_config = MOCK_CONFIG.copy()

@pytest.mark.unit
@patch('core.cache.redis.Redis')
def test_get_redis_client(mock_redis: Mock, cache_fixture: TestCacheFixture) -> None:
    """Test Redis client singleton creation and connection pooling."""
    # First client instantiation
    client1 = get_redis_client()
    assert client1 is not None
    assert mock_redis.call_count == 1
    
    # Verify connection pool configuration
    pool_config = mock_redis.call_args[1].get('connection_pool')
    assert pool_config is not None
    assert pool_config.max_connections == 100
    assert pool_config.timeout == 20
    
    # Second client instantiation should reuse existing
    client2 = get_redis_client()
    assert client2 is client1
    assert mock_redis.call_count == 1
    
    # Test connection error handling
    mock_redis.side_effect = ConnectionError("Connection failed")
    with pytest.raises(Exception) as exc_info:
        get_redis_client()
    assert "Failed to establish Redis connection" in str(exc_info.value)

@pytest.mark.unit
def test_cache_operations(cache_fixture: TestCacheFixture) -> None:
    """Test comprehensive cache CRUD operations and error handling."""
    client = get_redis_client()
    
    # Test setting multiple values
    test_data = {
        "key1": {"value": "test1"},
        "key2": {"value": "test2"},
        "key3": [1, 2, 3]
    }
    
    for key, value in test_data.items():
        assert client.set(key, json.dumps(value))
    
    # Test bulk retrieval
    for key, expected in test_data.items():
        value = client.get(key)
        assert value is not None
        assert json.loads(value) == expected
    
    # Test partial update
    updated_value = {"value": "updated"}
    assert client.set("key1", json.dumps(updated_value))
    value = client.get("key1")
    assert json.loads(value) == updated_value
    
    # Test deletion
    assert client.delete("key1")
    assert client.get("key1") is None
    
    # Test error handling
    with pytest.raises(TypeError):
        client.set("invalid", object())  # Non-serializable object

@pytest.mark.unit
def test_cache_ttl(cache_fixture: TestCacheFixture) -> None:
    """Test cache TTL functionality with various expiration scenarios."""
    client = get_redis_client()
    
    # Set values with different TTLs
    test_data = {
        "project:1": {"id": 1, "name": "Test Project"},
        "spec:1": {"id": 1, "content": "Test Spec"},
        "items:1": [{"id": 1, "content": "Test Item"}]
    }
    
    for key, value in test_data.items():
        resource_type = key.split(":")[0]
        ttl = CACHE_TTL.get(resource_type + "s", 300)  # Default 5 minutes
        client.setex(key, ttl, json.dumps(value))
    
    # Verify TTLs are set
    for key in test_data:
        ttl = client.ttl(key)
        assert ttl > 0
    
    # Test TTL expiration
    client.setex("expire:test", 1, json.dumps({"test": "value"}))
    time.sleep(1.1)  # Wait for expiration
    assert client.get("expire:test") is None
    
    # Verify non-expired keys remain
    for key in test_data:
        assert client.get(key) is not None

@pytest.mark.unit
def test_cache_pattern_clear(cache_fixture: TestCacheFixture) -> None:
    """Test pattern-based cache clearing with various matching patterns."""
    client = get_redis_client()
    
    # Set up test data with different patterns
    test_data = {
        "test:1": "value1",
        "test:2": "value2",
        "other:1": "value3",
        "test:sub:1": "value4"
    }
    
    for key, value in test_data.items():
        client.set(key, json.dumps(value))
    
    # Test exact pattern clearing
    pattern = get_cache_key_pattern("test")
    cursor = 0
    deleted = 0
    
    while True:
        cursor, keys = client.scan(cursor, match=pattern)
        if keys:
            deleted += client.delete(*keys)
        if cursor == 0:
            break
    
    # Verify pattern-matched keys are cleared
    assert client.get("test:1") is None
    assert client.get("test:2") is None
    assert client.get("other:1") is not None
    
    # Test nested pattern clearing
    pattern = get_cache_key_pattern("test:sub")
    cursor = 0
    deleted = 0
    
    while True:
        cursor, keys = client.scan(cursor, match=pattern)
        if keys:
            deleted += client.delete(*keys)
        if cursor == 0:
            break
    
    assert client.get("test:sub:1") is None

@pytest.mark.unit
def test_cache_manager_context(cache_fixture: TestCacheFixture) -> None:
    """Test CacheManager context manager behavior and resource handling."""
    # Test normal context operation
    with CacheManager() as cache:
        assert cache is not None
        assert cache.ping()
        
        # Test cache operations within context
        cache.set(TEST_KEY, json.dumps(TEST_VALUE))
        value = cache.get(TEST_KEY)
        assert json.loads(value) == TEST_VALUE
    
    # Test error handling within context
    with pytest.raises(Exception):
        with CacheManager() as cache:
            cache.ping = Mock(side_effect=ConnectionError("Connection lost"))
            cache.ping()
    
    # Test context reentry
    manager = CacheManager()
    with manager as cache1:
        assert cache1 is not None
    
    with manager as cache2:
        assert cache2 is not None
        assert cache1 is not cache2  # Should be new connection