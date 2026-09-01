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
