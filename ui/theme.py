"""
Evrak Yönetim Sistemi — Tema & Stil Tanımları
Özel Glassmorphism (Cam Efekti) / Gradient Teması
"""
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor

# ─────────── GLASSMORPHISM RENK PALETİ ───────────
BG_DARK        = "#0d0d14"  # Çok Koyu Lacivert/Siyah
BG_PANEL       = "rgba(255, 255, 255, 0.03)" # Yarı Saydam Panel
BG_CARD        = "rgba(0, 0, 0, 0.4)" # Yarı Saydam Kart
BG_INPUT       = "rgba(0, 0, 0, 0.2)"
BORDER         = "rgba(255, 255, 255, 0.1)"
BORDER_FOCUS   = "#00d4aa"
TEXT_PRIMARY   = "#ffffff"
TEXT_SECONDARY = "#a0a0b0"
TEXT_MUTED     = "#505060"

# ANA VURGU RENGİ (Gradient'li Yeşil/Turkuaz)
ACCENT         = "#00d4aa"
ACCENT_BG      = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d4aa, stop:1 #00b897)"
ACCENT_HOVER   = "#00e8bc"

# Durum Renkleri
SUCCESS        = "#10b981"
WARNING        = "#f59e0b"
ERROR          = "#ef4444"

STYLES = f"""
    QMainWindow {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #09090e, stop:0.5 #111118, stop:1 #09090e
        );
    }}

    /* ── Toolbar ── */
    QToolBar {{
        background: {BG_PANEL};
        border-bottom: 1px solid {BORDER};
        spacing: 6px;
        padding: 8px 16px;
    }}
    QToolBar QToolButton {{
        color: {TEXT_PRIMARY};
        background: transparent;
        border: 1px solid transparent;
        padding: 8px 16px;
        font-size: 13px;
        border-radius: 8px;
        font-weight: bold;
    }}
    QToolBar QToolButton:hover {{
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid {BORDER};
    }}
    QToolBar QToolButton:pressed {{
        background: {ACCENT_BG};
        color: #000000;
    }}

    /* ── Soldan Belge Listesi ── */
    QListWidget {{
        background: {BG_PANEL};
        border: 1px solid {BORDER};
        border-radius: 12px;
        outline: none;
        padding: 8px;
    }}
    QListWidget::item {{
        padding: 8px 12px;
        border-radius: 8px;
        margin: 2px 0;
        color: {TEXT_PRIMARY};
    }}
    QListWidget::item:selected {{
        background: rgba(0, 212, 170, 0.2);
        color: {TEXT_PRIMARY};
        border-left: 3px solid {ACCENT};
        font-weight: bold;
    }}
    QListWidget::item:hover:!selected {{
        background: rgba(255, 255, 255, 0.05);
    }}

    /* ── Giriş Alanları (Inputs) ── */
    QLineEdit, QTextEdit, QComboBox {{
        padding: 6px 12px;
        min-height: 24px;
        border: 1px solid {BORDER};
        border-radius: 8px;
        background: {BG_INPUT};
        color: {TEXT_PRIMARY};
        font-size: 14px;
        selection-background-color: {ACCENT};
        selection-color: #000;
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {BORDER_FOCUS};
    }}
    QComboBox::drop-down {{
        border: none;
    }}

    /* ── Genel Butonlar ── */
    QPushButton {{
        padding: 10px 20px;
        background: rgba(255, 255, 255, 0.05);
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 8px;
        font-size: 13px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background: rgba(255, 255, 255, 0.1);
    }}
    
    /* ── Birincil (Primary/Kaydet) Butonu ── */
    QPushButton#btn_save, QPushButton#btn_accent {{
        background: {ACCENT_BG};
        color: #000000;
        border: none;
        font-weight: bold;
    }}
    QPushButton#btn_save:hover, QPushButton#btn_accent:hover {{
        background: {ACCENT_HOVER};
    }}
    QPushButton#btn_save:disabled {{
        background: rgba(255, 255, 255, 0.05);
        color: {TEXT_MUTED};
        border: 1px solid {BORDER};
    }}

    /* ── İkincil Opsiyonlar (Secondary) ── */
    QPushButton#btn_secondary {{
        background: transparent;
        border: 1px solid {BORDER};
        color: {TEXT_PRIMARY};
    }}
    QPushButton#btn_secondary:hover {{
        background: rgba(255, 255, 255, 0.08);
    }}

    /* ── Splitter ── */
    QSplitter::handle {{
        background: {BORDER};
        width: 1px;
    }}

    /* ── Durum Çubuğu ── */
    QStatusBar {{
        background: rgba(0, 0, 0, 0.6);
        color: {TEXT_SECONDARY};
        font-size: 12px;
        border-top: 1px solid {BORDER};
    }}

    /* ── Paneller ve Kartlar ── */
    QScrollArea {{
        border: 1px solid {BORDER};
        border-radius: 12px;
        background: {BG_PANEL};
    }}

    QFrame#props_frame, QFrame#card {{
        background: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 16px;
    }}

    /* ── ScrollBar ── */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(255, 255, 255, 0.15);
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: rgba(255, 255, 255, 0.3);
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
    }}
    QScrollBar::handle:horizontal {{
        background: rgba(255, 255, 255, 0.15);
        border-radius: 4px;
        min-width: 20px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* ── Tablo (QTableWidget) ── */
    QTableWidget {{
        background: {BG_PANEL};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 12px;
        gridline-color: rgba(255, 255, 255, 0.05);
        font-size: 13px;
        selection-background-color: rgba(0, 212, 170, 0.2);
    }}
    QHeaderView::section {{
        background: rgba(0, 212, 170, 0.1);
        color: {ACCENT};
        padding: 10px;
        border: none;
        border-bottom: 1px solid {BORDER};
        font-weight: bold;
        font-size: 12px;
    }}

    /* ── Progress Bar ── */
    QProgressBar {{
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid {BORDER};
        border-radius: 6px;
        text-align: center;
        color: {TEXT_PRIMARY};
        height: 12px;
    }}
    QProgressBar::chunk {{
        background: {ACCENT_BG};
        border-radius: 5px;
    }}
"""

def apply_theme(window):
    """Ana pencereye Özel Glassmorphism temasını uygular."""
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#0d0d14"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.ColorRole.Base, QColor("#000000"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#111118"))
    pal.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.ColorRole.Button, QColor("#1f1f2e"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
    
    QApplication.instance().setPalette(pal)
    window.setStyleSheet(STYLES)
