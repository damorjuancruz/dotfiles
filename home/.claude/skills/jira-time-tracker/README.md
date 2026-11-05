# jira-time-tracker

Skill de Claude Code (también funciona en T3 Code) para cargar las horas del día en Jira. Reconstruye la actividad
a partir de git, GitHub, transcripts de Claude Code, threads de T3 Code (también de máquinas remotas por SSH, ver `sources.remote`), Chrome, ERPNext, Outlook/Teams y
documentos, propone bloques de tiempo y los carga **solo** después de que los confirmes.

- Los scripts (Python, solo stdlib) recolectan, normalizan, validan, calculan las variantes
  (agrupar / descontar almuerzo) y arman la página de revisión.
- El agente interpreta qué actividad corresponde a qué incidencia y redacta los comentarios.
- Para las incidencias con horas, el script sugiere un cambio de estado según el estado actual
  de Jira, GitHub y git: resolver si hay un PR mergeado y ese es el último día con actividad,
  pasar a revisión si hay un PR abierto, o a en curso si no se empezó. La página lo muestra como
  sugerencia; no se aplica sin que lo elijas.
- La revisión se hace en una página interactiva que sirve un servidor local (`scripts/server.py`,
  solo en `127.0.0.1` y con token). En T3 Code el agente la abre en el navegador integrado; en
  Claude Code te da el link. La página guarda cada cambio en el servidor, el agente se entera de
  los envíos siguiendo su log de eventos y la página se recarga sola cuando el agente arma una
  versión nueva. Al terminar, el agente apaga el servidor.

## Instalación

Ubicar el skill dentro de un `.claude` (por ejemplo `~/.claude/skills/jira-time-tracker`,
`~/cowork/.claude/skills/jira-time-tracker` o un skill sincronizado en
`~/.claude/skills/synced/<bucket>/jira-time-tracker`). Config, credenciales y estado se guardan en el `.claude` más cercano que lo contiene, en `<.claude>/jira-time-tracker/`:

```sh
mkdir -p ~/.claude/jira-time-tracker   # para ~/.claude/skills/jira-time-tracker
```

Si el skill no está dentro de ningún `.claude`, se usa `~/.config/jira-time-tracker/`.

Requisitos: Python ≥ 3.11, `git`, `gh` (autenticado), `sqlite3`.

La primera vez que se invoca el skill sin `config.json`, entra en **modo setup**: verifica
las dependencias y arma `<.claude>/jira-time-tracker/config.json` con vos (ver
`config.example.json`).

### Credenciales

Las credenciales se cargan **a mano** en `<.claude>/jira-time-tracker/.env`:

```sh
JIRA_API_TOKEN=...        # https://id.atlassian.com/manage-profile/security/api-tokens
ERPNEXT_API_KEY=...       # ERPNext → Mi configuración → Acceso API → Generar claves
ERPNEXT_API_SECRET=...
```

```sh
chmod 600 <.claude>/jira-time-tracker/.env
```

## Archivos

| Ruta | Contenido |
|---|---|
| `<.claude>/jira-time-tracker/config.json` | proyectos, estados excluidos, fuentes, reglas, modos de revisión |
| `<.claude>/jira-time-tracker/.env` | credenciales |
| `<.claude>/jira-time-tracker/state/<fecha>/` | datos crudos, digest, plan, estado de Jira y página de revisión del día |
| `<.claude>/jira-time-tracker/state/<fecha>/status_signals.json` | PRs vinculados y último commit de cada incidencia, para sugerir el estado |
| `<.claude>/jira-time-tracker/state/<fecha>/page_state.json` | lo que el usuario marcó en la página |
| `<.claude>/jira-time-tracker/state/<fecha>/server.*` | puerto y token (`server.json`), log de eventos para el agente (`server.log`) y errores (`server.err`) |
| `assets/review.html` | plantilla de la página de revisión (el script le inyecta los datos) |

### Modos de revisión

`review` en `config.json` define cómo abre la página (después se cambia con los toggles):

```json
"review": { "group": true, "lunch": true, "lunch_minutes": 30,
            "lunch_window": ["12:30", "14:00"], "comment_level": "normal" }
```

- **Agrupar:** junta el tiempo de cada incidencia en la menor cantidad de worklogs, respetando
  el total y sin mover reuniones, worklogs existentes, huecos ni salidas.
- **Descontar almuerzo:** deja `lunch_minutes` sin trabajar dentro de `lunch_window`. Se
  descuentan de la incidencia que cubre el tramo de menor actividad; si ya hay un hueco que
  alcanza, se usa ese.

Las rutas se pueden cambiar con `JTL_CONFIG_DIR` y `JTL_STATE_DIR`.

## Tests

```sh
python -m unittest discover -s tests -t .
```
