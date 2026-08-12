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
Password mặc định: `ChangeMe123!`

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
