from unittest.mock import MagicMock, patch

import pytest

from leadgen.sheet.webapp_client import WebAppError, post_batch


def test_missing_url_raises_without_any_network_call():
    with pytest.raises(WebAppError, match="SHEET_WEBAPP_URL is not set"):
        post_batch("", [{"company_name": "Acme"}])


def test_successful_post_returns_parsed_json():
    fake_response = MagicMock()
    fake_response.read.return_value = b'{"appended": 1}'
    fake_response.__enter__.return_value = fake_response

    with patch("leadgen.sheet.webapp_client.urllib.request.urlopen", return_value=fake_response):
        result = post_batch("https://script.google.com/macros/s/fake/exec", [{"company_name": "Acme"}])
    assert result == {"appended": 1}


def test_retries_then_raises_webapp_error_on_persistent_failure():
    import urllib.error

    with patch("leadgen.sheet.webapp_client.urllib.request.urlopen",
               side_effect=urllib.error.URLError("boom")) as mock_urlopen, \
         patch("leadgen.sheet.webapp_client.time.sleep"):
        with pytest.raises(WebAppError, match="failed after 3 attempts"):
            post_batch("https://script.google.com/macros/s/fake/exec", [], max_retries=3)
    assert mock_urlopen.call_count == 3
