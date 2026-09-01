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
