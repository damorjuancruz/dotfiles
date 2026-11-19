---
name: jira-time-tracker
description: Carga las horas trabajadas del día en Jira. Reconstruye la actividad (git, GitHub, Claude Code, T3 Code, Chrome, ERPNext, Outlook/Teams, documentos), deduce en qué incidencias se trabajó y arma una página de revisión interactiva (servidor local; en T3 Code se abre en el navegador integrado) donde el usuario confirma bloques, elige modos y comentarios, y decide incidencias nuevas, transiciones y comentarios de resolución; carga todo solo con su confirmación y apaga el servidor al terminar. Se puede correr varias veces en el mismo día (cada corrida retoma donde terminó la anterior). Usar cuando el usuario pida "cargá mis horas", "logueá horas en Jira", "imputá el día", "cierre del día", "cargá las horas de la mañana", "worklogs de hoy/ayer" o invoque /jira-time-tracker.
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

- `--date` y su valor van como dos argumentos. No los guardes juntos en una variable de shell
  (`D="--date X"` llega como un solo argumento y el script lo rechaza).
- Cada flag `--suggest` lleva una sola key: para varias, repetí el flag.

**Tandas.** El skill se puede correr varias veces en el mismo día, por ejemplo antes del
almuerzo y a la salida. Cada corrida es una tanda. Al terminar, `plan.py close` la archiva en
`<state>/runs/<n>/` (fase 6), y la tanda siguiente se planifica desde el corte de la última
cargada.

## Qué hacés vos y qué se delega

Vos (el modelo principal) hacés lo que necesita criterio: atribuir el tiempo, armar el plan,
interpretar las notas del usuario y redactar. Lo mecánico va a scripts o a subagentes:

- **Scripts:** recolección local, variantes, página, carga en Jira (`plan.py load`).
- **Subagentes Haiku:** las fuentes MCP (uno por fuente, fase 1) y cualquier búsqueda puntual
  que haga falta después, por ejemplo cuando el usuario pide revisar Teams o mails de un
  horario o de días anteriores, o una nueva consulta por la regla 9. Pasale qué buscar, el
  rango, que es solo lectura y que devuelva los mensajes con su texto. No hagas vos esas
  búsquedas.
- **Subagentes Sonnet:** la investigación de incidencias nuevas (fase 2).

**Herramientas:** al empezar, cargá en **una sola** llamada a ToolSearch las que usa el flujo,
no de a una: `select:Monitor,TaskStop` y, si existen, `preview_open`, `t3_preview_close` y
`t3_thread_organize` de T3 Code. Las de Jira y Microsoft 365 las cargan los subagentes que
las usan.

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
9. **Nunca negar actividad con datos posiblemente parciales.** Si el usuario pregunta (en una
   nota de la página o en el chat) si hubo actividad en un horario, y alguna fuente pudo
   haber quedado incompleta ahí (cobertura `partial` o `failed` en `raw/mcp_<fuente>.json`, o
   sin `coverage`), pedile a un subagente que vuelva a leer esa fuente para ese horario, desde
   30 minutos antes hasta 30 minutos después, como dice la fase 1 (en Teams, leyendo los
   chats). Los eventos nuevos se agregan a `raw/mcp_<fuente>.json` con los ids siguientes,
   deduplicados por id original, y se actualiza `coverage`. Si aun así queda incompleto, la respuesta lo dice: "no encontré mensajes,
   pero la consulta pudo quedar incompleta", nunca "no hubo mensajes".

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
   - **`TANDA N: planificar desde HH:MM`:** ya hubo tandas cargadas ese día. Esta tanda cubre
     solo desde esa hora hasta el corte. La línea de tiempo ya viene recortada, y los worklogs
     marcados `[tanda anterior]` no van en el plan. Si una tanda anterior descontó el almuerzo,
     el script no lo vuelve a ofrecer.
   - **`TANDA ABIERTA`:** quedó un plan sin cerrar. Según en qué estado quedó:
     - la revisión no terminó: retomala desde la fase 4 (`server.py start` y `Monitor`) sin
       reescribir el plan;
     - sus worklogs ya están entre los existentes del digest (se cargó pero no se cerró):
       `plan.py close --outcome load` y volvé a correr `collect.py`;
     - no se cargó nada y el usuario pidió empezar de nuevo: `plan.py close --outcome cancel`;
     - quedó a mitad de la carga: avisá en el chat qué falta y no sigas.
