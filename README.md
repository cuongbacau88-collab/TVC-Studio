# PayOS auto top-up

Để bật nạp xu tự động, cấu hình các biến môi trường trên Railway:

- `PAYOS_CLIENT_ID`
- `PAYOS_API_KEY`
- `PAYOS_CHECKSUM_KEY`
- `PAYOS_RETURN_URL=https://tvcstudioai.info/app#wallet`
- `PAYOS_CANCEL_URL=https://tvcstudioai.info/app#wallet`

Đặt webhook PayOS về `https://tvcstudioai.info/api/payos/webhook`. Webhook được kiểm tra chữ ký và cộng xu idempotent theo `orderCode`, nên PayOS gửi lại cùng một webhook cũng không cộng trùng.

`returnUrl` chỉ đưa khách quay lại ví và hiển thị trạng thái đang xác nhận. Xu chỉ được cộng sau khi backend xác thực webhook, đối chiếu `orderCode`, số tiền và giao dịch pending trong database. Admin sync/approve chỉ là fallback cho giao dịch cần đối soát.

Worker giới hạn file output ở 2 GB mặc định. Có thể thay đổi bằng biến môi trường `WORKER_MAX_OUTPUT_MB`; giới hạn được kiểm tra cả theo `Content-Length` và kích thước stream thực tế.
# TVC Studio AI Business V2.1

Web kinh doanh AI video có backend thật, database SQLite, tài khoản, credits, job queue, admin và Worker API.

## Tính năng đã chạy
- Landing page
- Đăng ký / đăng nhập
- Session cookie HttpOnly
- 30 credits miễn phí cho tài khoản mới
- Upload ảnh + motion thật
- Tạo job và trừ credits
- Hàng đợi Waiting / Running / Done / Failed
- Download output
- Hoàn credits tự động nếu worker báo lỗi
- Yêu cầu nạp credits
- PayOS webhook tự động settlement topup và ghi credit ledger
- Admin sync/duyệt topup pending cho trường hợp cần đối soát
- Admin cộng/trừ credits thủ công
- Admin xem users / jobs / stats
- Worker API để RTX 5090 claim job
- Worker demo để test end-to-end

## Ghi chú production
- Railway cần giữ database trong `PERSISTENT_DATA_DIR` hoặc `RAILWAY_VOLUME_MOUNT_PATH`.
- Không đưa `PAYOS_API_KEY` hoặc `PAYOS_CHECKSUM_KEY` xuống frontend hay ghi vào log.
- Chưa email/OTP/reset password
- Chưa rate limit/WAF
- Chưa HTTPS/domain reverse proxy
- Chưa nối workflow Wan Animate 2 thật vì cần API JSON của workflow ComfyUI cụ thể

## Chạy Windows
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set ADMIN_PASSWORD=MatKhauAdminRatManh
set WORKER_TOKEN=mot-token-worker-rat-dai
uvicorn app:app --host 0.0.0.0 --port 8000
```

Mở:
- Trang chủ: http://127.0.0.1:8000
- Dashboard: http://127.0.0.1:8000/app
- Admin: http://127.0.0.1:8000/admin

## Chạy Ubuntu
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_PASSWORD='MatKhauAdminRatManh'
export WORKER_TOKEN='mot-token-worker-rat-dai'
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Admin mặc định khi test local
Email: `cuongtv.bx92@gmail.com`
Password mặc định: `Cuong123@`

**Phải đổi mật khẩu qua biến môi trường trước khi public website.**

## Test job queue không cần GPU
Mở terminal thứ hai:
```bash
python worker_demo.py
```

Worker demo sẽ lấy motion upload của khách làm output giả để kiểm tra:
upload → queue → progress → done → download.

## Nối RTX 5090 + ComfyUI
Dùng `worker_comfyui.py` làm khung.

Cần export workflow ComfyUI bằng chế độ API JSON và đặt:
`workflows/wan_animate_2_api.json`

Sau đó map các node input:
- ảnh nhân vật
- motion video
- prompt

Luồng cuối cùng:
Website → SQLite Queue → RTX5090 Worker → ComfyUI → Wan Animate 2 → MP4 → Website.

## Cấu trúc
```
motionhub_business_v2/
├─ app.py
├─ worker_demo.py
├─ worker_comfyui.py
├─ requirements.txt
├─ .env.example
├─ static/
│  ├─ index.html
│  ├─ app.html
│  ├─ admin.html
│  ├─ styles.css
│  ├─ app.js
│  └─ admin.js
├─ workflows/
└─ data/
   ├─ uploads/
   ├─ outputs/
   └─ motionhub.db   (tự tạo khi chạy)
