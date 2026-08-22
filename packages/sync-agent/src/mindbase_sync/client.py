"""Mindbase API client for sync agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx


class MindbaseClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{self.base_url}/v1/ingest", headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    def export_entries(self, since: datetime | None = None, limit: int = 500) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if since:
            params["since"] = since.isoformat()
        with httpx.Client(timeout=60) as client:
            resp = client.get(f"{self.base_url}/v1/export/entries", headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json()["entries"]

    def health(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