2. **Fuentes MCP: un subagente por fuente, en paralelo y en segundo plano.** Si el digest
   lista "Fuentes MCP a consultar", lanzá en **un solo mensaje** un Agent por cada fuente
   listada (`subagent_type: "general-purpose"`, `model: "haiku"`, en segundo plano), así
   corren a la vez y las respuestas grandes no entran a tu contexto. A cada uno pasale en el
   prompt: la fecha, el email del usuario (`jira.email`), el rango del día del digest (en una
   tanda siguiente, desde la hora de «planificar desde»), la ruta de destino
   `<state>/raw/mcp_<fuente>.json`, las instrucciones comunes de abajo y la sección de **su**
   fuente, completas:
   - Es **solo lectura**: no enviar, crear, modificar ni borrar nada.
   - Cargar las herramientas que va a usar con **una sola** llamada a ToolSearch
     (`select:` con todas juntas) y consultar la fuente como se describe abajo.
   - **Consultas en paralelo:** todas las consultas que no dependen entre sí van en un mismo
     mensaje: las lecturas de varios chats, las de varios mensajes (`read_resource`), las
     ventanas del buscador cuando se usa. Cada turno
     extra vuelve a leer todo lo acumulado: consultar de a una es más lento y más caro.
   - **Tanda siguiente del mismo día:** si el archivo de destino ya existe, leerlo, consultar
     solo desde la hora de «planificar desde», y agregar los eventos nuevos con los ids
     siguientes. En Teams, reutilizar el mapa de chats y el `context` que ya están, y buscar
     contexto solo de los chats nuevos.
   - **Listar, no buscar.** Teams y los mails se **leen como lista** (los chats y las carpetas
     del correo), no con el buscador: las búsquedas de Microsoft 365 (`chat_message_search`,
     `outlook_email_search` con `query`/`sender`/`recipient`, `sharepoint_search`) son un
     índice de búsqueda y no sirven para enumerar. Dicen `nextOffset` con 1 o 2 resultados,
     devuelven mensajes de fuera del horario pedido y omiten algunos que sí aparecen en otra
     consulta. El buscador queda solo para los casos que se indican abajo.
   - **Rango a cubrir:** desde 1 hora antes del inicio del rango del día hasta 1 hora después
     del final (sin rango: 07:00 a 21:00). Las fechas van siempre como ISO completo con hora y
     zona (`2026-11-12T14:00:00-03:00`): una fecha sola abarca el día entero.
   - **Deduplicar** por id del mensaje, evento o documento (si no viene id, por la URI del
     recurso). Nunca por texto u hora.
   - Fuentes:
     - `teams`, leyendo los chats:
       1. **Chats con actividad.** `teams_list_chats` con `limit: 25` devuelve los chats
          ordenados por su último mensaje, del más reciente al más viejo, con tema y miembros.
          Seguir `nextCursor` mientras haga falta. Para cada chat, leer sus mensajes con
          `read_resource` (`teams:///chats/{chatId}/messages`): devuelve los ~50 más
          recientes con autor, hora (`createdDateTime`, en UTC) y texto (`bodyPreview`). Leer
          los chats de a tandas, en paralelo. Cortar cuando aparece un chat cuyo mensaje más
          nuevo es anterior al inicio del rango: ese y los siguientes no tuvieron actividad.
          Máximo 40 chats leídos.
       2. **Mensajes del día:** los de cada chat dentro del rango, enviados (`from` = el
          usuario) y recibidos. Descartar mensajes de sistema (`messageType` distinto de
          `message`, `<systemEventMessage/>`) y los que solo tienen adjuntos o imágenes sin
          texto (anotarlos como «[adjunto]» si son lo único del grupo).
       3. **Nombre del chat:** el tema; en un 1:1, el otro miembro; en un grupo sin tema, los
          miembros. Nunca el id del chat.
       4. **Texto:** el de `bodyPreview` pasado a texto plano. Si termina en «...» (cortado) y es
          de trabajo, leer el mensaje completo con `read_resource`
          (`teams:///chats/{chatId}/messages/{messageId}`). Hasta 500 caracteres.
       5. Agrupar en un evento los mensajes del mismo chat sin cortes de más de 15 minutos.
       6. **Contexto de días anteriores:** de la misma lectura, los mensajes de los 7 días
          previos y del día siguiente de cada chat donde el usuario escribió ese día, hasta 15
          por chat (los más cercanos al día). Va en `context`, no en `events`.
       7. **Respaldo con el buscador:** solo si la lectura de un chat no llega hasta el inicio
          del rango (el chat tuvo más de ~50 mensajes después) o si se cortó en el máximo de
          40 chats. En ese caso, `chat_message_search` con `query: "*"`, `offset: 0`,
          `afterDateTime`/`beforeDateTime` del tramo que falta, partido en ventanas de 1 hora
          consultadas en paralelo, quedándose con los resultados de ese chat. Ese tramo queda
          en `coverage.incomplete` con el motivo «leído con el buscador», porque el buscador
          puede omitir mensajes.
       8. Cobertura `complete` si todos los chats con actividad se leyeron hasta el inicio del
          rango sin usar el respaldo.
     - `outlook`: `outlook_calendar_search` con `query: "*"`, `order: "oldest"`, `limit: 25`,
       `afterDateTime`/`beforeDateTime` del rango. Si llega a 25, partir el rango en dos y
       consultar cada mitad. Son reuniones; descartar las rechazadas o canceladas.
     - `mail`, leyendo las carpetas: `outlook_email_search` con `folderName: "Inbox"` y, aparte,
       `folderName: "Sent Items"`, cada una con `afterDateTime`/`beforeDateTime` del rango,
       `limit: 25` y **sin** `query`, `sender`, `recipient` ni `order` (así es una lista de la
       carpeta, no una búsqueda). Esta lista sí pagina bien: seguir `nextOffset` o
       `nextCursor` hasta el final (máximo 10 páginas por carpeta; si no se llega, cobertura
       parcial). Después:
       - Descartar notificaciones automáticas (Jira, GitHub, alertas de sistemas, newsletters,
         invitaciones de calendario): no son trabajo del usuario.
       - Agrupar en un evento los mails de la misma conversación sin cortes de más de 30
         minutos, con título `Mail con <persona>: <asunto> (N)` y los mensajes en
         `hints.messages` igual que Teams (`dir` `out` para Sent Items, `in` para Inbox).
       - Texto de hasta 500 caracteres; si viene cortado y es de trabajo, leer el mail con
         `read_resource` (`mail:///messages/{messageId}`).
       - Peso `normal` si el usuario mandó alguno, `weak` si solo recibió.
     - En Teams y en mails el texto va **plano**: sin etiquetas HTML, estilos ni imágenes, sin
       el historial citado de respuestas anteriores («De: … Enviado: …», «On … wrote:»), sin
       firmas ni avisos legales.
     - `sharepoint`: no hay forma de listar, así que va con el buscador: `sharepoint_search`
       con `query: "*"`, `author` = usuario, `limit: 50` y `offset: 0`, con el rango partido en
       ventanas de 2 horas consultadas en paralelo. Si una ventana llega a 50, partirla en dos.
       La cobertura lleva la nota «búsqueda: puede omitir documentos».
     - `google_drive`: `list_recent_files` con `orderBy: "lastModifiedByMe"`,
       `excludeContentSnippets: true` y `pageSize: 20`. Esta herramienta pagina con
       `nextPageToken`, que sí es confiable: seguir las páginas hasta encontrar un archivo
       modificado por el usuario antes del inicio del día (máximo 10 páginas; si no se llega,
       la cobertura es parcial). Quedarse con los modificados ese día. Si la fecha no es hoy,
       la cobertura lleva la nota "solo archivos cuya última modificación propia fue ese día":
       un archivo que se volvió a tocar después no aparece. Si la respuesta no trae la fecha
       de modificación propia, usar la última modificación de cualquiera y decirlo en `note`
       (no es un motivo para marcarla parcial).
   - Escribir el archivo con este formato:
     ```json
     {"source": "mcp",
      "events": [{"id": "teams:1", "source": "teams", "start": "ISO", "end": "ISO",
                  "title": "Chat con Natalia Bianchi (3 mensajes)", "detail": "...",
                  "hints": {"chat_id": "...", "with": "Natalia Bianchi", "msg_ids": ["..."],
                            "messages": [{"at": "ISO", "dir": "in", "from": "Natalia Bianchi",
                                          "text": "..."}]},
                  "weight": "normal"}],
      "context": {"teams": [{"chat_id": "...", "with": "Natalia Bianchi",
                             "messages": [{"at": "ISO", "dir": "out", "from": "yo", "text": "..."}]}]},
      "coverage": {"teams": {"status": "complete", "queries": 9, "chats_read": 7,
                             "incomplete": [{"start": "ISO", "end": "ISO", "reason": "leído con el buscador"}],
                             "error": null, "note": null}}}
     ```
     - Ids `outlook:N`, `mail:N`, `teams:N` y `docs:N`, numerados por hora después de deduplicar. El id
       original va en `hints.msg_ids` (Teams, todos los del grupo), `hints.event_id` (Outlook)
       o `hints.doc_id`.
     - Peso `strong` para reuniones, `normal` para los chats de Teams con algún mensaje de
       trabajo y `weak` para el resto. En `detail` va como máximo una frase: de qué trata el
       chat, el asunto de la reunión o el nombre del documento.
     - En Teams, `dir` es `out` (lo mandó el usuario) o `in` (lo recibió), y `from` es el
       nombre de quien lo mandó (`yo` para el usuario). Las horas van en la zona local (los
       `createdDateTime` de Teams vienen en UTC).
     - `coverage` lleva una entrada por cada fuente consultada. `status` es `complete` (se leyó
       todo el rango), `partial` (algún tramo pudo quedar incompleto, listado en `incomplete`) o
       `failed` (la fuente falló o no está autenticada, con el motivo en `error`).
     - Después de escribirlo, validarlo con `python -m json.tool <ruta> > /dev/null` y
       corregirlo si falla. Tiene que ser un solo objeto JSON, con `coverage` solo de su
       fuente.
   - Responder **solo** esto:
     - una línea por evento: `HH:MM–HH:MM fuente título {id}`;
     - debajo de cada evento de Teams o de mail, una línea por mensaje con su texto completo (hasta 500
       caracteres): `      HH:MM → Natalia Bianchi: texto` si lo mandó el usuario,
       `      HH:MM ← Natalia Bianchi: texto` si lo recibió;
     - una sección `Contexto de Teams (días anteriores)` con cada chat y sus mensajes en el
       mismo formato, con la fecha adelante (`DD/MM HH:MM`);
     - una línea de cobertura por fuente: `cobertura teams: completa (7 chats leídos, 9
       consultas)`, `cobertura teams: PARCIAL, 14:00–15:00 (motivo)` o `cobertura teams:
       FALLÓ (motivo)`.

     Nada más.

   **Mientras corren**, adelantá lo que no depende de ellos: anotá para cada evento local del
   digest (git, Claude/T3, ERPNext, GitHub, Chrome) a qué incidencia apunta, leé las
   candidatas y buscá si ya existen incidencias para los pedidos que veas. No agrupes, no
   repartas el tiempo ni escribas el plan hasta tener las respuestas de todos los
   subagentes: la fase 2 se hace con toda la información.

   Usá las respuestas como parte de la línea de tiempo. Leé los mensajes: dicen quién pidió
   qué, y de ahí salen la atribución, el texto del comentario y el Informador de las
   incidencias nuevas. La página también muestra esos eventos
   como evidencia, y `plan.py build` avisa en la página cada fuente con cobertura parcial o
   fallida.