```


## V2.1 - Trang chủ chọn model
Trang `/` giờ là trang chọn model dạng card như dịch vụ AI marketplace.
Model `AI Motion Studio` đang dẫn vào dashboard thật.
Các model còn lại hiển thị `Sắp có` để không tạo job mà worker chưa hỗ trợ.

Nếu website V2 đang chạy trên Railway:
1. Upload lại toàn bộ thư mục `static/` của V2.1 lên repo GitHub.
2. Commit vào `main`.
3. Railway tự redeploy.


## V2.2 - Card có ảnh thật
- Thêm thư mục `static/images/`
- Trang chủ chọn model dùng thumbnail ảnh thật cho 6 card
- Phù hợp để cập nhật Railway chỉ bằng cách upload lại `static/`


## V2.3
Đã tích hợp logo TVC vào navbar, dashboard, trang admin, footer và favicon.


## V2.3.1
Sửa logo/brand để chữ `TVC Studio AI` luôn nằm cùng một dòng, không bị rớt chữ `AI` xuống dưới.


## V2.4 — Affiliate / Kiếm tiền
Đã thêm hệ thống referral thật:
- Mã + link giới thiệu riêng cho từng tài khoản.
- Nhập mã người giới thiệu một lần.
- Người được giới thiệu nhận +10% credits khi topup được admin duyệt.
- Hạng Bạc: 10% hoa hồng trên credits khách trực tiếp mua.
- Hạng Vàng: 15% khi doanh số trực tiếp đạt 1.000 credits.
- Hạng Vàng nhận thêm 50% override trên hoa hồng trực tiếp của affiliate cấp dưới.
- Số dư affiliate tách khỏi ví credits sử dụng dịch vụ.
- Tỷ giá rút mặc định: 1 affiliate credit = 2.500 VND.
- Tối thiểu 10 affiliate credits/lần rút.
- Admin duyệt/từ chối yêu cầu rút.
- Dashboard admin xem đối tác, doanh số, hạng và số dư.

### Lưu ý production
Affiliate hiện tính trên topup được admin duyệt. Khi nối cổng thanh toán tự động, hãy gọi cùng logic duyệt topup sau webhook thanh toán thành công.


## V2.5 — Thanh công cụ đầu trang
Đã thêm thanh công cụ cố định giống bố cục mẫu:
- Logo TVC Studio AI
- VN / EN
- Chọn Model
- Lịch Sử
- Kiếm Tiền
- Số dư + Nạp Credits
- Tài Khoản
- Mobile menu responsive

Thanh công cụ được thêm vào trang chủ, dashboard khách hàng và trang admin.

## V2.5.1 — Mobile toolbar fix
- Thanh công cụ luôn hiện trên điện thoại.
- Hàng 1: logo + TVC Studio AI + VN/EN.
- Hàng 2: Chọn Model / Lịch Sử / Kiếm Tiền / Nạp Credits / Tài Khoản.
- Hàng nút có thể vuốt ngang trên màn hình nhỏ.
- Không còn ẩn toàn bộ menu sau nút hamburger.

## V2.5.2 — Toolbar nổi khi cuộn
- Cố định thanh công cụ bằng `position: fixed`.
- Giữ toolbar luôn hiện khi vuốt xuống / cuộn trang.
- Tăng `z-index` để không bị nội dung đè lên.
- Hỗ trợ safe-area trên iPhone / in-app browser.

## V2.6 — Liquid Glass + i18n + Account menu
- Logo + TVC Studio AI được căn giữa thanh công cụ.
- Thanh công cụ dùng hiệu ứng kính mờ / liquid-glass lấy cảm hứng từ iOS.
- VN / EN hoạt động thật cho menu và các nội dung chính.
- Thêm menu Tài Khoản ngay trên toolbar: tên, email, số dư, ví, affiliate, đăng xuất.
- Mobile: logo vẫn ở giữa; hàng công cụ bên dưới vuốt ngang và luôn nổi khi cuộn.

## V2.6.1 — Mobile toolbar giống mẫu
- Hàng trên: logo + TVC Studio AI ở giữa, VN/EN góc phải.
- Hàng dưới: 5 nút chia đều toàn chiều ngang.
- Icon ở trên, chữ ở dưới.
- Nút đang chọn có viền tím glow.
- Nạp Credits hiển thị số dư + 🔥 như mẫu.
- Tài khoản dùng avatar tròn + nhãn Tài Khoản.
- Thanh luôn fixed khi vuốt xuống.
- Desktop giữ bố cục V2.6.

## V2.6.2 — Sửa Tài Khoản trên điện thoại
- Sửa lỗi bấm `Tài Khoản` trên mobile nhưng menu không hiện.
- Account popover được đưa ra ngoài vùng toolbar bị ẩn trên mobile.
- Popup hiển thị dạng glass sheet, luôn nằm trên nội dung.
- Giữ đủ: tên, email, credits, Tài khoản, Ví credits, Affiliate, Đăng xuất.

## V2.6.3 — Desktop account restyle
- Làm lại riêng phần `Tài Khoản` trên PC cho gọn và đẹp hơn.
- Thu nhỏ pill tài khoản, avatar tròn cân đối hơn, tên không bị thô.
- Đồng bộ phong cách với ô Credits.
- Tinh chỉnh popup tài khoản trên desktop để nhìn sang và dễ đọc hơn.
- Mobile giữ nguyên bản V2.6.2.

## V2.6.4 — Desktop toolbar giống mẫu
- Desktop chuyển về một hàng duy nhất.
- Thứ tự: Logo + TVC Studio AI → VN/EN → Chọn Model → Lịch Sử → Kiếm Tiền → Credits → Tài Khoản.
- Bỏ bố cục 2 tầng trên PC.
- Nút Chọn Model có viền tím glow như ảnh mẫu.
- Credits và Tài Khoản đồng bộ cùng chiều cao / bo góc.
- Mobile vẫn giữ nguyên giao diện V2.6.2.


## V3.0 — Full Liquid Glass Theme
- Đổi toàn bộ giao diện sang chủ đề liquid glass xanh / tím / hồng.
- Giảm glow khoảng 15–20% so với bản concept để chữ dễ đọc hơn.
- Đồng bộ trang chủ, dashboard, wallet, affiliate, account, admin.
- Giữ nguyên backend, job queue, credits, affiliate và worker API.
- Desktop toolbar giữ một hàng; mobile giữ toolbar 2 hàng cố định.
- Không thay logic dữ liệu / database.

## V3.1 — Clear Glass
- Giảm mạnh màu tím.
- Nền chuyển sang xanh đen trung tính.
- Glass trong hơn, ánh cyan/blue là chính, hồng chỉ làm điểm nhấn.
- Button và trạng thái active bỏ glow tím nặng.
- Desktop và mobile cùng theme.

## V3.1.1 — Thay ảnh AI Motion Studio
- Đã thay ảnh mới cho mục / card `AI Motion Studio`.
- Ảnh được resize/crop đúng kích thước asset cũ để gắn vào web ngay.
- Không đổi backend hay logic, chỉ cập nhật hình hiển thị.

## V3.1.2 — Nút Tạo Video nổi hơn + card AI Motion Studio căn lại
- Thay ảnh card `AI Motion Studio` bằng ảnh người dùng gửi.
- Căn lại bố cục card theo hướng giống mẫu hơn: ảnh lớn phía trên, phần chữ căn giữa.
- Nút `Tạo Video` đổi sang kiểu full-width, to hơn, sáng hơn và có hiệu ứng sweep + pulse.
- Mobile và desktop đều áp dụng.

## V3.1.3 — Dọn lại card AI Motion Studio
- Xóa phần dư bị khoanh đỏ trong ảnh card AI Motion Studio bằng cách crop lại ảnh preview.
- Bỏ badge `ĐANG HOẠT ĐỘNG / WAN ANIMATE 2` trên card này theo yêu cầu.
- Căn lại chiều cao vùng ảnh để card gọn hơn.


## V3.1.4 — Card AI Motion Studio hiển thị video
- Phần preview của card `AI Motion Studio` đổi từ ảnh sang video.
- Web sẽ tự load video tại: `static/videos/card_motion.mp4`
- Nếu chưa có file video, web tự fallback về ảnh `static/images/card_motion.png`
- Chỉ cần upload file mp4 preview vào đúng đường dẫn là chạy.


## V3.2 — Mirror Glass
- Đổi giao diện sang kính gương trong kiểu liquid/mirror glass.
- Viền phản chiếu trắng, blur trong, ánh cyan/xanh/hồng rất nhẹ.
- Giảm màu tím và giảm neon đặc.
- Đồng bộ card, toolbar, nút, input, account popup và mobile.
- Admin password mặc định được cập nhật theo cấu hình mới.


## V3.2.1 — Sửa khung preview video
- Căn lại khung preview của card AI Motion Studio để khớp với video hơn.
- Bỏ khoảng trống thừa phía trên và phía dưới.
- Đổi preview sang fill khung đẹp hơn bằng `object-fit: cover`.


## V3.2.2 — Video bo góc sát khung hơn + preview mirror glass rõ hơn
- Giảm padding của khung preview để video sát viền hơn.
- Tăng độ bo góc đồng bộ giữa video và khung.
- Thêm lớp highlight phản chiếu ở mép trên để khung mang cảm giác kính gương rõ hơn.
- Tăng shadow / border / glow nhẹ cho vùng preview để nổi khối hơn nhưng vẫn đồng bộ giao diện.


## V3.2.3 — Sửa viền phải preview video
- Thu hẹp padding của khung preview.
- Kéo media preview sát mép phải hơn để viền phải khớp khung.
- Tinh chỉnh lại bo góc phải/trái cho preview video.


## V3.2.4 — Bật/tắt âm thanh cho video preview
- Video vẫn autoplay ở chế độ muted để Chrome/Safari/iPhone cho phép tự chạy.
- Thêm nút `Bật âm` nổi trên video.
- Khi người dùng bấm, video được unmute và phát âm thanh nếu file MP4 có audio track.
- Bấm lần nữa để tắt âm.


## V3.3 — Bright Pastel Glass Theme
- Đổi toàn bộ giao diện sang tông sáng hơn theo ảnh mẫu: xanh pastel / lavender / hồng nhạt.
- Toolbar, card, popup, preview frame và button đều sáng hơn, mềm hơn.
- Giữ hiệu ứng glass / mirror nhưng chuyển sang cảm giác tươi sáng, trong trẻo hơn.


## V3.3.1 — Balanced Bright Glass
- Giữ nền pastel sáng nhưng tăng độ tương phản của card.
- Card chuyển sang blue-glass trong vừa phải, chữ trắng đọc rõ.
- Bỏ cảm giác trắng bệch / mờ chữ của V3.3.
- Preview ảnh/video giữ màu gốc, giảm lớp phủ làm tối hoặc xanh ảnh.


## V3.3.2 — Remove black edge on motion preview
- Xóa nền/padding gây hở viền đen ở preview card AI Motion Studio.
- Cho media phủ kín khung hơn.
- Tắt lớp overlay của preview để không lộ mép đen bên phải.


## V3.3.3 — Bấm video mở player riêng có âm thanh
- Bấm trực tiếp vào preview video sẽ mở một màn hình player nổi.
- Player có controls, phát tiếng ngay sau thao tác bấm của người dùng nếu file MP4 có audio.
- Desktop mở modal lớn; điện thoại mở gần toàn màn hình.
- Đóng bằng nút X, bấm nền ngoài hoặc phím Esc.
- Khi đóng player, preview nhỏ tiếp tục chạy muted.


## V3.3.4 — Thêm phần giới thiệu
- Thêm khối giới thiệu trên trang chủ ngay trước danh sách model.
- Nội dung giới thiệu dịch vụ AI Motion Studio.
- Thêm dòng: `Hoàng Sa và Trường Sa là của Việt Nam. 🇻🇳`
- Hỗ trợ cả giao diện VN / EN.


## V3.3.5 — Xóa phần note credits thừa
- Xóa khối `Thanh toán bằng credits`.
- Xóa dòng `Job lỗi được hoàn credits tự động`.
- Giữ lại phần Giới thiệu và các card model bên dưới.


## V3.3.6 — Cập nhật slogan trang chủ
- Thay dòng phụ bên dưới tiêu đề bằng slogan:
  `TVC Studio AI – Khi hình ảnh bắt đầu chuyển động.`
- Đồng thời cập nhật luôn bản EN:
  `TVC Studio AI – When images begin to move.`
- Giữ nguyên bản đã xóa phần thừa từ V3.3.5.


## V3.3.7 — Chuyển nền tối hơn nhẹ
- Nền tổng thể được làm tối hơn một chút.
- Vẫn giữ phong cách pastel / glass.
- Sidebar và topbar được làm đậm hơn nhẹ để đồng bộ với nền mới.


## V3.3.8 — High Contrast Glass
- Nền tối hơn rõ rệt để chữ dễ đọc.
- Card chuyển sang navy glass đậm hơn.
- Tăng contrast cho heading, body text, label và placeholder.
- Input / select / textarea tối hơn, chữ trắng rõ.
- Sidebar và topbar đậm hơn nhưng vẫn giữ phong cách glass.


## V3.3.9 — Làm lại menu Tài Khoản
- Thiết kế lại popup Tài Khoản gọn, rõ và đồng bộ giao diện High Contrast.
- Header hiển thị avatar, tên và email.
- Có thẻ số dư Credits + nút Nạp thêm.
- Menu gồm: Lịch Sử, Nạp Credits, Hồ Sơ Của Tôi, Kiếm Tiền Affiliate, Đăng Xuất.
- Các mục trong Dashboard chuyển tab trực tiếp, không bị bấm mà không phản hồi.
- Cập nhật email admin mặc định sang cấu hình mới và tự migrate admin mặc định cũ nếu có.


## V3.3.10 — Giới thiệu glass nhẹ
- Giữ hiệu ứng kính nhẹ ở block Giới thiệu.
- Xóa dải bóng sáng nằm ngang ở mép trên.
- Giảm shadow/glow để block phẳng và đồng bộ hơn.
- Giữ chữ rõ và icon nhẹ nhàng.


## V3.3.11 — Đơn giản hóa phần Tạo Video
- Bỏ Model, Prompt, dropdown Chất lượng và khung Mẹo khỏi giao diện tạo video.
- Chỉ giữ: ảnh minh họa, tải ảnh nhân vật, tải video mẫu, chọn 9:16/16:9.
- Có 2 nút tạo trực tiếp: Nhanh 480p / 10 credits và Chất lượng 720p / 20 credits.
- Backend/job queue không thay đổi; các giá trị model, prompt, quality được gửi ẩn.


## V3.3.12 — Preview phần Tạo Video dùng video
- Thay ảnh minh họa ở đầu phần Tạo Video bằng video demo.
- Video dùng file `static/videos/card_motion.mp4`.
- Autoplay muted + loop + playsinline để chạy ổn trên desktop và mobile.
- Nếu trình duyệt chưa tải video, poster vẫn dùng `static/images/card_motion.png`.


## V3.3.13 — Khôi phục hiệu ứng gương
- Nút `Tạo Video` trang chủ có phản chiếu kính rõ, vệt sáng chạy và glow pulse.
- Khi bấm nút có hiệu ứng lõm nhẹ.
- Khôi phục glass nhẹ cho upload, tab 9:16/16:9 và nút tạo video trong trang Create.
- Sửa lỗi icon `9:16 (Dọc)` bị render thành thanh ngang màu be.


## V3.3.14 — Global Mirror Glass
- Đồng bộ hiệu ứng kính gương cho toàn bộ website, không chỉ nút Tạo Video.
- Áp dụng cho: Trang chủ, toolbar, Login/Đăng ký, Tạo Video, Job, Ví Credits, Affiliate, Tài Khoản và Admin.
- Card, input, tab, upload, button, sidebar, topbar và popup đều dùng cùng hệ glass.
- Giữ độ tương phản cao để chữ dễ đọc.
- Phần Giới thiệu vẫn giữ glass nhẹ và không còn dải bóng ngang.
- Giữ bản sửa icon 9:16 và hiệu ứng CTA từ V3.3.13.


## V3.3.15 — Toolbar Mirror Glass Restore
- Khôi phục hiệu ứng kính gương cho thanh công cụ trên cùng.
- Tăng lại phản chiếu, viền sáng, blur và chiều sâu cho:
  - nút Chọn Model / Lịch Sử / Kiếm Tiền
  - Nạp Credits
  - Tài Khoản
  - công tắc ngôn ngữ VN / EN
  - vùng logo / brand
- Giữ nguyên Global Mirror Glass ở các trang khác từ V3.3.14.


## V3.3.16 — Khôi phục toolbar cũ
- Khôi phục thanh công cụ desktop navy/glass theo mẫu cũ người dùng chọn.
- Bỏ hiệu ứng sweep quá mạnh, giữ kính nhẹ và chiều sâu vừa phải.
- Desktop trở lại một hàng: Logo → VN/EN → Chọn Model / Lịch Sử / Kiếm Tiền → Credits → Tài Khoản.
- Sửa dứt điểm lỗi Nạp Credits và Tài Khoản bị hiển thị lặp trên desktop.
- Các phần còn lại của website vẫn giữ Global Mirror Glass mới.


## V3.3.17 — Sửa bóng và lệch video trang Tạo Video
- Bỏ lớp bóng lớn ở vùng tiêu đề `AI Motion Studio`.
- Giữ card glass nhẹ nhưng phần header phẳng, sạch.
- Sửa preview video luôn phủ kín khung 16:9.
- Bỏ `max-height` cũ làm xuất hiện dải đen phía dưới video.
- Căn video chính giữa trên desktop và mobile.


## V3.3.18 — Mobile Smooth Tabs
- Chuyển tab trên điện thoại có fade + slide nhẹ thay vì đổi `display` đột ngột.
- Nút toolbar/sidebar có phản hồi bấm nhanh hơn.
- Lịch Sử / Kiếm Tiền / Nạp Credits trên toolbar app chuyển tab trực tiếp, không điều hướng lại trang.
- Đồng bộ trạng thái selected của toolbar với tab đang mở.
- Dữ liệu Job / Wallet / Affiliate được tải sau khi UI đã phản hồi để thao tác cảm giác nhanh hơn.


## V3.3.19 — Xóa Tài Khoản bị lặp trên mobile
- Xóa nút `A Tài Khoản` / `mobileAccountBtn` khỏi thanh nav.
- Thanh nav mobile còn 4 mục nên nhẹ và gọn hơn.
- Giữ lại đúng một nút tài khoản thật ở góc phải để mở popup tài khoản.
- Không còn 2 phần Tài Khoản chạy đồng thời.


## V3.3.20 — Hiện lại Tài Khoản trên mobile
- Sửa lỗi sau khi xóa nút Tài Khoản bị lặp khiến mobile không còn thấy nút tài khoản.
- Giữ thanh tab dưới chỉ 4 mục.
- Giữ VN/EN ở bên phải và logo ở giữa.
- Thêm đúng một nút avatar Tài Khoản ở góc trái hàng trên.
- Bấm avatar vẫn mở popup Tài Khoản đầy đủ.


## V3.3.21 — 5 tab dưới trên mobile
- Thanh mobile có đúng 5 tab: Chọn Model, Lịch Sử, Kiếm Tiền, Nạp Credits, Tài Khoản.
- Xóa nút Tài Khoản riêng ở hàng logo để không bị lặp.
- Tài Khoản trên trang app chuyển tab trực tiếp và mượt như các tab khác.
- Trang chủ/Admin bấm Tài Khoản sẽ mở `/app#account`.


