# chamnan — لكي يعرف المستودع نفسه

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> لا تحتوي هذه الصفحة على أي أرقام، عن قصد. كل القياسات موجودة في ملف README الإنجليزي وتتغيّر مع كل إصدار؛ أما هذه الصفحة فلا. ← [Evidence](../../README.md#evidence)

## ما هذا

إضافة لـ Claude Code. تبني فهرسًا للمستودع يقرأه الوكيل بدلًا من مسح الملفات ملفًا ملفًا، وتحتفظ بالسياق الهندسي الذي يتراكم أثناء عملك — حالة العمل، وسجلات الجلسات، وأسباب القرارات، والإجراءات التي تعيد استنتاجها في كل مرة.

كل ما تكتبه هو markdown عادي يُحفظ بجانب الشيفرة. لا اتصال بالشبكة أثناء التشغيل، ولا قاعدة بيانات، ولا خدمة تعمل في الخلفية، ولا نموذج embedding — مكتبة بايثون القياسية فقط.

## ما المشكلة التي يحلّها

مع كل جلسة جديدة، أو كلما ضُغط السياق، يضيع كل ما فهمه الوكيل عن شيفرتك ويعود إلى البحث من البداية.

يمنع chamnan هذا الاكتشاف المتكرر: يُسلَّم الفهرس عند بداية الجلسة، وتكون التكلفة رقمًا معروفًا ومحدودًا بدلًا من قراءات ملفات بلا حد.

## التثبيت

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

افتح جلسة جديدة، ثم شغّل `/chamnan:bootstrap` مرة واحدة لكل مستودع.

## اقرأ هذا قبل التثبيت

**chamnan مناسب لمجلد رئيسي واحد تعود إليه مرارًا.** كل ما يفعله يُدفع مقدّمًا ويُسترد في الجلسات اللاحقة — أما مستودع تفتحه مرة واحدة، فقد دفعت كل شيء ولم تسترد شيئًا.

**يبلّغ ولا يعيد كتابة شيفرتك.** الفهرس ينسخ التعليقات التي كتبتها أنت، ولا يختلق شيئًا. والملفات بلا تعليق تُذكر بأسمائها لتضيفها بنفسك.

**حدوده مقيسة ومكتوبة**، بما في ذلك القياسات التي تعمل ضد ميزته الأساسية نفسها.

## أين التفاصيل

| | |
|---|---|
| كل رقم، وكيف قيس | [README › Evidence](../../README.md#evidence) |
| مجموعة اختبارات الانحدار — يمكنك تشغيلها بنفسك | [`tests/run_tests.py`](../../tests/run_tests.py) |
| ما الذي تغيّر في كل إصدار، ولماذا | [CHANGELOG.md](../../CHANGELOG.md) |
| كل شيء | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
