from ._base import ModuleSpec, ModuleResult, run_with_spec

_SPEC = ModuleSpec(
    module="calling_schedules",
    list_path="common.schedules.list",
    detail_path="common.schedules.details",
    columns=("id", "name", "type", "location_id", "events"),
)


def run_module(api, writers, status_recorder) -> ModuleResult:
    return run_with_spec(spec=_SPEC, api=api, writers=writers, status_recorder=status_recorder)
