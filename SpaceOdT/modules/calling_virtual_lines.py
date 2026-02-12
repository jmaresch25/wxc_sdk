from ._base import ModuleSpec, ModuleResult, run_with_spec

_SPEC = ModuleSpec(
    module="calling_virtual_lines",
    list_path="telephony.virtual_line.list",
    detail_path="telephony.virtual_line.details",
    columns=("id", "first_name", "last_name", "location_id", "number"),
)


def run_module(api, writers, status_recorder) -> ModuleResult:
    return run_with_spec(spec=_SPEC, api=api, writers=writers, status_recorder=status_recorder)
