"""
Evrak Yönetim Sistemi — Dialog Pencereleri
SearchDialog, TableResultsDialog, DashboardDialog
"""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QTextEdit, QMessageBox, QFrame,
    QGridLayout, QComboBox, QGroupBox, QApplication, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap

from ui.theme import ACCENT, TEXT_PRIMARY, TEXT_SECONDARY, BG_PANEL, BG_INPUT, BORDER, BG_CARD, BG_DARK, SUCCESS, WARNING, ERROR
from database_manager import DatabaseManager
from utils import archive_document, get_resource_dir
from config_manager import ConfigManager
import openpyxl


# ═══════════════════ ORTAK STİLLER ═══════════════════

DIALOG_STYLE = f"""
    QDialog {{
        background-color: {BG_DARK};
    }}
    QLabel#section_title {{
        color: {TEXT_PRIMARY};
        font-size: 16px;
        font-weight: 600;
        padding: 4px 0;
    }}
    QTableWidget {{
        background: {BG_PANEL};
        color: {TEXT_PRIMARY};
        gridline-color: {BORDER};
        font-size: 13px;
        border: 1px solid {BORDER};
        border-radius: 6px;
        selection-background-color: #27272a;
    }}
    QHeaderView::section {{
        background: #18181b;
        color: {TEXT_SECONDARY};
        padding: 8px;
        border: none;
        border-bottom: 1px solid {BORDER};
        font-weight: 500;
        font-size: 12px;
    }}
    QLineEdit {{
        padding: 6px 12px;
        min-height: 28px;
        border: 1px solid {BORDER};
        border-radius: 6px;
        background: {BG_INPUT};
        color: {TEXT_PRIMARY};
        font-size: 14px;
    }}
    QLineEdit:focus {{
        border-color: {TEXT_PRIMARY};
    }}
    QTextEdit {{
        background: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 10px;
        font-size: 13px;
    }}
    QPushButton {{
        padding: 10px 20px;
        border: 1px solid {BORDER};
        border-radius: 6px;
        background: #18181b;
        color: {TEXT_PRIMARY};
        font-weight: 500;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background: #27272a;
    }}
    QPushButton#btn_accent {{
        background: {TEXT_PRIMARY};
        color: #18181b;
        border: none;
        font-weight: 600;
    }}
    QPushButton#btn_accent:hover {{
        background: #e4e4e7;
    }}
    QPushButton#btn_secondary {{
        background: transparent;
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
    }}
    QPushButton#btn_secondary:hover {{
        background: #27272a;
    }}
    QComboBox {{
        padding: 8px 12px;
        border: 1px solid {BORDER};
        border-radius: 6px;
        background: {BG_INPUT};
        color: {TEXT_PRIMARY};
        font-size: 13px;
    }}
    QComboBox:focus {{
        border-color: {TEXT_PRIMARY};
    }}
    QComboBox QAbstractItemView {{
        background: {BG_PANEL};
        color: {TEXT_PRIMARY};
        selection-background-color: #27272a;
        border: 1px solid {BORDER};
    }}
"""


# ═══════════════════ GİRİŞ (LOGIN) EKRANI ═══════════════════

