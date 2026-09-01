# chamnan — ca un depozit să se cunoască pe sine

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Această pagină nu conține niciun număr, în mod deliberat. Toate măsurătorile se află în README-ul în engleză și se schimbă la fiecare versiune; pagina aceasta nu. → [Evidence](../../README.md#evidence)

## Ce este

Un plugin pentru Claude Code. Construiește un index al depozitului pe care agentul îl citește în loc să parcurgă fișierele unul câte unul și păstrează contextul tehnic acumulat în timpul lucrului — starea lucrului, însemnările de sesiune, motivele din spatele deciziilor și procedurile pe care le rededuci de fiecare dată.

Tot ce scrie este markdown obișnuit, comis alături de cod. Fără apeluri de rețea la rulare, fără bază de date, fără daemon, fără model de embedding — doar biblioteca standard Python.

## Ce rezolvă

La fiecare sesiune nouă și ori de câte ori contextul este comprimat, dispare tot ce înțelesese agentul despre codul tău și o ia de la capăt cu căutarea.

chamnan face ca acea redescoperire să nu mai fie nevoie: indexul este predat la începutul sesiunii, iar costul este un număr cunoscut și mărginit, nu citiri de fișiere fără limită.

## Instalare

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Deschide o sesiune nouă, apoi rulează `/chamnan:bootstrap` o dată pentru fiecare depozit.

## De citit înainte de instalare

**chamnan este pentru acel dosar principal la care revii mereu.** Tot ce face se plătește în avans și se recuperează în sesiunile următoare — într-un depozit deschis o singură dată, ai plătit tot și nu ai recuperat nimic.

**Raportează, nu îți rescrie codul.** Indexul preia comentariile pe care le-ai scris deja și nu inventează niciunul. Fișierele fără comentariu sunt numite ca să le completezi tu.

**Limitele lui sunt măsurate și scrise**, inclusiv măsurătorile care pledează împotriva propriei sale funcții principale.

## Unde sunt detaliile

| | |
|---|---|
| Fiecare număr și cum a fost măsurat | [README › Evidence](../../README.md#evidence) |
| Setul de teste de regresie — îl poți rula singur | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Ce s-a schimbat la fiecare versiune și de ce | [CHANGELOG.md](../../CHANGELOG.md) |
| Tot restul | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
