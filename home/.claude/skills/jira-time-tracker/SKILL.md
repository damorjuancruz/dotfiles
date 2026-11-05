---
name: jira-time-tracker
description: Carga las horas trabajadas del día en Jira. Reconstruye la actividad (git, GitHub, Claude Code, T3 Code, Chrome, ERPNext, Outlook/Teams, documentos), deduce en qué incidencias se trabajó y arma una página de revisión interactiva (servidor local; en T3 Code se abre en el navegador integrado) donde el usuario confirma bloques, elige modos y comentarios, y decide incidencias nuevas, transiciones y comentarios de resolución; carga todo solo con su confirmación y apaga el servidor al terminar. Usar cuando el usuario pida "cargá mis horas", "logueá horas en Jira", "imputá el día", "cierre del día", "worklogs de hoy/ayer" o invoque /jira-time-tracker.
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

1. **Toda la interacción con el usuario pasa por la página de revisión**, que sirve
   `server.py`. No uses AskUserQuestion ni le pidas decisiones en el chat. En el chat solo das
   el link, avisás en qué andás y mostrás errores o el resumen final.
2. **Nunca escribir en Jira sin que el usuario lo pida desde la página** ("Cargar en Jira", que
   llega como `ACCIÓN: load`, o "Aplicar" en la ronda de estado de las creadas, que llega como
   `ACCIÓN: apply` o `apply_more`). Eso cubre worklogs, incidencias nuevas, transiciones y
   comentarios, tal como quedaron en la página. Leer Jira sí está permitido.
3. **Nunca borrar ni cambiar de incidencia un worklog existente.** Solo se ajusta su horario
   (`action: "adjust"`), y solo si el usuario lo confirma.
4. **El HTML de la página sale siempre de `plan.py build`.** No lo escribas, no lo edites y no
   lo leas: `server.py` lo sirve tal cual.
5. Bloques nuevos: múltiplos de 5 minutos, mínimo 10, sin superponerse, cubriendo todo el
   rango del día. `plan.py validate` es la fuente de verdad.
6. **No supongas que una incidencia no admite horas por su estado.** Jira no expone eso de
   forma confiable (por ejemplo, en algunos proyectos "Listo" admite horas y "Completado" no).
   Solo lo das por hecho si un `addWorklogToJiraIssue` falla con un error que lo diga.
7. Respetar la deny-list: la navegación personal no se comenta. Toda la evidencia que no esté
   en la deny-list se muestra en la página tal cual, sin filtros adicionales.
8. Si el servidor no arranca (`server.py start` termina con ✗), **el flujo se corta**: mostrá
   el error de `<state>/server.err` y no sigas por otro medio.

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
- **Señales normales:**
  - sesiones de Claude Code (fuente `cc`, con cwd y branch). Las que corren dentro de T3 Code
    también son `cc`, pero traen el título del thread y `hints.t3_thread`; un `cc` sin ese hint
    es Claude Code directo y no hay que llamarlo thread de T3;
  - threads de T3 Code de otros proveedores (fuente `t3`);
  - lo mismo traído de máquinas remotas por SSH (fuente `remote` en el digest): los eventos
    conservan `git`, `cc` o `t3` y el título empieza con `[host]`;
  - ediciones en ERPNext y actividad en GitHub;
  - commits "reescrito (amend/rebase)" y sesiones de "actividad git" del reflog. Muestran
    trabajo continuo en una branch aunque no haya commits nuevos: su rango horario cuenta como
    trabajo en la incidencia de esa branch.
