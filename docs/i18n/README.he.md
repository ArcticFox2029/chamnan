# chamnan — שהמאגר יכיר את עצמו

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> בעמוד הזה אין מספרים, במכוון. כל המדידות נמצאות ב-README באנגלית ומשתנות בכל גרסה; העמוד הזה לא. ← [Evidence](../../README.md#evidence)

## מה זה

תוסף ל-Claude Code. הוא בונה אינדקס של המאגר שהסוכן קורא במקום לסרוק קובץ אחר קובץ, ושומר את ההקשר ההנדסי שנצבר תוך כדי העבודה — מצב העבודה, רישומי סשנים, הנימוקים שמאחורי החלטות, והנהלים שאתם גוזרים מחדש בכל פעם.

כל מה שהוא כותב הוא markdown פשוט שנשמר לצד הקוד. בלי קריאות רשת בזמן ריצה, בלי מסד נתונים, בלי תהליך רקע, בלי מודל embedding — רק ספריית התקן של Python.

## מה זה פותר

בכל סשן חדש, או בכל פעם שההקשר נדחס, כל מה שהסוכן הבין על הקוד שלכם נעלם והוא חוזר לחפש מההתחלה.

chamnan מונע את הגילוי החוזר הזה: האינדקס נמסר בתחילת הסשן, והמחיר הוא מספר ידוע וחסום ולא קריאות קבצים ללא גבול.

## התקנה

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

פתחו סשן חדש, והריצו `/chamnan:bootstrap` פעם אחת לכל מאגר.

## קראו לפני ההתקנה

**chamnan מתאים לתיקייה מרכזית אחת שחוזרים אליה שוב ושוב.** כל מה שהוא עושה משולם מראש ונגבה בחזרה בסשנים הבאים — במאגר שפותחים פעם אחת שילמתם הכול ולא קיבלתם דבר.

**הוא מדווח, לא משכתב את הקוד שלכם.** האינדקס מעתיק את ההערות שכתבתם, ולא ממציא. קבצים בלי הערה מקבלים אזכור בשם כדי שתשלימו בעצמכם.

**המגבלות שלו נמדדו ונכתבו**, כולל מדידות שפועלות נגד התכונה המרכזית שלו עצמו.

## איפה הפרטים

| | |
|---|---|
| כל מספר, ואיך הוא נמדד | [README › Evidence](../../README.md#evidence) |
| מערך בדיקות רגרסיה — אפשר להריץ בעצמכם | [`tests/run_tests.py`](../../tests/run_tests.py) |
| מה השתנה בכל גרסה, ולמה | [CHANGELOG.md](../../CHANGELOG.md) |
| הכול | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