## V3.3.22 — Sửa đúng bố cục 5 tab mobile
- Sửa lỗi Nạp Credits / Tài Khoản bị hiển thị thành nút dài ngang.
- Ép 5 tab nằm cùng một hàng dưới logo.
- Mỗi tab hiển thị icon phía trên + tên phía dưới.
- Ẩn hoàn toàn toolbar-right desktop trên mobile để không bị lặp.


## V3.3.23 — Một Tài Khoản menu + Nạp VIP
- Mobile giữ đúng 1 tab `Tài Khoản`; bấm tab này chỉ mở menu Tài Khoản.
- Không dùng tab Tài Khoản dưới để điều hướng sang trang Tài Khoản riêng nữa.
- `Nạp Credits` đổi thành `Nạp VIP`.
- Ô Nạp VIP chỉ hiển thị số dư hiện tại ở phần icon, bỏ biểu tượng lửa/kim cương.
- Desktop cũng đổi nhãn nạp thành `Nạp VIP` và bỏ ký hiệu kim cương cạnh số dư.


## V3.3.24 — Đổi tên Ví Credits thành Ví TVC
- Đổi nhãn `Ví credits` / `Ví Credits` thành `Ví TVC`.
- Trang Ví trong dashboard cũng hiển thị tiêu đề `Ví TVC`.
- Mô tả đổi thành `Nạp VIP và lịch sử giao dịch`.
- Không đổi biến/backend `credits` để tránh ảnh hưởng số dư, job queue và thanh toán.


