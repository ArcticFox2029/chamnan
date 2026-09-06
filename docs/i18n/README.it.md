# chamnan — perché un repository conosca sé stesso

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Questa pagina non contiene numeri, di proposito. Tutte le misure stanno nel README in inglese e cambiano a ogni rilascio; questa pagina no. → [Evidence](../../README.md#evidence)

## Che cos'è

Un plugin per Claude Code. Costruisce un indice del repository che l'agente legge invece di scorrere i file uno per uno, e conserva il contesto tecnico che si accumula mentre lavori — lo stato del lavoro, gli appunti di sessione, le ragioni dietro le decisioni e le procedure che rideduci ogni volta.

Tutto ciò che scrive è markdown ordinario, versionato accanto al codice. Nessuna chiamata di rete a runtime, nessun database, nessun demone, nessun modello di embedding: solo la libreria standard di Python.

## Che cosa risolve

A ogni nuova sessione, e ogni volta che il contesto viene compattato, sparisce tutto ciò che l'agente aveva capito del tuo codice e ricomincia a cercare da zero.

chamnan fa sì che quella riscoperta non debba avvenire: l'indice viene consegnato all'avvio della sessione, e il costo è un numero noto e limitato invece di letture di file senza limite.

## Installazione

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Apri una nuova sessione, poi esegui `/chamnan:bootstrap` una volta per repository.

<!-- generated: build_sections.py -->

## Tutte le funzionalità

Quattro capacità. Tutto quello che segue funziona davvero nella versione attuale. Ogni parte si può spegnere separatamente in `.chamnan/config.json`, e nessuna dipende dalle altre.

### Capire — che cosa esiste e che cosa è collegato a che cosa

| | |
|---|---|
| **Indice** | `MAP.md` — una riga per file, generata dal codice stesso. L'agente legge l'indice e fa grep del dettaglio che gli serve, invece di percorrere l'albero. |
| **Impatto** | Chi dipende da questo file e quali test lo coprono. I suoi import stanno già in cima al file; ciò che costa è l'arco inverso — fate grep del percorso prima di modificare. |
| **Modello dei dati** | Nomi di tabelle e modelli con una riga di descrizione, estratti da DDL, migrazioni e modelli ORM — non un dump dell'intero schema. Compare solo se il repository ne definisce uno. |
| **Superficie API** | Metodo, percorso e handler, dai decoratori di rotta, dai documenti OpenAPI e dalle definizioni di servizio `.proto` — non l'intera specifica. |
| **Configurazione** | I nomi delle variabili d'ambiente che il repository legge. **Solo nomi, mai valori** — e avverte se `.env` non è in gitignore. |
| **Distribuzione** | Ciò che gira davvero, letto dai manifest di Kubernetes, Ansible, Compose, Helm e CI: tipi e nomi, immagini, ruoli, pipeline. Di un Secret prende solo il nome, nulla di ciò che contiene. |
| **Materiale non sorgente** | Documenti scansionati, esportazioni, archivi — solo conteggi, dimensioni ed estensioni prevalenti. Esiste perché l'agente non vada a guardare da sé, cosa che costa molto di più. **Mai aperto, mai letto.** |

### Ricordare — che cosa si stava facendo, e perché

| | |
|---|---|
| **Stato del lavoro** | `STATE.md` — ciò su cui si lavora proprio adesso; iniettato all'avvio della sessione, così la compattazione del contesto smette di cancellarlo. |
| **Registro di sessione** | Uno per sessione sotto `.chamnan/sessions/`. Alla sessione successiva arriva **solo ciò che è rimasto incompiuto**; una sessione chiusa bene non inietta nulla. |
| **Memoria** | `decisions/`, `lessons/`, `rules/`. Le regole sono vincoli permanenti, quindi stanno davanti all'agente a ogni sessione; decisioni e lezioni contribuiscono solo con un titolo e vengono lette quando il titolo appare pertinente. |
| **Fili aperti** | Linee di lavoro non ancora chiuse, con la storia dei file che quel filo ha toccato — e continuano a seguirli anche dopo una rinomina. |

### Riusare — ciò che è già stato risolto

| | |
|---|---|
| **Procedure** | Competenze che l'agente scrive **da sé** quando incontra qualcosa di complesso o ripetuto. Non una libreria già pronta, ma un meccanismo. |
| **Strumenti** | Nota che lo stesso script usa-e-getta è stato riscritto e propone di conservarlo — e lo ricorda prima che ne scriviate uno nuovo. |
| **Flussi di lavoro** | Nota che gli stessi comandi sono girati nello stesso ordine in giorni distinti, e propone di mettere per iscritto quella sequenza. |

### Accumulare — ciò che il repository ha imparato su di sé

| | |
|---|---|
| **Pietre miliari** | I pochi cambiamenti che hanno rimodellato il repository: che cosa si è spostato, perché ne valeva la pena, quali aree ha toccato. |
| **Candidati** | Le sequenze di comandi ripetute che vengono rilevate restano **sempre in attesa di conferma umana**. Nulla viene promosso in automatico. |
| **Ambienti** | Dichiarate che cosa sia production o staging e che cosa vi sia vietato — e vi avviserà quando quella dichiarazione invecchia. |
| **Rapporto** | Che cosa contiene lo spazio di lavoro, se è davvero raggiungibile, e come è cambiato il contesto per turno nel vostro repository. Il vostro numero, non il nostro. |

Il lavoro ingegneristico ripetuto diventa conoscenza riusabile del repository — **non è addestrare un modello né automatizzare lo sviluppatore.** È un modo di conservare un lavoro che altrimenti esisterebbe solo nella testa di chi l'ha fatto.

## Comandi

Tutti richiamabili dalla shell, e l'agente li richiama anche da sé.

| | |
|---|---|
| `chamnan-map` | costruisce e aggiorna l'indice |
| `chamnan-report` | che cosa contiene lo spazio di lavoro e come è cambiato il contesto per turno |
| `chamnan-impact` | chi dipende da questo file e quali test lo coprono |
| `chamnan-timeline` | che cosa è già successo a questo file |
| `chamnan-peek` | dice che cosa c'è dentro un file grande senza leggerlo nel contesto |
| `chamnan-promote` | conserva uno script come strumento permanente del repository |
| `chamnan-candidates` | vedere, confermare o respingere le ripetizioni rilevate |
| `chamnan-env` | dichiarare un ambiente e i suoi divieti, e verificare che la dichiarazione sia ancora fresca |
| `chamnan-age` | dove la conoscenza conservata ha cominciato a invecchiare |

E le competenze richiamate dall'interno della sessione: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Che cosa scrive, e dove

Tutto dentro `.chamnan/`, semplice markdown e JSON. Si legge, si modifica a mano e si cancella in qualsiasi momento senza rompere nulla.

| | |
|---|---|
| `MAP.md` | che cosa esiste e che cosa dipende da che cosa |
| `STATE.md` | su che cosa si lavora proprio adesso |
| `sessions/` | dove si è fermato il lavoro precedente |
| `memory/` | decisioni, lezioni e regole permanenti |
| `threads/` | linee di lavoro ancora aperte |
| `skills/` · `tools/` | procedure e script che vale la pena tenere |
| `milestones.md` | i cambiamenti che hanno rimodellato il repository |
| `config.json` | l'accensione di ogni parte e il tetto in byte del blocco iniettato nella sessione |

**L'unica scrittura fuori da `.chamnan/`** è un hook Git pre-commit facoltativo che tiene l'indice al passo con l'albero — installato solo se acconsentite, e rimovibile.

**L'agente non impara.** Nulla viene addestrato, nulla resta fuori da questa cartella, e la sessione successiva riparte comunque da zero — solo che riparte da zero *in un repository che sa spiegarsi da sé*. La continuità sta negli artefatti, non nel modello.

## Sicurezza

| | |
|---|---|
| **Nessuna chiamata di rete a runtime** | Nemmeno una. Non serve alcuna chiave API e nulla viene inviato da nessuna parte. |
| **Non riscrive il vostro codice** | Riferisce, non modifica. L'indice copia i commenti che avete già scritto, non se li inventa; i file senza commento vengono elencati per nome perché li completiate voi. |
| **Nessun demone, nessun lavoro in background** | Nessun processo residente, nessun database, nessun modello di embedding — solo la libreria standard di Python. |
| **I segreti vengono filtrati per primi** | Tutto ciò che sta per essere scritto o iniettato nella sessione passa prima dal filtro dei segreti: restano i *nomi* delle variabili, non i valori. E il limite che quel filtro non raggiunge è scritto accanto al suo stesso numero nel README inglese. |
| **Che cosa può farvi un plugin installato** | Spiegato per intero nel README inglese, compreso il punto in cui chamnan spezza la catena di esfiltrazione. |

## Con che cosa funziona

chamnan è testo e Python di libreria standard. Niente nell'indice appartiene a un fornitore, a un editor o a un sistema operativo particolare.

| | |
|---|---|
| **Qualsiasi modello, qualsiasi fornitore** | L'indice è testo semplice e viene passato come contesto. Il modello cambia solo quanto valga la pena inviarne, mai dove va ciascuna cosa. La dimensione si regola con `--model`, `--window` o `--profile`. Cambiare modello non richiede di reinstallare nulla. `--model` riconosce queste famiglie per nome: `claude` · `codestral` · `deepseek` · `fable` · `gemini` · `gemma` · `glm` · `gpt` · `grok` · `haiku` · `kimi` · `mistral` · `openai` · `opus` · `sonnet` — il confronto ignora maiuscole, separatori e numeri di versione. `llama` e `qwen` sono esclusi di proposito: entrambi escono in più dimensioni che vogliono budget diversi, quindi nominarli restituisce il profilo predefinito e una riga che dice a quali due dimensioni potrebbe riferirsi. **Un modello che non è nell'elenco funziona lo stesso**: riceve il profilo predefinito e una nota che non è stato riconosciuto, e nulla fallisce. `--window` prende il numero direttamente ed è sempre esatto. |
| **macOS, Linux, Windows, WSL** | Lo stesso plugin ovunque, solo libreria standard, niente da installare. Su macOS e Linux i comandi si eseguono direttamente. Su Windows la shell non sa avviare uno script senza estensione, quindi accanto a ogni comando e a ogni hook c'è un `.cmd` generato; vengono distribuiti con il plugin e la CI li esegue davvero. WSL si comporta come Linux. |
| **Molti agenti, un solo indice** | Claude Code lo riceve tramite un hook di sessione e nel tuo progetto non viene scritto alcun file. Anche Gemini CLI ha un vero hook di sessione. Gli altri agenti ricevono un file nel percorso che quell'agente legge, e quelli che leggono lo stesso percorso condividono il file invece di tenerne ciascuno una copia che si allontana dalle altre. |
| **Hermes Agent** | Hermes è anche un piano di controllo che guida altri agenti di codice, perciò un repository configurato per lui spesso significa più strumenti che leggono lo stesso indice. Cerca le istruzioni di progetto in un ordine fisso e prende la prima che trova; chamnan scrive il file in testa a quell'ordine, lo dimensiona sul limite che Hermes documenta e rifiuta di sovrascrivere un file che non ha scritto lui. |

## Come installarlo

Quale strada si prende dipende solo dal fatto che quello strumento abbia o no un hook di sessione.

| | |
|---|---|
| **Claude Code** | Installalo come plugin ed esegui una volta il comando di avvio dentro un repository. Nel tuo codice non viene scritto nulla, e da lì in poi ogni sessione parte con l'indice già nel contesto. |
| **Tutto il resto, Hermes compreso** | Chiedi prima che cosa rileva chamnan, poi digli per quale agente scrivere. Quando cambia la forma del repository, ricostruisci l'indice e riscrivi il file; un hook Git facoltativo fa entrambe le cose al commit. Claude Code non serve: sono comandi ordinari e il plugin è solo una via di consegna, non il prodotto. Senza un agente indicato, stampa che cosa ha rilevato e il comando che servirebbe, e lascia a te la decisione. Non scrive mai per supposizione. |

I nomi dei comandi, l'elenco completo degli agenti e il file che ciascuno riceve stanno nel README in inglese, dove vive ogni dettaglio legato a una versione.


## Requisiti

Claude Code · Python · Git · macOS, Linux o Windows

Nient'altro, e nessuna dipendenza da installare. La versione minima di Python è in [README › Requirements](../../README.md#requirements) — questa pagina non porta numeri, perché sono i numeri a cambiare.

## Spegnere o rimuovere

Spegnete a pezzi in `.chamnan/config.json` · fermatelo in un solo repository · rimuovete il plugin dall'intera macchina · cancellate `.chamnan/` quando volete senza rompere nulla — i passaggi dettagliati in [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

## Da leggere prima di installare

**chamnan è pensato per quell'unica cartella principale a cui torni di continuo.** Tutto quello che fa si paga in anticipo e si incassa nelle sessioni successive: su un repository aperto una volta sola hai pagato tutto e non hai incassato nulla.

**Riferisce, non riscrive il tuo codice.** L'indice riporta i commenti che hai già scritto e non ne inventa. I file senza commento vengono elencati per nome perché li completi tu.

**I suoi limiti sono misurati e scritti**, comprese le misure che giocano contro la sua stessa funzione principale.

## Dove stanno i dettagli

| | |
|---|---|
| Ogni numero, e come è stato misurato | [README › Evidence](../../README.md#evidence) |
| Suite di test di regressione — puoi eseguirla tu | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Che cosa è cambiato a ogni rilascio, e perché | [CHANGELOG.md](../../CHANGELOG.md) |
| Tutto il resto | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
