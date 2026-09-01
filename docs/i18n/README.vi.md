# chamnan — để kho mã tự biết về chính nó

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Trang này cố ý không có con số nào. Mọi kết quả đo đều nằm trong README tiếng Anh và thay đổi theo mỗi bản phát hành; trang này thì không. → [Evidence](../../README.md#evidence)

## Đây là gì

Một plugin cho Claude Code. Nó dựng một chỉ mục của kho mã để agent đọc thay vì quét từng tệp, và giữ lại bối cảnh kỹ thuật tích lũy trong lúc làm việc — trạng thái công việc, ghi chép phiên làm việc, lý do đằng sau các quyết định, và những quy trình bạn phải suy ra lại mỗi lần.

Mọi thứ nó ghi ra đều là markdown thuần được commit cạnh mã nguồn. Không gọi mạng khi chạy, không cơ sở dữ liệu, không tiến trình nền, không mô hình embedding — chỉ thư viện chuẩn của Python.

## Nó giải quyết điều gì

Mỗi phiên mới, hoặc mỗi lần ngữ cảnh bị nén, những gì agent đã hiểu về mã nguồn của bạn biến mất, và nó quay lại grep từ đầu.

chamnan khiến việc khám phá lại đó không cần xảy ra: chỉ mục được trao ngay khi phiên bắt đầu, với chi phí là một con số có giới hạn đã biết thay vì số lần đọc tệp không giới hạn.

## Cài đặt

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Mở một phiên mới, rồi chạy `/chamnan:bootstrap` một lần cho mỗi kho mã.

## Đọc trước khi cài

**chamnan hợp với một thư mục chính mà bạn quay lại làm việc nhiều lần.** Mọi thứ nó làm đều là trả trước rồi thu lại ở các phiên sau — với một kho mã bạn chỉ mở một lần, bạn đã trả toàn bộ mà không thu được gì.

**Nó báo cáo, không sửa mã của bạn.** Chỉ mục sao chép những chú thích bạn đã viết, không tự bịa ra. Tệp không có chú thích sẽ được nêu tên để bạn tự bổ sung.

**Giới hạn của nó đã được đo và ghi lại**, kể cả những kết quả đo bất lợi cho chính tính năng cốt lõi của nó.

## Chi tiết nằm ở đâu

| | |
|---|---|
| Mọi con số, và cách đo ra chúng | [README › Evidence](../../README.md#evidence) |
| Bộ kiểm thử hồi quy — bạn tự chạy được | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Mỗi bản phát hành đã đổi gì, và vì sao | [CHANGELOG.md](../../CHANGELOG.md) |
| Toàn bộ | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
