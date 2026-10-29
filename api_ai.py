import os
import sys
import time
import json
import uuid
import base64
import threading
import subprocess
from io import BytesIO

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.01
except ImportError:
    pyautogui = None

try:
    import mss
    sct = mss.mss()
except ImportError:
    sct = None

from PIL import Image, ImageGrab

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "HASIL_DATASET", "synthetic_rapor_dataset.jsonl")
MODEL_DIR = os.path.join(BASE_DIR, "models", "Qwen2.5-3B-Instruct")

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.config["SECRET_KEY"] = "skripsi_husain_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ==============================================================================
# PEMERIKSAAN & PEMUATAN MODEL AI LOKAL (SEBELUM SERVER AKTIF)
# ==============================================================================
tokenizer = None
model = None
model_status = {"loaded": False, "message": "Sedang mempersiapkan model AI..."}

def ensure_and_load_model():
    global tokenizer, model, model_status
    print("=" * 60)
    print("VALIDASI & INISIALISASI MODEL AI LOKAL")
    print("=" * 60)

    model_complete = False
    if os.path.exists(MODEL_DIR):
        files = os.listdir(MODEL_DIR)
        has_safetensors = any(f.endswith(".safetensors") for f in files)
        has_config = os.path.exists(os.path.join(MODEL_DIR, "config.json"))
        if has_safetensors and has_config:
            model_complete = True

    if not model_complete:
        print("[INFO] Model belum ada atau belum lengkap di folder lokal.")
        print("[INFO] Menjalankan ai.py untuk mendownload model secara utuh...")
        res_ai = subprocess.run([sys.executable, os.path.join(BASE_DIR, "ai.py")])
        if res_ai.returncode != 0:
            print("[WARN] ai.py selesai dengan kode peringatan.")

        print("[INFO] Menjalankan fix_config.py (1x) untuk sinkronisasi konfigurasi...")
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "fix_config.py")])

    print(f"[INFO] Memuat tokenizer dan model dari: {MODEL_DIR}")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        use_cuda = torch.cuda.is_available()
        print(f"[INFO] Akselerasi CUDA GPU: {'AKTIF' if use_cuda else 'TIDAK TERSEDIA (CPU Mode)'}")
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_DIR,
            torch_dtype=torch.float16 if use_cuda else torch.float32,
            device_map="auto" if use_cuda else None
        )
        model_status = {"loaded": True, "message": "Model AI Lokal Siap Digunakan"}
        print("[INFO] Model AI Lokal berhasil dimuat ke memori!")
    except Exception as e:
        model_status = {"loaded": False, "message": f"Gagal memuat model: {e}"}
        print(f"[ERROR] {model_status['message']}")

# ==============================================================================
# MULTI TERMINAL SESSIONS
# ==============================================================================
terminals = {}

def start_terminal_session(term_id=None, name=None):
    if term_id is None:
        term_id = str(uuid.uuid4())[:8]
    if name is None:
        name = f"Terminal {len(terminals) + 1}"

    proc = subprocess.Popen(
        ["cmd.exe"],
        cwd=BASE_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    )

    terminals[term_id] = {"process": proc, "name": name}

    def reader():
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            socketio.emit("terminal_output", {"term_id": term_id, "data": line})

    threading.Thread(target=reader, daemon=True).start()
    return term_id, name

# ==============================================================================
# SCREEN STREAMING CONTROLS (DEFAULT: SCREEN MATI & MODE LIVE)
# ==============================================================================
screen_active_clients = 0
screen_streaming_enabled = False  # Default Mati

def capture_screen():
    global sct
    if sct:
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
    else:
        img = ImageGrab.grab()
    img.thumbnail((1280, 720))
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=60)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def screen_stream_worker():
    while True:
        if screen_streaming_enabled and screen_active_clients > 0:
            try:
                frame_data = capture_screen()
                socketio.emit("screen_frame", {"image": frame_data})
            except Exception:
                pass
            time.sleep(0.08)
        else:
            time.sleep(0.4)

threading.Thread(target=screen_stream_worker, daemon=True).start()

# ==============================================================================
# API ENDPOINTS COMPATIBLE WITH dataset_generator.py (Port 8000)
# ==============================================================================
@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/connection", methods=["GET"])
def connection():
    return jsonify({
        "status": "ok",
        "message": "Server API Siap",
        "model_loaded": model_status["loaded"],
        "model_message": model_status["message"]
    })

@app.route("/api/login", methods=["POST"])
def login():
    username = request.form.get("username") or (request.json or {}).get("username")
    password = request.form.get("password") or (request.json or {}).get("password")
    if username == "husain" and password == "password_skripsi_aman":
        return jsonify({
            "access_token": "skripsi_jwt_token_husain_2026",
            "token_type": "bearer"
        })
    return jsonify({"detail": "Username atau password salah"}), 401

@app.route("/generate", methods=["POST"])
def generate():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"detail": "Unauthorized"}), 401

    if not model_status["loaded"] or model is None or tokenizer is None:
        return jsonify({"detail": "Model AI belum siap: " + model_status["message"]}), 503

    payload = request.get_json(force=True) or {}
    prompt = payload.get("prompt", "")
    max_tokens = int(payload.get("max_tokens", 3500))
    suhu = float(payload.get("temperature", 0.85))
    top_p = float(payload.get("top_p", 0.9))

    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    with torch.no_grad():
        generated_ids = model.generate(
            **model_inputs,
            max_new_tokens=max_tokens,
            temperature=suhu,
            top_p=top_p,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    output_ids = [out_ids[len(in_ids):] for in_ids, out_ids in zip(model_inputs.input_ids, generated_ids)]
    generated_text = tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0]

    return jsonify({
        "text": generated_text,
        "response": generated_text,
        "generated_text": generated_text
    })