## V3.3.27 — Đồng bộ toàn bộ nhãn Credits → TVC
- Đổi toàn bộ phần hiển thị cho người dùng từ `Credits/credits` thành `TVC`.
- Bao gồm: Trang chủ, Tạo Video, chi phí job, Ví TVC, Tài Khoản, Affiliate, Admin và thông báo lỗi.
- Ví dụ: `10 credits` → `1 TVC`, `credits dự kiến` → `TVC dự kiến`, `Không đủ credits` → `Không đủ TVC`.
- Không đổi tên cột database, API field hoặc biến backend `credits` để tránh phá dữ liệu và logic hiện tại.


## V3.3.27 — Cập nhật gói tạo video
- Đổi `Tạo Video Nhanh` thành `Tạo Video Thường`.
- Gói thường: `1 TVC`.
- Gói chất lượng cao: `2 TVC`.
- Bỏ chữ `480` và `720` trong phần nút/gói tạo video.


## V3.3.27 — Giá tạo video mới
- Gói `Tạo Video Thường`: `1 TVC`.
- Gói `Tạo Video Chất Lượng`: `2 TVC`.
- Bỏ toàn bộ chữ `480/720` ở phần hiển thị nút tạo video.
- Đồng bộ cả frontend và backend tính phí.


## V3.3.28 — Đồng bộ menu Tài Khoản mobile + PC
- Giữ đúng mẫu menu Tài Khoản: avatar, Xin chào, tên, trạng thái, số dư TVC, Nạp thêm.
- Menu gồm: Lịch Sử, Nạp VIP, Hồ Sơ Của Tôi, Kiếm Tiền Affiliate, Đăng xuất.
- Mobile và desktop dùng cùng một kiểu panel.
- Không tạo thêm nút/menu Tài Khoản thứ hai.


