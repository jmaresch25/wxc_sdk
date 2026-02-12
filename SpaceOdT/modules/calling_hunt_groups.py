from ._base import ModuleSpec, ModuleResult, run_with_spec

_SPEC = ModuleSpec(
    module="calling_hunt_groups",
    list_path="telephony.hunt_group.list",
    detail_path="telephony.hunt_group.details",
    columns=("id", "name", "location_id", "phone_number", "extension"),
)


def run_module(api, writers, status_recorder) -> ModuleResult:
    return run_with_spec(spec=_SPEC, api=api, writers=writers, status_recorder=status_recorder)
