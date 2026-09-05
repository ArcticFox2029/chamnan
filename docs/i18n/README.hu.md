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

<!-- generated: build_sections.py -->

## Minden képesség

Négy képesség. Minden, ami alább szerepel, valóban fut a jelenlegi kiadásban. Mindegyik rész külön kikapcsolható a `.chamnan/config.json` fájlban, és egyik sem függ a többitől.

### Megérteni — mi van, és mi mivel függ össze

| | |
|---|---|
| **Index** | `MAP.md` — fájlonként egy sor, magából a kódból előállítva. Az ügynök az indexet olvassa, majd grepel rá a szükséges részletre, ahelyett hogy bejárná a fát. |
| **Hatás** | Ki függ ettől a fájltól, és mely tesztek fedik le. A saját importjai amúgy is a fájl tetején állnak; a drága az ellenkező irány — grepelje meg az útvonalat, mielőtt hozzányúl. |
| **Adatmodell** | Tábla- és modellnevek egysoros leírással, DDL-ből, migrációkból és ORM-modellekből kiszedve — nem a teljes séma kiírása. Csak akkor jelenik meg, ha a tároló tényleg definiál ilyet. |
| **API-felület** | Metódus, útvonal és kezelő, útvonal-dekorátorokból, OpenAPI-dokumentumokból és `.proto` szolgáltatásdefiníciókból — nem a teljes specifikáció. |
| **Konfiguráció** | Azoknak a környezeti változóknak a neve, amelyeket a tároló olvas. **Csak nevek, értékek soha** — és figyelmeztet, ha a `.env` nincs a gitignore-ban. |
| **Üzembe helyezés** | Ami valóban fut, Kubernetes-, Ansible-, Compose-, Helm- és CI-manifesztekből olvasva: típusok és nevek, image-ek, szerepek, futószalagok. Egy Secretből csak a nevét veszi, semmit abból, ami alatta van. |
| **Nem forráskód jellegű anyag** | Beszkennelt papírok, exportok, archívumok — csak darabszám, méret és a leggyakoribb kiterjesztések. Azért van, hogy az ügynök ne menjen el megnézni magától, ami sokkal drágább. **Soha nem nyitja meg, soha nem olvassa el.** |

### Emlékezni — mi volt folyamatban, és miért

| | |
|---|---|
| **Munkaállapot** | `STATE.md` — amin éppen most folyik a munka; a munkamenet indulásakor bekerül, hogy a kontextus tömörítése ne törölje ki többé. |
| **Munkamenet-feljegyzés** | Munkamenetenként egy a `.chamnan/sessions/` alatt. A következő munkamenetbe **csak a befejezetlen** jut el; egy tisztán lezárt munkamenet semmit sem küld tovább. |
| **Emlékezet** | `decisions/`, `lessons/`, `rules/`. A szabályok állandó korlátok, ezért minden munkamenetben az ügynök előtt állnak; a döntések és tanulságok csak címet adnak, és akkor olvassa el őket, ha a cím ide illőnek látszik. |
| **Nyitott szálak** | Még le nem zárt munkavonalak, azzal a történettel együtt, hogy az adott szál mely fájlokat érintette — és átnevezés után is követik őket. |

### Újrahasználni — amit már egyszer megoldottunk

| | |
|---|---|
| **Eljárások** | Készségek, amelyeket az ügynök **maga ír meg**, amikor valami bonyolultba vagy ismétlődőbe ütközik. Nem mellékelt kész könyvtár, hanem mechanizmus. |
| **Eszközök** | Észreveszi, hogy ugyanazt az eldobható szkriptet megint megírták, és felajánlja, hogy megtartja — majd szól róla, mielőtt újat írna. |
| **Munkafolyamatok** | Észreveszi, hogy ugyanazok a parancsok ugyanabban a sorrendben futottak külön napokon, és felajánlja, hogy leírja a sorozatot. |

### Gyarapodni — amit a tároló megtanult önmagáról