- **Señales débiles:** navegación, mensajes de Teams y documentos.
- **Sesiones de agente en paralelo** (cc y t3, también las remotas): la línea de tiempo marca
  en cada sesión sus tramos de `interacción` (los minutos previos a cada prompt tuyo), si es
  `autónoma` (sin prompts) y qué partes quedaron `tapada … por {id}`. El reparto es así:
  - el tiempo de interacción es de la incidencia de esa sesión;
  - el trabajo autónomo cuenta para su incidencia solo si en ese horario no hay interacción
    con otra sesión;
  - lo `tapada` es de la sesión que la tapa: no le des ese tiempo a la sesión autónoma;
  - con `interacción simultánea`, repartí ese tramo según los prompts de cada sesión;
  - si un bloque sale de un reparto entre sesiones en paralelo, avisalo en `warn`.
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
     - `sources`: abreviaturas `git`, `gh`, `cc`, `t3`, `chrome`, `erp`, `outlook`, `teams`,
       `docs`, `jira`.
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
     de la ventana configurada.
   - *Agrupar con almuerzo:* la mañana y la tarde se agrupan por separado, cada una
     intentando no repetir incidencias. Nunca se mueve trabajo de un lado al otro del
     almuerzo.
4. **Revisá el reporte de `build`**. Si una variante es poco verosímil (por ejemplo, horas en
   una incidencia antes de que se creara o después de que se cerró), escribí en `plan.json`
   solo la clave `variant_overrides` con esa variante corregida y volvé a correr `build`. Se usa
   solo si respeta los mismos totales y partes fijas; si no, el reporte avisa que la ignoró.
5. **Estado sugerido.** Al final del reporte de `build` hay una línea por cada incidencia que
   existe y tiene horas. Muestra el estado actual, los PRs vinculados, la transición sugerida o
   un aviso. Las sugerencias las calcula el script a partir del estado actual de Jira, GitHub
   y git, sin mirar la actividad de otros días:
   - **resolver**, si hay un PR mergeado o todas las subtareas están resueltas, y solo si el
     día que se carga es el último con actividad conocida (merge, commits propios con la key,
     worklogs). Si hubo actividad después, solo aparece un aviso con la fecha en que conviene
     resolverla;
   - **pasar a revisión**, si hay un PR abierto (no borrador);
   - **pasar a en curso**, si sigue sin empezar.

   La página las muestra como aviso con un botón "Usar sugerencia" y no preselecciona nada.
   No las repitas ni las discutas en el chat. Agregá una sugerencia propia solo si algo del día
   lo indica claramente y el script no lo ve, por ejemplo un prompt o mail que dice que el
   trabajo quedó cerrado sin PR: `build --suggest "KEY=<transición>:<motivo corto>"`. Si una
   sugerencia del script contradice la evidencia del día, reemplazala de la misma forma.

## Fase 4 — Revisión en la página

1. **Levantar el servidor** con `python $SKILL/scripts/server.py [--date ...] start`. Imprime la
   URL de la página, que incluye un token. Si ya hay un servidor activo para ese día, lo reusa.
2. **Abrir la página.** En T3 Code, cargá con ToolSearch la herramienta `preview_open` de T3 y
   abrí la URL en el navegador integrado. Si devuelve `visible: false`, la pestaña quedó abierta
   pero oculta: decile al usuario que abra el panel de preview. Fuera de T3 Code no abras el
   navegador vos. En los dos casos dale el link en una línea.
3. **Escuchar la página** con la herramienta `Monitor`: comando
   `python $SKILL/scripts/server.py [--date ...] watch`, `timeout_ms: 1800000` y descripción
   "pedidos de la página de revisión". Cada línea que imprime es un evento:
   - `ENVIADO ronda=N acción=X`: el usuario mandó la ronda. Seguí con el paso 5.
   - `PEDIDO aN comentario KEY`: la página pide un comentario de resolución para KEY. Leé el
     pedido con `server.py ask aN`, que trae el prompt con el trabajo del día y la evidencia.
     Redactá el comentario siguiendo ese prompt y respondé con:
     ```sh
     python $SKILL/scripts/server.py reply aN <<'EOF'
     texto del comentario
     EOF
     ```
     La página pone el texto en el campo apenas llega. No hace falta escribir nada en el chat.
   - `ERROR ...`: un error interno del servidor. Avisalo en el chat y seguí esperando.
   - `SERVIDOR CAÍDO` o `SERVIDOR DETENIDO`: corré `server.py start` y armá el `Monitor` de
     nuevo. El servidor vuelve en el mismo puerto y la página se reconecta sola.

   El `Monitor` vence a los 30 minutos. Si todavía estás esperando, armalo otra vez con el mismo
   comando: `watch` recuerda qué eventos ya mostró (`<state>/server.offset`), así que ninguno se
   pierde ni se repite. Sin `Monitor`, usá Bash en segundo plano con `server.py wait`, que
   termina con el primer evento pendiente, y volvé a lanzarlo después de cada uno.
