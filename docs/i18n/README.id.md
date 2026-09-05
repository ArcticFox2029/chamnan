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

<!-- generated: build_sections.py -->

## Seluruh fitur

Empat kemampuan. Semua yang tercantum di bawah sudah berjalan di rilis saat ini. Setiap bagian bisa dimatikan sendiri-sendiri di `.chamnan/config.json`, dan tidak ada yang bergantung pada yang lain.

### Memahami — apa yang ada, dan apa terhubung dengan apa

| | |
|---|---|
| **Indeks** | `MAP.md` — satu baris per berkas, dihasilkan dari kodenya sendiri. Agen membaca indeks lalu melakukan grep untuk detail yang diperlukan, bukan menyusuri seluruh pohon berkas. |
| **Dampak** | Siapa yang bergantung pada berkas ini, dan uji mana yang menutupinya. Import miliknya sendiri sudah ada di bagian atas berkas; yang mahal dicari justru arah sebaliknya — grep jalurnya sebelum mengubah. |
| **Model data** | Nama tabel dan model dengan ringkasan satu baris, diambil dari DDL, migrasi dan model ORM — bukan dump skema utuh. Hanya muncul kalau repositorinya memang mendefinisikannya. |
| **Permukaan API** | Metode, path dan handler, dari dekorator rute, dokumen OpenAPI dan definisi layanan `.proto` — bukan seluruh spesifikasi. |
| **Konfigurasi** | Nama variabel lingkungan yang dibaca repositori. **Hanya nama, nilainya tidak pernah dicatat** — dan ia memperingatkan bila `.env` belum masuk gitignore. |
| **Deployment** | Apa yang benar-benar berjalan, dibaca dari manifes Kubernetes, Ansible, Compose, Helm dan CI: jenis dan nama, image, peran, pipeline. Secret hanya menyumbang namanya, tidak isinya. |
| **Bahan non-sumber** | Dokumen pindaian, ekspor, arsip — hanya jumlah, ukuran dan ekstensi yang dominan. Bagian ini ada supaya agen tidak pergi melihat sendiri, yang jauh lebih mahal. **Tidak pernah dibuka, tidak pernah dibaca.** |

### Mengingat — sedang mengerjakan apa, dan mengapa

| | |
|---|---|
| **Status kerja** | `STATE.md` — apa yang sedang dikerjakan saat ini, disuntikkan saat sesi dimulai supaya pemadatan konteks berhenti menghapusnya. |
| **Catatan sesi** | Satu catatan per sesi di `.chamnan/sessions/`. **Hanya yang belum selesai** yang sampai ke sesi berikutnya; sesi yang tuntas rapi tidak menyuntikkan apa pun. |
| **Memori** | `decisions/`, `lessons/`, `rules/`. Aturan adalah batasan tetap, jadi selalu ada di depan agen setiap sesi; keputusan dan pelajaran hanya menyumbang judul, dan dibaca ketika judulnya tampak relevan. |
| **Utas terbuka** | Alur kerja yang belum selesai, lengkap dengan riwayat berkas mana saja yang sudah tersentuh — dan tetap terikut setelah berkasnya diganti nama. |

### Memakai ulang — yang sudah pernah dipecahkan

| | |
|---|---|
| **Prosedur** | Keterampilan yang **ditulis agen sendiri** ketika bertemu sesuatu yang rumit atau berulang. Bukan pustaka jadi yang disertakan, melainkan sebuah mekanisme. |
| **Perkakas** | Melihat skrip sementara yang sama ditulis lagi, lalu menawarkan untuk menyimpannya — dan menyebutkannya sebelum Anda menulis skrip baru. |
| **Alur kerja** | Melihat rangkaian perintah yang sama berjalan dengan urutan sama di hari-hari yang terpisah, lalu menawarkan untuk mencatat urutan itu. |

### Berkembang — apa yang dipelajari repositori tentang dirinya