| | |
|---|---|
| **Mérföldkövek** | Az a néhány változás, amely átformálta a tárolót: mi költözött, miért érte meg, mely területeket érintette. |
| **Jelöltek** | Az észlelt ismétlődő parancssorozatok **mindig emberi megerősítésre várnak**. Semmi sem lép elő automatikusan. |
| **Környezetek** | Jelentse ki, mi a production vagy a staging, és mi tilos ott — és szól, amikor ez a kijelentés megöregszik. |
| **Jelentés** | Mit tárol a munkatér, tényleg elérhető-e, és hogyan változott a fordulónkénti kontextus az ön tárolójában. Az ön száma, nem a miénk. |

Az ismétlődő mérnöki munka újrahasználható tárolótudássá válik — **nem modelltanítás, és nem a fejlesztő automatizálása.** Olyan munka megőrzésének módja, amely különben csak annak a fejében létezne, aki elvégezte.

## Parancsok

Mind hívható a parancsértelmezőből, és az ügynök is hívja őket magától.

| | |
|---|---|
| `chamnan-map` | felépíti és frissíti az indexet |
| `chamnan-report` | mit tárol a munkatér, és hogyan változott a fordulónkénti kontextus |
| `chamnan-impact` | ki függ ettől a fájltól, és mely tesztek fedik le |
| `chamnan-timeline` | mi történt eddig ezzel a fájllal |
| `chamnan-peek` | megmondja, mi van egy nagy fájlban anélkül, hogy beolvasná a kontextusba |
| `chamnan-promote` | megőriz egy szkriptet a tároló állandó eszközeként |
| `chamnan-candidates` | megnézni, megerősíteni vagy elutasítani az észlelt ismétlődéseket |
| `chamnan-env` | kijelenteni egy környezetet és tilalmait, és ellenőrizni, hogy a kijelentés még friss-e |
| `chamnan-age` | hol kezdett elavulni a tárolt tudás |

És a munkameneten belülről hívható készségek: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Mit ír, és hová

Minden a `.chamnan/` mappán belül, hétköznapi markdown és JSON. Olvasható, kézzel szerkeszthető, és bármikor törölhető anélkül, hogy bármi elromlana.

| | |
|---|---|
| `MAP.md` | mi van, és mi mitől függ |
| `STATE.md` | min folyik éppen most a munka |
| `sessions/` | hol állt meg az előző munkaszakasz |
| `memory/` | döntések, tanulságok és állandó szabályok |
| `threads/` | még nyitott munkavonalak |
| `skills/` · `tools/` | megőrzésre érdemes eljárások és szkriptek |
| `milestones.md` | a változások, amelyek átformálták a tárolót |
| `config.json` | az egyes részek be- és kikapcsolása, és a munkamenetbe kerülő blokk bájtkorlátja |

**Az egyetlen írás a `.chamnan/` mappán kívül** egy választható Git pre-commit horog, amely az indexet a fához igazítva tartja — csak akkor kerül be, ha igent mond, és eltávolítható.

**Az ügynök nem tanul.** Semmit sem tanítunk, semmi sem marad ezen a mappán kívül, és a következő munkamenet továbbra is nulláról indul — csak épp nulláról *egy önmagát elmagyarázó tárolóban*. A folytonosság az iratokban van, nem a modellben.

## Biztonság

| | |
|---|---|
| **Futás közben semmilyen hálózati hívás** | Egyetlen egy sem. Nem kell API-kulcs, és semmi nem megy sehová. |
| **Nem írja át a forrását** | Jelent, nem szerkeszt. Az index a már megírt megjegyzéseit másolja, nem találja ki őket; a megjegyzés nélküli fájlokat néven nevezi, hogy ön pótolja. |
| **Nincs démon, nincs háttérmunka** | Nincs bent maradó folyamat, nincs adatbázis, nincs beágyazó modell — csak a Python szabványos könyvtára. |
| **A titkok szűrése az első** | Minden, ami leírásra vagy a munkamenetbe kerülne, előbb áthalad a titokszűrőn: a változók *neve* megmarad, az értékük nem. Azt a határt pedig, ameddig ez a szűrő nem ér el, az angol README-ben a saját száma mellé írtuk. |
| **Mit tehet önnel egy telepített bővítmény** | Teljes egészében az angol README-ben, azzal együtt, hogy a chamnan hol vágja el a kiszivárgás láncát. |

