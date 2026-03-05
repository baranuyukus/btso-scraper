"""
BTSO CAPTCHA Çözücü + Şirket Scraper
--------------------------------------
Gemini AI ile CAPTCHA çözer, başarısız olursa KNN modeli dener.
Birden fazla denemeyle CAPTCHA'yı sunucuya göndererek doğrular.
"""

import os
import io
import re
import csv
import time
import base64
import requests
from PIL import Image
from google import genai


# ============ AYARLAR ============
GEMINI_API_KEY = "AIzaSyDUyDm8AN5TN-KMTx9dY35u2tXc0_pYzd0"
GEMINI_MODEL = "gemini-flash-latest"
MAX_CAPTCHA_RETRIES = 15

BASE_URL = "https://www.btso.org.tr"
CAPTCHA_URL = f"{BASE_URL}/include/aspcaptcha.asp"
MEMBERS_URL = f"{BASE_URL}/?page=members/members.asp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.6778.86 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

# Gemini client
gemini_client = None


def init_gemini():
    global gemini_client
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def create_session():
    """Yeni session oluştur ve ana sayfayı ziyaret et"""
    session = requests.Session()
    session.headers.update(HEADERS)
    session.get(MEMBERS_URL, timeout=15)
    return session


def download_captcha(session):
    """CAPTCHA görselini indir"""
    resp = session.get(
        CAPTCHA_URL,
        headers={
            "Referer": MEMBERS_URL,
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Dest": "image",
        },
        timeout=15,
    )
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content))
    return img, resp.content


def solve_with_gemini(image_bytes):
    """Gemini ile CAPTCHA çöz"""
    if gemini_client is None:
        init_gemini()

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            genai.types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            "Bu bir CAPTCHA görseli. İçindeki 6 haneli sayıyı oku. "
            "SADECE 6 rakamı yaz, başka hiçbir şey yazma. "
            "Noktalı gürültü var, onu yoksay.",
        ],
    )

    text = response.text.strip()
    digits = re.sub(r"[^0-9]", "", text)
    return digits if len(digits) == 6 else None


def solve_with_model(img):
    """KNN modeli ile CAPTCHA çöz (yedek)"""
    try:
        from captcha_model import load_model, predict_captcha
        model_data = load_model()
        return predict_captcha(img, model_data)
    except Exception:
        return None