3. **Cobertura parcial.** Si alguna fuente quedó parcial o falló:
   - no afirmes que no hubo mensajes, reuniones ni documentos en un horario que esa fuente
     no cubrió (ver la regla invariable 9);
   - decilo en la nota de la página (`build --note`), con la fuente y los horarios
     incompletos, para que el usuario sepa que puede faltar evidencia.

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
  - uso de la página de revisión de este skill (fuente `jtt`): tramos en que el usuario usó la
    página de verdad (mouse, teclado, scroll, con la pestaña visible), cortados cuando pasa un
    rato sin uso. Es el tiempo de revisar y cargar horas, del día que se hizo, aunque la
    revisión sea de otro día. Va a la subtarea "Gestión y comunicación" de `misc_issues`,
    salvo que las `agent_notes` digan otra cosa. La línea `sesión del skill {id}` indica qué
    sesión `cc` o `t3` corría el skill: su trabajo autónomo va a la misma incidencia, y el
    rato que esperó al usuario no cuenta (no hay eventos ahí);
  - commits "reescrito (amend/rebase)" y sesiones de "actividad git" del reflog. Muestran
    trabajo continuo en una branch aunque no haya commits nuevos: su rango horario cuenta como
    trabajo en la incidencia de esa branch.
- **Chats de Teams con mensajes de trabajo:** señal normal. Si un bloque de soporte, de
  Varias o sin incidencia clara coincide con un chat (del día o del contexto de días
  anteriores), la atribución sale de ese chat: quién pidió qué. Si el pedido no tiene
  incidencia, es candidato a una nueva con esa persona como Informador. El comentario
  describe lo que se pidió y se resolvió según los mensajes.
