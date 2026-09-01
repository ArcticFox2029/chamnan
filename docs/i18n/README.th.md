# chamnan — ให้ repository รู้จักตัวเอง

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> หน้านี้ไม่มีตัวเลขโดยตั้งใจ ผลวัดทุกอย่างอยู่ใน README ภาษาอังกฤษและเปลี่ยนทุก release ส่วนหน้านี้ไม่เปลี่ยน → [Evidence](../../README.md#evidence)

## นี่คืออะไร

ปลั๊กอิน Claude Code ที่สร้างดัชนีของ repository ให้ agent อ่านแทนการไล่เปิดไฟล์ และเก็บบริบททางวิศวกรรมที่เกิดขึ้นระหว่างทำงาน — สถานะงาน บันทึกเซสชัน เหตุผลเบื้องหลังการตัดสินใจ และขั้นตอนที่ต้องคิดใหม่ทุกครั้ง

ทุกอย่างที่มันเขียนคือ markdown ธรรมดาที่ commit ไว้ข้างโค้ด ไม่มีการเรียกเครือข่ายตอนทำงาน ไม่มีฐานข้อมูล ไม่มี daemon ไม่มีโมเดล embedding — Python standard library ล้วน

## มันแก้ปัญหาอะไร

ทุกครั้งที่เปิดเซสชันใหม่ หรือทุกครั้งที่ context ถูกบีบ สิ่งที่ agent เข้าใจเกี่ยวกับโค้ดของคุณหายไปหมด แล้วมันก็เริ่มไล่อ่านไฟล์ใหม่ตั้งแต่ต้น

chamnan ทำให้การค้นพบซ้ำนั้นไม่ต้องเกิดขึ้น ดัชนีถูกยื่นให้ตอนเริ่มเซสชัน ด้วยต้นทุนที่มีขอบเขตแน่นอน แทนการอ่านไฟล์ที่ไม่มีขอบเขต

## ติดตั้ง

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

เปิดเซสชันใหม่ แล้วสั่ง `/chamnan:bootstrap` หนึ่งครั้งต่อ repository

## อ่านก่อนติดตั้ง

**chamnan เหมาะกับโฟลเดอร์หลักที่คุณกลับมาทำงานซ้ำๆ** ทุกอย่างที่มันทำคือการลงทุนที่คืนทุนในเซสชันถัดๆ ไป — ถ้าเป็น repo ที่เปิดครั้งเดียว คุณจ่ายไปทั้งหมดแล้วไม่ได้อะไรกลับ

**มันรายงาน ไม่แก้โค้ดให้** ดัชนีคัดลอกคอมเมนต์ที่คุณเขียนไว้แล้ว ไม่ได้แต่งขึ้นเอง ไฟล์ที่ไม่มีคอมเมนต์จะถูกระบุชื่อไว้ให้คุณไปเติมเอง

**ข้อจำกัดถูกวัดและเขียนไว้แล้ว** รวมถึงผลวัดที่ค้านฟีเจอร์หลักของมันเอง และฟีเจอร์ที่วัดแล้วตัดสินใจไม่สร้าง — อยู่ใน Evidence ของ README ภาษาอังกฤษ

## รายละเอียดอยู่ที่ไหน

| | |
|---|---|
| ตัวเลขทุกตัว และวิธีที่วัดมันมา | [README › Evidence](../../README.md#evidence) |
| ชุดทดสอบถดถอย — รันเองได้ | [`tests/run_tests.py`](../../tests/run_tests.py) |
| แต่ละรุ่นแก้อะไร และทำไม | [CHANGELOG.md](../../CHANGELOG.md) |
| ทุกอย่าง | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
