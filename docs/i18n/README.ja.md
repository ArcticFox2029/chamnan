# chamnan — リポジトリに自分自身を把握させる

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> このページには意図的に数値を載せていません。測定結果はすべて英語版 README にあり、リリースごとに変わります。このページは変わりません。→ [Evidence](../../README.md#evidence)

## これは何か

Claude Code のプラグインです。ファイルを一つずつ走査する代わりに agent が読むためのインデックスをリポジトリに作り、作業のなかで積み上がった技術的な文脈——作業状態、セッションの記録、判断の理由、毎回導き直している手順——を残します。

書き出されるものはすべて、コードの隣にコミットされる普通の markdown です。実行時にネットワークを呼ばず、データベースもデーモンも embedding モデルもありません。Python の標準ライブラリだけで動きます。

## 何を解決するのか

セッションが新しくなるたび、あるいはコンテキストが圧縮されるたびに、agent がそのコードベースについて理解していたことは失われ、また grep からやり直しになります。

chamnan はその再発見を起こさせません。インデックスはセッション開始時に手渡され、費用は上限のない読み込みではなく、上限のわかっている数値です。

## インストール

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

新しいセッションを開き、リポジトリごとに一度 `/chamnan:bootstrap` を実行してください。

## 入れる前に読んでください

**chamnan が向いているのは、何度も戻ってくる主要なフォルダです。** 行うことはすべて先に払って後のセッションで回収する形なので、一度しか開かないリポジトリでは払っただけで何も戻りません。

**報告はしますが、コードは書き換えません。** インデックスはあなたが書いたコメントを写すだけで、代わりに作文はしません。コメントのないファイルは名前を挙げるので、ご自身で足してください。

**限界は測定されて書かれています。** 中心的な機能に不利な測定結果も、測定したうえで作らなかった機能も含めて、英語版 README の Evidence にあります。

## 詳細はどこにあるか

| | |
|---|---|
| すべての数値と、その測り方 | [README › Evidence](../../README.md#evidence) |
| 回帰テスト一式 — ご自身で実行できます | [`tests/run_tests.py`](../../tests/run_tests.py) |
| 各リリースで何を、なぜ変えたか | [CHANGELOG.md](../../CHANGELOG.md) |
| すべて | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