## V3.3.29 — Tài Khoản chỉ mở menu nổi
- Chỉ giữ đúng 1 nút `Tài Khoản` trên thanh công cụ.
- Xóa nhóm avatar/Tài Khoản bị lặp ở góc phải desktop.
- Xóa nút Tài Khoản phụ ở sidebar và avatar/đăng xuất phụ trong topbar Dashboard.
- Bấm `Tài Khoản` trên PC hoặc điện thoại chỉ mở menu nổi.
- Không tự chuyển sang trang thông tin tài khoản nữa.
- Chỉ bấm `Hồ Sơ Của Tôi` bên trong menu mới mở trang thông tin chi tiết.


## V3.3.30 — Sửa dứt điểm nút Tài Khoản không mở menu
- Sửa handler Tài Khoản còn sót từ bản cũ.
- Xóa tham chiếu tới các nút Tài Khoản đã bị xóa.
- Bấm đúng một nút `Tài Khoản` sẽ toggle popup `accountPopover`.
- Popup được chuyển trực tiếp xuống `body`, tránh bị toolbar cắt/che.
- Bấm ngoài hoặc phím Esc sẽ đóng menu.
- `Hồ Sơ Của Tôi` mới mở tab thông tin tài khoản; nút Tài Khoản chính không mở trang hồ sơ.


