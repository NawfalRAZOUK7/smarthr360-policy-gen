"""HTTP client for smarthr360-core-hr (live HR aggregates).

The caller's HR token is passed through — core-hr authorizes the reads
itself. Used by the analytics/simulation endpoints when `source=live`
is requested, so policies are evaluated against the real organization
instead of the demo analytical store.
"""

from __future__ import annotations

import os

import requests

SESSION = requests.Session()
SESSION.trust_env = False

DEFAULT_TIMEOUT = 6


class ServiceError(Exception):
    pass


def _unwrap(payload):
    if isinstance(payload, dict):
        if "data" in payload:
            payload = payload["data"]
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
    return payload


class CoreHRClient:
    def __init__(self, bearer_token: str):
        self.base = os.environ.get(
            "CORE_HR_API_URL", "http://core-hr:8000"
        ).rstrip("/")
        self.headers = {"Authorization": f"Bearer {bearer_token}"}

    def _get(self, path: str) -> list[dict]:
        url = f"{self.base}{path}"
        try:
            resp = SESSION.get(url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as exc:
            raise ServiceError(f"core-hr unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise ServiceError(f"core-hr returned {resp.status_code} for {path}")
        return _unwrap(resp.json()) or []

    def get_live_stats(self) -> dict:
        """Aggregate live indicators from core-hr.

        - headcount / inactive count from employee profiles
          (is_active=False is the closest operational proxy of turnover)
        - average performance from review overall_scores
        """
        employees = self._get("/api/hr/employees/?page_size=100")
        headcount = len(employees)
        inactive = sum(1 for e in employees if not e.get("is_active", True))
        turnover = round(100 * inactive / headcount, 1) if headcount else 0.0

        reviews = self._get("/api/reviews/?page_size=100")
        scores = [
            float(r["overall_score"])
            for r in reviews
            if r.get("overall_score") is not None
        ]
        avg_performance = round(sum(scores) / len(scores), 2) if scores else 0.0

        return {
            "source": "smarthr360-core-hr (live)",
            "headcount": headcount,
            "active": headcount - inactive,
            "turnover": turnover,
            "performance": avg_performance,
            "reviews_counted": len(scores),
        }
