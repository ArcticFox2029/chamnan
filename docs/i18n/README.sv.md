# chamnan — så att ett repo känner sig självt

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Den här sidan innehåller medvetet inga siffror. Alla mätningar finns i den engelska README-filen och ändras vid varje release; den här sidan gör det inte. → [Evidence](../../README.md#evidence)

## Vad det är

Ett plugin till Claude Code. Det bygger ett index över repot som agenten läser i stället för att gå igenom filerna en och en, och bevarar det tekniska sammanhang som byggs upp under arbetet — arbetsläget, sessionsanteckningar, skälen bakom besluten och de arbetsgångar man härleder på nytt varje gång.

Allt det skriver är vanlig markdown, incheckad bredvid koden. Inga nätverksanrop vid körning, ingen databas, ingen bakgrundsprocess, ingen embedding-modell — bara Pythons standardbibliotek.

## Vad det löser

Vid varje ny session, och varje gång sammanhanget komprimeras, försvinner allt agenten hade förstått om din kodbas och den börjar leta om från början.

chamnan gör att den återupptäckten inte behöver ske: indexet ligger på plats när sessionen börjar, och priset är ett känt, begränsat tal i stället för obegränsad filläsning.

## Installation

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Öppna en ny session och kör `/chamnan:bootstrap` en gång per repo.

## Läs innan du installerar

**chamnan är till för den där huvudmappen du återvänder till gång på gång.** Allt det gör betalas i förskott och hämtas hem i senare sessioner — i ett repo du öppnar en enda gång har du betalat allt och hämtat hem ingenting.

**Det rapporterar, det skriver inte om din kod.** Indexet återger de kommentarer du redan skrivit och hittar inte på några. Filer utan kommentar namnges så att du kan fylla i dem själv.

**Dess gränser är uppmätta och nedskrivna**, inklusive de mätningar som talar mot dess egen huvudfunktion.

## Var detaljerna finns

| | |
|---|---|
| Varje siffra, och hur den mättes | [README › Evidence](../../README.md#evidence) |
| Regressionstester — du kan köra dem själv | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Vad som ändrades i varje release, och varför | [CHANGELOG.md](../../CHANGELOG.md) |
| Allt annat | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
