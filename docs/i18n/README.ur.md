# chamnan — تاکہ ریپوزٹری خود کو پہچانے

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> اس صفحے پر جان بوجھ کر کوئی عدد نہیں ہے۔ تمام پیمائشیں انگریزی README میں ہیں اور ہر ریلیز کے ساتھ بدلتی ہیں؛ یہ صفحہ نہیں بدلتا۔ ← [Evidence](../../README.md#evidence)

## یہ کیا ہے

Claude Code کا ایک پلگ اِن۔ یہ ریپوزٹری کی ایک فہرست بناتا ہے جسے ایجنٹ فائلیں ایک ایک کر کے کھنگالنے کے بجائے پڑھتا ہے، اور کام کے دوران جمع ہونے والا تکنیکی سیاق محفوظ رکھتا ہے — کام کی حالت، سیشن کے ریکارڈ، فیصلوں کے پیچھے کی وجوہات، اور وہ طریقے جو آپ ہر بار نئے سرے سے نکالتے ہیں۔

یہ جو کچھ لکھتا ہے وہ سادہ markdown ہے جو کوڈ کے ساتھ ہی commit ہوتا ہے۔ چلتے وقت کوئی نیٹ ورک کال نہیں، کوئی ڈیٹابیس نہیں، کوئی daemon نہیں، کوئی embedding ماڈل نہیں — صرف Python کی معیاری لائبریری۔

## یہ کیا حل کرتا ہے

ہر نئے سیشن میں، یا جب بھی سیاق دبایا جاتا ہے، ایجنٹ نے آپ کے کوڈ کے بارے میں جو سمجھا تھا وہ مٹ جاتا ہے اور وہ دوبارہ شروع سے تلاش کرنے لگتا ہے۔

chamnan اس دوبارہ دریافت کو ہونے ہی نہیں دیتا: فہرست سیشن کے آغاز پر ہی دے دی جاتی ہے، اور قیمت ایک معلوم، محدود عدد ہوتی ہے، نہ کہ لامحدود فائل خوانی۔

## تنصیب

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

ایک نیا سیشن کھولیں، پھر ہر ریپوزٹری میں ایک بار `/chamnan:bootstrap` چلائیں۔

## تنصیب سے پہلے پڑھیں

**chamnan اُس مرکزی فولڈر کے لیے ہے جس پر آپ بار بار واپس آتے ہیں۔** یہ جو کچھ کرتا ہے وہ پہلے ادا کیا جاتا ہے اور بعد کے سیشنوں میں وصول ہوتا ہے — جس ریپوزٹری کو آپ ایک ہی بار کھولتے ہیں، وہاں آپ نے پورا ادا کیا اور کچھ وصول نہ ہوا۔

**یہ اطلاع دیتا ہے، آپ کا کوڈ نہیں بدلتا۔** فہرست وہی تبصرے اٹھاتی ہے جو آپ پہلے لکھ چکے ہیں، خود سے نہیں گھڑتی۔ بغیر تبصرے والی فائلوں کے نام گنوا دیے جاتے ہیں تاکہ آپ خود شامل کریں۔

**اس کی حدود ناپی اور لکھی گئی ہیں**، بشمول وہ پیمائشیں جو خود اس کی بنیادی خصوصیت کے خلاف جاتی ہیں۔

## تفصیل کہاں ہے

| | |
|---|---|
| ہر عدد، اور وہ کیسے ناپا گیا | [README › Evidence](../../README.md#evidence) |
| ریگریشن ٹیسٹ — آپ خود چلا سکتے ہیں | [`tests/run_tests.py`](../../tests/run_tests.py) |
| ہر ریلیز میں کیا بدلا، اور کیوں | [CHANGELOG.md](../../CHANGELOG.md) |
| سب کچھ | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
