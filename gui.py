"""
BTSO Şirket Yönetim Paneli
----------------------------
PySide6 ile modern dark-theme masaüstü uygulaması.
"""

import os
import sys
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QSpinBox, QProgressBar, QFrame, QScrollArea, QSplitter,
    QAbstractItemView, QDialog, QDialogButtonBox, QMessageBox,
    QFileDialog, QSizePolicy, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QFont, QColor, QIcon, QPalette

import database as db
from scraper_worker import ScraperWorker


# ============ RENKLER ============
BG_DARK = "#0f1923"
BG_PANEL = "#1a2332"
BG_CARD = "#1e2d3d"
BG_INPUT = "#243447"
BORDER = "#2a3f55"
ACCENT = "#00bcd4"
ACCENT_HOVER = "#26c6da"
TEXT_PRIMARY = "#ecf0f1"
TEXT_SECONDARY = "#8899aa"
TEXT_MUTED = "#556677"
DANGER = "#e74c3c"
SUCCESS = "#2ecc71"
FONT_FAMILY = "'Helvetica Neue', 'Arial', sans-serif"


DARK_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}

/* Sidebar */
#sidebar {{
    background-color: {BG_PANEL};
    border-right: 1px solid {BORDER};
    min-width: 200px;
    max-width: 200px;
}}
#sidebar QPushButton {{
    text-align: left;
    padding: 11px 16px;
    border: none;
    border-radius: 8px;
    margin: 2px 8px;
    color: {TEXT_SECONDARY};
    font-size: 13px;
    font-weight: 500;
}}
#sidebar QPushButton:hover {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
}}
#sidebar QPushButton[active="true"] {{
    background-color: {BG_INPUT};
    color: {ACCENT};
    font-weight: bold;
}}
#appTitle {{
    color: {ACCENT};
    font-size: 17px;
    font-weight: bold;
    padding: 18px 16px 14px 16px;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 6px;
}}

/* Table */
QTableWidget {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: {BG_INPUT};
    alternate-background-color: #1c2a38;
    font-size: 12px;
}}
QTableWidget::item {{
    padding: 5px 8px;
    border: none;
}}
QHeaderView::section {{
    background-color: {BG_CARD};
    color: {ACCENT};
    padding: 8px;
    border: none;
    border-bottom: 2px solid {ACCENT};
    font-weight: bold;
    font-size: 12px;
}}

/* Inputs */
QLineEdit, QComboBox, QSpinBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 10px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    selection-background-color: {BG_CARD};
    border: 1px solid {BORDER};
}}

/* Buttons */
QPushButton {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: {BG_INPUT};
    border-color: {ACCENT};
}}
QPushButton[accent="true"] {{
    background-color: {ACCENT};
    color: {BG_DARK};
    border: none;
}}
QPushButton[accent="true"]:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton[danger="true"] {{
    background-color: {DANGER};
    color: white;
    border: none;
}}
QPushButton[danger="true"]:hover {{
    background-color: #ff6b5b;
}}

/* Progress */
QProgressBar {{
    background-color: {BG_INPUT};
    border-radius: 6px;
    text-align: center;
    color: {TEXT_PRIMARY};
    height: 20px;
    font-size: 11px;
    border: 1px solid {BORDER};
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

/* Log */
QTextEdit {{
    background-color: #0a1015;
    color: {SUCCESS};
    border: 1px solid {BORDER};
    border-radius: 8px;
    font-family: 'Menlo', 'SF Mono', 'Courier New', monospace;
    font-size: 11px;
    padding: 8px;
}}

/* ScrollBar */
QScrollBar:vertical {{
    background: {BG_PANEL};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 6px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 3px;
}}
"""


# ============ HELPER WIDGETS ============

def make_card_frame():
    """Ortak kart stili"""
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame {{
            background-color: {BG_PANEL};
            border-radius: 10px;
            border: 1px solid {BORDER};
        }}
    """)
    return f


class StatCard(QFrame):
    """İstatistik kartı — emoji yok, clean tasarım"""
    def __init__(self, label, value="0", color=ACCENT):
        super().__init__()
        self.color = color
        self.setStyleSheet(f"""
            StatCard {{
                background-color: {BG_PANEL};
                border-radius: 10px;
                border: 1px solid {BORDER};
                padding: 14px;
            }}
        """)
        self.setMinimumHeight(90)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(16, 12, 16, 12)

        # Label üst
        desc = QLabel(label)
        desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: 600; "
                           "letter-spacing: 0.5px; text-transform: uppercase; border: none;")
        layout.addWidget(desc)

        # Değer
        self.value_lbl = QLabel(str(value))
        self.value_lbl.setStyleSheet(f"color: {color}; font-size: 26px; font-weight: bold; "
                                     "font-family: 'SF Pro Display', 'Helvetica Neue', system-ui; border: none;")
        layout.addWidget(self.value_lbl)

    def set_value(self, val):
        self.value_lbl.setText(str(val))


