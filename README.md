# BTSO Sirket Scraper & Yonetim Paneli

BTSO (Bursa Ticaret ve Sanayi Odasi) uye sirket verilerini ceken ve yoneten masaustu uygulamasi.

## Ozellikler

- **CAPTCHA Cozucu**: SVM modeli ile otomatik CAPTCHA cozme (%96.7 dogruluk)
- **Multi-Thread Scraper**: Paralel veri cekme, sonsuz retry, sayfa bazli progress
- **GUI Yonetim Paneli**: PySide6 ile modern dark-theme arayuz
  - Dashboard (istatistikler, komite dagilimi)
  - Sirket listeleme, filtreleme, siralama
  - Not ekleme / silme
  - Komite goruntuleme
  - Scraper kontrolu (baslat/durdur/devam)
- **SQLite Veritabani**: Dogrudan veritabanina kayit
- **Self-Learning**: Basarili CAPTCHA cozumleri dataset'e eklenir

## Kurulum

```bash
pip install -r requirements.txt
```

## Kullanim

### GUI Uygulamasi
```bash
python gui.py
```

### Sadece Scraper (CLI)
```bash
python scraper.py              # Yeni baslat
python scraper.py --resume     # Kaldigindan devam
python scraper.py --workers 5  # 5 thread
```

### Model Egitimi
```bash
python captcha_model.py
```

## Build

Windows ve macOS icin otomatik build GitHub Actions ile saglanir.
Release sayfasindan indirilebilir.

## Teknolojiler

- Python 3.11+
- PySide6 (GUI)
- scikit-learn (SVM model)
- requests (HTTP)
- SQLite (veritabani)
- PyInstaller (build)
