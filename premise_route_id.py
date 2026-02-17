from dotenv import load_dotenv
from wxc_sdk import WebexSimpleApi

load_dotenv(override=True)

api = WebexSimpleApi()

# 1) Trunks (premise_route_id típico = trunk_id)
for trunk in api.telephony.prem_pstn.trunk.list():
    print(f"trunk_name={trunk.name} trunk_id={trunk.trunk_id}")

# 2) Route Groups (route_id alternativo si route_type = ROUTE_GROUP)
for rg in api.telephony.prem_pstn.route_group.list():
    print(f"route_group_name={rg.name} route_group_id={rg.rg_id}")

# 3) Dial Plans (mapea route_id + route_type)
for dp in api.telephony.prem_pstn.dial_plan.list():
    print(f"dial_plan_name={dp.name} route_type={dp.route_type} route_id={dp.route_id}")