- **Señales débiles:** navegación, chats de Teams sin contenido de trabajo (saludos,
  confirmaciones sueltas) y documentos.
- **Sesiones de agente en paralelo** (cc, t3 y jtt, también las remotas): la línea de tiempo marca
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
- **Mails:** como Teams. Un mail de trabajo con contenido es señal normal: dice quién pidió
  qué, y sirve para atribuir, para el comentario y para el Informador.
- **Tiempo genérico** (mails sin tema identificable, Teams, gestión, soporte a compañeros, capacitación, entorno de
  desarrollo): a la subtarea que corresponda de `misc_issues`.
- **Contexto de las incidencias:** las candidatas con actividad en el día (●) traen un
  extracto de la descripción en el digest. Usá `getJiraIssue` solo si ese extracto no alcanza
  para decidir, y nunca para candidatas sin actividad.
- **Proyectos:** leé las `agent_notes` de cada proyecto (`digest.json` → `projects`).
- **Incidencia nueva:** si la actividad no encaja en ninguna existente, proponela en
  `new_issues` (con `ref: "NEW-1"`). La investigación es mecánica: **delegala** a un Agent
  (`subagent_type: "general-purpose"`, `model: "sonnet"`), uno por incidencia y todos en un
  mismo mensaje si son varias. Pasale qué se pidió y quién (con los ids de evidencia y los
  mensajes que lo muestran), el proyecto y el tipo probables, y los pasos 0 a 7 de abajo. Que
  devuelva solo: la key existente si encontró una que encaja (con el motivo), o el borrador en
  el formato de `plan.py new-issue` (sin `blocks`). Vos revisás el borrador, decidís y lo
  cargás. Los pasos:
  0. Antes de proponerla, buscar si ya existe: `searchJiraIssuesUsingJql` con palabras del
     pedido (persona afectada, sistema, cliente, módulo), sin filtrar por asignado ni por fecha.
     Si encontrás una que encaja, aunque esté asignada a otra persona, usala con un `warn`.
  1. Buscar 3 a 5 incidencias parecidas del mismo proyecto y tipo con
     `searchJiraIssuesUsingJql` (por palabras del resumen, mismo componente o mismo padre) y
     leer 2 o 3 con `getJiraIssue`.
  2. Consultar los campos del tipo con `getJiraIssueTypeMetaWithFields`.
  3. En `fields` va cada campo que en las parecidas se completa a mano, con el valor
     propuesto y, si es de selección, sus `options`. Los campos obligatorios van siempre.
  4. Quedan afuera los que tienen valor por defecto y no se suelen tocar (por ejemplo un campo
     de compañía que siempre es igual o que no aparece en la pantalla de Jira): Jira pone el
     default. El Informador es la excepción (punto 6).
  5. En `similar` van las keys usadas de referencia.
  6. **Informador:** va siempre, como campo `{"key": "reporter", "name": "Informador", "value":
     "<nombre>"}`. Es la persona que pidió el trabajo según la evidencia (mensaje de Teams, mail
     o reunión; si el pedido es de días anteriores, buscalo ahí). Si nadie lo pidió, es el
     usuario. En la página se edita como texto; el accountId lo resuelve `plan.py load` al
     crear (fase 5).
  7. El resumen y la descripción describen el pedido (qué se necesita y para quién, por ejemplo
     el empleado o el cliente afectado), pero **no nombran al solicitante** («a pedido de …»):
     eso lo dice el Informador.

  Para cambiar un borrador ya cargado (resumen, padre, campos, Informador) usá
  `plan.py edit "draft NEW-1 'summary=…' 'field.reporter=…'"`. No edites `plan.json` a mano.
  El mismo procedimiento vale para las incidencias nuevas que el usuario pide desde la página
  (fase 4). Esas se agregan con `plan.py new-issue`, no editando `plan.json`.

