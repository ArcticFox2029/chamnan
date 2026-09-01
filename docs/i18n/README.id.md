# chamnan — membuat repositori mengenali dirinya sendiri

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Halaman ini sengaja tidak memuat angka. Semua hasil pengukuran ada di README bahasa Inggris dan berubah setiap rilis; halaman ini tidak. → [Evidence](../../README.md#evidence)

## Apa ini

Sebuah plugin Claude Code. Ia membangun indeks repositori untuk dibaca agent alih-alih memindai berkas satu per satu, dan menyimpan konteks teknis yang terkumpul selama Anda bekerja — status pekerjaan, catatan sesi, alasan di balik keputusan, dan prosedur yang selalu Anda turunkan ulang.

Semua yang ditulisnya adalah markdown biasa yang di-commit di samping kode. Tanpa panggilan jaringan saat berjalan, tanpa basis data, tanpa daemon, tanpa model embedding — hanya pustaka standar Python.

## Masalah apa yang dipecahkan

Setiap sesi baru, atau setiap kali konteks dipadatkan, apa pun yang sudah dipahami agent tentang basis kode Anda hilang, dan ia kembali melakukan grep dari awal.

chamnan membuat penemuan ulang itu tidak perlu terjadi: indeks diserahkan di awal sesi, dengan biaya berupa angka berbatas yang diketahui, bukan pembacaan berkas tanpa batas.

## Pemasangan

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Buka sesi baru, lalu jalankan `/chamnan:bootstrap` sekali per repositori.

## Baca sebelum memasang

**chamnan cocok untuk satu folder utama yang Anda datangi berulang kali.** Semua yang dilakukannya dibayar di muka dan ditagih kembali pada sesi-sesi berikutnya — pada repositori yang hanya dibuka sekali, Anda membayar penuh dan tidak menagih apa pun.

**Ia melaporkan, bukan menulis ulang kode Anda.** Indeks menyalin komentar yang sudah Anda tulis, bukan mengarangnya. Berkas tanpa komentar disebutkan namanya agar Anda melengkapinya sendiri.

**Batasannya telah diukur dan dituliskan**, termasuk hasil pengukuran yang justru melemahkan fitur utamanya sendiri.

## Di mana detailnya

| | |
|---|---|
| Setiap angka, dan bagaimana ia diukur | [README › Evidence](../../README.md#evidence) |
| Rangkaian uji regresi — bisa Anda jalankan sendiri | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Apa yang berubah di tiap rilis, dan mengapa | [CHANGELOG.md](../../CHANGELOG.md) |
| Semuanya | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
