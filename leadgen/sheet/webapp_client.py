"""POSTs a batch of new leads to the deployed Apps Script Web App (Code.gs / doPost).

The Web App runs "Execute as: Me" on the Google side, so this client needs no Google OAuth
of its own -- deploying Code.gs once (see HOW-TO-Deploy-Sheet.md) is the only manual step;
every run after that is a plain HTTPS POST. Uses stdlib urllib only, to avoid pulling in
`requests` for a single POST call.
"""
import json
import time
import urllib.error
import urllib.request
from typing import List, Optional


class WebAppError(RuntimeError):
    pass


def post_batch(webapp_url: str, leads: List[dict], excluded: Optional[List[dict]] = None,
                dropped: Optional[List[dict]] = None, max_retries: int = 3,
                backoff_seconds: float = 2.0, timeout_seconds: float = 30.0) -> dict:
    if not webapp_url:
        raise WebAppError(
            "SHEET_WEBAPP_URL is not set -- deploy Code.gs first (see HOW-TO-Deploy-Sheet.md), "
            "then put the Web App URL in .env"
        )
    payload = json.dumps({
        "leads": leads,
        "excluded": excluded or [],
        "dropped": dropped or [],
    }).encode("utf-8")

    last_error: Exception = RuntimeError("no attempts made")
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                webapp_url, data=payload,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(backoff_seconds * attempt)

    raise WebAppError(f"POST to Sheet web app failed after {max_retries} attempts: {last_error}")
