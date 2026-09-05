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

<!-- generated: build_sections.py -->

## Alle funksjoner

Fire evner. Alt nedenfor kjører faktisk i den nåværende utgaven. Hver del kan slås av hver for seg i `.chamnan/config.json`, og ingen avhenger av de andre.

### Forstå — hva som finnes, og hva som henger sammen med hva

| | |
|---|---|
| **Indeks** | `MAP.md` — én linje per fil, laget ut fra koden selv. Agenten leser indeksen og greper den detaljen den trenger, i stedet for å gå gjennom hele treet. |
| **Virkning** | Hvem som avhenger av denne filen, og hvilke tester som dekker den. Filens egne importer står uansett øverst i den; det dyre er motsatt retning — grep stien før du endrer. |
| **Datamodell** | Tabell- og modellnavn med én linjes beskrivelse, hentet fra DDL, migreringer og ORM-modeller — ikke en dump av hele skjemaet. Vises bare hvis repositoriet faktisk definerer et. |
| **API-flate** | Metode, sti og handler, fra rutedekoratorer, OpenAPI-dokumenter og `.proto`-tjenestedefinisjoner — ikke hele spesifikasjonen. |
| **Konfigurasjon** | Navnene på miljøvariablene repositoriet leser. **Bare navn, aldri verdier** — og den advarer hvis `.env` ikke ligger i gitignore. |
| **Utrulling** | Hva som faktisk kjører, lest fra manifester for Kubernetes, Ansible, Compose, Helm og CI: typer og navn, images, roller, pipelines. Fra en Secret tas bare navnet, ingenting av det som ligger under. |
| **Ikke-kildemateriale** | Skannede papirer, eksporter, arkiver — bare antall, størrelser og de vanligste filendelsene. Avsnittet finnes for at agenten ikke skal gå og se selv, noe som koster langt mer. **Åpnes aldri, leses aldri.** |

### Huske — hva som holdt på, og hvorfor

| | |
|---|---|
| **Arbeidstilstand** | `STATE.md` — det som arbeides med akkurat nå; settes inn når økten starter, slik at komprimering av konteksten slutter å slette det. |
| **Øktnotat** | Ett per økt under `.chamnan/sessions/`. Til neste økt når **bare det uferdige**; en økt som er avsluttet ryddig, setter ikke inn noe som helst. |
| **Hukommelse** | `decisions/`, `lessons/`, `rules/`. Regler er varige begrensninger og står derfor foran agenten hver økt; beslutninger og lærdommer bidrar bare med en tittel og leses når tittelen virker relevant. |
| **Åpne tråder** | Arbeidslinjer som ennå ikke er lukket, med historikken over hvilke filer tråden har vært innom — og de følger filen også etter et navnebytte. |

### Gjenbruke — det som allerede er løst én gang

| | |
|---|---|
| **Framgangsmåter** | Ferdigheter agenten skriver **selv** når den støter på noe innfløkt eller gjentatt. Ikke et medfølgende bibliotek, men en mekanisme. |
| **Verktøy** | Merker at det samme engangsskriptet er skrevet igjen, og tilbyr å ta vare på det — og nevner det før du skriver et nytt. |
| **Arbeidsflyter** | Merker at de samme kommandoene gikk i samme rekkefølge på atskilte dager, og tilbyr å skrive ned rekkefølgen. |

### Vokse — hva repositoriet har lært om seg selv

| | |
|---|---|
| **Milepæler** | De få endringene som formet repositoriet om: hva som flyttet seg, hvorfor det var verdt det, hvilke områder det rørte. |
| **Kandidater** | Oppdagede gjentatte kommandorekker holdes **alltid tilbake i påvente av et menneskes bekreftelse**. Ingenting forfremmes automatisk. |
| **Miljøer** | Erklær hva production eller staging er og hva som er forbudt der — og den sier fra når den erklæringen blir gammel. |
| **Rapport** | Hva arbeidsrommet inneholder, om det faktisk er å nå, og hvordan konteksten per tur har endret seg i ditt repositorium. Ditt tall, ikke vårt. |

Gjentatt ingeniørarbeid blir til gjenbrukbar repositoriekunnskap — **ikke trening av en modell, og ikke automatisering av utvikleren.** Det er en måte å bevare arbeid som ellers bare fantes i hodet på den som gjorde det.

## Kommandoer

Alle kan kalles fra skallet, og agenten kaller dem også selv.

| | |
|---|---|
| `chamnan-map` | bygger og oppdaterer indeksen |
| `chamnan-report` | hva arbeidsrommet inneholder, og hvordan konteksten per tur har endret seg |
| `chamnan-impact` | hvem som avhenger av denne filen, og hvilke tester som dekker den |
| `chamnan-timeline` | hva som hittil har skjedd med denne filen |
| `chamnan-peek` | sier hva som er i en stor fil uten å lese den inn i konteksten |
| `chamnan-promote` | tar vare på et skript som fast verktøy for repositoriet |
| `chamnan-candidates` | se, bekrefte eller avvise oppdagede gjentakelser |
| `chamnan-env` | erklære et miljø og forbudene der, og sjekke at erklæringen fortsatt er fersk |
| `chamnan-age` | hvor den lagrede kunnskapen har begynt å bli gammel |

Og ferdigheter som kalles inne fra økten: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Hva den skriver, og hvor

Alt inne i `.chamnan/`, vanlig markdown og JSON. Kan leses, endres for hånd og slettes når som helst uten at noe går i stykker.

