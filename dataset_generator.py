import json
import os
import random
import re
import sys
import requests
from tqdm.auto import tqdm

# Force UTF-8 stdout/stderr on Windows cmd to prevent UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ==============================================================================
# FUNGSI CEK KONEKSI KE API LOKAL (/connection)
# ==============================================================================
def cek_koneksi_api():
    url = "http://127.0.0.1:8000/connection"
    print("[CHECK] Mengecek koneksi ke Server API Lokal (http://127.0.0.1:8000)...")
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"[SUCCESS] KONEKSI BERHASIL: {data.get('message')}")
            if not data.get("model_loaded"):
                print(f"[WAIT] Status Model: {data.get('model_message')}")
            return True
        else:
            print(f"[WARN] Server merespons dengan status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print("[ERROR] KONEKSI GAGAL: Tidak dapat terhubung ke server lokal. Pastikan 'api_ai.py' sudah berjalan.")
        print(f"Detail Error: {e}")
        return False

# ==============================================================================
# FUNGSI LOGIN UNTUK MENDAPATKAN TOKEN JWT
# ==============================================================================
def login_ke_api(username="husain", password="password_skripsi_aman"):
    url = "http://127.0.0.1:8000/api/login"
    data = {
        "username": username,
        "password": password
    }
    print("[AUTH] Melakukan proses otentikasi (Login) ke server API...")
    try:
        response = requests.post(url, data=data, timeout=5)
        if response.status_code == 200:
            token = response.json().get("access_token")
            print("[SUCCESS] LOGIN BERHASIL: Akses Token berhasil didapatkan.")
            return token
        else:
            print(f"[ERROR] LOGIN GAGAL ({response.status_code}): {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Gagal memanggil endpoint login: {e}")
        return None

# ==============================================================================
# FUNGSI KONEKSI KE API LOKAL (127.0.0.1:8000/generate)
# ==============================================================================
def rangkai_kalimat(prompt, token, max_tokens=3800, suhu=0.85, top_p=0.9):
    url = "http://127.0.0.1:8000/generate"
    payload = {
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": suhu,
        "top_p": top_p
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=1500)
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, dict):
                return result.get("text") or result.get("response") or result.get("generated_text") or str(result)
            return str(result)
        else:
            raise Exception(f"API Error Status {response.status_code}: {response.text}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Gagal terhubung ke server lokal (127.0.0.1:8000/generate): {e}")

# ==============================================================================
# 1. BANK TOPIK PENGEMBANGAN NARATIF ALAMI
# ==============================================================================
nama_anak = [
    "Budi", "Aisyah", "Fatih", "Zahra", "Kevin", "Kirana", "Raffa", "Syifa",
    "Arjuna", "Kinara", "Kenzo", "Naura", "Daffa", "Khadijah", "Bima", "Lestari",
    "Aditya", "Nisa", "Hasan", "Husna", "Tari", "Bayu", "Caca", "Doni", "Elang",
    "Farah", "Gilang", "Hani", "Intan", "Jihan", "Maulana", "Nadia", "Omar", "Putri",
    "Rama", "Salsa", "Umar", "Vina", "Wira", "Zidan"
]

data_agama = [
    "khusyuk saat sholat dhuha, hafal surat-surat pendek, doa harian, dan senang mendengarkan kisah nabi",
    "rajin menyiram tanaman sekolah, memberi makan ikan kolam, dan menjaga kebersihan lingkungan kelas",
    "santun dalam berucap, selalu mengucapkan tolong, terima kasih, maaf, dan menyapa guru dengan senyum salam",
    "masih perlu diingatkan dan dibimbing untuk ikut serta dalam rangkaian doa bersama dan wudhu tertib",
    "kadang asyik bermain sendiri saat kegiatan ibadah pagi dan perlu pendekatan lembut agar mau bergabung"
]

data_jatidiri = [
    "mandiri saat makan bekal, memakai sepatu, merapikan alat main sendiri, dan memiliki regulasi emosi yang matang",
    "lincah melompat simpai, menjaga keseimbangan di titian, tangkas berlari, dan motorik halus jemarinya sangat terkoordinasi",
    "mudah bergaul, berempati tinggi, peka membantu teman yang kesulitan, serta suka berbagi perlengkapan bermain",
    "masih pemalu saat berada di keramaian, butuh dorongan untuk memimpin kelompok atau mengutarakan keinginan",
    "mudah menangis atau tantrum saat keinginannya belum terpenuhi, serta masih belajar berbagi mainan favorit"
]

