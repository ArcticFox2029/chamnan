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

<!-- generated: build_sections.py -->

## Tüm özellikler

Dört yetenek. Aşağıdaki tablolarda yer alan her şey mevcut sürümde gerçekten çalışıyor. Her parça `.chamnan/config.json` içinde ayrı ayrı kapatılabilir ve hiçbiri diğerine bağlı değildir.

### Anlamak — ne var, ve ne neye bağlı

| | |
|---|---|
| **Dizin** | `MAP.md` — dosya başına bir satır, kodun kendisinden üretilir. Ajan dizini okur, gereken ayrıntıyı grep eder; ağacı baştan sona taramaz. |
| **Etki** | Bu dosyaya kim bağımlı ve hangi testler onu kapsıyor. Dosyanın kendi import'ları zaten en üstünde yazılı; pahalı olan ters yön — değiştirmeden önce yolu grep edin. |
| **Veri modeli** | Tablo ve model adları, birer satırlık özetle; DDL'den, göçlerden ve ORM modellerinden çıkarılır — şemanın tam dökümü değil. Yalnızca depo gerçekten tanımlıyorsa görünür. |
| **API yüzeyi** | Metot, yol ve işleyici; rota dekoratörlerinden, OpenAPI belgelerinden ve `.proto` servis tanımlarından — şartnamenin tamamı değil. |
| **Yapılandırma** | Deponun okuduğu ortam değişkeni adları. **Yalnızca adlar, değerler asla kaydedilmez** — ve `.env` gitignore'da değilse uyarır. |
| **Dağıtım** | Gerçekte ne çalışıyor: Kubernetes, Ansible, Compose, Helm ve CI manifestlerinden okunan türler ve adlar, imajlar, roller, hatlar. Secret yalnızca adını verir, altındaki hiçbir şeyi değil. |
| **Kaynak olmayan malzeme** | Taranmış evrak, dışa aktarımlar, arşivler — yalnızca sayı, boyut ve baskın uzantılar. Ajanın gidip kendisi bakmasını engellemek için var; o çok daha pahalıya mal olur. **Asla açılmaz, asla okunmaz.** |

### Hatırlamak — ne yapılıyordu, ve neden

| | |
|---|---|
| **Çalışma durumu** | `STATE.md` — şu anda üzerinde çalışılan iş; oturum başlangıcında enjekte edilir, böylece bağlam sıkıştırması onu silmeyi bırakır. |
| **Oturum kaydı** | `.chamnan/sessions/` altında oturum başına bir kayıt. Sonraki oturuma **yalnızca bitmemiş olan** ulaşır; temiz kapanan bir oturum hiçbir şey enjekte etmez. |
| **Bellek** | `decisions/`, `lessons/`, `rules/`. Kurallar kalıcı kısıtlardır, bu yüzden her oturumda ajanın önündedir; kararlar ve dersler yalnızca başlık verir ve başlık ilgili göründüğünde okunur. |
| **Açık iş hatları** | Hâlâ süren çalışma hatları ve o hattın hangi dosyalara dokunduğunun geçmişi — dosya yeniden adlandırılsa da izini sürmeye devam eder. |

### Yeniden kullanmak — bir kez çözülmüş olanı

| | |
|---|---|
| **Prosedürler** | Ajanın karmaşık ya da yinelenen bir şeyle karşılaştığında **kendi yazdığı** beceriler. Paketle gelen hazır bir kütüphane değil, bir mekanizma. |
| **Araçlar** | Aynı geçici betiğin yeniden yazıldığını fark eder ve saklamayı önerir — üstelik siz yeni bir betik yazmadan önce onu hatırlatır. |
| **İş akışları** | Aynı komut dizisinin ayrı günlerde aynı sırayla çalıştığını fark eder ve o diziyi yazmayı önerir. |

### Birikmek — deponun kendisi hakkında öğrendikleri

| | |
|---|---|
| **Kilometre taşları** | Deponun biçimini değiştiren birkaç değişiklik: ne taşındı, neden değdi, hangi alanlara dokundu. |
| **Adaylar** | Tespit edilen yinelenen komut dizileri **her zaman insan onayı bekler**. Hiçbir şey kendiliğinden terfi etmez. |
| **Ortamlar** | production ya da staging'in ne olduğunu ve neyin yasak olduğunu bildirin; o bildirim eskiyince uyarır. |
| **Rapor** | Çalışma alanı ne tutuyor, gerçekten erişilebilir mi, ve deponuzun tur başına bağlamı nasıl değişti. Sizin sayınız, bizim değil. |

