---
name: jira-time-tracker
description: Carga las horas trabajadas del día en Jira. Reconstruye la actividad (git, GitHub, Claude Code, Chrome, ERPNext, Outlook/Teams, documentos), deduce en qué incidencias se trabajó y arma una página de revisión interactiva (artifact) donde el usuario confirma bloques, elige modos y comentarios, y decide incidencias nuevas, transiciones y comentarios de resolución; carga todo solo con su confirmación y borra la página al terminar. Usar cuando el usuario pida "cargá mis horas", "logueá horas en Jira", "imputá el día", "cierre del día", "worklogs de hoy/ayer" o invoque /jira-time-tracker.
---

# jira-time-tracker

Reconstruye el día de trabajo y carga worklogs en Jira. Los scripts (en `scripts/`, junto a
este archivo) juntan, validan, calculan las variantes y arman la página de revisión de forma
determinista. Vos (el agente) interpretás qué actividad corresponde a qué incidencia, redactás
los comentarios y aplicás lo que el usuario decide en la página.

`$SKILL` = directorio de este archivo (el "Base directory" que indica Claude Code al cargar el
skill). Correr siempre `python $SKILL/scripts/<script>.py`. Si el usuario pasó una fecha
(`AAAA-MM-DD`, "ayer", etc.), pasar `--date AAAA-MM-DD` a todos los scripts; si no, es hoy.
`<state>` = el directorio del digest que imprime `collect.py` (`.../state/<fecha>/`).

## Reglas invariables

1. **Toda la interacción con el usuario pasa por la página de revisión** (un artifact). No
   uses AskUserQuestion ni le pidas decisiones en el chat. En la terminal solo das el link,
   avisás en qué andás y mostrás errores o el resumen final.
2. **Nunca escribir en Jira sin que el usuario lo pida desde la página** ("Cargar en Jira", que
   llega como `ACCIÓN: load`, o "Aplicar" en la ronda de estado de las creadas, que llega como
   `ACCIÓN: apply` o `apply_more`). Eso cubre worklogs, incidencias nuevas, transiciones y
   comentarios, tal como quedaron en la página. Leer Jira sí está permitido.
3. **Nunca borrar ni cambiar de incidencia un worklog existente.** Solo se ajusta su horario
   (`action: "adjust"`), y solo si el usuario lo confirma.
4. **El HTML de la página sale siempre de `plan.py build`.** No lo escribas, no lo edites y no
   lo leas: publicá el archivo tal cual.
5. Bloques nuevos: múltiplos de 5 minutos, mínimo 10, sin superponerse, cubriendo todo el
   rango del día. `plan.py validate` es la fuente de verdad.
6. **No supongas que una incidencia no admite horas por su estado.** Jira no expone eso de
   forma confiable (por ejemplo, en algunos proyectos "Listo" admite horas y "Completado" no).
   Solo lo das por hecho si un `addWorklogToJiraIssue` falla con un error que lo diga.
7. Respetar la deny-list: la navegación personal no se comenta. Toda la evidencia que no esté
   en la deny-list se muestra en la página tal cual, sin filtros adicionales.
8. Si no se puede publicar el artifact (herramienta `Artifact` no disponible o publicación
   rechazada), **el flujo se corta**: avisalo y no sigas por otro medio.

## Fase 0 — Setup y chequeos

- Si cualquier script sale con código 3 y "No existe .../config.json", ir a **Modo setup**
  (al final) y volver acá cuando termine.
- Correr `python $SKILL/scripts/setup.py check`. Las líneas `✗` bloquean el flujo: explicá
  cómo resolverlas. Las `!` se avisan y se sigue: por ejemplo, sin ERPNext no hay checkin y
  la hora de entrada se toma de la primera actividad (avisalo en la nota de la página).

## Fase 1 — Recolección

1. Correr `python $SKILL/scripts/collect.py [--date ...]`. Imprime el **digest**, que es tu
   insumo principal: rango del día, estado de cada fuente, worklogs existentes, candidatas y
   línea de tiempo con ids de evento entre llaves.
