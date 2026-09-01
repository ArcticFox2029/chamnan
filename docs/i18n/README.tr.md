# chamnan — deponun kendini tanıması için

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Bu sayfada bilerek hiç sayı yok. Tüm ölçümler İngilizce README'de ve her sürümle değişiyor; bu sayfa değişmiyor. → [Evidence](../../README.md#evidence)

## Bu nedir

Bir Claude Code eklentisi. Ajanın dosyaları tek tek taraması yerine okuyacağı bir depo dizini kurar ve çalışırken biriken mühendislik bağlamını saklar — işin durumu, oturum kayıtları, kararların ardındaki gerekçeler ve her seferinde yeniden çıkardığınız yordamlar.

Yazdığı her şey, kodun yanına commit edilen düz markdown. Çalışırken ağ çağrısı yok, veritabanı yok, arka plan süreci yok, embedding modeli yok — yalnızca Python standart kütüphanesi.

## Neyi çözer

Her yeni oturumda ya da bağlam her sıkıştırıldığında, ajanın kod tabanınız hakkında anladığı her şey kaybolur ve baştan aramaya döner.

chamnan bu yeniden keşfin hiç yaşanmamasını sağlar: dizin oturumun başında elinize verilir ve maliyeti sınırsız dosya okuması değil, bilinen ve sınırlı bir sayıdır.

## Kurulum

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Yeni bir oturum açın, sonra her depo için bir kez `/chamnan:bootstrap` çalıştırın.

## Kurmadan önce okuyun

**chamnan, tekrar tekrar döndüğünüz tek bir ana klasör içindir.** Yaptığı her şey önce ödenir, sonraki oturumlarda tahsil edilir — bir kez açtığınız bir depoda tamamını ödediniz ve hiçbir şey geri almadınız.

**Bildirir, kodunuzu yeniden yazmaz.** Dizin, sizin yazdığınız yorumları kopyalar; kendi uydurmaz. Yorumu olmayan dosyaların adını sayar ki kendiniz ekleyin.

**Sınırları ölçülmüş ve yazılmıştır**, kendi temel özelliğinin aleyhine çıkan ölçümler dahil.

## Ayrıntılar nerede

| | |
|---|---|
| Her sayı ve nasıl ölçüldüğü | [README › Evidence](../../README.md#evidence) |
| Regresyon testleri — kendiniz çalıştırabilirsiniz | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Her sürümde ne değişti ve neden | [CHANGELOG.md](../../CHANGELOG.md) |
| Her şey | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
