import os
import sys
import shutil
import tempfile
import atexit
import logging
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF

logger = logging.getLogger("Utils")

# ═══════════════════ YOLLAR ═══════════════════

def get_base_dir() -> str:
    """Uygulamanın çalıştığı ana dizini döndürür (PyInstaller OneDir uyumlu)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__))

def get_resource_dir() -> str:
    """Okunabilir asset/resource dosyalarının yerini döndürür."""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__))

# ═══════════════════ GÜVENLİ TEMP DİZİNİ ═══════════════════

_TEMP_DIR = None  # Modül seviyesinde tek referans

def get_temp_dir() -> str:
    """
    Uygulama için güvenli bir geçici klasör döndürür.
    Windows'ta %TEMP%/SivasBelediyesiDMS altına yazar.
    Erişim hatası olursa kullanıcının Desktop'ına düşer.
    """
    global _TEMP_DIR
    if _TEMP_DIR and os.path.isdir(_TEMP_DIR):
        return _TEMP_DIR

    candidates = [
        os.path.join(tempfile.gettempdir(), "SivasBelediyesiDMS"),
        os.path.join(os.path.expanduser("~"), "Desktop", "SivasBelediyesiDMS_temp"),
        os.path.join(os.path.expanduser("~"), "SivasBelediyesiDMS_temp"),
    ]

    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            # Yazma testi
            test_file = os.path.join(path, ".write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            _TEMP_DIR = path
            logger.info(f"Geçici dizin: {path}")
            return path
        except (PermissionError, OSError) as e:
            logger.warning(f"Geçici dizin oluşturulamadı ({path}): {e}")
            continue

    # Son çare: tempfile modülünün kendi dizini
    _TEMP_DIR = tempfile.gettempdir()
    return _TEMP_DIR

def cleanup_temp_dir():
    """Uygulama kapanırken geçici dosyaları güvenle temizler."""
    global _TEMP_DIR
    if _TEMP_DIR and os.path.isdir(_TEMP_DIR):
        try:
            shutil.rmtree(_TEMP_DIR, ignore_errors=True)
            logger.info(f"Geçici dizin temizlendi: {_TEMP_DIR}")
        except Exception as e:
            logger.warning(f"Geçici dizin temizlenemedi: {e}")

# Uygulama kapanırken otomatik temizlik
atexit.register(cleanup_temp_dir)

# ═══════════════════ DİZİN YARDIMCILARI ═══════════════════

def ensure_dir(path: str) -> str:
    """
    Belirtilen dizinin var olduğundan emin olur.
    Erişim hatası alırsa alternatif yolları dener.
    Her zaman gerçek kullanılabilir yolu döndürür.
    """
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except (PermissionError, OSError) as e:
        logger.warning(f"Dizin oluşturulamadı ({path}): {e}")
        # Alternatif: temp dizini altında oluştur
        fallback = os.path.join(get_temp_dir(), os.path.basename(path))
        try:
            os.makedirs(fallback, exist_ok=True)
            logger.info(f"Alternatif dizin kullanılıyor: {fallback}")
            return fallback
        except Exception:
            return get_temp_dir()

# ═══════════════════ ARŞİVLEME ═══════════════════

def create_searchable_pdf(image_path: str, output_pdf_path: str, lang: str = "tur") -> bool:
    """Görüntüyü Aranabilir (Searchable) PDF'e çevirir (Tesseract metin katmanıyla)."""
    try:
        import pytesseract
        from PIL import Image
        from config_manager import ConfigManager
        
        config = ConfigManager()
        configured_tess = config.get("tesseract_cmd", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        ocr_lang = config.get("ocr_language", lang)
        
        # Olası Tesseract yolları (Kullanıcı AppData'ya da kurmuş olabilir)
        common_paths = [
            configured_tess,
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Programs\Tesseract-OCR\tesseract.exe")
        ]
        
        valid_tess_cmd = None
        for p in common_paths:
            if p and os.path.exists(p):
                valid_tess_cmd = p
                break
                
        if valid_tess_cmd:
            pytesseract.pytesseract.tesseract_cmd = valid_tess_cmd
        else:
            logger.warning("Tesseract executable bulunamadı, Aranabilir PDF oluşturulamıyor.")
            return False
            
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(image_path, extension='pdf', lang=ocr_lang)
        with open(output_pdf_path, 'wb') as f:
            f.write(pdf_bytes)
        logger.info(f"Aranabilir PDF oluşturuldu: {output_pdf_path}")
        return True
    except Exception as e:
        logger.error(f"Searchable PDF oluşturma hatası: {e}")
        return False

def archive_document(source_path: str, mahalle: str, ada: str) -> str:
    """
    Belgeyi işlem sonrası arşiv klasörüne taşır/kopyalar.
    Eğer dosya resim ise, varsayılan olarak Tesseract ile Aranabilir PDF'e (Searchable PDF) dönüştürülüp öyle arşivlenir.
    Format: evrak_arsiv/{mahalle}/ADA_{ada}/{dosya_adi}
    """
    if not source_path or not os.path.exists(source_path):
        raise FileNotFoundError(f"Kaynak dosya bulunamadı: {source_path}")

    safe_mahalle = str(mahalle).strip().upper() if mahalle else "BILINMEYEN_MAHALLE"
    safe_ada = str(ada).strip().upper() if ada else "BILINMIYOR"

    archive_base = Path(get_base_dir()) / "evrak_arsiv"
    target_dir = archive_base / safe_mahalle / f"ADA_{safe_ada}"
    
    actual_dir = ensure_dir(str(target_dir))

    filename = os.path.basename(source_path)
    base_name, ext = os.path.splitext(filename)
    
    target_path = ""
    
    # Resim dosyası ise Aranabilir PDF yapmayı dene
    if ext.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
        pdf_filename = f"{base_name}.pdf"
        target_path = os.path.join(actual_dir, pdf_filename)
        success = create_searchable_pdf(source_path, target_path)
        
        # Tesseract çalışmazsa klasike resim kopyasına geri dön
        if not success:
            logger.warning("PDF oluşturulamadı, resim olarak kopyalanıyor...")
            target_path = os.path.join(actual_dir, filename)
            shutil.copy2(source_path, target_path)
    else:
        # Zaten PDF ise veya farklı bir dosya ise doğrudan kopyala
        target_path = os.path.join(actual_dir, filename)
        shutil.copy2(source_path, target_path)

    return str(target_path)

# ═══════════════════ PDF ═══════════════════

def convert_pdf_to_image(pdf_path: str, output_path: str = None, page_num: int = 0) -> str:
    """PDF dosyasının belirtilen sayfasını JPEG resmine çevirir."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF bulunamadı: {pdf_path}")

    doc = fitz.open(pdf_path)
    if page_num >= len(doc):
        page_num = 0
    page = doc.load_page(page_num)
    pix = page.get_pixmap(dpi=300)
    
    if output_path is None:
        # Preview'ları temp dizinine yaz (uygulama dizininden çıkar)
        base = os.path.splitext(os.path.basename(pdf_path))[0]
        output_path = os.path.join(get_temp_dir(), f"{base}_preview.jpg")
        
    pix.save(output_path)
    doc.close()
    return output_path

def get_preview_image(file_path: str) -> str:
    """Eğer dosya PDF ise resme çevirir, JPEG ise doğrudan yolunu döndürür."""
    if file_path.lower().endswith(".pdf"):
        return convert_pdf_to_image(file_path)
    return file_path

# ═══════════════════ THUMBNAIL ═══════════════════

def generate_thumbnail(file_path: str, size: tuple = (120, 160)) -> str:
    """
    Dosyanın küçük resim (thumbnail) versiyonunu oluşturur.
    Thumbnail'ler Windows %TEMP% klasörüne kaydedilir (güvenli).
    """
    thumb_dir = os.path.join(get_temp_dir(), "thumbnails")
    ensure_dir(thumb_dir)
    
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    thumb_path = os.path.join(thumb_dir, f"{base_name}_thumb.jpg")
    
    # Zaten üretilmişse tekrar üretme
    if os.path.exists(thumb_path):
        return thumb_path
    
    try:
        if file_path.lower().endswith(".pdf"):
            doc = fitz.open(file_path)
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=72)  # Thumbnail için düşük DPI yeterli
            pix.save(thumb_path)
            doc.close()
            # Resize with Pillow
            img = Image.open(thumb_path)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumb_path, "JPEG", quality=85)
            img.close()
        else:
            img = Image.open(file_path)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumb_path, "JPEG", quality=85)
            img.close()
    except Exception:
        # Hata olursa boş bir placeholder döndür
        img = Image.new("RGB", size, (60, 60, 60))
        img.save(thumb_path, "JPEG")
        img.close()
    
    return thumb_path

# ═══════════════════ YARDIMCILAR ═══════════════════

def get_pdf_page_count(file_path: str) -> int:
    """PDF dosyasının sayfa sayısını döndürür. PDF değilse 1 döner."""
    if file_path.lower().endswith(".pdf"):
        try:
            doc = fitz.open(file_path)
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 1
    return 1

def extract_text_from_file(file_path: str) -> str:
    """
    Dosyadan ham metni doğrudan çıkarır (AI kullanmadan).
    PDF → PyMuPDF text extraction (tüm sayfalar).
    Resim → PyMuPDF OCR veya boş string.
    """
    if not os.path.exists(file_path):
        return ""
    
    try:
        if file_path.lower().endswith(".pdf"):
            doc = fitz.open(file_path)
            full_text = []
            for page in doc:
                text = page.get_text("text")
                if text and text.strip():
                    full_text.append(text.strip())
            doc.close()
            return "\n".join(full_text)
        else:
            # Resim dosyası — PyMuPDF ile OCR dene
            try:
                doc = fitz.open(file_path)
                page = doc[0]
                text = page.get_text("text")
                doc.close()
                return text.strip() if text else ""
            except Exception:
                return ""
    except Exception:
        return ""

def release_pixmap(pixmap_ref):
    """QPixmap nesnesini güvenli şekilde serbest bırakır (dosya kilidini kaldırır)."""
    if pixmap_ref is not None:
        try:
            from PyQt6.QtGui import QPixmap
            pixmap_ref = QPixmap()  # Boş pixmap ile değiştir → dosya kilidi kalkar
        except Exception:
            pass
    return None
