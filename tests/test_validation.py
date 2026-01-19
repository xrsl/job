"""Tests for URL validation."""

import pytest
from job.main import validate_url


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com", "https://example.com"),
        ("http://example.com", "http://example.com"),
        ("example.com", "https://example.com"),
        ("www.example.com", "https://www.example.com"),
        ("https://example.com/jobs/123", "https://example.com/jobs/123"),
    ],
)
def test_validate_url_success(url: str, expected: str):
    """Test successful URL validation."""
    result = validate_url(url)
    assert result == expected


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "ftp://example.com",
        "javascript:alert(1)",
        "no-tld",  # No TLD and not localhost
        "",
    ],
)
def test_validate_url_failure(url: str):
    """Test URL validation failures."""
    from typer import Exit

    with pytest.raises(Exit):
        validate_url(url)


def test_validate_url_localhost():
    """Test that localhost is accepted."""
    result = validate_url("localhost")
    assert result == "https://localhost"
