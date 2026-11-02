# jira-time-tracker

Skill de Claude Code para cargar las horas del día en Jira. Reconstruye la actividad
a partir de git, GitHub, transcripts de Claude Code, Chrome, ERPNext, Outlook/Teams y
documentos, propone bloques de tiempo y los carga **solo** después de que los confirmes.

- Los scripts (Python, solo stdlib) recolectan, normalizan, validan, calculan las variantes
  (agrupar / descontar almuerzo) y arman la página de revisión.
- El agente interpreta qué actividad corresponde a qué incidencia y redacta los comentarios.
- La revisión se hace en una página interactiva (artifact de claude.ai) que el agente publica,
  lee y borra al terminar. Requiere poder publicar artifacts desde la sesión.

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