## Fase 3 — Plan y página

1. Escribí `<state>/plan.json` **una sola vez** (el formato está en el docstring de
   `plan.py`). Después, todo cambio se hace con `plan.py edit` y `plan.py comments`, nunca
   reescribiendo el JSON a mano (la única excepción es `variant_overrides`, ver el punto 4):
   - Horas locales `HH:MM`. Los `id` (`b1`, `g1`…) los asigna el script.
   - En una tanda siguiente, el plan cubre desde la hora de «planificar desde» hasta el corte.
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
     - `comments`: el mismo trabajo en tres niveles (`breve`, `normal` y `detallado`), con el
       formato de "Redacción de los comentarios", al final de esta fase.
     - `confidence`: alta, media o baja.
     - `sources`: abreviaturas `git`, `gh`, `cc`, `t3`, `jtt`, `chrome`, `erp`, `outlook`, `mail`,
       `teams`, `docs`, `jira`.
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
     Cuando el usuario pide otro texto para una fila, cargá la key exacta de esa fila (la que
     muestra el reporte de `review`, con `+` si es agrupada) y revisá que la key de los bloques
     sueltos no quede con el texto viejo si también aparece en otra variante.
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

### Redacción de los comentarios

Estas reglas valen para los tres niveles de cada bloque, para los comentarios de las filas
agrupadas y para los comentarios de resolución:

