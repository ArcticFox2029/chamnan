# chamnan — 讓儲存庫了解它自己

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> 本頁刻意不含任何數字。所有測量結果都在英文 README 中，且每次發布都會變動；本頁不會。→ [Evidence](../../README.md#evidence)

## 這是什麼

一個 Claude Code 外掛。它為儲存庫建立索引供 agent 閱讀，取代逐一掃描檔案；並保留你工作過程中累積的工程脈絡——工作狀態、工作階段紀錄、決策背後的理由，以及那些每次都要重新推導的步驟。

它寫下的一切都是提交在程式碼旁邊的純 markdown。執行時不發出任何網路請求，沒有資料庫，沒有常駐程式，沒有 embedding 模型——只用 Python 標準函式庫。

## 它解決什麼問題

每開一個新的工作階段，或每次脈絡被壓縮，agent 對你程式碼庫的理解就全部消失，然後又回去逐一 grep。

chamnan 讓這種重新發現不必發生：索引在工作階段開始時就交到手上，代價是一個有上限的已知數字，而不是沒有上限的檔案讀取。

## 安裝

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

開一個新的工作階段，每個儲存庫執行一次 `/chamnan:bootstrap`。

## 安裝前請先讀這段

**chamnan 適合你會反覆回來工作的那個主資料夾。** 它做的每件事都是先付出、之後每個工作階段收回——對只打開一次的儲存庫，你付出了全部卻收不回任何東西。

**它只回報，不改寫你的程式碼。** 索引複製你已經寫下的註解，不會替你捏造。沒有註解的檔案會被逐一列出，由你自己補上。

**它的限制都經過測量並寫了下來**，包括與它自身核心功能相悖的測量結果，以及測量後決定不做的功能——都在英文 README 的 Evidence 一節。

## 細節在哪裡

| | |
|---|---|
| 每個數字，以及它是怎麼測出來的 | [README › Evidence](../../README.md#evidence) |
| 迴歸測試套件——你可以自己跑 | [`tests/run_tests.py`](../../tests/run_tests.py) |
| 每個版本改了什麼、為什麼 | [CHANGELOG.md](../../CHANGELOG.md) |
| 全部內容 | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
