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

<!-- generated: build_sections.py -->

## Toàn bộ tính năng

Bốn nhóm năng lực. Mọi thứ trong bảng dưới đây đều đang chạy thật trong bản phát hành hiện tại. Từng phần có thể tắt riêng trong `.chamnan/config.json`, và không phần nào phụ thuộc phần nào.

### Hiểu — có những gì, và cái gì nối với cái gì

| | |
|---|---|
| **Chỉ mục** | `MAP.md` — mỗi tệp một dòng, sinh ra từ chính mã nguồn. Tác nhân đọc chỉ mục rồi grep phần chi tiết cần thiết, thay vì đi khắp cây thư mục. |
| **Ảnh hưởng** | Ai phụ thuộc vào tệp này, và bài kiểm thử nào phủ nó. Import của chính tệp đã nằm ở đầu tệp; thứ tốn công tìm là chiều ngược lại — hãy grep đường dẫn trước khi sửa. |
| **Mô hình dữ liệu** | Tên bảng và tên model kèm một dòng mô tả, rút từ DDL, migration và ORM, chứ không phải một bản đổ toàn bộ schema. Chỉ xuất hiện khi kho có định nghĩa. |
| **Bề mặt API** | Phương thức, đường dẫn và handler, lấy từ route decorator, tài liệu OpenAPI và định nghĩa dịch vụ `.proto` — chứ không phải cả bản đặc tả. |
| **Cấu hình** | Tên các biến môi trường mà kho đọc. **Chỉ tên, không bao giờ ghi giá trị** — và cảnh báo nếu `.env` chưa được gitignore. |
| **Triển khai** | Thứ thật sự đang chạy, đọc từ manifest của Kubernetes, Ansible, Compose, Helm và CI: loại và tên, image, vai trò, pipeline. Secret chỉ đóng góp cái tên, không gì bên dưới. |
| **Tài liệu không phải mã nguồn** | Giấy tờ đã quét, bản xuất, kho nén — chỉ báo số lượng, kích thước và phần mở rộng chiếm đa số. Nó tồn tại để tác nhân khỏi phải tự đi xem, việc vốn tốn kém hơn nhiều. **Không bao giờ mở, không bao giờ đọc.** |

### Nhớ — đang làm gì, và vì sao

| | |
|---|---|
| **Trạng thái công việc** | `STATE.md` — việc đang làm ngay lúc này, được nạp vào lúc mở phiên để việc nén ngữ cảnh không xoá mất nó. |
| **Bản ghi phiên** | Mỗi phiên một bản trong `.chamnan/sessions/`. **Chỉ phần chưa xong** mới sang phiên kế tiếp; một phiên kết thúc gọn gàng thì không nạp gì cả. |
| **Bộ nhớ** | `decisions/`, `lessons/`, `rules/`. Quy tắc là ràng buộc thường trực nên luôn được đặt trước mặt tác nhân mỗi phiên; quyết định và bài học chỉ góp tiêu đề, và được đọc khi tiêu đề tỏ ra liên quan. |
| **Luồng còn mở** | Những mạch công việc chưa xong, kèm lịch sử mạch đó đã chạm vào những tệp nào — và vẫn theo được sau khi tệp bị đổi tên. |

### Dùng lại — thứ đã giải một lần

| | |
|---|---|
| **Quy trình** | Những kỹ năng mà tác nhân **tự viết** khi gặp việc phức tạp hoặc lặp lại. Không phải một thư viện đóng gói sẵn, mà là một cơ chế. |
| **Công cụ** | Nhận ra cùng một script tạm lại được viết ra lần nữa, và đề nghị giữ nó lại — rồi nhắc đến nó trước khi bạn kịp viết script mới. |
| **Chuỗi thao tác** | Nhận ra cùng một loạt lệnh chạy theo cùng thứ tự vào những ngày tách biệt, và đề nghị ghi chuỗi đó lại. |

### Tích luỹ — điều kho tự học được về chính nó

