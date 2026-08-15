"""
Native AI Motion & Face Animation Engine for TVC Studio AI.
Seamlessly animates character appearance to follow motion video movements.
"""
import os
import tempfile
import subprocess
from pathlib import Path
import cv2
import numpy as np

def render_ai_motion_video(character_img_path: Path, motion_video_path: Path, output_video_path: Path) -> bool:
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    
    char_img = cv2.imread(str(character_img_path))
    if char_img is None:
        print(f"Cannot read character image from {character_img_path}")
        return False
    
    cap = cv2.VideoCapture(str(motion_video_path))
    if not cap.isOpened():
        print(f"Cannot read motion video from {motion_video_path}")
        return False
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0:
        width, height = 720, 1280

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    # 1. Detect Character Face
    gray_char = cv2.cvtColor(char_img, cv2.COLOR_BGR2GRAY)
    char_faces = face_cascade.detectMultiScale(gray_char, 1.1, 4, minSize=(50, 50))
    
    if len(char_faces) > 0:
        cx, cy, cw, ch = sorted(char_faces, key=lambda f: f[2] * f[3], reverse=True)[0]
        pad_x = int(cw * 0.22)
        pad_y_top = int(ch * 0.35)
        pad_y_bot = int(ch * 0.22)
        
        x1 = max(0, cx - pad_x)
        y1 = max(0, cy - pad_y_top)
        x2 = min(char_img.shape[1], cx + cw + pad_x)
        y2 = min(char_img.shape[0], cy + ch + pad_y_bot)
        char_face_crop = char_img[y1:y2, x1:x2]
    else:
        h_crop = int(char_img.shape[0] * 0.6)
        char_face_crop = char_img[0:h_crop, :]

    temp_raw = tempfile.mktemp(suffix=".avi")
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    out = cv2.VideoWriter(temp_raw, fourcc, fps, (width, height))
    
    prev_box = None
    frame_idx = 0
    
    # 2. Process frames and track motion
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.15, 4, minSize=(50, 50))
        
        if len(faces) > 0:
            fx, fy, fw, fh = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)[0]
            curr_box = np.array([fx, fy, fw, fh], dtype=float)
            prev_box = curr_box if prev_box is None else prev_box * 0.7 + curr_box * 0.3
        
        if prev_box is not None:
            bx, by, bw, bh = prev_box.astype(int)
            p_x = int(bw * 0.22)
            p_yt = int(bh * 0.35)
            p_yb = int(bh * 0.22)
            
            tx1 = max(0, bx - p_x)
            ty1 = max(0, by - p_yt)
            tx2 = min(width, bx + bw + p_x)
            ty2 = min(height, by + bh + p_yb)
            
            tw = tx2 - tx1
            th = ty2 - ty1
            
            if tw > 20 and th > 20:
                resized_char = cv2.resize(char_face_crop, (tw, th), interpolation=cv2.INTER_LANCZOS4)
                mask = np.zeros((th, tw), dtype=np.uint8)
                cv2.ellipse(mask, (tw // 2, th // 2), (tw // 2 - 4, th // 2 - 4), 0, 0, 360, 255, -1)
                mask = cv2.GaussianBlur(mask, (21, 21), 11)
                
                center = (tx1 + tw // 2, ty1 + th // 2)
                try:
                    frame = cv2.seamlessClone(resized_char, frame, mask, center, cv2.NORMAL_CLONE)
                except Exception:
                    alpha = (mask.astype(float) / 255.0)[:, :, np.newaxis]
                    roi = frame[ty1:ty2, tx1:tx2]
                    frame[ty1:ty2, tx1:tx2] = (resized_char * alpha + roi * (1.0 - alpha)).astype(np.uint8)

        out.write(frame)
        frame_idx += 1
        if frame_idx >= 450: # up to 18 seconds
            break
            
    cap.release()
    out.release()
    
    # 3. Output to H.264 MP4 with preserved audio
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", temp_raw,
        "-i", str(motion_video_path),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-shortest",
        str(output_video_path)
    ]
    
    try:
        res = subprocess.run(ffmpeg_cmd, capture_output=True, timeout=60)
        if os.path.exists(temp_raw):
            os.remove(temp_raw)
        return res.returncode == 0 and output_video_path.exists() and output_video_path.stat().st_size > 1000
    except Exception as e:
        print("FFmpeg encode error:", e)
        if os.path.exists(temp_raw):
            os.remove(temp_raw)
        return False
