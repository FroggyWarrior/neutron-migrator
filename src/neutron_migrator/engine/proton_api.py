"""Minimal direct Proton REST calls (session refresh, trash purge, logout).

These endpoints are the ones used by Proton's own web client; they are not part
of a documented public API, so every failure is surfaced with debug details.
"""
from __future__ import annotations

import requests

from ..errors import AppError

BASE = "https://mail.proton.me/api"
UA = "NeutronMigrator/1.0 (+https://proton.me)"
OK_CODES = (1000, 1001)


class ProtonApi:
    def __init__(self, uid: str, refresh_token: str = "", access_token: str = ""):
        self.uid, self.refresh_token, self.access_token = uid, refresh_token, access_token

    def _headers(self, auth: bool = True) -> dict[str, str]:
        h = {"x-pm-appversion": "other", "x-pm-locale": "en_US", "User-Agent": UA, "Accept": "application/vnd.protonmail.v1+json"}
        if auth:
            h |= {"x-pm-uid": self.uid, "Authorization": f"Bearer {self.access_token}"}
        return h

    def _call(self, method: str, path: str, payload: dict | None = None, auth: bool = True) -> dict:
        url = f"{BASE}/{path.lstrip('/')}"
        try:
            r = requests.request(method, url, json=payload, headers=self._headers(auth), timeout=45)
        except requests.RequestException as exc:
            raise AppError("error.network", debug=f"{method} {url}\n{exc!r}") from exc
        try:
            data = r.json()
        except ValueError:
            data = {}
        code = data.get("Code")
        if r.status_code >= 400 or (code is not None and code not in OK_CODES):
            raise AppError(
                "error.generic",
                message=str(data.get("Error") or r.reason or r.status_code),
                debug=f"{method} {url}\nHTTP {r.status_code}\n{r.text[:3000]}",
            )
        return data

    def authenticate(self) -> None:
        if self.access_token:
            return
        if not self.refresh_token:
            raise AppError("error.session_expired", debug="No refresh token available in engine config.")
        data = self._call("POST", "auth/v4/refresh", {
            "UID": self.uid, "RefreshToken": self.refresh_token,
            "ResponseType": "token", "GrantType": "refresh_token", "Secure": True,
        }, auth=False)
        self.access_token = data.get("AccessToken", "")
        self.refresh_token = data.get("RefreshToken", self.refresh_token)
        if not self.access_token:
            raise AppError("error.session_expired", debug=f"Refresh returned no AccessToken: {list(data)}")

    def share_ids(self) -> list[str]:
        self.authenticate()
        shares: list[str] = []
        for vol in self._call("GET", "drive/volumes").get("Volumes", []):
            sid = vol.get("ShareID") or (vol.get("Share") or {}).get("ShareID")
            if not sid and vol.get("VolumeID"):
                detail = self._call("GET", f"drive/volumes/{vol['VolumeID']}")
                v = detail.get("Volume", detail)
                sid = v.get("ShareID") or (v.get("Share") or {}).get("ShareID")
            if sid:
                shares.append(sid)
        if not shares:
            raise AppError("error.scan_failed", debug="No Drive share found for this account.")
        return shares

    def empty_trash(self) -> None:
        for sid in self.share_ids():
            self._call("DELETE", f"drive/shares/{sid}/trash")

    def logout(self) -> None:
        if self.access_token or self.refresh_token:
            self.authenticate()
            self._call("DELETE", "auth/v4")