# chamnan — 저장소가 스스로를 알게 한다

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> 이 페이지에는 의도적으로 숫자를 넣지 않았습니다. 모든 측정값은 영문 README에 있고 릴리스마다 바뀌지만, 이 페이지는 바뀌지 않습니다. → [Evidence](../../README.md#evidence)

## 이것은 무엇인가

Claude Code 플러그인입니다. 파일을 하나씩 훑는 대신 agent가 읽을 색인을 저장소에 만들고, 작업하면서 쌓인 엔지니어링 맥락 — 작업 상태, 세션 기록, 결정의 이유, 매번 다시 유도하게 되는 절차 — 을 남깁니다.

기록되는 것은 모두 코드 옆에 커밋되는 평범한 markdown입니다. 실행 중 네트워크를 호출하지 않고, 데이터베이스도 데몬도 embedding 모델도 없습니다. Python 표준 라이브러리만 씁니다.

## 무엇을 해결하는가

세션이 새로 시작될 때마다, 또는 컨텍스트가 압축될 때마다 agent가 코드베이스에 대해 알아낸 것은 사라지고 다시 grep부터 시작합니다.

chamnan은 그 재발견이 아예 일어나지 않게 합니다. 색인은 세션이 시작될 때 건네지고, 비용은 한도 없는 파일 읽기가 아니라 한도가 정해진 숫자입니다.

## 설치

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

새 세션을 열고 저장소마다 한 번 `/chamnan:bootstrap`을 실행하세요.

## 설치 전에 읽어 주세요

**chamnan은 반복해서 돌아오는 주 작업 폴더에 맞습니다.** 하는 일이 모두 먼저 쓰고 이후 세션에서 회수하는 구조라, 한 번만 여는 저장소에서는 비용만 치르고 돌려받는 것이 없습니다.

**보고할 뿐 코드를 고치지 않습니다.** 색인은 이미 써 둔 주석을 옮길 뿐 대신 지어내지 않습니다. 주석이 없는 파일은 이름을 짚어 주니 직접 채우면 됩니다.

**한계는 측정되어 적혀 있습니다.** 핵심 기능에 불리한 측정 결과와, 측정한 뒤 만들지 않기로 한 기능까지 영문 README의 Evidence에 있습니다.

## 자세한 내용은 어디에

| | |
|---|---|
| 모든 숫자와 그 측정 방법 | [README › Evidence](../../README.md#evidence) |
| 회귀 테스트 모음 — 직접 실행할 수 있습니다 | [`tests/run_tests.py`](../../tests/run_tests.py) |
| 릴리스마다 무엇을 왜 바꿨는지 | [CHANGELOG.md](../../CHANGELOG.md) |
| 전체 | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
