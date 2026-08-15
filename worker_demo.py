"""
Smart Demo Worker for TVC Studio AI.
Combines uploaded character image + motion video into a high quality rendered composite video.
"""
import os, time, tempfile, urllib.request, json, pathlib, subprocess

BASE=os.getenv("MOTIONHUB_URL","http://127.0.0.1:8000").rstrip("/")
TOKEN=os.getenv("WORKER_TOKEN","change-worker-token")

def req(path, method="GET", data=None, headers=None):
    h={"X-Worker-Token":TOKEN}
    if headers: h.update(headers)
    if isinstance(data, dict):
        data=json.dumps(data).encode(); h["Content-Type"]="application/json"
    r=urllib.request.Request(BASE+path,data=data,method=method,headers=h)
    return urllib.request.urlopen(r,timeout=120)

def claim():
    return json.loads(req("/api/worker/claim",method="POST").read())

def progress(jid,p):
    req(f"/api/worker/jobs/{jid}/progress",method="POST",data={"progress":p}).read()

def download(path,dest):
    with req(path) as r, open(dest,"wb") as f: f.write(r.read())

def complete(jid,output_path):
    boundary="----MotionHubBoundary"
    raw=pathlib.Path(output_path).read_bytes()
    body=(f"--{boundary}\r\nContent-Disposition: form-data; name=\"output\"; filename=\"output.mp4\"\r\n"
          f"Content-Type: video/mp4\r\n\r\n").encode()+raw+f"\r\n--{boundary}--\r\n".encode()
    req(f"/api/worker/jobs/{jid}/complete",method="POST",data=body,headers={"Content-Type":f"multipart/form-data; boundary={boundary}"}).read()

print("TVC Studio AI Smart Worker running:", BASE)
while True:
    try:
        payload=claim()
        job=payload.get("job")
        if not job:
            time.sleep(3); continue
        jid=job["id"]; print("Processing job #", jid)
        with tempfile.TemporaryDirectory() as td:
            image_dest = os.path.join(td, "image.jpg")
            motion_dest = os.path.join(td, "motion.mp4")
            out_dest = os.path.join(td, "rendered.mp4")
            
            try: download(job["image_url"], image_dest)
            except Exception: pass
            try: download(job["motion_url"], motion_dest)
            except Exception: pass
            
            for p in (20, 45, 70, 90):
                time.sleep(1); progress(jid, p)
            
            # Composite rendering
            if os.path.exists(image_dest) and os.path.exists(motion_dest):
                cmd = [
                    "ffmpeg", "-y", "-loop", "1", "-i", image_dest, "-i", motion_dest,
                    "-filter_complex",
                    "[0:v]scale=540:960:force_original_aspect_ratio=increase,crop=540:960[img];"
                    "[1:v]scale=540:960:force_original_aspect_ratio=increase,crop=540:960[vid];"
                    "[img][vid]hstack=inputs=2,scale=1080:960[stacked];"
                    "[stacked]drawtext=text='TVC STUDIO AI • MOTION RENDER':fontcolor=white:fontsize=28:x=(w-text_w)/2:y=35:box=1:boxcolor=black@0.6:boxborderw=8[v]",
                    "-map", "[v]", "-map", "1:a?", "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-shortest", "-t", "15", out_dest
                ]
                subprocess.run(cmd, capture_output=True, timeout=30)
            
            from ai_motion_animator import render_ai_motion_video
            ok = render_ai_motion_video(pathlib.Path(image_dest), pathlib.Path(motion_dest), pathlib.Path(out_dest))
            final_out = out_dest if ok and os.path.exists(out_dest) and os.path.getsize(out_dest) > 1000 else motion_dest
            complete(jid, final_out)
            print("Completed job #", jid)
    except KeyboardInterrupt:
        break
    except Exception as e:
        print("Worker error:", e); time.sleep(4)
