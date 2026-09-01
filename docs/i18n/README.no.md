# chamnan — så et repositorium kjenner seg selv

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Denne siden inneholder bevisst ingen tall. Alle målinger står i den engelske README-en og endrer seg ved hver utgivelse; denne siden gjør det ikke. → [Evidence](../../README.md#evidence)

## Hva dette er

Et plugin til Claude Code. Det bygger en indeks over repositoriet som agenten leser i stedet for å gå gjennom filene én etter én, og tar vare på den tekniske sammenhengen som bygger seg opp underveis — arbeidets tilstand, øktnotater, begrunnelsene bak beslutningene og de framgangsmåtene man utleder på nytt hver gang.

Alt det skriver er vanlig markdown, sjekket inn ved siden av koden. Ingen nettverkskall under kjøring, ingen database, ingen bakgrunnsprosess, ingen embedding-modell — bare Pythons standardbibliotek.

## Hva det løser

Ved hver nye økt, og hver gang konteksten komprimeres, forsvinner alt agenten hadde forstått om kodebasen din, og den begynner å lete på nytt.

chamnan gjør den gjenoppdagelsen unødvendig: indeksen ligger klar når økten starter, og prisen er et kjent, avgrenset tall framfor ubegrenset fillesing.

## Installasjon

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Åpne en ny økt, og kjør `/chamnan:bootstrap` én gang per repositorium.

## Les før du installerer

**chamnan er ment for den ene hovedmappen du vender tilbake til gang på gang.** Alt det gjør betales på forskudd og hentes inn igjen i senere økter — i et repositorium du åpner én gang, har du betalt alt og hentet inn ingenting.

**Det rapporterer, det skriver ikke om koden din.** Indeksen gjengir kommentarene du allerede har skrevet, og finner ikke på noen. Filer uten kommentar nevnes ved navn så du kan fylle dem inn selv.

**Grensene er målt og skrevet ned**, også de målingene som taler imot dets egen hovedfunksjon.

## Hvor detaljene er

| | |
|---|---|
| Hvert tall, og hvordan det ble målt | [README › Evidence](../../README.md#evidence) |
| Regresjonstester — du kan kjøre dem selv | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Hva som endret seg i hver utgivelse, og hvorfor | [CHANGELOG.md](../../CHANGELOG.md) |
| Alt det andre | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