2. **Fuentes MCP, mediante un subagente.** Si el digest lista "Fuentes MCP a consultar",
   delegá la consulta con la herramienta Agent (`subagent_type: "general-purpose"`,
   `model: "haiku"`), así las respuestas grandes no entran a tu contexto. Pasale en el prompt:
   la fecha, el email del usuario (`jira.email`), la ruta de destino `<state>/raw/mcp.json` y
   estas instrucciones:
   - Es **solo lectura**: no enviar, crear, modificar ni borrar nada.
   - Cargar las herramientas con ToolSearch y consultar, acotado al día:
     - `outlook`: `outlook_calendar_search` con `query: "*"`, `afterDateTime`/`beforeDateTime`
       del día y `limit: 25`. Son reuniones; descartar las rechazadas o canceladas.
     - `teams`: `chat_message_search` con `query: "*"`, `sender` = email del usuario y rango
       del día.
     - `sharepoint`: `sharepoint_search` con `query: "*"`, `author` = usuario y
       `afterDateTime` = el día.
     - `google_drive`: `list_recent_files` con `orderBy: "lastModifiedByMe"`,
       `excludeContentSnippets: true` y `pageSize: 20`; solo los modificados ese día.
   - Escribir el archivo con este formato:
     `{"source": "mcp", "events": [{"id": "outlook:1", "source": "outlook", "start": ISO, "end": ISO, "title": "...", "detail": "...", "hints": {...}, "weight": "strong|weak"}]}`.
     Ids `outlook:N`, `teams:N` y `docs:N`. Peso `strong` para reuniones, `weak` para el resto.
     En `detail` va como máximo una frase: asunto, participantes o nombre del documento.
   - Responder **solo** una línea por evento (`HH:MM–HH:MM fuente título {id}`) y una línea
     por fuente que haya fallado o no esté autenticada. Nada más.

   Usá esa respuesta como parte de la línea de tiempo. La página también muestra esos eventos
   como evidencia.

## Fase 2 — Atribución

Objetivo: **minutos totales por incidencia** a lo largo del día. Criterios, en orden de peso:

- **Señales fuertes:**
  - key explícita en branch, commit, PR, título de sesión de Claude Code o URL de Jira;
  - reuniones del calendario;
  - comentarios o cambios de estado del usuario en Jira (fuente `jira`).
- **Señales normales:** sesiones de Claude Code (cwd y branch), ediciones en ERPNext,
  actividad en GitHub, commits "reescrito (amend/rebase)" y sesiones de "actividad git" del
  reflog. Estas sesiones muestran trabajo continuo en una branch aunque no haya commits
  nuevos: su rango horario cuenta como trabajo en la incidencia de esa branch.
- **Señales débiles:** navegación, mensajes de Teams y documentos.
- **Branches sin key:** deducí la incidencia por el repo, la descripción de las candidatas y
  el resto de la actividad. Si no alcanza, proponé la mejor opción con confianza baja y un
  `warn` que lo explique; el usuario lo corrige desde la página.
- **Prioridad de candidatas:** primero las asignadas al usuario (★); después las que tocó en
  los últimos días; después cualquier otra. Las marcadas con ✗ (estado excluido) **no se
  proponen**.
- **Reviews de PR:** van a la incidencia del código revisado (key del PR o branch), aunque esté
  asignada a otra persona; marcalo en `warn` para que el usuario lo vea. Si no hay key, van a
  la subtarea "Revisión de código" de `misc_issues`.
- **Reuniones:** van a la incidencia identificable por asunto o participantes. Si no hay, a la
  subtarea "Reuniones".
- **Tiempo genérico** (mails, Teams, gestión, soporte a compañeros, capacitación, entorno de
  desarrollo): a la subtarea que corresponda de `misc_issues`.
- **Contexto de las incidencias:** las candidatas con actividad en el día (●) traen un
  extracto de la descripción en el digest. Usá `getJiraIssue` solo si ese extracto no alcanza
  para decidir, y nunca para candidatas sin actividad.
- **Proyectos:** leé las `agent_notes` de cada proyecto (`digest.json` → `projects`).
- **Incidencia nueva:** si la actividad no encaja en ninguna existente, proponela en
  `new_issues` (con `ref: "NEW-1"`) y completá sus campos así:
  1. Buscá 3 a 5 incidencias parecidas del mismo proyecto y tipo con
     `searchJiraIssuesUsingJql` (por palabras del resumen, mismo componente o mismo padre) y
     leé 2 o 3 con `getJiraIssue`.
  2. Consultá los campos del tipo con `getJiraIssueTypeMetaWithFields`.
  3. En `fields` poné cada campo que en las parecidas se completa a mano, con el valor
     propuesto y, si es de selección, sus `options`. Los campos obligatorios van siempre.
  4. Dejá afuera los que tienen valor por defecto y no se suelen tocar (por ejemplo un campo
     de compañía que siempre es igual o que no aparece en la pantalla de Jira): Jira pone el
     default.
  5. En `similar` van las keys que usaste de referencia.

  El mismo procedimiento vale para las incidencias nuevas que el usuario pide desde la página
  (fase 4). Esas se agregan con `plan.py new-issue`, no editando `plan.json`.