@app.route("/api/dataset", methods=["GET"])
def get_dataset():
    if not os.path.exists(DATASET_PATH):
        return jsonify({"total": 0, "rows": []})

    rows = []
    total = 0
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                total += 1
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass

    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 15))
    start = max(0, total - (page * limit))
    end = total - ((page - 1) * limit)
    displayed = rows[start:end]
    displayed.reverse()

    return jsonify({
        "total": total,
        "page": page,
        "limit": limit,
        "rows": displayed
    })

# ==============================================================================
# SOCKETIO EVENTS
# ==============================================================================
@socketio.on("connect")
def handle_connect():
    global screen_active_clients
    screen_active_clients += 1
    emit("model_status", model_status)
    emit("screen_toggle_status", {"enabled": screen_streaming_enabled})
    if not terminals:
        start_terminal_session("term-1", "Terminal 1")
    term_list = [{"id": k, "name": v["name"]} for k, v in terminals.items()]
    emit("terminals_list", {"terminals": term_list})

@socketio.on("disconnect")
def handle_disconnect():
    global screen_active_clients
    screen_active_clients = max(0, screen_active_clients - 1)

@socketio.on("toggle_screen")
def handle_toggle_screen(data):
    global screen_streaming_enabled
    screen_streaming_enabled = bool(data.get("enabled", False))
    emit("screen_toggle_status", {"enabled": screen_streaming_enabled}, broadcast=True)

@socketio.on("new_terminal")
def handle_new_terminal():
    tid, name = start_terminal_session()
    term_list = [{"id": k, "name": v["name"]} for k, v in terminals.items()]
    socketio.emit("terminals_list", {"terminals": term_list})
    emit("terminal_created", {"id": tid, "name": name})

@socketio.on("close_terminal")
def handle_close_terminal(data):
    tid = data.get("term_id")
    if tid in terminals:
        try:
            terminals[tid]["process"].terminate()
        except Exception:
            pass
        del terminals[tid]
        term_list = [{"id": k, "name": v["name"]} for k, v in terminals.items()]
        socketio.emit("terminals_list", {"terminals": term_list})

@socketio.on("terminal_input")
def handle_terminal_input(data):
    tid = data.get("term_id")
    cmd = data.get("command", "")
    if tid in terminals and terminals[tid]["process"].stdin:
        terminals[tid]["process"].stdin.write(cmd + "\n")
        terminals[tid]["process"].stdin.flush()

@socketio.on("run_generator")
def handle_run_generator(data=None):
    tid = (data or {}).get("term_id")
    if not tid or tid not in terminals:
        if terminals:
            tid = list(terminals.keys())[0]
        else:
            tid, _ = start_terminal_session("term-1", "Terminal 1")

    cmd = f'"{sys.executable}" dataset_generator.py\n'
    if tid in terminals and terminals[tid]["process"].stdin:
        terminals[tid]["process"].stdin.write(cmd)
        terminals[tid]["process"].stdin.flush()
        socketio.emit("terminal_output", {
            "term_id": tid,
            "data": f"\r\n[Executing: {sys.executable} dataset_generator.py]\r\n"
        })

@socketio.on("stop_generator")
def handle_stop_generator(data=None):
    tid = (data or {}).get("term_id")
    try:
        subprocess.run(["powershell", "-Command", "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*dataset_generator.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True)
        msg = "\r\n[STOPPED] Proses dataset_generator.py berhasil dihentikan.\r\n"
        target_id = tid if (tid and tid in terminals) else (list(terminals.keys())[0] if terminals else "term-1")
        socketio.emit("terminal_output", {"term_id": target_id, "data": msg})
    except Exception as e:
        print(f"[ERROR] Gagal menghentikan generator: {e}")

@socketio.on("mouse_control")
def handle_mouse_control(data):
    if not pyautogui:
        return
    screen_w, screen_h = pyautogui.size()
    action = data.get("action")
    x = int(data.get("x", 0) * screen_w)
    y = int(data.get("y", 0) * screen_h)

    if action == "move":
        pyautogui.moveTo(x, y)
    elif action == "click":
        button = data.get("button", "left")
        pyautogui.click(x=x, y=y, button=button)
    elif action == "dblclick":
        pyautogui.doubleClick(x=x, y=y)
    elif action == "mousedown":
        button = data.get("button", "left")
        pyautogui.mouseDown(x=x, y=y, button=button)
    elif action == "mouseup":
        button = data.get("button", "left")
        pyautogui.mouseUp(x=x, y=y, button=button)
    elif action == "scroll":
        delta = int(data.get("deltaY", 0))
        pyautogui.scroll(-delta * 2)

@socketio.on("keyboard_control")
def handle_keyboard_control(data):
    if not pyautogui:
        return
    key = data.get("key")
    text = data.get("text")
    if text:
        pyautogui.write(text)
    elif key:
        key_map = {
            "Enter": "enter", "Backspace": "backspace", "Tab": "tab",
            "Escape": "esc", "ArrowUp": "up", "ArrowDown": "down",
            "ArrowLeft": "left", "ArrowRight": "right", "Delete": "delete"
        }
        pyautogui.press(key_map.get(key, key.lower()))

if __name__ == "__main__":
    ensure_and_load_model()
    print("=" * 60)
    print(f"[INFO] Server berjalan di http://127.0.0.1:8000")
    print("=" * 60)
    socketio.run(app, host="0.0.0.0", port=8000, debug=False)
