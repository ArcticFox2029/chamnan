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

<!-- generated: build_sections.py -->

## Toate funcțiile

Patru capacități. Tot ce apare mai jos chiar rulează în versiunea curentă. Fiecare parte poate fi oprită separat în `.chamnan/config.json`, și niciuna nu depinde de celelalte.

### A înțelege — ce există și ce este legat de ce

| | |
|---|---|
| **Index** | `MAP.md` — o linie pe fișier, generată din codul însuși. Agentul citește indexul și face grep pe detaliul de care are nevoie, în loc să parcurgă tot arborele. |
| **Impact** | Cine depinde de acest fișier și ce teste îl acoperă. Importurile proprii sunt oricum în capul fișierului; scump este sensul invers — faceți grep pe cale înainte de a modifica. |
| **Model de date** | Nume de tabele și modele cu o linie de descriere, extrase din DDL, migrări și modele ORM — nu o descărcare a întregii scheme. Apare doar dacă depozitul chiar definește una. |
| **Suprafața API** | Metodă, cale și handler, din decoratori de rute, documente OpenAPI și definiții de serviciu `.proto` — nu întreaga specificație. |
| **Configurație** | Numele variabilelor de mediu pe care depozitul le citește. **Doar nume, niciodată valori** — și avertizează dacă `.env` nu este în gitignore. |
| **Implementare** | Ce rulează cu adevărat, citit din manifeste Kubernetes, Ansible, Compose, Helm și CI: tipuri și nume, imagini, roluri, conducte. Dintr-un Secret ia doar numele, nimic din ce se află dedesubt. |
| **Material care nu este cod** | Documente scanate, exporturi, arhive — doar numărători, dimensiuni și extensiile predominante. Există ca agentul să nu se ducă să se uite singur, ceea ce costă mult mai mult. **Niciodată deschis, niciodată citit.** |

### A ține minte — ce se făcea și de ce

| | |
|---|---|
| **Starea lucrului** | `STATE.md` — la ce se lucrează chiar acum; se introduce la începutul sesiunii, ca să nu-l mai șteargă compactarea contextului. |
| **Însemnare de sesiune** | Una pe sesiune, sub `.chamnan/sessions/`. În sesiunea următoare ajunge **doar ce a rămas neterminat**; o sesiune închisă curat nu introduce nimic. |
| **Memorie** | `decisions/`, `lessons/`, `rules/`. Regulile sunt constrângeri permanente, deci stau în fața agentului la fiecare sesiune; deciziile și lecțiile dau doar un titlu și sunt citite când titlul pare potrivit. |
| **Fire deschise** | Linii de lucru încă neînchise, cu istoricul fișierelor pe care firul le-a atins — și le urmăresc și după o redenumire. |

### A refolosi — ce a fost deja rezolvat o dată

| | |
|---|---|
| **Proceduri** | Deprinderi pe care agentul le scrie **singur** când dă peste ceva complicat sau repetat. Nu o bibliotecă livrată, ci un mecanism. |
| **Unelte** | Observă că același script de unică folosință a fost scris din nou și propune să-l păstreze — și îl amintește înainte să scrieți altul. |
| **Fluxuri de lucru** | Observă că aceleași comenzi au rulat în aceeași ordine în zile distincte, și propune să scrie secvența. |

### A se aduna — ce a învățat depozitul despre sine

| | |
|---|---|
| **Repere** | Puținele schimbări care au remodelat depozitul: ce s-a mutat, de ce a meritat, ce zone a atins. |
| **Candidați** | Secvențele repetate de comenzi detectate rămân **întotdeauna în așteptarea confirmării unui om**. Nimic nu este promovat automat. |
| **Medii** | Declarați ce este production sau staging și ce este interzis acolo — iar el vă avertizează când declarația se învechește. |
| **Raport** | Ce ține spațiul de lucru, dacă este într-adevăr accesibil, și cum s-a schimbat contextul pe tură în depozitul dumneavoastră. Cifra dumneavoastră, nu a noastră. |

Munca de inginerie repetată devine cunoaștere reutilizabilă a depozitului — **nu antrenarea unui model și nici automatizarea dezvoltatorului.** Este un mod de a păstra o muncă ce altfel ar exista doar în capul celui care a făcut-o.

## Comenzi

Toate pot fi apelate din shell, iar agentul le apelează și singur.

| | |
|---|---|
| `chamnan-map` | construiește și actualizează indexul |
| `chamnan-report` | ce ține spațiul de lucru și cum s-a schimbat contextul pe tură |
| `chamnan-impact` | cine depinde de acest fișier și ce teste îl acoperă |
| `chamnan-timeline` | ce i s-a întâmplat până acum acestui fișier |
| `chamnan-peek` | spune ce se află într-un fișier mare fără a-l citi în context |
| `chamnan-promote` | păstrează un script ca unealtă permanentă a depozitului |
| `chamnan-candidates` | a vedea, a confirma sau a respinge repetițiile detectate |
| `chamnan-env` | a declara un mediu și interdicțiile lui, și a verifica dacă declarația este încă proaspătă |
| `chamnan-age` | de unde a început să se învechească cunoașterea păstrată |

Și deprinderile apelate din interiorul sesiunii: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Ce scrie și unde

Totul în `.chamnan/`, markdown și JSON obișnuite. Se pot citi, edita de mână și șterge oricând fără să se strice nimic.

| | |
|---|---|
| `MAP.md` | ce există și ce depinde de ce |
| `STATE.md` | la ce se lucrează chiar acum |
| `sessions/` | unde s-a oprit lucrul precedent |
| `memory/` | decizii, lecții și reguli permanente |
| `threads/` | linii de lucru încă deschise |
| `skills/` · `tools/` | proceduri și scripturi care merită păstrate |
| `milestones.md` | schimbările care au remodelat depozitul |
| `config.json` | pornirea și oprirea fiecărei părți, și plafonul în octeți al blocului introdus în sesiune |

