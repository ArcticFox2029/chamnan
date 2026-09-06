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

<!-- generated: build_sections.py -->

## Alla funktioner

Fyra förmågor. Allt nedan körs på riktigt i den nuvarande utgåvan. Varje del går att stänga av var för sig i `.chamnan/config.json`, och ingen är beroende av någon annan.

### Förstå — vad som finns, och vad som hänger ihop med vad

| | |
|---|---|
| **Index** | `MAP.md` — en rad per fil, framställd ur koden själv. Agenten läser indexet och grepar fram den detalj som behövs, i stället för att vandra igenom trädet. |
| **Påverkan** | Vem som beror av den här filen och vilka tester som täcker den. Filens egna importer står ändå högst upp i den; det dyra är motsatt riktning — grepa sökvägen innan du ändrar. |
| **Datamodell** | Tabell- och modellnamn med en rads beskrivning, hämtade ur DDL, migrationer och ORM-modeller — inte en dump av hela schemat. Visas bara om förrådet faktiskt definierar något. |
| **API-yta** | Metod, sökväg och hanterare, ur ruttdekoratorer, OpenAPI-dokument och `.proto`-tjänstedefinitioner — inte hela specifikationen. |
| **Konfiguration** | Namnen på de miljövariabler förrådet läser. **Bara namn, aldrig värden** — och det varnar om `.env` inte ligger i gitignore. |
| **Driftsättning** | Vad som faktiskt kör, läst ur manifest för Kubernetes, Ansible, Compose, Helm och CI: sorter och namn, avbilder, roller, pipelines. Av en Secret tas bara namnet, inget av det som ligger under. |
| **Icke-källmaterial** | Inskannade papper, exporter, arkiv — bara antal, storlekar och de vanligaste filändelserna. Avsnittet finns för att agenten inte ska gå och titta själv, vilket kostar långt mer. **Öppnas aldrig, läses aldrig.** |

### Minnas — vad som höll på att göras, och varför

| | |
|---|---|
| **Arbetsläge** | `STATE.md` — det som arbetas på just nu; matas in vid sessionens början så att kontextkomprimeringen slutar radera det. |
| **Sessionsanteckning** | En per session under `.chamnan/sessions/`. Till nästa session når **bara det som blev oavslutat**; en session som avslutats rent matar inte in något alls. |
| **Minne** | `decisions/`, `lessons/`, `rules/`. Regler är bestående begränsningar och står därför framför agenten varje session; beslut och lärdomar bidrar bara med en rubrik och läses när rubriken verkar relevant. |
| **Öppna trådar** | Arbetslinjer som ännu inte stängts, med historiken över vilka filer tråden rört — och de följer filen även efter ett namnbyte. |

### Återanvända — det som redan lösts en gång

| | |
|---|---|
| **Rutiner** | Färdigheter som agenten skriver **själv** när den stöter på något komplicerat eller upprepat. Inget medföljande bibliotek, utan en mekanism. |
| **Verktyg** | Märker att samma engångsskript skrivits igen och erbjuder sig att spara det — och påminner om det innan du skriver ett nytt. |
| **Arbetsflöden** | Märker att samma kommandon kört i samma ordning skilda dagar, och erbjuder sig att skriva ned följden. |

### Växa — vad förrådet lärt sig om sig självt

| | |
|---|---|
| **Milstolpar** | De få ändringar som omformade förrådet: vad som flyttade, varför det var värt det, vilka områden det rörde. |
| **Kandidater** | Upptäckta upprepade kommandoföljder hålls **alltid kvar i väntan på en människas bekräftelse**. Inget befordras automatiskt. |
| **Miljöer** | Förklara vad production eller staging är och vad som är förbjudet där — och det säger till när den förklaringen åldras. |
| **Rapport** | Vad arbetsytan innehåller, om det verkligen går att nå, och hur kontexten per drag har förändrats i ditt förråd. Din siffra, inte vår. |

Upprepat ingenjörsarbete blir återanvändbar förrådskunskap — **inte modellträning, och inte automatisering av utvecklaren.** Det är ett sätt att bevara arbete som annars bara funnits i huvudet på den som utförde det.

## Kommandon

Alla går att anropa från skalet, och agenten anropar dem också själv.

| | |
|---|---|
| `chamnan-map` | bygger och uppdaterar indexet |
| `chamnan-report` | vad arbetsytan innehåller och hur kontexten per drag förändrats |
| `chamnan-impact` | vem som beror av den här filen och vilka tester som täcker den |
| `chamnan-timeline` | vad som hänt med den här filen hittills |
| `chamnan-peek` | säger vad som finns i en stor fil utan att läsa in den i kontexten |
| `chamnan-promote` | sparar ett skript som ett fast verktyg för förrådet |
| `chamnan-candidates` | se, bekräfta eller avvisa upptäckta upprepningar |
| `chamnan-env` | förklara en miljö och dess förbud, och kontrollera att förklaringen fortfarande är färsk |
| `chamnan-age` | var den sparade kunskapen börjat åldras |

Och färdigheter som anropas inifrån sessionen: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Vad det skriver, och var

Allt inuti `.chamnan/`, vanlig markdown och JSON. Går att läsa, ändra för hand och radera när som helst utan att något går sönder.

| | |
|---|---|
| `MAP.md` | vad som finns, och vad som beror av vad |
| `STATE.md` | vad som arbetas på just nu |
| `sessions/` | var det förra arbetspasset stannade |
| `memory/` | beslut, lärdomar och bestående regler |
| `threads/` | arbetslinjer som fortfarande är öppna |
| `skills/` · `tools/` | rutiner och skript som är värda att spara |
| `milestones.md` | de ändringar som omformade förrådet |
| `config.json` | på och av för varje del, och bytetaket för blocket som matas in i sessionen |

