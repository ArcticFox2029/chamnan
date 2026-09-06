# chamnan — zodat een repository zichzelf kent

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Deze pagina bevat bewust geen cijfers. Alle metingen staan in de Engelse README en veranderen bij elke release; deze pagina niet. → [Evidence](../../README.md#evidence)

## Wat dit is

Een Claude Code-plugin. Hij bouwt een index van de repository die de agent leest in plaats van bestanden één voor één te doorzoeken, en bewaart de technische context die tijdens het werk ontstaat — de stand van het werk, sessienotities, de redenen achter beslissingen en de procedures die je telkens opnieuw afleidt.

Alles wat hij schrijft is gewone markdown, naast de code gecommit. Geen netwerkaanroepen tijdens het draaien, geen database, geen daemon, geen embeddingmodel — alleen de standaardbibliotheek van Python.

## Wat het oplost

Bij elke nieuwe sessie, en telkens als de context wordt samengeperst, is alles weg wat de agent van je codebase had begrepen, en begint hij opnieuw met zoeken.

chamnan maakt dat herontdekken overbodig: de index ligt er bij aanvang van de sessie, en de prijs is een bekend, begrensd getal in plaats van onbegrensd bestanden lezen.

## Installatie

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Open een nieuwe sessie en voer `/chamnan:bootstrap` eenmaal per repository uit.

<!-- generated: build_sections.py -->

## Alle functies

Vier vermogens. Alles hieronder draait echt in de huidige uitgave. Elk onderdeel is apart uit te zetten in `.chamnan/config.json`, en geen enkel onderdeel hangt van een ander af.

### Begrijpen — wat er is, en wat waarmee samenhangt

| | |
|---|---|
| **Index** | `MAP.md` — één regel per bestand, gegenereerd uit de code zelf. De agent leest de index en grept het benodigde detail, in plaats van de boom af te lopen. |
| **Impact** | Wie van dit bestand afhangt en welke tests het dekken. De eigen imports staan toch al bovenaan het bestand; duur is de omgekeerde richting — grep het pad voordat je iets wijzigt. |
| **Datamodel** | Tabel- en modelnamen met één regel uitleg, gehaald uit DDL, migraties en ORM-modellen — geen dump van het hele schema. Verschijnt alleen als de repository er werkelijk een definieert. |
| **API-oppervlak** | Methode, pad en handler, uit route-decorators, OpenAPI-documenten en `.proto`-servicedefinities — niet de hele specificatie. |
| **Configuratie** | De namen van de omgevingsvariabelen die de repository leest. **Alleen namen, nooit waarden** — en het waarschuwt als `.env` niet in gitignore staat. |
| **Uitrol** | Wat er werkelijk draait, gelezen uit manifesten van Kubernetes, Ansible, Compose, Helm en CI: soorten en namen, images, rollen, pipelines. Van een Secret komt alleen de naam, niets van wat eronder staat. |
| **Niet-broncode-materiaal** | Gescande stukken, exports, archieven — alleen aantallen, groottes en overheersende extensies. Het bestaat opdat de agent niet zelf gaat kijken, wat veel duurder uitpakt. **Wordt nooit geopend, nooit gelezen.** |

### Onthouden — waaraan werd gewerkt, en waarom

| | |
|---|---|
| **Werkstand** | `STATE.md` — waaraan op dit moment wordt gewerkt; wordt bij het starten van de sessie ingevoegd zodat het samenvatten van de context het niet langer wist. |
| **Sessieverslag** | Eén per sessie onder `.chamnan/sessions/`. Naar de volgende sessie gaat **alleen wat onaf bleef**; een netjes afgesloten sessie voegt helemaal niets in. |
| **Geheugen** | `decisions/`, `lessons/`, `rules/`. Regels zijn blijvende beperkingen en staan dus elke sessie voor de agent; beslissingen en lessen leveren alleen een titel en worden gelezen wanneer die titel ter zake lijkt. |
| **Open draden** | Werklijnen die nog niet zijn afgesloten, met de geschiedenis van welke bestanden die draad heeft geraakt — en ze blijven die volgen nadat een bestand is hernoemd. |

### Hergebruiken — wat al eens is opgelost

| | |
|---|---|
| **Procedures** | Vaardigheden die de agent **zelf schrijft** wanneer hij iets ingewikkelds of herhaalds tegenkomt. Geen meegeleverde bibliotheek, maar een mechanisme. |
| **Gereedschap** | Merkt dat hetzelfde wegwerpscript opnieuw is geschreven en biedt aan het te bewaren — en noemt het voordat je een nieuw script schrijft. |
| **Werkstromen** | Merkt dat dezelfde commando's in dezelfde volgorde liepen op losse dagen, en biedt aan die volgorde vast te leggen. |

### Aangroeien — wat de repository over zichzelf heeft geleerd

| | |
|---|---|
| **Mijlpalen** | De paar wijzigingen die de vorm van de repository hebben veranderd: wat verhuisde, waarom het de moeite waard was, welke gebieden het raakte. |
| **Kandidaten** | Ontdekte herhaalde commandoreeksen wachten **altijd op bevestiging door een mens**. Niets wordt automatisch bevorderd. |
| **Omgevingen** | Verklaar wat production of staging is en wat daar verboden is — en het waarschuwt wanneer die verklaring veroudert. |
| **Rapport** | Wat de werkruimte bevat, of het werkelijk bereikbaar is, en hoe de context per beurt in jouw repository is veranderd. Jouw getal, niet het onze. |

Herhaald ingenieurswerk wordt herbruikbare repositorykennis — **geen modeltraining, en geen automatisering van de ontwikkelaar.** Het is een manier om werk te bewaren dat anders alleen bestond in het hoofd van wie het deed.

## Commando's

Allemaal aan te roepen vanuit de shell, en de agent roept ze ook zelf aan.

| | |
|---|---|
| `chamnan-map` | bouwt de index en houdt hem bij |
| `chamnan-report` | wat de werkruimte bevat en hoe de context per beurt is veranderd |
| `chamnan-impact` | wie van dit bestand afhangt en welke tests het dekken |
| `chamnan-timeline` | wat er tot nu toe met dit bestand is gebeurd |
| `chamnan-peek` | zegt wat er in een groot bestand zit zonder het in de context te lezen |
| `chamnan-promote` | bewaart een script als vast gereedschap van de repository |
| `chamnan-candidates` | ontdekte herhalingen bekijken, bevestigen of afwijzen |
| `chamnan-env` | een omgeving en haar verboden verklaren, en nagaan of die verklaring nog vers is |
| `chamnan-age` | waar de opgeslagen kennis is beginnen te verouderen |

En vaardigheden die vanuit de sessie worden aangeroepen: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Wat het schrijft, en waar

Alles binnen `.chamnan/`, gewone markdown en JSON. Leesbaar, met de hand aan te passen en op elk moment te verwijderen zonder dat er iets stukgaat.

| | |
|---|---|
| `MAP.md` | wat er is, en wat waarvan afhangt |
| `STATE.md` | waaraan op dit moment wordt gewerkt |
| `sessions/` | waar het vorige werk is gestopt |
| `memory/` | beslissingen, lessen en blijvende regels |
| `threads/` | werklijnen die nog openstaan |
| `skills/` · `tools/` | procedures en scripts die het bewaren waard zijn |
| `milestones.md` | de wijzigingen die de vorm van de repository veranderden |
| `config.json` | het aan- en uitzetten van elk onderdeel, en de bytegrens van het blok dat in de sessie wordt ingevoegd |

**De enige schrijfactie buiten `.chamnan/`** is een optionele Git-pre-commit-hook die de index in de pas houdt met de boom — die wordt alleen geplaatst als je ja zegt, en is te verwijderen.

**De agent leert niet.** Er wordt niets getraind, er blijft niets buiten deze map achter, en de volgende sessie begint nog steeds bij nul — alleen bij nul *in een repository die zichzelf uitlegt*. De continuïteit zit in de artefacten, niet in het model.

## Veiligheid

| | |
|---|---|
| **Geen netwerkaanroep tijdens het draaien** | Geen enkele. Er is geen API-sleutel nodig en er wordt niets ergens heen gestuurd. |
| **Herschrijft je broncode niet** | Het rapporteert, het bewerkt niet. De index kopieert de commentaren die je al hebt geschreven en verzint ze niet; bestanden zonder commentaar worden bij naam genoemd zodat jij ze aanvult. |
| **Geen daemon, geen achtergrondwerk** | Geen blijvend proces, geen database, geen embeddingmodel — alleen de standaardbibliotheek van Python. |
| **Geheimen worden eerst gefilterd** | Alles wat wordt geschreven of in de sessie wordt ingevoegd, gaat eerst door het geheimenfilter: de *namen* van variabelen blijven, de waarden niet. En de grens die dat filter niet haalt, staat naast zijn eigen getal in de Engelse README. |
| **Wat een geïnstalleerde plugin jou kan aandoen** | Volledig uitgelegd in de Engelse README, inclusief waar chamnan de keten van weglekken doorbreekt. |

## Waarmee het samenwerkt

chamnan is tekst en Python uit de standaardbibliotheek. Niets in de index hoort bij één leverancier, één editor of één besturingssysteem.

| | |
|---|---|
| **Elk model, elke leverancier** | De index is gewone tekst en gaat mee als context. Het model bepaalt alleen hoeveel ervan de moeite waard is om te sturen, nooit waar iets terechtkomt. Stel de omvang in met `--model`, `--window` of `--profile`. Van model wisselen vraagt geen herinstallatie. `--model` herkent deze families op naam: `claude` · `codestral` · `deepseek` · `fable` · `gemini` · `gemma` · `glm` · `gpt` · `grok` · `haiku` · `kimi` · `mistral` · `openai` · `opus` · `sonnet` — bij het vergelijken tellen hoofdletters, scheidingstekens en versienummers niet mee. `llama` en `qwen` ontbreken met opzet: beide verschijnen in meerdere maten die verschillende budgetten willen, dus die noemen levert het standaardprofiel op plus een regel over welke twee maten bedoeld konden zijn. **Een model dat niet op de lijst staat werkt gewoon**: het krijgt het standaardprofiel en een notitie dat het niet herkend werd, en er faalt niets. `--window` neemt het getal rechtstreeks en is altijd exact. |
| **macOS, Linux, Windows, WSL** | Overal dezelfde plugin, alleen standaardbibliotheek, niets te installeren. Op macOS en Linux draaien de commando's rechtstreeks. Op Windows kan de shell geen script zonder extensie starten, dus staat naast elk commando en elke hook een gegenereerde `.cmd`; die worden met de plugin meegeleverd en CI voert ze ook echt uit. WSL gedraagt zich als Linux. |
| **Veel agents, één index** | Claude Code krijgt het via een sessie-hook en er wordt geen bestand in je project geschreven. Gemini CLI heeft eveneens een echte sessie-hook. Andere agents krijgen een bestand op het pad dat die agent leest, en agents die hetzelfde pad lezen delen dat bestand in plaats van elk een kopie te bewaren die uit elkaar gaat lopen. |
| **Hermes Agent** | Hermes is tegelijk een besturingslaag die andere codeeragents aanstuurt, dus een repository die daarvoor is ingericht betekent vaak dat meerdere gereedschappen dezelfde index lezen. Het zoekt projectinstructies in een vaste volgorde en neemt de eerste die het vindt; chamnan schrijft het bestand dat bovenaan die volgorde staat, past de omvang aan op de limiet die Hermes zelf documenteert, en weigert een bestand te overschrijven dat het niet zelf heeft geschreven. |

## Zo zet je het op

Welke weg je neemt hangt alleen af van de vraag of dat gereedschap een sessie-hook heeft.

| | |
|---|---|
| **Claude Code** | Installeer het als plugin en voer het bootstrap-commando één keer uit binnen een repository. Er wordt niets in je code geschreven, en daarna begint elke sessie met de index al in de context. |
| **Al het andere, Hermes inbegrepen** | Vraag eerst wat chamnan detecteert en zeg dan voor welke agent het moet schrijven. Verandert de vorm van de repository, bouw dan de index opnieuw en schrijf het bestand nog eens; een optionele Git-hook doet beide bij het committen. Claude Code is niet nodig: dit zijn gewone commando's en de plugin is slechts één bezorgroute, niet het product. Noem je geen agent, dan drukt het af wat het heeft gedetecteerd en welk commando zou passen, en laat het de beslissing aan jou. Het schrijft nooit op een vermoeden. |

Commandonamen, de volledige lijst met agents en het bestand dat elk ontvangt staan in de Engelse README, waar elk versiegebonden detail thuishoort.


## Vereisten

Claude Code · Python · Git · macOS, Linux of Windows

Verder niets, en geen afhankelijkheden om te installeren. De minimale Python-versie staat in [README › Requirements](../../README.md#requirements) — deze pagina draagt geen getallen, want juist de getallen veranderen.

## Uitzetten of verwijderen

Zet het per onderdeel uit in `.chamnan/config.json` · stop het in één repository · verwijder de plugin van de hele machine · wis `.chamnan/` wanneer je wilt zonder dat er iets stukgaat — de stappen staan in [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

## Lees dit vóór het installeren

**chamnan is bedoeld voor die ene hoofdmap waar je telkens naar terugkeert.** Alles wat hij doet betaal je vooraf en int je in latere sessies — bij een repository die je één keer opent heb je alles betaald en niets geïnd.

**Hij rapporteert, hij herschrijft je code niet.** De index neemt de commentaren over die jij al hebt geschreven en verzint niets. Bestanden zonder commentaar worden bij naam genoemd zodat je ze zelf aanvult.

**Zijn beperkingen zijn gemeten en opgeschreven**, inclusief metingen die tegen zijn eigen kernfunctie pleiten.

## Waar de details staan

| | |
|---|---|
| Elk getal, en hoe het gemeten is | [README › Evidence](../../README.md#evidence) |
| Regressietests — zelf uit te voeren | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Wat er per release veranderde, en waarom | [CHANGELOG.md](../../CHANGELOG.md) |
| Al het overige | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