## V3.3.31 — Native Account Menu + Fast Mobile
- Thay nút Tài Khoản dùng JavaScript toggle bằng `details/summary` native của trình duyệt.
- Bấm Tài Khoản mở menu trực tiếp, không phụ thuộc JS nên ổn định hơn trên Safari iPhone.
- Chỉ `Hồ Sơ Của Tôi` mới mở trang thông tin tài khoản.
- Giảm lag mobile bằng cách tắt live backdrop-blur trên các card/nút và tắt animation trang trí.
- Chuyển tab mobile rút gọn còn fade rất ngắn, không slide/scale.


## V3.3.32 — Account Popup Viewport Fix
- Sửa menu Tài Khoản mobile không bị lệch/tràn mép màn hình.
- Khi xoay ngang, popup tự fit theo chiều cao màn hình và có thể cuộn bên trong.
- Bỏ tình trạng mở menu nhưng phần dưới không xem được trên landscape.


## V3.3.33 — Menu Tài Khoản nổi, không đẩy 5 tab
- Bấm Tài Khoản chỉ mở menu overlay.
- 5 tab Chọn Model / Lịch Sử / Kiếm Tiền / Nạp VIP / Tài Khoản giữ nguyên một hàng.
- Ép thứ tự và grid-column cố định để không bị nhảy hàng khi mở menu.
- Popup dùng `position: fixed`, không tham gia layout của toolbar.
- Màn hình ngang vẫn cuộn được menu riêng.


## V3.3.34 — Sửa toolbar PC về đúng một hàng
- PC: Logo + VN/EN + Chọn Model + Lịch Sử + Kiếm Tiền + Nạp VIP + Tài Khoản nằm cùng một hàng.
- Không còn nút Tài Khoản nằm riêng phía trên.
- Không còn 4 tab bị rơi xuống phần nội dung.
- Menu Tài Khoản vẫn là popup overlay, mở menu không đẩy hoặc thay đổi vị trí các tab.
- Mobile giữ nguyên bố cục 5 tab của V3.3.33.


## V3.3.35 — Popup Tài Khoản nhỏ kiểu Aidancing
- Bấm Tài Khoản chỉ mở một popup nhỏ, neo ngay dưới nút.
- Không mở panel lớn, không đẩy 5 tab, không đổi bố cục toolbar.
- Giữ mirror glass nhẹ: nền navy trong, blur nhẹ, viền sáng mảnh, shadow vừa.
- Không có dải bóng ngang lớn.
- Mobile dọc: popup nhỏ ở bên phải, không tràn màn hình.
- Mobile ngang: popup vẫn nhỏ và cuộn bên trong nếu thiếu chiều cao.
- Desktop: popup nhỏ neo ngay dưới nút Tài Khoản.


