# chamnan — aby repozitář znal sám sebe

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Tato stránka záměrně neobsahuje žádná čísla. Všechna měření jsou v anglickém README a mění se s každým vydáním; tato stránka ne. → [Evidence](../../README.md#evidence)

## Co to je

Zásuvný modul pro Claude Code. Vytvoří index repozitáře, který agent čte místo procházení souborů jeden po druhém, a uchová inženýrský kontext, jenž se během práce nasbírá — stav práce, záznamy sezení, důvody rozhodnutí a postupy, které pokaždé odvozujete znovu.

Vše, co zapíše, je obyčejný markdown commitnutý vedle kódu. Za běhu žádné síťové volání, žádná databáze, žádný démon, žádný embedding model — pouze standardní knihovna Pythonu.

## Co řeší

S každým novým sezením, a pokaždé když se kontext zhutní, zmizí vše, co agent o vašem kódu pochopil, a začne hledat od začátku.

chamnan tomuto opětovnému objevování zabrání: index dostane hned na začátku sezení a cenou je známé, ohraničené číslo, ne neomezené čtení souborů.

## Instalace

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Otevřete nové sezení a spusťte `/chamnan:bootstrap` jednou pro každý repozitář.

<!-- generated: build_sections.py -->

## Všechny funkce

Čtyři schopnosti. Vše uvedené níže v aktuálním vydání skutečně běží. Každou část lze vypnout zvlášť v `.chamnan/config.json` a žádná nezávisí na ostatních.

### Rozumět — co existuje a co s čím souvisí

| | |
|---|---|
| **Rejstřík** | `MAP.md` — jeden řádek na soubor, vzniká ze samotného kódu. Agent čte rejstřík a grepne si potřebný detail, místo aby procházel celý strom. |
| **Dopad** | Kdo na tomto souboru závisí a které testy jej pokrývají. Vlastní importy souboru jsou stejně nahoře v něm; drahá je opačná hrana — před změnou si cestu grepněte. |
| **Datový model** | Názvy tabulek a modelů s jednořádkovým popisem, vytažené z DDL, migrací a ORM modelů — ne výpis celého schématu. Objeví se jen tehdy, když repozitář nějaké skutečně definuje. |
| **Povrch API** | Metoda, cesta a handler — z dekorátorů tras, dokumentů OpenAPI a definic služeb `.proto`, ne celá specifikace. |
| **Konfigurace** | Názvy proměnných prostředí, které repozitář čte. **Jen názvy, hodnoty se nikdy nezaznamenávají** — a upozorní, pokud `.env` není v gitignore. |
| **Nasazení** | Co skutečně běží: druhy a názvy, obrazy, role, pipeline — načteno z manifestů Kubernetes, Ansible, Compose, Helm a CI. Ze Secretu se bere jen jeho název a nic z obsahu. |
| **Nezdrojový materiál** | Naskenované papíry, exporty, archivy — jen počty, velikosti a převažující přípony. Existuje proto, aby se tam agent nešel podívat sám, což vyjde mnohem dráž. **Nikdy se neotevírá, nikdy nečte.** |

### Pamatovat — co se dělalo a proč

| | |
|---|---|
| **Stav práce** | `STATE.md` — na čem se pracuje právě teď; vkládá se na začátku sezení, aby to komprese kontextu přestala mazat. |
| **Záznam sezení** | Jeden záznam na sezení v `.chamnan/sessions/`. Do dalšího sezení se dostane **jen to nedokončené**; sezení uzavřené načisto nevkládá nic. |
| **Paměť** | `decisions/`, `lessons/`, `rules/`. Pravidla jsou trvalá omezení, takže stojí před agentem každé sezení; rozhodnutí a poučení přispívají jen názvem a čtou se, když název vypadá relevantně. |
| **Otevřená vlákna** | Linie práce, které ještě nejsou uzavřené, spolu s historií souborů, jichž se ta linie dotkla — a sledují je i po přejmenování souboru. |

### Použít znovu — co už bylo vyřešeno

| | |
|---|---|
| **Postupy** | Dovednosti, které si agent **píše sám**, když narazí na něco složitého nebo opakovaného. Ne přibalená hotová knihovna, ale mechanismus. |
| **Nástroje** | Všimne si, že tentýž provizorní skript byl napsán znovu, a nabídne jej uchovat — a připomene jej dřív, než napíšete nový. |
| **Pracovní postupy** | Všimne si, že tytéž příkazy běžely ve stejném pořadí v oddělené dny, a nabídne tu posloupnost zapsat. |

### Hromadit — co se repozitář dozvěděl sám o sobě

| | |
|---|---|
| **Milníky** | Těch pár změn, které přetvarovaly repozitář: co se přesunulo, proč to stálo za to a jakých oblastí se to dotklo. |
| **Kandidáti** | Zachycené opakující se posloupnosti příkazů **vždy čekají na potvrzení člověkem**. Nic se nepovyšuje automaticky. |
| **Prostředí** | Deklarujte, co je production nebo staging a co je tam zakázáno — a upozorní, až ta deklarace zestárne. |
| **Zpráva** | Co pracovní prostor drží, zda je to skutečně dosažitelné a jak se změnil kontext na tah ve vašem repozitáři. Vaše číslo, ne naše. |

Opakovaná inženýrská práce se stává znovupoužitelnou znalostí repozitáře — **není to trénink modelu ani automatizace vývojáře.** Je to mechanismus, jak uchovat práci, která by jinak existovala jen v hlavě toho, kdo ji odvedl.

## Příkazy

Všechny lze volat ze shellu a agent je volá i sám.

| | |
|---|---|
| `chamnan-map` | sestaví a aktualizuje rejstřík |
| `chamnan-report` | co drží pracovní prostor a jak se změnil kontext na tah |
| `chamnan-impact` | kdo na tomto souboru závisí a které testy jej pokrývají |
| `chamnan-timeline` | co se s tímto souborem dosud dělo |
| `chamnan-peek` | řekne, co je uvnitř velkého souboru, aniž by ho načetl do kontextu |
| `chamnan-promote` | uchová skript jako stálý nástroj repozitáře |
| `chamnan-candidates` | prohlédnout, potvrdit nebo zamítnout zachycená opakování |
| `chamnan-env` | deklarovat prostředí a jeho zákazy a ověřit, že deklarace je stále čerstvá |
| `chamnan-age` | kde nashromážděná znalost začala stárnout |

A dovednosti volané zevnitř sezení: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Co zapisuje a kam

Vše uvnitř `.chamnan/`, obyčejný markdown a JSON. Dá se to číst, ručně upravit a kdykoli smazat, aniž by se něco rozbilo.

| | |
|---|---|
| `MAP.md` | co existuje a co na čem závisí |
| `STATE.md` | co se dělá právě teď |
| `sessions/` | kde se předchozí práce zastavila |
| `memory/` | rozhodnutí, poučení a trvalá pravidla |
| `threads/` | linie práce, které jsou ještě otevřené |
| `skills/` · `tools/` | postupy a skripty, které stojí za uchování |
| `milestones.md` | změny, které přetvarovaly repozitář |
| `config.json` | zapínání a vypínání každé části a strop velikosti bloku vkládaného do sezení |

**Jediný zápis mimo `.chamnan/`** je volitelný Git hook pre-commit, který drží rejstřík v souladu se stromem — nainstaluje se, jen když souhlasíte, a jde odstranit.

**Agent se neučí.** Nic se netrénuje, nic nezůstává mimo tento adresář a další sezení stále začíná od nuly — jen začíná od nuly *v repozitáři, který se sám vysvětlí*. Spojitost je v artefaktech, ne v modelu.

## Bezpečnost

| | |
|---|---|
| **Za běhu žádné síťové volání** | Ani jedno. Klíč k API není potřeba, nikam se nic neposílá. |
| **Nepřepisuje váš zdroj** | Hlásí, neupravuje. Rejstřík kopíruje komentáře, které jste už napsali, a nevymýšlí si je; soubory bez komentáře jsou vyjmenovány, abyste je doplnili sami. |
| **Žádný démon, žádná práce na pozadí** | Žádný trvale běžící proces, žádná databáze, žádný embedding model — jen standardní knihovna Pythonu. |
| **Tajemství se filtrují jako první** | Vše, co se má zapsat nebo vložit do sezení, projde nejdřív filtrem tajemství: *názvy* proměnných zůstávají, hodnoty ne. A hranice, kam tenhle filtr nedosáhne, je popsána vedle jeho vlastního čísla v anglickém README. |
| **Co s vámi může udělat nainstalovaný plugin** | Celé je to vysvětleno v anglickém README, včetně toho, kde chamnan přetrhne řetěz úniku. |

## S čím to funguje

chamnan je text a Python ze standardní knihovny. Nic v indexu nepatří jednomu dodavateli, jednomu editoru ani jednomu operačnímu systému.

| | |
|---|---|
| **Jakýkoli model, jakýkoli dodavatel** | Index je prostý text a předává se jako kontext. Model mění jen to, kolik se vyplatí poslat, nikdy to, kam co patří. Velikost nastavíte pomocí `--model`, `--window` nebo `--profile`. Změna modelu nevyžaduje nic přeinstalovat. `--model` rozpozná tyto rodiny podle jména: `claude` · `codestral` · `deepseek` · `fable` · `gemini` · `gemma` · `glm` · `gpt` · `grok` · `haiku` · `kimi` · `mistral` · `openai` · `opus` · `sonnet` — porovnání nehledí na velikost písmen, oddělovače ani čísla verzí. `llama` a `qwen` jsou záměrně vynechány: obě vycházejí v několika velikostech, které chtějí různé rozpočty, takže jejich jméno vrátí výchozí profil a řádek o tom, které dvě velikosti to mohly být. **Model, který na seznamu není, přesto funguje**: dostane výchozí profil a poznámku, že nebyl rozpoznán, a nic neselže. `--window` bere číslo přímo a je vždy přesný. |
| **macOS, Linux, Windows, WSL** | Všude tentýž plugin, jen standardní knihovna, není co instalovat. Na macOS a Linuxu se příkazy spouštějí přímo. Na Windows shell neumí spustit skript bez přípony, a tak vedle každého příkazu i háčku leží vygenerovaný `.cmd`; dodávají se s pluginem a CI spouští právě je. WSL se chová jako Linux. |
| **Mnoho agentů, jeden index** | Claude Code jej dostává přes háček relace a do vašeho projektu se nezapisuje žádný soubor. Gemini CLI má rovněž skutečný háček relace. Ostatní agenti dostanou soubor v cestě, kterou čtou, a ti, kdo čtou tutéž cestu, sdílejí jeden soubor, místo aby si každý držel kopii, která se rozchází. |
| **Hermes Agent** | Hermes je zároveň řídicí vrstva, která diriguje jiné kódovací agenty, takže repozitář připravený pro něj obvykle znamená několik nástrojů čtoucích tentýž index. Pokyny projektu hledá v pevném pořadí a bere první nalezený; chamnan zapisuje soubor stojící v čele toho pořadí, velikost přizpůsobuje limitu, který Hermes sám dokumentuje, a odmítá přepsat soubor, který nenapsal. |

## Jak to nasadit

Kterou cestou půjdete, závisí jen na tom, zda má nástroj háček relace.

| | |
|---|---|
| **Claude Code** | Nainstalujte jako plugin a jednou spusťte úvodní příkaz uvnitř repozitáře. Do vašeho kódu se nic nezapisuje a od té chvíle každá relace začíná s indexem už v kontextu. |
| **Všechno ostatní, včetně Hermes** | Nejdřív se zeptejte, co chamnan rozpoznal, a pak řekněte, pro kterého agenta má psát. Když se tvar repozitáře změní, sestavte index znovu a soubor zapište znovu; volitelný Git háček udělá při commitu obojí. Claude Code není potřeba: jsou to běžné příkazy a plugin je jen jedna cesta doručení, ne produkt. Bez uvedeného agenta vypíše, co rozpoznal, a příkaz, který by se hodil, a rozhodnutí nechá na vás. Nikdy nepíše podle dohadu. |

Názvy příkazů, úplný seznam agentů a soubor, který každý dostane, jsou v anglickém README, kde žije každý detail vázaný na verzi.


## Požadavky

Claude Code · Python · Git · macOS, Linux nebo Windows

Nic dalšího a žádné závislosti k instalaci. Minimální verze Pythonu je v [README › Requirements](../../README.md#requirements) — tahle stránka čísla nenese, protože právě čísla se mění.

## Vypnout nebo odstranit

Vypínejte po částech v `.chamnan/config.json` · zastavte v jednom repozitáři · odstraňte plugin z celého stroje · smažte `.chamnan/` kdykoli, nic se nerozbije — podrobné kroky v [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

## Přečtěte si před instalací

**chamnan je pro jednu hlavní složku, ke které se opakovaně vracíte.** Vše, co dělá, se platí předem a vybírá v dalších sezeních — u repozitáře, který otevřete jednou, jste zaplatili celé a nevybrali nic.

**Hlásí, nepřepisuje váš kód.** Index kopíruje komentáře, které jste už napsali, a nic si nevymýšlí. Soubory bez komentáře jmenuje, abyste je doplnili sami.

**Jeho meze jsou změřené a sepsané**, včetně měření, která mluví proti jeho vlastní hlavní funkci.

## Kde jsou podrobnosti

| | |
|---|---|
| Každé číslo a jak bylo změřeno | [README › Evidence](../../README.md#evidence) |
| Sada regresních testů — můžete spustit sami | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Co se v každém vydání změnilo a proč | [CHANGELOG.md](../../CHANGELOG.md) |
| Vše ostatní | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