class SidebarButton(QPushButton):
    def __init__(self, icon, text):
        super().__init__(f"  {icon}  {text}")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)


# ============ DASHBOARD ============

class DashboardPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(20)
        layout.setContentsMargins(28, 24, 28, 24)

        # Başlık
        title = QLabel("Dashboard")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Genel bakış ve istatistikler")
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        # Stat kartları
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)

        self.card_sirket = StatCard("TOPLAM ŞİRKET", "0", ACCENT)
        self.card_komite = StatCard("KOMİTE", "0", "#9b59b6")
        self.card_not = StatCard("NOT", "0", "#e67e22")
        self.card_son = StatCard("SON KAYIT", "-", SUCCESS)

        cards_layout.addWidget(self.card_sirket)
        cards_layout.addWidget(self.card_komite)
        cards_layout.addWidget(self.card_not)
        cards_layout.addWidget(self.card_son)
        layout.addLayout(cards_layout)

        # Dağılım başlık
        dist_title = QLabel("Komite Bazlı Şirket Dağılımı")
        dist_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT_PRIMARY}; margin-top: 10px;")
        layout.addWidget(dist_title)

        # Dağılım chart
        self.dist_frame = make_card_frame()
        self.dist_layout = QVBoxLayout(self.dist_frame)
        self.dist_layout.setSpacing(4)
        self.dist_layout.setContentsMargins(16, 14, 16, 14)
        layout.addWidget(self.dist_frame)

        layout.addStretch()
        self.setWidget(container)

    def refresh(self):
        try:
            stats = db.get_stats()
            self.card_sirket.set_value(f"{stats['toplam_sirket']:,}".replace(",", "."))
            self.card_komite.set_value(str(stats['toplam_komite']))
            self.card_not.set_value(str(stats['toplam_not']))
            self.card_son.set_value(stats.get('son_kayit', '-'))

            # Dağılım temizle
            while self.dist_layout.count():
                item = self.dist_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            komiteler = db.get_komiteler()
            komiteler.sort(key=lambda x: x['sirket_sayisi'], reverse=True)
            max_val = komiteler[0]['sirket_sayisi'] if komiteler else 1

            for k in komiteler[:20]:
                row_widget = QWidget()
                row_widget.setStyleSheet("border: none; background: transparent;")
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 2, 0, 2)
                row_layout.setSpacing(8)

                # Komite kodu
                code_lbl = QLabel(k['komite_kodu'])
                code_lbl.setFixedWidth(65)
                code_lbl.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 11px; border: none;")
                code_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                row_layout.addWidget(code_lbl)

                # Bar
                bar_pct = k['sirket_sayisi'] / max_val
                bar = QFrame()
                bar.setFixedHeight(14)
                bar.setMinimumWidth(max(4, int(bar_pct * 350)))
                bar.setMaximumWidth(max(4, int(bar_pct * 350)))
                bar.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                                  f"stop:0 {ACCENT}, stop:1 #0097a7); "
                                  f"border-radius: 3px; border: none;")
                row_layout.addWidget(bar)

                # Sayı
                count_lbl = QLabel(str(k['sirket_sayisi']))
                count_lbl.setFixedWidth(45)
                count_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; border: none;")
                row_layout.addWidget(count_lbl)

                row_layout.addStretch()
                self.dist_layout.addWidget(row_widget)

        except Exception as e:
            print(f"Dashboard refresh error: {e}")


