# chamnan — jotta repositorio tuntisi itsensä

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Tällä sivulla ei ole tarkoituksella yhtään lukua. Kaikki mittaukset ovat englanninkielisessä README-tiedostossa ja muuttuvat joka julkaisussa; tämä sivu ei. → [Evidence](../../README.md#evidence)

## Mikä tämä on

Claude Code -laajennus. Se rakentaa repositoriosta hakemiston, jonka agentti lukee sen sijaan että kävisi tiedostot yksi kerrallaan läpi, ja säilyttää työn aikana kertyvän teknisen taustan — työn tilan, istuntomuistiinpanot, päätösten perustelut ja ne menettelyt, jotka johdetaan joka kerta uudelleen.

Kaikki mitä se kirjoittaa on tavallista markdownia, versioituna koodin vierellä. Ei verkkokutsuja ajon aikana, ei tietokantaa, ei taustaprosessia, ei embedding-mallia — pelkkä Pythonin vakiokirjasto.

## Minkä se ratkaisee

Jokaisessa uudessa istunnossa, ja aina kun konteksti tiivistetään, kaikki minkä agentti oli ymmärtänyt koodistasi katoaa ja se aloittaa etsimisen alusta.

chamnan tekee tuosta uudelleenlöytämisestä tarpeetonta: hakemisto annetaan istunnon alussa, ja hinta on tunnettu, rajattu luku eikä rajaton määrä tiedostojen lukemista.

## Asennus

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Avaa uusi istunto ja aja `/chamnan:bootstrap` kerran kutakin repositoriota kohden.

## Lue ennen asennusta

**chamnan on sitä yhtä pääkansiota varten, johon palaat yhä uudelleen.** Kaikki mitä se tekee maksetaan etukäteen ja peritään takaisin myöhemmissä istunnoissa — kerran avatussa repositoriossa maksoit kaiken etkä perinyt mitään.

**Se raportoi, ei kirjoita koodiasi uudelleen.** Hakemisto kopioi kommentit jotka olet jo kirjoittanut, eikä keksi niitä. Kommentittomat tiedostot luetellaan nimeltä, jotta täydennät ne itse.

**Sen rajat on mitattu ja kirjoitettu**, mukaan lukien mittaukset jotka puhuvat sen omaa pääominaisuutta vastaan.

## Missä yksityiskohdat ovat

| | |
|---|---|
| Jokainen luku ja miten se mitattiin | [README › Evidence](../../README.md#evidence) |
| Regressiotestit — voit ajaa ne itse | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Mikä muuttui kussakin julkaisussa ja miksi | [CHANGELOG.md](../../CHANGELOG.md) |
| Kaikki muu | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
