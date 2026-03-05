"""
BTSO Şirket Scraper — Tam Kapsam Garantili
--------------------------------------------
Her sayfa başarılı olana kadar tekrar dener.
Tüm komitelerin tüm sayfaları eksiksiz çekilir.
Sayfa bazlı progress takibi ile kaldığı yerden devam eder.
"""

import os
import io
import csv
import time
import json
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from PIL import Image
from bs4 import BeautifulSoup
from captcha_model import load_model, predict_captcha


# ============ AYARLAR ============
MAX_CONCURRENT = 12         # Toplam eşzamanlı HTTP bağlantı
KOMITE_WORKERS = 3          # Eşzamanlı komite
PAGE_WORKERS = 6            # Komite içi eşzamanlı sayfa

BASE_URL = "https://www.btso.org.tr"
CAPTCHA_URL = f"{BASE_URL}/include/aspcaptcha.asp"
MEMBERS_URL = f"{BASE_URL}/?page=members/members.asp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.6778.86 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

import sys

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
BUNDLE_DIR = getattr(sys, '_MEIPASS', BASE_DIR)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "sirketler.csv")
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "progress.json")
DATASET_DIR = os.path.join(BUNDLE_DIR, "dataset")
DATASET_IMAGES = os.path.join(BASE_DIR, "dataset", "images")
DATASET_LABELS = os.path.join(BUNDLE_DIR, "dataset", "labels.csv")

# Thread-safe
csv_lock = threading.Lock()
dataset_lock = threading.Lock()
progress_lock = threading.Lock()
print_lock = threading.Lock()
stop_event = threading.Event()
connection_sem = threading.Semaphore(MAX_CONCURRENT)

captcha_model_data = None
stats_lock = threading.Lock()
stats = {
    "komite_ok": 0, "komite_fail": 0,
    "total_companies": 0, "total_pages": 0,
    "captcha_attempts": 0, "captcha_success": 0,
    "learned": 0,
}


def inc_stat(key, val=1):
    with stats_lock:
        stats[key] += val


def log(msg):
    with print_lock:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def setup():
    global captcha_model_data
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DATASET_IMAGES, exist_ok=True)
    # DB init
    import database as dbmod
    dbmod.init_db()
    captcha_model_data = load_model()
    log(f"Model yüklendi: {captcha_model_data.get('model_name','KNN')} "
        f"({captcha_model_data['train_samples']} örnek, "
        f"CV: {captcha_model_data.get('cv_accuracy', 0):.1f}%)")


def decode_resp(resp):
    return resp.content.decode("iso-8859-9", errors="replace")


def fix_enc(text):
    for bad, good in {"\u00dd":"İ","\u00fd":"ı","\u00de":"Ş","\u00fe":"ş","\u00d0":"Ğ","\u00f0":"ğ"}.items():
        text = text.replace(bad, good)
    return text


def solve_captcha(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    return predict_captcha(img, captcha_model_data)


def save_learned(image_bytes, solution):
    with dataset_lock:
        idx = 1
        for f in os.listdir(DATASET_IMAGES):
            try:
                n = int(f.replace("captcha_", "").replace(".png", ""))
                idx = max(idx, n + 1)
            except:
                pass
        fname = f"captcha_{idx:03d}.png"
        Image.open(io.BytesIO(image_bytes)).save(os.path.join(DATASET_IMAGES, fname))
        with open(DATASET_LABELS, "a", newline="") as f:
            csv.writer(f).writerow([fname, solution])
        inc_stat("learned")


# ============ PROGRESS ============
# progress yapısı:
# {
#   "completed_komites": {"01. GRUP": {"total_pages": 36, "fetched_pages": [1,2,...,36]}},
#   "failed_pages": {"01. GRUP": [5, 12]}  -- sonraki run'da tekrar denenecek
# }

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"completed_komites": {}, "failed_pages": {}}


def save_progress(progress):
    with progress_lock:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)


def is_komite_done(progress, kv):
    """Komite tamamen tamamlanmış mı?"""
    info = progress.get("completed_komites", {}).get(kv)
    if not info:
        return False
    total = info.get("total_pages", 0)
    fetched = info.get("fetched_pages", [])
    return total > 0 and len(fetched) >= total


def mark_page_done(progress, kv, page, total_pages):
    """Sayfayı tamamlanmış olarak işaretle"""
    with progress_lock:
        if kv not in progress.setdefault("completed_komites", {}):
            progress["completed_komites"][kv] = {"total_pages": total_pages, "fetched_pages": []}
        info = progress["completed_komites"][kv]
        info["total_pages"] = total_pages
        if page not in info["fetched_pages"]:
            info["fetched_pages"].append(page)
            info["fetched_pages"].sort()


def get_missing_pages(progress, kv):
    """Eksik sayfaları döndür"""
    info = progress.get("completed_komites", {}).get(kv)
    if not info:
        return None  # Komite hiç başlamamış
    total = info.get("total_pages", 0)
    fetched = set(info.get("fetched_pages", []))
    return [p for p in range(1, total + 1) if p not in fetched]


