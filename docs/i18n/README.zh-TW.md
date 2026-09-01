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

<!-- generated: build_sections.py -->

## 全部功能

四類能力。下表所列皆已在目前版本中實際運作。每一部分都可在 `.chamnan/config.json` 中單獨關閉，彼此之間沒有相依。

### 理解 —— 有什麼，以及什麼與什麼相連

| | |
|---|---|
| **索引** | `MAP.md` —— 每個檔案一行，由程式碼產生。代理讀索引，再按需 grep 細節，不必走遍整棵目錄樹。 |
| **影響面** | 誰相依於這個檔案，哪些測試涵蓋它。檔案自己的 import 就寫在開頭，真正費力去找的是反向邊 —— 動手改之前先 grep 一下路徑。 |
| **資料模型** | 資料表與模型名稱，各配一行說明，取自 DDL、遷移腳本與 ORM 模型，而非整份 schema 傾印。儲存庫中確有定義時才會出現。 |
| **API 介面** | 方法、路徑與處理函式，取自路由裝飾器、OpenAPI 文件與 `.proto` 服務定義，而非整份規格。 |
| **設定** | 儲存庫讀取的環境變數名稱。**只有名稱，絕不記錄值** —— 並會在 `.env` 未被 gitignore 時提出警告。 |
| **部署** | 實際在跑的東西，讀自 Kubernetes、Ansible、Compose、Helm 與 CI 清單：種類與名稱、映像檔、角色、流水線。Secret 只提供名稱，其下內容一概不取。 |
| **非原始碼資料** | 掃描文件、匯出檔、壓縮檔等，只報告數量、大小與主要副檔名。它存在的目的是讓代理不必親自去看 —— 那要貴得多。**從不開啟，從不讀取。** |

### 記住 —— 當時在做什麼，以及為什麼

| | |
|---|---|
| **工作狀態** | `STATE.md` —— 此刻正在進行的工作，於工作階段開始時注入，讓上下文壓縮不再把它抹掉。 |
| **工作階段紀錄** | `.chamnan/sessions/` 下每次一份。**只有未完成的部分**會進入下一次；乾淨收尾的工作階段什麼也不注入。 |
| **記憶** | `decisions/`、`lessons/`、`rules/`。規則是長期限制，因此每次都擺在代理面前；決策與教訓只提供標題，標題看來相關時才被讀取。 |
| **未結線索** | 仍在進行中的工作線，附帶該線索已觸及哪些檔案的歷史 —— 檔案改名後依然跟得上。 |

### 重用 —— 已經解決過一次的事

| | |
|---|---|
| **操作程序** | 代理遇到複雜或重複的事情時**自己寫下**的技能。這不是隨附的現成程式庫，而是一套機制。 |
| **工具** | 發現同一個暫時腳本又被寫出來時，提議把它留下，並在你動手寫新腳本之前先推薦它。 |
| **工作流程** | 發現同一組指令在多個彼此獨立的日子以相同順序執行時，提議把這個序列記下來。 |

### 沉澱 —— 儲存庫對自己的認識

| | |
|---|---|
| **里程碑** | 為數不多、真正改變了儲存庫形狀的變更：什麼移動了、為什麼值得、影響了哪些區域。 |
| **候選項** | 偵測到的重複指令序列，一律擱置**等人確認**。沒有任何東西會被自動提升。 |
| **環境** | 宣告 production 或 staging 是什麼、有哪些禁忌，並在宣告變舊時提醒你。 |
| **報告** | 工作區裡存了什麼、是否真的取得到，以及你儲存庫的每輪上下文如何變化。是你自己的數字，不是我們的。 |

重複的工程勞動沉澱為可重用的儲存庫知識 —— **不是訓練模型，也不是取代開發者。** 它是一種保存工作的機制，否則那些工作只存在於做過它的人腦中。

## 指令

全部可從命令列呼叫，代理也會自行呼叫。

| | |
|---|---|
| `chamnan-map` | 產生並更新索引 |
| `chamnan-report` | 工作區存了什麼，每輪上下文如何變化 |
| `chamnan-impact` | 誰相依於這個檔案，哪些測試涵蓋它 |
| `chamnan-timeline` | 這個檔案先前經歷過什麼 |
| `chamnan-peek` | 在不把大檔案讀進上下文的前提下說清它裡面有什麼 |
| `chamnan-promote` | 把腳本留存為本儲存庫的常備工具 |
| `chamnan-candidates` | 檢視、確認或否決系統偵測到的重複行為 |
| `chamnan-env` | 宣告環境及其禁忌，並檢查宣告是否仍然新鮮 |
| `chamnan-age` | 已存知識從哪裡開始變舊 |

以及可在工作階段中呼叫的技能： `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## 它寫什麼，寫在哪裡

全部位於 `.chamnan/`，是普通的 markdown 與 JSON。可讀、可手改、可隨時刪除而不影響任何東西。

| | |
|---|---|
| `MAP.md` | 有什麼，以及什麼相依於什麼 |
| `STATE.md` | 此刻正在做什麼 |
| `sessions/` | 上一段工作停在哪裡 |
| `memory/` | 決策、教訓與長期規則 |
| `threads/` | 仍未結束的工作線 |
| `skills/` · `tools/` | 值得留下的程序與腳本 |
| `milestones.md` | 改變了儲存庫形狀的那些變更 |
| `config.json` | 各部分的開關，以及注入工作階段那段內容的位元組上限 |

**`.chamnan/` 之外唯一的寫入**，是一個可選的 Git pre-commit 掛鉤，用來讓索引跟上程式碼 —— 只有你同意才會安裝，而且可以移除。

**代理並沒有在學習。** 沒有任何訓練，沒有任何東西留在這個目錄之外，下一次依然從零開始 —— 只是從零開始*在一個能自我說明的儲存庫裡*。連續性在產出物裡，不在模型裡。

## 安全

| | |
|---|---|
| **執行時不發出網路呼叫** | 一次也沒有。不需要 API key，沒有任何東西被送往別處。 |
| **不改寫你的原始碼** | 它只報告，不修改。索引複製你已經寫好的註解，而不是自行編造；沒有註解的檔案會被列出名字，交給你去補。 |
| **沒有常駐程式，沒有背景工作** | 沒有常駐行程，沒有資料庫，沒有嵌入模型 —— 只有 Python 標準函式庫。 |
| **憑證先被過濾** | 凡是要寫下或注入工作階段的內容都先經過憑證過濾器：保留變數*名稱*，不保留值；而這個過濾器達不到的上限，就寫在英文 README 中它自己的數字旁邊。 |
| **一個已安裝的外掛能對你做什麼** | 英文 README 中有完整說明，包括 chamnan 在哪一環切斷了外洩鏈條。 |

## 系統需求

Claude Code · Python · Git · macOS、Linux 或 Windows

此外別無所需，沒有要額外安裝的相依套件。Python 的最低版本寫在 [README › Requirements](../../README.md#requirements) 中 —— 本頁不寫數字，因為數字正是會變的東西。

## 關閉或解除安裝

可在 `.chamnan/config.json` 中逐項關閉 · 可在單一儲存庫內停用 · 可整機解除安裝外掛 · 可隨時刪除 `.chamnan/` 而不影響任何東西 —— 詳細步驟見 [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