Yinelenen mühendislik emeği, yeniden kullanılabilir depo bilgisine dönüşür — **model eğitimi değil, geliştiricinin otomasyonu da değil.** Aksi hâlde yalnızca onu yapan kişinin kafasında kalacak işi saklamanın yolu.

## Komutlar

Hepsi kabuktan çağrılabilir; ajan da bunları kendisi çağırır.

| | |
|---|---|
| `chamnan-map` | dizini oluşturur ve günceller |
| `chamnan-report` | çalışma alanı ne tutuyor, tur başına bağlam nasıl değişti |
| `chamnan-impact` | bu dosyaya kim bağımlı, hangi testler kapsıyor |
| `chamnan-timeline` | bu dosyanın başından neler geçti |
| `chamnan-peek` | büyük bir dosyayı bağlama okumadan içinde ne olduğunu söyler |
| `chamnan-promote` | bir betiği deponun kalıcı aracı olarak saklar |
| `chamnan-candidates` | tespit edilen yinelenmeleri görmek, onaylamak ya da reddetmek |
| `chamnan-env` | ortamı ve yasaklarını bildirmek, bildirimin hâlâ taze olduğunu denetlemek |
| `chamnan-age` | saklanan bilgi nereden eskimeye başlamış |

Ve oturum içinden çağrılan beceriler: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Ne yazar, nereye

Hepsi `.chamnan/` içinde, sıradan markdown ve JSON. Okunabilir, elle düzenlenebilir, istediğiniz an silinebilir — hiçbir şey bozulmaz.

| | |
|---|---|
| `MAP.md` | ne var, ve ne neye bağımlı |
| `STATE.md` | şu anda ne yapılıyor |
| `sessions/` | önceki çalışma nerede durdu |
| `memory/` | kararlar, dersler ve kalıcı kurallar |
| `threads/` | hâlâ açık çalışma hatları |
| `skills/` · `tools/` | saklamaya değer prosedürler ve betikler |
| `milestones.md` | deponun biçimini değiştiren değişiklikler |
| `config.json` | her parçanın açılıp kapanması ve oturuma enjekte edilen bloğun bayt tavanı |

**`.chamnan/` dışına yapılan tek yazma**, dizini ağaçla uyumlu tutan isteğe bağlı bir Git pre-commit kancasıdır — yalnızca siz evet derseniz kurulur ve kaldırılabilir.

**Ajan öğrenmiyor.** Hiçbir şey eğitilmez, bu dizinin dışında hiçbir şey kalmaz ve sonraki oturum yine sıfırdan başlar — yalnızca *kendini açıklayabilen bir depoda* sıfırdan başlar. Süreklilik üretilen dosyalarda, modelde değil.

## Güvenlik

| | |
|---|---|
| **Çalışırken ağ çağrısı yok** | Bir tane bile. API anahtarı gerekmez, hiçbir şey hiçbir yere gönderilmez. |
| **Kaynağınızı yeniden yazmaz** | Raporlar, düzenlemez. Dizin zaten yazdığınız yorumları kopyalar, uydurmaz; yorumsuz dosyaların adları sıralanır ki siz doldurun. |
| **Daemon yok, arka plan işi yok** | Yerleşik süreç yok, veritabanı yok, gömme modeli yok — yalnızca Python'un standart kütüphanesi. |
| **Sırlar önce süzülür** | Yazılacak ya da oturuma enjekte edilecek her şey önce bir sır süzgecinden geçer: değişken *adları* kalır, değerleri kalmaz. Bu süzgecin ulaşamadığı sınır ise İngilizce README'de kendi sayısının yanında yazılıdır. |
| **Kurulu bir eklenti size ne yapabilir** | İngilizce README'de tam olarak açıklanmıştır; chamnan'ın sızıntı zincirini nerede kestiği dahil. |

## Nelerle çalışır

chamnan metin ve standart kütüphane Python'ıdır. Dizindeki hiçbir şey belirli bir sağlayıcıya, belirli bir editöre ya da belirli bir işletim sistemine ait değildir.

