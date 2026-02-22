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

## launcher_V2 · Dev Spec Sheet (plan previo, sin implementación)

> Objetivo de este apartado: definir el diseño/plan para una nueva versión `Space_OdT/v21/transformacion/v2_launcher_csv_dependencias.py` con comportamiento común para scripts de transformación, antes de escribir código.

### 1) Qué estamos construyendo

**Qué es**
- Un launcher CLI común (v2) para ejecutar scripts de transformación de `Space_OdT.v21.transformacion` con selección guiada, modo single/bulk y logging estandarizado de troubleshooting.

**Para quién**
- Operación técnica y equipos de migración/provisión que hoy ejecutan múltiples scripts con parámetros heterogéneos.

**Problema que resuelve**
- Elimina boilerplate repetido por script.
- Reduce errores humanos al elegir script, CSV y modo de ejecución.
- Estandariza visibilidad operativa (pasos por pantalla + log clave acotado de tamaño).

**Cómo va a funcionar (alto nivel)**
1. Menú en terminal (CLI interactiva).
2. Lista scripts disponibles con selección por letras (`a,b,c,...`).
3. Pregunta modo: un registro (single) o varios registros (bulk).
4. Si single: mantiene flujo actual contra un único CSV `results_manual.csv`.
5. Si bulk: carga CSV de `[rootdir]/input_data` (`Ubicaciones.csv`, `Global.csv`, `Usuarios.csv`).
6. Ejecuta script objetivo con prechecks + validaciones mínimas.
7. Registra `LOGGER.info` en cada paso importante.
8. Genera log de troubleshooting con información clave y rotación/límite para evitar crecimiento excesivo (escenario >4000 líneas).

**Conceptos principales y relación**
- `Launcher V2` (orquestador) → selecciona `Script Target`.
- `ExecutionMode` (`single` | `bulk`) → decide fuente de entrada CSV.
- `DataResolver` → resuelve rutas y presencia de archivos.
- `RunnerAdapter` → normaliza llamada de scripts con distinta firma.
- `TroubleshootingLogger` → captura eventos clave, limita tamaño y facilita diagnóstico.

**Distilling/refactor (principio)**
- Centralizar inicialización, validaciones, logging, parseo de modo y resolución de CSV en launcher.
- Mantener en cada script solo lógica específica de negocio (API y transformación).

---

### 2) Diseño de experiencia de usuario (CLI)

**User stories (happy flow)**
- Como operador, quiero ver un menú simple para escoger script por letra y no recordar comandos largos.
- Como operador, quiero elegir si ejecuto sobre un único registro o en lote para no editar scripts.
- Como operador, quiero ver por pantalla los pasos críticos para entender qué está ocurriendo.
- Como operador, quiero un log corto pero útil para troubleshooting.

**Flujos alternativos**
- Script no aplicable al modo elegido → el launcher sugiere cambio de modo/script y no ejecuta.
- CSV faltante o vacío → error temprano con mensaje accionable.
- Dependencia no cumplida (p.ej. `Global.csv`) → bloquea ejecución con motivo explícito.

**Estructura de UI (terminal)**
1. Banner `Launcher V2`.
2. Menú de scripts (`a) ...`, `b) ...`, ...).
3. Prompt de selección.
4. Prompt de modo (`1=single`, `2=bulk`).
5. Confirmación resumen (script + modo + archivos detectados).
6. Ejecución con trazas `INFO`.
7. Resultado final (OK/KO + ruta de log).

**Mockup textual rápido**
```text
=== Space_OdT Launcher V2 ===
a) ubicacion_configurar_pstn
b) ubicacion_alta_numeraciones_desactivadas
c) usuarios_modificar_licencias
...
Selecciona script [a..n]: c
Modo: 1) single (results_manual.csv)  2) bulk (input_data)
Selecciona modo [1/2]: 2
Resumen: script=usuarios_modificar_licencias, modo=bulk
CSV detectados: input_data/Global.csv, input_data/Usuarios.csv
¿Confirmar ejecución? [s/N]: s
[INFO] Validando dependencias...
[INFO] Ejecutando...
[INFO] Finalizado OK. Log: Space_OdT/.artifacts/logs/launcher_v2_troubleshooting.log
```

---

### 3) Necesidades técnicas

**Inventario de casos específicos por script (a identificar antes de implementar)**
- **Ubicaciones** (`ubicacion_*`): dependen de `Ubicaciones.csv` y en algunos casos también `Global.csv`.
- **Usuarios** (`usuarios_*`): dependen de `Usuarios.csv`; algunos requieren campos/licencias/IDs concretos.
- **Workspaces** (`workspaces_*`): dependen de CSV de workspaces (si aplica en input_data actual) y pueden requerir validación adicional.
- **Scripts utilitarios** (`get_route_id`, `inspect_params`, `generar_csv_candidatos_desde_artifacts`): no todos encajan en modo transaccional single/bulk; marcar como "fuera de menú operativo" o en sección avanzada.

