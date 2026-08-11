"""
Khung worker để nối ComfyUI/Wan Animate 2.

Ý tưởng:
1) claim job từ MotionHub
2) tải ảnh + motion
3) upload input vào ComfyUI
4) đọc workflows/wan_animate_2_api.json
5) thay placeholder:
   __CHARACTER_IMAGE__
   __MOTION_VIDEO__
   __PROMPT__
6) POST workflow vào /prompt của ComfyUI
7) chờ hoàn tất
8) upload mp4 về /api/worker/jobs/{id}/complete

File này cố ý để phần mapping workflow ở dạng TODO vì mỗi workflow Wan Animate 2
có node ID khác nhau. Khi có workflow API JSON đang chạy thật, chỉ cần map 3 node.
"""
import os
MOTIONHUB_URL=os.getenv("MOTIONHUB_URL","http://127.0.0.1:8000")
WORKER_TOKEN=os.getenv("WORKER_TOKEN","change-worker-token")
COMFYUI_URL=os.getenv("COMFYUI_URL","http://127.0.0.1:8188")

print("MotionHub:",MOTIONHUB_URL)
print("ComfyUI:",COMFYUI_URL)
print("TODO: đặt workflows/wan_animate_2_api.json rồi map input node IDs.")