**Den enda skrivningen utanför `.chamnan/`** är en valfri Git-pre-commit-krok som håller indexet i takt med trädet — den läggs in bara om du säger ja, och går att ta bort.

**Agenten lär sig inte.** Ingenting tränas, ingenting blir kvar utanför den här katalogen, och nästa session börjar fortfarande från noll — bara från noll *i ett förråd som förklarar sig självt*. Kontinuiteten ligger i artefakterna, inte i modellen.

## Säkerhet

| | |
|---|---|
| **Inga nätverksanrop under körning** | Inte ett enda. Ingen API-nyckel behövs och ingenting skickas någonstans. |
| **Skriver inte om din kod** | Det rapporterar, det redigerar inte. Indexet kopierar de kommentarer du redan skrivit och hittar inte på dem; filer utan kommentar namnges så att du fyller i dem själv. |
| **Ingen demon, inget bakgrundsarbete** | Ingen bestående process, ingen databas, ingen inbäddningsmodell — bara Pythons standardbibliotek. |
| **Hemligheter filtreras först** | Allt som ska skrivas eller matas in i sessionen går först genom hemlighetsfiltret: variablernas *namn* blir kvar, värdena inte. Och den gräns filtret inte når står bredvid sin egen siffra i den engelska README-filen. |
| **Vad ett installerat tillägg kan göra mot dig** | Förklarat i sin helhet i den engelska README-filen, inklusive var chamnan bryter läckagekedjan. |

## Vad det fungerar med

chamnan är text och Python ur standardbiblioteket. Inget i indexet tillhör en viss leverantör, en viss editor eller ett visst operativsystem.

| | |
|---|---|
| **Vilken modell som helst, vilken leverantör som helst** | Indexet är vanlig text och skickas med som kontext. Modellen ändrar bara hur mycket som är värt att skicka, aldrig var något hamnar. Storleken ställs in med `--model`, `--window` eller `--profile`. Att byta modell kräver ingen ominstallation. `--model` känner igen dessa familjer på namnet: `claude` · `codestral` · `deepseek` · `fable` · `gemini` · `gemma` · `glm` · `gpt` · `grok` · `haiku` · `kimi` · `mistral` · `openai` · `opus` · `sonnet` — jämförelsen bryr sig inte om versaler, avgränsare eller versionsnummer. `llama` och `qwen` är medvetet utelämnade: båda kommer i flera storlekar som vill ha olika budgetar, så att namnge dem ger standardprofilen och en rad om vilka två storlekar som kunde ha avsetts. **En modell som inte står på listan fungerar ändå**: den får standardprofilen och en notis om att den inte känns igen, och ingenting fallerar. `--window` tar talet direkt och är alltid exakt. |
| **macOS, Linux, Windows, WSL** | Samma plugin överallt, enbart standardbibliotek, inget att installera. På macOS och Linux körs kommandona direkt. På Windows kan skalet inte köra ett skript utan filändelse, så intill varje kommando och varje krok ligger en genererad `.cmd`; de följer med plugin-paketet och CI kör just dem. WSL beter sig som Linux. |
| **Många agenter, ett index** | Claude Code får blocket via en sessionskrok och ingen fil skrivs in i ditt projekt. Gemini CLI har också en riktig sessionskrok. Övriga agenter får en fil på den sökväg agenten läser, och de som läser samma sökväg delar filen i stället för att var och en hålla en kopia som glider isär. |
| **Hermes Agent** | Hermes är samtidigt ett styrlager som dirigerar andra kodagenter, så ett repo som ställts in för det betyder ofta att flera verktyg läser samma index. Det letar efter projektinstruktioner i en fast ordning och tar den första det hittar; chamnan skriver filen som står först i den ordningen, anpassar storleken till den gräns Hermes själv dokumenterar och vägrar skriva över en fil som det inte skrivit. |

## Så sätter du upp det

Vilken väg in du tar beror bara på om verktyget har en sessionskrok.

| | |
|---|---|
| **Claude Code** | Installera som plugin och kör startkommandot en gång inne i ett repo. Inget skrivs till din kod, och därefter börjar varje session med indexet redan i kontexten. |
| **Allt annat, Hermes inräknat** | Fråga först vad chamnan upptäcker och säg sedan vilken agent det ska skriva för. När repots form ändras bygger du om indexet och skriver filen igen; en valfri Git-krok gör bådadera vid commit. Claude Code behövs inte: det här är vanliga kommandon och plugin-paketet är bara en leveransväg, inte produkten. Utan angiven agent skriver det ut vad det upptäckt och vilket kommando som skulle passa, och lämnar beslutet till dig. Det skriver aldrig på en gissning. |

Kommandonamn, hela listan över agenter och filen var och en får finns i den engelska README-filen, där varje versionsbunden detalj bor.


## Krav

Claude Code · Python · Git · macOS, Linux eller Windows

Inget mer, och inga beroenden att installera. Lägsta Python-version står i [README › Requirements](../../README.md#requirements) — den här sidan bär inga siffror, eftersom det är siffrorna som ändras.

## Stänga av eller ta bort

Stäng av delvis i `.chamnan/config.json` · stoppa det i ett enda förråd · ta bort tillägget från hela maskinen · radera `.chamnan/` när du vill utan att något går sönder — stegen finns i [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