class LoginDialog(QDialog):
    """Sisteme giriş için kullanıcı adı ve şifre soran ekran (v7.0)"""

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.user_data = None
        self.setWindowTitle("Sivas Belediyesi — Evrak Yönetim Sistemi Girişi")
        self.setFixedSize(500, 520)
        self.setStyleSheet(DIALOG_STYLE)
        
        # Dialog kapatılma tuşunu kapat (esc ile geçilemesin)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 30)
        layout.setSpacing(20)

        # Başlık ve Logo Bölümü
        header_layout = QVBoxLayout()
        header_layout.setSpacing(10)
        
        # Logo Ekleme
        logo_label = QLabel()
        logo_path = os.path.join(get_resource_dir(), "assets", "sivas_logo.jpg")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Logoyu boyutlandır (Pürüzsüz)
            pixmap = pixmap.scaled(140, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(logo_label)
        
        title = QLabel("Sisteme Giriş Yapın")
        title.setObjectName("section_title")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title)

        subtitle = QLabel("Devam etmek için kullanıcı bilgilerinizi giriniz.")
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle)

        layout.addLayout(header_layout)
        layout.addSpacing(10)

        # Form Alanı
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)

        self.txt_username = QLineEdit()
        self.txt_username.setMinimumHeight(48)
        self.txt_username.setPlaceholderText("Kullanıcı Adı (ör: admin)")
        self.txt_username.setStyleSheet("font-size: 14px; padding: 10px; border-radius: 8px;")
        self.txt_username.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(self.txt_username)

        self.txt_password = QLineEdit()
        self.txt_password.setMinimumHeight(48)
        self.txt_password.setPlaceholderText("Şifre (ör: admin123)")
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setStyleSheet("font-size: 14px; padding: 10px; border-radius: 8px;")
        self.txt_password.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.txt_password.returnPressed.connect(self.do_login)
        form_layout.addWidget(self.txt_password)

        layout.addLayout(form_layout)
        
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet(f"color: {ERROR}; font-size: 13px;")
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_error)

        layout.addStretch()

        # Buton
        self.btn_login = QPushButton("Giriş Yap")
        self.btn_login.setMinimumHeight(50)
        self.btn_login.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setStyleSheet(f"""
            QPushButton {{
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: #1d4ed8;
            }}
        """)
        self.btn_login.clicked.connect(self.do_login)
        layout.addWidget(self.btn_login)

    def do_login(self):
        username = self.txt_username.text().strip()
        password = self.txt_password.text().strip()

        if not username or not password:
            self.lbl_error.setText("Kullanıcı adı ve şifre boş bırakılamaz.")
            return

        self.btn_login.setText("Doğrulanıyor...")
        self.btn_login.setEnabled(False)
        QApplication.processEvents()

        user = self.db.verify_user(username, password)
        if user:
            self.user_data = user
            self.db.log_audit(user['id'], user['username'], "Giriş Yapıldı", "Başarılı Login")
            self.accept()
        else:
            self.lbl_error.setText("Hatalı kullanıcı adı veya şifre.")
            self.btn_login.setText("Giriş Yap")
            self.btn_login.setEnabled(True)





# ═══════════════════ ARAMA DİALOGU ═══════════════════

