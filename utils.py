import os
import sys
import shutil
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF

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

def ensure_dir(path: str) -> None:
    """Belirtilen dizinin var olduğundan emin olur, yoksa oluşturur."""
    os.makedirs(path, exist_ok=True)

def archive_document(source_path: str, mahalle: str, ada: str) -> str:
    """
    Belgeyi işlem sonrası arşiv klasörüne taşır/kopyalar.
    Format: evrak_arsiv/{mahalle}/ADA_{ada}/{dosya_adi}
    """
    if not source_path or not os.path.exists(source_path):
        raise FileNotFoundError(f"Kaynak dosya bulunamadı: {source_path}")

    safe_mahalle = str(mahalle).strip().upper() if mahalle else "BILINMEYEN_MAHALLE"
    safe_ada = str(ada).strip().upper() if ada else "BILINMIYOR"

    archive_base = Path("evrak_arsiv")
    target_dir = archive_base / safe_mahalle / f"ADA_{safe_ada}"
    
    ensure_dir(str(target_dir))

    filename = os.path.basename(source_path)
    target_path = target_dir / filename

    shutil.copy2(source_path, target_path)
    return str(target_path)

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
        base = os.path.splitext(pdf_path)[0]
        output_path = f"{base}_preview.jpg"
        
    pix.save(output_path)
    doc.close()
    return output_path

def get_preview_image(file_path: str) -> str:
    """Eğer dosya PDF ise resme çevirir, JPEG ise doğrudan yolunu döndürür."""
    if file_path.lower().endswith(".pdf"):
        return convert_pdf_to_image(file_path)
    return file_path

def generate_thumbnail(file_path: str, size: tuple = (120, 160)) -> str:
    """
    Dosyanın küçük resim (thumbnail) versiyonunu oluşturur.
    Thumbnail'ler temp_previews/ klasörüne kaydedilir.
    """
    ensure_dir("temp_previews")
    
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    thumb_path = os.path.join("temp_previews", f"{base_name}_thumb.jpg")
    
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
        else:
            img = Image.open(file_path)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumb_path, "JPEG", quality=85)
    except Exception:
        # Hata olursa boş bir placeholder döndür
        img = Image.new("RGB", size, (60, 60, 60))
        img.save(thumb_path, "JPEG")
    
    return thumb_path

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


