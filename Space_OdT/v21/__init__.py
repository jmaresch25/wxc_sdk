"""API pública liviana para v21.

Nota: evitamos imports eager de submódulos pesados para no contaminar
`sys.modules` durante `python -m Space_OdT.v21.transformacion.<script>`.
"""

__all__ = ['MissingV21InputsError', 'V21Runner', 'launch_v21_ui', 'launch_v211_ui']


def __getattr__(name: str):
    if name in {'MissingV21InputsError', 'V21Runner'}:
        from .engine import MissingV21InputsError, V21Runner

        mapping = {
            'MissingV21InputsError': MissingV21InputsError,
            'V21Runner': V21Runner,
        }
        return mapping[name]

    if name == 'launch_v21_ui':
        from .ui import launch_v21_ui

        return launch_v21_ui

    if name == 'launch_v211_ui':
        from .ui_v211 import launch_v211_ui

        return launch_v211_ui

    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