# ============ SAYFA ÇEKİCİ ============

def is_success(html):
    if "Arama Sonucu" in html:
        return True
    soup = BeautifulSoup(html, "lxml")
    ps = soup.find("select", {"name": "kayitaraligi"})
    if ps and len(ps.find_all("option")) > 1:
        return True
    return len(html) > 52000


def parse_page(html):
    soup = BeautifulSoup(html, "lxml")
    companies = []
    result_table = None
    for h2 in soup.find_all("h2"):
        if "Arama" in h2.get_text():
            result_table = h2.find_next("table")
            break
    if not result_table:
        for t in soup.find_all("table"):
            rows = t.find_all("tr", recursive=False)
            if len(rows) > 3:
                first = rows[0].find_all("td", recursive=False)
                if len(first) == 2 and ("Firma" in first[0].get_text() or "nvan" in first[0].get_text()):
                    result_table = t
                    break
    if result_table:
        for row in result_table.find_all("tr", recursive=False)[1:]:
            cells = row.find_all("td", recursive=False)
            if len(cells) >= 2:
                unvan = fix_enc(cells[0].get_text(strip=True))
                tarih = cells[1].get_text(strip=True)
                if unvan:
                    companies.append({"unvan": unvan, "kayit_tarihi": tarih})
    ps = soup.find("select", {"name": "kayitaraligi"})
    return companies, len(ps.find_all("option")) if ps else 1


def save_companies(companies, kv, kt, page):
    """Şirketleri doğrudan SQLite veritabanına kaydet"""
    import database as dbmod
    batch = []
    for c in companies:
        batch.append({
            "komite_kodu": kv,
            "komite_adi": fix_enc(kt),
            "firma_unvani": c["unvan"],
            "kayit_tarihi": c.get("kayit_tarihi", ""),
            "sayfa": page,
        })
    with csv_lock:
        dbmod.add_companies_batch(batch)


def fetch_page_guaranteed(komite_value, page):
    """
    Sayfa başarılı olana kadar SONSUZ dene.
    Sadece Ctrl+C ile durdurulabilir.
    """
    attempt = 0
    backoff = 1

    while not stop_event.is_set():
        attempt += 1
        connection_sem.acquire()
        try:
            s = requests.Session()
            s.headers.update(HEADERS)
            s.get(MEMBERS_URL, timeout=15)

            r = s.get(CAPTCHA_URL, headers={"Referer": MEMBERS_URL}, timeout=10)
            if r.status_code != 200 or len(r.content) < 100:
                time.sleep(0.5)
                continue

            inc_stat("captcha_attempts")
            solution = solve_captcha(r.content)
            if not solution or len(solution) != 6:
                continue

            resp = s.post(MEMBERS_URL, data={
                "kurumunvani": "", "meslekgruptanimi": komite_value,
                "kayitaraligi": str(page), "strCAPTCHA": solution, "submit": "Ara",
            }, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": BASE_URL, "Referer": MEMBERS_URL,
                "Upgrade-Insecure-Requests": "1",
            }, timeout=15)

            html = decode_resp(resp)
            if is_success(html):
                inc_stat("captcha_success")
                save_learned(r.content, solution)
                backoff = 1  # Reset backoff
                return parse_page(html)

        except requests.exceptions.Timeout:
            time.sleep(min(backoff, 5))
            backoff = min(backoff * 1.5, 10)
        except requests.exceptions.ConnectionError:
            time.sleep(min(backoff, 10))
            backoff = min(backoff * 2, 15)
        except Exception:
            time.sleep(1)
        finally:
            connection_sem.release()

        # Her 30 denemede bir uyar
        if attempt % 30 == 0:
            log(f"  ⚠ {komite_value} s.{page}: {attempt} deneme, hala deniyor...")

    return None, 0  # Sadece Ctrl+C ile


