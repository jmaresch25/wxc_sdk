from ._base import ModuleSpec, ModuleResult, run_with_spec

_SPEC = ModuleSpec(
    module="calling_pstn_locations",
    list_path="telephony.pstn.list",
    detail_path="telephony.pstn.details",
    columns=("id", "name", "location_id", "provider", "status"),
)


def run_module(api, writers, status_recorder) -> ModuleResult:
    return run_with_spec(spec=_SPEC, api=api, writers=writers, status_recorder=status_recorder)
