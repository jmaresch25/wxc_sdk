from ._base import ModuleSpec, ModuleResult, run_with_spec

_SPEC = ModuleSpec(
    module="devices",
    list_path="devices.list",
    detail_path="devices.details",
    columns=("id", "display_name", "model", "workspace_id", "person_id"),
)


def run_module(api, writers, status_recorder) -> ModuleResult:
    return run_with_spec(spec=_SPEC, api=api, writers=writers, status_recorder=status_recorder)
