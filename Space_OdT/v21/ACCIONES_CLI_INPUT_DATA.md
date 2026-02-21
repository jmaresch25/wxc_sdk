# Space_OdT v2.1 · Acciones CLI (fuente `Space_OdT/input_data`)

> Todos los comandos están en formato modular `python -m ...` y priorizan los CSV de `Space_OdT/input_data/`.
> 
> Requisito previo: exportar token o usar `--token`.
>
> ```bash
> export WEBEX_ACCESS_TOKEN="<TOKEN_WEBEX>"
> ```

| Acción | Script encargado | Comando exacto desde CLI (modular) |
|---|---|---|
| Lista con todos los ID de ubicaciones que están creados | `Space_OdT.cli` (`inventory_run`) + export `locations.csv` | `python -m Space_OdT.cli inventory_run --out-dir .artifacts --no-report && python -c "import csv; p='Space_OdT/.artifacts/exports/locations.csv'; r=csv.DictReader(open(p, encoding='utf-8-sig')); print('location_id,name'); [print(f\"{row.get('location_id','')},{row.get('name','')}\") for row in r if (row.get('location_id') or '').strip()]"` |
| Saber valor de `routegroupId` | `Space_OdT.v21.transformacion.get_route_id` | `python -m Space_OdT.v21.transformacion.get_route_id --org-id "$(python -c \"import csv; print(next(csv.DictReader(open('Space_OdT/input_data/global.csv', encoding='utf-8-sig')))['org_id'])\")"` |
| Configurar PSTN de Ubicación | `Space_OdT.v21.transformacion.ubicacion_configurar_pstn` | `python -m Space_OdT.v21.transformacion.ubicacion_configurar_pstn --csv Space_OdT/input_data/Ubicaciones.csv --token "$WEBEX_ACCESS_TOKEN"` |
| Alta numeraciones en ubicación de Webex (estado desactivado) | `Space_OdT.v21.transformacion.ubicacion_alta_numeraciones_desactivadas` | `python -m Space_OdT.v21.transformacion.ubicacion_alta_numeraciones_desactivadas --csv Space_OdT/input_data/Ubicaciones.csv --token "$WEBEX_ACCESS_TOKEN"` |
| Añadir la cabecera de Ubicación | `Space_OdT.v21.transformacion.ubicacion_actualizar_cabecera` | `python -m Space_OdT.v21.transformacion.ubicacion_actualizar_cabecera --csv Space_OdT/input_data/Ubicaciones.csv --token "$WEBEX_ACCESS_TOKEN"` |
| Configuración llamadas internas | `Space_OdT.v21.transformacion.ubicacion_configurar_llamadas_internas` | `python -m Space_OdT.v21.transformacion.ubicacion_configurar_llamadas_internas --csv Space_OdT/input_data/Ubicaciones.csv --token "$WEBEX_ACCESS_TOKEN"` |
| Configurar Permisos de Llamadas Salientes por Defecto | `Space_OdT.v21.transformacion.ubicacion_configurar_permisos_salientes_defecto` | `python -m Space_OdT.v21.transformacion.ubicacion_configurar_permisos_salientes_defecto --csv Space_OdT/input_data/Ubicaciones.csv --token "$WEBEX_ACCESS_TOKEN"` |
| Saber valor de `licenses` | `Space_OdT.cli` (`inventory_run`) + export `licenses.csv` | `python -m Space_OdT.cli inventory_run --out-dir .artifacts --no-report && python -c "import csv; p='Space_OdT/.artifacts/exports/licenses.csv'; r=csv.DictReader(open(p, encoding='utf-8-sig')); print('license_id,name'); [print(f\"{row.get('license_id','')},{row.get('name','')}\") for row in r if (row.get('license_id') or '').strip()]"` |
| Asignar usuarios a LOCATION | `Space_OdT.v21.transformacion.usuarios_asignar_location_desde_csv` | `python -m Space_OdT.v21.transformacion.usuarios_asignar_location_desde_csv --csv Space_OdT/input_data/Usuarios.csv --token "$WEBEX_ACCESS_TOKEN" --apply` |
| Modificación de licencias en usuarios | `Space_OdT.v21.transformacion.usuarios_modificar_licencias` | `python -m Space_OdT.v21.transformacion.usuarios_modificar_licencias --csv Space_OdT/input_data/Usuarios.csv --token "$WEBEX_ACCESS_TOKEN"` |
| Obtener ID del Usuario Creado | `Space_OdT.cli` (`inventory_run`) + export `people.csv` | `python -m Space_OdT.cli inventory_run --out-dir .artifacts --no-report && python -c "import csv; p='Space_OdT/.artifacts/exports/people.csv'; r=csv.DictReader(open(p, encoding='utf-8-sig')); print('email,person_id'); [print(f\"{row.get('email','')},{row.get('person_id','')}\") for row in r if (row.get('person_id') or '').strip()]"` |
| Añadir Número de Intercomunicación Legacy (Secundario) | `Space_OdT.v21.transformacion.usuarios_anadir_intercom_legacy` | `python -m Space_OdT.v21.transformacion.usuarios_anadir_intercom_legacy --csv Space_OdT/input_data/Usuarios.csv --token "$WEBEX_ACCESS_TOKEN"` |
| Configurar Perfil de Llamadas Salientes (si difiere del defecto) | `Space_OdT.v21.transformacion.usuarios_configurar_perfil_saliente_custom` | `python -m Space_OdT.v21.transformacion.usuarios_configurar_perfil_saliente_custom --csv Space_OdT/input_data/Usuarios.csv --token "$WEBEX_ACCESS_TOKEN"` |

## Variante orquestada con launcher (mismo patrón)

Cuando quieras mantener un único entrypoint para acciones de transformación habilitadas en launcher:

```bash
python -m Space_OdT.v21.transformacion.launcher_csv_dependencias \
  --csv-path Space_OdT/input_data/Ubicaciones.csv \
  --script-name ubicacion_configurar_pstn \
  --auto-confirm
```

Cambia `--csv-path` a `Space_OdT/input_data/Usuarios.csv` y `--script-name` por la acción de usuario correspondiente.

## Modo standalone (v21 · primeras 3 transformaciones de ubicación)

Estos scripts ahora resuelven automáticamente `Global.csv` + `Ubicaciones.csv` desde `Space_OdT/input_data` si no indicas `--input-dir` ni `--csv`.

```bash
python -m Space_OdT.v21.transformacion.ubicacion_configurar_pstn
python -m Space_OdT.v21.transformacion.ubicacion_alta_numeraciones_desactivadas
python -m Space_OdT.v21.transformacion.ubicacion_actualizar_cabecera
```

Opcionalmente puedes apuntar a otro set de CSV:

```bash
python -m Space_OdT.v21.transformacion.ubicacion_alta_numeraciones_desactivadas \
  --input-dir /ruta/a/mis_csv
```
