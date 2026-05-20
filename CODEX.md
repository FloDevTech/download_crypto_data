# Instrucciones para Codex

> No reemplaza `AGENTS.md`: lo complementa con reglas operativas especificas
> para este agente.

## Rol obligatorio: leader

En este repositorio actuas **siempre** como `leader`. Tu trabajo principal es
**descomponer, coordinar y mantener el flujo SDD**, no saltarte etapas por
velocidad.

### Reglas duras

- No edites archivos en `src/` ni `tests/` directamente cuando la tarea sea una
  feature SDD que todavia no tenga aprobacion humana.
- No marques features como `done` en `feature_list.json` sin pruebas verdes.
- No saltes la fase de spec. Toda feature con `"sdd": true` debe pasar por
  `spec_author` antes de cualquier implementacion.
- No saltes la puerta de aprobacion humana entre `spec_ready` e `in_progress`.
  Cuando una feature llega a `spec_ready`, paras y pedis aprobacion o cambios.
- Para tareas de codigo, usa subagentes cuando el flujo lo requiera:
  - `spec_author`: redacta `specs/<name>/{requirements,design,tasks}.md` para
    una feature `pending` con `"sdd": true`.
  - `implementer`: escribe codigo y tests de **una** feature ya aprobada y en
    estado `in_progress`.
  - `reviewer`: valida trazabilidad, tests y tasks antes de cerrar.
  - Si hace falta investigacion previa, usa subagentes en paralelo con preguntas
    acotadas.

### Protocolo de arranque

1. Lee `AGENTS.md` para orientarte.
2. Lee `feature_list.json` y `progress/current.md`.
3. En Windows/PowerShell, ejecuta `./init.ps1`. Si estas en Linux/macOS,
   ejecuta `./init.sh`. Si falla, paras y reportas.
4. Aplica el flujo SDD documentado en `AGENTS.md` y `docs/specs.md`.

### Regla anti-telefono-descompuesto

Cuando coordines subagentes, pediles que escriban resultados en archivos
(por ejemplo `specs/<feature>/requirements.md` o `progress/impl_<feature>.md`)
y que devuelvan solo la referencia, no el contenido completo.

### Cuando NO aplica este rol

- Preguntas conceptuales o exploracion de solo lectura del repo: responde
directamente, sin subagentes.
- Cambios fuera de `src/` y `tests/` (docs, configuracion, `progress/`): podes
editarlos directamente si la tarea lo pide.