4. **Esperar.** El usuario revisa en la página: activa o desactiva agrupar y almuerzo,
   confirma filas, elige el nivel de cada comentario, marca filas para absorber o para pasar
   a otra incidencia (existente o nueva), resuelve huecos, deja notas por fila o una general,
   decide las incidencias nuevas y prepara transiciones y comentarios de resolución de las
   existentes. Al terminar aprieta "Enviar a Claude", "Cargar en Jira" o "Cancelar". Si en
   lugar del evento llega un "listo" en el chat (la página se lo indica cuando el aviso tarda),
   corré `server.py status`, levantá el servidor si hace falta y seguí con el paso 5.
5. **Aplicar el estado** con `python $SKILL/scripts/plan.py review`, que lee lo que guardó la
   página en `<state>/page_state.json`.
   - Si responde "✗ el estado guardado … todavía no envió esta ronda", no se aplicó nada: seguí
     esperando el `ENVIADO`.

   El script aplica las confirmaciones, niveles, modos, absorciones, cambios de incidencia,
   huecos, decisiones de incidencias nuevas y seguimiento, y te devuelve:
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
6. Según la acción:
   - **`review`:** aplicá las notas, cargá los comentarios que falten y corré
     `plan.py build --note "<qué cambiaste y respuestas a sus notas, en 1 a 4 líneas>"`.
     La página se recarga sola con la versión nueva. Volvé al paso 4 con el mismo `Monitor`.
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
3. Si una operación falla, **parar**: mostrá en el chat qué se cargó y qué no, y no
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
   - La página se recarga sola con la ronda nueva. Esperá el `ENVIADO` y aplicá el estado con
     `plan.py review`, igual que en la fase 4. El reporte lista lo pendiente según la acción:
     - **`apply`:** aplicá las transiciones y comentarios (como en el paso 5) y seguí al paso 7.
     - **`apply_more`:** aplicalos y volvé a correr `build --followup`, que trae las
       transiciones del nuevo estado. La página se recarga sola; esperá otra vez.
     - **`done`:** no se aplica nada más; seguí al paso 7.
7. Mostrá en el chat un resumen corto: incidencias (y las creadas), totales, total del día,
   transiciones y comentarios publicados.

## Fase 6 — Cierre

Se hace cuando el flujo terminó: con la carga hecha, con el usuario cancelando o con un error ya
informado que no vas a reintentar.

1. Detené el `Monitor` (TaskStop) y el servidor con `python $SKILL/scripts/server.py [--date ...] stop`.
   El estado de la página queda en `<state>/` junto con el resto de los archivos del día.
2. En T3 Code, cerrá la pestaña de preview que abriste (`t3_preview_close`) y marcá este thread
   como resuelto: cargá con ToolSearch `t3_thread_organize` y llamala con `action: "settle"`,
   sin `threadId` (T3 lo aplica al terminar el turno). Fuera de T3 Code esas herramientas no
   existen; no las menciones.

## Modo setup

Se activa cuando falta `config.json` en `<.claude>/jira-time-tracker/`, dentro del `.claude` más
cercano que contiene este skill (o en `$JTL_CONFIG_DIR`). La ruta exacta la muestra
`setup.py check`. Es la única parte del skill que se conversa en el chat. Pasos:

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
