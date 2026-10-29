import os
import sys
import time
import json
import uuid
import base64
import ctypes
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
    pyautogui.PAUSE = 0.005
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
# WIN32 SETUP — DPI + SendInput structures
# ==============================================================================
if os.name == "nt":
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# SendInput structures
INPUT_MOUSE    = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE        = 0x0001
MOUSEEVENTF_LEFTDOWN    = 0x0002
MOUSEEVENTF_LEFTUP      = 0x0004
MOUSEEVENTF_RIGHTDOWN   = 0x0008
MOUSEEVENTF_RIGHTUP     = 0x0010
MOUSEEVENTF_MIDDLEDOWN  = 0x0020
MOUSEEVENTF_MIDDLEUP    = 0x0040
MOUSEEVENTF_WHEEL       = 0x0800
MOUSEEVENTF_HWHEEL      = 0x1000
MOUSEEVENTF_ABSOLUTE    = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_UNICODE     = 0x0004

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT_UNION)]

def _send_input(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

def _make_mouse_input(flags, dx=0, dy=0, data=0):
    mi = MOUSEINPUT(dx=dx, dy=dy, mouseData=data, dwFlags=flags, time=0,
                    dwExtraInfo=ctypes.pointer(ctypes.c_ulong(0)))
    return INPUT(type=INPUT_MOUSE, _input=_INPUT_UNION(mi=mi))

def _make_key_input(vk, flags=0, scan=0):
    ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0,
                    dwExtraInfo=ctypes.pointer(ctypes.c_ulong(0)))
    return INPUT(type=INPUT_KEYBOARD, _input=_INPUT_UNION(ki=ki))

# VK codes
VK_MAP = {
    "Enter": 0x0D, "Return": 0x0D,
    "Backspace": 0x08, "Tab": 0x09, "Escape": 0x1B, "Esc": 0x1B,
    "Delete": 0x2E, "Insert": 0x2D, "Home": 0x24, "End": 0x23,
    "PageUp": 0x21, "PageDown": 0x22,
    "ArrowUp": 0x26, "ArrowDown": 0x28, "ArrowLeft": 0x25, "ArrowRight": 0x27,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "PrintScreen": 0x2C, "ScrollLock": 0x91, "Pause": 0x13,
    "CapsLock": 0x14, "NumLock": 0x90,
    "Shift": 0x10, "Control": 0x11, "Alt": 0x12,
    "Meta": 0x5B, "Win": 0x5B,
    " ": 0x20, "Space": 0x20,
}

EXTENDED_KEYS = {0x26, 0x28, 0x25, 0x27, 0x2E, 0x2D, 0x24, 0x23, 0x21, 0x22, 0x5B}

def send_vk(vk, down=True):
    flags = 0
    if not down:
        flags |= KEYEVENTF_KEYUP
    if vk in EXTENDED_KEYS:
        flags |= KEYEVENTF_EXTENDEDKEY
    _send_input(_make_key_input(vk, flags))

def send_unicode_char(ch, down=True):
    flags = KEYEVENTF_UNICODE | (0 if down else KEYEVENTF_KEYUP)
    _send_input(_make_key_input(0, flags, scan=ord(ch)))

def press_vk_with_modifiers(vk, ctrl=False, alt=False, shift=False, meta=False):
    mods = []
    if ctrl:  mods.append(0x11)
    if alt:   mods.append(0x12)
    if shift: mods.append(0x10)
    if meta:  mods.append(0x5B)
    for m in mods:
        send_vk(m, down=True)
    send_vk(vk, down=True)
    send_vk(vk, down=False)
    for m in reversed(mods):
        send_vk(m, down=False)

# ==============================================================================
# SCREEN METRICS
# ==============================================================================
def get_screen_metrics():
    if os.name == "nt":
        try:
            w = ctypes.windll.user32.GetSystemMetrics(0)
            h = ctypes.windll.user32.GetSystemMetrics(1)
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
    if pyautogui:
        return pyautogui.size()
    return 1920, 1080

