from __future__ import annotations

from pathlib import Path

from Space_OdT.v21.transformacion import v2_launcher_csv_dependencias as launcher_v2


def test_required_csv_for_user_script_includes_usuarios_csv():
    csvs = launcher_v2._required_csv_for_script('usuarios_modificar_licencias')

    assert 'Usuarios.csv' in csvs


def test_resolve_input_paths_bulk_is_case_insensitive(tmp_path):
    bulk_dir = tmp_path / 'input_data'
    bulk_dir.mkdir()
    (bulk_dir / 'usuarios.csv').write_text('person_id\nabc\n', encoding='utf-8')

    resolved = launcher_v2.resolve_input_paths('usuarios_modificar_licencias', 'bulk', bulk_dir=bulk_dir)

    assert len(resolved) == 1
    assert {path.name for path in resolved} == {'usuarios.csv'}


def test_validate_input_files_detects_empty_csv(tmp_path):
    empty_csv = tmp_path / 'Usuarios.csv'
    empty_csv.write_text('person_id\n', encoding='utf-8')

    ok, error = launcher_v2.validate_input_files([empty_csv])

    assert ok is False
    assert error is not None
    assert 'CSV vacío' in error


def test_run_launcher_v2_returns_error_on_missing_dependency(tmp_path):
    missing_bulk = tmp_path / 'input_data'
    missing_bulk.mkdir()

    result = launcher_v2.run_launcher_v2(
        script_name='usuarios_modificar_licencias',
        mode='bulk',
        token='x',
        auto_confirm=True,
        bulk_dir=missing_bulk,
    )

    assert result['status'] == 'error'
    assert 'CSV faltante' in result['reason']


def test_run_launcher_v2_executes_with_single_mode(monkeypatch, tmp_path):
    single_csv = tmp_path / 'results_manual.csv'
    single_csv.write_text('person_id\np-1\n', encoding='utf-8')

    monkeypatch.setattr(
        launcher_v2,
        '_run_script',
        lambda **kwargs: {'script_name': kwargs['script_name'], 'status': 'executed'},
    )

    result = launcher_v2.run_launcher_v2(
        script_name='usuarios_modificar_licencias',
        mode='single',
        token='x',
        auto_confirm=True,
        single_csv=single_csv,
    )

    assert result['status'] == 'ok'
    assert result['mode'] == 'single'
    assert Path(result['csv_paths'][0]).name == 'results_manual.csv'
