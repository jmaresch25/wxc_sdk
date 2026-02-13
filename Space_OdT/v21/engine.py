from __future__ import annotations

import asyncio
import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any

from wxc_sdk.as_api import AsLocationsApi, AsWebexSimpleApi

from .io import bootstrap_v21_inputs, load_locations, save_json, write_plan_csv
from .models import EntityType, LocationInput, PlannedAction, RunSummary, Stage


class MissingV21InputsError(RuntimeError):
    """Raised when required v2.1 input templates were generated."""


class V21Runner:
    def __init__(self, *, token: str, out_dir: Path):
        self.token = token
        self.out_dir = out_dir

    @property
    def v21_dir(self) -> Path:
        return self.out_dir / 'v21'

    def _ensure_inputs(self) -> None:
        created = bootstrap_v21_inputs(self.v21_dir)
        if created:
            created_lines = '\n'.join(f'  - {path}' for path in created)
            raise MissingV21InputsError(
                'Se crearon plantillas requeridas para v2.1. Completá los archivos y reintentá:\n'
                f'{created_lines}'
            )

    def load_plan_rows(self) -> list[dict[str, Any]]:
        self._ensure_inputs()
        locations = load_locations(self.v21_dir / 'input_locations.csv')
        actions = self._build_plan(locations=locations)
        return [
            {
                'action_id': idx,
                'entity_type': a.entity_type.value,
                'entity_key': a.entity_key,
                'stage': a.stage.value,
                'mode': a.mode,
                'details': a.details,
            }
            for idx, a in enumerate(actions)
        ]

    async def run(self, *, dry_run: bool = True) -> dict[str, Any]:
        plan_rows = self.load_plan_rows()
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        run_id = str(uuid.uuid4())
        mode = 'dry_run' if dry_run else 'apply'

        write_plan_csv(self.v21_dir / 'plan.csv', plan_rows)
        run_state = {
            'run_id': run_id,
            'executed_at': now,
            'mode': mode,
            'completed_count': len(plan_rows),
            'failed_count': 0,
            'planned_count': len(plan_rows),
            'planned_actions': plan_rows,
        }
        save_json(self.v21_dir / 'run_state.json', run_state)

        summary = RunSummary(
            run_id=run_id,
            mode=mode,
            completed_count=len(plan_rows),
            failed_count=0,
            planned_count=len(plan_rows),
            outputs={
                'plan_csv': str(self.v21_dir / 'plan.csv'),
                'run_state': str(self.v21_dir / 'run_state.json'),
            },
        )
        return summary.__dict__

    async def run_locations_async(self, rows: list[LocationInput], *, apply: bool = True, max_concurrency: int = 20) -> dict[str, Any]:
        log_path = self.v21_dir / 'changes.log'
        sem = asyncio.Semaphore(max_concurrency)
        snapshots: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []

        async with AsWebexSimpleApi(tokens=self.token, concurrent_requests=max_concurrency) as api:
            locations_api = AsLocationsApi(session=api.session)
            await api.people.me()

            async def worker(row: LocationInput) -> None:
                async with sem:
                    result = await self._upsert_location(locations_api, row, apply=apply)
                    results.append(result)
                    self._append_jsonl(log_path, result)
                    if result.get('remote_id'):
                        try:
                            details = await locations_api.details(result['remote_id'], org_id=row.org_id)
                        except Exception:
                            details = await locations_api.by_name(row.location_name, org_id=row.org_id)
                        if details is not None:
                            snapshots.append(self._to_jsonable_location(details))

            await asyncio.gather(*(worker(row) for row in rows), return_exceptions=False)

        snapshot_payload = {'items': snapshots}
        save_json(self.v21_dir / 'results_locations.json', snapshot_payload)

        return {
            'summary': {
                'total': len(rows),
                'success': sum(1 for r in results if r['status'] == 'success'),
                'pending': sum(1 for r in results if r['status'] == 'pending'),
                'rejected': sum(1 for r in results if r['status'] == 'rejected'),
            },
            'items': results,
            'snapshot': snapshot_payload,
        }

    async def _upsert_location(self, locations_api: AsLocationsApi, row: LocationInput, *, apply: bool) -> dict[str, Any]:
        location_key = row.location_id or row.location_name
        try:
            existing = await locations_api.by_name(row.location_name, org_id=row.org_id)
            if not apply:
                return {
                    'row_number': row.row_number,
                    'location_key': location_key,
                    'status': 'pending',
                    'remote_id': existing.location_id if existing else None,
                    'error_type': None,
                    'error': None,
                }

            remote_id: str | None = None
            if existing is None:
                self._validate_required_fields(row)
                remote_id = await locations_api.create(
                    name=row.location_name,
                    time_zone=row.payload.get('time_zone') or '',
                    preferred_language=row.payload.get('preferred_language') or '',
                    announcement_language=row.payload.get('announcement_language') or '',
                    address1=row.payload.get('address1') or '',
                    address2=row.payload.get('address2') or None,
                    city=row.payload.get('city') or '',
                    state=row.payload.get('state') or '',
                    postal_code=row.payload.get('postal_code') or '',
                    country=row.payload.get('country') or '',
                    org_id=row.org_id,
                )
            else:
                settings = await locations_api.details(existing.location_id, org_id=row.org_id)
                if row.payload.get('time_zone'):
                    settings.time_zone = row.payload.get('time_zone')
                if row.payload.get('preferred_language'):
                    settings.preferred_language = row.payload.get('preferred_language')
                if row.payload.get('announcement_language'):
                    settings.announcement_language = row.payload.get('announcement_language')
                if settings.address is not None:
                    if row.payload.get('address1'):
                        settings.address.address1 = row.payload.get('address1')
                    if row.payload.get('address2'):
                        settings.address.address2 = row.payload.get('address2')
                    if row.payload.get('city'):
                        settings.address.city = row.payload.get('city')
                    if row.payload.get('state'):
                        settings.address.state = row.payload.get('state')
                    if row.payload.get('postal_code'):
                        settings.address.postal_code = row.payload.get('postal_code')
                    if row.payload.get('country'):
                        settings.address.country = row.payload.get('country')
                await locations_api.update(existing.location_id, settings=settings, org_id=row.org_id)
                remote_id = existing.location_id

            return {
                'row_number': row.row_number,
                'location_key': location_key,
                'status': 'success',
                'remote_id': remote_id,
                'error_type': None,
                'error': None,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                'row_number': row.row_number,
                'location_key': location_key,
                'status': 'rejected',
                'remote_id': None,
                'error_type': type(exc).__name__,
                'error': str(exc),
            }

    @staticmethod
    def _to_jsonable_location(location: Any) -> dict[str, Any]:
        if hasattr(location, 'model_dump'):
            return location.model_dump(mode='json', by_alias=True, exclude_none=True)
        return dict(location)

    @staticmethod
    def _append_jsonl(path: Path, result: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = {
            'row_number': result.get('row_number'),
            'location_key': result.get('location_key'),
            'status': result.get('status'),
            'remote_id': result.get('remote_id'),
            'error_type': result.get('error_type'),
            'error': result.get('error'),
        }
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + '\n')

    @staticmethod
    def _validate_required_fields(row: LocationInput) -> None:
        required = ('time_zone', 'preferred_language', 'announcement_language', 'address1', 'city', 'state', 'postal_code', 'country')
        missing = [field for field in required if not (row.payload.get(field) or '').strip()]
        if missing:
            raise ValueError(f"row {row.row_number}: missing required fields for create: {', '.join(missing)}")

    def _build_plan(self, *, locations: list[LocationInput]) -> list[PlannedAction]:
        actions: list[PlannedAction] = []
        for location in locations:
            location_key = location.location_id or location.location_name
            actions.append(
                PlannedAction(
                    EntityType.LOCATION,
                    location_key,
                    Stage.LOCATION_CREATE_AND_ACTIVATE,
                    'manual_closure',
                    'Alta/actualización determinista de sede',
                )
            )
        return actions
