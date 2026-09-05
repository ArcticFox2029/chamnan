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

<!-- generated: build_sections.py -->

## Alle Funktionen

Vier Fähigkeiten. Alles unten Aufgeführte läuft im aktuellen Release wirklich. Jeder Teil lässt sich in `.chamnan/config.json` einzeln abschalten, und keiner hängt vom anderen ab.

### Verstehen — was es gibt und was womit zusammenhängt

| | |
|---|---|
| **Index** | `MAP.md` — eine Zeile je Datei, aus dem Code selbst erzeugt. Der Agent liest den Index und greppt das nötige Detail, statt den Baum abzulaufen. |
| **Auswirkung** | Wer von dieser Datei abhängt und welche Tests sie abdecken. Die eigenen Importe stehen ohnehin oben in der Datei; teuer ist die Gegenrichtung — greppen Sie den Pfad, bevor Sie ändern. |
| **Datenmodell** | Tabellen- und Modellnamen mit einzeiliger Beschreibung, gezogen aus DDL, Migrationen und ORM-Modellen — kein Dump des ganzen Schemas. Erscheint nur, wenn das Repository tatsächlich eines definiert. |
| **API-Oberfläche** | Methode, Pfad und Handler — aus Route-Dekoratoren, OpenAPI-Dokumenten und `.proto`-Servicedefinitionen, nicht die ganze Spezifikation. |
| **Konfiguration** | Die Namen der Umgebungsvariablen, die das Repository liest. **Nur Namen, Werte werden nie festgehalten** — und es warnt, wenn `.env` nicht in gitignore steht. |
| **Deployment** | Was tatsächlich läuft: Arten und Namen, Images, Rollen, Pipelines — gelesen aus Kubernetes-, Ansible-, Compose-, Helm- und CI-Manifesten. Von einem Secret kommt nur der Name, nichts darunter. |
| **Nicht-Quellmaterial** | Gescannte Unterlagen, Exporte, Archive — nur Anzahl, Größe und vorherrschende Endungen. Der Abschnitt existiert, damit der Agent nicht selbst nachsieht, was weit teurer wäre. **Wird nie geöffnet, nie gelesen.** |

### Erinnern — was gerade getan wurde und warum

| | |
|---|---|
| **Arbeitsstand** | `STATE.md` — woran gerade gearbeitet wird; wird zu Sitzungsbeginn eingespielt, damit die Kontextverdichtung es nicht mehr auslöscht. |
| **Sitzungsnotiz** | Eine Notiz je Sitzung unter `.chamnan/sessions/`. In die nächste Sitzung gelangt **nur das Unfertige**; eine sauber abgeschlossene Sitzung spielt gar nichts ein. |
| **Gedächtnis** | `decisions/`, `lessons/`, `rules/`. Regeln sind dauerhafte Einschränkungen und stehen daher in jeder Sitzung vor dem Agenten; Entscheidungen und Lehren steuern nur einen Titel bei und werden gelesen, wenn der Titel einschlägig wirkt. |
| **Offene Stränge** | Arbeitslinien, die noch nicht geschlossen sind, samt der Historie, welcher Datei dieser Strang begegnet ist — und sie folgen ihr auch über eine Umbenennung hinweg. |

### Wiederverwenden — was schon einmal gelöst wurde

| | |
|---|---|
| **Verfahren** | Fertigkeiten, die der Agent **selbst schreibt**, wenn er auf Komplexes oder Wiederkehrendes stößt. Keine mitgelieferte Bibliothek, sondern ein Mechanismus. |
| **Werkzeuge** | Bemerkt, dass dasselbe Wegwerfskript erneut geschrieben wurde, und bietet an, es zu behalten — und erwähnt es, bevor Sie ein neues schreiben. |
| **Abläufe** | Bemerkt, dass dieselben Befehle an getrennten Tagen in derselben Reihenfolge liefen, und bietet an, die Folge festzuhalten. |

### Anwachsen — was das Repository über sich selbst gelernt hat

