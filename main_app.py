"""
Sivas Belediyesi Evrak Yönetim Sistemi — v6.0
main_app.py — Ana uygulama penceresi
"""
import sys
import os
import json
import logging
import webbrowser

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QMessageBox, QSplitter,
    QTextEdit, QToolBar, QListWidget, QListWidgetItem, QScrollArea,
    QFileDialog, QStatusBar, QSizePolicy, QProgressDialog, QDialog
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import (
    QPixmap, QDragEnterEvent, QDropEvent, QFont, QAction,
    QIcon,
)

from utils import archive_document, get_preview_image, generate_thumbnail, get_resource_dir
from ai_engine import DocumentAnalyzer
from database_manager import DatabaseManager
from tools import BatchWorker, PDFMerger, ExcelExporter

from ui.theme import apply_theme, ACCENT, TEXT_SECONDARY, BORDER, BG_CARD
from ui.workers import WorkerThread, TableWorkerThread
from ui.dialogs import SearchDialog, TableResultsDialog, DashboardDialog, LoginDialog, SettingsDialog
from ui.widgets import ZoomableGraphicsView


# ─────────────────────── ANA PENCERE ────────────────────────────────
class MainWindow(QMainWindow):
    SUPPORTED_EXTS = (".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sivas Belediyesi — Evrak Yönetim Sistemi")
        self.setMinimumSize(1200, 750)
        self.setAcceptDrops(True)

        apply_theme(self)

        # Motorlar
        try:
            self.analyzer = DocumentAnalyzer()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"AI Motoru başlatılamadı:\n{e}")
            self.analyzer = None

        self.db = DatabaseManager()

        # Durum değişkenleri
        self.logged_in_user = None
        self.user_data = None
        self.loaded_files: list[str] = []
        self.selected_index: int = -1
        self.ocr_results: dict[int, dict] = {}
        self._cached_pixmap = None
        self._cached_path = None

        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """Klavye kısayollarını tanımlar (v7.0)"""
        import PyQt6.QtGui as QtGui
        
        # Ctrl+S: Kaydet
        shortcut_save = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        shortcut_save.activated.connect(self._action_save)
        
        # Enter: Listedeki bir sonraki elemana geç
        shortcut_next = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Return), self)
        shortcut_next.activated.connect(self._select_next_item)
        
        # Enter (Numpad)
        shortcut_next_num = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Enter), self)
        shortcut_next_num.activated.connect(self._select_next_item)

    def _select_next_item(self):
        """Enter'a basıldığında listedeki bir sonraki evraka geçer."""
        if self.thumb_list.count() > 0:
            current = self.thumb_list.currentRow()
            next_row = current + 1
            if next_row < self.thumb_list.count():
                self.thumb_list.setCurrentRow(next_row)
            else:
                self._set_status("Son evraktasınız.", "#ffc107")

    # ───────── ARAÇ ÇUBUĞU ─────────
    def _build_toolbar(self):
        tb = QToolBar("Ana Araçlar")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        actions = [
            ("📂  İçe Aktar", "Belge dosyalarını içe aktarır (PDF / JPEG)", self._action_import),
            None,  # separator
            ("🤖  OCR Yap", "Seçili belgeyi Gemini AI ile analiz eder", self._action_ocr),
            ("📊  Tablo OCR", "Seçili belgedeki tablo verilerini çıkarır", self._action_table_ocr),
            ("💾  Kaydet", "Analiz sonucunu veritabanına ve arşive kaydeder", self._action_save),
            None,
            ("🔍  Sorgula", "Kayıtlı belgelerde arama yapar", self._action_search),
            ("📊  Dashboard", "Sistem istatistiklerini gösterir", self._action_dashboard),
            None,
            ("⚙️  Ayarlar", "API Anahtarı ve sistem ayarları", self._action_settings),
            None,
            ("🗑️  Sil", "Seçili belgeyi listeden kaldırır", self._action_delete),
            None,
            ("📁  Toplu İşle", "Bir klasördeki tüm belgeleri otomatik analiz eder", self._action_batch),
            ("📄  PDF Birleştir", "Listedeki belgeleri tek bir PDF dosyasına birleştirir", self._action_pdf_merge),
            ("📈  Excel Aktar", "Veritabanındaki kayıtları Excel dosyasına aktarır", self._action_excel),
        ]

        for item in actions:
            if item is None:
                tb.addSeparator()
            else:
                text, tip, handler = item
                act = QAction(text, self)
                act.setToolTip(tip)
                act.triggered.connect(handler)
                tb.addAction(act)

        # Global Search Bar (Sağa Yaslı)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.global_search_input = QLineEdit()
        self.global_search_input.setPlaceholderText("🔍  Hızlı Arama (Tüm kelimeler)...")
        self.global_search_input.setMinimumWidth(250)
        self.global_search_input.setStyleSheet("padding: 6px; border-radius: 6px;")
        self.global_search_input.returnPressed.connect(self._action_global_search)
        tb.addWidget(self.global_search_input)

        self.btn_global_search = QPushButton("Ara")
        self.btn_global_search.setStyleSheet("padding: 6px 12px; border-radius: 6px; background-color: #2563eb; color: white; font-weight: bold;")
        self.btn_global_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_global_search.clicked.connect(self._action_global_search)
        tb.addWidget(self.btn_global_search)

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
        lbl_docs.setStyleSheet(f"color: {ACCENT}; padding: 4px;")
        left_layout.addWidget(lbl_docs)

        self.thumb_list = QListWidget()
        self.thumb_list.setIconSize(QSize(100, 130))
        self.thumb_list.setSpacing(4)
        self.thumb_list.setMinimumWidth(160)
        self.thumb_list.currentRowChanged.connect(self._on_thumb_selected)
        left_layout.addWidget(self.thumb_list)

        hint = QLabel("Dosyaları buraya sürükleyebilirsiniz")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; padding: 4px;")
        left_layout.addWidget(hint)

        splitter.addWidget(left)

        # SAĞ — Önizleme + Özellikler
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)
        right_layout.setSpacing(8)

        # Üst: Büyük Önizleme (ZoomableGraphicsView - v7.0)
        self.preview_view = ZoomableGraphicsView()
        right_layout.addWidget(self.preview_view, stretch=3)

        # Alt: Özellikler Paneli
        props = QFrame()
        props.setObjectName("props_frame")
        props_layout = QVBoxLayout(props)
        props_layout.setSpacing(8)

        prop_title = QLabel("Evrak Bilgileri")
        prop_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        prop_title.setStyleSheet(f"color: {ACCENT}; border: none;")
        props_layout.addWidget(prop_title)

        row1 = QHBoxLayout()
        self.fields = {}
        for key, label_text in [("mahalle", "Mahalle"), ("ada", "Ada")]:
            col = QVBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold; border: none;")
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
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold; border: none;")
            txt = QLineEdit()
            txt.setPlaceholderText(label_text)
            self.fields[key] = txt
            col.addWidget(lbl)
            col.addWidget(txt)
            row2.addLayout(col)
        props_layout.addLayout(row2)

        lbl_raw = QLabel("Okunan Metin")
        lbl_raw.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold; border: none;")
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

    # ═══════════ TOOLBAR AKSİYONLARI ═══════════
    def _action_import(self):
        try:
            files, _ = QFileDialog.getOpenFileNames(
                self, "Belge Seç", "",
                "Belge Dosyaları (*.pdf *.jpg *.jpeg *.png *.bmp *.tiff *.tif)"
            )
            if files:
                self._add_files(files)
        except Exception as e:
            QMessageBox.critical(self, "İçe Aktarma Hatası", f"Dosyalar seçilirken hata oluştu:\n{e}")

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

    def _on_ocr_done(self, result: dict):
        if result.get("error"):
            self._set_status(f"❌ OCR hatası: {str(result['error'])[:50]}...", "#ff4757")
            if self.selected_index >= 0:
                self._update_item_badge(self.selected_index, "failed")
            QMessageBox.critical(self, "OCR Hatası", f"Belge analiz edilirken sorun oluştu:\n{result['error']}")
            return
            
        self._set_status("✅ OCR tamamlandı!", "#00d47e")
        if self.selected_index >= 0:
            self.ocr_results[self.selected_index] = result
            self._update_item_badge(self.selected_index, "approved" if result.get("ocr_details", {}).get("engine") == "gemini-2.5-flash" else "needs_review")
        self._fill_properties(result)

    def _on_ocr_error(self, msg: str):
        self._set_status("❌ OCR hatası!", "#ff4757")
        if self.selected_index >= 0:
            self._update_item_badge(self.selected_index, "failed")
        QMessageBox.critical(self, "OCR Hatası", f"Belge analiz edilirken sorun oluştu:\n{msg}")

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

        # Duplikasyon kontrolü
        dup = self.db.check_duplicate(fp)
        if dup:
            reply = QMessageBox.question(self, "Duplikasyon Uyarısı",
                f"Bu dosya daha önce işlenmiş (ID: {dup.get('id')}).\nYine de kaydetmek istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

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
            self._set_status("✅ Evrak arşivlendi.", "#00d47e")
            self._action_map()
            self._remove_current()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Arşivleme başarısız:\n{e}")

    def _action_delete(self):
        """Seçili belgeyi tablodan/listeden siler"""
        if self.selected_index < 0 or self.selected_index >= len(self.loaded_files):
            QMessageBox.warning(self, "Uyarı", "Silmek için bir belge seçin.")
            return

        item = self.thumb_list.currentItem()
        if not item: return

        reply = QMessageBox.question(
            self, "Onay", "Seçili belgeyi uygulamadan kaldırmak istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.loaded_files.pop(self.selected_index)
            if self.selected_index in self.ocr_results:
                del self.ocr_results[self.selected_index]
            self._fill_thumbnails()
            self._set_status("Belge silindi.")
            
    def _action_settings(self):
        """Ayarlar diyaloğunu açar"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Restart Analyzer with new key
            try:
                self.analyzer = DocumentAnalyzer()
                self._set_status("Ayarlar güncellendi: Yeni API Anahtarı aktif.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"API Anahtarı geçersiz veya motor başlatılamadı:\n{e}")
                self.analyzer = None

    def _action_table_ocr(self):
        """Tablo OCR — Seçili belgedeki tablo verilerini çıkarır."""
        if self.selected_index < 0 or self.selected_index >= len(self.loaded_files):
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir belge seçin.")
            return
        if not self.analyzer:
            QMessageBox.warning(self, "Uyarı", "AI Motoru aktif değil.")
            return

        fp = self.loaded_files[self.selected_index]
        self._set_status("📊 Tablo analiz ediliyor... Bu işlem 30-60 saniye sürebilir.", "#ffaa00")

        self._table_worker = TableWorkerThread(fp, self.analyzer)
        self._table_worker.finished.connect(self._on_table_ocr_done)
        self._table_worker.error.connect(self._on_ocr_error)
        self._table_worker.start()

    def _on_table_ocr_done(self, result: dict):
        """Tablo OCR tamamlandığında sonuçları göster."""
        row_count = result.get("row_count", 0)
        self._set_status(f"✅ Tablo OCR tamamlandı! {row_count} satır bulundu.", "#00d47e")

        if row_count > 0:
            dlg = TableResultsDialog(result, self.db, self)
            dlg.exec()
        else:
            QMessageBox.information(self, "Tablo OCR", "Belgede tablo verisi bulunamadı.")
            self._fill_properties(result)

    def _action_search(self):
        dlg = SearchDialog(self.db, self)
        dlg.exec()

    def _action_dashboard(self):
        dlg = DashboardDialog(self.db, self)
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

        self._add_files(files)

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
        fp = result.get("_source_file", "")
        if fp in self.loaded_files:
            list_idx = self.loaded_files.index(fp)
            self.ocr_results[list_idx] = result
            self._update_item_badge(list_idx, "approved" if result.get("ocr_details", {}).get("engine") == "gemini-2.5-flash" else "needs_review")

    def _on_batch_all_done(self, results):
        self.batch_progress.close()
        success = sum(1 for r in results if "error" not in r or not r["error"])
        fail = len(results) - success
        QMessageBox.information(self, "Toplu İşleme Tamamlandı",
            f"Toplam: {len(results)}\n✅ Başarılı: {success}\n❌ Başarısız: {fail}")
        self._set_status(f"✅ Toplu işleme tamamlandı: {success}/{len(results)} başarılı.", "#00d47e")
        if self.selected_index >= 0:
            self._on_thumb_selected(self.selected_index)

    def _on_batch_error(self, idx, msg):
        logging.warning(f"Toplu İşleme Hata [Dosya #{idx}]: {msg}")
        if idx < len(self.loaded_files):
            self._update_item_badge(idx, "failed")

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
            self._set_status(f"📄 PDF birleştirildi: {out}", "#00d47e")
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
            self._set_status(f"📈 Excel aktarıldı: {out}", "#00d47e")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel aktarımı başarısız:\n{e}")

    def _action_map(self):
        """Haritada Göster — Sivas Belediyesi CBS Entegrasyonu."""
        mahalle = self.fields["mahalle"].text().strip()
        ada = self.fields["ada"].text().strip()
        parsel = self.fields["parsel"].text().strip()
        if not ada:
            QMessageBox.information(self, "Bilgi", "Haritada göstermek için en az Ada bilgisi gereklidir.")
            return
            
        # Sivas Kent Rehberi (Özel URL Formatı / Varsayılan Format)
        # Örnek gerçeğe yakın format: https://kentrehberi.sivas.bel.tr/map?mahalle={}&ada={}&parsel={}
        import urllib.parse
        base_url = "https://kentrehberi.sivas.bel.tr/map"
        params = {"ada": ada}
        if mahalle: params["mahalle"] = mahalle
        if parsel: params["parsel"] = parsel
            
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        log_msg = f"🗺️ CBS SORGUSU — Mahalle: {mahalle}, Ada: {ada}, Parsel: {parsel} | URL: {url}"
        logging.info(log_msg)
        self._set_status(log_msg, "#55aaff")
        
        try:
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Tarayıcı açılamadı:\n{e}")

    # ═══════════ DOSYA YÖNETİMİ ═══════════
    def _create_badged_icon(self, thumb_path: str, status: str = "pending") -> QIcon:
        """Küçük resim üzerine durum rozeti (badge) çizer."""
        from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
        
        pixmap = QPixmap(thumb_path)
        if pixmap.isNull():
            return QIcon()
            
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Durum renkleri
        colors = {
            "pending": QColor(245, 158, 11),  # Amber/Sarı
            "approved": QColor(16, 185, 129), # Zümrüt/Yeşil
            "needs_review": QColor(59, 130, 246), # Mavi
            "failed": QColor(239, 68, 68)     # Kırmızı
        }
        
        color = colors.get(status, QColor(100, 100, 100))
        
        # Sağ üst köşeye çiz
        radius = 12
        margin = 4
        x = pixmap.width() - (radius * 2) - margin
        y = margin
        
        # Gölge/Dış çerçeve
        painter.setPen(QPen(QColor(0, 0, 0, 150), 2))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(x, y, radius * 2, radius * 2)
        
        painter.end()
        return QIcon(pixmap)

    def _update_item_badge(self, row: int, status: str):
        """Listedeki öğenin simgesini durum rozeti ile günceller."""
        if 0 <= row < self.thumb_list.count():
            item = self.thumb_list.item(row)
            thumb = generate_thumbnail(self.loaded_files[row])
            item.setIcon(self._create_badged_icon(thumb, status))

    def _add_files(self, paths: list[str]):
        try:
            for fp in paths:
                if fp in self.loaded_files:
                    continue
                self.loaded_files.append(fp)
                thumb = generate_thumbnail(fp)
                item = QListWidgetItem()
                item.setIcon(self._create_badged_icon(thumb, "pending"))
                item.setText(os.path.basename(fp))
                item.setToolTip(fp)
                self.thumb_list.addItem(item)
                
                # Başlangıçta ocr_results dictionary'sine boş değer atma
                list_idx = len(self.loaded_files) - 1
                if list_idx not in self.ocr_results:
                    pass # Sadece listeye eklendi

            if self.thumb_list.count() > 0 and self.selected_index < 0:
                self.thumb_list.setCurrentRow(0)

            self._set_status(f"📁 {len(self.loaded_files)} belge yüklendi.", "#00d47e")
        except Exception as e:
            QMessageBox.critical(self, "Dosya Yükleme Hatası", f"Dosyalar yüklenirken hata oluştu:\n{e}")

    def _remove_current(self):
        if self.selected_index < 0:
            return
        idx = self.selected_index
        self.loaded_files.pop(idx)
        self.ocr_results.pop(idx, None)
        new_ocr = {}
        for k, v in self.ocr_results.items():
            if k > idx:
                new_ocr[k - 1] = v
            else:
                new_ocr[k] = v
        self.ocr_results = new_ocr

        self.thumb_list.takeItem(idx)
        self.selected_index = -1
        self._cached_pixmap = None
        self._cached_path = None
        self._clear_properties()
        self.preview_view.scene.clear()
        
        if self.thumb_list.count() > 0:
            self.thumb_list.setCurrentRow(min(idx, self.thumb_list.count() - 1))

    # ═══════════ SEÇİM & ÖNİZLEME ═══════════
    def _on_thumb_selected(self, row: int):
        self.selected_index = row
        if row < 0 or row >= len(self.loaded_files):
            return
        fp = self.loaded_files[row]

        # Büyük önizleme (cache'li)
        try:
            preview = get_preview_image(fp)
            if self._cached_path != preview:
                self._cached_pixmap = QPixmap(preview)
                self._cached_path = preview
            if self._cached_pixmap and not self._cached_pixmap.isNull():
                self.preview_view.set_image(self._cached_pixmap)
        except Exception:
            self.preview_view.scene.clear()

        # OCR sonuçları varsa doldur
        if row in self.ocr_results:
            self._fill_properties(self.ocr_results[row])
        else:
            self._clear_properties()

        # Update Save Button State (Eğer db_record ise pasif yap)
        item = self.thumb_list.item(row)
        if item and item.data(Qt.ItemDataRole.UserRole) == "db_record":
            self.btn_save.setEnabled(False)
            self.btn_save.setText("Kayıtlı Evrak")
            # Butonu güncellemek yerine readonly yapabilir
        elif self.user_data and self.user_data.get('role') != 'admin':
            self.btn_save.setEnabled(False)
            self.btn_save.setText("Yetki Yok")
        else:
            self.btn_save.setEnabled(True)
            self.btn_save.setText("💾 Kaydet")

    def _action_global_search(self):
        """Global arama barı üzerinden FTS5 ile arama yapar ve sol listeyi günceller."""
        query = self.global_search_input.text().strip()
        if not query:
            self._set_status("Arama kutusu boş.", "#ffc107")
            return
            
        try:
            results = self.db.search_documents(query)
            
            # Listeyi temizle
            self.thumb_list.clear()
            self.loaded_files.clear()
            self.ocr_results.clear()
            self.preview_view.scene.clear()
            self._clear_properties()
            
            if not results:
                self._set_status(f"'{query}' için sonuç bulunamadı.", "#ffc107")
                return

            list_index = 0
            for r in results:
                fp = r.get("image_path") or r.get("file_path")
                if fp and os.path.exists(fp):
                    self.loaded_files.append(fp)
                    self.ocr_results[list_index] = r
                    list_index += 1
                    
                    item = QListWidgetItem(f"[{r.get('ada')}/{r.get('parsel')}] - {os.path.basename(fp)}")
                    item.setData(Qt.ItemDataRole.UserRole, "db_record")
                    
                    icon_path = os.path.join(get_resource_dir(), "assets", "badge_approved.png")
                    if os.path.exists(icon_path):
                        item.setIcon(QIcon(icon_path))

                    self.thumb_list.addItem(item)
                    
            self._set_status(f"FTS5 Arama Tamamlandı: {len(self.loaded_files)} sonuç listelendi.", "#00d47e")
            
            if self.thumb_list.count() > 0:
                self.thumb_list.setCurrentRow(0)
                
        except Exception as e:
            logging.error(f"Arama Hatası: {e}")
            self._set_status(f"Arama Hatası: {e}", ERROR)

    # ═══════════ YARDIMCI ═══════════
    def _fill_properties(self, data: dict):
        self.fields["mahalle"].setText(data.get("mahalle", ""))
        self.fields["ada"].setText(data.get("ada", ""))
        self.fields["parsel"].setText(data.get("parsel", ""))
        self.fields["tarih"].setText(data.get("tarih", ""))
        self.txt_raw.setText(data.get("raw_text", ""))
        
        # RBAC Check (v7.0)
        if self.logged_in_user and self.logged_in_user.get("role") == "admin":
            self.btn_save.setEnabled(True)
        else:
            self.btn_save.setEnabled(False)
            self.btn_save.setToolTip("Kaydetmek için Admin yetkisi gereklidir.")
            
        self.btn_map.setEnabled(True)

    def _clear_properties(self):
        for f in self.fields.values():
            f.clear()
        self.txt_raw.clear()
        self.btn_save.setEnabled(False)
        self.btn_map.setEnabled(False)

    def _set_status(self, text: str, color: str = "#8a8a96"):
        self.status_msg.setText(text)
        self.status_msg.setStyleSheet(f"color: {color}; font-weight: bold;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.selected_index >= 0 and self._cached_pixmap and not self._cached_pixmap.isNull():
            self.preview_view.fitInView(self.preview_view.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def closeEvent(self, event):
        """Uygulama kapanırken dosya kilitlerini serbest bırakır ve temp dosyaları temizler."""
        # QPixmap dosya kilidini kaldır
        self._cached_pixmap = None
        self._cached_path = None
        self.preview_view.scene.clear()
        
        # Temp dizinini temizle
        from utils import cleanup_temp_dir
        cleanup_temp_dir()
        
        super().closeEvent(event)


# ═══════════ GİRİŞ NOKTASI ═══════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    
    # 1. Veritabanı (Login için gerekli)
    db = DatabaseManager()
    
    # 2. Login Ekranı (v7.0)
    login = LoginDialog(db)
    if login.exec() == QDialog.DialogCode.Accepted:
        user = login.user_data
        
        # 3. Ana Pencere
        window = MainWindow()
        window.db = db # Aynı instance
        window.logged_in_user = user
        window.user_data = user
        
        # Başlık, İkon ve Statüs
        window.setWindowTitle(f"Sivas Belediyesi — Evrak Yönetim Sistemi (Kullanıcı: {user['username']} - Rol: {user['role'].upper()})")
        app_icon_path = os.path.join(get_resource_dir(), "assets", "icon.ico")
        if os.path.exists(app_icon_path):
            window.setWindowIcon(QIcon(app_icon_path))
        window._set_status(f"Hoş geldiniz, {user['username']}. Oturum açıldı.")
        
        # RBAC Toplu İşlemi Gizle (İsteğe bağlı, personel yetkisi yoksa toolbar modify edilebilir)
        if user['role'] != 'admin':
            pass # Currently saving is blocked in _fill_properties
            
        window.show()
        sys.exit(app.exec())
    else:
        # Uygulama kapatıldı
        sys.exit(0)
