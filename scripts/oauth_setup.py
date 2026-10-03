from __future__ import annotations

import argparse
import json
import secrets
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv

from zoho_inventory_connector.config import READ_ONLY_SCOPES, Settings


def build_auth_url(settings: Settings, state: str) -> str:
    if not settings.zoho_client_id:
        raise SystemExit("Set ZOHO_CLIENT_ID in .env before generating an auth URL.")

    params = {
        "scope": ",".join(READ_ONLY_SCOPES),
        "client_id": settings.zoho_client_id,
        "state": state,
        "response_type": "code",
        "redirect_uri": settings.zoho_redirect_uri,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{settings.zoho_accounts_base_url}/oauth/v2/auth?{urlencode(params)}"


def exchange_code(settings: Settings, code: str) -> dict:
    if not settings.zoho_client_id or not settings.zoho_client_secret:
        raise SystemExit("Set ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET in .env first.")

    response = httpx.post(
        f"{settings.zoho_accounts_base_url}/oauth/v2/token",
        data={
            "code": code,
            "client_id": settings.zoho_client_id,
            "client_secret": settings.zoho_client_secret,
            "redirect_uri": settings.zoho_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=settings.zoho_request_timeout_seconds,
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise SystemExit(
            f"Zoho returned non-JSON OAuth response (HTTP {response.status_code})."
        ) from exc

    if response.is_error or "access_token" not in payload:
        error = payload.get("error") or payload.get("message") or "unknown OAuth error"
        raise SystemExit(f"OAuth exchange failed (HTTP {response.status_code}): {error}")
    return payload


def main() -> None:
    load_dotenv()
    settings = Settings()

    parser = argparse.ArgumentParser(description="Zoho Inventory OAuth setup helper")
    sub = parser.add_subparsers(dest="command", required=True)

    auth_url = sub.add_parser("auth-url", help="Generate the Zoho OAuth consent URL")
    auth_url.add_argument(
        "--state",
        default=None,
        help="Optional CSRF state. A random value is generated when omitted.",
    )

    exchange = sub.add_parser("exchange", help="Exchange authorization code for tokens")
    exchange.add_argument("--code", required=True, help="Short-lived Zoho authorization code")

    args = parser.parse_args()

    if args.command == "auth-url":
        state = args.state or secrets.token_urlsafe(24)
        print(f"State (verify it on callback): {state}")
        print(build_auth_url(settings, state))
        return

    payload = exchange_code(settings, args.code)
    print(
        "OAuth exchange succeeded. Treat the following output as sensitive; "
        "store the refresh token in .env and do not commit it."
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