## Fase 3 — Plan y página

1. Escribí `<state>/plan.json` **una sola vez** (el formato está en el docstring de
   `plan.py`). Después, todo cambio se hace con `plan.py edit` y `plan.py comments`, nunca
   reescribiendo el JSON a mano (la única excepción es `variant_overrides`, ver el punto 4):
   - Horas locales `HH:MM`. Los `id` (`b1`, `g1`…) los asigna el script.
   - Cada worklog existente del digest aparece **una vez**, como `existing` (sin cambios) o
     como `adjust` (nuevo horario, con `worklog_id`), con su `comment` original. Si un
     existente no está alineado a 5 minutos, proponé un `adjust` que lo alinee.
   - Las **reuniones** llevan `"fixed": true`: no se mueven al agrupar ni reciben el almuerzo.
   - El plan base sigue la cronología real. No lo consolides vos: el modo agrupar lo hace el
     script.
   - Toda incidencia con actividad **significativa** (resuelta, comentada, con commit o con
     cambio de estado) recibe al menos un bloque de 10 minutos, aunque haya sido menos.
   - Solo se absorbe el **ruido**, es decir, actividad sin evidencia de trabajo real (abrir
     un ticket un minuto). Va en `absorbed`.
   - **Huecos:** los tramos sin actividad van a `gaps` como `kind: "open"`.
   - **Sin checkin:** poné `start` en el plan con la hora de la primera actividad.
   - Cada bloque nuevo lleva:
     - `comments`: el mismo trabajo en tres niveles, en español: `breve` (una línea corta),
       `normal` (una o dos oraciones) y `detallado` (bitácora técnica: qué se hizo, dónde y
       por qué). Sin inventar nada que no esté en la evidencia.
     - `confidence`: alta, media o baja.
     - `sources`: abreviaturas `git`, `gh`, `cc`, `chrome`, `erp`, `outlook`, `teams`, `docs`,
       `jira`.
     - `evidence`: los ids de evento que lo respaldan (la página los muestra al expandir).
     - `warn`: lo que haya que destacar.
     - `confirmed`: no se pone; lo marca el usuario en la página.
2. Correr `plan.py build`. Valida el plan, calcula las cuatro variantes (con y sin agrupar,
   con y sin almuerzo), revisa que todas respeten los totales y las partes fijas, trae el estado
   y las transiciones disponibles de cada incidencia, y genera `<state>/review.html`.
   - Si hay errores (✗), corregí el plan con `edit` y repetí.
   - Si dice **"Faltan comentarios"**, cargalos todos juntos y repetí `build`:
     ```sh
     python $SKILL/scripts/plan.py comments <<'EOF'
     {"b7": {"breve": "...", "normal": "...", "detallado": "..."},
      "b2+b5": {"breve": "...", "normal": "...", "detallado": "..."}}
     EOF
     ```
     Las keys con `+` son filas agrupadas: el comentario combina el trabajo de esos bloques
     (el reporte lista el comentario normal de cada uno) en un texto coherente y sin repetir.
3. **Cómo se arman las variantes** (para entender el reporte, no para recalcularlas):
   - *Agrupar:* dentro de cada tramo entre partes fijas, un bloque por incidencia; entre
     tramos se intercambia tiempo mientras baje la cantidad de worklogs. Los totales no
     cambian.
   - *Almuerzo:* si un hueco ya cubre el almuerzo dentro de la ventana, se usa ese hueco y no
     se descuenta nada. Si no, se descuentan los minutos de la ventana de menor actividad, de
     los bloques que la cubren (repartido si son varios), y el hueco queda en algún momento
     de la ventana configurada, aunque al agrupar esa incidencia quede en otro horario.
4. **Revisá el reporte de `build`**. Si una variante es poco verosímil (por ejemplo, horas en
   una incidencia antes de que se creara o después de que se cerró), escribí en `plan.json`
   solo la clave `variant_overrides` con esa variante corregida y volvé a correr `build`. Se usa
   solo si respeta los mismos totales y partes fijas; si no, el reporte avisa que la ignoró.

## Fase 4 — Revisión en la página

1. **Publicar** con la herramienta `Artifact`: `file_path` = `<state>/review.html`,
   `icon: "clock"`, una `description` de una oración y
   `capabilities: {"db": {}, "comments": {}, "sample": {}}`. Guardá la URL con
   `plan.py url <URL>` y dale al usuario el link en una línea.
   Si el resultado no confirma que la sesión quedó mirando el artifact, agregá en esa línea
   que, al terminar, escriba "listo" en la terminal.
