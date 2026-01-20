"""Tests for page fetchers."""

from unittest.mock import Mock, patch

import pytest
import requests

from job.fetchers import StaticFetcher


def test_static_fetcher_success():
    """Test successful static page fetch."""
    fetcher = StaticFetcher(timeout=5)

    with patch("requests.get") as mock_get:
        mock_response = Mock()
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = fetcher.fetch("https://example.com")

        assert "Test content" in result
        mock_get.assert_called_once()


def test_static_fetcher_timeout():
    """Test static fetcher timeout handling."""
    # Create mock logger that accepts structlog's keyword arguments
    mock_logger = Mock()
    mock_logger.debug = Mock()
    mock_logger.warning = Mock()

    fetcher = StaticFetcher(timeout=5, logger=mock_logger)

    with patch("requests.get", side_effect=requests.Timeout):
        with pytest.raises(requests.Timeout):
            fetcher.fetch("https://example.com")

    # Verify warning was called with structlog-style keyword args
    mock_logger.warning.assert_called_once_with("request_timeout", timeout_seconds=5)


def test_static_fetcher_request_error():
    """Test static fetcher error handling."""
    fetcher = StaticFetcher(timeout=5)

    with patch("requests.get", side_effect=requests.RequestException("Network error")):
        with pytest.raises(requests.RequestException):
            fetcher.fetch("https://example.com")