# ============ ŞİRKETLER ============

class CompaniesPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Başlık
        top = QHBoxLayout()
        title = QLabel("Şirketler")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {TEXT_PRIMARY};")
        top.addWidget(title)
        top.addStretch()

        self.total_label = QLabel("")
        self.total_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        top.addWidget(self.total_label)
        layout.addLayout(top)

        # Filtre bar
        filter_frame = make_card_frame()
        filter_inner = QHBoxLayout(filter_frame)
        filter_inner.setContentsMargins(12, 10, 12, 10)
        filter_inner.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Firma adı ara...")
        self.search_input.setMinimumWidth(220)
        self.search_input.returnPressed.connect(self.apply_filters)
        filter_inner.addWidget(self.search_input)

        self.komite_combo = QComboBox()
        self.komite_combo.setMinimumWidth(180)
        self.komite_combo.addItem("Tüm Komiteler", "")
        self.komite_combo.currentIndexChanged.connect(self.apply_filters)
        filter_inner.addWidget(self.komite_combo)

        self.limit_combo = QComboBox()
        self.limit_combo.setFixedWidth(90)
        for n in [50, 100, 200, 500]:
            self.limit_combo.addItem(f"{n} kayıt", n)
        self.limit_combo.currentIndexChanged.connect(self.apply_filters)
        filter_inner.addWidget(self.limit_combo)

        search_btn = QPushButton("Ara")
        search_btn.setProperty("accent", True)
        search_btn.setFixedWidth(60)
        search_btn.clicked.connect(self.apply_filters)
        filter_inner.addWidget(search_btn)

        clear_btn = QPushButton("Temizle")
        clear_btn.setFixedWidth(65)
        clear_btn.clicked.connect(self.clear_filters)
        filter_inner.addWidget(clear_btn)

        export_btn = QPushButton("CSV Aktar")
        export_btn.setFixedWidth(80)
        export_btn.clicked.connect(self.export_csv)
        filter_inner.addWidget(export_btn)

        layout.addWidget(filter_frame)

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Komite", "Firma Unvanı", "Kayıt Tarihi", "Sayfa", "Not"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 55)
        self.table.setColumnWidth(4, 45)

        header.sectionClicked.connect(self.on_header_click)
        self.table.doubleClicked.connect(self.on_row_double_click)
        layout.addWidget(self.table)

        # Sayfalama
        page_frame = QWidget()
        page_layout = QHBoxLayout(page_frame)
        page_layout.setContentsMargins(0, 4, 0, 0)

        self.prev_btn = QPushButton("< Önceki")
        self.prev_btn.setFixedWidth(80)
        self.prev_btn.clicked.connect(self.prev_page)
        page_layout.addWidget(self.prev_btn)

        page_layout.addStretch()
        self.page_label = QLabel("Sayfa 1 / 1")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        page_layout.addWidget(self.page_label)
        page_layout.addStretch()

        self.next_btn = QPushButton("Sonraki >")
        self.next_btn.setFixedWidth(80)
        self.next_btn.clicked.connect(self.next_page)
        page_layout.addWidget(self.next_btn)
        layout.addWidget(page_frame)

        # State
        self.current_page = 1
        self.sort_col = "kayit_tarihi"
        self.sort_dir = "DESC"
        self._company_ids = []

    def load_komiteler(self):
        self.komite_combo.blockSignals(True)
        self.komite_combo.clear()
        self.komite_combo.addItem("Tüm Komiteler", "")
        try:
            for k in db.get_komiteler():
                self.komite_combo.addItem(
                    f"{k['komite_kodu']} ({k['sirket_sayisi']})", k['komite_kodu']
                )
        except Exception:
            pass
        self.komite_combo.blockSignals(False)

    def apply_filters(self):
        self.current_page = 1
        self.load_data()

    def clear_filters(self):
        self.search_input.clear()
        self.komite_combo.setCurrentIndex(0)
        self.current_page = 1
        self.load_data()

    def get_filters(self):
        f = {}
        search = self.search_input.text().strip()
        if search:
            f["search"] = search
        komite = self.komite_combo.currentData()
        if komite:
            f["komite"] = komite
        return f

    def load_data(self):
        try:
            limit = self.limit_combo.currentData() or 50
            result = db.get_companies(
                filters=self.get_filters(),
                sort_col=self.sort_col,
                sort_dir=self.sort_dir,
                page=self.current_page,
                limit=limit,
            )

            self._company_ids = []
            self.table.setRowCount(0)
            self.table.setRowCount(len(result["data"]))

            for row_idx, c in enumerate(result["data"]):
                self._company_ids.append(c["id"])

                self.table.setItem(row_idx, 0, QTableWidgetItem(c["komite_kodu"]))

                unvan_item = QTableWidgetItem(c["firma_unvani"])
                self.table.setItem(row_idx, 1, unvan_item)

                self.table.setItem(row_idx, 2, QTableWidgetItem(c.get("kayit_tarihi", "")))

                pg_item = QTableWidgetItem(str(c.get("sayfa", "")))
                pg_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 3, pg_item)

                not_count = c.get("not_sayisi", 0)
                if not_count:
                    not_item = QTableWidgetItem("N")
                    not_item.setTextAlignment(Qt.AlignCenter)
                    not_item.setForeground(QColor("#e67e22"))
                    font = not_item.font()
                    font.setBold(True)
                    not_item.setFont(font)
                else:
                    not_item = QTableWidgetItem("")
                    not_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, 4, not_item)

            self.total_label.setText(f"{result['total']:,} sonuc".replace(",", "."))
            self.page_label.setText(f"Sayfa {result['page']} / {result['total_pages']}")
            self.prev_btn.setEnabled(result['page'] > 1)
            self.next_btn.setEnabled(result['page'] < result['total_pages'])

        except Exception as e:
            self.total_label.setText(f"Hata: {str(e)[:40]}")

    def on_header_click(self, col):
        col_map = {0: "komite_kodu", 1: "firma_unvani", 2: "kayit_tarihi", 3: "sayfa"}
        col_name = col_map.get(col)
        if col_name:
            if self.sort_col == col_name:
                self.sort_dir = "ASC" if self.sort_dir == "DESC" else "DESC"
            else:
                self.sort_col = col_name
                self.sort_dir = "ASC"
            self.load_data()

    def on_row_double_click(self, index):
        row = index.row()
        if row < len(self._company_ids):
            sirket_id = self._company_ids[row]
            dlg = CompanyDetailDialog(sirket_id, self)
            dlg.exec()
            self.load_data()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def next_page(self):
        self.current_page += 1
        self.load_data()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV Kaydet", "export.csv", "CSV (*.csv)")
        if path:
            count = db.export_csv(filters=self.get_filters(), output_path=path)
            QMessageBox.information(self, "Export", f"{count} kayit aktarildi.")

    def refresh(self):
        self.load_komiteler()
        self.load_data()

    def filter_komite(self, komite_kodu):
        idx = self.komite_combo.findData(komite_kodu)
        if idx >= 0:
            self.komite_combo.setCurrentIndex(idx)
        self.apply_filters()