2. **Esperar.** El usuario revisa en la página: activa o desactiva agrupar y almuerzo,
   confirma filas, elige el nivel de cada comentario, marca filas para absorber o para pasar
   a otra incidencia (existente o nueva), resuelve huecos, deja notas por fila o una general,
   decide las incidencias nuevas y prepara transiciones y comentarios de resolución de las
   existentes. Al terminar aprieta "Enviar a Claude", "Cargar en
   Jira" o "Cancelar". Te enteras de dos formas: llega un comentario de la página enviado a
   Claude, o el usuario escribe "listo" en la terminal. No hace falta responder en el hilo del
   comentario.
3. **Leer el estado** con `ArtifactData` (cargala con ToolSearch si hace falta):
   `action: "get"`, la `url`, `collection: "review"`, `doc_id: "state"` y como `out_dir` un
   directorio de tu **scratchpad** de la sesión (nunca `<state>`: está dentro de `.claude` y
   la herramienta no puede escribir ahí). Si no tenés scratchpad, omití `out_dir` y pasale a
   `plan.py review` el JSON que devuelve por stdin con un heredoc. Después aplicarlo:
   `plan.py review <archivo>`, con la ruta que indique el resultado de `ArtifactData`.
   - Si responde "✗ el estado guardado … volvé a leerlo", la página todavía estaba guardando
     cuando llegó el aviso: esperá unos segundos y repetí la lectura (no se aplicó nada).
   - El usuario también puede avisar escribiendo "listo" si el aviso de la página no llegó
     (la página se lo indica).

   El script aplica las confirmaciones, niveles, modos,
   absorciones, cambios de incidencia, huecos, decisiones de incidencias nuevas y seguimiento,
   y te devuelve:
   - las **notas del usuario** con el contexto de cada fila: interpretalas y aplicalas con
     `plan.py edit` (ver `plan.py edit --help`; las filas se nombran por id, `b3` o `g1`) o con
     `plan.py comments` si piden otro texto;
   - las **incidencias nuevas pedidas** ("nueva 1 → b3, b5: «indicaciones»"): armá cada
     borrador como en la fase 2 (incidencias parecidas, campos del tipo) y cargalo con los
     bloques que indica el reporte:
     ```sh
     python $SKILL/scripts/plan.py new-issue <<'EOF'
     {"project": "SIT", "type": "Tarea", "summary": "...", "similar": ["SIT-1"],
      "fields": [{"key": "description", "name": "Descripción", "value": "..."}],
      "blocks": ["b3", "b5"]}
     EOF
     ```
   - los comentarios que faltan (de bloques nuevos o de grupos nuevos);
   - la `ACCIÓN` que eligió el usuario.
4. Según la acción:
   - **`review`:** aplicá las notas, cargá los comentarios que falten y corré
     `plan.py build --note "<qué cambiaste y respuestas a sus notas, en 1 a 4 líneas>"`.
     Volvé a publicar con el **mismo `file_path`** (sin `icon` ni `capabilities`, así conserva
     las que tiene) y volvé al paso 2. Si ya no tenés la publicación en esta conversación,
     leé el artifact con `Artifact action: "read"` y la URL guardada en `plan.json`
     (`artifact_url`), y publicá con esa `url`.
   - **`cancel`:** no se escribe nada en Jira. Pasá a la fase 6.
   - **`load`:** si `review` dijo "no se puede cargar todavía", tratala como `review` y
     explicá en la nota qué falta. Si dijo "Listo para cargar", seguí con la fase 5.

## Fase 5 — Carga

Seguí el orden de la lista "Pendiente en Jira" que imprime `review`:

1. **Incidencias nuevas** con decisión "crear": `createJiraIssue` con los campos tal como
   quedaron en la página, `assignee_account_id` = `jira.account_id` y `parent` si es subtarea.
   Después, `plan.py edit "replace NEW-1 <KEY>"` por cada una (el script las anota como
   creadas para la ronda de estado). No les cambies el estado en este paso.
2. **Worklogs:** `plan.py ops` devuelve las operaciones de la variante elegida, con el
   comentario del nivel elegido. Ejecutá cada una, en orden, con `addWorklogToJiraIssue`:
   `cloudId`, `issueIdOrKey`, `started`, `timeSpent`, `commentBody` (si está vacío, no lo
   mandes) y `contentFormat: "markdown"`. Para `op: "update"`, pasá también `worklogId`.
3. Si una operación falla, **parar**: mostrá en la terminal qué se cargó y qué no, y no
   reintentes sin que el usuario lo pida.
