# chamnan — aby repozitář znal sám sebe

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Tato stránka záměrně neobsahuje žádná čísla. Všechna měření jsou v anglickém README a mění se s každým vydáním; tato stránka ne. → [Evidence](../../README.md#evidence)

## Co to je

Zásuvný modul pro Claude Code. Vytvoří index repozitáře, který agent čte místo procházení souborů jeden po druhém, a uchová inženýrský kontext, jenž se během práce nasbírá — stav práce, záznamy sezení, důvody rozhodnutí a postupy, které pokaždé odvozujete znovu.

Vše, co zapíše, je obyčejný markdown commitnutý vedle kódu. Za běhu žádné síťové volání, žádná databáze, žádný démon, žádný embedding model — pouze standardní knihovna Pythonu.

## Co řeší

S každým novým sezením, a pokaždé když se kontext zhutní, zmizí vše, co agent o vašem kódu pochopil, a začne hledat od začátku.

chamnan tomuto opětovnému objevování zabrání: index dostane hned na začátku sezení a cenou je známé, ohraničené číslo, ne neomezené čtení souborů.

## Instalace

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Otevřete nové sezení a spusťte `/chamnan:bootstrap` jednou pro každý repozitář.

## Přečtěte si před instalací

**chamnan je pro jednu hlavní složku, ke které se opakovaně vracíte.** Vše, co dělá, se platí předem a vybírá v dalších sezeních — u repozitáře, který otevřete jednou, jste zaplatili celé a nevybrali nic.

**Hlásí, nepřepisuje váš kód.** Index kopíruje komentáře, které jste už napsali, a nic si nevymýšlí. Soubory bez komentáře jmenuje, abyste je doplnili sami.

**Jeho meze jsou změřené a sepsané**, včetně měření, která mluví proti jeho vlastní hlavní funkci.

## Kde jsou podrobnosti

| | |
|---|---|
| Každé číslo a jak bylo změřeno | [README › Evidence](../../README.md#evidence) |
| Sada regresních testů — můžete spustit sami | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Co se v každém vydání změnilo a proč | [CHANGELOG.md](../../CHANGELOG.md) |
| Vše ostatní | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