| | |
|---|---|
| **Herhangi bir model, herhangi bir sağlayıcı** | Dizin düz metindir ve bağlam olarak gönderilir. Model yalnızca ne kadarının gönderilmeye değer olduğunu değiştirir; neyin nereye gideceğini asla. Boyutu `--model`, `--window` ya da `--profile` ile ayarlarsınız. Model değiştirmek hiçbir şeyi yeniden kurmayı gerektirmez. `--model` şu aileleri adlarıyla tanır: `claude` · `codestral` · `deepseek` · `gemini` · `gemma` · `glm` · `gpt` · `grok` · `kimi` · `mistral` · `openai` — eşleştirme büyük küçük harfi, ayırıcıları ve sürüm numaralarını dikkate almaz. `llama` ve `qwen` bilerek dışarıda bırakılmıştır: ikisi de farklı bütçeler isteyen birkaç boyutta çıkar, bu yüzden adlarını vermek varsayılan profili ve hangi iki boyutun kastedilmiş olabileceğini söyleyen bir satırı döndürür. **Listede olmayan bir model yine de çalışır**: varsayılan profili ve tanınmadığına dair bir not alır, hiçbir şey başarısız olmaz. `--window` sayıyı doğrudan alır ve her zaman kesindir. |
| **macOS, Linux, Windows, WSL** | Her yerde aynı eklenti, yalnızca standart kütüphane, kurulacak bir şey yok. macOS ve Linux'ta komutlar doğrudan çalışır. Windows'ta kabuk uzantısız bir betiği çalıştıramaz, bu yüzden her komutun ve her kancanın yanında üretilmiş bir `.cmd` durur; bunlar eklentiyle birlikte gelir ve CI doğrudan onları çalıştırır. WSL, Linux gibi davranır. |
| **Çok ajan, tek dizin** | Claude Code bloğu bir oturum kancasıyla alır ve projenize hiçbir dosya yazılmaz. Gemini CLI'nin de gerçek bir oturum kancası vardır. Diğer ajanlar, o ajanın okuduğu yolda bir dosya alır; aynı yolu okuyanlar ise her biri zamanla birbirinden ayrışan bir kopya tutmak yerine dosyayı paylaşır. |
| **Hermes Agent** | Hermes aynı zamanda başka kod ajanlarını yöneten bir denetim katmanıdır; bu yüzden onun için hazırlanmış bir depo çoğu zaman birden çok aracın aynı dizini okuması demektir. Proje yönergelerini sabit bir sırayla arar ve bulduğu ilkini alır; chamnan bu sıranın başındaki dosyayı yazar, boyutunu Hermes'in kendi belgelediği sınıra göre ayarlar ve kendi yazmadığı bir dosyanın üzerine yazmayı reddeder. |

## Nasıl kurulur

Hangi yoldan gireceğiniz yalnızca o aracın oturum kancası olup olmadığına bağlıdır.

| | |
|---|---|
| **Claude Code** | Eklenti olarak kurun ve bir depo içinde başlangıç komutunu bir kez çalıştırın. Kodunuza hiçbir şey yazılmaz ve bundan sonra her oturum dizin zaten bağlamdayken başlar. |
| **Geri kalan her şey, Hermes dâhil** | Önce chamnan'ın ne algıladığını sorun, sonra hangi ajan için yazacağını söyleyin. Deponun biçimi değiştiğinde dizini yeniden kurun ve dosyayı tekrar yazın; isteğe bağlı bir Git kancası işlem sırasında ikisini de yapar. Claude Code gerekmez: bunlar sıradan komutlardır ve eklenti yalnızca bir teslim yoludur, ürünün kendisi değil. Ajan belirtilmezse ne algıladığını ve hangi komutun uygun olacağını yazdırır, kararı size bırakır. Asla tahmine dayanarak yazmaz. |

Komut adları, ajanların tam listesi ve her birinin aldığı dosya İngilizce README'de yer alır; sürüme bağlı her ayrıntı orada yaşar.


## Gereksinimler

Claude Code · Python · Git · macOS, Linux ya da Windows

Başka bir şey gerekmez, kurulacak bağımlılık da yoktur. Python'un asgari sürümü [README › Requirements](../../README.md#requirements) içindedir — bu sayfa sayı taşımaz, çünkü değişen şey sayılardır.

## Kapatmak ya da kaldırmak

`.chamnan/config.json` içinde parça parça kapatın · tek bir depoda durdurun · eklentiyi makineden tümüyle kaldırın · `.chamnan/` dizinini istediğiniz an silin, hiçbir şey bozulmaz — ayrıntılı adımlar [README › Update, disable, uninstall](../../README.md#update-disable-uninstall) içinde.

<!-- /generated -->

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
