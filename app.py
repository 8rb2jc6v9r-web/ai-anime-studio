"""AI Anime Studio（デモ版）: 外部APIなし・無料。主人公と背景をコードで描き、FFmpegで動画化する。"""
import os, re, math, random, shutil, hashlib, subprocess, threading, uuid, glob
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template
from PIL import Image, ImageDraw

BASE = Path(__file__).parent
OUT = BASE / "output"; OUT.mkdir(exist_ok=True)
app = Flask(__name__)
JOBS = {}
SCENES, W, H = 6, 1080, 1920

# 場面ごとの空の色（上, 下, 太陽/月）: 夕焼け・月夜・桜・昼・朝焼け・森
PALETTES = [((255,183,120),(120,70,140),(255,240,200)), ((20,24,60),(60,40,110),(250,250,220)),
            ((255,214,224),(250,150,180),(255,255,255)), ((140,200,230),(60,120,170),(255,255,240)),
            ((255,150,90),(190,50,60),(255,225,150)), ((30,60,70),(10,30,40),(200,255,230))]
HAIR = [(30,30,50),(120,60,40),(60,60,120),(150,40,60),(200,170,80)]
CLOTH = [(200,40,50),(40,90,160),(90,60,150),(30,130,100),(220,120,40)]

def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError("FFmpegエラー: " + r.stderr[-300:])

def find_font():
    c = [os.getenv("FONT_PATH", ""), "C:/Windows/Fonts/meiryo.ttc", "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"]
    c += glob.glob("/usr/share/fonts/**/*CJK*", recursive=True) + glob.glob("/usr/share/fonts/**/*Gothic*", recursive=True)
    return next((x for x in c if x and Path(x).exists()), None)

