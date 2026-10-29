import os
import sys
from transformers import AutoConfig, AutoTokenizer

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models", "Qwen2.5-3B-Instruct")

def main():
    print("=" * 60)
    print("MEMPERBAIKI FILE KONFIGURASI DAN TOKENIZER")
    print("=" * 60)
    os.makedirs(MODEL_DIR, exist_ok=True)
    try:
        print("[INFO] Memvalidasi dan menyimpan konfigurasi model...")
        config = AutoConfig.from_pretrained(MODEL_ID)
        config.save_pretrained(MODEL_DIR)

        print("[INFO] Memvalidasi dan menyimpan tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        tokenizer.save_pretrained(MODEL_DIR)

        print("[INFO] Berhasil! File konfigurasi dan tokenizer telah diperbarui.")
        return 0
    except Exception as e:
        print(f"[ERROR] Gagal memperbarui konfigurasi: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
