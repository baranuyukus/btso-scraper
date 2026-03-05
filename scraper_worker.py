"""
Scraper QThread Worker
-----------------------
GUI'den başlatılıp durdurulabilen scraper worker.
Stats'ı periyodik olarak günceller.
"""

import os
import time
import threading
from PySide6.QtCore import QThread, Signal, QTimer

from scraper import (
    setup as scraper_setup, get_komite_list, scrape_komite,
    load_progress, save_progress, is_komite_done,
    stop_event, stats,
    fix_enc
)
import database as db


class ScraperWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int, int)
    stats_signal = Signal(dict)
    finished_signal = Signal(dict)

    def __init__(self, workers=3, resume=False):
        super().__init__()
        self.workers = workers
        self.resume = resume
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True
        stop_event.set()

    def run(self):
        import scraper as scr

        stop_event.clear()
        self._stop_flag = False

        for k in stats:
            stats[k] = 0

        # Log override
        original_log = scr.log
        def gui_log(msg):
            self.log_signal.emit(msg)
        scr.log = gui_log

        try:
            self.log_signal.emit("Model yukleniyor...")
            scraper_setup()
            self.log_signal.emit("Model hazir")

            # DB init
            db.init_db()

            komiteler = get_komite_list()
            self.log_signal.emit(f"{len(komiteler)} komite bulundu")

            progress = load_progress() if self.resume else {"completed_komites": {}, "failed_pages": {}}

            remaining = [k for k in komiteler if not is_komite_done(progress, k["value"])]
            total = len(komiteler)
            done_before = total - len(remaining)

            self.log_signal.emit(f"{len(remaining)} komite cekilecek ({self.workers} thread)")
            self.progress_signal.emit(done_before, total)

            # Stats timer - her 2 saniyede bir güncelle
            stats_stop = threading.Event()

            def stats_updater():
                while not stats_stop.is_set():
                    self.stats_signal.emit(dict(stats))
                    # Şirket sayısını DB'den çek
                    try:
                        count = db.get_company_count()
                        s = dict(stats)
                        s["total_companies"] = count
                        self.stats_signal.emit(s)
                    except Exception:
                        pass
                    stats_stop.wait(2)

            stats_thread = threading.Thread(target=stats_updater, daemon=True)
            stats_thread.start()

            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = {executor.submit(scrape_komite, k, progress): k for k in remaining}

                for future in as_completed(futures):
                    if self._stop_flag:
                        break
                    try:
                        future.result()
                    except Exception as e:
                        k = futures[future]
                        self.log_signal.emit(f"Hata {k['value']}: {str(e)[:60]}")

                    done_now = sum(1 for kv in progress.get("completed_komites", {})
                                  if is_komite_done(progress, kv))
                    self.progress_signal.emit(done_now, total)

            stats_stop.set()

            if self._stop_flag:
                self.log_signal.emit("Durduruldu. Ilerleme kaydedildi.")
                save_progress(progress)

        except Exception as e:
            self.log_signal.emit(f"Hata: {str(e)}")
        finally:
            scr.log = original_log
            self.stats_signal.emit(dict(stats))
            self.finished_signal.emit(dict(stats))
