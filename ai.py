import os
import sys
from huggingface_hub import snapshot_download

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models", "Qwen2.5-3B-Instruct")

def main():
    print("=" * 60)
    print("SISTEM DOWNLOAD DAN PENYIMPANAN MODEL LOKAL")
    print(f"Target Model: {MODEL_ID}")
    print(f"Folder Lokal: {MODEL_DIR}")
    print("=" * 60)

    os.makedirs(MODEL_DIR, exist_ok=True)

    has_safetensors = False
    if os.path.exists(MODEL_DIR):
        files = os.listdir(MODEL_DIR)
        has_safetensors = any(f.endswith('.safetensors') for f in files)

    if has_safetensors and os.path.exists(os.path.join(MODEL_DIR, "config.json")):
        print(f"[INFO] File model sudah lengkap di: {MODEL_DIR}")
        print("[INFO] Melewati proses download.")
        return 0

    print(f"[INFO] Memulai download file model dari Hugging Face ke: {MODEL_DIR}")
    print("[INFO] Harap tunggu sampai proses selesai 100%...")
    try:
        snapshot_download(
            repo_id=MODEL_ID,
            local_dir=MODEL_DIR,
            local_dir_use_symlinks=False,
            resume_download=True
        )
        print(f"\n[INFO] Sukses! Seluruh file model berhasil disimpan di: {MODEL_DIR}")
        return 0
    except Exception as e:
        print(f"\n[ERROR] Gagal mendownload model: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
