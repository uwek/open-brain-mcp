"""
Tests für ai.py
"""

import json
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import ai


class TestGetEmbedding:
    """Tests für get_embedding()."""

    @pytest.mark.asyncio
    async def test_get_embedding_success(self, mock_async_client):
        """Erfolgreicher Embedding-Call."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 1536}]
        }
        mock_async_client.post = AsyncMock(return_value=mock_response)
        
        result = await ai._get_embedding_call(mock_async_client, "test text")
        
        assert len(result) == 1536
        assert result[0] == 0.1

    @pytest.mark.asyncio
    async def test_get_embedding_http_error(self, mock_async_client):
        """HTTP-Error wird propagiert."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock(status_code=500)
        )
        mock_async_client.post = AsyncMock(return_value=mock_response)
        
        with pytest.raises(httpx.HTTPStatusError):
            await ai._get_embedding_call(mock_async_client, "test")


class TestExtractMetadata:
    """Tests für extract_metadata()."""

    @pytest.mark.asyncio
    async def test_extract_metadata_success(self, mock_async_client):
        """Erfolgreiche Metadata-Extraktion."""
        expected_metadata = {
            "type": "observation",
            "topics": ["python"],
            "people": [],
            "action_items": [],
            "dates_mentioned": [],
        }
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": json.dumps(expected_metadata)}}
            ]
        }
        mock_async_client.post = AsyncMock(return_value=mock_response)
        
        result = await ai._extract_metadata_call(mock_async_client, "test")
        
        assert result["type"] == "observation"
        assert "python" in result["topics"]

    @pytest.mark.asyncio
    async def test_extract_metadata_invalid_json(self, mock_async_client):
        """Fallback bei ungültigem JSON."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "not valid json"}}]
        }
        mock_async_client.post = AsyncMock(return_value=mock_response)
        
        result = await ai._extract_metadata_call(mock_async_client, "test")
        
        assert result["type"] == "observation"
        assert "uncategorized" in result["topics"]

    @pytest.mark.asyncio
    async def test_extract_metadata_missing_key(self, mock_async_client):
        """Fallback bei fehlendem Key."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"choices": [{}]}
        mock_async_client.post = AsyncMock(return_value=mock_response)
        
        result = await ai._extract_metadata_call(mock_async_client, "test")
        
        assert result["type"] == "observation"


class TestGetEmbeddingAndMetadata:
    """Tests für get_embedding_and_metadata()."""

    @pytest.mark.asyncio
    async def test_combined_call(self):
        """Kombinierter Call liefert beide Ergebnisse."""
        with patch("ai._get_embedding_call", new_callable=AsyncMock) as mock_emb:
            with patch("ai._extract_metadata_call", new_callable=AsyncMock) as mock_meta:
                mock_emb.return_value = [0.1] * 1536
                mock_meta.return_value = {"type": "task", "topics": ["test"]}
                
                embedding, metadata = await ai.get_embedding_and_metadata("test text")
                
                assert len(embedding) == 1536
                assert metadata["type"] == "task"


class TestRetryLogic:
    """Tests für Retry-Logik mit tenacity."""

    @pytest.mark.asyncio
    async def test_retries_on_connect_error(self, mock_async_client):
        """Retry bei ConnectError."""
        call_count = [0]
        
        async def failing_then_success(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise httpx.ConnectError("Connection failed", request=MagicMock())
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"data": [{"embedding": [0.1] * 1536}]}
            return mock_response
        
        mock_async_client.post = failing_then_success
        
        result = await ai._get_embedding_call(mock_async_client, "test")
        
        assert call_count[0] == 3
        assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self, mock_async_client):
        """Retry bei TimeoutException."""
        call_count = [0]
        
        async def failing_then_success(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise httpx.TimeoutException("Timeout", request=MagicMock())
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"data": [{"embedding": [0.1] * 1536}]}
            return mock_response
        
        mock_async_client.post = failing_then_success
        
        result = await ai._get_embedding_call(mock_async_client, "test")
        
        assert call_count[0] == 2


class TestRateLimiter:
    """Tests für Rate-Limiter."""

    def test_rate_limiter_init(self):
        """Rate-Limiter wird korrekt initialisiert."""
        limiter = ai.RateLimiter(calls_per_second=2.0)
        assert limiter._interval == 0.5

    def test_rate_limiter_high_rate(self):
        """Rate-Limiter mit hoher Rate."""
        limiter = ai.RateLimiter(calls_per_second=10.0)
        assert limiter._interval == 0.1

    def test_rate_limiter_low_rate(self):
        """Rate-Limiter mit niedriger Rate."""
        limiter = ai.RateLimiter(calls_per_second=0.5)
        assert limiter._interval == 2.0

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_no_wait(self):
        """Erster acquire() wartet nicht."""
        limiter = ai.RateLimiter(calls_per_second=10.0)
        
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        
        assert elapsed < 0.1  # Sollte fast sofort zurückkehren

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_waits(self):
        """Zweiter acquire() wartet."""
        limiter = ai.RateLimiter(calls_per_second=10.0)  # 0.1s interval
        
        await limiter.acquire()
        
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        
        # Sollte mindestens 0.1s gewartet haben
        assert elapsed >= 0.08  # Etwas Toleranz

    @pytest.mark.asyncio
    async def test_rate_limiter_concurrent(self):
        """Concurrent acquire() werden serialisiert."""
        limiter = ai.RateLimiter(calls_per_second=5.0)  # 0.2s interval
        
        start = time.monotonic()
        
        # 3 concurrent acquires
        results = await asyncio.gather(
            limiter.acquire(),
            limiter.acquire(),
            limiter.acquire(),
        )
        
        elapsed = time.monotonic() - start
        
        # 3 calls à 0.2s = 0.6s minimum, mit Toleranz
        assert elapsed >= 0.35  # Toleranz für async scheduling

    @pytest.mark.asyncio
    async def test_rate_limiter_with_api_call(self, mock_async_client):
        """Rate-Limiter wird bei API-Calls angewendet."""
        # Reset rate limiter
        ai._rate_limiter = None
        
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1] * 1536}]}
        mock_async_client.post = AsyncMock(return_value=mock_response)
        
        # Setze sehr niedrige Rate für Test
        with patch("config.OPENROUTER_RATE_LIMIT", 5.0):
            ai._rate_limiter = ai.RateLimiter(calls_per_second=5.0)
            
            start = time.monotonic()
            
            # Zwei schnelle Calls
            await ai._get_embedding_call(mock_async_client, "test1")
            await ai._get_embedding_call(mock_async_client, "test2")
            
            elapsed = time.monotonic() - start
            
            # Sollte mindestens 0.2s gewartet haben (2 calls * 0.2s)
            assert elapsed >= 0.15

    def test_get_rate_limiter_singleton(self):
        """get_rate_limiter() gibt Singleton zurück."""
        ai._rate_limiter = None
        
        limiter1 = ai.get_rate_limiter()
        limiter2 = ai.get_rate_limiter()
        
        assert limiter1 is limiter2

    def test_get_rate_limiter_uses_config(self):
        """get_rate_limiter() verwendet Konfiguration."""
        ai._rate_limiter = None
        
        with patch("config.OPENROUTER_RATE_LIMIT", 5.0):
            limiter = ai.get_rate_limiter()
            assert limiter._interval == 0.2