# ============ ŞİRKET DETAY ============

class CompanyDetailDialog(QDialog):
    def __init__(self, sirket_id, parent=None):
        super().__init__(parent)
        self.sirket_id = sirket_id
        self.setWindowTitle("Sirket Detayi")
        self.setMinimumSize(520, 480)
        self.setStyleSheet(DARK_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        company = db.get_company(sirket_id)
        if not company:
            layout.addWidget(QLabel("Sirket bulunamadi"))
            return

        # Firma unvanı
        title = QLabel(company["firma_unvani"])
        title.setWordWrap(True)
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ACCENT};")
        layout.addWidget(title)

        # Bilgiler
        info_frame = make_card_frame()
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(14, 10, 14, 10)
        info_layout.setSpacing(4)

        info_layout.addWidget(QLabel(f"Komite: {company['komite_adi']}"))
        info_layout.addWidget(QLabel(f"Kayit Tarihi: {company.get('kayit_tarihi', '-')}"))
        info_layout.addWidget(QLabel(f"Sayfa: {company.get('sayfa', '-')}"))
        layout.addWidget(info_frame)

        # Notlar başlık
        notes_title = QLabel("Notlar")
        notes_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT_PRIMARY};")
        layout.addWidget(notes_title)

        # Notlar listesi
        self.notes_scroll = QScrollArea()
        self.notes_scroll.setWidgetResizable(True)
        self.notes_scroll.setMaximumHeight(180)
        self.notes_scroll.setStyleSheet(f"QScrollArea {{ border: 1px solid {BORDER}; border-radius: 8px; }}")

        self.notes_widget = QWidget()
        self.notes_layout = QVBoxLayout(self.notes_widget)
        self.notes_layout.setContentsMargins(10, 8, 10, 8)
        self.notes_layout.setSpacing(6)
        self.notes_scroll.setWidget(self.notes_widget)
        layout.addWidget(self.notes_scroll)

        # Not ekleme alanı
        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText("Not yazin...")
        self.note_input.setMaximumHeight(70)
        layout.addWidget(self.note_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        add_btn = QPushButton("Not Ekle")
        add_btn.setProperty("accent", True)
        add_btn.setFixedWidth(100)
        add_btn.clicked.connect(self.add_note)
        btn_row.addWidget(add_btn)
        layout.addLayout(btn_row)

        self.load_notes()

    def load_notes(self):
        while self.notes_layout.count():
            item = self.notes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        notes = db.get_notes(self.sirket_id)
        if not notes:
            lbl = QLabel("Henuz not yok")
            lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-style: italic;")
            self.notes_layout.addWidget(lbl)
        else:
            for note in notes:
                row_w = QWidget()
                row_w.setStyleSheet(f"background-color: {BG_INPUT}; border-radius: 6px; padding: 6px;")
                row_l = QHBoxLayout(row_w)
                row_l.setContentsMargins(8, 4, 4, 4)
                row_l.setSpacing(8)

                text_lbl = QLabel(note['not_metni'])
                text_lbl.setWordWrap(True)
                text_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
                row_l.addWidget(text_lbl, 1)

                date_lbl = QLabel(note.get('tarih', '')[:10])
                date_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
                row_l.addWidget(date_lbl)

                del_btn = QPushButton("X")
                del_btn.setFixedSize(24, 24)
                del_btn.setStyleSheet(f"background: {DANGER}; border-radius: 4px; "
                                      f"color: white; font-size: 11px; font-weight: bold; border: none;")
                del_btn.clicked.connect(lambda checked, nid=note['id']: self.delete_note(nid))
                row_l.addWidget(del_btn)

                self.notes_layout.addWidget(row_w)

        self.notes_layout.addStretch()

    def add_note(self):
        text = self.note_input.toPlainText().strip()
        if text:
            db.add_note(self.sirket_id, text)
            self.note_input.clear()
            self.load_notes()

    def delete_note(self, note_id):
        db.delete_note(note_id)
        self.load_notes()


# ============ KOMİTELER ============

class KomitelerPage(QWidget):
    switch_to_companies = Signal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Komiteler")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        subtitle = QLabel("Cift tiklayarak komitenin sirketlerini goruntuleyebilirsiniz")
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; margin-bottom: 6px;")
        layout.addWidget(subtitle)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Kodu", "Adi", "Sirket Sayisi"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(2, 110)

        self.table.doubleClicked.connect(self.on_row_double_click)
        layout.addWidget(self.table)

    def on_row_double_click(self, index):
        row = index.row()
        code_item = self.table.item(row, 0)
        if code_item:
            self.switch_to_companies.emit(code_item.text())

    def refresh(self):
        try:
            komiteler = db.get_komiteler()
            self.table.setRowCount(len(komiteler))
            for i, k in enumerate(komiteler):
                self.table.setItem(i, 0, QTableWidgetItem(k["komite_kodu"]))
                self.table.setItem(i, 1, QTableWidgetItem(k["komite_adi"]))

                count_item = QTableWidgetItem(str(k["sirket_sayisi"]))
                count_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, 2, count_item)
        except Exception:
            pass


