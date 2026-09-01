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
