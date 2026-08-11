"""
Worker demo cho MotionHub AI Business V2.
Nó KHÔNG render AI thật. Nó claim job, cập nhật tiến độ,
sau đó dùng chính motion input làm output để test toàn bộ hệ thống.

Chạy:
  set MOTIONHUB_URL=http://127.0.0.1:8000
  set WORKER_TOKEN=change-worker-token
  python worker_demo.py
"""
import os, time, tempfile, urllib.request, json, pathlib

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

print("MotionHub demo worker running:",BASE)
while True:
    try:
        payload=claim()
        job=payload.get("job")
        if not job:
            time.sleep(4); continue
        jid=job["id"]; print("Claimed job",jid)
        with tempfile.TemporaryDirectory() as td:
            motion=os.path.join(td,"motion.mp4")
            download(job["motion_url"],motion)
            for p in (10,25,45,65,82,95):
                time.sleep(1); progress(jid,p)
            complete(jid,motion)
            print("Completed demo job",jid)
    except KeyboardInterrupt:
        break
    except Exception as e:
        print("Worker error:",e); time.sleep(5)
