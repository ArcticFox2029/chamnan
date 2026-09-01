# chamnan — så et repository kender sig selv

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Denne side indeholder bevidst ingen tal. Alle målinger står i den engelske README og ændrer sig ved hver udgivelse; det gør denne side ikke. → [Evidence](../../README.md#evidence)

## Hvad det er

Et plugin til Claude Code. Det bygger et indeks over repositoriet, som agenten læser i stedet for at gennemgå filerne én for én, og bevarer den tekniske sammenhæng, der samler sig undervejs — arbejdets tilstand, sessionsnoter, begrundelserne bag beslutningerne og de fremgangsmåder, man udleder forfra hver gang.

Alt hvad det skriver, er almindelig markdown, committet ved siden af koden. Ingen netværkskald under kørsel, ingen database, ingen dæmon, ingen embedding-model — kun Pythons standardbibliotek.

## Hvad det løser

Ved hver ny session, og hver gang konteksten komprimeres, forsvinder alt hvad agenten havde forstået om din kodebase, og den begynder at lede forfra.

chamnan gør den genopdagelse overflødig: indekset ligger klar ved sessionens start, og prisen er et kendt, afgrænset tal frem for ubegrænset fillæsning.

## Installation

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Åbn en ny session, og kør `/chamnan:bootstrap` én gang pr. repository.

## Læs før du installerer

**chamnan er til den ene hovedmappe, du vender tilbage til igen og igen.** Alt hvad det gør, betales forud og hentes hjem i de følgende sessioner — i et repository, du åbner én gang, har du betalt det hele og hentet intet hjem.

**Det rapporterer, det omskriver ikke din kode.** Indekset gengiver de kommentarer, du allerede har skrevet, og opfinder ingen. Filer uden kommentar nævnes ved navn, så du selv kan udfylde dem.

**Dets grænser er målt og skrevet ned**, inklusive de målinger, der taler imod dets egen hovedfunktion.

## Hvor detaljerne er

| | |
|---|---|
| Hvert tal, og hvordan det blev målt | [README › Evidence](../../README.md#evidence) |
| Regressionstest — du kan køre dem selv | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Hvad der ændrede sig i hver udgivelse, og hvorfor | [CHANGELOG.md](../../CHANGELOG.md) |
| Alt det øvrige | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
