"""OAuth flow with Strava: loopback redirect, token persistence, auto-refresh."""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .logging_setup import get_logger

_log = get_logger()

AUTH_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
DEFAULT_SCOPE = "read,activity:read_all,activity:write,profile:read_all"
LOOPBACK_HOST = "127.0.0.1"
LOOPBACK_PORT = 8731
REDIRECT_URI = f"http://{LOOPBACK_HOST}:{LOOPBACK_PORT}/callback"

TOKENS_PATH = Path(os.path.expanduser("~/.config/strava-mcp/tokens.json"))


@dataclass
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: int

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Tokens":
        return cls(
            access_token=d["access_token"],
            refresh_token=d["refresh_token"],
            expires_at=int(d["expires_at"]),
        )


def _save_tokens(tokens: Tokens) -> None:
    TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKENS_PATH.write_text(json.dumps(tokens.to_dict(), indent=2))
    try:
        os.chmod(TOKENS_PATH, 0o600)
    except OSError:
        pass


def _load_tokens() -> Tokens | None:
    if not TOKENS_PATH.exists():
        return None
    try:
        return Tokens.from_dict(json.loads(TOKENS_PATH.read_text()))
    except (json.JSONDecodeError, KeyError):
        return None


class _CallbackHandler(BaseHTTPRequestHandler):
    server_state: dict = {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        state = (params.get("state") or [""])[0]
        if state != self.server_state.get("expected_state"):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"State mismatch")
            return
        code = (params.get("code") or [""])[0]
        self.server_state["code"] = code
        self.server_state["error"] = (params.get("error") or [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Strava MCP connect\xc3\xa9. Tu peux fermer cet onglet.</h2></body></html>"
        )

    def log_message(self, format: str, *args) -> None:  # silence
        return


def _run_oauth_flow(client_id: str, client_secret: str, scope: str) -> Tokens:
    state = secrets.token_urlsafe(24)
    _CallbackHandler.server_state = {"expected_state": state, "code": None, "error": ""}

    httpd = HTTPServer((LOOPBACK_HOST, LOOPBACK_PORT), _CallbackHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    auth_params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": scope,
        "approval_prompt": "auto",
        "state": state,
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(auth_params)}"
    print(f"[strava-mcp] Ouvre ce lien pour autoriser Strava :\n  {url}", file=sys.stderr)
    try:
        webbrowser.open(url)
    except Exception:
        pass

    deadline = time.time() + 300
    while time.time() < deadline:
        if _CallbackHandler.server_state.get("code") or _CallbackHandler.server_state.get("error"):
            break
        time.sleep(0.25)

    httpd.shutdown()
    code = _CallbackHandler.server_state.get("code")
    err = _CallbackHandler.server_state.get("error")
    if err:
        raise RuntimeError(f"OAuth Strava erreur: {err}")
    if not code:
        raise RuntimeError("OAuth Strava: timeout en attente du code.")

    resp = httpx.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    tokens = Tokens(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=int(data["expires_at"]),
    )
    _save_tokens(tokens)
    _log.info("oauth_completed", extra={"event": "oauth_completed", "expires_at": tokens.expires_at})
    return tokens


def _refresh(client_id: str, client_secret: str, refresh_token: str) -> Tokens:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    tokens = Tokens(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=int(data["expires_at"]),
    )
    _save_tokens(tokens)
    return tokens


class TokenManager:
    """Centralise les credentials et tokens, refresh à la demande."""

    def __init__(self, scope: str = DEFAULT_SCOPE) -> None:
        load_dotenv()
        self.client_id = os.environ.get("STRAVA_CLIENT_ID", "").strip()
        self.client_secret = os.environ.get("STRAVA_CLIENT_SECRET", "").strip()
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET manquants. "
                "Crée une app sur https://www.strava.com/settings/api et renseigne .env."
            )
        self.scope = scope
        self._tokens: Tokens | None = _load_tokens()

    def ensure_authorized(self) -> Tokens:
        if self._tokens is None:
            self._tokens = _run_oauth_flow(self.client_id, self.client_secret, self.scope)
        return self._tokens

    def access_token(self) -> str:
        tokens = self.ensure_authorized()
        if tokens.expires_at - int(time.time()) < 60:
            _log.info("oauth_refresh", extra={"event": "oauth_refresh"})
            try:
                tokens = _refresh(self.client_id, self.client_secret, tokens.refresh_token)
            except Exception:
                _log.exception("oauth_refresh_failed", extra={"event": "oauth_refresh_failed"})
                raise
            self._tokens = tokens
        return tokens.access_token