## Mivel működik együtt

A chamnan szöveg és szabványos könyvtári Python. Az indexben semmi sem tartozik egyetlen szállítóhoz, egyetlen szerkesztőhöz vagy egyetlen operációs rendszerhez.

| | |
|---|---|
| **Bármelyik modell, bármelyik szállító** | Az index egyszerű szöveg, és kontextusként megy át. A modell csak azt változtatja, mennyit érdemes elküldeni, azt soha, hogy mi hová kerül. A méretet a `--model`, `--window` vagy `--profile` állítja. Modellt váltani nem jár újratelepítéssel. |
| **macOS, Linux, Windows, WSL** | Mindenütt ugyanaz a bővítmény, csak szabványos könyvtár, nincs mit telepíteni. macOS-en és Linuxon a parancsok közvetlenül futnak. Windowson a parancsértelmező nem tud kiterjesztés nélküli szkriptet futtatni, ezért minden parancs és minden horog mellé generált `.cmd` kerül; ezek a bővítménnyel érkeznek, és a CI éppen ezeket futtatja. A WSL úgy viselkedik, mint a Linux. |
| **Sok ügynök, egyetlen index** | A Claude Code munkamenet-horgon át kapja meg, és a projektedbe egyetlen fájl sem íródik. A Gemini CLI-nek is van valódi munkamenet-horga. A többi ügynök abban az útvonalban kap fájlt, amelyet olvas, és akik ugyanazt olvassák, osztoznak a fájlon ahelyett, hogy mindegyik a maga széttartó másolatát őrizné. |
| **Hermes Agent** | A Hermes egyben vezérlőréteg is, amely más kódügynököket irányít, így az érte beállított tároló gyakran azt jelenti, hogy több eszköz ugyanazt az indexet olvassa. A projekt utasításait rögzített sorrendben keresi, és az elsőt veszi, amit talál; a chamnan a sorrend élén álló fájlt írja, méretét a Hermes által magának dokumentált korláthoz igazítja, és megtagadja olyan fájl felülírását, amelyet nem ő írt. |

## Így állítod be

Hogy melyik úton indulsz, kizárólag attól függ, van-e az eszköznek munkamenet-horga.

| | |
|---|---|
| **Claude Code** | Telepítsd bővítményként, és futtasd le egyszer az indító parancsot egy tárolón belül. A kódodba semmi sem íródik, és onnantól minden munkamenet úgy indul, hogy az index már a kontextusban van. |
| **Minden más, a Hermesszel együtt** | Előbb kérdezd meg, mit észlelt a chamnan, aztán mondd meg, melyik ügynöknek írjon. Ha a tároló alakja változik, építsd újra az indexet, és írd ki újra a fájlt; egy választható Git-horog véglegesítéskor mindkettőt elvégzi. Claude Code nem kell: ezek hétköznapi parancsok, a bővítmény pedig csak egy kézbesítési út, nem maga a termék. Megnevezett ügynök nélkül kiírja, mit észlelt és melyik parancs illene, a döntést pedig rád hagyja. Sosem ír találgatásból. |

A parancsnevek, az ügynökök teljes listája és a fájl, amelyet mindegyik kap, az angol README-ben található, ahol minden verzióhoz kötött részlet lakik.


## Követelmények

Claude Code · Python · Git · macOS, Linux vagy Windows

Semmi más, és nincs telepítendő függőség. A Python legkisebb verziója a [README › Requirements](../../README.md#requirements) részben van — ezen az oldalon nincsenek számok, mert épp a számok változnak.

## Kikapcsolás vagy eltávolítás

Kapcsolja ki részenként a `.chamnan/config.json` fájlban · állítsa le egyetlen tárolóban · távolítsa el a bővítményt az egész gépről · törölje a `.chamnan/` mappát bármikor, semmi nem romlik el — a részletes lépések: [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
