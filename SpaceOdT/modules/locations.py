from ._base import ModuleSpec, ModuleResult, run_with_spec

_SPEC = ModuleSpec(
    module="locations",
    list_path="locations.list",
    detail_path="locations.details",
    columns=("id", "name", "address", "timezone", "preferred_language"),
)


def run_module(api, writers, status_recorder) -> ModuleResult:
    return run_with_spec(spec=_SPEC, api=api, writers=writers, status_recorder=status_recorder)
