# SpaceOdT

Utilidad para exportar artefactos de espacios y dejar un resumen de estado por endpoint.

## Prerrequisitos

Antes de ejecutar, definí un token válido en la variable de entorno:

```bash
export WEBEX_ACCESS_TOKEN="<tu_token_webex>"
```

> `WEBEX_ACCESS_TOKEN` es obligatorio para autenticar todas las llamadas.

## Comando de ejecución

Ejecutá el proceso desde la raíz del repo:

```bash
python -m SpaceOdT
```

Si tu implementación usa un entrypoint distinto, reemplazá el comando por el script equivalente (por ejemplo `python SpaceOdT/main.py`).

## Exportes esperados

Una corrida exitosa genera estos artefactos:

- `status.csv`: estado por endpoint/objeto procesado.
- Archivos de export por recurso (por ejemplo JSON/CSV por endpoint consultado).
- Archivos vacíos cuando un recurso no es accesible o no está disponible (ver política abajo).

## Interpretación de `status.csv`

`status.csv` debe leerse como fuente de verdad del resultado técnico por endpoint:

- `403`: el token no tiene permisos/scope para ese endpoint o recurso.
- `404`: el recurso/endpoint no existe para ese tenant, usuario o configuración.
- `error`: fallo no mapeado a HTTP esperado (timeouts, errores de red, parseo, etc.).

Recomendación operativa:

- Si hay muchos `403`, revisar scopes del token.
- Si hay muchos `404`, validar si la feature aplica al tenant/objeto objetivo.
- Si hay `error`, reintentar y revisar logs para causa raíz.

## Política de archivos vacíos

Un archivo vacío **no** se interpreta como “sin datos” por defecto.

En SpaceOdT, la política es:

- **Archivo vacío = endpoint no accesible o no disponible**.

Por lo tanto, para diferenciar entre “sin datos” y “no accesible/no disponible”, siempre cruzar el archivo con `status.csv`.
