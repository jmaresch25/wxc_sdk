# SpaceOdT V1 — Scope (MVP)

## 1) Definición de lo que estamos construyendo

### Qué es
SpaceOdT V1 es una capa de consulta y exportación de información operativa, aislada en `SpaceOdT/`, para evitar acoplar decisiones de producto tempranas al resto del repositorio.

### Para quién es
- Equipo interno de operaciones/soporte.
- Stakeholders de producto que necesitan validar el modelo de datos y flujos sin riesgo sobre escritura.

### Qué problema resuelve
- Centraliza lectura de entidades clave para análisis y diagnóstico.
- Evita cambios destructivos al operar bajo política **read-only**.
- Permite validar rápidamente diseño e implementación en paralelo.

### Cómo va a funcionar (V1)
- `backend/`: endpoints/servicios de consulta (sin mutaciones).
- `frontend/`: visualización de listados y detalle de entidades.
- `cache/`: almacenamiento temporal para acelerar lecturas.
- `exports/`: generación de salidas (CSV/JSON) desde datos consultados.
- `docs/`: decisiones de alcance, contratos y notas técnicas.

### Principios de modelado (distilling the model)
- Priorizar MVP: empezar por los casos de lectura de mayor valor.
- El mejor refactor inicial es eliminar complejidad no esencial.
- Enfoque zoom out / zoom in: primero mapa general, luego detalle por módulo.

---

## 2) Diseño de experiencia de usuario (UX)

### User stories (happy + alternativas)
1. Como operador, quiero listar entidades clave para obtener visibilidad rápida del estado.
2. Como operador, quiero abrir detalle de una entidad para entender su contexto.
3. Como analista, quiero exportar resultados filtrados para análisis externo.
4. Flujo alternativo: si falla la red, mostrar estado degradado y reintento.
5. Flujo alternativo: si no hay datos, mostrar estado vacío explícito.

### Impacto en estructura UI
- Menú mínimo:
  - Dashboard / Listado
  - Detalle
  - Exportaciones
- Navegación simple: listado -> detalle -> volver al listado.

### Wireframe textual (MVP)
- Vista lista: filtros simples + tabla + acción “Exportar”.
- Vista detalle: metadatos + relaciones + historial básico consultable.

---

## 3) Necesidades técnicas

### Reglas y contrato V1
- **V1 es estrictamente solo lectura**: no se implementa create/update/delete.
- Validación de contrato mediante separación de rutas/servicios de lectura.

### Diseño técnico
- Preferencia por funciones pequeñas y composables.
- Inyección de dependencias (cliente API, cache, exportador) por argumentos.
- Abstracciones ligeras para proveedores de datos/cache/export.

### Datos y relaciones (alto nivel)
- Entidades principales:
  - Organización
  - Ubicación
  - Espacio
  - Persona/Usuario
  - Línea/Asignación
- Relaciones:
  - Organización 1..N Ubicaciones
  - Ubicación 1..N Espacios
  - Espacio N..N Personas (según pertenencia/asignación)
  - Persona 0..N Líneas

### Dependencias y librerías
- Reutilizar dependencias existentes del repositorio para cliente API y tests.
- Evitar incorporar nuevas dependencias hasta validar brechas reales del MVP.

### Edge cases documentados
- Error de red/transitorio en backend externo.
- Respuestas parciales o paginadas.
- Datos inconsistentes entre cache y fuente.

---

## 4) Testing y seguridad

### Cobertura objetivo
- Cobertura inicial enfocada en rutas críticas de lectura y exportación.

### Tipos de test
- Unit tests: parseo/mapeo de entidades y reglas de filtrado.
- Integración: lectura contra adaptadores de datos y cache.
- End-to-end liviano: flujo listado -> detalle -> exportación.

### Side-effects esperables
- Carga adicional de consultas sobre backend fuente (mitigar con cache).

### Seguridad para ship en V1
- Sin operaciones de escritura en la superficie expuesta.
- Sanitización de parámetros de filtro.
- Control de acceso a endpoints de lectura/exportación.
- Auditoría básica de accesos y exportaciones.

---

## 5) Plan de trabajo

### Estimación inicial (MVP)
- Día 1: estructura base y contratos read-only.
- Día 2: listado + detalle de entidades principales.
- Día 3: exportaciones + cache inicial.
- Día 4: pruebas, endurecimiento, documentación.

### Milestones
1. Estructura `SpaceOdT/` lista.
2. Primer flujo consultable extremo a extremo.
3. Exportación estable.
4. Cierre de documentación y criterios DoD.

### Riesgos y alternativas
- Riesgo: latencia/inestabilidad de API externa.
  - Mitigación: cache y reintentos acotados.
- Riesgo: ambigüedad de modelo de datos.
  - Mitigación: glosario + revisión temprana con stakeholders.

### Definition of Done
- Requerido:
  - Alcance V1 documentado y aprobado.
  - Flujos solo lectura funcionando.
  - Tests base para rutas críticas.
- Opcional:
  - Optimizaciones adicionales de cache y métricas avanzadas.

---

## 6) Ripple effects

- Actualizar documentación funcional y técnica de producto.
- Comunicar explícitamente el alcance read-only a usuarios internos.
- Alinear nomenclatura en equipos de frontend/backend/data.
- Preparar backlog V2 para mutaciones (sin mezclar en V1).

---

## 7) Contexto ampliado

### Limitaciones actuales
- V1 no contempla mutaciones ni automatizaciones operativas.
- Dependencia de sistemas externos para disponibilidad de datos.

### Extensiones futuras
- V2 con create/update/delete bajo permisos y auditoría reforzada.
- Alertas inteligentes y vistas agregadas por dominio.
- Integraciones adicionales con sistemas de reporting.

### Moonshot ideas
- Motor de recomendaciones operativas basado en patrones de uso.
- Simulador de impacto antes de cambios de configuración (what-if).

---

## 8) Alcance funcional V1

### 8.1 Incluido
- Consulta de entidades y relaciones clave.
- Visualización de listado y detalle.
- Exportación de datos consultados.

### 8.2 Excluido
- **8.2 Devices fuera de alcance en V1**.
- Cualquier operación create/update/delete.

---

## 9) Glosario corto (entidades y relaciones)

- **Organización**: contenedor principal de administración.
- **Ubicación**: unidad física/lógica dentro de una organización.
- **Espacio**: recurso operativo asociado a una ubicación.
- **Persona/Usuario**: actor humano asociado a espacios y líneas.
- **Línea/Asignación**: identidad o recurso de comunicación vinculado a persona/espacio.
- **Relación**: vínculo entre entidades para navegación, filtros y reporting.