**Propuesta técnica (sin código aún)**
- Crear `v2_launcher_csv_dependencias.py` como capa de orquestación.
- Definir catálogo declarativo de scripts:
  - `display_name`, `module_name`, `entity_type`, `supports_single`, `supports_bulk`, `required_csv`.
- Añadir resolvedor de input:
  - `single` → `results_manual.csv`.
  - `bulk` → `input_data/Ubicaciones.csv`, `input_data/Global.csv`, `input_data/Usuarios.csv` según script.
- Adaptador de ejecución:
  - Invocación uniforme (subprocess o import dinámico), evitando que cada script sea standalone completo.
- Logging:
  - `LOGGER.info` para hitos.
  - Handler específico troubleshooting con límites (`RotatingFileHandler` o tope por líneas/eventos).
- Seguridad/robustez:
  - Validar rutas dentro de root esperado.
  - Sanitizar selección de menú.
  - Fallo temprano con códigos de salida coherentes.

**Dependencias externas**
- Priorizar stdlib (`argparse`, `logging`, `pathlib`, `subprocess/importlib`, `dataclasses`).
- Sin nuevas librerías salvo necesidad clara.

---

### 4) Testing y seguridad

**Cobertura objetivo (fase implementación)**
- Cobertura funcional de launcher (selección script, selección modo, resolución CSV, errores esperados).

**Tipos de tests**
- Unit tests:
  - parser de menú,
  - resolvedor de CSV por modo,
  - mapeo script→dependencias,
  - política de logging limitado.
- Regression tests:
  - preservar comportamiento single actual (`results_manual.csv`).
- E2E ligero:
  - ejecución simulada con scripts dummy/mocks.

**Side-effects previstos**
- Cambio de entrypoint operacional para transformaciones.
- Necesidad de documentar scripts que quedan fuera del flujo común.

**Checks de seguridad para ship**
- No ejecutar módulos fuera del catálogo permitido.
- No sobreescribir logs sin control (rotación/tamaño).
- Manejo seguro de token por entorno/argumento sin exponerlo en logs.

---

### 5) Plan de trabajo (MVP primero)

**Estimación inicial**
- Diseño final + inventario scripts: 0.5–1 día.
- Implementación núcleo launcher v2: 1–1.5 días.
- Tests + hardening logging: 0.5–1 día.
- Documentación y transición: 0.5 día.

**Milestones**
1. **M1**: inventario definitivo de scripts y matriz de compatibilidad single/bulk.
2. **M2**: menú interactivo + selección por letra.
3. **M3**: resolvedor de input single/bulk + validaciones.
4. **M4**: logging troubleshooting acotado + trazas INFO.
5. **M5**: pruebas, ajustes y documentación final.

**Riesgos y alternativas**
- Riesgo: firmas de scripts heterogéneas.
  - Mitigación: `RunnerAdapter` con wrappers específicos mínimos.
- Riesgo: CSV con encabezados dispares.
  - Mitigación: validación previa de columnas requeridas por script.
- Riesgo: logs excesivos en bulk.
  - Mitigación: rotación y resumen de eventos repetitivos.

**Definition of Done**
- Requerido:
  - menú CLI,
  - selección script por letras,
  - modo single/bulk,
  - carga CSV según modo,
  - log troubleshooting limitado,
  - `LOGGER.info` en pasos clave.
- Opcional:
  - modo no interactivo con flags equivalentes,
  - export de resumen JSON de ejecución.

---

### 6) Ripple effects

- Actualizar documentación operativa para reemplazar comandos manuales por flujo launcher v2 cuando aplique.
- Comunicar al equipo qué scripts entran en launcher común y cuáles se mantienen como utilitarios especializados.
- Revisar automatizaciones CI/CD o wrappers internos que invoquen el launcher antiguo.

---

### 7) Contexto amplio y evolución

- Limitación actual: scripts con responsabilidades mezcladas (lógica de negocio + bootstrap CLI).
- Evolución propuesta: arquitectura modular donde launcher inyecta contexto y cada script conserva solo lógica específica.
- Extensiones futuras:
  - perfiles de ejecución por cliente/proyecto,
  - dry-run uniforme,
  - reintentos controlados,
  - panel de resultados agregado por lote.
- Idea moonshot: pipeline declarativo de transformaciones (DAG simple) configurable por YAML para ejecutar secuencias completas con validaciones automáticas.

