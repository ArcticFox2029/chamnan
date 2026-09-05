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

<!-- generated: build_sections.py -->

## Alle funktioner

Fire evner. Alt herunder kører rent faktisk i den nuværende udgave. Hver del kan slås fra hver for sig i `.chamnan/config.json`, og ingen afhænger af de andre.

### Forstå — hvad der findes, og hvad der hænger sammen med hvad

| | |
|---|---|
| **Indeks** | `MAP.md` — én linje pr. fil, dannet ud fra koden selv. Agenten læser indekset og greper den detalje, den skal bruge, i stedet for at gå hele træet igennem. |
| **Påvirkning** | Hvem der afhænger af denne fil, og hvilke tests der dækker den. Filens egne imports står alligevel øverst i den; det dyre er den modsatte retning — grep stien, før du retter. |
| **Datamodel** | Tabel- og modelnavne med én linjes beskrivelse, hentet fra DDL, migreringer og ORM-modeller — ikke et dump af hele skemaet. Vises kun, hvis arkivet faktisk definerer et. |
| **API-flade** | Metode, sti og handler, fra rutedekoratorer, OpenAPI-dokumenter og `.proto`-servicedefinitioner — ikke hele specifikationen. |
| **Konfiguration** | Navnene på de miljøvariabler, arkivet læser. **Kun navne, aldrig værdier** — og den advarer, hvis `.env` ikke er i gitignore. |
| **Udrulning** | Hvad der faktisk kører, læst fra manifester til Kubernetes, Ansible, Compose, Helm og CI: typer og navne, images, roller, pipelines. Fra en Secret tages kun navnet, intet af det nedenunder. |
| **Ikke-kildemateriale** | Skannede papirer, eksporter, arkiver — kun antal, størrelser og de hyppigste filendelser. Afsnittet findes, for at agenten ikke selv går ind og kigger, hvilket koster langt mere. **Åbnes aldrig, læses aldrig.** |

### Huske — hvad der var i gang, og hvorfor

| | |
|---|---|
| **Arbejdstilstand** | `STATE.md` — det, der arbejdes på lige nu; sættes ind ved sessionens start, så komprimeringen af konteksten holder op med at slette det. |
| **Sessionsnotat** | Ét pr. session under `.chamnan/sessions/`. Til næste session når **kun det ufærdige**; en session, der er lukket pænt, sætter slet intet ind. |
| **Hukommelse** | `decisions/`, `lessons/`, `rules/`. Regler er blivende begrænsninger og står derfor foran agenten hver session; beslutninger og lærdomme bidrager kun med en titel og læses, når titlen ser relevant ud. |
| **Åbne tråde** | Arbejdslinjer, der endnu ikke er lukket, med historikken over hvilke filer tråden har rørt — og de følger filen også efter en omdøbning. |

### Genbruge — det, der allerede er løst én gang

| | |
|---|---|
| **Fremgangsmåder** | Færdigheder, som agenten skriver **selv**, når den støder på noget indviklet eller gentaget. Ikke et medfølgende bibliotek, men en mekanisme. |
| **Værktøjer** | Bemærker, at det samme engangsskript er skrevet igen, og tilbyder at gemme det — og nævner det, før du skriver et nyt. |
| **Arbejdsgange** | Bemærker, at de samme kommandoer er kørt i samme rækkefølge på adskilte dage, og tilbyder at skrive den rækkefølge ned. |

### Vokse — hvad arkivet har lært om sig selv

| | |
|---|---|
| **Milepæle** | De få ændringer, der omformede arkivet: hvad der flyttede sig, hvorfor det var det værd, hvilke områder det rørte. |
| **Kandidater** | Opdagede gentagne kommandorækker holdes **altid tilbage og venter på et menneskes bekræftelse**. Intet forfremmes automatisk. |
| **Miljøer** | Erklær, hvad production eller staging er, og hvad der er forbudt der — og den siger til, når den erklæring bliver gammel. |
| **Rapport** | Hvad arbejdsrummet indeholder, om det faktisk kan nås, og hvordan konteksten pr. tur har ændret sig i dit arkiv. Dit tal, ikke vores. |