- Todo en español y en voz impersonal con "se" ("se migraron", "se corrigió"). Nunca en
  primera persona, ni mezclando las dos voces en un mismo comentario.
- Sin nombres de branches ni hashes de commit. Tampoco se habla de "commits" o "push": se
  describe el cambio que hicieron.
- No se nombran las herramientas con las que se hizo el trabajo (Claude Code, T3 Code,
  Claude in Chrome, la guía de revisión de T3) ni los skills, aunque el trabajo haya sido
  armar o mejorar un skill: se describe qué hace lo que se construyó.
- Solo lo que está en la evidencia. Si no se sabe por qué se hizo algo, no se escribe un motivo.
- Solo lo que corresponde a la incidencia. Quedan afuera las tareas accesorias (generar
  credenciales, pedir autorizaciones, sacar capturas de referencia), las etapas o fases de un
  plan interno y lo que fue de otro tema. Ante la duda, más genérico.

Cada nivel agrega información que el anterior no tiene. `normal` resume y `detallado` suma
detalle. Si `detallado` solo reparte las oraciones de `normal` en viñetas, le falta contenido.
Los ejemplos describen el mismo trabajo en los tres niveles:

- `breve`: una oración en una línea, con lo principal del bloque.
  > Se migraron los modelos a atributos de Laravel 13 y se quitó el symlink de
  > docker-compose.prod.yml.
- `normal`: una o dos oraciones cortas, con qué se hizo y dónde (el repo, el sistema o el
  módulo). Nombra los cambios sin enumerar cada archivo ni explicar motivos.
  > Se migraron los modelos de grainvision-web a atributos de Laravel 13 y se quitó el
  > symlink de docker-compose.prod.yml.
- `detallado`: una viñeta por cambio, con guion (`- `). Suma lo que `normal` omite: qué
  propiedades, archivos, componentes o pantallas se tocaron, por qué (si la evidencia lo
  dice), qué se probó y qué quedó pendiente.
  ```
  - Se reemplazaron las propiedades table, fillable y hidden por los atributos de Laravel 13 en todos los modelos de grainvision-web.
  - Se eliminó el symlink docker-compose.prod.yml porque el archivo es un contrato con el deploy y no puede depender de otro.
  - Se aplicaron a la migración los cambios del diff de Laravel 13 que afectan a los modelos.
  ```

