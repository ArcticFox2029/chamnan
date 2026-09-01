# chamnan — damit ein Repository sich selbst kennt

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Diese Seite enthält bewusst keine Zahlen. Alle Messwerte stehen in der englischen README und ändern sich mit jedem Release; diese Seite nicht. → [Evidence](../../README.md#evidence)

## Was das ist

Ein Claude-Code-Plugin. Es baut einen Index des Repositories, den der Agent liest, statt Dateien einzeln zu durchsuchen, und bewahrt den technischen Kontext, der sich beim Arbeiten ansammelt — Arbeitsstand, Sitzungsnotizen, die Gründe hinter Entscheidungen und die Abläufe, die man jedes Mal neu herleitet.

Alles, was es schreibt, ist einfaches Markdown, neben dem Code eingecheckt. Kein Netzwerkaufruf zur Laufzeit, keine Datenbank, kein Daemon, kein Embedding-Modell — nur die Python-Standardbibliothek.

## Was es löst

Mit jeder neuen Sitzung, und jedes Mal wenn der Kontext komprimiert wird, ist alles verloren, was der Agent über deine Codebasis herausgefunden hatte — und er fängt wieder bei der Suche an.

chamnan sorgt dafür, dass dieses Wiederentdecken gar nicht erst nötig wird: Der Index liegt zu Sitzungsbeginn vor, und der Preis ist eine bekannte, begrenzte Zahl statt unbegrenzter Dateizugriffe.

## Installation

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Öffne eine neue Sitzung und führe `/chamnan:bootstrap` einmal pro Repository aus.

## Vor der Installation lesen

**chamnan ist für den einen Hauptordner gedacht, zu dem du immer wieder zurückkehrst.** Alles daran wird vorab bezahlt und in späteren Sitzungen wieder eingebracht — bei einem Repository, das du einmal öffnest, hast du voll bezahlt und nichts zurückbekommen.

**Es berichtet, es schreibt deinen Code nicht um.** Der Index übernimmt die Kommentare, die du selbst geschrieben hast, und erfindet nichts. Dateien ohne Kommentar werden namentlich genannt, damit du sie selbst ergänzt.

**Seine Grenzen sind gemessen und aufgeschrieben**, einschließlich der Messungen, die gegen seine eigene Kernfunktion sprechen.

## Wo die Details stehen

| | |
|---|---|
| Jede Zahl und wie sie gemessen wurde | [README › Evidence](../../README.md#evidence) |
| Regressionstests — selbst ausführbar | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Was sich in jedem Release geändert hat, und warum | [CHANGELOG.md](../../CHANGELOG.md) |
| Alles Übrige | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