Gentaget ingeniørarbejde bliver til genbrugelig arkivviden — **ikke træning af en model, og ikke automatisering af udvikleren.** Det er en måde at bevare arbejde, der ellers kun fandtes i hovedet på den, der udførte det.

## Kommandoer

Alle kan kaldes fra skallen, og agenten kalder dem også selv.

| | |
|---|---|
| `chamnan-map` | bygger og opdaterer indekset |
| `chamnan-report` | hvad arbejdsrummet indeholder, og hvordan konteksten pr. tur har ændret sig |
| `chamnan-impact` | hvem der afhænger af denne fil, og hvilke tests der dækker den |
| `chamnan-timeline` | hvad der hidtil er sket med denne fil |
| `chamnan-peek` | siger, hvad der er i en stor fil, uden at læse den ind i konteksten |
| `chamnan-promote` | gemmer et skript som fast værktøj for arkivet |
| `chamnan-candidates` | se, bekræfte eller afvise opdagede gentagelser |
| `chamnan-env` | erklære et miljø og dets forbud, og kontrollere at erklæringen stadig er frisk |
| `chamnan-age` | hvor den gemte viden er begyndt at blive gammel |

Og færdigheder, der kaldes inde fra sessionen: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Hvad den skriver, og hvor

Alt inde i `.chamnan/`, almindelig markdown og JSON. Kan læses, rettes i hånden og slettes når som helst, uden at noget går i stykker.

| | |
|---|---|
| `MAP.md` | hvad der findes, og hvad der afhænger af hvad |
| `STATE.md` | hvad der arbejdes på lige nu |
| `sessions/` | hvor det forrige arbejde stoppede |
| `memory/` | beslutninger, lærdomme og blivende regler |
| `threads/` | arbejdslinjer, der stadig er åbne |
| `skills/` · `tools/` | fremgangsmåder og skripter, der er værd at gemme |
| `milestones.md` | de ændringer, der omformede arkivet |
| `config.json` | til og fra for hver del, og byteloftet for den blok, der sættes ind i sessionen |

**Den eneste skrivning uden for `.chamnan/`** er en valgfri Git-pre-commit-hook, der holder indekset i takt med træet — den lægges kun ind, hvis du siger ja, og kan fjernes.

**Agenten lærer ikke.** Intet trænes, intet bliver tilbage uden for denne mappe, og næste session begynder stadig fra nul — bare fra nul *i et arkiv, der forklarer sig selv*. Sammenhængen ligger i artefakterne, ikke i modellen.

## Sikkerhed

| | |
|---|---|
| **Ingen netværkskald under kørsel** | Ikke ét. Der kræves ingen API-nøgle, og intet sendes nogen steder hen. |
| **Skriver ikke din kode om** | Den rapporterer, den retter ikke. Indekset kopierer de kommentarer, du allerede har skrevet, og finder dem ikke på; filer uden kommentar nævnes ved navn, så du selv kan udfylde dem. |
| **Ingen dæmon, intet baggrundsarbejde** | Ingen blivende proces, ingen database, ingen embedding-model — kun Pythons standardbibliotek. |
| **Hemmeligheder filtreres først** | Alt, der skal skrives eller sættes ind i sessionen, går først gennem hemmelighedsfilteret: variablernes *navne* bliver, værdierne ikke. Og den grænse, filteret ikke når, står ved siden af sit eget tal i den engelske README. |
| **Hvad et installeret plugin kan gøre ved dig** | Forklaret fuldt ud i den engelske README, herunder hvor chamnan bryder lækagekæden. |

## Hvad det virker sammen med