data_steam_seni = [
    "sangat kritis menanyakan fenomena alam, mengelompokkan benda berdasarkan pola, dan lancar berhitung kuantitas 1-20",
    "kreatif mendesain bangunan balok kompleks, memadukan warna cat air secara harmonis, dan senang bernyanyi",
    "cakap mengekspresikan gagasan secara verbal, menyusun kalimat majemuk, dan antusias menyimak buku cerita",
    "mulai mengenali lambang huruf dan angka awal, meski masih memerlukan arahan saat memegang krayon dan gunting",
    "cenderung mudah menyerah saat merangkai puzzle rumit dan belum berminat mencoba eksplorasi bahan alam basah"
]

data_kokurikuler_8dimensi = [
    "proyek kebun mini sekolah: menunjukkan Dimensi Beriman & Akhlak pada Alam, Bergotong Royong, dan Bernalar Kritis",
    "kunjungan sentra batik & gerabah: mengembangkan Dimensi Berkebinekaan Global, Kreatif, dan Menghargai Budaya Lokal",
    "market day cilik: mengasah Dimensi Kemandirian, Komunikasi Efektif, Gotong Royong, dan Nalar Kuantitatif",
    "rekayasa daur ulang botol plastik: melatih Dimensi Bernalar Kritis, Kreativitas Terapan, dan Kepedulian Lingkungan Hidup",
    "pentas tari kreasi tradisional: memupuk Dimensi Berkebinekaan Global, Percaya Diri, Disiplin, dan Kolaborasi Kelompok"
]

FOKUS_AGAMA = [
    "pembiasaan ibadah rutin, adab wudhu dan sholat dhuha berjamaah, serta kefasihan melafalkan doa harian dan surat-surat pendek Al-Qur'an",
    "akhlak mulia kepada sesama teman dan guru, membiasakan 5S (senyum, sapa, salam, sopan, santun) serta berkata tolong, maaf, dan terima kasih",
    "sikap kasih sayang dan kepedulian terhadap lingkungan hidup serta seluruh ciptaan Tuhan dengan merawat tanaman dan menjaga kebersihan",
    "antusiasme ananda saat menyimak kisah-kisah teladan para nabi dan meneladani nilai-nilai kejujuran serta amanah di sekolah",
    "adab makan islami, tertib berdoa sebelum dan sesudah kegiatan, serta kesadaran berbuat kebaikan tanpa pamrih",
    "evaluasi holistik terhadap kematangan spiritual ananda dan internalisasi nilai keimanan sepanjang semester ini"
]

FOKUS_JATI = [
    "kemandirian ananda dalam mengurus diri sendiri, seperti memakai sepatu, merapikan alat makan bekal, dan membereskan mainan ke tempat semula",
    "pengelolaan emosi dan regulasi diri, kemampuan mengutarakan perasaan secara positif, dan sikap sabar menunggu giliran bermain",
    "keterampilan fisik motorik kasar berupa keseimbangan tubuh berjalan di papan titian, kelincahan melompat, serta ketangkasan koordinasi fisik",
    "keterampilan motorik halus dan koordinasi bilateral jemari tangan dalam menggunting pola, meronce manik, dan memegang alat tulis dengan mantap",
    "kemampuan interaksi sosial, kepekaan empati menolong teman yang menangis atau kesulitan, serta kerelaan berbagi alat mainan",
    "rasa percaya diri ananda saat tampil di depan kelas, inisiatif memimpin barisan, serta kemampuan mengenali dan menjaga keamanan diri"
]

