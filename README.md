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
- Admin duyệt / từ chối topup
- Admin cộng/trừ credits thủ công
- Admin xem users / jobs / stats
- Worker API để RTX 5090 claim job
- Worker demo để test end-to-end

## Chưa phải production hoàn chỉnh
- Chưa nối cổng thanh toán thật
- Chưa object storage/S3
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
Email: `admin@motionhub.local`
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
Model `AI Copy Chuyển Động` đang dẫn vào dashboard thật.
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

## V3.1.1 — Thay ảnh Copy Chuyển Động
- Đã thay ảnh mới cho mục / card `Copy Chuyển Động`.
- Ảnh được resize/crop đúng kích thước asset cũ để gắn vào web ngay.
- Không đổi backend hay logic, chỉ cập nhật hình hiển thị.

## V3.1.2 — Nút Tạo Video nổi hơn + card Copy Chuyển Động căn lại
- Thay ảnh card `Copy Chuyển Động` bằng ảnh người dùng gửi.
- Căn lại bố cục card theo hướng giống mẫu hơn: ảnh lớn phía trên, phần chữ căn giữa.
- Nút `Tạo Video` đổi sang kiểu full-width, to hơn, sáng hơn và có hiệu ứng sweep + pulse.
- Mobile và desktop đều áp dụng.

## V3.1.3 — Dọn lại card Copy Chuyển Động
- Xóa phần dư bị khoanh đỏ trong ảnh card Copy Chuyển Động bằng cách crop lại ảnh preview.
- Bỏ badge `ĐANG HOẠT ĐỘNG / WAN ANIMATE 2` trên card này theo yêu cầu.
- Căn lại chiều cao vùng ảnh để card gọn hơn.


## V3.1.4 — Card Copy Chuyển Động hiển thị video
- Phần preview của card `Copy Chuyển Động` đổi từ ảnh sang video.
- Web sẽ tự load video tại: `static/videos/card_motion.mp4`
- Nếu chưa có file video, web tự fallback về ảnh `static/images/card_motion.png`
- Chỉ cần upload file mp4 preview vào đúng đường dẫn là chạy.


## V3.2 — Mirror Glass
- Đổi giao diện sang kính gương trong kiểu liquid/mirror glass.
- Viền phản chiếu trắng, blur trong, ánh cyan/xanh/hồng rất nhẹ.
- Giảm màu tím và giảm neon đặc.
- Đồng bộ card, toolbar, nút, input, account popup và mobile.
- Admin password mặc định được cập nhật theo cấu hình mới.
