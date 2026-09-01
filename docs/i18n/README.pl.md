# chamnan — żeby repozytorium znało samo siebie

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Ta strona celowo nie zawiera żadnych liczb. Wszystkie pomiary są w angielskim README i zmieniają się z każdym wydaniem; ta strona nie. → [Evidence](../../README.md#evidence)

## Co to jest

Wtyczka do Claude Code. Buduje indeks repozytorium, który agent czyta zamiast przeglądać pliki po kolei, i zachowuje kontekst inżynierski narastający w trakcie pracy — stan pracy, zapisy sesji, powody decyzji oraz procedury, które za każdym razem wyprowadzasz od nowa.

Wszystko, co zapisuje, to zwykły markdown commitowany obok kodu. Bez wywołań sieciowych w czasie działania, bez bazy danych, bez demona, bez modelu embedding — wyłącznie biblioteka standardowa Pythona.

## Co rozwiązuje

Przy każdej nowej sesji, i za każdym razem gdy kontekst zostaje skompresowany, wszystko co agent zrozumiał o twoim kodzie znika, a on wraca do szukania od zera.

chamnan sprawia, że to ponowne odkrywanie nie musi się zdarzyć: indeks jest podany na starcie sesji, a kosztem jest znana, ograniczona liczba, a nie nieograniczone czytanie plików.

## Instalacja

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Otwórz nową sesję, potem uruchom `/chamnan:bootstrap` raz na repozytorium.

<!-- generated: build_sections.py -->

## Wszystkie funkcje

Cztery zdolności. Wszystko wymienione poniżej naprawdę działa w bieżącym wydaniu. Każdą część można wyłączyć osobno w `.chamnan/config.json` i żadna nie zależy od pozostałych.

### Rozumieć — co istnieje i co jest z czym połączone

| | |
|---|---|
| **Indeks** | `MAP.md` — jedna linia na plik, generowana z samego kodu. Agent czyta indeks i grepuje potrzebny szczegół, zamiast przechodzić całe drzewo. |
| **Wpływ** | Kto zależy od tego pliku i które testy go pokrywają. Własne importy pliku są i tak na jego górze; kosztowna jest krawędź odwrotna — zgrepuj ścieżkę przed zmianą. |
| **Model danych** | Nazwy tabel i modeli z jednolinijkowym opisem, wyciągnięte z DDL, migracji i modeli ORM — a nie zrzut całego schematu. Pojawia się tylko wtedy, gdy repozytorium faktycznie go definiuje. |
| **Powierzchnia API** | Metoda, ścieżka i handler — z dekoratorów tras, dokumentów OpenAPI i definicji usług `.proto`, a nie cała specyfikacja. |
| **Konfiguracja** | Nazwy zmiennych środowiskowych, które czyta repozytorium. **Tylko nazwy, wartości nigdy nie są zapisywane** — i ostrzega, jeśli `.env` nie jest w gitignore. |
| **Wdrożenie** | Co faktycznie działa: rodzaje i nazwy, obrazy, role, potoki — odczytane z manifestów Kubernetes, Ansible, Compose, Helm i CI. Z Secreta bierze się tylko nazwę i nic z zawartości. |
| **Materiał nieźródłowy** | Skany, eksporty, archiwa — jedynie liczby, rozmiary i dominujące rozszerzenia. Istnieje po to, by agent nie poszedł zajrzeć sam, co kosztuje znacznie więcej. **Nigdy nie otwierane, nigdy nie czytane.** |

### Pamiętać — co było robione i dlaczego

| | |
|---|---|
| **Stan pracy** | `STATE.md` — to, nad czym praca trwa właśnie teraz; wstrzykiwane na starcie sesji, żeby kompaktowanie kontekstu przestało to kasować. |
| **Zapis sesji** | Jeden zapis na sesję w `.chamnan/sessions/`. Do następnej sesji trafia **tylko to, co niedokończone**; sesja zamknięta czysto nie wstrzykuje niczego. |
| **Pamięć** | `decisions/`, `lessons/`, `rules/`. Reguły to stałe ograniczenia, więc stoją przed agentem w każdej sesji; decyzje i lekcje dają sam tytuł i są czytane, gdy tytuł wygląda na trafny. |
| **Otwarte wątki** | Linie pracy, które jeszcze się nie domknęły, wraz z historią plików, których ta linia dotknęła — i podążają za nimi także po zmianie nazwy pliku. |

### Użyć ponownie — tego, co już rozwiązano

| | |
|---|---|
| **Procedury** | Umiejętności, które agent pisze **sam**, gdy natrafi na coś złożonego albo powtarzalnego. To nie dołączona gotowa biblioteka, lecz mechanizm. |
| **Narzędzia** | Zauważa, że ten sam doraźny skrypt został napisany ponownie, i proponuje go zachować — a potem przypomina o nim, zanim napiszesz nowy. |
| **Przepływy pracy** | Zauważa, że te same komendy szły w tej samej kolejności w osobne dni, i proponuje zapisać tę sekwencję. |

### Narastać — czego repozytorium dowiedziało się o sobie

| | |
|---|---|
| **Kamienie milowe** | Te nieliczne zmiany, które przemodelowały repozytorium: co się przeniosło, dlaczego było warto, jakich obszarów dotknęło. |
| **Kandydaci** | Wykryte powtarzalne sekwencje komend **zawsze czekają na potwierdzenie przez człowieka**. Nic nie awansuje automatycznie. |
| **Środowiska** | Zadeklaruj, czym jest production albo staging i co jest tam zabronione — a on ostrzeże, gdy ta deklaracja się zestarzeje. |
| **Raport** | Co trzyma przestrzeń robocza, czy naprawdę jest osiągalne i jak zmienił się kontekst na turę w twoim repozytorium. To twoja liczba, nie nasza. |

Powtarzalna praca inżynierska staje się wielokrotnie użyteczną wiedzą repozytorium — **to nie trenowanie modelu ani automatyzacja programisty.** To mechanizm zachowania pracy, która inaczej istniałaby tylko w głowie tego, kto ją wykonał.

## Polecenia

Wszystkie wywoływane z powłoki, a agent wywołuje je również sam.

| | |
|---|---|
| `chamnan-map` | buduje i odświeża indeks |
| `chamnan-report` | co trzyma przestrzeń robocza i jak zmienił się kontekst na turę |
| `chamnan-impact` | kto zależy od tego pliku i które testy go pokrywają |
| `chamnan-timeline` | co już przydarzyło się temu plikowi |
| `chamnan-peek` | mówi, co jest w dużym pliku, nie wczytując go do kontekstu |
| `chamnan-promote` | zachowuje skrypt jako stałe narzędzie repozytorium |
| `chamnan-candidates` | obejrzeć, potwierdzić albo odrzucić wykryte powtórzenia |
| `chamnan-env` | zadeklarować środowisko i jego zakazy oraz sprawdzić, czy deklaracja jest wciąż świeża |
| `chamnan-age` | gdzie zgromadzona wiedza zaczęła się starzeć |

Oraz umiejętności wywoływane z wnętrza sesji: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Co zapisuje i gdzie

Wszystko w `.chamnan/`, zwykły markdown i JSON. Da się to czytać, poprawiać ręcznie i usunąć w każdej chwili, nic się nie zepsuje.

| | |
|---|---|
| `MAP.md` | co istnieje i co od czego zależy |
| `STATE.md` | co jest robione właśnie teraz |
| `sessions/` | gdzie zatrzymała się poprzednia praca |
| `memory/` | decyzje, lekcje i stałe reguły |
| `threads/` | linie pracy wciąż otwarte |
| `skills/` · `tools/` | procedury i skrypty warte zachowania |
| `milestones.md` | zmiany, które przemodelowały repozytorium |
| `config.json` | włączanie i wyłączanie każdej części oraz limit rozmiaru bloku wstrzykiwanego do sesji |

**Jedyny zapis poza `.chamnan/`** to opcjonalny hak Git pre-commit, który utrzymuje indeks w zgodzie z drzewem — instalowany tylko wtedy, gdy się zgodzisz, i usuwalny.

**Agent się nie uczy.** Nic nie jest trenowane, nic nie zostaje poza tym katalogiem, a następna sesja wciąż zaczyna od zera — tyle że zaczyna od zera *w repozytorium, które samo się tłumaczy*. Ciągłość jest w artefaktach, nie w modelu.

## Bezpieczeństwo

| | |
|---|---|
| **Żadnych wywołań sieciowych w czasie działania** | Ani jednego. Klucz API nie jest potrzebny, nic nigdzie nie jest wysyłane. |
| **Nie przepisuje twojego kodu** | Raportuje, nie edytuje. Indeks kopiuje komentarze, które już napisałeś, i ich nie zmyśla; pliki bez komentarza są wymienione z nazwy, żebyś uzupełnił je sam. |
| **Bez demona, bez pracy w tle** | Żadnego stale działającego procesu, żadnej bazy danych, żadnego modelu osadzeń — tylko biblioteka standardowa Pythona. |
| **Sekrety są filtrowane najpierw** | Wszystko, co ma zostać zapisane albo wstrzyknięte do sesji, przechodzi najpierw przez filtr sekretów: *nazwy* zmiennych zostają, wartości nie. A granica, do której ten filtr nie sięga, jest opisana obok jego własnej liczby w angielskim README. |
| **Co zainstalowana wtyczka może ci zrobić** | Opisane w całości w angielskim README, łącznie z tym, gdzie chamnan przerywa łańcuch wycieku. |

## Wymagania

Claude Code · Python · Git · macOS, Linux albo Windows

Nic poza tym i żadnych zależności do zainstalowania. Minimalna wersja Pythona jest w [README › Requirements](../../README.md#requirements) — ta strona nie zawiera liczb, bo to właśnie liczby się zmieniają.

## Wyłączyć albo usunąć

Wyłączaj po kawałku w `.chamnan/config.json` · zatrzymaj w jednym repozytorium · usuń wtyczkę z całej maszyny · skasuj `.chamnan/` kiedy chcesz, nic się nie zepsuje — szczegółowe kroki w [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

## Przeczytaj przed instalacją

**chamnan jest dla jednego głównego katalogu, do którego wracasz raz za razem.** Wszystko, co robi, płaci się z góry i odbiera w kolejnych sesjach — w repozytorium otwartym raz zapłaciłeś całość i nie odebrałeś nic.

**Raportuje, nie przepisuje twojego kodu.** Indeks kopiuje komentarze, które już napisałeś, i nic nie zmyśla. Pliki bez komentarza są wymienione z nazwy, żebyś dopisał je sam.

**Jego ograniczenia zostały zmierzone i spisane**, łącznie z pomiarami przemawiającymi przeciwko jego własnej głównej funkcji.

## Gdzie są szczegóły

| | |
|---|---|
| Każda liczba i sposób jej pomiaru | [README › Evidence](../../README.md#evidence) |
| Zestaw testów regresyjnych — możesz uruchomić sam | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Co zmieniło się w każdym wydaniu i dlaczego | [CHANGELOG.md](../../CHANGELOG.md) |
| Całość | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