| | |
|---|---|
| **Cột mốc** | Vài thay đổi hiếm hoi đã đổi hình dạng của kho: cái gì đã dời, vì sao đáng làm, chạm vào những vùng nào. |
| **Ứng viên** | Chuỗi lệnh lặp lại được phát hiện sẽ **luôn chờ người xác nhận**. Không có gì được thăng cấp tự động. |
| **Môi trường** | Khai báo production hay staging là gì, có điều gì cấm, rồi cảnh báo khi lời khai báo ấy đã cũ. |
| **Báo cáo** | Không gian làm việc đang giữ gì, có thật sự với tới được không, và ngữ cảnh mỗi lượt của kho bạn đã thay đổi ra sao. Là con số của bạn, không phải của chúng tôi. |

Công sức kỹ thuật lặp đi lặp lại trở thành tri thức dùng lại được của kho — **không phải huấn luyện mô hình, cũng không phải tự động hoá lập trình viên.** Nó là cơ chế giữ lại phần việc mà nếu không thì chỉ tồn tại trong đầu người đã làm.

## Lệnh

Tất cả đều gọi được từ shell, và chính tác nhân cũng gọi chúng.

| | |
|---|---|
| `chamnan-map` | tạo và cập nhật chỉ mục |
| `chamnan-report` | không gian làm việc giữ gì, và ngữ cảnh mỗi lượt đổi ra sao |
| `chamnan-impact` | ai phụ thuộc vào tệp này, bài kiểm thử nào phủ nó |
| `chamnan-timeline` | tệp này đã trải qua những gì |
| `chamnan-peek` | nói rõ bên trong một tệp lớn có gì mà không nạp nó vào ngữ cảnh |
| `chamnan-promote` | giữ một script lại thành công cụ thường trực của kho |
| `chamnan-candidates` | xem, xác nhận hoặc bác bỏ những lặp lại đã phát hiện |
| `chamnan-env` | khai báo môi trường và điều cấm của nó, rồi kiểm tra khai báo còn mới không |
| `chamnan-age` | tri thức đã lưu bắt đầu cũ đi từ chỗ nào |

Và các kỹ năng gọi được trong phiên: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Nó ghi gì, và ghi ở đâu

Tất cả nằm trong `.chamnan/`, là markdown và JSON thường. Đọc được, sửa tay được, xoá lúc nào cũng không hỏng gì.

| | |
|---|---|
| `MAP.md` | có những gì, và cái gì phụ thuộc cái gì |
| `STATE.md` | đang làm gì ngay lúc này |
| `sessions/` | đợt làm việc trước dừng ở đâu |
| `memory/` | quyết định, bài học và quy tắc thường trực |
| `threads/` | những mạch công việc còn mở |
| `skills/` · `tools/` | quy trình và script đáng giữ |
| `milestones.md` | những thay đổi đã đổi hình dạng của kho |
| `config.json` | bật tắt từng phần, và trần dung lượng của khối nạp vào phiên |

**Lần ghi duy nhất bên ngoài `.chamnan/`** là một Git pre-commit hook tuỳ chọn, giữ cho chỉ mục theo kịp cây mã — chỉ cài khi bạn đồng ý, và gỡ được.

**Tác nhân không học gì cả.** Không có gì được huấn luyện, không có gì đọng lại ngoài thư mục này, và phiên sau vẫn bắt đầu từ số không — chỉ là bắt đầu từ số không *trong một kho biết tự giải thích*. Tính liên tục nằm ở các tệp sinh ra, không nằm ở mô hình.

## An toàn

| | |
|---|---|
| **Không gọi mạng khi chạy** | Không một lần nào. Không cần API key, không có gì được gửi đi đâu. |
| **Không viết lại mã nguồn của bạn** | Nó báo cáo, chứ không sửa. Chỉ mục chép lại chú thích bạn đã viết, chứ không bịa ra; tệp không có chú thích thì được nêu tên để bạn tự bổ sung. |
| **Không daemon, không việc chạy nền** | Không tiến trình thường trú, không cơ sở dữ liệu, không mô hình embedding — chỉ thư viện chuẩn của Python. |
| **Bí mật được lọc trước** | Mọi thứ sắp được ghi ra hay nạp vào phiên đều đi qua bộ lọc bí mật: giữ *tên* biến, bỏ giá trị. Còn giới hạn mà bộ lọc ấy không với tới thì được ghi ngay cạnh con số của nó trong README tiếng Anh. |
| **Một plugin đã cài có thể làm gì với bạn** | README tiếng Anh nói đủ, kể cả chỗ chamnan cắt đứt chuỗi rò rỉ. |