| | |
|---|---|
| **Meilensteine** | Die wenigen Änderungen, die das Repository umgeformt haben: was umgezogen ist, warum es sich lohnte, welche Bereiche es berührt hat. |
| **Kandidaten** | Erkannte wiederkehrende Befehlsfolgen warten **immer auf menschliche Bestätigung**. Nichts wird automatisch befördert. |
| **Umgebungen** | Erklären Sie, was production oder staging ist und was dort verboten ist — und es meldet sich, wenn diese Erklärung veraltet. |
| **Bericht** | Was der Arbeitsbereich enthält, ob es tatsächlich erreichbar ist, und wie sich der Kontext je Zug in Ihrem Repository verändert hat. Ihre Zahl, nicht unsere. |

Wiederkehrende Ingenieursarbeit wird zu wiederverwendbarem Repository-Wissen — **kein Modelltraining und keine Automatisierung der Entwicklerin.** Es ist ein Mechanismus, Arbeit zu bewahren, die sonst nur im Kopf dessen existierte, der sie geleistet hat.

## Befehle

Alle aus der Shell aufrufbar, und der Agent ruft sie auch selbst auf.

| | |
|---|---|
| `chamnan-map` | baut den Index und hält ihn aktuell |
| `chamnan-report` | was der Arbeitsbereich enthält und wie sich der Kontext je Zug verändert hat |
| `chamnan-impact` | wer von dieser Datei abhängt und welche Tests sie abdecken |
| `chamnan-timeline` | was mit dieser Datei bisher geschehen ist |
| `chamnan-peek` | sagt, was in einer großen Datei steckt, ohne sie in den Kontext zu lesen |
| `chamnan-promote` | behält ein Skript als ständiges Werkzeug des Repositorys |
| `chamnan-candidates` | erkannte Wiederholungen ansehen, bestätigen oder ablehnen |
| `chamnan-env` | eine Umgebung samt ihrer Verbote erklären und prüfen, ob die Erklärung noch frisch ist |
| `chamnan-age` | wo das gespeicherte Wissen zu altern begonnen hat |

Und Fertigkeiten, die aus der Sitzung heraus aufgerufen werden: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Was es schreibt, und wohin

Alles innerhalb von `.chamnan/`, gewöhnliches Markdown und JSON. Lesbar, von Hand änderbar und jederzeit löschbar, ohne dass etwas kaputtgeht.

| | |
|---|---|
| `MAP.md` | was es gibt und was wovon abhängt |
| `STATE.md` | woran gerade gearbeitet wird |
| `sessions/` | wo die letzte Arbeitsstrecke aufgehört hat |
| `memory/` | Entscheidungen, Lehren und dauerhafte Regeln |
| `threads/` | Arbeitslinien, die noch offen sind |
| `skills/` · `tools/` | Verfahren und Skripte, die es zu behalten lohnt |
| `milestones.md` | die Änderungen, die das Repository umgeformt haben |
| `config.json` | das An und Aus jedes Teils und die Byte-Obergrenze des in die Sitzung eingespielten Blocks |

**Der einzige Schreibvorgang außerhalb von `.chamnan/`** ist ein optionaler Git-pre-commit-Hook, der den Index am Baum entlangführt — er wird nur installiert, wenn Sie zustimmen, und lässt sich entfernen.

**Der Agent lernt nicht.** Nichts wird trainiert, nichts bleibt außerhalb dieses Verzeichnisses, und die nächste Sitzung beginnt weiterhin bei null — nur eben bei null *in einem Repository, das sich selbst erklärt*. Die Kontinuität liegt in den Artefakten, nicht im Modell.

## Sicherheit

| | |
|---|---|
| **Zur Laufzeit keine Netzwerkaufrufe** | Kein einziger. Kein API-Schlüssel nötig, nichts wird irgendwohin gesendet. |
| **Schreibt Ihren Quelltext nicht um** | Es berichtet, es bearbeitet nicht. Der Index kopiert Kommentare, die Sie bereits geschrieben haben, und erfindet sie nicht; Dateien ohne Kommentar werden namentlich genannt, damit Sie sie ergänzen. |
| **Kein Daemon, keine Hintergrundarbeit** | Kein dauerhaft laufender Prozess, keine Datenbank, kein Embedding-Modell — nur Pythons Standardbibliothek. |
| **Geheimnisse werden zuerst gefiltert** | Alles, was geschrieben oder in die Sitzung eingespielt wird, läuft zuerst durch den Geheimnisfilter: Variablen*namen* bleiben, Werte nicht. Und die Grenze, die dieser Filter nicht erreicht, steht im englischen README direkt neben seiner eigenen Zahl. |
| **Was ein installiertes Plugin Ihnen antun kann** | Vollständig im englischen README erklärt, einschließlich der Stelle, an der chamnan die Abflusskette durchtrennt. |

