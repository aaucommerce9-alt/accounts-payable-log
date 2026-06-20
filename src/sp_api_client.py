"""
Amazon SP-API client.

Handles LWA token refresh, request signing, and rate-limit retries.
All actual HTTP calls are centralised here so every other module stays clean.
"""

import time
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
_SP_API_BASE   = "https://sellingpartnerapi-na.amazon.com"


class SPAPIClient:
    def __init__(self, cfg: dict):
        sp = cfg["sp_api"]
        self._app_id      = sp["lwa_app_id"]
        self._secret      = sp["lwa_client_secret"]
        self._refresh_tok = sp["refresh_token"]
        self._marketplace = sp["marketplace_id"]
        self._backoff     = cfg["sync"]["retry_backoff_seconds"]
        self._access_token: str | None = None
        self._token_expiry: float = 0.0

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------
    def _ensure_token(self):
        if time.time() < self._token_expiry - 60:
            return
        resp = requests.post(_LWA_TOKEN_URL, data={
            "grant_type":    "refresh_token",
            "refresh_token": self._refresh_tok,
            "client_id":     self._app_id,
            "client_secret": self._secret,
        }, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        self._access_token = body["access_token"]
        self._token_expiry = time.time() + body.get("expires_in", 3600)
        logger.debug("LWA access token refreshed.")

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _headers(self) -> dict:
        self._ensure_token()
        return {
            "x-amz-access-token": self._access_token,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = _SP_API_BASE + path
        for attempt, wait in enumerate([0] + list(self._backoff)):
            if wait:
                logger.warning("Rate-limited; waiting %ss before retry %s.", wait, attempt)
                time.sleep(wait)
            r = requests.get(url, headers=self._headers(), params=params, timeout=30)
            if r.status_code == 429:
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"SP-API request failed after retries: {path}")

    def _post(self, path: str, body: dict) -> dict:
        url = _SP_API_BASE + path
        for attempt, wait in enumerate([0] + list(self._backoff)):
            if wait:
                logger.warning("Rate-limited; waiting %ss before retry %s.", wait, attempt)
                time.sleep(wait)
            r = requests.post(url, headers=self._headers(), json=body, timeout=30)
            if r.status_code == 429:
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"SP-API POST failed after retries: {path}")

    # ------------------------------------------------------------------
    # Orders API
    # ------------------------------------------------------------------
    def get_orders(self, created_after: str) -> list[dict]:
        """Return all orders created after the ISO-8601 timestamp."""
        orders = []
        params = {
            "MarketplaceIds": self._marketplace,
            "CreatedAfter":   created_after,
            "OrderStatuses":  "Unshipped,PartiallyShipped,Shipped,Canceled,Unfulfillable",
        }
        while True:
            data = self._get("/orders/v0/orders", params)
            payload = data.get("payload", {})
            orders.extend(payload.get("Orders", []))
            next_token = payload.get("NextToken")
            if not next_token:
                break
            params = {"NextToken": next_token, "MarketplaceIds": self._marketplace}
        logger.info("Fetched %d orders.", len(orders))
        return orders

    def get_order_items(self, order_id: str) -> list[dict]:
        items = []
        params: dict = {}
        while True:
            data = self._get(f"/orders/v0/orders/{order_id}/orderItems", params or None)
            payload = data.get("payload", {})
            items.extend(payload.get("OrderItems", []))
            next_token = payload.get("NextToken")
            if not next_token:
                break
            params = {"NextToken": next_token}
        return items

    # ------------------------------------------------------------------
    # Finances API
    # ------------------------------------------------------------------
    def list_financial_event_groups(self, posted_after: str) -> list[dict]:
        groups = []
        params = {"PostedAfter": posted_after}
        while True:
            data = self._get("/finances/v0/financialEventGroups", params)
            payload = data.get("payload", {})
            groups.extend(payload.get("FinancialEventGroupList", []))
            next_token = payload.get("NextToken")
            if not next_token:
                break
            params = {"NextToken": next_token}
        logger.info("Fetched %d financial event groups.", len(groups))
        return groups

    def list_financial_events_by_group(self, group_id: str) -> dict:
        data = self._get(f"/finances/v0/financialEventGroups/{group_id}/financialEvents")
        return data.get("payload", {}).get("FinancialEvents", {})

    def list_financial_events(self, posted_after: str) -> dict:
        """Flat pull of all financial events since a date (no group filter)."""
        events: dict = {}
        params = {"PostedAfter": posted_after}
        while True:
            data = self._get("/finances/v0/financialEvents", params)
            payload = data.get("payload", {})
            fe = payload.get("FinancialEvents", {})
            for key, val in fe.items():
                events.setdefault(key, []).extend(val if isinstance(val, list) else [val])
            next_token = payload.get("NextToken")
            if not next_token:
                break
            params = {"NextToken": next_token}
        return events

    # ------------------------------------------------------------------
    # Reports API — Settlement report
    # ------------------------------------------------------------------
    def request_settlement_report(self) -> str:
        """Request a new settlement report and return the reportId."""
        body = {
            "reportType": "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2",
            "marketplaceIds": [self._marketplace],
        }
        data = self._post("/reports/2021-06-30/reports", body)
        report_id = data.get("reportId")
        logger.info("Requested settlement report: %s", report_id)
        return report_id

    def get_report_status(self, report_id: str) -> dict:
        return self._get(f"/reports/2021-06-30/reports/{report_id}")

    def get_report_document(self, document_id: str) -> bytes:
        meta = self._get(f"/reports/2021-06-30/documents/{document_id}")
        url  = meta.get("url")
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        return r.content

    def wait_for_report(self, report_id: str, poll_interval: int = 30, max_wait: int = 600) -> str | None:
        """Poll until report is DONE; return documentId or None on failure."""
        elapsed = 0
        while elapsed < max_wait:
            status = self.get_report_status(report_id)
            state  = status.get("processingStatus")
            if state == "DONE":
                return status.get("reportDocumentId")
            if state in ("CANCELLED", "FATAL"):
                logger.error("Settlement report %s: %s", report_id, state)
                return None
            logger.debug("Report %s status: %s — waiting...", report_id, state)
            time.sleep(poll_interval)
            elapsed += poll_interval
        logger.error("Report %s timed out after %ss.", report_id, max_wait)
        return None