4. Verificar con `collect.py --refresh jira [--date ...]`: los worklogs del digest tienen que
   coincidir con lo cargado.
5. **Seguimiento** de las incidencias que ya existían, recién después de cargar las horas:
   - transiciones con `transitionJiraIssue`, usando el id de transición y, si hay campos
     (por ejemplo `resolution`), `fields: {"resolution": {"name": "..."}}`;
   - comentarios de resolución marcados para publicar con `addCommentToJiraIssue`, con el
     texto exacto de la página.
6. **Estado de las incidencias creadas** (solo si se creó alguna): siempre en una ronda aparte,
   con las transiciones reales que Jira ofrece recién creada la incidencia.
   - `plan.py build --followup --suggest <KEY>=<transición> --note "..."`. Trae de Jira, sin
     caché, el estado y las transiciones de cada creada y las lista. Con `--suggest`
     preseleccionás la que más acerque al estado que sugiere la evidencia (resuelta, o al menos
     en progreso), por id, estado destino o nombre; si no coincide, avisa y no preselecciona
     nada. No deduzcas caminos de otras incidencias: solo vale lo que Jira devuelve ahora.
   - Republicá con el mismo `file_path`, esperá y leé el estado igual que en la fase 4.
     `plan.py review` lista lo pendiente según la acción:
     - **`apply`:** aplicá las transiciones y comentarios (como en el paso 5) y seguí al paso 7.
     - **`apply_more`:** aplicalos y volvé a correr `build --followup`, que trae las
       transiciones del nuevo estado; republicá y esperá otra vez.
     - **`done`:** no se aplica nada más; seguí al paso 7.
7. Mostrá en la terminal un resumen corto: incidencias (y las creadas), totales, total del día,
   transiciones y comentarios publicados.

## Fase 6 — Cierre

Borrá el artifact con `Artifact` (`action: "delete"`, la `url` de `plan.json`), también si el
usuario canceló o si la carga se cortó por un error después de informarlo. La página no debe
quedar en la cuenta del usuario.

## Modo setup

Se activa cuando falta `config.json` en `<.claude>/jira-time-tracker/`, dentro del `.claude` más
cercano que contiene este skill (o en `$JTL_CONFIG_DIR`). La ruta exacta la muestra
`setup.py check`. Es la única parte del skill que se conversa en la terminal. Pasos:

1. `python $SKILL/scripts/setup.py check`: informar dependencias y credenciales faltantes.
2. Pedir al usuario los proyectos Jira a usar y el sitio y email de Atlassian, si no se
   deducen. Si la `cloudId` no se conoce, obtenerla con `getAccessibleAtlassianResources`.
3. `python $SKILL/scripts/setup.py discover --projects A,B --site ... --email ...`: propone un
   config y lista datos locales (emails de commits recientes, top de dominios de Chrome).
   - Sin `JIRA_API_TOKEN`, completar `account_id` con `atlassianUserInfo` y los estados de
     cada proyecto con `searchJiraIssuesUsingJql`, recorriendo los `status` distintos con su
     `statusCategory`. Todo esto es solo lectura.
   - Preguntar cuáles de los `recent_commit_emails` son del usuario: el resto son de
     compañeros.
   - Proponer `excluded_statuses`: los estados que, sin ser categoría Done, signifiquen
     terminado.
   - Definir con el usuario las `agent_notes` de cada proyecto y los valores de `review`
     (agrupar y almuerzo activados al abrir la página, duración y ventana del almuerzo, nivel
     de comentario por defecto).
   - Proponer agregar a `deny_domains` los dominios personales del top de Chrome.
4. Mostrar el config final y, **con confirmación**, escribirlo en `config.json`.
5. Credenciales: indicar al usuario que cargue a mano `JIRA_API_TOKEN`, `ERPNEXT_API_KEY` y
   `ERPNEXT_API_SECRET` en `.env` y lo deje en `chmod 600` (ver README). **Nunca pedirle que
   pegue secretos en el chat.**
6. **Tareas Varias** (si `misc_issues` está vacío): ofrecer crear, en el proyecto que elija el
   usuario:
   - la tarea padre "Tareas Varias - <Nombre Completo>", asignada al usuario;
   - las subtareas "Tareas Varias - <Nombre Completo> - X", con X: Reuniones, Revisión de
     código, Soporte a compañeros, Gestión y comunicación, Capacitación / investigación,
     Entorno de desarrollo / infraestructura y Otras.

   Primero mostrar la lista, y crear solo con confirmación. Después registrar las keys en
   `misc_issues`.
7. Volver a correr `setup.py check`.