# ============ SCRAPER ============

class ScraperPage(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Scraper")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        # Kontroller
        ctrl_frame = make_card_frame()
        ctrl = QHBoxLayout(ctrl_frame)
        ctrl.setContentsMargins(14, 10, 14, 10)
        ctrl.setSpacing(10)

        ctrl.addWidget(QLabel("Thread:"))
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 10)
        self.workers_spin.setValue(3)
        self.workers_spin.setFixedWidth(60)
        ctrl.addWidget(self.workers_spin)

        self.start_btn = QPushButton("Baslat")
        self.start_btn.setProperty("accent", True)
        self.start_btn.clicked.connect(self.start_scraper)
        ctrl.addWidget(self.start_btn)

        self.resume_btn = QPushButton("Devam Et")
        self.resume_btn.clicked.connect(self.resume_scraper)
        ctrl.addWidget(self.resume_btn)

        self.stop_btn = QPushButton("Durdur")
        self.stop_btn.setProperty("danger", True)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_scraper)
        ctrl.addWidget(self.stop_btn)

        self.import_btn = QPushButton("CSV > DB")
        self.import_btn.clicked.connect(self.import_csv)
        ctrl.addWidget(self.import_btn)

        self.clear_db_btn = QPushButton("DB Sil")
        self.clear_db_btn.setProperty("danger", True)
        self.clear_db_btn.clicked.connect(self.clear_database)
        ctrl.addWidget(self.clear_db_btn)

        ctrl.addStretch()
        layout.addWidget(ctrl_frame)

        # Progress
        self.progress = QProgressBar()
        self.progress.setFormat("%v / %m komite")
        layout.addWidget(self.progress)

        # Stats kartları
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        self.stat_captcha = StatCard("CAPTCHA BASARI", "0/0", ACCENT)
        self.stat_companies = StatCard("DB SIRKET", "0", SUCCESS)
        self.stat_learned = StatCard("OGRENILEN", "0", "#e67e22")
        stats_layout.addWidget(self.stat_captcha)
        stats_layout.addWidget(self.stat_companies)
        stats_layout.addWidget(self.stat_learned)
        layout.addLayout(stats_layout)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

    def start_scraper(self):
        self._run(resume=False)

    def resume_scraper(self):
        self._run(resume=True)

    def _run(self, resume):
        if self.worker and self.worker.isRunning():
            return

        self.worker = ScraperWorker(workers=self.workers_spin.value(), resume=resume)
        self.worker.log_signal.connect(self.on_log)
        self.worker.progress_signal.connect(self.on_progress)
        self.worker.stats_signal.connect(self.on_stats)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

        self.start_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log.clear()
        self.log.append("Scraper baslatildi...")

    def stop_scraper(self):
        if self.worker:
            self.worker.stop()
            self.log.append("Durduruluyor...")

    def on_log(self, msg):
        self.log.append(msg)
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_progress(self, done, total):
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)

    def on_stats(self, s):
        attempts = s.get("captcha_attempts", 0)
        success = s.get("captcha_success", 0)
        self.stat_captcha.set_value(f"{success}/{attempts}")
        db_count = s.get("total_companies", 0)
        self.stat_companies.set_value(f"{db_count:,}".replace(",", "."))
        self.stat_learned.set_value(str(s.get("learned", 0)))

    def on_finished(self, s):
        self.start_btn.setEnabled(True)
        self.resume_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.log.append("-" * 40)
        self.log.append("Scraper tamamlandi!")

    def import_csv(self):
        self.log.append("CSV'den veritabanina import ediliyor...")
        QApplication.processEvents()
        try:
            count = db.import_csv()
            self.log.append(f"{count:,} sirket import edildi!".replace(",", "."))
        except Exception as e:
            self.log.append(f"Hata: {e}")

    def clear_database(self):
        reply = QMessageBox.question(
            self, "DB Sil",
            "Tum sirketler ve notlar silinecek. Emin misiniz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                db.clear_companies()
                self.log.append("Veritabani temizlendi!")
                self.stat_companies.set_value("0")
            except Exception as e:
                self.log.append(f"Hata: {e}")


# ============ AYARLAR ============

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 24)

        title = QLabel("Ayarlar")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        # Dosya yolları
        paths_frame = make_card_frame()
        paths_layout = QVBoxLayout(paths_frame)
        paths_layout.setContentsMargins(16, 14, 16, 14)
        paths_layout.setSpacing(8)

        paths_title = QLabel("DOSYA YOLLARI")
        paths_title.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: bold; "
                                  "letter-spacing: 0.5px;")
        paths_layout.addWidget(paths_title)

        for label, path in [("Veritabani", db.DB_FILE), ("CSV", db.CSV_FILE),
                            ("Dataset", os.path.join(db.BASE_DIR, "dataset"))]:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(80)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
            row.addWidget(lbl)
            val = QLabel(path)
            val.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 11px;")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(val)
            paths_layout.addLayout(row)

        layout.addWidget(paths_frame)

        # İşlemler
        ops_frame = make_card_frame()
        ops_layout = QVBoxLayout(ops_frame)
        ops_layout.setContentsMargins(16, 14, 16, 14)
        ops_layout.setSpacing(10)

        ops_title = QLabel("VERITABANI ISLEMLERI")
        ops_title.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: bold; "
                                "letter-spacing: 0.5px;")
        ops_layout.addWidget(ops_title)

        reimport_btn = QPushButton("CSV'den Yeniden Import Et")
        reimport_btn.setProperty("accent", True)
        reimport_btn.clicked.connect(self.reimport)
        ops_layout.addWidget(reimport_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {SUCCESS};")
        ops_layout.addWidget(self.status_label)

        layout.addWidget(ops_frame)
        layout.addStretch()

    def reimport(self):
        self.status_label.setText("Import ediliyor...")
        QApplication.processEvents()
        try:
            count = db.import_csv()
            self.status_label.setText(f"{count:,} sirket import edildi!".replace(",", "."))
        except Exception as e:
            self.status_label.setText(f"Hata: {e}")


# ============ ANA PENCERE ============

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BTSO Sirket Yonetim Paneli")
        self.setMinimumSize(1100, 700)
        self.resize(1300, 800)

        # DB başlat
        db.init_db()
        stats = db.get_stats()
        if stats["toplam_sirket"] == 0 and os.path.exists(db.CSV_FILE):
            db.import_csv()

        # Ana layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        app_title = QLabel("  BTSO Panel")
        app_title.setObjectName("appTitle")
        sidebar_layout.addWidget(app_title)

        sidebar_layout.addSpacing(6)

        self.nav_buttons = []
        pages_def = [
            ("D", "Dashboard"),
            ("S", "Sirketler"),
            ("K", "Komiteler"),
            ("R", "Scraper"),
            ("A", "Ayarlar"),
        ]

        for icon, text in pages_def:
            btn = SidebarButton(icon, text)
            btn.clicked.connect(lambda checked, t=text: self.switch_page(t))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append((text, btn))

        sidebar_layout.addStretch()

        ver = QLabel("  v1.0")
        ver.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; padding: 10px;")
        sidebar_layout.addWidget(ver)

        main_layout.addWidget(sidebar)

        # Content stack
        self.stack = QStackedWidget()

        self.dashboard_page = DashboardPage()
        self.companies_page = CompaniesPage()
        self.komiteler_page = KomitelerPage()
        self.scraper_page = ScraperPage()
        self.settings_page = SettingsPage()

        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.companies_page)
        self.stack.addWidget(self.komiteler_page)
        self.stack.addWidget(self.scraper_page)
        self.stack.addWidget(self.settings_page)

        self.komiteler_page.switch_to_companies.connect(self.open_companies_for_komite)

        main_layout.addWidget(self.stack)

        self.switch_page("Dashboard")

    def switch_page(self, name):
        page_map = {
            "Dashboard": 0, "Sirketler": 1,
            "Komiteler": 2, "Scraper": 3, "Ayarlar": 4,
        }
        idx = page_map.get(name, 0)
        self.stack.setCurrentIndex(idx)

        for text, btn in self.nav_buttons:
            btn.setProperty("active", text == name)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        widget = self.stack.currentWidget()
        if hasattr(widget, 'refresh'):
            widget.refresh()

    def open_companies_for_komite(self, komite_kodu):
        self.switch_page("Sirketler")
        self.companies_page.filter_komite(komite_kodu)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