def submit_search(session, captcha_text, meslek_grubu="01. GRUP", kayit_araligi="1", kurum_unvani=""):
    """BTSO üye arama formunu gönder"""
    data = {
        "kurumunvani": kurum_unvani,
        "meslekgruptanimi": meslek_grubu,
        "kayitaraligi": kayit_araligi,
        "strCAPTCHA": captcha_text,
        "submit": "Ara",
    }

    resp = session.post(
        MEMBERS_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": BASE_URL,
            "Referer": MEMBERS_URL,
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp


def is_search_successful(html):
    """Arama sonucu geldi mi kontrol et"""
    # "Arama Sonucu" başlığı var mı?
    if "Arama Sonucu" in html or "Arama Sonucu" in html.replace("ý", "ı"):
        return True

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    # Sayfa seçeneği birden fazla mı?
    page_select = soup.find("select", {"name": "kayitaraligi"})
    if page_select:
        options = page_select.find_all("option")
        if len(options) > 1:
            return True

    # Yanıt boyutu kontrolü
    if len(html) > 52000:
        return True

    return False


def solve_captcha_and_submit(meslek_grubu="01. GRUP", kayit_araligi="1"):
    """
    CAPTCHA çözüp form gönder. Başarılı olana kadar dene.
    Returns: (session, response) veya (None, None)
    """
    if gemini_client is None:
        init_gemini()

    for attempt in range(1, MAX_CAPTCHA_RETRIES + 1):
        try:
            # Yeni session her denemede
            session = create_session()

            # CAPTCHA indir
            img, raw_bytes = download_captcha(session)

            # Gemini ile çöz
            solution = solve_with_gemini(raw_bytes)

            if not solution:
                # Model ile dene
                solution = solve_with_model(img)

            if not solution or len(solution) != 6:
                print(f"  [{attempt}] CAPTCHA çözülemedi, tekrar deneniyor...")
                continue

            # Form gönder
            response = submit_search(session, solution, meslek_grubu, kayit_araligi)

            # Başarı kontrolü
            if is_search_successful(response.text):
                print(f"  [{attempt}] ✓ CAPTCHA çözüldü: {solution}")
                return session, response
            else:
                print(f"  [{attempt}] ✗ CAPTCHA yanlış: {solution}")

        except Exception as e:
            print(f"  [{attempt}] Hata: {str(e)[:80]}")

        time.sleep(0.5)

    return None, None


def parse_companies(html):
    """HTML'den şirket bilgilerini çıkar"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    companies = []

    # "Arama Sonucu" başlığını bul ve sonrasındaki tabloyu al
    h2_tags = soup.find_all("h2")
    result_table = None
    for h2 in h2_tags:
        if "Arama" in h2.get_text():
            # Başlıktan sonraki tablo
            result_table = h2.find_next("table")
            break

    if not result_table:
        # Alternatif: 2 sütunlu, 5+ satırlı tabloyu bul
        tables = soup.find_all("table")
        for t in tables:
            rows = t.find_all("tr", recursive=False)
            if len(rows) > 5:
                first_row = rows[0].find_all("td", recursive=False)
                if len(first_row) == 2:
                    text = first_row[0].get_text(strip=True)
                    if "Firma" in text or "nvan" in text:
                        result_table = t
                        break

    if result_table:
        rows = result_table.find_all("tr", recursive=False)
        for row in rows[1:]:  # İlk satır başlık
            cells = row.find_all("td", recursive=False)
            if len(cells) >= 2:
                unvan = cells[0].get_text(strip=True)
                tarih = cells[1].get_text(strip=True)
                if unvan:
                    companies.append({
                        "unvan": unvan,
                        "kayit_tarihi": tarih,
                    })

    # Sayfa sayısını bul
    page_select = soup.find("select", {"name": "kayitaraligi"})
    total_pages = 1
    if page_select:
        options = page_select.find_all("option")
        total_pages = len(options)

    return companies, total_pages


def get_komite_list():
    """Mevcut komite (meslek grubu) listesini çek"""
    from bs4 import BeautifulSoup
    session = create_session()
    resp = session.get(MEMBERS_URL, timeout=15)
    soup = BeautifulSoup(resp.text, "lxml")

    select = soup.find("select", {"name": "meslekgruptanimi"})
    komiteler = []
    if select:
        for option in select.find_all("option"):
            val = option.get("value", "")
            if val:
                komiteler.append(val)
    return komiteler


def main():
    """Test: Tek bir komite için şirketleri çek"""
    print("=" * 60)
    print("  BTSO Şirket Scraper")
    print("=" * 60)

    init_gemini()

    # Komite listesini al
    komiteler = get_komite_list()
    print(f"\n📋 {len(komiteler)} komite bulundu")
    for i, k in enumerate(komiteler[:5]):
        print(f"   {i+1}. {k}")
    if len(komiteler) > 5:
        print(f"   ... ve {len(komiteler) - 5} komite daha")

    # İlk komite ile test
    test_komite = komiteler[0] if komiteler else "01. GRUP"
    print(f"\n🔍 Test: '{test_komite}' araması yapılıyor...")
    print(f"   CAPTCHA çözülüyor...")

    session, response = solve_captcha_and_submit(meslek_grubu=test_komite)

    if not session or not response:
        print("\n❌ CAPTCHA çözülemedi!")
        return

    # Sonuçları parse et
    companies, total_pages = parse_companies(response.text)
    print(f"\n✅ Sonuçlar alındı!")
    print(f"   Sayfa 1/{total_pages}")
    print(f"   Bu sayfada {len(companies)} şirket")

    if companies:
        print(f"\n   İlk 5 şirket:")
        for i, c in enumerate(companies[:5]):
            print(f"   {i+1}. {c.get('unvan', '-')}")
            if c.get("adres"):
                print(f"      📍 {c['adres'][:60]}")
            if c.get("telefon"):
                print(f"      📞 {c['telefon']}")

    # Yanıtı kaydet
    with open("last_response.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"\n   Tam yanıt 'last_response.html' dosyasına kaydedildi.")


if __name__ == "__main__":
    main()