| | |
|---|---|
| **Tonggak** | Segelintir perubahan yang mengubah bentuk repositori: apa yang berpindah, mengapa layak dikerjakan, wilayah mana yang tersentuh. |
| **Kandidat** | Rangkaian perintah berulang yang terdeteksi selalu **ditahan menunggu konfirmasi manusia**. Tidak ada yang dinaikkan otomatis. |
| **Lingkungan** | Menyatakan apa itu production atau staging dan apa larangannya, lalu memperingatkan ketika pernyataan itu sudah usang. |
| **Laporan** | Apa yang disimpan workspace, apakah benar-benar terjangkau, dan bagaimana konteks per giliran repositori Anda berubah. Angka Anda, bukan angka kami. |

Kerja rekayasa yang berulang menjadi pengetahuan repositori yang bisa dipakai ulang — **bukan pelatihan model, dan bukan otomatisasi pengembang.** Ini mekanisme untuk menyimpan kerja yang kalau tidak, hanya ada di kepala orang yang mengerjakannya.

## Perintah

Semuanya bisa dipanggil dari shell, dan agen juga memanggilnya sendiri.

| | |
|---|---|
| `chamnan-map` | membangun dan memperbarui indeks |
| `chamnan-report` | apa yang disimpan workspace, dan bagaimana konteks per giliran berubah |
| `chamnan-impact` | siapa yang bergantung pada berkas ini, dan uji mana yang menutupinya |
| `chamnan-timeline` | apa saja yang sudah terjadi pada berkas ini |
| `chamnan-peek` | menjelaskan isi berkas besar tanpa membacanya ke dalam konteks |
| `chamnan-promote` | menyimpan sebuah skrip sebagai perkakas tetap repositori |
| `chamnan-candidates` | melihat, mengonfirmasi atau menolak pengulangan yang terdeteksi |
| `chamnan-env` | menyatakan lingkungan dan larangannya, lalu memeriksa apakah pernyataannya masih segar |
| `chamnan-age` | di mana pengetahuan yang tersimpan mulai menua |

Dan keterampilan yang dipanggil dari dalam sesi: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Apa yang ditulisnya, dan di mana

Semuanya di dalam `.chamnan/`, berupa markdown dan JSON biasa. Bisa dibaca, disunting tangan, dan dihapus kapan saja tanpa merusak apa pun.

| | |
|---|---|
| `MAP.md` | apa yang ada, dan apa bergantung pada apa |
| `STATE.md` | apa yang sedang dikerjakan saat ini |
| `sessions/` | di mana kerja sebelumnya berhenti |
| `memory/` | keputusan, pelajaran dan aturan tetap |
| `threads/` | alur kerja yang masih terbuka |
| `skills/` · `tools/` | prosedur dan skrip yang layak disimpan |
| `milestones.md` | perubahan yang mengubah bentuk repositori |
| `config.json` | menyalakan dan mematikan tiap bagian, serta batas ukuran blok yang disuntikkan ke sesi |

**Satu-satunya tulisan di luar `.chamnan/`** adalah hook Git pre-commit opsional yang menjaga indeks tetap seiring dengan kode — dipasang hanya jika Anda setuju, dan bisa dilepas.

**Agennya tidak belajar.** Tidak ada yang dilatih, tidak ada yang tersisa di luar direktori ini, dan sesi berikutnya tetap mulai dari nol — hanya saja mulai dari nol *di dalam repositori yang menjelaskan dirinya sendiri*. Kesinambungannya ada pada berkasnya, bukan pada modelnya.

## Keamanan

| | |
|---|---|
| **Tidak memanggil jaringan saat berjalan** | Sekali pun tidak. Tidak perlu API key, tidak ada yang dikirim ke mana pun. |
| **Tidak menulis ulang kode Anda** | Ia melaporkan, bukan menyunting. Indeksnya menyalin komentar yang sudah Anda tulis, bukan mengarangnya; berkas tanpa komentar disebutkan namanya untuk Anda isi sendiri. |
| **Tanpa daemon, tanpa kerja latar** | Tidak ada proses menetap, tidak ada basis data, tidak ada model embedding — hanya pustaka standar Python. |
| **Kredensial disaring lebih dulu** | Semua yang akan ditulis atau disuntikkan ke sesi melewati penyaring kredensial: *nama* variabel disimpan, nilainya tidak. Batas yang tidak bisa dicapai penyaring itu ditulis tepat di samping angkanya sendiri di README bahasa Inggris. |
| **Apa yang bisa dilakukan sebuah plugin terpasang terhadap Anda** | Dijelaskan lengkap di README bahasa Inggris, termasuk di titik mana chamnan memutus rantai kebocoran. |

