# chamnan — 让仓库了解它自己

<sub>[🇬🇧 English](../../README.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> 本页刻意不含任何数字。所有测量结果都在英文 README 中，且每次发布都会变化；本页不会。→ [Evidence](../../README.md#evidence)

## 这是什么

一个 Claude Code 插件。它为仓库建立索引供 agent 阅读，取代逐个扫描文件；并保留你工作过程中积累的工程上下文——工作状态、会话记录、决策背后的理由，以及那些你每次都要重新推导的操作步骤。

它写下的一切都是提交在代码旁边的普通 markdown。运行时不发起任何网络请求，没有数据库，没有守护进程，没有 embedding 模型——只用 Python 标准库。

## 它解决什么问题

每开一个新会话，或每次上下文被压缩，agent 对你代码库的全部理解就消失了，然后它又回去逐个 grep 文件。

chamnan 让这种重新发现不必发生：会话开始时索引就已交到手上，代价是一个有上界的已知数字，而不是无上界的文件读取。

## 安装

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

开一个新会话，每个仓库运行一次 `/chamnan:bootstrap`。

## 安装前请读这一段

**chamnan 适合你反复回来工作的那个主目录。** 它做的每件事都是先付出、之后每个会话收回——对于只打开一次的仓库，你付出了全部却什么也收不回。

**它只报告，不改写你的代码。** 索引复制你已经写下的注释，不会替你编造。没有注释的文件会被逐一列出，由你自己补。

**它的局限都经过测量并写了下来**，包括那些与它自身核心功能相悖的测量结果，以及测量之后决定不做的功能——都在英文 README 的 Evidence 一节。

## 细节在哪里

| | |
|---|---|
| 每个数字，以及它是怎么测出来的 | [README › Evidence](../../README.md#evidence) |
| 回归测试套件——你可以自己跑 | [`tests/run_tests.py`](../../tests/run_tests.py) |
| 每个版本改了什么，为什么 | [CHANGELOG.md](../../CHANGELOG.md) |
| 全部内容 | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
