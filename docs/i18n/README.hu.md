# chamnan — hogy egy tároló ismerje önmagát

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Ezen az oldalon szándékosan nincs egyetlen szám sem. Minden mérés az angol README-ben van, és minden kiadással változik; ez az oldal nem. → [Evidence](../../README.md#evidence)

## Mi ez

Egy Claude Code bővítmény. Indexet épít a tárolóról, amelyet az ügynök olvas ahelyett, hogy fájlonként végigpásztázná, és megőrzi a munka közben felhalmozódó mérnöki környezetet — a munka állapotát, a munkamenetek feljegyzéseit, a döntések mögötti okokat és azokat az eljárásokat, amelyeket minden alkalommal újra levezetsz.

Amit ír, az mind egyszerű markdown, a kód mellé commitolva. Futás közben nincs hálózati hívás, nincs adatbázis, nincs démon, nincs embedding modell — csak a Python standard könyvtára.

## Mit old meg

Minden új munkamenetnél, és valahányszor a környezet összetömörödik, eltűnik minden, amit az ügynök megértett a kódbázisodból, és újrakezdi a keresést.

A chamnan feleslegessé teszi ezt az újrafelfedezést: az index a munkamenet elején kerül a kezébe, és az ára egy ismert, korlátos szám, nem pedig korlátlan fájlolvasás.

## Telepítés

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Nyiss egy új munkamenetet, majd futtasd a `/chamnan:bootstrap` parancsot tárolónként egyszer.

## Telepítés előtt olvasd el

**A chamnan arra az egy fő mappára való, ahová újra és újra visszatérsz.** Amit csinál, azt előre kifizeted, és a későbbi munkamenetekben szeded be — egy egyszer megnyitott tárolónál mindent kifizettél, és semmit nem szedtél be.

**Jelent, nem írja át a kódodat.** Az index a már megírt megjegyzéseidet másolja, nem talál ki semmit. A megjegyzés nélküli fájlokat névvel felsorolja, hogy magad pótold.

**A korlátait megmérték és leírták**, beleértve azokat a méréseket is, amelyek a saját fő funkciója ellen szólnak.

## Hol vannak a részletek

| | |
|---|---|
| Minden szám, és hogyan mérték | [README › Evidence](../../README.md#evidence) |
| Regressziós tesztkészlet — magad is futtathatod | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Mi változott az egyes kiadásokban, és miért | [CHANGELOG.md](../../CHANGELOG.md) |
| Minden más | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