Los comentarios de resolución siguen las mismas reglas, en prosa de 2 a 5 oraciones.

## Fase 4 — Revisión en la página

1. **Levantar el servidor** con `python $SKILL/scripts/server.py [--date ...] start`. Imprime la
   URL de la página, que incluye un token. Si ya hay un servidor activo para ese día, lo reusa.
2. **Abrir la página.** En T3 Code, abrí la URL con `preview_open` (ya cargada al empezar) en
   el navegador integrado. Si devuelve `visible: false`, la pestaña quedó abierta
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

   Nunca tengas dos `Monitor` del mismo `watch`: antes de armar otro, detené el anterior
   (TaskStop). Si el usuario avisa en el chat que reinició T3 Code o que cambió el código del
   skill, corré `server.py stop` y `server.py start`, volvé a abrir la preview y armá el
   `Monitor` de nuevo.

   El `Monitor` vence a los 30 minutos. Si todavía estás esperando, armalo otra vez con el mismo
   comando: `watch` recuerda qué eventos ya mostró (`<state>/server.offset`), así que ninguno se
   pierde ni se repite. Sin `Monitor`, usá Bash en segundo plano con `server.py wait`, que
   termina con el primer evento pendiente, y volvé a lanzarlo después de cada uno.
4. **Esperar.** El usuario revisa en la página: activa o desactiva agrupar y almuerzo,
   confirma filas, elige el nivel de cada comentario o edita el texto directamente (los
   niveles son textos sugeridos), edita el resumen y los campos de las incidencias nuevas, marca filas para absorber o para pasar
   a otra incidencia (existente o nueva), resuelve huecos, deja notas por fila o una general,
   decide las incidencias nuevas y prepara transiciones y comentarios de resolución de las
   existentes. Al terminar aprieta "Enviar a Claude", "Cargar en Jira" o "Cancelar". Si en
   lugar del evento llega un "listo" en el chat (la página se lo indica cuando el aviso tarda),
   corré `server.py status`, levantá el servidor si hace falta y seguí con el paso 5.
5. **Aplicar el estado** con `python $SKILL/scripts/plan.py review`, que lee lo que guardó la
   página en `<state>/page_state.json`.
   - Si responde "✗ el estado guardado … todavía no envió esta ronda", no se aplicó nada: seguí
     esperando el `ENVIADO`.

   El script aplica las confirmaciones, niveles, textos editados, modos, absorciones, cambios
   de incidencia, huecos, decisiones y campos de incidencias nuevas y seguimiento. Los textos
   que el usuario editó a mano se cargan tal cual: no los reescribas salvo que lo pida (cargar
   comentarios nuevos con `plan.py comments` para esa fila descarta su texto). Te devuelve:
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
   - **`load`:** si `review` dijo "Listo para cargar", seguí con la fase 5, aunque haya
     incidencias nuevas por crear: se crean en su primer paso. Si dijo "no se puede cargar
     todavía", tratala como `review` y explicá en la nota qué falta.

## Fase 5 — Carga

La carga la hace un script, no vos: no uses las herramientas de Jira para escribir worklogs,
crear incidencias ni aplicar transiciones, salvo para retomar una carga que falló (paso 3).

1. Correr `python $SKILL/scripts/plan.py [--date ...] load`. Solo corre si `review` aprobó la
   carga de esta ronda. Hace, en orden y por la API de Jira:
   - crea las incidencias nuevas con decisión "crear", asignadas al usuario, con los campos de
     la página. El Informador se busca por nombre y tiene que ser un usuario de Atlassian, no
     un cliente de Jira Service Management. Cada creada reemplaza a su NEW-n en el plan y queda
     anotada para la ronda de estado;
   - carga los worklogs de la variante elegida, con el comentario elegido o editado;
   - aplica las transiciones y los comentarios de resolución de las incidencias que ya
     existían;
   - verifica que los worklogs cargados aparezcan en Jira.

   Cada paso queda anotado en `<state>/load_log.json`.
