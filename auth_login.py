"""
Kite Connect Auto-Login Helper.

This script automates the daily access-token refresh flow:
    1. Opens the Kite login URL in your default browser.
    2. Starts a tiny local HTTP server (http://127.0.0.1:8000) to capture
       the redirect that Zerodha sends back with the `request_token`.
    3. Exchanges the request_token for an access_token via Kite Connect API.
    4. Writes the fresh access_token back to the `.env` file so every other
       module picks it up automatically.

Prerequisites
-------------
    1. Set your KITE_API_KEY and KITE_API_SECRET in the `.env` file.
    2. In your Kite Connect app settings on https://developers.kite.trade,
       set the **Redirect URL** to:  http://127.0.0.1:8000

Usage
-----
    python auth_login.py
"""

import os
import sys
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from dotenv import load_dotenv, set_key
from kiteconnect import KiteConnect

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
ENV_FILE = Path(__file__).resolve().parent / ".env"
REDIRECT_PORT = 8000
REDIRECT_URL = f"http://127.0.0.1:{REDIRECT_PORT}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(name)s  —  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("auth_login")


# ──────────────────────────────────────────────
# Redirect handler
# ──────────────────────────────────────────────
class _TokenCaptureHandler(BaseHTTPRequestHandler):
    """
    Handles the single GET redirect from Kite login.

    Kite redirects to:
        http://127.0.0.1:8000/?request_token=XXXX&action=login&status=success

    We extract `request_token`, store it on the server instance, and
    respond with a friendly HTML page.
    """

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        request_token = query.get("request_token", [None])[0]
        status = query.get("status", [None])[0]

        if request_token and status == "success":
            self.server.captured_token = request_token
            self._respond(
                200,
                "<h2 style='font-family:sans-serif;color:#22c55e;'>"
                "✅ Login successful!</h2>"
                "<p style='font-family:sans-serif;'>You can close this tab. "
                "The access token is being generated…</p>",
            )
            logger.info("✓ Captured request_token: %s…", request_token[:8])
        else:
            self.server.captured_token = None
            self._respond(
                400,
                "<h2 style='font-family:sans-serif;color:#ef4444;'>"
                "❌ Login failed or was cancelled.</h2>"
                "<p style='font-family:sans-serif;'>Please try again.</p>",
            )
            logger.error("✗ Login callback had no valid request_token.")

    def _respond(self, code: int, body: str):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = (
            "<!DOCTYPE html><html><head><title>IV-Sniper Auth</title></head>"
            f"<body style='display:flex;justify-content:center;align-items:center;"
            f"height:100vh;background:#0f172a;'>"
            f"<div style='text-align:center;'>{body}</div>"
            f"</body></html>"
        )
        self.wfile.write(html.encode())

    def log_message(self, fmt, *args):
        """Suppress default stderr logging from BaseHTTPRequestHandler."""
        pass


# ──────────────────────────────────────────────
# Core flow
# ──────────────────────────────────────────────

def _ensure_env_file():
    """Create .env file with template if it doesn't exist."""
    if not ENV_FILE.exists():
        ENV_FILE.write_text(
            "# IV-Sniper — Zerodha Kite Connect Credentials\n"
            "# Fill in your API key and secret, then run: python auth_login.py\n\n"
            "KITE_API_KEY=\n"
            "KITE_API_SECRET=\n"
            "KITE_ACCESS_TOKEN=\n",
            encoding="utf-8",
        )
        logger.info("Created template .env file at %s", ENV_FILE)


def _update_env_token(access_token: str):
    """
    Write the fresh access_token back into the .env file.

    Uses python-dotenv's `set_key` so all other values are preserved.
    """
    set_key(str(ENV_FILE), "KITE_ACCESS_TOKEN", access_token)
    logger.info("✓ KITE_ACCESS_TOKEN written to .env")


def run_login_flow():
    """
    Full auto-login flow:
        1. Load .env
        2. Open Kite login URL
        3. Wait for redirect with request_token
        4. Exchange for access_token
        5. Save to .env
    """
    _ensure_env_file()
    load_dotenv(ENV_FILE, override=True)

    api_key = os.getenv("KITE_API_KEY", "").strip()
    api_secret = os.getenv("KITE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        logger.error(
            "KITE_API_KEY and KITE_API_SECRET must be set in .env before login."
        )
        logger.error("Edit the file: %s", ENV_FILE)
        sys.exit(1)

    kite = KiteConnect(api_key=api_key)
    login_url = kite.login_url()

    # ── Step 1: Print login URL ─────────────────
    print()
    print("┌─────────────────────────────────────────────────────────┐")
    print("│          IV-Sniper — Kite Connect Login                 │")
    print("├─────────────────────────────────────────────────────────┤")
    print("│  Copy the URL below and open it in your browser:       │")
    print("└─────────────────────────────────────────────────────────┘")
    print()
    print(f"  {login_url}")
    print()
    print("  ⏳ Waiting for redirect on port 8000…")
    print()

    # ── Step 2: Wait for redirect ─────────────
    server = HTTPServer(("127.0.0.1", REDIRECT_PORT), _TokenCaptureHandler)
    server.captured_token = None
    server.handle_request()          # blocks until ONE request comes in

    request_token = server.captured_token
    if not request_token:
        logger.error("No request_token received. Aborting.")
        sys.exit(1)

    # ── Step 3: Exchange for access_token ─────
    try:
        session_data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = session_data["access_token"]
    except Exception as exc:
        logger.error("Session generation failed: %s", exc)
        sys.exit(1)

    # ── Step 4: Persist ───────────────────────
    _update_env_token(access_token)

    print()
    print("┌─────────────────────────────────────────────────────────┐")
    print("│  ✅  Access token saved to .env                         │")
    print("│  You can now run: python daily_iv_logger.py --once      │")
    print("└─────────────────────────────────────────────────────────┘")
    print()


# ──────────────────────────────────────────────
# Entry
# ──────────────────────────────────────────────
if __name__ == "__main__":
    run_login_flow()
