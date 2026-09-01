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

<!-- generated: build_sections.py -->

## 全部功能

四类能力。下表所列均已在当前版本中实际运行。每一部分都可在 `.chamnan/config.json` 中单独关闭，彼此之间没有依赖。

### 理解 —— 有什么，以及什么与什么相连

| | |
|---|---|
| **索引** | `MAP.md` —— 每个文件一行，由代码生成。代理读索引，再按需 grep 细节，而不必遍历整棵目录树。 |
| **影响面** | 谁依赖这个文件，哪些测试覆盖它。文件自身的 import 就写在开头，真正费力查找的是反向边 —— 改动前先 grep 一下路径。 |
| **数据模型** | 表名与模型名，各配一行说明，取自 DDL、迁移脚本和 ORM 模型，而不是整份 schema 转储。仓库中确有定义时才会出现。 |
| **API 表面** | 方法、路径与处理函数，取自路由装饰器、OpenAPI 文档和 `.proto` 服务定义，而不是整份规格。 |
| **配置** | 仓库读取的环境变量名。**只有名字，绝不记录值** —— 并会在 `.env` 未被 gitignore 时发出警告。 |
| **部署** | 实际运行的东西，读自 Kubernetes、Ansible、Compose、Helm 与 CI 清单：类型与名称、镜像、角色、流水线。Secret 只贡献名字，其下内容一概不取。 |
| **非源码资料** | 扫描件、导出文件、压缩包等，只报告数量、大小与主要扩展名。它存在的目的是让代理不必亲自去看 —— 那要贵得多。**从不打开，从不读取。** |

### 记住 —— 当时在做什么，以及为什么

| | |
|---|---|
| **工作状态** | `STATE.md` —— 此刻正在进行的工作，在会话开始时注入，使上下文压缩不再将其抹去。 |
| **会话记录** | `.chamnan/sessions/` 下每次会话一份。**只有未完成的部分**会进入下一次会话；干净收尾的会话什么也不注入。 |
| **记忆** | `decisions/`、`lessons/`、`rules/`。规则是长期约束，因此每次会话都摆在代理面前；决策与教训只提供标题，标题看起来相关时才被读取。 |
| **未结线索** | 仍在进行中的工作线，附带该线索已触及哪些文件的历史 —— 文件改名后依然跟得上。 |

### 复用 —— 已经解决过一次的事

| | |
|---|---|
| **操作流程** | 代理在遇到复杂或重复的事情时**自己写下**的技能。这不是随包附送的现成库，而是一套机制。 |
| **工具** | 发现同一个临时脚本被再次写出来时，提出把它留下，并在你动手写新脚本之前先推荐它。 |
| **工作流** | 发现同一组命令在多个彼此独立的日子里以相同顺序运行时，提出把这个序列记下来。 |

### 沉淀 —— 仓库对自己的认识

| | |
|---|---|
| **里程碑** | 为数不多、真正改变了仓库形状的变更：什么移动了、为什么值得、影响了哪些区域。 |
| **候选项** | 检测到的重复命令序列，一律搁置**等人确认**。没有任何东西会被自动提升。 |
| **环境** | 声明 production 或 staging 是什么、有哪些禁忌，并在声明变旧时提醒你。 |
| **报告** | 工作区里存了什么、是否真的取得到，以及你仓库的每轮上下文如何变化。是你自己的数字，不是我们的。 |

重复的工程劳动沉淀为可复用的仓库知识 —— **不是训练模型，也不是取代开发者。** 它是一种保存工作的机制，否则那些工作只存在于做过它的人脑子里。

## 命令

全部可从命令行调用，代理也会自行调用。

| | |
|---|---|
| `chamnan-map` | 生成并更新索引 |
| `chamnan-report` | 工作区存了什么，每轮上下文如何变化 |
| `chamnan-impact` | 谁依赖这个文件，哪些测试覆盖它 |
| `chamnan-timeline` | 这个文件此前经历过什么 |
| `chamnan-peek` | 在不把大文件读进上下文的前提下说清它里面有什么 |
| `chamnan-promote` | 把脚本留存为本仓库的常备工具 |
| `chamnan-candidates` | 查看、确认或否决系统检测到的重复行为 |
| `chamnan-env` | 声明环境及其禁忌，并检查声明是否仍然新鲜 |
| `chamnan-age` | 已存知识从哪里开始变旧 |

以及可在会话中调用的技能： `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## 它写什么，写在哪里

全部位于 `.chamnan/`，是普通的 markdown 与 JSON。可读、可手改、可随时删除而不影响任何东西。

| | |
|---|---|
| `MAP.md` | 有什么，以及什么依赖什么 |
| `STATE.md` | 此刻正在做什么 |
| `sessions/` | 上一段工作停在哪里 |
| `memory/` | 决策、教训与长期规则 |
| `threads/` | 仍未结束的工作线 |
| `skills/` · `tools/` | 值得留下的流程与脚本 |
| `milestones.md` | 改变了仓库形状的那些变更 |
| `config.json` | 各部分的开关，以及注入会话的那段内容的字节上限 |

**`.chamnan/` 之外唯一的写入**，是一个可选的 Git pre-commit 钩子，用于让索引跟上代码 —— 只有你同意才会安装，并且可以移除。

**代理并没有在学习。** 没有任何训练，没有任何东西留在这个目录之外，下一次会话依然从零开始 —— 只是从零开始*在一个能自我说明的仓库里*。连续性在产物里，不在模型里。

## 安全

| | |
|---|---|
| **运行时不发起网络调用** | 一次也没有。不需要 API key，没有任何东西被发往别处。 |
| **不改写你的源码** | 它只报告，不修改。索引复制你已经写好的注释，而不是自行编造；没有注释的文件会被列出名字，交给你去补。 |
| **没有守护进程，没有后台工作** | 没有常驻进程，没有数据库，没有嵌入模型 —— 只有 Python 标准库。 |
| **凭据先被过滤** | 凡是要写下或注入会话的内容都先经过凭据过滤器：保留变量*名*，不保留值；而这个过滤器达不到的上限，就写在英文 README 中它自己的数字旁边。 |
| **一个已安装的插件能对你做什么** | 英文 README 中有完整说明，包括 chamnan 在哪一环切断了外泄链条。 |

## 系统要求

Claude Code · Python · Git · macOS、Linux 或 Windows

此外别无所需，没有要额外安装的依赖。Python 的最低版本写在 [README › Requirements](../../README.md#requirements) 中 —— 本页不写数字，因为数字正是会变的东西。

## 关闭或卸载

可在 `.chamnan/config.json` 中逐项关闭 · 可在单个仓库内停用 · 可整机卸载插件 · 可随时删除 `.chamnan/` 而不影响任何东西 —— 详细步骤见 [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