## Womit es zusammenarbeitet

chamnan ist Text und Python aus der Standardbibliothek. Nichts im Index gehört einem bestimmten Anbieter, einem bestimmten Editor oder einem bestimmten Betriebssystem.

| | |
|---|---|
| **Jedes Modell, jeder Anbieter** | Der Index ist einfacher Text und wird als Kontext übergeben. Das Modell ändert nur, wie viel davon sich zu senden lohnt, nie wohin etwas gehört. Die Größe stellt man mit `--model`, `--window` oder `--profile` ein. Ein Modellwechsel erfordert keine Neuinstallation. |
| **macOS, Linux, Windows, WSL** | Überall dasselbe Plugin, nur Standardbibliothek, nichts zu installieren. Unter macOS und Linux laufen die Befehle direkt. Unter Windows kann die Kommandozeile ein Skript ohne Endung nicht ausführen, deshalb liegt neben jedem Befehl und jedem Hook ein erzeugtes `.cmd`; sie werden mit dem Plugin ausgeliefert und die CI führt sie tatsächlich aus. WSL verhält sich wie Linux. |
| **Viele Agenten, ein Index** | Claude Code bekommt den Block über einen Session-Hook, in Ihr Projekt wird keine Datei geschrieben. Gemini CLI hat ebenfalls einen echten Session-Hook. Alle anderen Agenten bekommen eine Datei an der Stelle, die sie lesen, und Agenten mit derselben Stelle teilen sich die Datei, statt jeweils eine Kopie zu halten, die auseinanderdriftet. |
| **Hermes Agent** | Hermes ist zugleich eine Steuerebene, die andere Coding-Agenten dirigiert. Ein dafür eingerichtetes Repository bedeutet deshalb oft, dass mehrere Werkzeuge denselben Index lesen. Es sucht Projektanweisungen in fester Reihenfolge und nimmt die erste gefundene; chamnan schreibt die Datei an der Spitze dieser Reihenfolge, bemisst sie an der von Hermes dokumentierten Obergrenze und überschreibt keine Datei, die es nicht selbst geschrieben hat. |

## So wird es eingerichtet

Welcher Weg es wird, hängt allein davon ab, ob das Werkzeug einen Session-Hook hat.

| | |
|---|---|
| **Claude Code** | Als Plugin installieren und den Bootstrap-Befehl einmal in einem Repository ausführen. In Ihren Code wird nichts geschrieben, und danach beginnt jede Sitzung mit dem Index bereits im Kontext. |
| **Alles andere, Hermes eingeschlossen** | Fragen Sie zuerst, was chamnan erkennt, und sagen Sie dann, für welchen Agenten geschrieben werden soll. Ändert sich die Form des Repositories, bauen Sie den Index neu und schreiben die Datei erneut; ein optionaler Git-Hook erledigt beim Commit beides. Claude Code wird nicht gebraucht: Das sind gewöhnliche Befehle, und das Plugin ist nur ein Zustellweg, nicht das Produkt. Ohne genannten Agenten gibt es aus, was erkannt wurde und welcher Befehl passen würde, und überlässt Ihnen die Entscheidung. Es schreibt nie auf Verdacht. |

Befehlsnamen, die vollständige Liste der Agenten und die Datei, die jeder bekommt, stehen in der englischen README, wo jedes versionsabhängige Detail lebt.


## Voraussetzungen

Claude Code · Python · Git · macOS, Linux oder Windows

Sonst nichts, und keine Abhängigkeiten zu installieren. Die Mindestversion von Python steht in [README › Requirements](../../README.md#requirements) — diese Seite trägt keine Zahlen, denn die Zahlen sind das, was sich ändert.

## Abschalten oder entfernen

Teilweise abschalten in `.chamnan/config.json` · in einem einzelnen Repository stoppen · das Plugin von der ganzen Maschine entfernen · `.chamnan/` jederzeit löschen, ohne dass etwas kaputtgeht — die genauen Schritte in [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