## V3.3.36 — Google Login
- Chưa đăng nhập: tab cuối hiển thị **Đăng nhập** thay vì Tài Khoản.
- Bấm Đăng nhập mở popup glass nhỏ, không đẩy 5 tab.
- Popup có nút **Đăng nhập bằng Google**, đăng nhập Email và Đăng ký.
- Google credential được gửi về FastAPI và xác minh server-side bằng `verify_oauth2_token`.
- Tài khoản Google mới tự tạo user + 30 TVC; email đã tồn tại sẽ được liên kết sau khi token Google được xác minh.
- Đăng nhập thành công: tab đổi lại thành **Tài Khoản** và giữ popup tài khoản V3.3.35.
- Railway cần `GOOGLE_CLIENT_ID`. Không cần Client Secret cho luồng GIS popup này.
- Cookie session mặc định Secure trên HTTPS; local HTTP có thể đặt `COOKIE_SECURE=false`.


## V3.3.37 — Google Login config fix
- Sửa lỗi popup báo “Google Login chưa được cấu hình” dù đã tạo OAuth Client.
- Railway `GOOGLE_CLIENT_ID` vẫn được ưu tiên.
- Có fallback bằng chính OAuth Client ID public của TVC Studio AI nếu Railway chưa nạp biến.
- `/api/auth/google-config` trả thêm `source` để kiểm tra đang đọc từ Railway hay fallback.
- Không dùng/không nhúng Google Client Secret.


## V3.3.38 — Chống tạo video trùng
- Frontend khóa cả hai nút render ngay từ lần bấm đầu tiên và hiện “Đang tạo video...”.
- Không cho đổi tỷ lệ/tệp trong lúc request đang gửi.
- Mỗi request có `request_key` idempotency riêng.
- Backend có unique idempotency key theo user và khóa tạo job theo user.
- Request trùng/retry trả lại job đã nhận thay vì tạo/trừ TVC lần nữa.
- Backend giữ khóa trong lúc upload; sau khi tạo xong còn cooldown 8 giây chống double tap từ client cũ.
- Trừ TVC bằng câu lệnh atomic, không cho số dư âm nếu có request đồng thời.


## V3.3.39 — Business polish / Footer / Pricing / Referral
- Nền tảng phát triển từ V3.3.38, giữ Google Login và duplicate-job guard.
- Lịch Sử ẩn tên model kỹ thuật, thay bằng “Véo 3 né ra tí 🤏”.
- Xóa hoàn toàn card “AI Thay Đổi Trang Phục Video”.
- Đổi “Kiếm Tiền” thành “Giới Thiệu”; bỏ UI hạng Bạc/Vàng, hoa hồng và rút tiền.
- Giai đoạn test chỉ ghi nhận link/mã referral; cơ chế +5 lượt / +1 lượt được mô tả nhưng chưa tự động cộng.
- Tắt phát sinh thưởng affiliate % cũ khi admin duyệt top-up.
- Tài khoản mới bắt đầu 0 TVC; tài khoản cũ không bị thay đổi số dư.
- Gói Nạp VIP: 10K/3 lượt, 60K/25 lượt, 99K/50 lượt.
- Thêm bộ đếm Video Thường và Video Chất Lượng từ số dư TVC.
- Thêm footer và các trang: Bảng Giá, Về Chúng Tôi, Liên Hệ, Điều Khoản, Bảo Mật, Hoàn Tiền, Chính Sách Nội Dung AI.
- Thông tin liên hệ: Mr Cường / cuongtv.bx92@gmail.com / Zalo 0917764222.
- Job lỗi do hệ thống: hoàn TVC tự động; nội dung 18+ bị cấm.


## V3.3.40 — Một mức giá / Một nút Tạo Video
- Xóa lựa chọn Video Thường / Video Chất Lượng khỏi giao diện.
- Trang tạo video chỉ còn một nút **Tạo Video**.
- Mỗi job luôn trừ đúng **1 TVC = 1 lượt video**, backend tự ép mức giá này dù client cũ gửi quality 480/720.
- Giữ nguyên duplicate-job guard / request_key để chống bấm nhiều lần tạo nhiều video.
- Ví chỉ còn một bộ đếm **Lượt video còn lại**; bỏ bộ đếm Chất Lượng.
- Lịch sử job không còn hiện 480p/720p để tránh tạo cảm giác có hai gói chất lượng.
- Bảng Giá, Điều Khoản và Về Chúng Tôi được cập nhật theo cơ chế đồng giá.
- Worker/Wan vẫn nhận profile nội bộ mặc định; người dùng không phải chọn chất lượng.


## V3.3.43 — Public pages dùng toolbar như Trang Chủ
- Bảng Giá / Về Chúng Tôi / Liên Hệ / Điều Khoản / Bảo Mật / Hoàn Tiền / Nội Dung AI dùng đúng toolbar 5 tab của Trang Chủ.
- Toolbar giữ Chọn Model / Lịch Sử / Giới Thiệu / Nạp VIP / Đăng nhập-Tài Khoản.
- Google Login và popup tài khoản hoạt động trên các trang public.
- Mobile Bảng Giá ép 3 gói thành 1 cột; gói 99K/50 lượt luôn hiện đầy đủ.
- Footer được làm lại bằng CSS sạch riêng: không dính chữ, logo nhỏ đúng tỷ lệ, copyright không bay sang góc.
- Xóa khối “3 bước để khách tạo video” trên Trang Chủ.
- Patch đóng gói trực tiếp từ V3.3.40.