def win_set_cursor(x, y):
    screen_w, screen_h = get_screen_metrics()
    abs_x = int(x * 65535 / max(screen_w - 1, 1))
    abs_y = int(y * 65535 / max(screen_h - 1, 1))
    _send_input(_make_mouse_input(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
                                   dx=abs_x, dy=abs_y))

def win_mouse_event(flags, data=0):
    _send_input(_make_mouse_input(flags, data=data))

# ==============================================================================
# MODEL AI
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
        print("[INFO] Model belum ada. Menjalankan ai.py untuk download...")
        res_ai = subprocess.run([sys.executable, os.path.join(BASE_DIR, "ai.py")])
        if res_ai.returncode != 0:
            print("[WARN] ai.py selesai dengan kode peringatan.")
        print("[INFO] Menjalankan fix_config.py...")
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "fix_config.py")])

    print(f"[INFO] Memuat tokenizer dan model dari: {MODEL_DIR}")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        use_cuda = torch.cuda.is_available()
        print(f"[INFO] CUDA: {'AKTIF' if use_cuda else 'TIDAK TERSEDIA (CPU)'}")
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_DIR,
            torch_dtype=torch.float16 if use_cuda else torch.float32,
            device_map="auto" if use_cuda else None
        )
        model_status = {"loaded": True, "message": "Model AI Lokal Siap Digunakan"}
        print("[INFO] Model AI berhasil dimuat!")
        socketio.emit("model_status", model_status)
    except Exception as e:
        model_status = {"loaded": False, "message": f"Gagal memuat model: {e}"}
        print(f"[ERROR] {model_status['message']}")
        socketio.emit("model_status", model_status)

# ==============================================================================
# MULTI TERMINAL — PowerShell binary mode with robust reader
# ==============================================================================
terminals = {}

def start_terminal_session(term_id=None, name=None):
    if term_id is None:
        term_id = str(uuid.uuid4())[:8]
    if name is None:
        name = f"Terminal {len(terminals) + 1}"

    proc = subprocess.Popen(
        ["powershell.exe", "-NoLogo", "-NoExit", "-Command", "-"],
        cwd=BASE_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,  # unbuffered binary
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    )

    terminals[term_id] = {"process": proc, "name": name, "logs": ""}

    def reader():
        buf = b""
        while True:
            try:
                chunk = proc.stdout.read(1)
                if not chunk:
                    break
                buf += chunk
                # Try to decode accumulated buffer (UTF-8 may span multiple bytes)
                try:
                    text = buf.decode("utf-8", errors="replace")
                    buf = b""
                    if term_id in terminals:
                        terminals[term_id]["logs"] = (terminals[term_id]["logs"] + text)[-300000:]
                    socketio.emit("terminal_output", {"term_id": term_id, "data": text})
                except Exception:
                    pass
            except Exception:
                break

    threading.Thread(target=reader, daemon=True).start()

    # Initial interactive prompt so terminal is never blank black
    try:
        init_cmd = f"Write-Host '[{name} Aktif - PowerShell]' -ForegroundColor Cyan; Write-Host ('Direktori: ' + (Get-Location).Path) -ForegroundColor DarkGray; Write-Host ''\n"
        proc.stdin.write(init_cmd.encode("utf-8"))
        proc.stdin.flush()
    except Exception:
        pass

    return term_id, name

def write_terminal(tid, cmd):
    if tid not in terminals:
        return
    proc = terminals[tid]["process"]
    if proc.stdin and proc.poll() is None:
        try:
            proc.stdin.write((cmd + "\n").encode("utf-8"))
            proc.stdin.flush()
        except Exception as e:
            err = f"[ERROR] {e}\r\n"
            if tid in terminals:
                terminals[tid]["logs"] += err
            socketio.emit("terminal_output", {"term_id": tid, "data": err})

# ==============================================================================
# SCREEN STREAMING
# ==============================================================================
screen_active_clients = 0
screen_streaming_enabled = False

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
    img.save(buffer, format="JPEG", quality=65)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def screen_stream_worker():
    while True:
        if screen_streaming_enabled and screen_active_clients > 0:
            try:
                frame_data = capture_screen()
                socketio.emit("screen_frame", {"image": frame_data})
            except Exception:
                pass
            time.sleep(0.05)
        else:
            time.sleep(0.3)

