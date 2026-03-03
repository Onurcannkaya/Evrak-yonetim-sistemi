"""
Sivas Belediyesi Evrak Yönetim Sistemi — NAPS2 Tarzı Arayüz
main_app.py — Ana uygulama penceresi
"""
import sys
import os
import json
import logging

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QMessageBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QTextEdit, QToolBar, QListWidget, QListWidgetItem, QScrollArea,
    QDialog, QFileDialog, QStatusBar, QSizePolicy, QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QPalette, QColor, QDragEnterEvent, QDropEvent, QIcon, QFont, QAction

from utils import archive_document, get_preview_image, generate_thumbnail
from ai_engine import DocumentAnalyzer
from database_manager import DatabaseManager
from tools import BatchWorker, PDFMerger, ExcelExporter


# ─────────────────────────── İŞ PARÇACIĞI ───────────────────────────
class WorkerThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, document_path, analyzer):
        super().__init__()
        self.document_path = document_path
        self.analyzer = analyzer

    def run(self):
        try:
            result = self.analyzer.analyze_document(self.document_path)
            if "error" in result and result["error"]:
                self.error.emit(result["error"])
            else:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────── SORGU DİALOGU ──────────────────────────────
class SearchDialog(QDialog):
    """Veritabanı arama penceresi."""

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Evrak Sorgulama")
        self.setMinimumSize(900, 600)
        self.setup_ui()
        self.load_all()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Başlık
        title = QLabel("🔍  Evrak Arama ve Sorgulama")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #8dd35f;")
        layout.addWidget(title)

        # Arama Barı
        bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Mahalle, Ada, Parsel veya metin içeriği ile arayın...")
        self.search_input.setStyleSheet(
            "padding:10px; border:1px solid #555; border-radius:6px; "
            "background:#2d2d2d; color:white; font-size:14px;"
        )
        self.search_input.returnPressed.connect(self.do_search)

        btn_search = QPushButton("Ara")
        btn_search.setStyleSheet(
            "padding:10px 20px; background:#4e9a06; color:white; "
            "border:none; border-radius:6px; font-weight:bold; font-size:14px;"
        )
        btn_search.clicked.connect(self.do_search)

        btn_all = QPushButton("Tümünü Göster")
        btn_all.setStyleSheet(
            "padding:10px 20px; background:#555; color:white; "
            "border:none; border-radius:6px; font-weight:bold; font-size:14px;"
        )
        btn_all.clicked.connect(self.load_all)

        bar.addWidget(self.search_input, stretch=1)
        bar.addWidget(btn_search)
        bar.addWidget(btn_all)
        layout.addLayout(bar)

        # Sonuç Tablosu
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Mahalle", "Ada", "Parsel", "Tarih"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setStyleSheet(
            "QTableWidget { background:#2d2d2d; color:white; gridline-color:#444; font-size:13px; }"
            "QHeaderView::section { background:#3a3a3a; color:white; padding:6px; border:1px solid #555; font-weight:bold; }"
        )
        self.table.itemDoubleClicked.connect(self.on_row_double_click)
        layout.addWidget(self.table, stretch=1)

        # Detay Kutusu
        self.detail_txt = QTextEdit()
        self.detail_txt.setReadOnly(True)
        self.detail_txt.setMaximumHeight(180)
        self.detail_txt.setStyleSheet(
            "background:#2d2d2d; color:#ccc; border:1px solid #444; "
            "border-radius:6px; padding:8px; font-size:13px;"
        )
        self.detail_txt.setPlaceholderText("Bir satıra çift tıklayarak detayları görüntüleyebilirsiniz...")
        layout.addWidget(self.detail_txt)

    def load_all(self):
        results = self.db.search_advanced()
        self._populate(results)

    def do_search(self):
        q = self.search_input.text().strip()
        if not q:
            self.load_all()
            return
        results = self.db.search_documents(q)
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

    def on_row_double_click(self, item):
        row = item.row()
        data = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if data:
            raw = data.get("raw_text", "Metin bulunamadı")
            fp = data.get("file_path", "")
            self.detail_txt.setText(f"📄 Dosya: {fp}\n\n--- Okunan Metin ---\n{raw}")