## V3.3.44 — Home label / glass toolbar / single-quality fix
- Đổi tab “Chọn Model” thành “Trang Chủ” trên toàn bộ toolbar.
- SĐT/Zalo hiển thị dạng 0917.764.222, liên kết tel vẫn dùng số nguyên.
- Slogan mới: “AI không khiến bạn tụt lại – Người biết dùng AI mới khiến bạn tụt lại.”
- Khôi phục hiệu ứng nhấn/lún/glow nhẹ cho nút và tab; mobile dùng animation rất ngắn.
- Toolbar trong suốt hơn với mirror glass navy, blur nhẹ và không có glare lớn.
- Xóa hoàn toàn trường quality khỏi form tạo video; backend bỏ tham số quality từ user và luôn dùng profile nội bộ.
- Thêm /api/version để kiểm tra Railway đã chạy V3.3.44.
- Thêm ghi chú “Video chuyển động nên có thời lượng từ 10s đến 20s.” gần ô tải video mẫu.


## V3.3.46 — Toolbar glass 70/20/10
- Thanh trên cùng đổi sang palette 70% navy + 20% xanh lam + 10% tím.
- Giữ hiệu ứng gương trong suốt, không chuyển sang nền đen đặc khi đổi trang hoặc scroll.
- Áp dụng đồng nhất cho Trang Chủ và toàn bộ trang public/chính sách.
- Active tab sáng hơn nhẹ, vẫn giữ phong cách mirror glass.
- Mobile dùng blur nhẹ hơn để hạn chế lag.

## GPU service adapters

Bốn dịch vụ mở rộng dùng chung contract worker:

- `POST /v1/jobs`: nhận `client_job_id`, `operation`, `priority`, JSON `payload` và file multipart; trả `id` hoặc `job_id`.
- `GET /v1/jobs/{id}`: trả trạng thái và progress.
- `DELETE /v1/jobs/{id}`: hủy job còn trong hàng chờ.
- `GET /v1/jobs/{id}/result`: stream ảnh hoặc video kết quả.
- `GET /health`: health riêng của worker.

Trạng thái được chuẩn hóa về `queued`, `processing`, `completed`, `failed`,
`cancelled`. URL, token, capability và timeout đều lấy từ biến môi trường.

### Biến môi trường GPU

```env
VIDEO_WORKER_URL=
VIDEO_WORKER_TOKEN=
OUTFIT_WORKER_URL=
OUTFIT_WORKER_TOKEN=
BACKGROUND_WORKER_URL=
BACKGROUND_WORKER_TOKEN=
UPSCALE_WORKER_URL=
UPSCALE_WORKER_TOKEN=
WORKER_REQUEST_TIMEOUT=30
WORKER_POLL_INTERVAL=4
VIDEO_USAGE_COST=
VIDEO_ALLOWED_DURATIONS=
UPSCALE_ALLOWED_SCALES=2,4
UPSCALE_FACE_RESTORE_SUPPORTED=false
```

AI Video Creator chỉ nhận job khi đã cấu hình worker, `VIDEO_USAGE_COST` và danh
sách thời lượng model hỗ trợ, ví dụ `VIDEO_ALLOWED_DURATIONS=5,10`.

### Storage

Production must use persistent storage. Railway's container filesystem is
ephemeral and is replaced on deploy, so mount a Railway Volume (for example at
`/data`) and set:

```env
PERSISTENT_DATA_DIR=/data
```

The application stores `motionhub.db`, uploaded inputs, and generated outputs
under that directory. Without this variable and a mounted volume, users,
credits, ledgers, top-ups, and jobs can be lost when Railway redeploys.

`StorageBackend` tách lưu trữ khỏi API. Adapter `local` dùng cho development
qua `STORAGE_BACKEND=local` và `STORAGE_LOCAL_ROOT`. Railway production

### Model registry và nâng cấp video HD

Model được chọn bằng biến môi trường: Motion Studio dùng danh sách
`MOTION_STUDIO_MODELS` (Wan-Animate-2/SCAIL-2), AI Video Creator dùng
`VIDEO_MODEL`, thay trang phục dùng `OUTFIT_MODEL`, đổi bối cảnh dùng
`BACKGROUND_MASK_MODEL` + `BACKGROUND_MODEL`, và nâng ảnh dùng
`UPSCALE_MODEL`.

`video_upscale` là hậu xử lý nội bộ ưu tiên cao cho Motion Studio và AI Tạo
Video, không có card và không trừ thêm lượt. Khi bật, video gốc được gửi tới
worker cấu hình bởi `VIDEO_UPSCALE_WORKER_URL/TOKEN`; payload yêu cầu giữ tỷ
lệ, FPS, thời lượng, âm thanh, danh tính và chuyển động, đồng thời nâng cạnh
ngắn tới `VIDEO_UPSCALE_TARGET_SHORT_SIDE`. Trạng thái công khai là
`upscaling`. Nếu submit/poll/tải bản HD lỗi, job chuyển sang hoàn thành và
endpoint kết quả tiếp tục trả video render gốc.
