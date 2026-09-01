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