threading.Thread(target=screen_stream_worker, daemon=True).start()

# ==============================================================================
# API ENDPOINTS
# ==============================================================================
@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/connection", methods=["GET"])
def connection():
    return jsonify({
        "status": "ok",
        "message": "Server API Siap",
        "model_loaded": model_status["loaded"],
        "model_message": model_status["message"]
    })

@app.route("/api/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    body = request.get_json(force=True, silent=True) or {}
    username = (request.form.get("username") or body.get("username", "") or request.values.get("username", "")).strip()
    password = (request.form.get("password") or body.get("password", "") or request.values.get("password", "")).strip()
    print(f"[AUTH ATTEMPT] username='{username}', password_length={len(password)}")
    if username.lower() == "husain" and password == "password_skripsi_aman":
        return jsonify({"access_token": "skripsi_jwt_token_husain_2026", "token_type": "bearer"})
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
    return jsonify({"text": generated_text, "response": generated_text, "generated_text": generated_text})

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
    return jsonify({"total": total, "page": page, "limit": limit, "rows": displayed})

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
    term_list = [{"id": k, "name": v["name"], "logs": v.get("logs", "")} for k, v in terminals.items()]
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
    term_list = [{"id": k, "name": v["name"], "logs": v.get("logs", "")} for k, v in terminals.items()]
    socketio.emit("terminals_list", {"terminals": term_list})
    emit("terminal_created", {"id": tid, "name": name, "logs": terminals[tid].get("logs", "")})

@socketio.on("close_terminal")
def handle_close_terminal(data):
    tid = data.get("term_id")
    if tid in terminals:
        try:
            terminals[tid]["process"].terminate()
        except Exception:
            pass
        del terminals[tid]
        term_list = [{"id": k, "name": v["name"], "logs": v.get("logs", "")} for k, v in terminals.items()]
        socketio.emit("terminals_list", {"terminals": term_list})

@socketio.on("terminal_input")
def handle_terminal_input(data):
    tid = data.get("term_id")
    cmd = data.get("command", "")
    if tid:
        write_terminal(tid, cmd)

@socketio.on("run_generator")
def handle_run_generator(data=None):
    tid = (data or {}).get("term_id")
    if not tid or tid not in terminals:
        tid = list(terminals.keys())[0] if terminals else None
    if not tid:
        tid, _ = start_terminal_session("term-1", "Terminal 1")

    cmd = f'& "{sys.executable}" dataset_generator.py'
    write_terminal(tid, cmd)
    socketio.emit("terminal_output", {
        "term_id": tid,
        "data": f"\r\n[Executing: {sys.executable} dataset_generator.py]\r\n"
    })

@socketio.on("stop_generator")
def handle_stop_generator(data=None):
    tid = (data or {}).get("term_id")
    try:
        subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*dataset_generator.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
            capture_output=True
        )
        msg = "\r\n[STOPPED] Proses dataset_generator.py berhasil dihentikan.\r\n"
        target_id = tid if (tid and tid in terminals) else (list(terminals.keys())[0] if terminals else "term-1")
        socketio.emit("terminal_output", {"term_id": target_id, "data": msg})
    except Exception as e:
        print(f"[ERROR] Gagal menghentikan generator: {e}")