| | |
|---|---|
| `MAP.md` | hva som finnes, og hva som avhenger av hva |
| `STATE.md` | hva det arbeides med akkurat nå |
| `sessions/` | hvor forrige arbeidsøkt stanset |
| `memory/` | beslutninger, lærdommer og varige regler |
| `threads/` | arbeidslinjer som fortsatt er åpne |
| `skills/` · `tools/` | framgangsmåter og skript det er verdt å ta vare på |
| `milestones.md` | endringene som formet repositoriet om |
| `config.json` | på og av for hver del, og bytetaket for blokken som settes inn i økten |

**Den eneste skrivingen utenfor `.chamnan/`** er en valgfri Git-pre-commit-hook som holder indeksen i takt med treet — den legges bare inn hvis du sier ja, og kan fjernes.

**Agenten lærer ikke.** Ingenting trenes, ingenting blir igjen utenfor denne mappen, og neste økt begynner fortsatt fra null — bare fra null *i et repositorium som forklarer seg selv*. Sammenhengen ligger i artefaktene, ikke i modellen.

## Sikkerhet

| | |
|---|---|
| **Ingen nettverkskall under kjøring** | Ikke ett. Ingen API-nøkkel trengs, og ingenting sendes noe sted. |
| **Skriver ikke om koden din** | Den rapporterer, den redigerer ikke. Indeksen kopierer kommentarene du allerede har skrevet, og dikter dem ikke opp; filer uten kommentar nevnes ved navn så du kan fylle dem ut selv. |
| **Ingen daemon, ingen bakgrunnsarbeid** | Ingen vedvarende prosess, ingen database, ingen embedding-modell — bare Pythons standardbibliotek. |
| **Hemmeligheter filtreres først** | Alt som skal skrives eller settes inn i økten, går først gjennom hemmelighetsfilteret: variablenes *navn* blir igjen, verdiene ikke. Og grensen filteret ikke når, står ved siden av sitt eget tall i den engelske README-en. |
| **Hva et installert tillegg kan gjøre mot deg** | Forklart i sin helhet i den engelske README-en, inkludert hvor chamnan bryter lekkasjekjeden. |

## Hva det virker sammen med

chamnan er tekst og Python fra standardbiblioteket. Ingenting i indeksen tilhører én bestemt leverandør, én bestemt editor eller ett bestemt operativsystem.

| | |
|---|---|
| **Enhver model, enhver leverandør** | Indeksen er vanlig tekst og sendes med som kontekst. Modellen endrer bare hvor mye det er verdt å sende, aldri hvor noe havner. Størrelsen settes med `--model`, `--window` eller `--profile`. Å bytte modell krever ingen reinstallasjon. |
| **macOS, Linux, Windows, WSL** | Samme plugin overalt, bare standardbibliotek, ingenting å installere. På macOS og Linux kjøres kommandoene direkte. På Windows kan skallet ikke kjøre et skript uten filendelse, så ved siden av hver kommando og hver krok ligger en generert `.cmd`; de følger med plugin-et, og CI kjører nettopp dem. WSL oppfører seg som Linux. |
| **Mange agenter, ét indeks** | Claude Code får blokken via en øktkrok, og ingen fil skrives inn i prosjektet ditt. Gemini CLI har også en ekte øktkrok. Øvrige agenter får en fil på stien agenten leser, og de som leser samme sti deler filen i stedet for at hver har en kopi som driver fra hverandre. |
| **Hermes Agent** | Hermes er samtidig et styringslag som dirigerer andre kodeagenter, så et repo satt opp for det betyr ofte at flere verktøy leser den samme indeksen. Det leter etter prosjektinstruksjoner i en fast rekkefølge og tar den første det finner; chamnan skriver filen først i den rekkefølgen, tilpasser størrelsen til grensen Hermes selv dokumenterer, og nekter å overskrive en fil det ikke har skrevet. |

## Slik setter du det opp

Hvilken vei inn du tar, avhenger bare av om verktøyet har en øktkrok.

| | |
|---|---|
| **Claude Code** | Installer som plugin, og kjør startkommandoen én gang inne i et repo. Ingenting skrives til koden din, og deretter starter hver økt med indeksen allerede i konteksten. |
| **Alt andet, Hermes iberegnet** | Spør først hva chamnan finner, og si så hvilken agent den skal skrive for. Når formen på repoet endres, bygger du indeksen på nytt og skriver filen igjen; en valgfri Git-krok gjør begge deler ved commit. Claude Code trengs ikke: dette er vanlige kommandoer, og plugin-et er bare én leveringsvei, ikke produktet. Uten en nevnt agent skriver det ut hva det fant og hvilken kommando som ville passe, og lar avgjørelsen være din. Det skriver aldri på en gjetning. |

Kommandonavn, hele listen over agenter og filen hver av dem får, står i den engelske README-en, der hver versjonsbundet detalj bor.


## Krav

Claude Code · Python · Git · macOS, Linux eller Windows

Ikke noe mer, og ingen avhengigheter å installere. Laveste Python-versjon står i [README › Requirements](../../README.md#requirements) — denne siden bærer ingen tall, for det er tallene som endrer seg.

## Slå av eller fjerne

Slå av del for del i `.chamnan/config.json` · stopp det i ett enkelt repositorium · fjern tillegget fra hele maskinen · slett `.chamnan/` når du vil, uten at noe går i stykker — trinnene står i [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
