from ._base import ModuleSpec, ModuleResult, run_with_spec

_SPEC = ModuleSpec(
    module="calling_virtual_extensions",
    list_path="telephony.virtual_extensions.list",
    detail_path="telephony.virtual_extensions.details",
    columns=("id", "name", "phone_number", "extension", "routing_type"),
)


def run_module(api, writers, status_recorder) -> ModuleResult:
    return run_with_spec(spec=_SPEC, api=api, writers=writers, status_recorder=status_recorder)
