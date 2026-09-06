# chamnan — para que un repositorio se conozca a sí mismo

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Esta página no contiene ninguna cifra, a propósito. Todas las mediciones están en el README en inglés y cambian con cada versión; esta página no. → [Evidence](../../README.md#evidence)

## Qué es

Un plugin para Claude Code. Construye un índice del repositorio que el agente lee en lugar de recorrer los archivos uno a uno, y conserva el contexto de ingeniería que se acumula mientras trabajas: el estado del trabajo, los registros de sesión, las razones detrás de las decisiones y los procedimientos que vuelves a deducir cada vez.

Todo lo que escribe es markdown corriente, versionado junto al código. Sin llamadas de red en ejecución, sin base de datos, sin demonio, sin modelo de embeddings: solo la biblioteca estándar de Python.

## Qué resuelve

En cada sesión nueva, y cada vez que el contexto se compacta, desaparece todo lo que el agente había entendido de tu código y vuelve a buscar desde cero.

chamnan hace que ese redescubrimiento no tenga que ocurrir: el índice se entrega al empezar la sesión, y el coste es una cifra conocida y acotada en vez de lecturas de archivos sin límite.

## Instalación

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Abre una sesión nueva y ejecuta `/chamnan:bootstrap` una vez por repositorio.

<!-- generated: build_sections.py -->

## Todas las funciones

Cuatro capacidades. Todo lo que aparece abajo funciona de verdad en la versión actual. Cada parte se puede apagar por separado en `.chamnan/config.json`, y ninguna depende de otra.

### Entender — qué existe y qué está conectado con qué

| | |
|---|---|
| **Índice** | `MAP.md` — una línea por archivo, generada del propio código. El agente lee el índice y hace grep del detalle que necesita, en vez de recorrer todo el árbol. |
| **Impacto** | Quién depende de este archivo y qué pruebas lo cubren. Sus propios imports ya están arriba del archivo; lo caro es la arista inversa — haz grep de la ruta antes de cambiar nada. |
| **Modelo de datos** | Nombres de tablas y modelos con una línea de descripción, extraídos de DDL, migraciones y modelos ORM — no un volcado del esquema entero. Solo aparece si el repositorio define alguno. |
| **Superficie de API** | Método, ruta y manejador, desde decoradores de rutas, documentos OpenAPI y definiciones de servicio `.proto` — no la especificación completa. |
| **Configuración** | Los nombres de las variables de entorno que lee el repositorio. **Solo nombres, nunca valores** — y avisa si `.env` no está en gitignore. |
| **Despliegue** | Lo que de verdad se ejecuta, leído de manifiestos de Kubernetes, Ansible, Compose, Helm y CI: tipos y nombres, imágenes, roles, tuberías. De un Secret solo toma su nombre, nada de lo que hay debajo. |
| **Material que no es código** | Papeles escaneados, exportaciones, archivos comprimidos — solo cantidades, tamaños y extensiones dominantes. Existe para que el agente no vaya a mirar por su cuenta, lo que sale mucho más caro. **Nunca se abre, nunca se lee.** |

### Recordar — qué se estaba haciendo y por qué

| | |
|---|---|
| **Estado del trabajo** | `STATE.md` — aquello en lo que se trabaja ahora mismo; se inyecta al empezar la sesión para que la compactación del contexto deje de borrarlo. |
| **Registro de sesión** | Uno por sesión bajo `.chamnan/sessions/`. A la siguiente sesión llega **solo lo que quedó sin terminar**; una sesión cerrada en limpio no inyecta nada. |
| **Memoria** | `decisions/`, `lessons/`, `rules/`. Las reglas son restricciones permanentes, así que están delante del agente en cada sesión; decisiones y lecciones aportan solo un título y se leen cuando el título parece pertinente. |
| **Hilos abiertos** | Líneas de trabajo aún sin cerrar, con el historial de qué archivos ha tocado ese hilo — y lo siguen incluso después de renombrar el archivo. |

### Reutilizar — lo que ya se resolvió una vez

| | |
|---|---|
| **Procedimientos** | Habilidades que el agente escribe **por sí mismo** cuando topa con algo complejo o repetido. No es una biblioteca incluida, sino un mecanismo. |
| **Herramientas** | Nota que el mismo script desechable se ha vuelto a escribir y propone conservarlo — y lo recuerda antes de que escribas uno nuevo. |
| **Flujos de trabajo** | Nota que los mismos comandos corrieron en el mismo orden en días distintos, y propone dejar esa secuencia por escrito. |

### Acumular — lo que el repositorio ha aprendido sobre sí mismo

| | |
|---|---|
| **Hitos** | Los pocos cambios que rehicieron la forma del repositorio: qué se movió, por qué valía la pena, qué zonas tocó. |
| **Candidatos** | Las secuencias repetidas de comandos detectadas quedan **siempre a la espera de que una persona las confirme**. Nada asciende de forma automática. |
| **Entornos** | Declara qué es production o staging y qué está prohibido allí — y te avisa cuando esa declaración envejece. |
| **Informe** | Qué guarda el espacio de trabajo, si de verdad está al alcance, y cómo ha cambiado el contexto por turno en tu repositorio. Tu cifra, no la nuestra. |

El trabajo de ingeniería repetido se convierte en conocimiento reutilizable del repositorio — **no es entrenar un modelo ni automatizar al desarrollador.** Es un mecanismo para conservar un trabajo que, si no, solo existiría en la cabeza de quien lo hizo.

## Comandos

Todos se pueden invocar desde la shell, y el agente también los invoca por su cuenta.

| | |
|---|---|
| `chamnan-map` | construye y actualiza el índice |
| `chamnan-report` | qué guarda el espacio de trabajo y cómo ha cambiado el contexto por turno |
| `chamnan-impact` | quién depende de este archivo y qué pruebas lo cubren |
| `chamnan-timeline` | qué le ha pasado a este archivo hasta ahora |
| `chamnan-peek` | dice qué hay dentro de un archivo grande sin leerlo al contexto |
| `chamnan-promote` | conserva un script como herramienta permanente del repositorio |
| `chamnan-candidates` | ver, confirmar o descartar las repeticiones detectadas |
| `chamnan-env` | declarar un entorno y sus prohibiciones, y comprobar que la declaración sigue fresca |
| `chamnan-age` | dónde ha empezado a envejecer el conocimiento guardado |

Y las habilidades que se invocan desde dentro de la sesión: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Qué escribe, y dónde

Todo dentro de `.chamnan/`, markdown y JSON corrientes. Se puede leer, editar a mano y borrar en cualquier momento sin que se rompa nada.

| | |
|---|---|
| `MAP.md` | qué existe y qué depende de qué |
| `STATE.md` | en qué se trabaja ahora mismo |
| `sessions/` | dónde se detuvo el trabajo anterior |
| `memory/` | decisiones, lecciones y reglas permanentes |
| `threads/` | líneas de trabajo todavía abiertas |
| `skills/` · `tools/` | procedimientos y scripts que vale la pena guardar |
| `milestones.md` | los cambios que rehicieron la forma del repositorio |
| `config.json` | el encendido de cada parte y el techo en bytes del bloque inyectado en la sesión |

**La única escritura fuera de `.chamnan/`** es un hook de Git pre-commit opcional que mantiene el índice al paso del árbol — se instala solo si dices que sí, y se puede quitar.

**El agente no aprende.** Nada se entrena, nada queda fuera de este directorio, y la siguiente sesión sigue empezando de cero — solo que de cero *en un repositorio que se explica a sí mismo*. La continuidad está en los artefactos, no en el modelo.

## Seguridad

| | |
|---|---|
| **Ninguna llamada de red en ejecución** | Ni una. No hace falta clave de API y no se envía nada a ninguna parte. |
| **No reescribe tu código** | Informa, no edita. El índice copia los comentarios que ya escribiste, no se los inventa; los archivos sin comentario se nombran para que los completes tú. |
| **Sin demonio, sin trabajo en segundo plano** | Ningún proceso residente, ninguna base de datos, ningún modelo de embeddings — solo la biblioteca estándar de Python. |
| **Los secretos se filtran primero** | Todo lo que vaya a escribirse o a inyectarse en la sesión pasa antes por el filtro de secretos: quedan los *nombres* de las variables, no los valores. Y el límite al que ese filtro no llega está escrito junto a su propia cifra en el README en inglés. |
| **Qué puede hacerte un plugin instalado** | Explicado por completo en el README en inglés, incluido dónde chamnan corta la cadena de filtración. |

## Con qué funciona

chamnan es texto y Python de biblioteca estándar. Nada del índice pertenece a un proveedor, a un editor ni a un sistema operativo concretos.

| | |
|---|---|
| **Cualquier modelo, cualquier proveedor** | El índice es texto plano y se envía como contexto. El modelo solo cambia cuánto merece la pena enviar, nunca dónde va cada cosa. Ajusta el tamaño con `--model`, `--window` o `--profile`. Cambiar de modelo no obliga a reinstalar nada. `--model` reconoce estas familias por nombre: `claude` · `codestral` · `deepseek` · `fable` · `gemini` · `gemma` · `glm` · `gpt` · `grok` · `haiku` · `kimi` · `mistral` · `openai` · `opus` · `sonnet` — la comparación ignora mayúsculas, separadores y números de versión. `llama` y `qwen` quedan fuera a propósito: ambas se publican en varios tamaños que quieren presupuestos distintos, así que nombrarlas devuelve el perfil por defecto y una línea diciendo a qué dos tamaños podría referirse. **Un modelo que no esté en la lista sigue funcionando**: recibe el perfil por defecto y una nota de que no fue reconocido, y nada falla. `--window` toma el número directamente y siempre es exacto. |
| **macOS, Linux, Windows, WSL** | El mismo plugin en todas partes, solo biblioteca estándar, nada que instalar. En macOS y Linux los comandos se ejecutan directamente. En Windows el intérprete de comandos no puede ejecutar un script sin extensión, así que junto a cada comando y cada hook hay un `.cmd` generado; se distribuyen con el plugin y CI los ejecuta de verdad. WSL se comporta como Linux. |
| **Muchos agentes, un solo índice** | Claude Code lo recibe por un hook de sesión y no se escribe ningún archivo en tu proyecto. Gemini CLI también tiene un hook de sesión real. El resto de agentes recibe un archivo en la ruta que ese agente lee, y los que leen la misma ruta comparten el archivo en lugar de guardar cada uno una copia que se va desviando. |
| **Hermes Agent** | Hermes es además un plano de control que dirige otros agentes de código, así que un repositorio configurado para él suele significar varias herramientas leyendo el mismo índice. Busca las instrucciones del proyecto en un orden fijo y toma la primera que encuentra; chamnan escribe el archivo que encabeza ese orden, lo dimensiona según el límite que Hermes documenta y se niega a sobrescribir uno que no haya escrito él. |

## Cómo instalarlo

Por qué vía entras depende solo de si esa herramienta tiene un hook de sesión.

| | |
|---|---|
| **Claude Code** | Instálalo como plugin y ejecuta una vez el comando de arranque dentro de un repositorio. No se escribe nada en tu código, y a partir de ahí cada sesión empieza con el índice ya en contexto. |
| **Todo lo demás, Hermes incluido** | Pregunta primero qué ha detectado chamnan y luego dile para qué agente debe escribir. Cuando cambie la forma del repositorio, reconstruye el índice y vuelve a escribir el archivo; un hook de Git opcional hace ambas cosas al confirmar. No hace falta Claude Code: son comandos normales y el plugin es solo una vía de entrega, no el producto. Si no nombras un agente, imprime lo que ha detectado y el comando que lo configuraría, y te deja la decisión. Nunca escribe por suposición. |

Los nombres de los comandos, la lista completa de agentes y el archivo que recibe cada uno están en el README en inglés, donde vive todo detalle ligado a una versión.


## Requisitos

Claude Code · Python · Git · macOS, Linux o Windows

Nada más, y ninguna dependencia que instalar. La versión mínima de Python está en [README › Requirements](../../README.md#requirements) — esta página no lleva cifras, porque lo que cambia son las cifras.

## Apagar o quitar

Apaga por partes en `.chamnan/config.json` · deténlo en un solo repositorio · quita el plugin de toda la máquina · borra `.chamnan/` cuando quieras sin que se rompa nada — los pasos detallados en [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

## Léelo antes de instalar

**chamnan es para esa carpeta principal a la que vuelves una y otra vez.** Todo lo que hace se paga por adelantado y se cobra en las sesiones siguientes: en un repositorio que abres una sola vez, pagaste todo y no cobraste nada.

**Informa, no reescribe tu código.** El índice copia los comentarios que ya escribiste y no inventa ninguno. Los archivos sin comentario se nombran uno a uno para que los completes tú.

**Sus límites están medidos y escritos**, incluidas las mediciones que van en contra de su propia función principal.

## Dónde está el detalle

| | |
|---|---|
| Cada cifra, y cómo se midió | [README › Evidence](../../README.md#evidence) |
| Suite de pruebas de regresión — puedes ejecutarla tú | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Qué cambió en cada versión, y por qué | [CHANGELOG.md](../../CHANGELOG.md) |
| Todo lo demás | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