class SearchDialog(QDialog):
    """Gelişmiş arama penceresi — çok kriterli filtreleme desteği."""

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Evrak Sorgulama")
        self.setMinimumSize(1000, 650)
        self.setStyleSheet(DIALOG_STYLE)
        self.setup_ui()
        self.load_all()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Başlık
        title = QLabel("🔍  Evrak Arama ve Sorgulama")
        title.setObjectName("section_title")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # ── Filtre Alanları ──
        filter_frame = QFrame()
        filter_frame.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 10px;
                padding: 12px;
            }}
        """)
        filter_layout = QGridLayout(filter_frame)
        filter_layout.setSpacing(10)

        # Satır 1: Free text + Mahalle
        lbl_search = QLabel("Arama")
        lbl_search.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Metin içeriği ile ara...")
        self.search_input.returnPressed.connect(self.do_search)

        lbl_mahalle = QLabel("Mahalle")
        lbl_mahalle.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
        self.filter_mahalle = QLineEdit()
        self.filter_mahalle.setPlaceholderText("Mahalle filtresi")

        filter_layout.addWidget(lbl_search, 0, 0)
        filter_layout.addWidget(self.search_input, 1, 0)
        filter_layout.addWidget(lbl_mahalle, 0, 1)
        filter_layout.addWidget(self.filter_mahalle, 1, 1)

        # Satır 2: Ada + Parsel + Tarih
        lbl_ada = QLabel("Ada")
        lbl_ada.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
        self.filter_ada = QLineEdit()
        self.filter_ada.setPlaceholderText("Ada no")

        lbl_parsel = QLabel("Parsel")
        lbl_parsel.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
        self.filter_parsel = QLineEdit()
        self.filter_parsel.setPlaceholderText("Parsel no")

        lbl_tarih = QLabel("Tarih")
        lbl_tarih.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
        self.filter_tarih = QLineEdit()
        self.filter_tarih.setPlaceholderText("Yıl veya tarih")

        filter_layout.addWidget(lbl_ada, 2, 0)
        filter_layout.addWidget(self.filter_ada, 3, 0)
        filter_layout.addWidget(lbl_parsel, 2, 1)
        filter_layout.addWidget(self.filter_parsel, 3, 1)
        filter_layout.addWidget(lbl_tarih, 2, 2)
        filter_layout.addWidget(self.filter_tarih, 3, 2)

        layout.addWidget(filter_frame)

        # ── Butonlar ──
        btn_bar = QHBoxLayout()
        btn_search = QPushButton("🔍  Ara")
        btn_search.setObjectName("btn_accent")
        btn_search.clicked.connect(self.do_search)

        btn_all = QPushButton("📋  Tümünü Göster")
        btn_all.setObjectName("btn_secondary")
        btn_all.clicked.connect(self.load_all)

        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")

        btn_bar.addWidget(btn_search)
        btn_bar.addWidget(btn_all)
        btn_bar.addStretch()
        btn_bar.addWidget(self.lbl_count)
        layout.addLayout(btn_bar)

        # ── Sonuç Tablosu ──
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Mahalle", "Ada", "Parsel", "Tarih"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(self.table.styleSheet() + """
            QTableWidget { alternate-background-color: rgba(255,255,255,0.02); }
        """)
        self.table.itemDoubleClicked.connect(self.on_row_double_click)
        layout.addWidget(self.table, stretch=1)

        # ── Detay Kutusu ──
        self.detail_txt = QTextEdit()
        self.detail_txt.setReadOnly(True)
        self.detail_txt.setMaximumHeight(160)
        self.detail_txt.setPlaceholderText("Bir satıra çift tıklayarak detayları görüntüleyebilirsiniz...")
        layout.addWidget(self.detail_txt)

    def load_all(self):
        results = self.db.search_advanced()
        self._populate(results)

    def do_search(self):
        free_text = self.search_input.text().strip() or None
        mahalle = self.filter_mahalle.text().strip() or None
        ada = self.filter_ada.text().strip() or None
        parsel = self.filter_parsel.text().strip() or None

        # Eğer hiçbir filtre yoksa tümünü göster
        if not any([free_text, mahalle, ada, parsel]):
            self.load_all()
            return

        results = self.db.search_advanced(
            ada=ada,
            parsel=parsel,
            mahalle=mahalle,
            free_text=free_text,
        )
        self._populate(results)

    def _populate(self, results):
        self.table.setRowCount(len(results))
        for i, d in enumerate(results):
            self.table.setItem(i, 0, QTableWidgetItem(str(d.get("id", ""))))
            self.table.setItem(i, 1, QTableWidgetItem(str(d.get("p_mahalle") or d.get("mahalle", ""))))
            self.table.setItem(i, 2, QTableWidgetItem(str(d.get("ada", ""))))
            self.table.setItem(i, 3, QTableWidgetItem(str(d.get("parsel", ""))))
            self.table.setItem(i, 4, QTableWidgetItem(str(d.get("extracted_date", ""))))
            self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, d)
        self.lbl_count.setText(f"{len(results)} kayıt bulundu")

    def on_row_double_click(self, item):
        row = item.row()
        data = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if data:
            raw = data.get("raw_text", "Metin bulunamadı")
            fp = data.get("file_path", "")
            self.detail_txt.setText(f"📄 Dosya: {fp}\n\n--- Okunan Metin ---\n{raw}")


# ═══════════════════ TABLO SONUÇLARI DİALOGU ═══════════════════

class TableResultsDialog(QDialog):
    """Tablo belgelerinden çıkarılan çoklu satırları gösteren pencere."""

    def __init__(self, result: dict, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.result = result
        self.db = db
        self.rows = result.get("_table_rows", [])
        self.setWindowTitle(f"Tablo Sonuçları — {len(self.rows)} Satır")
        self.setMinimumSize(1100, 650)
        self.setStyleSheet(DIALOG_STYLE)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Başlık
        title_text = self.result.get("table_title", "Tablo Belgesi")
        title = QLabel(f"📊 {title_text} — {len(self.rows)} kayıt tespit edildi")
        title.setObjectName("section_title")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        # Tablo
        cols = ["Sıra", "Mahalle", "Ada", "Parsel", "Nitelik", "TC", "Ad Soyad", "Baba Adı"]
        self.table = QTableWidget(len(self.rows), len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(self.table.styleSheet() + """
            QTableWidget { alternate-background-color: rgba(255,255,255,0.02); }
        """)

        for i, row in enumerate(self.rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(row.get("sira", i + 1))))
            self.table.setItem(i, 1, QTableWidgetItem(str(row.get("mahalle", ""))))
            self.table.setItem(i, 2, QTableWidgetItem(str(row.get("ada", ""))))
            self.table.setItem(i, 3, QTableWidgetItem(str(row.get("parsel", ""))))
            self.table.setItem(i, 4, QTableWidgetItem(str(row.get("nitelik", ""))))
            self.table.setItem(i, 5, QTableWidgetItem(str(row.get("tc_kimlik", ""))))
            self.table.setItem(i, 6, QTableWidgetItem(str(row.get("ad_soyad", ""))))
            self.table.setItem(i, 7, QTableWidgetItem(str(row.get("baba_adi", ""))))

        layout.addWidget(self.table, stretch=1)

        # Butonlar
        btn_row = QHBoxLayout()
        
        btn_export = QPushButton(f"📊 Excel'e Aktar")
        btn_export.setObjectName("btn_secondary")
        btn_export.clicked.connect(self._export_excel)

        btn_save = QPushButton(f"💾 Tümünü Kaydet ({len(self.rows)} kayıt)")
        btn_save.setObjectName("btn_accent")
        btn_save.clicked.connect(self._save_all)
        
        btn_row.addStretch()
        btn_row.addWidget(btn_export)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _export_excel(self):
        if not self.rows:
            QMessageBox.warning(self, "Uyarı", "Dışa aktarılacak tablo verisi bulunamadı.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Excel Olarak Kaydet", "", "Excel Dosyası (*.xlsx)"
        )
        if not file_path:
            return
            
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Tablo Verileri"
            
            # Başlıkları yaz (1. Satır)
            headers = ["Sıra", "Mahalle", "Ada", "Parsel", "Nitelik", "TC Kimlik", "Ad Soyad", "Baba Adı"]
            ws.append(headers)
            
            # Başlıkları kalın yap
            for col in range(1, len(headers) + 1):
                ws.cell(row=1, column=col).font = openpyxl.styles.Font(bold=True)
            
            # Verileri yaz
            for i, row in enumerate(self.rows):
                ws.append([
                    str(row.get("sira", i + 1)),
                    str(row.get("mahalle", "")),
                    str(row.get("ada", "")),
                    str(row.get("parsel", "")),
                    str(row.get("nitelik", "")),
                    str(row.get("tc_kimlik", "")),
                    str(row.get("ad_soyad", "")),
                    str(row.get("baba_adi", ""))
                ])
                
            # Otomatik sütun genişliği
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter # Get the column name
                for cell in col:
                    try: 
                        if len(str(cell.value)) > max_length:
                            max_length = len(cell.value)
                    except:
                        pass
                adjusted_width = (max_length + 2)
                ws.column_dimensions[column].width = adjusted_width
                
            wb.save(file_path)
            QMessageBox.information(self, "Başarılı", f"Veriler başarıyla Excel'e aktarıldı!\n\nDosya: {file_path}")
            os.startfile(file_path) # Automatically open the saved file in Microsoft Excel
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel'e aktarım sırasında bir hata oluştu:\n{str(e)}")

    def _save_all(self):
        saved = 0
        errors = 0
        for row in self.rows:
            try:
                mahalle = row.get("mahalle", "")
                ada = row.get("ada", "")
                if not mahalle and not ada:
                    continue
                doc_data = {
                    "image_path": "",
                    "mahalle": mahalle,
                    "ada": ada,
                    "parsel": row.get("parsel", ""),
                    "tarih": "",
                    "raw_text": str(row),
                    "corrected_text": str(row),
                    "doc_type": "table_row",
                    "ocr_details": {"engine": "gemini-2.5-flash", "source": "table_ocr"},
                }
                self.db.add_document(doc_data)
                saved += 1
            except Exception:
                errors += 1

        QMessageBox.information(
            self, "Toplu Kayıt",
            f"✅ {saved} kayıt başarıyla kaydedildi.\n❌ {errors} kayıt atlandı."
        )


# ═══════════════════ DASHBOARD DİALOGU ═══════════════════

class DashboardDialog(QDialog):
    """Sistem istatistiklerini gösteren dashboard paneli."""

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("📊 Dashboard — Sistem İstatistikleri")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(DIALOG_STYLE)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Başlık
        title = QLabel("📊  Sistem İstatistikleri")
        title.setObjectName("section_title")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        # İstatistikleri al
        try:
            stats = self.db.get_statistics()
        except Exception as e:
            import logging
            logging.error(f"Dashboard hatası: {e}")
            stats = {}

        # ── Kart Satırı 1: Genel Sayılar ──
        cards_row1 = QHBoxLayout()
        cards_row1.setSpacing(12)
        cards_row1.addWidget(self._make_card(
            "📁", "Toplam Belge",
            str(stats.get("total_documents", 0)),
            ACCENT
        ))
        
        # Benzersiz mahalle sayısını top_mahalle'den veya query'den alabiliriz
        # get_statistics() top_mahalle dönüyor, uzunluğu farklı mahalle sayısı hakkında fikir verir
        # veya en azından total_streets veya total_parcels gösterelim
        cards_row1.addWidget(self._make_card(
            "🏘️", "Sokak Sayısı",
            str(stats.get("total_streets", 0)),
            "#7c4dff"
        ))
        cards_row1.addWidget(self._make_card(
            "📋", "Parsel Sayısı",
            str(stats.get("total_parcels", 0)),
            "#ff6e40"
        ))
        layout.addLayout(cards_row1)

        # ── Kart Satırı 2: Durum ──
        by_status = stats.get("by_status", {})
        cards_row2 = QHBoxLayout()
        cards_row2.setSpacing(12)
        cards_row2.addWidget(self._make_card(
            "✅", "Onaylı",
            str(by_status.get("approved", 0)),
            SUCCESS
        ))
        cards_row2.addWidget(self._make_card(
            "⚠️", "İnceleme Bekliyor",
            str(by_status.get("needs_review", 0) + by_status.get("review", 0)),
            WARNING
        ))
        cards_row2.addWidget(self._make_card(
            "❌", "Başarısız",
            str(by_status.get("failed", 0) + by_status.get("error", 0)),
            ERROR
        ))
        layout.addLayout(cards_row2)

        # ── Son İşlenen Belgeler ──
        recent_title = QLabel("🕐  Son İşlenen Belgeler")
        recent_title.setStyleSheet(f"color: {ACCENT}; font-size: 14px; font-weight: bold; margin-top: 8px;")
        layout.addWidget(recent_title)

        recent_docs = stats.get("recent_documents", [])
        if recent_docs:
            recent_table = QTableWidget(min(len(recent_docs), 8), 4)
            recent_table.setHorizontalHeaderLabels(["ID", "Dosya", "Tür", "Tarih"])
            recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            recent_table.setMaximumHeight(250)
            recent_table.setAlternatingRowColors(True)
            recent_table.setStyleSheet(recent_table.styleSheet() + """
                QTableWidget { alternate-background-color: rgba(255,255,255,0.02); }
            """)
            for i, doc in enumerate(recent_docs[:8]):
                recent_table.setItem(i, 0, QTableWidgetItem(str(doc.get("id", ""))))
                recent_table.setItem(i, 1, QTableWidgetItem(str(doc.get("file", ""))))
                recent_table.setItem(i, 2, QTableWidgetItem(str(doc.get("type", ""))))
                recent_table.setItem(i, 3, QTableWidgetItem(str(doc.get("date", ""))))
            layout.addWidget(recent_table)
        else:
            no_data = QLabel("Henüz işlenmiş belge bulunmuyor.")
            no_data.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; padding: 20px;")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_data)

        layout.addStretch()

    def _make_card(self, icon: str, label: str, value: str, color: str) -> QFrame:
        """İstatistik kartı widget'ı oluşturur."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 12px;
                padding: 16px;
            }}
            QFrame:hover {{
                border-color: {color};
                background: rgba(30, 30, 34, 0.95);
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(6)
        card_layout.setContentsMargins(16, 12, 16, 12)

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 24px; border: none;")
        card_layout.addWidget(lbl_icon)

        lbl_value = QLabel(value)
        lbl_value.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold; border: none;")
        card_layout.addWidget(lbl_value)

        lbl_name = QLabel(label)
        lbl_name.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; border: none;")
        card_layout.addWidget(lbl_name)

        return card


class SettingsDialog(QDialog):
    """Sistem ayarlarını (API Anahtarları vb.) güncelleyen ekran (v8.5)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sistem Ayarları")
        self.setFixedSize(450, 250)
        self.setStyleSheet(DIALOG_STYLE)
        
        self.config_manager = ConfigManager()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 20)
        layout.setSpacing(20)
        
        title = QLabel("⚙️  Sistem Ayarları")
        title.setObjectName("section_title")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # API Anahtarı Formu
        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)
        
        lbl_api = QLabel("Google Gemini API Anahtarı:")
        lbl_api.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold;")
        self.txt_api = QLineEdit()
        self.txt_api.setPlaceholderText("AIzaSy...")
        self.txt_api.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.txt_api.setText(self.config_manager.get("google_api_key", ""))
        self.txt_api.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_INPUT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 10px;
                color: {TEXT_PRIMARY};
                font-family: Consolas, monospace;
            }}
            QLineEdit:focus {{
                border: 2px solid {ACCENT};
            }}
        """)
        
        form_layout.addWidget(lbl_api)
        form_layout.addWidget(self.txt_api)
        layout.addLayout(form_layout)
        
        layout.addStretch()
        
        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        btn_cancel = QPushButton("İptal")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{ background-color: {BORDER}; }}
        """)
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton("Kaydet")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #1d4ed8; }}
        """)
        btn_save.clicked.connect(self.save_settings)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
    def save_settings(self):
        new_key = self.txt_api.text().strip()
        if not new_key:
            QMessageBox.warning(self, "Uyarı", "API Anahtarı boş bırakılamaz.")
            return
            
        self.config_manager.set("google_api_key", new_key)
        QMessageBox.information(self, "Başarılı", "Ayarlar kaydedildi. Yeni işlemler bu API anahtarını kullanacak.")
        self.accept()
