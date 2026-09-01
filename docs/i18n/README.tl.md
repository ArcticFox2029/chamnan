# chamnan — para makilala ng repository ang sarili nito

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md)</sub>

> Sadyang walang numero sa pahinang ito. Nasa Ingles na README ang lahat ng sukat at nagbabago ito kada release; ang pahinang ito ay hindi. → [Evidence](../../README.md#evidence)

## Ano ito

Isang plugin para sa Claude Code. Gumagawa ito ng index ng repository na babasahin ng agent sa halip na isa-isahing suriin ang mga file, at iniingatan ang teknikal na konteksto na naiipon habang nagtatrabaho ka — estado ng gawain, tala ng sesyon, dahilan sa likod ng mga desisyon, at mga hakbang na paulit-ulit mong inaalala.

Lahat ng isinusulat nito ay payak na markdown na naka-commit katabi ng code. Walang tawag sa network habang tumatakbo, walang database, walang daemon, walang embedding model — standard library lamang ng Python.

## Ano ang nilulutas nito

Sa bawat bagong sesyon, o sa tuwing pinipiga ang konteksto, nawawala ang lahat ng naunawaan ng agent tungkol sa iyong codebase, at babalik ito sa panimulang paghahanap.

Pinipigilan ito ng chamnan: iniaabot na ang index sa simula ng sesyon, at ang gastos ay isang alam at may hangganang bilang, hindi walang hanggang pagbabasa ng file.

## Pag-install

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Magbukas ng bagong sesyon, tapos patakbuhin ang `/chamnan:bootstrap` nang isang beses kada repository.

<!-- generated: build_sections.py -->

## Lahat ng tampok

Apat na kakayahan. Lahat ng nakalista sa ibaba ay talagang tumatakbo sa kasalukuyang bersyon. Bawat bahagi ay maaaring patayin nang hiwalay sa `.chamnan/config.json`, at walang isa mang umaasa sa iba.

### Umunawa — ano ang naroon, at ano ang nakakabit sa ano

| | |
|---|---|
| **Indeks** | `MAP.md` — isang linya bawat file, ginawa mula mismo sa code. Binabasa ng ahente ang indeks at ginigrep ang detalyeng kailangan, sa halip na lakarin ang buong puno ng direktoryo. |
| **Epekto** | Sino ang umaasa sa file na ito, at aling mga pagsubok ang sumasaklaw dito. Ang sarili nitong import ay nasa itaas na ng file; ang mahal hanapin ay ang kabilang direksyon — grepin ang landas bago baguhin. |
| **Modelo ng datos** | Mga pangalan ng talahanayan at modelo na may isang linyang paglalarawan, hango sa DDL, migrations at ORM models — hindi buong dump ng schema. Lumilitaw lamang kung talagang may tinutukoy ang repositoryo. |
| **Ibabaw ng API** | Method, landas at handler, mula sa route decorators, dokumentong OpenAPI at kahulugan ng serbisyo sa `.proto` — hindi ang buong ispesipikasyon. |
| **Konpigurasyon** | Ang mga pangalan ng environment variable na binabasa ng repositoryo. **Pangalan lamang, hindi kailanman ang halaga** — at nagbababala kung wala sa gitignore ang `.env`. |
| **Pagdedeploy** | Ang tunay na tumatakbo, binasa mula sa manifest ng Kubernetes, Ansible, Compose, Helm at CI: uri at pangalan, images, papel, pipelines. Sa isang Secret, ang pangalan lamang ang kinukuha, wala sa nilalaman nito. |
| **Materyal na hindi source code** | Mga naka-scan na papeles, export, archive — bilang, laki at pinakamadalas na extension lamang. Naririto ito upang huwag nang pumunta at tumingin mismo ang ahente, na mas mahal nang malayo. **Hindi kailanman binubuksan, hindi kailanman binabasa.** |

### Tumanda ang alaala — ano ang ginagawa, at bakit

| | |
|---|---|
| **Katayuan ng gawain** | `STATE.md` — kung ano ang ginagawa ngayon mismo; ipinapasok sa simula ng sesyon upang tumigil na sa pagbura nito ang pagsisiksik ng konteksto. |
| **Talaan ng sesyon** | Isa bawat sesyon sa ilalim ng `.chamnan/sessions/`. **Ang hindi natapos lamang** ang umaabot sa susunod na sesyon; ang sesyong malinis na natapos ay walang ipinapasok. |
| **Alaala** | `decisions/`, `lessons/`, `rules/`. Ang mga tuntunin ay panatilihing hangganan, kaya nasa harap ng ahente ang mga ito bawat sesyon; ang mga pasya at aral ay pamagat lamang ang inaambag, at binabasa kapag mukhang kaugnay ang pamagat. |
| **Bukas na sinulid** | Mga linya ng gawaing hindi pa naisasara, kasama ang kasaysayan kung aling mga file ang nahawakan ng sinulid na iyon — at sinusundan pa rin ito matapos palitan ang pangalan ng file. |

### Gamitin muli — ang nalutas na minsan

| | |
|---|---|
| **Pamamaraan** | Mga kasanayang **isinusulat mismo ng ahente** kapag nakatagpo ito ng masalimuot o paulit-ulit. Hindi isang nakahandang aklatan, kundi isang mekanismo. |
| **Kasangkapan** | Napapansing muling isinulat ang parehong pansamantalang script, at inaalok itong itago — at binabanggit ito bago ka sumulat ng bago. |
| **Daloy ng trabaho** | Napapansing tumakbo ang parehong mga utos sa parehong pagkakasunod sa magkahiwalay na araw, at inaalok na isulat ang pagkakasunod na iyon. |

### Maipon — ang natutunan ng repositoryo tungkol sa sarili

| | |
|---|---|
| **Palatandaan** | Ang iilang pagbabagong humubog muli sa repositoryo: ano ang lumipat, bakit sulit, at aling bahagi ang nagalaw. |
| **Kandidato** | Ang natukoy na paulit-ulit na pagkakasunod ng utos ay **laging hinihintay ang kumpirmasyon ng tao**. Walang awtomatikong itinataas. |
| **Kapaligiran** | Ipahayag kung ano ang production o staging at kung ano ang ipinagbabawal doon — at magbibigay-babala ito kapag tumanda na ang pahayag. |
| **Ulat** | Ano ang laman ng workspace, tunay ba itong naaabot, at paano nagbago ang konteksto bawat pasada sa repositoryo mo. Numero mo, hindi amin. |

Ang paulit-ulit na gawaing inhinyeriya ay nagiging kaalaman ng repositoryong magagamit muli — **hindi pagsasanay ng modelo, at hindi pag-aautomat sa developer.** Isa itong paraan upang mapanatili ang gawaing kung hindi ay nasa ulo lamang ng gumawa nito.

## Mga utos

Lahat ay matatawag mula sa shell, at tinatawag din ang mga ito ng ahente mismo.

| | |
|---|---|
| `chamnan-map` | gumagawa at nag-uupdate ng indeks |
| `chamnan-report` | ano ang laman ng workspace at paano nagbago ang konteksto bawat pasada |
| `chamnan-impact` | sino ang umaasa sa file na ito at aling mga pagsubok ang sumasaklaw dito |
| `chamnan-timeline` | ano na ang nangyari sa file na ito |
| `chamnan-peek` | sinasabi kung ano ang nasa loob ng malaking file nang hindi ito binabasa papasok sa konteksto |
| `chamnan-promote` | itinatago ang isang script bilang permanenteng kasangkapan ng repositoryo |
| `chamnan-candidates` | tingnan, kumpirmahin o tanggihan ang natukoy na pag-uulit |
| `chamnan-env` | ipahayag ang kapaligiran at ang mga ipinagbabawal doon, at tingnan kung sariwa pa ang pahayag |
| `chamnan-age` | saan nagsimulang tumanda ang naimbak na kaalaman |

At ang mga kasanayang tinatawag mula sa loob ng sesyon: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Ano ang isinusulat nito, at saan

Lahat ay nasa loob ng `.chamnan/`, karaniwang markdown at JSON. Nababasa, naeedit nang mano-mano, at nabubura anumang oras nang walang nasisira.

| | |
|---|---|
| `MAP.md` | ano ang naroon, at ano ang umaasa sa ano |
| `STATE.md` | ano ang ginagawa ngayon mismo |
| `sessions/` | saan tumigil ang nakaraang gawain |
| `memory/` | mga pasya, aral at panatilihing tuntunin |
| `threads/` | mga linya ng gawaing bukas pa |
| `skills/` · `tools/` | mga pamamaraan at script na sulit itago |
| `milestones.md` | ang mga pagbabagong humubog muli sa repositoryo |
| `config.json` | ang pagbukas at pagsara ng bawat bahagi, at ang hangganan sa laki ng bloke na ipinapasok sa sesyon |

**Ang tanging isinusulat sa labas ng `.chamnan/`** ay isang opsyonal na Git pre-commit hook na nagpapanatiling kasabay ng puno ang indeks — inilalagay lamang kung papayag ka, at natatanggal.

**Hindi natututo ang ahente.** Walang sinasanay, walang natitira sa labas ng direktoryong ito, at ang susunod na sesyon ay nagsisimula pa rin sa wala — nagsisimula lamang sa wala *sa loob ng repositoryong marunong magpaliwanag ng sarili*. Ang pagpapatuloy ay nasa mga file, hindi sa modelo.

## Kaligtasan

| | |
|---|---|
| **Walang tawag sa network habang tumatakbo** | Wala ni isa. Walang kailangang API key, at walang ipinapadala kahit saan. |
| **Hindi nito isinusulat muli ang code mo** | Nag-uulat ito, hindi nag-eedit. Kinokopya ng indeks ang mga komentong naisulat mo na, hindi ito kumakatha; ang mga file na walang komento ay pinapangalanan upang ikaw ang pumuno. |
| **Walang daemon, walang gawain sa likod** | Walang nananatiling proseso, walang database, walang embedding model — ang karaniwang aklatan lamang ng Python. |
| **Sinasala muna ang mga lihim** | Lahat ng isusulat o ipapasok sa sesyon ay dumadaan muna sa salaan ng lihim: nananatili ang *pangalan* ng variable, hindi ang halaga. At ang hangganang hindi naaabot ng salaang iyon ay nakasulat katabi ng sarili nitong numero sa README na Ingles. |
| **Ano ang kayang gawin sa iyo ng isang naka-install na plugin** | Buong ipinaliwanag sa README na Ingles, kasama kung saan pinuputol ng chamnan ang tanikala ng pagtagas. |

## Kailangan

Claude Code · Python · Git · macOS, Linux o Windows

Wala nang iba, at walang dependency na ii-install. Ang pinakamababang bersyon ng Python ay nasa [README › Requirements](../../README.md#requirements) — walang numero ang pahinang ito, dahil ang numero ang nagbabago.

## Patayin o alisin

Patayin nang paisa-isa sa `.chamnan/config.json` · ihinto sa iisang repositoryo · alisin ang plugin sa buong makina · burahin ang `.chamnan/` anumang oras nang walang nasisira — nasa [README › Update, disable, uninstall](../../README.md#update-disable-uninstall) ang detalyadong hakbang

<!-- /generated -->

## Basahin bago mag-install

**Angkop ang chamnan sa iisang pangunahing folder na paulit-ulit mong binabalikan.** Lahat ng ginagawa nito ay bayad muna at bawi sa mga susunod na sesyon — sa repository na minsan mo lang bubuksan, nagbayad ka nang buo at walang nabawi.

**Nag-uulat ito, hindi binabago ang code mo.** Kinokopya lang ng index ang mga komentong naisulat mo na, hindi ito kumakatha. Pinapangalanan ang mga file na walang komento para ikaw mismo ang magdagdag.

**Nasukat at naisulat na ang mga limitasyon nito**, pati ang mga sukat na sumasalungat sa sarili nitong pangunahing tampok.

## Nasaan ang detalye

| | |
|---|---|
| Bawat numero, at kung paano ito sinukat | [README › Evidence](../../README.md#evidence) |
| Regression test suite — patakbuhin mo mismo | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Ano ang binago kada release, at bakit | [CHANGELOG.md](../../CHANGELOG.md) |
| Lahat | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