FOKUS_STEAM = [
    "kemampuan literasi berbahasa reseptif dan ekspresif, keberanian menceritakan pengalaman pribadi dengan kosakata kaya dan terstruktur",
    "pemahaman logika matematika awal dan numerasi, mengenali konsep perbandingan ukuran, mengurutkan pola, dan menghitung kuantitas benda nyata",
    "kepekaan eksplorasi sains lingkungan, rasa penasaran yang tinggi saat meneliti perubahan benda, mencampur warna, dan mengamati siklus alam",
    "keterampilan rekayasa teknologi sederhana dan pemecahan masalah (problem solving) saat menyusun konstruksi balok bertingkat yang stabil",
    "apresiasi dan kreativitas karya seni rupa, keindahan perpaduan warna lukisan cat air, kecintaan membentuk media lempung, serta gerak tari berirama",
    "daya imajinasi kritis ananda dalam menghubungkan konsep pengetahuan baru dengan fenomena kehidupan sehari-hari"
]

FOKUS_KOKURIKULER = [
    "partisipasi aktif ananda dalam proyek tematik P5 kokurikuler sekolah, menunjukkan kebanggaan dalam belajar kontekstual di luar kelas",
    "integrasi Dimensi Beriman, Bertakwa kepada Tuhan YME, dan Berakhlak Mulia pada Alam melalui aksi nyata kepedulian lingkungan proyek",
    "penerapan Dimensi Bergotong Royong dan Kemandirian, kerja sama yang kompak bersama kawan kelompok tanpa saling bergantung berlebihan",
    "perwujudan Dimensi Bernalar Kritis dan Kreatif dalam menganalisis masalah sederhana proyek dan menghasilkan karya daur ulang orisinal",
    "internalisasi Dimensi Berkebinekaan Global, sikap toleran menghargai perbedaan latar belakang teman, dan apresiasi budaya tradisional",
    "penguatan Dimensi Komunikatif dan Berwawasan Lingkungan yang berkelanjutan dalam membentuk karakter profil pelajar Pancasila"
]

def buat_skenario_holistik():
    nama = random.choice(nama_anak)
    status_rand = random.random()
    if status_rand < 0.40:
        tingkat = "POSITIF (Berkembang Sangat Baik)"
        c_agama = random.choice(data_agama[:3])
        c_jati = random.choice(data_jatidiri[:3])
        c_steam = random.choice(data_steam_seni[:3])
        c_koku = random.choice(data_kokurikuler_8dimensi[:3])
    elif status_rand < 0.80:
        tingkat = "MENENGAH (Mulai Berkembang)"
        c_agama = random.choice(data_agama[2:4])
        c_jati = random.choice(data_jatidiri[2:4])
        c_steam = random.choice(data_steam_seni[2:4])
        c_koku = random.choice(data_kokurikuler_8dimensi[1:4])
    else:
        tingkat = "BUTUH BIMBINGAN (Perlu Perhatian Khusus)"
        c_agama = random.choice(data_agama[3:])
        c_jati = random.choice(data_jatidiri[3:])
        c_steam = random.choice(data_steam_seni[3:])
        c_koku = random.choice(data_kokurikuler_8dimensi[2:])

    semester_rand = random.choice(["Semester 1", "Semester 2", "Semester 1 dan 2"])

    skenario_teks = (
        f"Ananda {nama} memiliki status capaian {tingkat}. "
        f"1. Nilai Agama & Budi Pekerti: {c_agama}. "
        f"2. Jati Diri: {c_jati}. "
        f"3. STEAM & Seni: {c_steam}. "
        f"4. Kokurikuler & 8 Dimensi Profil Lulusan: {c_koku}. "
        f"Fokus Evaluasi & Refleksi: {semester_rand}."
    )
    return skenario_teks, nama, tingkat

def bersihkan_narasi(teks):
    """Membersihkan label 'Paragraf X:', sapaan, dan merapikan spasi enter ganda"""
    # Hapus sapaan pembuka surat jika ada
    teks = re.sub(r'^(Dear|Halo|Hai|Selamat pagi|Assalamualaikum).*?\n', '', teks, flags=re.IGNORECASE).strip()
    # Hapus label seperti "Paragraf 1:", "Paragraf 2:", "Paragraf ke-1:"
    teks = re.sub(r'(?i)(?:^|\n)\s*(?:paragraf|paragraf\s*ke)\s*[-–]?\s*\d+\s*[:\.]?\s*', '\n\n', teks)
    # Hapus tanda bullet atau penomoran di awal baris paragraf
    teks = re.sub(r'(?m)^\s*[\*\-•]\s*', '', teks)
    # Normalkan enter ganda (maksimal 2 enter berturut-turut)
    teks = re.sub(r'\n{3,}', '\n\n', teks)
    return teks.strip()