2. Si termina con "Carga completa", seguí con el paso 4.
3. **Si se detiene** ("Carga detenida"), el reporte dice qué se hizo, qué paso falló y por
   qué. Retomá vos:
   - Si el error es de un dato que podés corregir sin decidir por el usuario (un campo con
     otro formato, una opción que Jira nombra distinto), corregilo con `plan.py edit` (por
     ejemplo `draft NEW-1 …`) y volvé a correr `plan.py load`: saltea lo hecho y sigue desde
     el paso que falló.
   - Si el script no puede hacer ese paso (por ejemplo, un tipo de campo que no sabe
     convertir), hacelo vos con la herramienta de Jira correspondiente y después corré
     `plan.py load` de nuevo para el resto. Si fue una creación, aplicá `plan.py edit
     "replace NEW-1 <KEY>"` antes de volver a correr.
   - Si hace falta una decisión del usuario (no hay un usuario claro para el Informador, Jira
     no deja cargar horas en esa incidencia por su estado o por permisos), mostrá en el chat
     qué se cargó y qué falta, preguntá, y no sigas hasta que responda.
4. **Estado de las incidencias creadas** (solo si se creó alguna): siempre en una ronda aparte,
   con las transiciones reales que Jira ofrece recién creada la incidencia.
   - `plan.py build --followup --suggest <KEY>=<transición> --note "..."`. Trae de Jira, sin
     caché, el estado y las transiciones de cada creada y las lista. Con `--suggest`
     preseleccionás la que más acerque al estado que sugiere la evidencia (resuelta, o al menos
     en progreso), por id, estado destino o nombre; si no coincide, avisa y no preselecciona
     nada. No deduzcas caminos de otras incidencias: solo vale lo que Jira devuelve ahora.
   - La página se recarga sola con la ronda nueva. Esperá el `ENVIADO` y aplicá el estado con
     `plan.py review`, igual que en la fase 4. Según la acción:
     - **`apply`:** `plan.py load` aplica las transiciones y comentarios; seguí al paso 5.
     - **`apply_more`:** `plan.py load` y volvé a correr `build --followup`, que trae las
       transiciones del nuevo estado. La página se recarga sola; esperá otra vez.
     - **`done`:** no se aplica nada más; seguí al paso 5.
5. Mostrá en el chat un resumen corto: incidencias (y las creadas), totales, total del día,
   transiciones y comentarios publicados.

## Fase 6 — Cierre

Se hace cuando el flujo terminó: con la carga hecha, con el usuario cancelando o con un error ya
informado que no vas a reintentar.

1. Detené el `Monitor` (TaskStop) y el servidor con `python $SKILL/scripts/server.py [--date ...] stop`.
2. Cerrá la tanda con `python $SKILL/scripts/plan.py [--date ...] close --outcome load` si se
   cargó en Jira, o `--outcome cancel` si no se cargó nada. Archiva el plan, la página y su
   estado en `<state>/runs/<n>/`, y la próxima corrida del día arranca en el corte de esta.
   También arma el resumen de métricas de la tanda (ver «Métricas»), así que cerrá siempre,
   también al cancelar. Si
   la carga quedó a medias por un error, no la cierres: el usuario decide cómo seguir.
3. En T3 Code, cerrá la pestaña de preview que abriste (`t3_preview_close`) y marcá este thread
   como resuelto: llamá a `t3_thread_organize` (ya cargada al empezar) con `action: "settle"`,
   sin `threadId` (T3 lo aplica al terminar el turno). Fuera de T3 Code esas herramientas no
   existen; no las menciones.

## Métricas

Los scripts registran métricas de cada tanda en `<state>/metrics.json` y, al cerrarla, agregan
un resumen a `<STATE_ROOT>/metrics.jsonl`: eventos por fuente y tiempos de recolección,
cobertura de las fuentes MCP, rondas y lo que el usuario hizo en cada una (cantidades, nunca
textos), la primera propuesta (`plan.r1.json`) comparada con lo cargado y desglosada por
confianza, resultado de la carga, y turnos y tokens de la sesión y de sus subagentes. No hace
falta hacer nada para que se registren.

Cuando el usuario pida revisar o mejorar el skill, empezá por
`python $SKILL/scripts/metrics.py report [--since AAAA-MM-DD]` (o `--json` para analizarlas
aparte) antes de leer transcripts.

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
