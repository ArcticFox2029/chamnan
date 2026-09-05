# chamnan — jotta repositorio tuntisi itsensä

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Tällä sivulla ei ole tarkoituksella yhtään lukua. Kaikki mittaukset ovat englanninkielisessä README-tiedostossa ja muuttuvat joka julkaisussa; tämä sivu ei. → [Evidence](../../README.md#evidence)

## Mikä tämä on

Claude Code -laajennus. Se rakentaa repositoriosta hakemiston, jonka agentti lukee sen sijaan että kävisi tiedostot yksi kerrallaan läpi, ja säilyttää työn aikana kertyvän teknisen taustan — työn tilan, istuntomuistiinpanot, päätösten perustelut ja ne menettelyt, jotka johdetaan joka kerta uudelleen.

Kaikki mitä se kirjoittaa on tavallista markdownia, versioituna koodin vierellä. Ei verkkokutsuja ajon aikana, ei tietokantaa, ei taustaprosessia, ei embedding-mallia — pelkkä Pythonin vakiokirjasto.

## Minkä se ratkaisee

Jokaisessa uudessa istunnossa, ja aina kun konteksti tiivistetään, kaikki minkä agentti oli ymmärtänyt koodistasi katoaa ja se aloittaa etsimisen alusta.

chamnan tekee tuosta uudelleenlöytämisestä tarpeetonta: hakemisto annetaan istunnon alussa, ja hinta on tunnettu, rajattu luku eikä rajaton määrä tiedostojen lukemista.

## Asennus

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Avaa uusi istunto ja aja `/chamnan:bootstrap` kerran kutakin repositoriota kohden.

<!-- generated: build_sections.py -->

## Kaikki ominaisuudet

Neljä kykyä. Kaikki alla luetellut ovat oikeasti käytössä nykyisessä julkaisussa. Jokainen osa voidaan kytkeä pois erikseen tiedostossa `.chamnan/config.json`, eikä yksikään riipu toisesta.

### Ymmärtää — mitä on olemassa ja mikä liittyy mihin

| | |
|---|---|
| **Hakemisto** | `MAP.md` — rivi tiedostoa kohti, tuotettu itse koodista. Agentti lukee hakemiston ja grepittää tarvitsemansa yksityiskohdan sen sijaan, että kävisi koko puun läpi. |
| **Vaikutus** | Kuka riippuu tästä tiedostosta ja mitkä testit kattavat sen. Tiedoston omat importit ovat joka tapauksessa sen yläosassa; kallista on käänteinen suunta — grepitä polku ennen muutosta. |
| **Tietomalli** | Taulujen ja mallien nimet yhden rivin kuvauksella, poimittuna DDL:stä, migraatioista ja ORM-malleista — ei koko skeeman vedosta. Näkyy vain, jos repositorio todella määrittelee sellaisen. |
| **API-pinta** | Metodi, polku ja käsittelijä reittikoristeista, OpenAPI-dokumenteista ja `.proto`-palvelumäärittelyistä — ei koko spesifikaatiota. |
| **Asetukset** | Niiden ympäristömuuttujien nimet, joita repositorio lukee. **Vain nimet, arvoja ei koskaan kirjata** — ja se varoittaa, jos `.env` ei ole gitignoressa. |
| **Käyttöönotto** | Mikä oikeasti pyörii, luettuna Kubernetesin, Ansiblen, Composen, Helmin ja CI:n manifesteista: tyypit ja nimet, imaget, roolit, putket. Secretistä otetaan vain nimi, ei mitään sen alta. |
| **Muu kuin lähdekoodi** | Skannatut paperit, viennit, arkistot — vain lukumäärät, koot ja yleisimmät päätteet. Osio on olemassa, jotta agentti ei menisi katsomaan itse, mikä maksaa paljon enemmän. **Ei koskaan avata, ei koskaan lueta.** |

### Muistaa — mitä oltiin tekemässä ja miksi

| | |
|---|---|
| **Työn tila** | `STATE.md` — se, mitä juuri nyt tehdään; syötetään istunnon alussa, jotta kontekstin tiivistäminen lakkaa pyyhkimästä sitä. |
| **Istuntomerkintä** | Yksi istuntoa kohti hakemistossa `.chamnan/sessions/`. Seuraavaan istuntoon pääsee **vain kesken jäänyt**; siististi päätetty istunto ei syötä mitään. |
| **Muisti** | `decisions/`, `lessons/`, `rules/`. Säännöt ovat pysyviä rajoituksia, joten ne ovat agentin edessä joka istunnossa; päätökset ja opit antavat vain otsikon ja luetaan, kun otsikko vaikuttaa asiaankuuluvalta. |
| **Avoimet langat** | Työlinjat, joita ei ole vielä suljettu, sekä historia siitä, mitä tiedostoja lanka on koskettanut — ja ne seuraavat tiedostoa myös uudelleennimeämisen jälkeen. |

### Käyttää uudelleen — se, mikä on jo kerran ratkaistu

| | |
|---|---|
| **Menettelyt** | Taitoja, jotka agentti kirjoittaa **itse** törmätessään johonkin monimutkaiseen tai toistuvaan. Ei mukana tuleva kirjasto vaan mekanismi. |
| **Työkalut** | Huomaa, että sama kertakäyttöskripti on kirjoitettu taas, ja tarjoutuu säilyttämään sen — ja mainitsee sen ennen kuin kirjoitat uuden. |
| **Työnkulut** | Huomaa, että samat komennot ajettiin samassa järjestyksessä eri päivinä, ja tarjoutuu kirjaamaan sen järjestyksen ylös. |

### Karttua — mitä repositorio on oppinut itsestään

| | |
|---|---|
| **Virstanpylväät** | Ne harvat muutokset, jotka muovasivat repositorion uusiksi: mikä siirtyi, miksi se kannatti, mihin alueisiin se kosketti. |
| **Ehdokkaat** | Havaitut toistuvat komentosarjat jäävät **aina odottamaan ihmisen vahvistusta**. Mitään ei ylennetä automaattisesti. |
| **Ympäristöt** | Ilmoita, mikä production tai staging on ja mikä siellä on kiellettyä — ja se huomauttaa, kun ilmoitus vanhenee. |
| **Raportti** | Mitä työtila pitää sisällään, onko se todella saavutettavissa, ja miten konteksti vuoroa kohti on muuttunut sinun repositoriossasi. Sinun lukusi, ei meidän. |

Toistuva insinöörityö muuttuu uudelleenkäytettäväksi repositoriotiedoksi — **ei mallin kouluttamista eikä kehittäjän automatisointia.** Se on tapa säilyttää työ, joka muuten olisi vain sen tekijän päässä.

## Komennot

Kaikki kutsuttavissa komentotulkista, ja agentti kutsuu niitä myös itse.

| | |
|---|---|
| `chamnan-map` | rakentaa ja päivittää hakemiston |
| `chamnan-report` | mitä työtila pitää sisällään ja miten konteksti vuoroa kohti on muuttunut |
| `chamnan-impact` | kuka riippuu tästä tiedostosta ja mitkä testit kattavat sen |
| `chamnan-timeline` | mitä tälle tiedostolle on tähän mennessä tapahtunut |
| `chamnan-peek` | kertoo, mitä isossa tiedostossa on, lukematta sitä kontekstiin |
| `chamnan-promote` | säilyttää skriptin repositorion pysyvänä työkaluna |
| `chamnan-candidates` | katsoa, vahvistaa tai hylätä havaitut toistot |
| `chamnan-env` | ilmoittaa ympäristö ja sen kiellot sekä tarkistaa, onko ilmoitus yhä tuore |
| `chamnan-age` | mistä talletettu tieto on alkanut vanhentua |

Ja istunnon sisältä kutsuttavat taidot: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Mitä se kirjoittaa ja minne

Kaikki hakemistossa `.chamnan/`, tavallista markdownia ja JSONia. Luettavissa, käsin muokattavissa ja poistettavissa milloin tahansa ilman että mikään hajoaa.

| | |
|---|---|
| `MAP.md` | mitä on olemassa ja mikä riippuu mistä |
| `STATE.md` | mitä juuri nyt tehdään |
| `sessions/` | mihin edellinen työrupeama pysähtyi |
| `memory/` | päätökset, opit ja pysyvät säännöt |
| `threads/` | työlinjat, jotka ovat yhä auki |
| `skills/` · `tools/` | säilyttämisen arvoiset menettelyt ja skriptit |
| `milestones.md` | muutokset, jotka muovasivat repositorion uusiksi |
| `config.json` | kunkin osan päälle ja pois, sekä istuntoon syötettävän lohkon tavukatto |

**Ainoa kirjoitus `.chamnan/`-hakemiston ulkopuolelle** on valinnainen Git-pre-commit-koukku, joka pitää hakemiston puun tahdissa — se asennetaan vain jos suostut, ja sen voi poistaa.

**Agentti ei opi.** Mitään ei kouluteta, mitään ei jää tämän hakemiston ulkopuolelle, ja seuraava istunto alkaa yhä nollasta — vain nollasta *repositoriossa, joka selittää itsensä*. Jatkuvuus on tuotoksissa, ei mallissa.

## Turvallisuus

| | |
|---|---|
| **Ei verkkokutsuja ajon aikana** | Ei ainuttakaan. API-avainta ei tarvita, eikä mitään lähetetä minnekään. |
| **Ei kirjoita koodiasi uusiksi** | Se raportoi, ei muokkaa. Hakemisto kopioi jo kirjoittamasi kommentit eikä keksi niitä; kommentittomat tiedostot mainitaan nimeltä, jotta täydennät ne itse. |
| **Ei taustaprosessia eikä taustatyötä** | Ei pysyvää prosessia, ei tietokantaa, ei upotusmallia — vain Pythonin vakiokirjasto. |
| **Salaisuudet suodatetaan ensin** | Kaikki kirjoitettava tai istuntoon syötettävä kulkee ensin salaisuussuodattimen läpi: muuttujien *nimet* jäävät, arvot eivät. Ja se raja, johon suodatin ei yllä, on kirjoitettu oman lukunsa viereen englanninkielisessä README-tiedostossa. |
| **Mitä asennettu laajennus voi tehdä sinulle** | Selitetty kokonaan englanninkielisessä README-tiedostossa, mukaan lukien se, missä kohtaa chamnan katkaisee vuotoketjun. |

## Minkä kanssa tämä toimii

chamnan on tekstiä ja vakiokirjaston Pythonia. Mikään hakemistossa ei kuulu yhdelle toimittajalle, yhdelle editorille eikä yhdelle käyttöjärjestelmälle.

| | |
|---|---|
| **Mikä tahansa malli, mikä tahansa toimittaja** | Hakemisto on tavallista tekstiä ja lähetetään kontekstina. Malli muuttaa vain sen, kuinka paljon kannattaa lähettää, ei koskaan sitä mihin mikäkin menee. Koko asetetaan valitsimilla `--model`, `--window` tai `--profile`. Mallin vaihtaminen ei vaadi mitään uudelleenasennusta. `--model` tunnistaa nämä perheet nimeltä: `claude` · `codestral` · `deepseek` · `gemini` · `gemma` · `glm` · `gpt` · `grok` · `kimi` · `mistral` · `openai` — vertailu ei välitä kirjainkoosta, erottimista eikä versionumeroista. `llama` ja `qwen` on jätetty tarkoituksella pois: kumpaakin on useaa kokoa, jotka haluavat eri budjetin, joten niiden nimeäminen palauttaa oletusprofiilin ja rivin siitä, kumpaa kahdesta koosta on voitu tarkoittaa. **Malli, jota ei ole luettelossa, toimii silti**: se saa oletusprofiilin ja huomautuksen ettei sitä tunnistettu, eikä mikään epäonnistu. `--window` ottaa luvun suoraan ja on aina tarkka. |
| **macOS, Linux, Windows, WSL** | Sama lisäosa kaikkialla, pelkkä vakiokirjasto, ei mitään asennettavaa. macOS:llä ja Linuxilla komennot ajetaan suoraan. Windowsissa komentotulkki ei osaa ajaa päätteetöntä skriptiä, joten jokaisen komennon ja koukun viereen tehdään `.cmd`-tiedosto; ne toimitetaan lisäosan mukana ja CI ajaa juuri niitä. WSL käyttäytyy kuin Linux. |
| **Monta agenttia, yksi hakemisto** | Claude Code saa lohkon istuntokoukun kautta eikä projektiisi kirjoiteta tiedostoa. Myös Gemini CLI:llä on aito istuntokoukku. Muut agentit saavat tiedoston siihen polkuun, jota kyseinen agentti lukee, ja samaa polkua lukevat jakavat tiedoston sen sijaan että kukin pitäisi omaa kopiotaan, joka erkanee muista. |
| **Hermes Agent** | Hermes on myös ohjauskerros, joka johtaa muita koodiagentteja, joten sitä varten pystytetty repositorio tarkoittaa usein useaa työkalua lukemassa samaa hakemistoa. Se etsii projektin ohjeita kiinteässä järjestyksessä ja ottaa ensimmäisen löytämänsä; chamnan kirjoittaa tuon järjestyksen kärjessä olevan tiedoston, mitoittaa sen Hermesin itsensä dokumentoimaan rajaan ja kieltäytyy korvaamasta tiedostoa, jota se ei ole kirjoittanut. |

## Näin otat sen käyttöön

Kumpaa reittiä menet, riippuu vain siitä, onko työkalussa istuntokoukku.

| | |
|---|---|
| **Claude Code** | Asenna lisäosana ja aja aloituskomento kerran repositorion sisällä. Koodiisi ei kirjoiteta mitään, ja sen jälkeen jokainen istunto alkaa hakemisto jo kontekstissa. |
| **Kaikki muu, Hermes mukaan lukien** | Kysy ensin, mitä chamnan tunnistaa, ja kerro sitten, mille agentille sen pitää kirjoittaa. Kun repositorion muoto muuttuu, rakenna hakemisto uudelleen ja kirjoita tiedosto uudestaan; valinnainen Git-koukku tekee molemmat committaessa. Claude Codea ei tarvita: nämä ovat tavallisia komentoja, ja lisäosa on vain yksi toimitustapa, ei tuote. Ilman nimettyä agenttia se tulostaa, mitä se tunnisti ja mikä komento sopisi, ja jättää päätöksen sinulle. Se ei koskaan kirjoita arvauksen perusteella. |

Komentojen nimet, agenttien täysi luettelo ja kunkin saama tiedosto ovat englanninkielisessä README-tiedostossa, jossa jokainen versioon sidottu yksityiskohta asuu.


## Vaatimukset

Claude Code · Python · Git · macOS, Linux tai Windows

Ei muuta, eikä asennettavia riippuvuuksia. Pythonin vähimmäisversio on tiedostossa [README › Requirements](../../README.md#requirements) — tällä sivulla ei ole lukuja, koska juuri luvut muuttuvat.

## Kytkeä pois tai poistaa

Kytke pois osa kerrallaan tiedostossa `.chamnan/config.json` · pysäytä se yhdessä repositoriossa · poista laajennus koko koneelta · poista `.chamnan/` milloin tahansa ilman että mikään hajoaa — vaiheet ovat kohdassa [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

## Lue ennen asennusta

**chamnan on sitä yhtä pääkansiota varten, johon palaat yhä uudelleen.** Kaikki mitä se tekee maksetaan etukäteen ja peritään takaisin myöhemmissä istunnoissa — kerran avatussa repositoriossa maksoit kaiken etkä perinyt mitään.

**Se raportoi, ei kirjoita koodiasi uudelleen.** Hakemisto kopioi kommentit jotka olet jo kirjoittanut, eikä keksi niitä. Kommentittomat tiedostot luetellaan nimeltä, jotta täydennät ne itse.

**Sen rajat on mitattu ja kirjoitettu**, mukaan lukien mittaukset jotka puhuvat sen omaa pääominaisuutta vastaan.

## Missä yksityiskohdat ovat

| | |
|---|---|
| Jokainen luku ja miten se mitattiin | [README › Evidence](../../README.md#evidence) |
| Regressiotestit — voit ajaa ne itse | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Mikä muuttui kussakin julkaisussa ja miksi | [CHANGELOG.md](../../CHANGELOG.md) |
| Kaikki muu | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
