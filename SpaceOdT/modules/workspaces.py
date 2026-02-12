from ._base import ModuleSpec, ModuleResult, run_with_spec

_SPEC = ModuleSpec(
    module="workspaces",
    list_path="workspaces.list",
    detail_path="workspaces.details",
    columns=("id", "display_name", "location_id", "capacity", "type"),
)


def run_module(api, writers, status_recorder) -> ModuleResult:
    return run_with_spec(spec=_SPEC, api=api, writers=writers, status_recorder=status_recorder)
