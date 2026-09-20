"""
MFAPI client.

MFAPI is used only as the raw mutual-fund NAV source.
The rest of the analytics are calculated by Wealth Navigator.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests


BASE_URL = "https://api.mfapi.in"
TIMEOUT = 30


class MFAPIError(RuntimeError):
    pass


class MFAPIClient:
    def __init__(self, base_url: str = BASE_URL, timeout: int = TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "WealthNavigatorPro/1.0"}
        )

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{path}"
        last_error = None
        for attempt in range(3):
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                if r.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                return r.json()
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise MFAPIError(f"MFAPI request failed: {url}: {last_error}")

    def search(self, query: str) -> List[Dict[str, Any]]:
        data = self._get("/mf/search", params={"q": query})
        if isinstance(data, dict):
            # Some API versions wrap results.
            for key in ("data", "results", "schemes"):
                if isinstance(data.get(key), list):
                    return data[key]
            return []
        return data if isinstance(data, list) else []

    def latest(self, scheme_code: str) -> Dict[str, Any]:
        return self._get(f"/mf/{scheme_code}/latest")

    def history(
        self,
        scheme_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return self._get(f"/mf/{scheme_code}", params=params or None)