# ─────────────────────── ANA PENCERE ────────────────────────────────
class MainWindow(QMainWindow):
    SUPPORTED_EXTS = (".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sivas Belediyesi — Evrak Yönetim Sistemi")
        self.setMinimumSize(1200, 750)
        self.setAcceptDrops(True)

        self._apply_theme()

        # Motorlar
        try:
            self.analyzer = DocumentAnalyzer()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"AI Motoru başlatılamadı:\n{e}")
            self.analyzer = None

        self.db = DatabaseManager()

        # Durum değişkenleri
        self.loaded_files: list[str] = []      # Yüklenen dosya yolları
        self.selected_index: int = -1          # Seçili dosyanın indeksi
        self.ocr_results: dict[int, dict] = {} # indeks → OCR sonucu

        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

    # ───────── TEMA ─────────
    def _apply_theme(self):
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(32, 32, 32))
        pal.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        pal.setColor(QPalette.ColorRole.Base, QColor(40, 40, 40))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
        pal.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        pal.setColor(QPalette.ColorRole.Button, QColor(50, 50, 50))
        pal.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        pal.setColor(QPalette.ColorRole.Highlight, QColor(78, 154, 6))
        pal.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        QApplication.instance().setPalette(pal)

        self.setStyleSheet("""
            QMainWindow { background: #202020; }
            QToolBar { background: #2a2a2a; border-bottom: 1px solid #444; spacing: 6px; padding: 4px; }
            QToolBar QToolButton { 
                color: white; background: transparent; border: none; 
                padding: 8px 14px; font-size: 13px; border-radius: 4px;
            }
            QToolBar QToolButton:hover { background: #3d3d3d; }
            QToolBar QToolButton:pressed { background: #4e9a06; }
            QListWidget { background: #262626; border: none; outline: none; }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #333; }
            QListWidget::item:selected { background: #4e9a06; }
            QLineEdit, QTextEdit {
                padding: 8px; border: 1px solid #555; border-radius: 5px;
                background: #2d2d2d; color: white; font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus { border-color: #4e9a06; }
            QPushButton#btn_save {
                padding: 12px; background: #4e9a06; color: white;
                border: none; border-radius: 6px; font-size: 14px; font-weight: bold;
            }
            QPushButton#btn_save:hover { background: #61b510; }
            QPushButton#btn_save:disabled { background: #444; color: #777; }
            QSplitter::handle { background: #444; width: 2px; }
            QStatusBar { background: #262626; color: #aaa; font-size: 12px; }
        """)

    # ───────── ARAÇ ÇUBUĞU ─────────
    def _build_toolbar(self):
        tb = QToolBar("Ana Araçlar")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        self.act_import = QAction("📂  İçe Aktar", self)
        self.act_import.setToolTip("Belge dosyalarını içe aktarır (PDF / JPEG)")
        self.act_import.triggered.connect(self._action_import)
        tb.addAction(self.act_import)

        tb.addSeparator()

        self.act_ocr = QAction("🤖  OCR Yap", self)
        self.act_ocr.setToolTip("Seçili belgeyi Gemini AI ile analiz eder")
        self.act_ocr.triggered.connect(self._action_ocr)
        tb.addAction(self.act_ocr)

        self.act_save = QAction("💾  Kaydet", self)
        self.act_save.setToolTip("Analiz sonucunu veritabanına ve arşive kaydeder")
        self.act_save.triggered.connect(self._action_save)
        tb.addAction(self.act_save)

        tb.addSeparator()

        self.act_search = QAction("🔍  Sorgula", self)
        self.act_search.setToolTip("Kayıtlı belgelerde arama yapar")
        self.act_search.triggered.connect(self._action_search)
        tb.addAction(self.act_search)

        tb.addSeparator()

        self.act_delete = QAction("🗑️  Sil", self)
        self.act_delete.setToolTip("Seçili belgeyi listeden kaldırır")
        self.act_delete.triggered.connect(self._action_delete)
        tb.addAction(self.act_delete)

        tb.addSeparator()

        self.act_batch = QAction("📁  Toplu İşle", self)
        self.act_batch.setToolTip("Bir klasördeki tüm belgeleri otomatik analiz eder")
        self.act_batch.triggered.connect(self._action_batch)
        tb.addAction(self.act_batch)

        tb.addSeparator()

        self.act_pdf_merge = QAction("📑  PDF Birleştir", self)
        self.act_pdf_merge.setToolTip("Listedeki belgeleri tek bir PDF dosyasına birleştirir")
        self.act_pdf_merge.triggered.connect(self._action_pdf_merge)
        tb.addAction(self.act_pdf_merge)

        self.act_excel = QAction("📊  Excel Aktar", self)
        self.act_excel.setToolTip("Veritabanındaki kayıtları Excel dosyasına aktarır")
        self.act_excel.triggered.connect(self._action_excel)
        tb.addAction(self.act_excel)

    # ───────── MERKEZİ LAYOUT ─────────
    def _build_central(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(3)

        # SOL — Thumbnail Listesi
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)
        left_layout.setSpacing(6)

        lbl_docs = QLabel("Belgeler")
        lbl_docs.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_docs.setStyleSheet("color: #8dd35f; padding: 4px;")
        left_layout.addWidget(lbl_docs)

        self.thumb_list = QListWidget()
        self.thumb_list.setIconSize(QSize(100, 130))
        self.thumb_list.setSpacing(4)
        self.thumb_list.setMinimumWidth(160)
        self.thumb_list.currentRowChanged.connect(self._on_thumb_selected)
        left_layout.addWidget(self.thumb_list)

        hint = QLabel("Dosyaları buraya sürükleyebilirsiniz")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
        left_layout.addWidget(hint)

        splitter.addWidget(left)

        # SAĞ — Önizleme + Özellikler
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)
        right_layout.setSpacing(8)

        # Üst: Büyük önizleme
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setStyleSheet("QScrollArea { border: 1px solid #444; border-radius: 6px; background: #1a1a1a; }")
        
        self.preview_label = QLabel("Önizleme alanı — İçe aktar veya sürükle-bırak ile belge ekleyin")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("color: #666; font-size: 14px;")
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.preview_scroll.setWidget(self.preview_label)
        right_layout.addWidget(self.preview_scroll, stretch=3)

        # Alt: Özellikler Paneli
        props = QFrame()
        props.setStyleSheet("QFrame { background: #272727; border: 1px solid #3a3a3a; border-radius: 8px; padding: 10px; }")
        props_layout = QVBoxLayout(props)
        props_layout.setSpacing(6)

        prop_title = QLabel("Evrak Bilgileri")
        prop_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        prop_title.setStyleSheet("color: #8dd35f; border: none;")
        props_layout.addWidget(prop_title)

        row1 = QHBoxLayout()
        self.fields = {}
        for key, label_text in [("mahalle", "Mahalle"), ("ada", "Ada")]:
            col = QVBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #aaa; font-size: 12px; font-weight: bold; border: none;")
            txt = QLineEdit()
            txt.setPlaceholderText(label_text)
            self.fields[key] = txt
            col.addWidget(lbl)
            col.addWidget(txt)
            row1.addLayout(col)
        props_layout.addLayout(row1)

        row2 = QHBoxLayout()
        for key, label_text in [("parsel", "Parsel"), ("tarih", "Tarih")]:
            col = QVBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #aaa; font-size: 12px; font-weight: bold; border: none;")
            txt = QLineEdit()
            txt.setPlaceholderText(label_text)
            self.fields[key] = txt
            col.addWidget(lbl)
            col.addWidget(txt)
            row2.addLayout(col)
        props_layout.addLayout(row2)

        lbl_raw = QLabel("Okunan Metin")
        lbl_raw.setStyleSheet("color: #aaa; font-size: 12px; font-weight: bold; border: none;")
        props_layout.addWidget(lbl_raw)

        self.txt_raw = QTextEdit()
        self.txt_raw.setReadOnly(True)
        self.txt_raw.setMaximumHeight(120)
        self.txt_raw.setPlaceholderText("OCR sonuçları burada görünecek...")
        props_layout.addWidget(self.txt_raw)

        btn_row = QHBoxLayout()

        self.btn_save = QPushButton("💾  Sisteme Aktar / Arşivle")
        self.btn_save.setObjectName("btn_save")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._action_save)
        btn_row.addWidget(self.btn_save)

        self.btn_map = QPushButton("🗺️  Haritada Göster")
        self.btn_map.setObjectName("btn_save")
        self.btn_map.setEnabled(False)
        self.btn_map.clicked.connect(self._action_map)
        btn_row.addWidget(self.btn_map)

        props_layout.addLayout(btn_row)

        right_layout.addWidget(props, stretch=2)

        splitter.addWidget(right)
        splitter.setSizes([220, 780])

        self.setCentralWidget(splitter)

    # ───────── DURUM ÇUBUĞU ─────────
    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_msg = QLabel("Hazır")
        sb.addWidget(self.status_msg)

    # ═══════════ SÜRÜKLE-BIRAK ═══════════
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            fp = url.toLocalFile()
            if os.path.isfile(fp) and fp.lower().endswith(self.SUPPORTED_EXTS):
                paths.append(fp)
        if paths:
            self._add_files(paths)

    # ═══════════ TOOLBAR AKSIYONLARI ═══════════
    def _action_import(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Belge Seç", "",
            "Belge Dosyaları (*.pdf *.jpg *.jpeg *.png *.bmp *.tiff *.tif)"
        )
        if files:
            self._add_files(files)

    def _action_ocr(self):
        if self.selected_index < 0 or self.selected_index >= len(self.loaded_files):
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir belge seçin.")
            return
        if not self.analyzer:
            QMessageBox.warning(self, "Uyarı", "AI Motoru aktif değil.")
            return

        fp = self.loaded_files[self.selected_index]
        self._set_status("🤖 Analiz ediliyor... Lütfen bekleyin.", "#ffaa00")

        self.worker = WorkerThread(fp, self.analyzer)
        self.worker.finished.connect(self._on_ocr_done)
        self.worker.error.connect(self._on_ocr_error)
        self.worker.start()

    def _action_save(self):
        if self.selected_index < 0:
            return
        mahalle = self.fields["mahalle"].text().strip()
        ada = self.fields["ada"].text().strip()
        parsel = self.fields["parsel"].text().strip()
        tarih = self.fields["tarih"].text().strip()
        raw_text = self.txt_raw.toPlainText().strip()

        if not mahalle or not ada:
            QMessageBox.warning(self, "Eksik Bilgi", "Arşivlemek için en az Mahalle ve Ada bilgisi gereklidir.")
            return

        fp = self.loaded_files[self.selected_index]
        try:
            target = archive_document(fp, mahalle, ada)
            doc_data = {
                "image_path": target,
                "mahalle": mahalle,
                "ada": ada,
                "parsel": parsel,
                "tarih": tarih,
                "raw_text": raw_text,
                "corrected_text": raw_text,
                "doc_type": "general",
                "ocr_details": {"engine": "gemini-2.5-flash"}
            }
            self.db.add_document(doc_data)
            QMessageBox.information(self, "Başarılı", "Evrak başarıyla arşivlendi ve veritabanına kaydedildi!")
            self._set_status("✅ Evrak arşivlendi.", "#8dd35f")
            # İşlenen dosyayı listeden kaldır
            self._remove_current()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Arşivleme başarısız:\n{e}")

    def _action_search(self):
        dlg = SearchDialog(self.db, self)
        dlg.exec()

    def _action_delete(self):
        if self.selected_index < 0:
            QMessageBox.warning(self, "Uyarı", "Silinecek belge seçili değil.")
            return
        self._remove_current()

    def _action_batch(self):
        """Toplu İşleme — Klasör seçtirip tüm dosyaları sırayla analiz eder."""
        if not self.analyzer:
            QMessageBox.warning(self, "Uyarı", "AI Motoru aktif değil.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Belge Klasörünü Seçin")
        if not folder:
            return
        files = [os.path.join(folder, f) for f in os.listdir(folder)
                 if f.lower().endswith(self.SUPPORTED_EXTS)]
        if not files:
            QMessageBox.information(self, "Bilgi", "Seçilen klasörde desteklenen dosya bulunamadı.")
            return

        # Dosyaları listeye ekle
        self._add_files(files)

        # İlerleme dialogu
        self.batch_progress = QProgressDialog("Toplu işleme başlatılıyor...", "İptal", 0, len(files), self)
        self.batch_progress.setWindowTitle("Toplu İşleme")
        self.batch_progress.setMinimumDuration(0)
        self.batch_progress.setWindowModality(Qt.WindowModality.WindowModal)

        self.batch_worker = BatchWorker(files, self.analyzer)
        self.batch_worker.progress.connect(self._on_batch_progress)
        self.batch_worker.item_done.connect(self._on_batch_item_done)
        self.batch_worker.all_done.connect(self._on_batch_all_done)
        self.batch_worker.error.connect(self._on_batch_error)
        self.batch_progress.canceled.connect(self.batch_worker.cancel)
        self.batch_worker.start()

    def _on_batch_progress(self, current, total, filename):
        self.batch_progress.setValue(current)
        self.batch_progress.setLabelText(f"İşleniyor ({current}/{total}): {filename}")
        self._set_status(f"🤖 Toplu İşleme: {current}/{total} — {filename}", "#ffaa00")

    def _on_batch_item_done(self, idx, result):
        # Dosyanın listemizdeki konumunu bul ve OCR sonucunu kaydet
        fp = result.get("_source_file", "")
        if fp in self.loaded_files:
            list_idx = self.loaded_files.index(fp)
            self.ocr_results[list_idx] = result

    def _on_batch_all_done(self, results):
        self.batch_progress.close()
        success = sum(1 for r in results if "error" not in r or not r["error"])
        fail = len(results) - success
        QMessageBox.information(self, "Toplu İşleme Tamamlandı",
            f"Toplam: {len(results)}\n✅ Başarılı: {success}\n❌ Başarısız: {fail}")
        self._set_status(f"✅ Toplu işleme tamamlandı: {success}/{len(results)} başarılı.", "#8dd35f")
        # Mevcut seçimi yenile
        if self.selected_index >= 0:
            self._on_thumb_selected(self.selected_index)

    def _on_batch_error(self, idx, msg):
        logging.warning(f"Toplu İşleme Hata [Dosya #{idx}]: {msg}")

    def _action_pdf_merge(self):
        """Listedeki dosyaları tek bir PDF'e birleştirir."""
        if not self.loaded_files:
            QMessageBox.warning(self, "Uyarı", "Listeye birleştirilecek dosya eklenmemiş.")
            return
        out, _ = QFileDialog.getSaveFileName(self, "PDF Kaydet", "birlestirilmis.pdf", "PDF (*.pdf)")
        if not out:
            return
        try:
            PDFMerger.merge(self.loaded_files, out)
            QMessageBox.information(self, "Başarılı", f"PDF dosyası oluşturuldu:\n{out}")
            self._set_status(f"📑 PDF birleştirildi: {out}", "#8dd35f")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PDF birleştirme başarısız:\n{e}")

    def _action_excel(self):
        """Veritabanındaki tüm kayıtları Excel dosyasına aktarır."""
        out, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "evrak_raporu.xlsx", "Excel (*.xlsx)")
        if not out:
            return
        try:
            data = self.db.search_advanced()
            columns = ["id", "p_mahalle", "ada", "parsel", "extracted_date", "raw_text"]
            ExcelExporter.export(data, out, columns)
            QMessageBox.information(self, "Başarılı", f"Excel raporu oluşturuldu:\n{out}")
            self._set_status(f"📊 Excel aktarıldı: {out}", "#8dd35f")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel aktarımı başarısız:\n{e}")

    def _action_map(self):
        """Haritada Göster — CBS entegrasyonu hazırlığı."""
        mahalle = self.fields["mahalle"].text().strip()
        ada = self.fields["ada"].text().strip()
        parsel = self.fields["parsel"].text().strip()
        if not ada:
            QMessageBox.information(self, "Bilgi", "Haritada göstermek için en az Ada bilgisi gereklidir.")
            return
        log_msg = f"🗺️ CBS HAZIRLIK — Mahalle: {mahalle}, Ada: {ada}, Parsel: {parsel}"
        logging.info(log_msg)
        self._set_status(log_msg, "#55aaff")
        QMessageBox.information(self, "Harita Bilgisi",
            f"Koordinat bilgisi loga kaydedildi.\n\n"
            f"Mahalle: {mahalle}\nAda: {ada}\nParsel: {parsel}\n\n"
            f"(CBS entegrasyonu yakında eklenecektir.)")

    # ═══════════ DOSYA YÖNETİMİ ═══════════
    def _add_files(self, paths: list[str]):
        for fp in paths:
            if fp in self.loaded_files:
                continue
            self.loaded_files.append(fp)
            thumb = generate_thumbnail(fp)
            item = QListWidgetItem()
            item.setIcon(QIcon(thumb))
            item.setText(os.path.basename(fp))
            item.setToolTip(fp)
            self.thumb_list.addItem(item)

        # İlk eklenen dosyayı seç
        if self.thumb_list.count() > 0 and self.selected_index < 0:
            self.thumb_list.setCurrentRow(0)

        self._set_status(f"📁 {len(self.loaded_files)} belge yüklendi.", "#8dd35f")

    def _remove_current(self):
        if self.selected_index < 0:
            return
        idx = self.selected_index
        self.loaded_files.pop(idx)
        self.ocr_results.pop(idx, None)
        # OCR sonuçlarının indekslerini güncelle
        new_ocr = {}
        for k, v in self.ocr_results.items():
            if k > idx:
                new_ocr[k - 1] = v
            else:
                new_ocr[k] = v
        self.ocr_results = new_ocr

        self.thumb_list.takeItem(idx)
        self.selected_index = -1
        self._clear_properties()
        self.preview_label.clear()
        self.preview_label.setText("Önizleme alanı")
        if self.thumb_list.count() > 0:
            self.thumb_list.setCurrentRow(min(idx, self.thumb_list.count() - 1))

    # ═══════════ SEÇIM & ÖNİZLEME ═══════════
    def _on_thumb_selected(self, row: int):
        self.selected_index = row
        if row < 0 or row >= len(self.loaded_files):
            return
        fp = self.loaded_files[row]

        # Büyük önizleme
        try:
            preview = get_preview_image(fp)
            pix = QPixmap(preview)
            if not pix.isNull():
                scaled = pix.scaled(
                    self.preview_scroll.size() * 0.95,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled)
        except Exception:
            self.preview_label.setText("Önizleme yüklenemedi")

        # OCR sonuçları varsa doldur
        if row in self.ocr_results:
            self._fill_properties(self.ocr_results[row])
        else:
            self._clear_properties()

    # ═══════════ OCR CALLBACK ═══════════
    def _on_ocr_done(self, result: dict):
        self._set_status("✅ OCR tamamlandı!", "#8dd35f")
        if self.selected_index >= 0:
            self.ocr_results[self.selected_index] = result
        self._fill_properties(result)

    def _on_ocr_error(self, msg: str):
        self._set_status("❌ OCR hatası!", "#ff5555")
        QMessageBox.critical(self, "OCR Hatası", f"Belge analiz edilirken sorun oluştu:\n{msg}")

    # ═══════════ YARDIMCI ═══════════
    def _fill_properties(self, data: dict):
        self.fields["mahalle"].setText(data.get("mahalle", ""))
        self.fields["ada"].setText(data.get("ada", ""))
        self.fields["parsel"].setText(data.get("parsel", ""))
        self.fields["tarih"].setText(data.get("tarih", ""))
        self.txt_raw.setText(data.get("raw_text", ""))
        self.btn_save.setEnabled(True)
        self.btn_map.setEnabled(True)

    def _clear_properties(self):
        for f in self.fields.values():
            f.clear()
        self.txt_raw.clear()
        self.btn_save.setEnabled(False)
        self.btn_map.setEnabled(False)

    def _set_status(self, text: str, color: str = "#aaa"):
        self.status_msg.setText(text)
        self.status_msg.setStyleSheet(f"color: {color}; font-weight: bold;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.selected_index >= 0 and self.preview_label.pixmap() and not self.preview_label.pixmap().isNull():
            fp = self.loaded_files[self.selected_index]
            try:
                preview = get_preview_image(fp)
                pix = QPixmap(preview)
                scaled = pix.scaled(
                    self.preview_scroll.size() * 0.95,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled)
            except Exception:
                pass


# ═══════════ GİRİŞ NOKTASI ═══════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