## Dùng được với những gì

chamnan là văn bản và Python thư viện chuẩn. Không có gì trong chỉ mục thuộc về một nhà cung cấp, một trình soạn thảo hay một hệ điều hành cụ thể.

| | |
|---|---|
| **Mô hình nào cũng được, nhà cung cấp nào cũng được** | Chỉ mục là văn bản thuần và được gửi kèm làm ngữ cảnh. Mô hình chỉ quyết định gửi bao nhiêu là đáng, không bao giờ quyết định cái gì đi đâu. Chỉnh kích thước bằng `--model`, `--window` hoặc `--profile`. Đổi mô hình không phải cài lại thứ gì. |
| **macOS, Linux, Windows, WSL** | Cùng một plugin ở mọi nơi, chỉ dùng thư viện chuẩn, không có gì phải cài. Trên macOS và Linux các lệnh chạy thẳng. Trên Windows, shell không chạy được tệp lệnh không có phần mở rộng, nên bên cạnh mỗi lệnh và mỗi hook có một tệp `.cmd` được sinh ra; chúng đi kèm plugin và CI chạy chính những tệp đó. WSL hoạt động như Linux. |
| **Nhiều tác nhân, một chỉ mục** | Claude Code nhận khối qua một hook phiên và không có tệp nào được ghi vào dự án của bạn. Gemini CLI cũng có hook phiên thật sự. Các tác nhân khác nhận một tệp tại đường dẫn mà tác nhân đó đọc, và những tác nhân đọc cùng một đường dẫn thì dùng chung tệp, thay vì mỗi bên giữ một bản sao dần lệch nhau. |
| **Hermes Agent** | Hermes đồng thời là lớp điều khiển chỉ huy các tác nhân lập trình khác, nên một kho được cấu hình cho nó thường có nghĩa là nhiều công cụ cùng đọc một chỉ mục. Nó tìm tệp hướng dẫn dự án theo thứ tự cố định và lấy tệp đầu tiên tìm thấy; chamnan ghi đúng tệp đứng đầu thứ tự ấy, chỉnh kích thước theo giới hạn mà chính Hermes công bố, và từ chối ghi đè tệp không phải do nó tạo ra. |

## Cách cài đặt

Đi lối nào chỉ phụ thuộc một điều: công cụ đó có hook phiên hay không.

| | |
|---|---|
| **Claude Code** | Cài như một plugin rồi chạy lệnh khởi tạo một lần trong kho. Không có gì được ghi vào mã của bạn, và từ đó mỗi phiên bắt đầu với chỉ mục đã nằm sẵn trong ngữ cảnh. |
| **Mọi thứ còn lại, kể cả Hermes** | Trước hết hãy hỏi chamnan phát hiện được gì, rồi cho biết cần ghi cho tác nhân nào. Khi hình dạng kho thay đổi thì dựng lại chỉ mục và ghi tệp lần nữa; một hook Git tùy chọn làm cả hai việc lúc commit. Không cần Claude Code: đây là những lệnh bình thường, còn plugin chỉ là một con đường chuyển giao, không phải sản phẩm. Nếu không nêu tên tác nhân, nó in ra thứ đã phát hiện cùng lệnh phù hợp, và để bạn quyết định. Nó không bao giờ ghi theo phỏng đoán. |

Tên lệnh, danh sách đầy đủ các tác nhân và tệp mà mỗi tác nhân nhận được đều nằm trong README tiếng Anh, nơi chứa mọi chi tiết gắn với phiên bản.


## Yêu cầu

Claude Code · Python · Git · macOS, Linux hoặc Windows

Ngoài ra không cần gì thêm, không có phụ thuộc nào phải cài. Phiên bản Python tối thiểu nằm trong [README › Requirements](../../README.md#requirements) — trang này không ghi con số, vì con số chính là thứ sẽ đổi.

## Tắt hoặc gỡ bỏ

Tắt từng phần trong `.chamnan/config.json` · dừng trong một kho · gỡ hẳn plugin · xoá `.chamnan/` bất cứ lúc nào mà không hỏng gì — các bước chi tiết ở [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