# ==============================================================================
# MOUSE CONTROL — Full SendInput, drag, middle, scroll + pinch
# ==============================================================================
@socketio.on("mouse_control")
def handle_mouse_control(data):
    screen_w, screen_h = get_screen_metrics()
    action = data.get("action")
    raw_x = data.get("x", 0)
    raw_y = data.get("y", 0)
    px = int(raw_x * screen_w)
    py = int(raw_y * screen_h)

    if action == "move":
        win_set_cursor(px, py)

    elif action == "mousedown":
        btn = data.get("button", "left")
        win_set_cursor(px, py)
        if btn == "right":
            win_mouse_event(MOUSEEVENTF_RIGHTDOWN)
        elif btn == "middle":
            win_mouse_event(MOUSEEVENTF_MIDDLEDOWN)
        else:
            win_mouse_event(MOUSEEVENTF_LEFTDOWN)

    elif action == "mouseup":
        btn = data.get("button", "left")
        win_set_cursor(px, py)
        if btn == "right":
            win_mouse_event(MOUSEEVENTF_RIGHTUP)
        elif btn == "middle":
            win_mouse_event(MOUSEEVENTF_MIDDLEUP)
        else:
            win_mouse_event(MOUSEEVENTF_LEFTUP)

    elif action == "click":
        btn = data.get("button", "left")
        win_set_cursor(px, py)
        if btn == "right":
            win_mouse_event(MOUSEEVENTF_RIGHTDOWN)
            win_mouse_event(MOUSEEVENTF_RIGHTUP)
        elif btn == "middle":
            win_mouse_event(MOUSEEVENTF_MIDDLEDOWN)
            win_mouse_event(MOUSEEVENTF_MIDDLEUP)
        else:
            win_mouse_event(MOUSEEVENTF_LEFTDOWN)
            win_mouse_event(MOUSEEVENTF_LEFTUP)

    elif action == "dblclick":
        win_set_cursor(px, py)
        win_mouse_event(MOUSEEVENTF_LEFTDOWN)
        win_mouse_event(MOUSEEVENTF_LEFTUP)
        time.sleep(0.035)
        win_mouse_event(MOUSEEVENTF_LEFTDOWN)
        win_mouse_event(MOUSEEVENTF_LEFTUP)

    elif action == "scroll":
        delta_y = float(data.get("deltaY", 0))
        delta_x = float(data.get("deltaX", 0))
        if abs(delta_y) >= abs(delta_x):
            ticks = int(-delta_y * 1.2)
            win_mouse_event(MOUSEEVENTF_WHEEL, data=ticks & 0xFFFFFFFF)
        else:
            ticks = int(delta_x * 1.2)
            win_mouse_event(MOUSEEVENTF_HWHEEL, data=ticks & 0xFFFFFFFF)

    elif action == "scroll_zoom":
        # Pinch-to-zoom simulation: Ctrl + Wheel
        delta = float(data.get("delta", 0))
        ticks = int(delta * 120)
        send_vk(0x11, down=True)   # Ctrl down
        win_mouse_event(MOUSEEVENTF_WHEEL, data=ticks & 0xFFFFFFFF)
        send_vk(0x11, down=False)  # Ctrl up

# ==============================================================================
# KEYBOARD CONTROL — Full VK, unicode, modifiers, F1-F12, Win key
# ==============================================================================
@socketio.on("keyboard_control")
def handle_keyboard_control(data):
    key = data.get("key", "")
    text = data.get("text")
    modifiers = data.get("modifiers") or {}
    ctrl  = modifiers.get("ctrl", False)
    alt   = modifiers.get("alt", False)
    shift = modifiers.get("shift", False)
    meta  = modifiers.get("meta", False)

    # Named key → VK
    vk = VK_MAP.get(key)

    # Single printable character with modifier
    if not vk and len(key) == 1:
        vk = ctypes.windll.user32.VkKeyScanW(ord(key)) & 0xFF

    if vk:
        press_vk_with_modifiers(vk, ctrl=ctrl, alt=alt, shift=shift, meta=meta)
        return

    # Pure text input (no modifiers)
    if text and not ctrl and not alt and not meta:
        for ch in text:
            send_unicode_char(ch, down=True)
            send_unicode_char(ch, down=False)

if __name__ == "__main__":
    # Start model loading in background so HTTP/WebSocket server starts immediately
    threading.Thread(target=ensure_and_load_model, daemon=True).start()
    print("=" * 60)
    print(f"[INFO] Server berjalan di http://127.0.0.1:8000")
    print("=" * 60)
    socketio.run(app, host="0.0.0.0", port=8000, debug=False)