# ---------- 台本（デモ版は入力文を6場面に分けるだけ） ----------
def make_script(story, dur):
    sec = dur // SCENES
    parts = [p.strip() for p in re.split(r"[。！？!?\n、]+", story) if p.strip()] or ["むかしむかし"]
    limit = int(sec * 5)  # 読み上げ速度の目安
    scenes = []
    for i in range(SCENES):
        a, b = i * len(parts) // SCENES, (i + 1) * len(parts) // SCENES
        t = "。".join(parts[a:b]) if b > a else parts[min(i * len(parts) // SCENES, len(parts) - 1)]
        scenes.append({"narration": t[:limit] + ("…" if len(t) > limit else ""), "seconds": sec})
    return {"scenes": scenes}

# ---------- 絵 ----------
def make_bg(path, i, seed):
    pal, w, r = PALETTES[i % 6], 1400, random.Random(seed * 10 + i)
    im = Image.new("RGB", (w, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H; d.line([(0, y), (w, y)], fill=tuple(int(pal[0][k] * (1 - t) + pal[1][k] * t) for k in range(3)))
    cx, cy = r.randint(300, 1100), r.randint(450, 800)
    d.ellipse([cx-170, cy-170, cx+170, cy+170], fill=pal[2])
    for _ in range(40):
        x, y, s = r.randint(0, w), r.randint(0, 1100), r.randint(3, 8); d.ellipse([x, y, x+s, y+s], fill=pal[2])
    for L, (base, amp) in enumerate([(1250, 160), (1450, 120), (1650, 90)]):
        col = tuple(int(pal[1][k] * (0.6 - 0.18 * L)) for k in range(3))
        pts = [(0, H)] + [(x, base - int(amp * (.5 + .5 * math.sin(x / 260 + L * 1.7 + i)))) for x in range(0, w + 101, 100)] + [(w, H)]
        d.polygon(pts, fill=col)
    im.save(path)

def make_hero(path, seed):  # 同じseed = 全シーンで同じ見た目
    hair, cloth, skin = HAIR[seed % 5] + (255,), CLOTH[(seed // 5) % 5] + (255,), (255, 224, 200, 255)
    im = Image.new("RGBA", (560, 860), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.polygon([(130, 420), (430, 420), (500, 850), (60, 850)], fill=cloth)
    d.polygon([(250, 420), (310, 420), (280, 640)], fill=(255, 255, 255, 255))
    d.rectangle([90, 610, 470, 670], fill=(250, 240, 220, 255))
    d.rectangle([250, 380, 310, 440], fill=skin)
    d.ellipse([110, 60, 450, 430], fill=hair); d.ellipse([140, 130, 420, 420], fill=skin)
    d.pieslice([120, 70, 440, 330], 180, 360, fill=hair)
    for x in (150, 210, 270, 330): d.polygon([(x, 200), (x + 60, 200), (x + 30, 290)], fill=hair)
    for ex in (205, 315):
        d.ellipse([ex-34, 290, ex+34, 370], fill=(255, 255, 255, 255)); d.ellipse([ex-22, 298, ex+22, 366], fill=(40, 60, 120, 255))
        d.ellipse([ex-8, 308, ex+4, 320], fill=(255, 255, 255, 255))
    d.arc([240, 370, 320, 400], 20, 160, fill=(190, 90, 90, 255), width=5)
    im.save(path)

# ---------- ナレーション（無料・オフライン: espeak-ng。EDGE_TTS=1 でedge-ttsも可） ----------
def tts(text, d, i):
    try:
        if os.getenv("EDGE_TTS") == "1":
            import asyncio, edge_tts
            asyncio.run(edge_tts.Communicate(text, "ja-JP-NanamiNeural").save(str(d / f"a{i}.mp3"))); return f"a{i}.mp3"
        if shutil.which("espeak-ng"):
            subprocess.run(["espeak-ng", "-v", "ja", "-s", "150", "-w", str(d / f"a{i}.wav"), text], check=True); return f"a{i}.wav"
    except Exception:
        pass
    return None

def wrap(t, w=11): return "\n".join(t[k:k + w] for k in range(0, len(t), w))

def build_scene(d, i, text, sec, font, audio):
    (d / f"t{i}.txt").write_text(wrap(text), encoding="utf-8")
    ff = font.replace("\\", "/").replace(":", "\\:") if font else None
    sub = (f"drawtext=fontfile='{ff}':textfile=t{i}.txt:fontsize=64:fontcolor=white:borderw=6:bordercolor=black:"
           f"line_spacing=14:x=(w-text_w)/2:y=h*0.1") if ff else "null"
    fc = (f"[0:v]crop=1080:1920:x='(in_w-1080)*t/{sec}':y=0,fps=30[bg];"
          f"[bg][1:v]overlay=x=(W-w)/2:y='H-h-300+14*sin(2*PI*t)'[o];[o]{sub},format=yuv420p[v];"
          f"[2:a]aresample=44100,aformat=channel_layouts=stereo,apad[a]")
    ain = ["-i", audio] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    run(["ffmpeg", "-y", "-loop", "1", "-t", str(sec), "-i", f"bg{i}.png", "-loop", "1", "-t", str(sec), "-i", "hero.png", *ain,
         "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", str(sec), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "21", "-c:a", "aac", "-b:a", "160k", f"s{i}.mp4"], cwd=d)

def pipeline(jid, story, dur):
    J = JOBS[jid]; d = OUT / jid; d.mkdir(exist_ok=True)
    try:
        font = find_font(); seed = int(hashlib.md5(story.encode()).hexdigest(), 16) % 1000
        if not font: J["warnings"].append("日本語フォントが無いため字幕なしです")
        J["message"] = "台本とシーン構成を作成中…"
        script = make_script(story, dur); J["script"] = script
        make_hero(d / "hero.png", seed); J["progress"] = 4
        voiced = 0
        for i, s in enumerate(script["scenes"]):
            J["message"] = f"シーン {i+1}/{SCENES} を作成中（絵・ナレーション・字幕）…"
            make_bg(d / f"bg{i}.png", i, seed)
            a = tts(s["narration"], d, i); voiced += bool(a)
            build_scene(d, i, s["narration"], s["seconds"], font, a)
            J["scenes_done"] = i + 1; J["progress"] = 4 + 90 * (i + 1) // SCENES
        if not voiced: J["warnings"].append("音声エンジン(espeak-ng)が無いため無音です")
        J["message"] = "動画をつないでいます…"; J["progress"] = 96
        (d / "list.txt").write_text("".join(f"file 's{i}.mp4'\n" for i in range(SCENES)))
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "-movflags", "+faststart", "final.mp4"], cwd=d)
        J.update(status="done", progress=100, message="完成しました！")
    except Exception as e:
        J.update(status="error", error=str(e))

@app.get("/")
def index(): return render_template("index.html")

@app.post("/api/generate")
def generate():
    b = request.json or {}; story = (b.get("story") or "").strip(); dur = int(b.get("duration", 60))
    if not story: return jsonify(error="ストーリーを入力してください"), 400
    if dur not in (30, 60, 120): return jsonify(error="長さは30・60・120秒から選んでください"), 400
    if len(story) > 2000: return jsonify(error="ストーリーは2000文字以内にしてください"), 400
    jid = uuid.uuid4().hex[:10]
    JOBS[jid] = {"status": "running", "progress": 0, "message": "開始", "scenes_done": 0, "warnings": [], "script": None, "error": None}
    threading.Thread(target=pipeline, args=(jid, story, dur), daemon=True).start()
    return jsonify(id=jid)

@app.get("/api/status/<jid>")
def status(jid): return jsonify(JOBS.get(jid) or {"status": "error", "error": "ジョブが見つかりません"})

@app.get("/api/video/<jid>")
def video(jid):
    return send_file(OUT / re.sub(r"\W", "", jid) / "final.mp4", mimetype="video/mp4",
                     as_attachment=bool(request.args.get("dl")), download_name="ai-anime-studio.mp4")

if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", 5000)))
