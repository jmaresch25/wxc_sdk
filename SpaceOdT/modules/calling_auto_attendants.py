from ._base import ModuleSpec, ModuleResult, run_with_spec

_SPEC = ModuleSpec(
    module="calling_auto_attendants",
    list_path="telephony.auto_attendant.list",
    detail_path="telephony.auto_attendant.details",
    columns=("id", "name", "location_id", "phone_number", "extension"),
)


def run_module(api, writers, status_recorder) -> ModuleResult:
    return run_with_spec(spec=_SPEC, api=api, writers=writers, status_recorder=status_recorder)
