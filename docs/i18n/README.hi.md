# chamnan — रिपॉज़िटरी को खुद की पहचान देना

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> इस पृष्ठ पर जानबूझकर कोई संख्या नहीं है। सभी माप अंग्रेज़ी README में हैं और हर रिलीज़ के साथ बदलते हैं; यह पृष्ठ नहीं बदलता। → [Evidence](../../README.md#evidence)

## यह क्या है

Claude Code का एक प्लगिन। यह रिपॉज़िटरी की एक सूची बनाता है जिसे agent फ़ाइलें एक-एक करके खंगालने के बजाय पढ़ता है, और काम के दौरान जमा हुआ तकनीकी संदर्भ सहेजता है — काम की स्थिति, सत्र के अभिलेख, निर्णयों के पीछे के कारण, और वे प्रक्रियाएँ जो आप हर बार दोबारा निकालते हैं।

यह जो कुछ लिखता है वह सादा markdown है, कोड के साथ ही commit किया हुआ। चलते समय कोई नेटवर्क कॉल नहीं, कोई डेटाबेस नहीं, कोई daemon नहीं, कोई embedding मॉडल नहीं — केवल Python की मानक लाइब्रेरी।

## यह क्या हल करता है

हर नए सत्र में, या जब भी संदर्भ संपीड़ित होता है, agent ने आपके कोडबेस के बारे में जो समझा था वह मिट जाता है और वह फिर से खोजना शुरू कर देता है।

chamnan उस दोबारा खोज को होने ही नहीं देता: सूची सत्र के आरंभ में ही सौंप दी जाती है, और लागत एक ज्ञात, सीमित संख्या होती है — असीमित फ़ाइल-पठन नहीं।

## स्थापना

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

एक नया सत्र खोलें, फिर हर रिपॉज़िटरी में एक बार `/chamnan:bootstrap` चलाएँ।

## स्थापित करने से पहले पढ़ें

**chamnan उस मुख्य फ़ोल्डर के लिए है जिस पर आप बार-बार लौटते हैं।** यह जो कुछ करता है वह पहले चुकाया जाता है और बाद के सत्रों में वसूला जाता है — जिस रिपॉज़िटरी को आप एक ही बार खोलते हैं, वहाँ आपने पूरा चुकाया और कुछ वसूल नहीं हुआ।

**यह बताता है, आपका कोड नहीं बदलता।** सूची वही टिप्पणियाँ उठाती है जो आपने पहले ही लिखी हैं, अपनी ओर से गढ़ती नहीं। बिना टिप्पणी वाली फ़ाइलों के नाम गिना दिए जाते हैं ताकि आप स्वयं जोड़ सकें।

**इसकी सीमाएँ मापी और लिखी गई हैं**, उन मापों सहित जो इसकी अपनी मुख्य विशेषता के विरुद्ध जाते हैं।

## विवरण कहाँ है

| | |
|---|---|
| हर संख्या, और वह कैसे मापी गई | [README › Evidence](../../README.md#evidence) |
| रिग्रेशन परीक्षण — आप स्वयं चला सकते हैं | [`tests/run_tests.py`](../../tests/run_tests.py) |
| हर रिलीज़ में क्या बदला, और क्यों | [CHANGELOG.md](../../CHANGELOG.md) |
| सब कुछ | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
