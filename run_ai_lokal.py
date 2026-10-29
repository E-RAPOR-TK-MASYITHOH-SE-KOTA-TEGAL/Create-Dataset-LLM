import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_DIR = "./models/Qwen2.5-3B-Instruct"

print("=" * 60)
print("MENJALANKAN MODEL AI LOKAL (OFFLINE)")
print("=" * 60)

# Validasi keberadaan folder dan file model
if not os.path.exists(MODEL_DIR):
    print(f"[ERROR] Folder model tidak ditemukan di: {MODEL_DIR}")
    exit(1)

files = os.listdir(MODEL_DIR)
if not any(f.endswith('.safetensors') for f in files):
    print(f"[ERROR] File .safetensors tidak ditemukan di {MODEL_DIR}!")
    print("Harap jalankan 'py ai.py' sampai selesai terlebih dahulu.")
    exit(1)

print(f"[INFO] Memuat tokenizer dan model dari folder lokal: {MODEL_DIR}...")
print("[INFO] Harap tunggu sebentar...")

# Memuat dari direktori lokal
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR,
    dtype=torch.float16,
    device_map="auto"
)

print("[INFO] Model berhasil dimuat dan siap digunakan!\n")
print("-" * 60)

# Loop Chat Interaktif
while True:
    try:
        prompt = input("\nMasukkan Prompt Anda (ketik 'keluar' untuk berhenti): ")
        if prompt.lower() in ["keluar", "exit", "quit"]:
            print("Keluar dari program. Sampai jumpa!")
            break
        
        if not prompt.strip():
            continue

        print("\nSedang memproses jawaban...")

        messages = [
            {"role": "user", "content": prompt}
        ]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

        generated_ids = model.generate(
            **model_inputs,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.7,
            top_p=0.9
        )
        
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]

        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

        print("\n--- JAWABAN AI ---")
        print(response)
        print("-" * 40)

    except KeyboardInterrupt:
        print("\nProgram dihentikan oleh pengguna.")
        break