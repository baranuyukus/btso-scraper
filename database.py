"""
BTSO Şirket Veritabanı
-----------------------
SQLite ile şirket yönetimi, not ekleme, filtreleme/sıralama.
"""

import os
import csv
import sqlite3
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_FILE = os.path.join(OUTPUT_DIR, "btso.db")
CSV_FILE = os.path.join(OUTPUT_DIR, "sirketler.csv")


def get_connection(db_path=None):
    conn = sqlite3.connect(db_path or DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path=None):
    """Veritabanını oluştur"""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sirketler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            komite_kodu TEXT NOT NULL,
            komite_adi TEXT NOT NULL,
            firma_unvani TEXT NOT NULL,
            kayit_tarihi TEXT,
            sayfa INTEGER,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS notlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sirket_id INTEGER NOT NULL,
            not_metni TEXT NOT NULL,
            tarih TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (sirket_id) REFERENCES sirketler(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_komite ON sirketler(komite_kodu);
        CREATE INDEX IF NOT EXISTS idx_unvan ON sirketler(firma_unvani);
        CREATE INDEX IF NOT EXISTS idx_tarih ON sirketler(kayit_tarihi);
        CREATE INDEX IF NOT EXISTS idx_notlar_sirket ON notlar(sirket_id);
    """)
    conn.commit()
    conn.close()


def import_csv(csv_path=None, db_path=None, progress_callback=None):
    """CSV'den veritabanına toplu import"""
    csv_path = csv_path or CSV_FILE
    if not os.path.exists(csv_path):
        return 0

    conn = get_connection(db_path)
    init_db(db_path)

    # Mevcut verileri temizle
    conn.execute("DELETE FROM sirketler")
    conn.commit()

    count = 0
    batch = []
    batch_size = 500

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        total = sum(1 for _ in open(csv_path, encoding="utf-8")) - 1

        f.seek(0)
        reader = csv.DictReader(f)

        for row in reader:
            batch.append((
                row.get("komite_kodu", ""),
                row.get("komite_adi", ""),
                row.get("firma_unvani", ""),
                row.get("kayit_tarihi", ""),
                int(row.get("sayfa", 0) or 0),
            ))
            count += 1

            if len(batch) >= batch_size:
                conn.executemany(
                    "INSERT INTO sirketler (komite_kodu, komite_adi, firma_unvani, kayit_tarihi, sayfa) "
                    "VALUES (?, ?, ?, ?, ?)", batch
                )
                conn.commit()
                batch = []
                if progress_callback:
                    progress_callback(count, total)

    if batch:
        conn.executemany(
            "INSERT INTO sirketler (komite_kodu, komite_adi, firma_unvani, kayit_tarihi, sayfa) "
            "VALUES (?, ?, ?, ?, ?)", batch
        )
        conn.commit()

    conn.close()
    return count


def add_companies_batch(companies, db_path=None):
    """Scraper'dan gelen şirketleri doğrudan DB'ye yaz"""
    if not companies:
        return 0
    conn = get_connection(db_path)
    init_db(db_path)
    batch = []
    for c in companies:
        batch.append((
            c.get("komite_kodu", ""),
            c.get("komite_adi", ""),
            c.get("firma_unvani", ""),
            c.get("kayit_tarihi", ""),
            int(c.get("sayfa", 0) or 0),
        ))
    conn.executemany(
        "INSERT INTO sirketler (komite_kodu, komite_adi, firma_unvani, kayit_tarihi, sayfa) "
        "VALUES (?, ?, ?, ?, ?)", batch
    )
    conn.commit()
    conn.close()
    return len(batch)


def clear_companies(db_path=None):
    """Tüm şirketleri sil (notlar korunur ama orphan olur)"""
    conn = get_connection(db_path)
    conn.execute("DELETE FROM sirketler")
    conn.execute("DELETE FROM notlar")
    conn.commit()
    conn.close()


def get_company_count(db_path=None):
    conn = get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM sirketler").fetchone()[0]
    conn.close()
    return count


def get_stats(db_path=None):
    """Genel istatistikler"""
    conn = get_connection(db_path)
    stats = {}
    stats["toplam_sirket"] = conn.execute("SELECT COUNT(*) FROM sirketler").fetchone()[0]
    stats["toplam_komite"] = conn.execute("SELECT COUNT(DISTINCT komite_kodu) FROM sirketler").fetchone()[0]
    stats["toplam_not"] = conn.execute("SELECT COUNT(*) FROM notlar").fetchone()[0]

    row = conn.execute("SELECT MAX(kayit_tarihi) FROM sirketler").fetchone()
    stats["son_kayit"] = row[0] if row else "-"

    # Notlu şirket sayısı
    stats["notlu_sirket"] = conn.execute(
        "SELECT COUNT(DISTINCT sirket_id) FROM notlar"
    ).fetchone()[0]

    conn.close()
    return stats


def get_komiteler(db_path=None):
    """Komite listesi ve istatistikleri"""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT komite_kodu, komite_adi, COUNT(*) as sirket_sayisi
        FROM sirketler
        GROUP BY komite_kodu, komite_adi
        ORDER BY komite_kodu
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_companies(filters=None, sort_col="kayit_tarihi", sort_dir="DESC",
                  page=1, limit=50, db_path=None):
    """Sayfalı ve filtrelenmiş şirket listesi"""
    conn = get_connection(db_path)
    filters = filters or {}

    where = []
    params = []

    if filters.get("komite"):
        where.append("komite_kodu = ?")
        params.append(filters["komite"])

    if filters.get("search"):
        where.append("firma_unvani LIKE ?")
        params.append(f"%{filters['search']}%")

    if filters.get("tarih_bas"):
        where.append("kayit_tarihi >= ?")
        params.append(filters["tarih_bas"])

    if filters.get("tarih_son"):
        where.append("kayit_tarihi <= ?")
        params.append(filters["tarih_son"])

    where_sql = " AND ".join(where) if where else "1=1"

    # Toplam sayı
    total = conn.execute(f"SELECT COUNT(*) FROM sirketler WHERE {where_sql}", params).fetchone()[0]

    # Sıralama güvenliği
    valid_cols = {"id", "komite_kodu", "komite_adi", "firma_unvani", "kayit_tarihi", "sayfa"}
    if sort_col not in valid_cols:
        sort_col = "kayit_tarihi"
    sort_dir = "ASC" if sort_dir.upper() == "ASC" else "DESC"

    offset = (page - 1) * limit
    rows = conn.execute(f"""
        SELECT s.*, 
               (SELECT COUNT(*) FROM notlar n WHERE n.sirket_id = s.id) as not_sayisi
        FROM sirketler s
        WHERE {where_sql}
        ORDER BY {sort_col} {sort_dir}
        LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()

    conn.close()
    return {
        "data": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total + limit - 1) // limit),
    }


def get_company(sirket_id, db_path=None):
    """Tek şirket detayı"""
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM sirketler WHERE id = ?", (sirket_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_note(sirket_id, text, db_path=None):
    """Not ekle"""
    conn = get_connection(db_path)
    conn.execute("INSERT INTO notlar (sirket_id, not_metni) VALUES (?, ?)", (sirket_id, text))
    conn.commit()
    conn.close()


def get_notes(sirket_id, db_path=None):
    """Şirketin notlarını getir"""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM notlar WHERE sirket_id = ? ORDER BY tarih DESC",
        (sirket_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_note(note_id, db_path=None):
    """Not sil"""
    conn = get_connection(db_path)
    conn.execute("DELETE FROM notlar WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()


def export_csv(filters=None, output_path=None, db_path=None):
    """Filtrelenmiş sonuçları CSV'ye aktar"""
    result = get_companies(filters=filters, page=1, limit=999999, db_path=db_path)
    output_path = output_path or os.path.join(OUTPUT_DIR, "export.csv")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["komite_kodu", "komite_adi", "firma_unvani", "kayit_tarihi", "sayfa"])
        for c in result["data"]:
            w.writerow([c["komite_kodu"], c["komite_adi"], c["firma_unvani"],
                        c["kayit_tarihi"], c["sayfa"]])

    return len(result["data"])


if __name__ == "__main__":
    init_db()
    count = import_csv()
    print(f"✅ {count} şirket import edildi")
    print(f"📊 {get_stats()}")