# ==============================================================================
# 2. EKSEKUSI GENERATOR DATASET
# ==============================================================================
if __name__ == "__main__":
    if not cek_koneksi_api():
        print("\n[ABORT] Proses dibatalkan. Pastikan server sudah berjalan dengan: 'python api_ai.py'")
        exit(1)

    API_TOKEN = login_ke_api()
    if not API_TOKEN:
        print("\n[ABORT] Proses dibatalkan. Otentikasi gagal.")
        exit(1)

    TARGET_JUMLAH_DATA = 2500

    output_dir = "HASIL_DATASET"
    os.makedirs(output_dir, exist_ok=True)
    output_jsonl = os.path.join(output_dir, "synthetic_rapor_dataset.jsonl")

    start_index = 0
    if os.path.exists(output_jsonl):
        with open(output_jsonl, "r", encoding="utf-8") as f:
            start_index = sum(1 for _ in f)
        print(f"[RESUME] File JSONL ditemukan! Melanjutkan dari data ke-{start_index + 1}...")
    else:
        print(f"[NEW] Membuat file JSONL baru di: {output_jsonl}")

    if start_index >= TARGET_JUMLAH_DATA:
        print(f"[DONE] Target {TARGET_JUMLAH_DATA} data sudah tercapai!")
    else:
        print(f"[START] Memulai Generate Narasi Rapor TK Masyithoh (Narasi Alami, Variasi 3-6 Paragraf)...")

        for i in tqdm(range(start_index, TARGET_JUMLAH_DATA), desc="Generate Narasi TK"):
            skenario_dinamis, nama_anak_terpilih, tingkat_capaian = buat_skenario_holistik()

            # Randomize jumlah paragraf per poin (3 sampai 6 paragraf)
            n_agama = random.randint(3, 6)
            n_jati = random.randint(3, 6)
            n_steam = random.randint(3, 6)
            n_koku = random.randint(3, 6)

            panduan_agama = "; lalu uraikan pula tentang ".join(FOKUS_AGAMA[:n_agama])
            panduan_jati = "; lalu uraikan pula tentang ".join(FOKUS_JATI[:n_jati])
            panduan_steam = "; lalu uraikan pula tentang ".join(FOKUS_STEAM[:n_steam])
            panduan_koku = "; lalu uraikan pula tentang ".join(FOKUS_KOKURIKULER[:n_koku])

            prompt_generator = f"""Anda adalah Guru PAUD profesional di TK Masyithoh VII yang sangat ahli menuliskan narasi rapor Kurikulum Merdeka yang PANJANG, HANGAT, NATURAL, MENDALAM, dan MENGALIR INDAH.

Konteks Mentah Observasi Anak:
{skenario_dinamis}

ATURAN STRUKTUR & GAYA BAHASA (WAJIB DIPATUHI SECARA KETAT):
1. DILARANG KERAS mencantumkan kata seperti "Paragraf 1:", "Paragraf 2:", tanda strip (-), atau bullet point di dalam teks narasi! Tuliskan murni berupa paragraf-paragraf deskriptif alami yang dipisahkan oleh baris baru (enter ganda / \n\n).
2. Setiap paragraf harus PANJANG dan MENDETAIL (minimal 4 hingga 6 kalimat deskriptif substantif), menggunakan gaya bahasa guru PAUD yang hangat, apresiatif, edukatif, dan solutif.
3. Jumlah paragraf yang harus Anda hasilkan untuk ananda {nama_anak_terpilih}:
   - Poin 1 (Nilai Agama dan Budi Pekerti): Tuliskan tepat {n_agama} paragraf panjang terpisah \n\n. Topik alur: {panduan_agama}.
   - Poin 2 (Jati Diri): Tuliskan tepat {n_jati} paragraf panjang terpisah \n\n. Topik alur: {panduan_jati}.
   - Poin 3 (DASAR-DASAR LITERASI, MATEMATIKA, SAINS, TEKNOLOGI REKAYASA DAN SENI): Tuliskan tepat {n_steam} paragraf panjang terpisah \n\n. Topik alur: {panduan_steam}.
   - Poin 4 (KO KULIKULER DENGAN 8 DIMENSI PROFIL LULUSAN): Tuliskan tepat {n_koku} paragraf panjang terpisah \n\n. Topik alur: {panduan_koku}.
   - Poin 5 (Refleksi untuk orang tua): Tuliskan tepat 1 paragraf singkat (3-5 kalimat) berisi apresiasi kemitraan dan rekomendasi stimulasi ringan di rumah.

Format Output Wajib (Tuliskan persis struktur ini):
OBSERVASI: [Tuliskan 1-2 kalimat rangkuman kondisi faktual ananda]
NARASI:
1. Nilai Agama dan Budi Pekerti
[Tuliskan {n_agama} paragraf mengalir alami di sini, pisahkan tiap paragraf dengan enter ganda tanpa label]

2. Jati Diri
[Tuliskan {n_jati} paragraf mengalir alami di sini, pisahkan tiap paragraf dengan enter ganda tanpa label]

3. DASAR-DASAR LITERASI, MATEMATIKA, SAINS, TEKNOLOGI REKAYASA DAN SENI
[Tuliskan {n_steam} paragraf mengalir alami di sini, pisahkan tiap paragraf dengan enter ganda tanpa label]

4. KO KULIKULER DENGAN 8 DIMENSI PROFIL LULUSAN
[Tuliskan {n_koku} paragraf mengalir alami di sini, pisahkan tiap paragraf dengan enter ganda tanpa label]

5. Refleksi untuk orang tua
[Tuliskan 1 paragraf singkat refleksi dan saran orang tua di sini]
"""

            try:
                hasil_AI = rangkai_kalimat(prompt_generator, token=API_TOKEN, max_tokens=3800, suhu=0.85, top_p=0.9)

                obs_match = re.search(r'OBSERVASI[\s\*:]+(.*?)(?=NARASI|$)', hasil_AI, re.DOTALL | re.IGNORECASE)
                nar_match = re.search(r'NARASI[\s\*:]+(.*)', hasil_AI, re.DOTALL | re.IGNORECASE)

                if obs_match and nar_match:
                    obs = obs_match.group(1).replace("<|im_end|>", "").strip()
                    nar_raw = nar_match.group(1).replace("<|im_end|>", "").strip()
                    nar = bersihkan_narasi(nar_raw)
                    status = "[SUCCESS]"
                else:
                    obs = "Observasi terdata."
                    nar = bersihkan_narasi(hasil_AI.replace("<|im_end|>", "").strip())
                    status = "[RAW]"

                data_row = {
                    "skenario": skenario_dinamis,
                    "status_capaian": tingkat_capaian,
                    "target_paragraf": {
                        "agama": n_agama,
                        "jati_diri": n_jati,
                        "steam": n_steam,
                        "kokurikuler": n_koku
                    },
                    "observasi": obs,
                    "narasi": nar
                }

                with open(output_jsonl, "a", encoding="utf-8") as f:
                    f.write(json.dumps(data_row, ensure_ascii=False) + "\n")

                tingkat_log = tingkat_capaian.split(" ")[0] 
                tqdm.write(f"[{i+1}/{TARGET_JUMLAH_DATA}] {status} | {tingkat_log} ({n_agama},{n_jati},{n_steam},{n_koku}p) -> Anak: {nama_anak_terpilih}")

            except Exception as e:
                tqdm.write(f"[{i+1}/{TARGET_JUMLAH_DATA}] [ERROR]: {e}")
                continue

    # ==============================================================================
    # 3. PREVIEW HASIL FILE JSONL
    # ==============================================================================
    if os.path.exists(output_jsonl):
        print(f"\n[INFO] Membaca contoh data terakhir dari: {output_jsonl}")
        with open(output_jsonl, "r", encoding="utf-8") as f:
            lines = f.readlines()
            print(f"Total Baris di File JSONL: {len(lines)}")
            if lines:
                print("\nContoh Baris Terakhir:")
                print(json.loads(lines[-1]))