## Bekerja dengan apa saja

chamnan adalah teks dan Python pustaka standar. Tidak ada isi indeks yang menjadi milik satu vendor, satu editor, atau satu sistem operasi tertentu.

| | |
|---|---|
| **Model apa pun, vendor apa pun** | Indeks berupa teks biasa dan dikirim sebagai konteks. Model hanya menentukan seberapa banyak yang layak dikirim, tidak pernah menentukan apa pergi ke mana. Aturlah ukurannya dengan `--model`, `--window`, atau `--profile`. Berganti model tidak menuntut pemasangan ulang apa pun. |
| **macOS, Linux, Windows, WSL** | Plugin yang sama di mana pun, hanya pustaka standar, tidak ada yang perlu dipasang. Di macOS dan Linux perintah berjalan langsung. Di Windows, shell tidak dapat menjalankan skrip tanpa ekstensi, sehingga di samping setiap perintah dan setiap hook diletakkan berkas `.cmd` hasil pembangkitan; berkas itu ikut terkirim bersama plugin dan CI menjalankannya sendiri. WSL berperilaku seperti Linux. |
| **Banyak agen, satu indeks** | Claude Code menerimanya lewat hook sesi dan tidak ada berkas yang ditulis ke proyek Anda. Gemini CLI juga punya hook sesi yang sesungguhnya. Agen lain menerima berkas di jalur yang dibacanya, dan agen yang membaca jalur sama berbagi berkas itu alih-alih masing-masing menyimpan salinan yang lama-lama menyimpang. |
| **Hermes Agent** | Hermes sekaligus lapisan kendali yang mengarahkan agen pemrograman lain, sehingga repositori yang disiapkan untuknya sering berarti beberapa perkakas membaca indeks yang sama. Ia mencari instruksi proyek dengan urutan tetap dan memakai yang pertama ditemukan; chamnan menulis berkas yang berada di puncak urutan itu, menyesuaikan ukurannya dengan batas yang didokumentasikan Hermes sendiri, dan menolak menimpa berkas yang bukan tulisannya. |

## Cara memasangnya

Lewat jalan mana Anda masuk hanya bergantung pada ada tidaknya hook sesi pada perkakas itu.

| | |
|---|---|
| **Claude Code** | Pasang sebagai plugin lalu jalankan perintah awal satu kali di dalam sebuah repositori. Tidak ada yang ditulis ke kode Anda, dan sesudahnya setiap sesi dimulai dengan indeks sudah berada di konteks. |
| **Selebihnya, termasuk Hermes** | Tanyakan dulu apa yang terdeteksi oleh chamnan, lalu sebutkan untuk agen mana ia harus menulis. Ketika bentuk repositori berubah, bangun ulang indeksnya dan tulis berkasnya lagi; sebuah hook Git opsional mengerjakan keduanya saat commit. Claude Code tidak diperlukan: ini perintah biasa, dan plugin hanyalah satu jalur pengantaran, bukan produknya. Tanpa agen yang disebut, ia mencetak apa yang terdeteksi beserta perintah yang cocok, dan menyerahkan keputusan kepada Anda. Ia tidak pernah menulis berdasarkan terkaan. |

Nama perintah, daftar lengkap agen, dan berkas yang diterima masing-masing ada di README bahasa Inggris, tempat setiap rincian yang terikat versi berada.


## Kebutuhan sistem

Claude Code · Python · Git · macOS, Linux atau Windows

Selain itu tidak ada, dan tidak ada dependensi yang perlu dipasang. Versi minimum Python ada di [README › Requirements](../../README.md#requirements) — halaman ini tidak memuat angka, karena angkalah yang berubah.

## Mematikan atau mencopot

Matikan per bagian di `.chamnan/config.json` · hentikan di satu repositori · copot plugin dari seluruh mesin · hapus `.chamnan/` kapan saja tanpa merusak apa pun — langkah lengkapnya di [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
