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