def scrape_komite(komite, progress):
    """Bir komitenin TÜM sayfalarını eksiksiz çek"""
    if stop_event.is_set():
        return

    kv, kt = komite["value"], komite["text"]

    # Zaten tamamen tamamlanmış mı?
    if is_komite_done(progress, kv):
        return

    log(f"🔍 {kv}: {fix_enc(kt)[:50]}...")

    # Hangi sayfalar eksik?
    missing = get_missing_pages(progress, kv)

    if missing is None:
        # Hiç başlamamış — ilk sayfayı çek, toplam sayfa öğren
        companies, total_pages = fetch_page_guaranteed(kv, 1)
        if companies is None:
            return  # Ctrl+C

        save_companies(companies, kv, kt, 1)
        mark_page_done(progress, kv, 1, total_pages)
        save_progress(progress)
        log(f"📄 {kv}: 1/{total_pages} ({len(companies)} şirket)")

        missing = list(range(2, total_pages + 1))
    else:
        total_pages = progress["completed_komites"][kv]["total_pages"]
        fetched_count = len(progress["completed_komites"][kv]["fetched_pages"])
        log(f"📄 {kv}: {fetched_count}/{total_pages} zaten çekilmiş, {len(missing)} eksik")

    if not missing:
        # Tüm sayfalar zaten çekilmiş
        inc_stat("komite_ok")
        log(f"✅ {kv}: tamamlandı (zaten)")
        return

    # Eksik sayfaları paralel çek
    total_c = 0
    with ThreadPoolExecutor(max_workers=PAGE_WORKERS) as executor:
        futures = {executor.submit(fetch_page_guaranteed, kv, p): p for p in missing}

        for future in as_completed(futures):
            if stop_event.is_set():
                save_progress(progress)
                return

            p = futures[future]
            try:
                comps, tp = future.result()
                if comps is not None:
                    save_companies(comps, kv, kt, p)
                    mark_page_done(progress, kv, p, total_pages)
                    total_c += len(comps)
                    inc_stat("total_pages")

                    fetched = len(progress["completed_komites"][kv]["fetched_pages"])
                    if fetched % 10 == 0 or fetched == total_pages:
                        log(f"  {kv}: {fetched}/{total_pages} sayfa ({total_c} şirket)")
                        save_progress(progress)

            except Exception as e:
                log(f"  ⚠ {kv} s.{p} hata: {str(e)[:40]}")

    # Komite tamamlandı mı kontrol et
    if is_komite_done(progress, kv):
        inc_stat("komite_ok")
        fetched = len(progress["completed_komites"][kv]["fetched_pages"])
        log(f"✅ {kv}: {total_pages} sayfa TAMAMEN çekildi")
    else:
        missing_now = get_missing_pages(progress, kv)
        log(f"⚠  {kv}: {len(missing_now)} sayfa hala eksik (Ctrl+C ile durduruldu?)")

    save_progress(progress)


def get_komite_list():
    s = requests.Session()
    s.headers.update(HEADERS)
    resp = s.get(MEMBERS_URL, timeout=15)
    html = resp.content.decode("iso-8859-9", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    sel = soup.find("select", {"name": "meslekgruptanimi"})
    return [{"value": o.get("value","").strip(), "text": o.get_text(strip=True)}
            for o in sel.find_all("option") if o.get("value","").strip()] if sel else []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--komite", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int, default=KOMITE_WORKERS)
    args = parser.parse_args()

    setup()

    print("=" * 60)
    print("  BTSO Şirket Scraper (Tam Kapsam Garantili)")
    print("=" * 60)

    komiteler = get_komite_list()
    log(f"📋 {len(komiteler)} komite")

    progress = load_progress() if args.resume else {"completed_komites": {}, "failed_pages": {}}

    # Durum özeti
    done_count = sum(1 for kv in progress.get("completed_komites", {}) if is_komite_done(progress, kv))
    partial_count = len(progress.get("completed_komites", {})) - done_count
    if done_count:
        log(f"📊 {done_count} komite tamamen tamamlanmış")
    if partial_count:
        log(f"📊 {partial_count} komite kısmen çekilmiş (devam edilecek)")

    if args.komite > 0:
        komiteler = komiteler[args.komite - 1:]

    remaining = [k for k in komiteler if not is_komite_done(progress, k["value"])]
    log(f"🚀 {len(remaining)} komite çekilecek | {args.workers} komite-thread | "
        f"{PAGE_WORKERS} sayfa-thread | max {MAX_CONCURRENT} bağlantı")
    log(f"📁 {OUTPUT_CSV}")
    log("─" * 60)

    start = time.time()
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(scrape_komite, k, progress): k for k in remaining}
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    log(f"❌ {futures[f]['value']}: {str(e)[:60]}")
    except KeyboardInterrupt:
        log("🛑 Durduruluyor... İlerleme kaydediliyor.")
        stop_event.set()
        time.sleep(2)  # Thread'lerin durmasını bekle
        save_progress(progress)

    elapsed = time.time() - start

    # Final rapor
    csv_lines = 0
    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
            csv_lines = sum(1 for _ in f) - 1

    done_final = sum(1 for kv in progress.get("completed_komites", {}) if is_komite_done(progress, kv))
    partial_final = len(progress.get("completed_komites", {})) - done_final
    total_komites = len(get_komite_list())

    print(f"\n{'='*60}")
    print(f"  SONUÇ ({int(elapsed//60)}dk {int(elapsed%60)}sn)")
    print(f"  ✅ Tamamen çekildi:  {done_final}/{total_komites} komite")
    if partial_final:
        print(f"  🔄 Kısmen çekildi:  {partial_final} komite")
    print(f"  🏢 Şirket:           {csv_lines}")
    print(f"  📄 Sayfa:            {stats['total_pages']}")
    print(f"  🔑 CAPTCHA:          {stats['captcha_success']}/{stats['captcha_attempts']}")
    if stats['captcha_attempts'] > 0:
        rate = stats['captcha_success'] / stats['captcha_attempts'] * 100
        print(f"  📊 Başarı oranı:     {rate:.1f}%")
    print(f"  🧠 Öğrenilen:        {stats['learned']}")
    print(f"  📁 {OUTPUT_CSV}")
    if partial_final or done_final < total_komites:
        print(f"\n  💡 Kaldığı yerden devam: python scraper.py --resume")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