chamnan er tekst og Python fra standardbiblioteket. Intet i indekset tilhører én bestemt leverandør, én bestemt editor eller ét bestemt styresystem.

| | |
|---|---|
| **Enhver model, enhver leverandør** | Indekset er almindelig tekst og sendes med som kontekst. Modellen ændrer kun, hvor meget det er værd at sende, aldrig hvor noget havner. Størrelsen sættes med `--model`, `--window` eller `--profile`. At skifte model kræver ingen geninstallation. `--model` genkender disse familier på navnet: `claude` · `codestral` · `deepseek` · `gemini` · `gemma` · `glm` · `gpt` · `grok` · `kimi` · `mistral` · `openai` — sammenligningen ser bort fra store og små bogstaver, skilletegn og versionsnumre. `llama` og `qwen` er bevidst udeladt: begge kommer i flere størrelser, der vil have forskellige budgetter, så at nævne dem giver standardprofilen og en linje om, hvilke to størrelser der kunne være ment. **En model, der ikke står på listen, virker alligevel**: den får standardprofilen og en note om, at den ikke blev genkendt, og intet fejler. `--window` tager tallet direkte og er altid præcist. |
| **macOS, Linux, Windows, WSL** | Samme plugin overalt, kun standardbibliotek, intet at installere. På macOS og Linux køres kommandoerne direkte. På Windows kan skallen ikke køre et script uden filendelse, så ved siden af hver kommando og hvert hook ligger en genereret `.cmd`; de følger med plugin'et, og CI kører netop dem. WSL opfører sig som Linux. |
| **Mange agenter, ét indeks** | Claude Code får blokken via et sessionshook, og der skrives ingen fil ind i dit projekt. Gemini CLI har også et rigtigt sessionshook. Øvrige agenter får en fil på den sti, agenten læser, og de der læser samme sti deler filen i stedet for hver at have en kopi, der driver fra hinanden. |
| **Hermes Agent** | Hermes er samtidig et styringslag, der dirigerer andre kodeagenter, så et repo sat op til det betyder ofte, at flere værktøjer læser det samme indeks. Det leder efter projektinstruktioner i en fast rækkefølge og tager den første, det finder; chamnan skriver filen forrest i den rækkefølge, tilpasser størrelsen til den grænse, Hermes selv dokumenterer, og nægter at overskrive en fil, det ikke har skrevet. |

## Sådan sætter du det op

Hvilken vej ind du tager, afhænger kun af, om værktøjet har et sessionshook.

| | |
|---|---|
| **Claude Code** | Installér som plugin, og kør startkommandoen én gang inde i et repo. Der skrives intet til din kode, og derefter begynder hver session med indekset allerede i konteksten. |
| **Alt andet, Hermes iberegnet** | Spørg først, hvad chamnan finder, og sig så, hvilken agent der skal skrives for. Når repoets form ændrer sig, bygger du indekset igen og skriver filen på ny; et valgfrit Git-hook gør begge dele ved commit. Claude Code er ikke nødvendig: det er almindelige kommandoer, og plugin'et er blot én leveringsvej, ikke produktet. Uden en nævnt agent skriver det ud, hvad det fandt, og hvilken kommando der ville passe, og lader beslutningen være din. Det skriver aldrig på et gæt. |

Kommandonavne, hele listen over agenter og den fil, hver enkelt får, står i den engelske README, hvor hver versionsbundet detalje bor.


## Krav

Claude Code · Python · Git · macOS, Linux eller Windows

Ikke andet, og ingen afhængigheder at installere. Den laveste Python-version står i [README › Requirements](../../README.md#requirements) — denne side bærer ingen tal, for det er tallene, der ændrer sig.

## Slå fra eller fjerne

Slå fra del for del i `.chamnan/config.json` · stop det i ét enkelt arkiv · fjern plugin'et fra hele maskinen · slet `.chamnan/` når du vil, uden at noget går i stykker — trinene står i [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
