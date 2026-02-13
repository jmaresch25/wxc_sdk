#!/usr/bin/env python3
"""Alta asíncrona de sedes (locations) en Webex Calling usando token Bearer.

Ejemplo:
python actions/action_alta_sedes_wbxc.py \
  --name Denver \
  --time-zone America/Chicago \
  --preferred-language en_us \
  --announcement-language en_us \
  --address1 "771 Alder Drive" \
  --city Milpitas \
  --state CA \
  --postal-code 95035 \
  --country US
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any


BASE_URL = "https://webexapis.com/v1"
PATH = "telephony/config/locations"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "name": args.name,
        "timeZone": args.time_zone,
        "preferredLanguage": args.preferred_language,
        "announcementLanguage": args.announcement_language,
        "address": {
            "address1": args.address1,
            "city": args.city,
            "state": args.state,
            "postalCode": args.postal_code,
            "country": args.country,
        },
    }


def build_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def create_location(*, token: str, payload: dict[str, Any], org_id: str | None, insecure: bool) -> dict[str, Any]:
    headers = build_headers(token)
    params = {"orgId": org_id} if org_id else None
    ssl = False if insecure else None
    url = f"{BASE_URL}/{PATH}"

    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async with session.post(url, headers=headers, params=params, json=payload, ssl=ssl) as response:
            text = await response.text()
            if response.status >= 400:
                raise RuntimeError(f"POST {PATH} -> {response.status}: {text[:1000]}")
            if not text:
                return {}
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text}


async def main_async() -> int:
    parser = argparse.ArgumentParser(description="Alta asíncrona de sedes Webex Calling (Bearer token)")
    parser.add_argument("--token", default=None, help="Token Bearer. Si no se indica, usa WEBEX_ACCESS_TOKEN")
    parser.add_argument("--org-id", default=None)
    parser.add_argument("--name", required=True)
    parser.add_argument("--time-zone", required=True)
    parser.add_argument("--preferred-language", required=True)
    parser.add_argument("--announcement-language", required=True)
    parser.add_argument("--address1", required=True)
    parser.add_argument("--city", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--postal-code", required=True)
    parser.add_argument("--country", required=True)
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Desactiva verificación SSL (solo para troubleshooting del entorno).",
    )
    args = parser.parse_args()

    token = args.token or os.getenv("WEBEX_ACCESS_TOKEN")
    if not token:
        print("ERROR: falta token Bearer. Usa --token o WEBEX_ACCESS_TOKEN")
        return 2

    payload = build_payload(args)
    result = await create_location(token=token, payload=payload, org_id=args.org_id, insecure=args.insecure)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
