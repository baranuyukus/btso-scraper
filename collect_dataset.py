"""
BTSO CAPTCHA Dataset Toplama (Gemini AI ile Otomatik)
------------------------------------------------------
Multi-thread olarak CAPTCHA indirir, Gemini Flash ile çözer,
ve dataset'e kaydeder. Ctrl+C ile durdurana kadar çalışır.
"""

import os
import io
import csv
import time
import base64
import threading
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from PIL import Image
from google import genai


# ============ AYARLAR ============
GEMINI_API_KEY = "AIzaSyDUyDm8AN5TN-KMTx9dY35u2tXc0_pYzd0"
GEMINI_MODEL = "gemini-flash-latest"
MAX_WORKERS = 15
RATE_LIMIT_DELAY = 1.0

BASE_URL = "https://www.btso.org.tr"
CAPTCHA_URL = f"{BASE_URL}/include/aspcaptcha.asp"
MEMBERS_URL = f"{BASE_URL}/?page=members/members.asp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.6778.86 Safari/537.36",
}

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
IMAGES_DIR = os.path.join(DATASET_DIR, "images")
LABELS_FILE = os.path.join(DATASET_DIR, "labels.csv")

csv_lock = threading.Lock()
counter_lock = threading.Lock()
stop_event = threading.Event()
stats = {"success": 0, "fail": 0, "total": 0}

# Gemini client (thread-safe)
client = None


def setup():
    global client
    os.makedirs(IMAGES_DIR, exist_ok=True)
    client = genai.Client(api_key=GEMINI_API_KEY)


def get_next_index():
    existing = []
    if os.path.exists(IMAGES_DIR):
        for f in os.listdir(IMAGES_DIR):
            try:
                num = int(f.replace("captcha_", "").replace(".png", ""))
                existing.append(num)
            except:
                pass
    return max(existing) + 1 if existing else 1


def download_captcha():
    session = requests.Session()
    session.headers.update(HEADERS)
    session.get(MEMBERS_URL, timeout=15)
    resp = session.get(CAPTCHA_URL, headers={"Referer": MEMBERS_URL}, timeout=15)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content))
    return img, resp.content


def solve_with_gemini(image_bytes):
    """Gemini Flash ile CAPTCHA çöz"""
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            genai.types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            "Bu bir CAPTCHA görseli. Görseldeki sayıyı oku. "
            "SADECE rakamları yaz, başka hiçbir şey yazma. "
            "Görsel siyah beyaz, noktalı gürültü var. "
            "6 haneli bir rakam olmalı. Sadece o 6 rakamı yaz.",
        ],
    )

    text = response.text.strip()
    digits = re.sub(r"[^0-9]", "", text)
    return digits


def save_label(fname, label):
    with csv_lock:
        write_header = not os.path.exists(LABELS_FILE)
        with open(LABELS_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["filename", "label"])
            writer.writerow([fname, label])


def process_one(idx):
    if stop_event.is_set():
        return None

    try:
        img, raw_bytes = download_captcha()
        solution = solve_with_gemini(raw_bytes)

        if not solution or len(solution) != 6:
            with counter_lock:
                stats["fail"] += 1
                stats["total"] += 1
            return f"  ✗ #{idx}: Geçersiz yanıt: '{solution}'"

        fname = f"captcha_{idx:03d}.png"
        fpath = os.path.join(IMAGES_DIR, fname)
        img.save(fpath)
        save_label(fname, solution)

        with counter_lock:
            stats["success"] += 1
            stats["total"] += 1
            s = stats["success"]

        return f"  ✓ #{idx}: {solution}  (toplam: {s})"

    except Exception as e:
        with counter_lock:
            stats["fail"] += 1
            stats["total"] += 1
        err = str(e).replace("\n", " ")[:100]
        return f"  ✗ #{idx}: {err}"


def main():
    setup()
    start_idx = get_next_index()

    print("=" * 55)
    print("  BTSO CAPTCHA Dataset Toplama (Gemini AI)")
    print("=" * 55)
    print(f"  Model:     {GEMINI_MODEL}")
    print(f"  Threadler: {MAX_WORKERS}")
    print(f"  Başlangıç: #{start_idx}")
    print(f"  Durdurmak için: Ctrl+C")
    print("=" * 55)

    idx = start_idx
    batch_size = MAX_WORKERS

    try:
        while not stop_event.is_set():
            futures = {}
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                for i in range(batch_size):
                    if stop_event.is_set():
                        break
                    future = executor.submit(process_one, idx + i)
                    futures[future] = idx + i

                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        print(result)

            idx += batch_size
            time.sleep(RATE_LIMIT_DELAY)

            with counter_lock:
                s, f, t = stats["success"], stats["fail"], stats["total"]
            print(f"\n  📊 Başarılı: {s} | Başarısız: {f} | Toplam: {t}\n")

    except KeyboardInterrupt:
        print("\n\n🛑 Durduruluyor...")
        stop_event.set()

    print(f"\n{'='*55}")
    print(f"  SONUÇ: {stats['success']} başarılı CAPTCHA")
    print(f"  Dataset: {LABELS_FILE}")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