**Singura scriere în afara `.chamnan/`** este un hook Git pre-commit opțional care ține indexul la pas cu arborele — se instalează doar dacă spuneți da, și poate fi scos.

**Agentul nu învață.** Nimic nu este antrenat, nimic nu rămâne în afara acestui director, iar sesiunea următoare tot de la zero pornește — doar că de la zero *într-un depozit care se explică singur*. Continuitatea este în artefacte, nu în model.

## Siguranță

| | |
|---|---|
| **Niciun apel de rețea la execuție** | Niciunul. Nu e nevoie de cheie API și nimic nu pleacă nicăieri. |
| **Nu vă rescrie codul** | Raportează, nu editează. Indexul copiază comentariile pe care le-ați scris deja, nu le inventează; fișierele fără comentariu sunt numite ca să le completați dumneavoastră. |
| **Fără demon, fără muncă în fundal** | Niciun proces rezident, nicio bază de date, niciun model de embedding — doar biblioteca standard Python. |
| **Secretele sunt filtrate mai întâi** | Tot ce urmează să fie scris sau introdus în sesiune trece mai întâi prin filtrul de secrete: rămân *numele* variabilelor, nu valorile. Iar limita la care acel filtru nu ajunge este scrisă lângă propria ei cifră în README-ul în engleză. |
| **Ce vă poate face un plugin instalat** | Explicat în întregime în README-ul în engleză, inclusiv unde chamnan rupe lanțul de scurgere. |

## Cu ce funcționează

chamnan este text și Python din biblioteca standard. Nimic din index nu aparține unui anumit furnizor, unui anumit editor sau unui anumit sistem de operare.

| | |
|---|---|
| **Orice model, orice furnizor** | Indexul este text simplu și se trimite drept context. Modelul schimbă doar cât merită trimis, niciodată unde ajunge ceva. Dimensiunea se reglează cu `--model`, `--window` sau `--profile`. Schimbarea modelului nu cere nicio reinstalare. `--model` recunoaște aceste familii după nume: `claude` · `codestral` · `deepseek` · `gemini` · `gemma` · `glm` · `gpt` · `grok` · `kimi` · `mistral` · `openai` — potrivirea nu ține cont de majuscule, separatori sau numere de versiune. `llama` și `qwen` lipsesc intenționat: ambele apar în mai multe dimensiuni care cer bugete diferite, așa că numindu-le primești profilul implicit și un rând care spune la care două dimensiuni s-ar fi putut referi. **Un model care nu e pe listă funcționează oricum**: primește profilul implicit și o notă că nu a fost recunoscut, și nimic nu eșuează. `--window` ia numărul direct și este întotdeauna exact. |
| **macOS, Linux, Windows, WSL** | Același plugin peste tot, doar bibliotecă standard, nimic de instalat. Pe macOS și Linux comenzile rulează direct. Pe Windows interpretorul nu poate rula un script fără extensie, așa că lângă fiecare comandă și fiecare cârlig stă un `.cmd` generat; sunt livrate cu pluginul, iar CI le rulează chiar pe ele. WSL se comportă ca Linux. |
| **Mulți agenți, un singur index** | Claude Code îl primește printr-un cârlig de sesiune și nu se scrie niciun fișier în proiectul tău. Și Gemini CLI are un cârlig de sesiune adevărat. Ceilalți agenți primesc un fișier în calea pe care o citesc, iar cei care citesc aceeași cale împart fișierul în loc ca fiecare să țină o copie care se depărtează. |
| **Hermes Agent** | Hermes este totodată un strat de control care dirijează alți agenți de cod, așa că un depozit pregătit pentru el înseamnă adesea mai multe unelte care citesc același index. Caută instrucțiunile proiectului într-o ordine fixă și ia prima găsită; chamnan scrie fișierul aflat în fruntea acelei ordini, îi potrivește dimensiunea la limita documentată chiar de Hermes și refuză să suprascrie un fișier pe care nu l-a scris el. |

## Cum îl instalezi

Pe ce cale intri depinde numai de faptul dacă unealta are sau nu un cârlig de sesiune.

| | |
|---|---|
| **Claude Code** | Instalează-l ca plugin și rulează o dată comanda de pornire într-un depozit. Nu se scrie nimic în codul tău, iar de atunci fiecare sesiune începe cu indexul deja în context. |
| **Tot restul, inclusiv Hermes** | Întreabă mai întâi ce a detectat chamnan, apoi spune-i pentru care agent să scrie. Când forma depozitului se schimbă, reconstruiește indexul și scrie fișierul din nou; un cârlig Git opțional le face pe amândouă la commit. Nu e nevoie de Claude Code: acestea sunt comenzi obișnuite, iar pluginul e doar o cale de livrare, nu produsul. Fără un agent numit, tipărește ce a detectat și ce comandă s-ar potrivi, lăsându-ți ție decizia. Nu scrie niciodată pe ghicite. |

Numele comenzilor, lista completă a agenților și fișierul primit de fiecare se află în README-ul în engleză, unde locuiește orice detaliu legat de o versiune.


## Cerințe

Claude Code · Python · Git · macOS, Linux sau Windows

Nimic altceva și nicio dependență de instalat. Versiunea minimă de Python se află în [README › Requirements](../../README.md#requirements) — această pagină nu poartă cifre, fiindcă tocmai cifrele se schimbă.

## Oprire sau eliminare

Opriți pe părți în `.chamnan/config.json` · opriți-l într-un singur depozit · eliminați pluginul de pe toată mașina · ștergeți `.chamnan/` oricând, fără să se strice nimic — pașii detaliați în [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
