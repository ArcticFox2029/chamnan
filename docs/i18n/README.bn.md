# chamnan — রিপোজিটরিকে নিজের পরিচয় দেওয়া

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> এই পাতায় ইচ্ছাকৃতভাবে কোনো সংখ্যা নেই। সব পরিমাপ ইংরেজি README-তে আছে এবং প্রতিটি রিলিজে বদলায়; এই পাতা বদলায় না। → [Evidence](../../README.md#evidence)

## এটি কী

Claude Code-এর একটি প্লাগিন। এটি রিপোজিটরির একটি সূচি তৈরি করে যা agent ফাইল একে একে ঘাঁটার বদলে পড়ে, এবং কাজ করতে করতে জমে ওঠা কারিগরি প্রেক্ষাপট ধরে রাখে — কাজের অবস্থা, সেশনের নথি, সিদ্ধান্তের পেছনের কারণ, আর যে ধাপগুলো আপনি প্রতিবার নতুন করে বের করেন।

এটি যা কিছু লেখে সবই সাধারণ markdown, কোডের পাশেই commit করা। চলার সময় কোনো নেটওয়ার্ক কল নেই, ডেটাবেস নেই, daemon নেই, embedding মডেল নেই — কেবল Python-এর স্ট্যান্ডার্ড লাইব্রেরি।

## এটি কী সমাধান করে

প্রতিটি নতুন সেশনে, বা যতবার প্রেক্ষাপট সংকুচিত হয়, agent আপনার কোডবেস সম্পর্কে যা বুঝেছিল তা মুছে যায় এবং সে আবার গোড়া থেকে খুঁজতে শুরু করে।

chamnan সেই পুনরাবিষ্কারটিকে ঘটতেই দেয় না: সূচি সেশনের শুরুতেই হাতে তুলে দেওয়া হয়, আর খরচ একটি জানা, সীমাবদ্ধ সংখ্যা — অসীম ফাইল-পাঠ নয়।

## ইনস্টল

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

একটি নতুন সেশন খুলুন, তারপর প্রতিটি রিপোজিটরিতে একবার `/chamnan:bootstrap` চালান।

## ইনস্টল করার আগে পড়ুন

**chamnan সেই মূল ফোল্ডারের জন্য যেখানে আপনি বারবার ফিরে আসেন।** এটি যা করে তার পুরোটাই আগে দিতে হয় এবং পরের সেশনগুলোতে ফেরত আসে — যে রিপোজিটরি আপনি একবারই খোলেন, সেখানে পুরোটা দিয়েছেন, কিছুই ফেরত পাননি।

**এটি জানায়, আপনার কোড বদলায় না।** সূচি আপনার লেখা মন্তব্যই তুলে আনে, নিজে বানায় না। মন্তব্যহীন ফাইলগুলোর নাম বলে দেওয়া হয় যাতে আপনি নিজে যোগ করতে পারেন।

**এর সীমাবদ্ধতা মাপা এবং লেখা আছে**, এমনকি সেই পরিমাপগুলোও যা এর নিজের মূল বৈশিষ্ট্যের বিপক্ষে যায়।

## বিস্তারিত কোথায়

| | |
|---|---|
| প্রতিটি সংখ্যা, এবং কীভাবে তা মাপা হয়েছে | [README › Evidence](../../README.md#evidence) |
| রিগ্রেশন পরীক্ষা — নিজেই চালাতে পারেন | [`tests/run_tests.py`](../../tests/run_tests.py) |
| প্রতিটি রিলিজে কী বদলেছে, এবং কেন | [CHANGELOG.md](../../CHANGELOG.md) |
| সবকিছু | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
