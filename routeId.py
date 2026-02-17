import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("WEBEX_TOKEN")

url = "https://webexapis.com/v1/telephony/config/dialPlans"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers)
response.raise_for_status()

data = response.json()

for dp in data.get("dialPlans", []):
    name = dp.get("name")
    route_id = dp.get("routeId")
    route_type = dp.get("routeType")

    print(f"DialPlan: {name}")
    print(f"  routeType: {route_type}")
    print(f"  routeId (premise_route_id): {route_id}")
    print()
