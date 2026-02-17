#!/usr/bin/env python3
"""Get Webex Calling route IDs using wxc_sdk.

Usage:
    python routeId_sdk.py
    python routeId_sdk.py --name "My Route"
    python routeId_sdk.py --org-id "<org_id>"
"""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv
from requests import HTTPError

from wxc_sdk import WebexSimpleApi


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='List route IDs using wxc_sdk')
    parser.add_argument('--name', help='Filter by routeName (exact match)')
    parser.add_argument('--org-id', help='Optional orgId (or set WEBEX_ORG_ID)')
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    token = os.getenv('WEBEX_ACCESS_TOKEN', '').strip()
    if not token:
        print('Missing WEBEX_ACCESS_TOKEN. Add it to your shell or .env file.')
        return 2

    org_id = args.org_id or os.getenv('WEBEX_ORG_ID')

    try:
        api = WebexSimpleApi(tokens=token)
        routes = list(api.telephony.route_choices(org_id=org_id))
    except HTTPError as e:
        status = getattr(getattr(e, 'response', None), 'status_code', None)
        if status == 401:
            print('\n401 Unauthorized from Webex API. Quick fix checklist:')
            print('1) Verify WEBEX_ACCESS_TOKEN is valid and not expired.')
            print('2) Use an Org Admin (full/read-only) token.')
            print('3) Ensure token has scope: spark-admin:telephony_config_read.\n')
            return 1
        print(f'Webex API error: {e}')
        return 1

    if args.name:
        routes = [r for r in routes if r.route_name == args.name]

    if not routes:
        print('No routes found.')
        return 0

    print('routeId\trouteName\trouteType')
    for route in routes:
        print(f'{route.route_id}\t{route.route_name}\t{route.route_type.value}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
